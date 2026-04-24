import asyncio
import base64
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from starlette.responses import JSONResponse

from asset_store import save_uploaded_asset
from caption_agent import generate_caption_payload
from client_store import get_client_store
from draft_store import list_client_drafts, save_draft_payload
from orchestrator_agent import RequestApprovalTool, TriggerPipelineNowTool, resolve_client_id
from public_base_url import get_public_base_url
from runtime_state_store import (
    delete_operator_session_state,
    get_operator_session_state,
    record_operator_audit_event,
    save_operator_session_state,
)
from schedule_store import load_schedule, split_schedule_views
from schedule_utils import parse_time_string, resolve_date_phrase
from strategy_agent import (
    build_strategy_request_from_prompt,
    format_strategy_plan_messages,
    prompt_requests_strategy,
    run_strategy_agent,
    summarize_strategy_plan_reply,
)
from strategy_plan_store import get_strategy_plan, list_strategy_plans
from whatsapp_transport import (
    fetch_media_bytes,
    get_agency_config,
    normalize_phone,
    send_button_message,
    send_list_message,
    send_text_message,
)

ONBOARDING_STEPS = [
    ("business_name", "What is the brand or business name?"),
    ("business_type", "What type of business is this?\nExamples: restaurant, gym, fashion brand, dental clinic"),
    ("main_language", "What is the main language?"),
    ("what_they_sell", "What do they sell or offer?"),
    ("target_audience", "Who is the target audience?"),
    ("brand_tone", "What is the brand tone?\nExamples: bold, premium, playful, warm"),
    ("products_examples", "Give 3 to 5 product or service examples."),
    ("city_market", "What city or market do they serve?"),
    ("words_to_avoid", "What words should Jarvis avoid?\nThis is optional. Reply with the words, or say skip."),
    ("inspiration_links", "Which competitors, inspirations, or references matter?\nThis is optional. Reply with names or links, or say skip."),
]

TIME_WINDOW_RE = re.compile(r"\b(?:\d{1,2}:\d{2}(?:\s*(?:am|pm))?|\d{1,2}\s*(?:am|pm))\b", re.IGNORECASE)
ROBUST_CLIENT_MENTION_RE = re.compile(r"@\[(?P<client>[^\]]+)\]")
RAW_CLIENT_MENTION_RE = re.compile(r"(?<!\[)@(?P<client>[A-Za-z0-9_-]+)")
DATE_PATTERNS = [
    re.compile(r"\b(?:today|tonight|tomorrow)\b", re.IGNORECASE),
    re.compile(r"\bnext\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.IGNORECASE),
    re.compile(r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.IGNORECASE),
    re.compile(r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}\b", re.IGNORECASE),
]
CONNECT_SCOPE = ",".join(
    [
        "pages_show_list",
        "pages_read_engagement",
        "pages_manage_posts",
        "instagram_basic",
        "instagram_content_publish",
        "business_management",
    ]
)

_BACKGROUND_TASKS: set[asyncio.Task] = set()
_META_HEALTH_CACHE: dict[str, dict[str, Any]] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_client_label(client_id: str, business_name: str | None = None) -> str:
    label = str(business_name or client_id or "").replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in label.split()) or "Client"


def _normalize_text(value: str | None) -> str:
    return str(value or "").strip()


def _coerce_api_result(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, JSONResponse):
        try:
            body = value.body.decode("utf-8") if isinstance(value.body, (bytes, bytearray)) else str(value.body or "")
            parsed = json.loads(body)
            return parsed if isinstance(parsed, dict) else {"status": "error", "reason": body}
        except Exception:
            return {"status": "error", "reason": str(value)}
    return {"status": "error", "reason": str(value)}


def _session_payload(phone: str) -> dict[str, Any]:
    record = get_operator_session_state(normalize_phone(phone)) or {}
    payload = record.get("payload_json") or {}
    return dict(payload) if isinstance(payload, dict) else {}


def _save_session(phone: str, payload: dict[str, Any]) -> dict[str, Any]:
    return save_operator_session_state(normalize_phone(phone), payload)


def _clear_session(phone: str) -> bool:
    return delete_operator_session_state(normalize_phone(phone))


def _spawn_background(coro):
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(lambda finished: _BACKGROUND_TASKS.discard(finished))
    return task


def _audit(phone: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
    try:
        record_operator_audit_event(
            event_type=event_type,
            payload=payload or {},
            actor=normalize_phone(phone),
        )
    except Exception:
        pass


def is_operator_phone(phone: str) -> bool:
    owner_phone = normalize_phone(get_agency_config().get("owner_phone"))
    return bool(owner_phone and normalize_phone(phone) == owner_phone)


def _client_rows() -> list[dict[str, Any]]:
    rows = []
    store = get_client_store()
    if not hasattr(store, "list_clients"):
        return []
    for client in (store.list_clients() or []):
        client_id = str(client.get("client_id") or "").strip()
        if not client_id:
            continue
        profile = client.get("profile_json") or {}
        business_name = str(profile.get("business_name") or "").strip()
        rows.append(
            {
                "client_id": client_id,
                "display_name": _format_client_label(client_id, business_name),
                "connected": bool(str(client.get("instagram_account_id") or "").strip()),
                "profile": profile,
                "meta_health": _client_meta_health(client_id, client),
            }
        )
    rows.sort(key=lambda item: item["display_name"].lower())
    return rows


def _client_meta_health(client_id: str, client_payload: dict[str, Any] | None = None, force_refresh: bool = False) -> dict[str, Any]:
    if not client_id:
        return {"ok": False, "status": "missing", "detail": "Client ID is missing."}
    if not force_refresh and client_id in _META_HEALTH_CACHE:
        cached = dict(_META_HEALTH_CACHE[client_id])
        cached["probe_source"] = "cached"
        return cached
    try:
        from webhook_server import check_meta_health_for_client

        health = check_meta_health_for_client(client_id, client_payload=client_payload, mode="direct")
        _META_HEALTH_CACHE[client_id] = dict(health)
        return health
    except Exception as exc:
        return {"ok": False, "status": "unknown", "detail": f"Meta status check failed: {exc}"}


def _clear_meta_health_cache() -> None:
    _META_HEALTH_CACHE.clear()


def _meta_status_label(health: dict[str, Any]) -> str:
    status = str((health or {}).get("status") or "").strip().lower()
    if status == "connected":
        label = "Meta connected"
    elif status == "expired_or_invalid":
        label = "Meta expired"
    elif status == "missing":
        label = "Meta not linked"
    else:
        label = "Meta unknown"
    if str((health or {}).get("probe_source") or "").strip() == "cached":
        label += " (cached)"
    return label


def _build_missing_fields_template(display_name: str, missing_fields: list[str]) -> str:
    header = f"*Almost ready for {display_name}* \u2726\n"
    body = "I have built most of the client profile already.\nI still need these details before I can save it:\n\n"
    for index, field in enumerate(missing_fields, start=1):
        body += f"{index}. {field}\n"
    body += "\nReply with the completed mini-brief in one message."
    return header + body


def _send_button_card(phone: str, *, header_text: str = "", body_text: str = "", buttons: list[dict] | None = None, footer_text: str = "", fallback_text: str = "", audit_event: str = "") -> dict[str, Any]:
    if audit_event:
        _audit(phone, "operator.interactive.button", {"event": audit_event})
    result = send_button_message(phone, header_text=header_text, body_text=body_text, buttons=buttons or [], footer_text=footer_text)
    if not result.get("success") and fallback_text:
        send_text_message(phone, fallback_text)
    return result


def _send_list_card(phone: str, *, header_text: str = "", body_text: str = "", button_text: str = "", sections: list[dict] | None = None, footer_text: str = "", fallback_text: str = "", audit_event: str = "") -> dict[str, Any]:
    if audit_event:
        _audit(phone, "operator.interactive.list", {"event": audit_event})
    result = send_list_message(phone, header_text=header_text, body_text=body_text, button_text=button_text, sections=sections or [], footer_text=footer_text)
    if not result.get("success") and fallback_text:
        send_text_message(phone, fallback_text)
    return result


def _send_back_button(phone: str, label: str = "", target: str = "") -> dict[str, Any]:
    body = label or "Need to go back without restarting the flow?"
    nav_id = f"OP_NAV:{target}" if target else "OP_NAV:ROOT"
    return send_button_message(
        phone,
        header_text="Navigation",
        body_text=body,
        buttons=[{"id": nav_id, "title": "Go Back"}],
        footer_text="Jarvis \u00b7 Navigation",
    )


def _root_menu_context(session: dict[str, Any]) -> str:
    mode = str(session.get("mode") or "").strip()
    if not mode:
        return ""
    context_map = {
        "client_pick": "An active client selection is still open, but you can start somewhere else below.",
        "awaiting_media": f"A draft is still open for {_format_client_label(str(session.get('client_id') or ''))}.",
        "media_collect": "A media bundle is still being collected in the background.",
        "preview": f"A preview is still open for {_format_client_label(str(session.get('client_id') or ''))}.",
        "strategy_prompt": f"A strategy brief is still open for {_format_client_label(str(session.get('client_id') or ''))}.",
        "strategy_menu": f"The strategy workspace is open for {_format_client_label(str(session.get('client_id') or ''))}.",
        "strategy_plan_pick": f"A saved-strategy list is open for {_format_client_label(str(session.get('client_id') or ''))}.",
        "onboarding_form": "A client intake draft is still open. You can return to it or start another action.",
        "add_client_mode_picker": "The Add Client options are open below.",
        "awaiting_client_brief_document": "Jarvis is waiting for a client brief document.",
        "awaiting_client_website_url": "Jarvis is waiting for a website URL.",
        "onboarding_missing_fields": "Jarvis is waiting for the missing client details before saving.",
    }
    if mode == "onboarding_build":
        name = str(session.get("building_client_name") or "").strip() or "that client"
        return f"{name} is still being built in the background."
    return context_map.get(mode, "")


def _get_client_row(client_id: str) -> dict[str, Any] | None:
    resolved = resolve_client_id(client_id)
    for row in _client_rows():
        if row["client_id"].lower() == resolved.lower():
            return row
    return None


def _extract_client_id_from_text(text: str) -> str:
    raw = str(text or "").strip()
    robust = ROBUST_CLIENT_MENTION_RE.search(raw)
    if robust:
        return resolve_client_id(robust.group("client"))
    loose = RAW_CLIENT_MENTION_RE.search(raw)
    if loose:
        return resolve_client_id(loose.group("client"))
    normalized = re.sub(r"\s+", " ", raw.replace("_", " ").replace("-", " ")).strip().lower()
    if raw.startswith("@"):
        for row in sorted(_client_rows(), key=lambda item: len(item["display_name"]), reverse=True):
            display = row["display_name"].lower()
            if raw.lower().startswith(f"@{display}") or raw.lower().startswith(f"@[{display}]"):
                return row["client_id"]
    for row in _client_rows():
        if normalized == row["display_name"].lower():
            return row["client_id"]
    return ""


def _build_client_picker_sections(prefix: str = "OP_CLIENT_PICK") -> list[dict[str, Any]]:
    rows = []
    for row in _client_rows()[:10]:
        health = row.get("meta_health") or {}
        status = str(health.get("status") or "").strip().lower()
        if status == "connected":
            desc = "Meta connected"
        elif status == "expired_or_invalid":
            desc = "Meta expired"
        elif status == "missing":
            desc = "Meta not linked"
        elif row["connected"]:
            desc = "Connected"
        else:
            desc = "Needs Meta connection"
        rows.append(
            {
                "id": f"{prefix}:{row['client_id']}",
                "title": row["display_name"],
                "description": desc,
            }
        )
    return [{"title": "Clients", "rows": rows}] if rows else []


def _help_text() -> str:
    return (
        "Jarvis WhatsApp operator shortcuts:\n"
        "- Type Hey Jarvis, menu, or /help to open the operator menu\n"
        "- You can still type /addclient, /clients, /schedules, /status, /strategy, or /connect\n\n"
        "Media workflow:\n"
        "- Send images or videos as Document, not Gallery\n"
        "- 1 image document = image post\n"
        "- 2 or more image documents within 10 seconds = carousel\n"
        "- 1 video document = reel/video post\n\n"
        "Preview replies:\n"
        "- yes\n"
        "- change make it more casual\n"
        "- schedule tomorrow 7pm\n"
        "- cancel"
    )


def _build_onboarding_prompt(index: int) -> str:
    total = len(ONBOARDING_STEPS)
    _key, prompt = ONBOARDING_STEPS[index]
    intro = "Let’s add a new client.\n\n" if index == 0 else ""
    return f"{intro}Step {index + 1} of {total}\n{prompt}"


def _send_onboarding_prompt(phone: str, index: int) -> None:
    key, _prompt = ONBOARDING_STEPS[index]
    prompt_text = _build_onboarding_prompt(index)
    if key == "main_language":
        result = send_button_message(
            phone,
            header_text="Jarvis Intake",
            body_text=prompt_text,
            buttons=[
                {"id": "OP_ONBOARD_LANG:arabic", "title": "Arabic"},
                {"id": "OP_ONBOARD_LANG:english", "title": "English"},
                {"id": "OP_ONBOARD_LANG:both", "title": "Both"},
            ],
            footer_text="You can also type the answer manually.",
        )
        if result.get("success"):
            return
    send_text_message(phone, prompt_text)


def _send_add_client_mode_picker(phone: str) -> None:
    _send_button_card(
        phone,
        header_text="New Client",
        body_text="Choose the fastest intake path for this client.",
        buttons=[
            {"id": "OP_ADD_CLIENT:QUICK", "title": "Quick Brief"},
            {"id": "OP_ADD_CLIENT:IMPORT", "title": "Import Brief"},
            {"id": "OP_ADD_CLIENT:WEBSITE", "title": "Scan Website"},
        ],
        footer_text="Jarvis \u00b7 Add Client",
        fallback_text="New Client:\n1. Quick Brief\n2. Import Brief\n3. Scan Website",
        audit_event="add_client_mode_picker",
    )
    _send_back_button(phone, "Need to go back to the main Jarvis menu?", "ROOT")


def _send_root_menu(phone: str) -> None:
    session = _session_payload(phone)
    rows = _client_rows()
    connected_count = sum(1 for r in rows if r["connected"])
    schedule = _safe_load_schedule_jobs()
    active, _history = split_schedule_views(schedule)
    active_count = len(active or [])
    dashboard = (
        "\u26a1 *Jarvis \u00b7 Agency OS*\n\n"
        "\U0001f1f0\U0001f1fc  *United Marketing Agency*\n"
        "_Your dedicated AI operator is online and standing by._\n\n"
        "\u2500\u2500\u2500  *Live Dashboard*  \u2500\u2500\u2500\n"
        f"* {len(rows)} client{'s' if len(rows) != 1 else ''} loaded\n"
        f"* {connected_count} Meta account{'s' if connected_count != 1 else ''} connected\n"
        f"* {active_count} release{'s' if active_count != 1 else ''} queued\n"
        "\u2699\ufe0f  All systems operational\n\n"
    )
    context = _root_menu_context(session)
    if context:
        dashboard += f"{context}\n\n"
    dashboard += "What would you like to do?"
    result = send_button_message(
        phone,
        header_text="Jarvis",
        body_text=dashboard,
        buttons=[
            {"id": "OP_MENU:POST", "title": "New Post"},
            {"id": "OP_MENU:ADD_CLIENT", "title": "Add Client"},
            {"id": "OP_MENU:MORE", "title": "More"},
        ],
        footer_text="Jarvis \u00b7 WhatsApp Operator",
    )
    if not result.get("success"):
        send_text_message(phone, _help_text())


def _send_more_menu(phone: str) -> None:
    _audit(phone, "more_menu", {})
    result = send_list_message(
        phone,
        header_text="Operator Menu",
        body_text="*Operator Actions* \u2726\nChoose the next workspace or check a live system summary.",
        button_text="View Actions",
        sections=[
            {
                "title": "Operator Actions",
                "rows": [
                    {"id": "OP_MORE:STRATEGY", "title": "Strategy", "description": "Research-backed content plan"},
                    {"id": "OP_MORE:CONNECT", "title": "Connect Meta", "description": "Link Facebook + Instagram"},
                    {"id": "OP_MORE:CLIENTS", "title": "Clients", "description": "View saved client roster"},
                    {"id": "OP_MORE:SCHEDULES", "title": "Schedules", "description": "Upcoming releases queue"},
                    {"id": "OP_MORE:STATUS", "title": "Status", "description": "System & connection health"},
                    {"id": "OP_MORE:REFRESH_META", "title": "Refresh Meta Status", "description": "Force-recheck all connections"},
                    {"id": "OP_MORE:HELP", "title": "Help", "description": "Back to main Jarvis menu"},
                ],
            }
        ],
        footer_text="Jarvis \u00b7 Operator",
        fallback_text="Operator Actions:\n1. Strategy\n2. Connect Meta\n3. Clients\n4. Schedules\n5. Status\n6. Refresh Meta Status\n7. Help",
    )
    _send_back_button(phone, "Return to the main Jarvis menu", "ROOT")
    if not result.get("success"):
        send_text_message(phone, _help_text())


def _build_clients_summary() -> str:
    rows = _client_rows()
    if not rows:
        return "*Client Roster* \u2726\nNo clients saved yet.\n\nReply with *Add Client* to create the first one."
    lines = [f"*Client Roster* \u2726\n{len(rows)} saved client(s)"]
    for row in rows[:20]:
        health = row.get("meta_health") or {}
        status = _meta_status_label(health) if health else ("Connected" if row["connected"] else "Needs connect")
        lines.append(f"\u2022 {row['display_name']} [{row['client_id']}] \u2014 {status}")
    lines.append("\n_Meta status may be cached for up to 90 seconds._")
    return "\n".join(lines)


def _safe_load_schedule_jobs() -> list[dict[str, Any]]:
    try:
        schedule = load_schedule("schedule.json")
    except Exception:
        return []
    return list(schedule or [])


def _build_schedules_summary() -> str:
    schedule = _safe_load_schedule_jobs()
    active, _history = split_schedule_views(schedule)
    active = list(active or [])
    if not active:
        return "*Release Queue* \U0001f4c5\nNo schedules yet.\nNo active scheduled releases are queued right now."
    lines = [f"*Release Queue* \U0001f4c5\n{len(active)} scheduled release(s)"]
    for item in active[:12]:
        client_id = str(item.get("client") or "").strip()
        topic = str(item.get("topic") or item.get("draft_name") or "Untitled").strip()
        date_label = str(item.get("scheduled_date") or "").strip() or ", ".join(item.get("days") or [])
        time_label = str(item.get("time") or "").strip()
        lines.append(f"\u2022 {_format_client_label(client_id)}: {topic} | {date_label} {time_label}".strip())
    return "\n".join(lines)


def _build_status_summary() -> str:
    rows = _client_rows()
    connected = sum(1 for row in rows if str((row.get("meta_health") or {}).get("status") or "").strip().lower() == "connected")
    expired = sum(1 for row in rows if str((row.get("meta_health") or {}).get("status") or "").strip().lower() == "expired_or_invalid")
    missing_meta = sum(1 for row in rows if str((row.get("meta_health") or {}).get("status") or "").strip().lower() == "missing")
    unknown_meta = sum(1 for row in rows if str((row.get("meta_health") or {}).get("status") or "").strip().lower() == "unknown")
    schedule = _safe_load_schedule_jobs()
    active_count, history_count = split_schedule_views(schedule)
    active_count = len(active_count or [])
    history_count = len(history_count or [])
    return (
        "*System Status* \u2726\n"
        f"\u2022 Clients: {len(rows)} total\n"
        f"\u2022 Connected Meta accounts: {connected}\n"
        f"\u2022 Expired Meta accounts: {expired}\n"
        f"\u2022 Missing Meta connections: {missing_meta}\n"
        f"\u2022 Meta status unknown: {unknown_meta}\n"
        f"\u2022 Active scheduled jobs: {active_count}\n"
        f"\u2022 Schedule history rows: {history_count}\n"
        f"\u2022 Operator phone: {normalize_phone(get_agency_config().get('owner_phone')) or 'not configured'}\n\n"
        "*Client Meta health*\n"
    )


def _build_caption_progress_callback(phone: str, client_id: str):
    announced = {"drafting": False}

    def callback(event: dict[str, Any]):
        event_name = str(event.get("event") or "").strip()
        if event_name == "drafting_started" and not announced["drafting"]:
            announced["drafting"] = True
            send_text_message(phone, f"*Writing caption* \u270d\ufe0f\nJarvis is crafting the caption for {_format_client_label(client_id)}.")

    return callback


def _send_preview_card(phone: str, session_or_payload: dict[str, Any]) -> None:
    gen_state = str(session_or_payload.get("generation_state") or "").strip()
    caption_payload = dict(session_or_payload.get("caption_payload") or {})
    cp_gen_state = str(caption_payload.get("generation_state") or "").strip()
    if gen_state == "generation_unavailable" or cp_gen_state == "generation_unavailable":
        reason = str(caption_payload.get("reason") or "Jarvis could not produce a real caption draft from the current model route.").strip()
        send_text_message(phone, f"*Caption generation failed* \u26a0\ufe0f\nJarvis could not produce a real caption draft from the current model route.\nReason: {reason}")
        _send_button_card(
            phone,
            header_text="Caption Blocked",
            body_text="A fresh model pass is needed before a caption preview can be shown.",
            buttons=[
                {"id": "OP_PREVIEW:TRY_AGAIN", "title": "Try Again"},
                {"id": "OP_PREVIEW:REVISE", "title": "Revise"},
                {"id": "OP_PREVIEW:CANCEL", "title": "Cancel"},
            ],
            footer_text="No fallback caption is shown when the model route fails.",
            fallback_text="Caption blocked:\n1. Try Again\n2. Revise\n3. Cancel\n\nReply with one of these if you prefer typing: try again, revise, change make the brief sharper and more local, or cancel.",
            audit_event="preview_generation_unavailable",
        )
        return
    client_id = str(session_or_payload.get("client_id") or "").strip()
    display_direction = str(session_or_payload.get("display_direction") or session_or_payload.get("content_goal") or session_or_payload.get("topic") or "").strip()
    media_kind = str(session_or_payload.get("media_kind") or "image_single")
    item_count = int(session_or_payload.get("item_count") or 1)
    send_text_message(phone, _preview_text(client_id, display_direction, caption_payload, media_kind, item_count))
    _send_button_card(
        phone,
        header_text="Next Move",
        body_text="What would you like to do with this draft?",
        buttons=[
            {"id": "OP_PREVIEW:POST_NOW", "title": "Publish Now"},
            {"id": "OP_PREVIEW:SCHEDULE", "title": "Schedule"},
            {"id": "OP_PREVIEW:REVISE", "title": "Revise"},
        ],
        footer_text="You can also reply with text",
        fallback_text="Next move:\n1. Publish Now\n2. Schedule\n3. Revise\n\nReply with one of these if you prefer typing: post now, schedule friday 17 at 6am, revise, change make it sharper and more local, or cancel.",
        audit_event="preview_actions",
    )


def _prompt_preview_schedule(phone: str, session: dict[str, Any]) -> None:
    session["expected_reply"] = "schedule"
    _save_session(phone, session)
    send_text_message(phone, "*Schedule this draft* \U0001f4c5\nSend the release time like: today 2pm, tomorrow 7pm, or friday 17 at 6am.")


def _prompt_preview_revise(phone: str, session: dict[str, Any]) -> None:
    session["expected_reply"] = "revise"
    _save_session(phone, session)
    send_text_message(phone, "*Revise this draft* \u270f\ufe0f\nTell Jarvis what to change. Example: make it sharper, more premium, more local to Kuwait, and shorter.")


def _open_strategy_menu(phone: str, client_id: str) -> None:
    _send_strategy_menu(phone, client_id)


def _send_saved_strategy_plans(phone: str, client_id: str) -> None:
    plans = list_strategy_plans(client_id)
    if not plans:
        send_text_message(phone, f"*Saved Plans* \u2726\nNo research-ready strategy plans exist yet for {_format_client_label(client_id)}.")
        return
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for plan in plans:
        key = " ".join(
            [
                str(plan.get("requested_prompt") or "").strip().lower(),
                str(plan.get("goal") or "").strip().lower(),
                str(plan.get("summary") or "").strip().lower(),
            ]
        ).strip()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(plan)
    rows = []
    for plan in deduped[:10]:
        plan_id = str(plan.get("plan_id") or "").strip()
        window = str(plan.get("window") or "next_30_days").strip()
        updated_at = str(plan.get("updated_at") or "").strip()
        summary = str(plan.get("summary") or "").strip() or f"{len(plan.get('items') or [])} item plan"
        rows.append(
            {
                "id": f"OP_STRATEGY_PLAN:{plan_id}",
                "title": window.replace("_", " ").title(),
                "description": f"{summary} · {updated_at[:10] if updated_at else 'recent'}",
            }
        )
    send_list_message(
        phone,
        header_text="Saved Plans",
        body_text=f"*Saved Plans* \u2726\nChoose a plan for {_format_client_label(client_id)}.",
        button_text="Open plan",
        sections=[{"title": "Strategy Plans", "rows": rows}],
        footer_text="Jarvis \u00b7 Strategy",
    )


def _send_strategy_plan_view(phone: str, plan_id: str) -> None:
    plan = get_strategy_plan(plan_id)
    if not plan:
        send_text_message(phone, "Jarvis could not find that saved strategy plan.")
        return
    messages = format_strategy_plan_messages(plan)
    for message in messages:
        send_text_message(phone, message)


def _parse_missing_field_submission(text: str, missing_fields: list[str]) -> tuple[dict[str, str], list[str]]:
    answers: dict[str, str] = {}
    raw = str(text or "").strip()
    if len(missing_fields) == 1:
        label_pattern = re.compile(r"^\s*(?:[-*]\s*)?(?:" + re.escape(missing_fields[0]) + r")(?:\s*(?::|-|=)\s*|\s+(?:is|are|will be|would be|includes?)\s+)", re.IGNORECASE | re.MULTILINE)
        match = label_pattern.search(raw)
        if match:
            answers[missing_fields[0]] = raw[match.end():].strip()
        else:
            answers[missing_fields[0]] = raw
        return answers, []
    numbered_pattern = re.compile(r"(?ms)^\s*(\d{1,2})[.)]\s*(.+?)(?::\s*|\n)(.*?)(?=^\s*\d{1,2}[.)]\s+|\Z)")
    numbered_matches = numbered_pattern.findall(raw)
    if numbered_matches:
        for _num, _label, value in numbered_matches:
            value = value.strip()
            if value:
                for field in missing_fields:
                    if field not in answers:
                        answers[field] = value
                        break
    if not answers:
        for field in missing_fields:
            label_pattern = re.compile(r"^\s*(?:[-*]\s*)?(?:" + re.escape(field) + r")(?:\s*(?::|-|=)\s*|\s+(?:is|are|will be|would be|includes?)\s+)", re.IGNORECASE | re.MULTILINE)
            match = label_pattern.search(raw)
            if match:
                end = raw.find("\n", match.end())
                answers[field] = raw[match.end():end].strip() if end > 0 else raw[match.end():].strip()
    unresolved = [f for f in missing_fields if f not in answers]
    return answers, unresolved


def _extract_hashtags(text: str) -> list[str]:
    return [match.group(0) for match in re.finditer(r"#[\w\u0600-\u06FF]+", str(text or ""))]


async def _handle_missing_fields_reply(phone: str, text: str, session: dict[str, Any]) -> None:
    missing_fields = list(session.get("missing_fields") or [])
    provisional_name = str(session.get("provisional_client_name") or "this client").strip()
    candidate_profile = dict(session.get("candidate_profile") or {})
    answers, unresolved = _parse_missing_field_submission(text, missing_fields)
    if unresolved:
        send_text_message(phone, _build_missing_fields_template(provisional_name, unresolved))
        return
    candidate_profile.update({field.replace(" ", "_").lower(): value for field, value in answers.items()})
    session = {
        "mode": "onboarding_build",
        "candidate_profile": candidate_profile,
        "provisional_client_name": provisional_name,
        "source_mode": str(session.get("source_mode") or "").strip(),
        "updated_at": _utc_now_iso(),
    }
    _save_session(phone, session)
    send_text_message(phone, f"Missing details received for {provisional_name}. Jarvis is finishing the brand profile now.")
    _spawn_background(_complete_onboarding(phone, candidate_profile if candidate_profile else answers))


async def _handle_synthesized_candidate(
    phone: str,
    synthesis_result: dict[str, Any],
    *,
    provisional_name: str = "",
    source_mode: str = "",
) -> None:
    status = str(synthesis_result.get("status") or "").strip().lower()
    reason = str(synthesis_result.get("reason") or synthesis_result.get("detail") or "").strip()
    missing_fields = list(synthesis_result.get("missing_fields") or [])
    if status in {"error", "failed"}:
        send_text_message(
            phone,
            (
                "*Client build paused* \u26a0\ufe0f\n"
                f"I could not finish the brand profile for {provisional_name or 'this client'} yet.\n"
                f"Reason: {reason or 'Provider rejected the request.'}"
            ),
        )
        return
    if missing_fields:
        session = {
            "mode": "onboarding_missing_fields",
            "provisional_client_name": provisional_name,
            "source_mode": source_mode,
            "missing_fields": missing_fields,
            "candidate_profile": dict(synthesis_result.get("data") or {}),
            "updated_at": _utc_now_iso(),
        }
        _save_session(phone, session)
        send_text_message(phone, _build_missing_fields_template(provisional_name or "this client", missing_fields))
        return
    data = dict(synthesis_result.get("data") or {})
    if not data:
        send_text_message(
            phone,
            (
                "*Client build paused* \u26a0\ufe0f\n"
                f"I could not finish the brand profile for {provisional_name or 'this client'} yet.\n"
                "Reason: The provider returned an empty profile."
            ),
        )
        return
    session = {
        "mode": "onboarding_build",
        "candidate_profile": data,
        "provisional_client_name": provisional_name,
        "source_mode": source_mode,
        "updated_at": _utc_now_iso(),
    }
    _save_session(phone, session)
    _spawn_background(_complete_onboarding(phone, data))


def _send_strategy_menu(phone: str, client_id: str) -> None:
    _save_session(phone, {"mode": "strategy_menu", "client_id": client_id, "updated_at": _utc_now_iso()})
    _audit(phone, "strategy_menu", {"client_id": client_id})
    send_button_message(
        phone,
        header_text="Strategy",
        body_text=f"*Strategy* \U0001f4ca \u2014 {_format_client_label(client_id)}\nBuild a new research-backed plan or open a saved one.",
        buttons=[
            {"id": "OP_STRATEGY:BUILD", "title": "New Plan"},
            {"id": "OP_STRATEGY:VIEW", "title": "Saved Plans"},
            {"id": "OP_NAV:MORE", "title": "Go Back"},
        ],
        footer_text="Jarvis \u00b7 Strategy",
    )


def _slugify_client_id(business_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(business_name or "").strip().lower()).strip("_")
    return slug or f"client_{uuid.uuid4().hex[:6]}"


def _unique_client_id(business_name: str) -> str:
    base = _slugify_client_id(business_name)
    existing = {row["client_id"].lower() for row in _client_rows()}
    if base.lower() not in existing:
        return base
    for index in range(2, 50):
        candidate = f"{base}_{index}"
        if candidate.lower() not in existing:
            return candidate
    return f"{base}_{uuid.uuid4().hex[:4]}"


def _recent_client_captions(client_id: str, *, exclude_bundle_name: str | None = None) -> list[str]:
    bundles = list_client_drafts(client_id).get("bundles", {})
    entries: list[str] = []
    for bundle_name, payload in (bundles or {}).items():
        if exclude_bundle_name and str(bundle_name).strip() == str(exclude_bundle_name).strip():
            continue
        caption_text = str((payload or {}).get("caption_text") or "").strip()
        if caption_text:
            entries.append(caption_text)
    return entries[-5:][::-1]


def _derive_topic(source_text: str, client_id: str, media_kind: str, asset_count: int) -> str:
    cleaned = ROBUST_CLIENT_MENTION_RE.sub("", str(source_text or ""))
    cleaned = RAW_CLIENT_MENTION_RE.sub("", cleaned)
    cleaned = re.sub(r"^\s*/\w+\s*", "", cleaned).strip(" -:\n")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned:
        return cleaned
    if media_kind == "video":
        return f"{_format_client_label(client_id)} reel concept"
    if asset_count > 1:
        return f"{_format_client_label(client_id)} carousel concept"
    return f"{_format_client_label(client_id)} image post"


def _infer_media_bundle(media_refs: list[dict[str, Any]]) -> tuple[str, str]:
    image_count = sum(1 for item in media_refs if str(item.get("kind") or "").strip() == "image")
    video_count = sum(1 for item in media_refs if str(item.get("kind") or "").strip() == "video")
    if video_count > 1 or (video_count and image_count):
        return "invalid", "Phase 1 supports either one video document or one-or-more image documents, but not mixed media bundles."
    if video_count == 1:
        return "video", ""
    if image_count >= 2:
        return "image_carousel", ""
    if image_count == 1:
        return "image_single", ""
    return "invalid", "No publishable media documents were collected."


def _safe_asset_filename(client_id: str, original_name: str, index: int, mime_type: str) -> str:
    stem, ext = os.path.splitext(str(original_name or "").strip())
    ext = ext.lower()
    if not ext:
        ext = ".mp4" if str(mime_type or "").startswith("video/") else ".jpg"
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "whatsapp_upload"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{stem}_{timestamp}_{index}{ext}"


def _preview_text(client_id: str, bundle_name: str, caption_payload: dict[str, Any], media_kind: str, item_count: int) -> str:
    hashtags = " ".join(caption_payload.get("hashtags") or [])
    quality = caption_payload.get("quality_gate") or {}
    dimensions = quality.get("dimensions") or {}
    score = quality.get("score", 0)
    threshold = quality.get("threshold", 85)
    verdict = str(quality.get("verdict") or "Needs another pass").strip()
    score_text = f"{score:g}" if isinstance(score, (int, float)) else str(score or 0)
    threshold_text = f"{threshold:g}" if isinstance(threshold, (int, float)) else str(threshold or 85)
    media_label = {
        "image_single": "1 image post",
        "image_carousel": f"{item_count} image carousel",
        "video": "1 video reel",
    }.get(media_kind, f"{item_count} media item(s)")
    snapshot_parts = []
    snapshot_labels = [
        ("visual_grounding", "Visual"),
        ("brand_voice_fidelity", "Voice"),
        ("audience_platform_fit", "Platform"),
        ("realism", "Realism"),
        ("hook_strength", "Hooks"),
        ("trend_relevance", "Trend"),
    ]
    for key, label in snapshot_labels:
        if key in dimensions:
            value = dimensions.get(key)
            if isinstance(value, (int, float)):
                snapshot_parts.append(f"{label} {value:g}")
            else:
                snapshot_parts.append(f"{label} {value}")
    snapshot_line = f"Quality snapshot: {' · '.join(snapshot_parts)}" if snapshot_parts else ""
    caption_text = str(caption_payload.get("caption") or "").strip()
    caption_block = f"Caption:\n{caption_text}" if caption_text else "Caption:\n"
    hashtags_block = f"Hashtags\n{hashtags}" if hashtags else "Hashtags\n"
    return (
        f"Preview ready for {_format_client_label(client_id)}\n"
        f"Direction: {bundle_name}\n"
        f"Format: {media_label}\n"
        f"Quality: {score_text}/{threshold_text} - {verdict}\n"
        f"{snapshot_line}\n\n"
        f"{caption_block}\n\n"
        f"{hashtags_block}\n\n"
        "Reply with one of the examples below if you prefer typing:\n"
        "• post now\n"
        "• schedule friday 17 at 6am\n"
        "• edit [paste your edited caption here]\n"
        "• edit hashtags #kuwait #specialtycoffee\n"
        "• append hashtags #icedcoffee\n"
        "• change make it sharper, more premium, and more local to Kuwait\n"
        "• try again\n"
        "• cancel"
    ).strip()


def _parse_release_intent(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    raw = re.sub(r"\btommorow\b", "tomorrow", raw, flags=re.IGNORECASE)
    lowered = raw.lower()
    if any(token in lowered for token in (" post now", " publish now", "post this now", " right now", " immediately")) or lowered in {"now", "yes now"}:
        return {"mode": "post_now"}
    time_match = TIME_WINDOW_RE.search(raw)
    if not time_match:
        return {"mode": ""}
    try:
        time_label = datetime.combine(datetime.now().date(), parse_time_string(time_match.group(0))).strftime("%I:%M %p")
    except Exception:
        return {"mode": ""}
    date_phrase = ""
    for pattern in DATE_PATTERNS:
        match = pattern.search(raw)
        if match:
            date_phrase = match.group(0)
            break
    if not date_phrase:
        return {"mode": ""}
    resolved = resolve_date_phrase(date_phrase)
    if not resolved:
        return {"mode": ""}
    return {
        "mode": "schedule",
        "scheduled_date": resolved.isoformat(),
        "days": [resolved.strftime("%A")],
        "time": time_label,
    }


def _encode_oauth_state(client_id: str, operator_phone: str) -> str:
    payload = json.dumps(
        {
            "client_id": str(client_id or "").strip(),
            "operator_phone": normalize_phone(operator_phone),
            "nonce": uuid.uuid4().hex,
            "issued_at": _utc_now_iso(),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def build_meta_connect_link(client_id: str, operator_phone: str) -> str:
    public_base = str(get_public_base_url() or os.getenv("META_OAUTH_PUBLIC_BASE_URL") or os.getenv("WEBHOOK_PROXY_URL") or "").strip().rstrip("/")
    if not public_base:
        return ""
    state = _encode_oauth_state(client_id, operator_phone)
    return f"{public_base}/api/meta-oauth/start?client_id={client_id}&phone={normalize_phone(operator_phone)}&state={state}"


async def _complete_onboarding(phone: str, answers: dict[str, Any]) -> None:
    from webhook_server import (
        ProfileSaveRequest,
        QuickIntakeRequest,
        SynthesizeRequest,
        api_save_client_profile,
        api_synthesize_client,
    )

    business_name = str(answers.get("business_name") or "").strip()
    if not business_name or business_name.startswith("/"):
        _clear_session(phone)
        send_text_message(phone, "Jarvis could not finish onboarding because the client name was invalid. Start Add Client again and begin with the real business name.")
        return
    client_id = _unique_client_id(business_name)
    quick_intake = QuickIntakeRequest(
        brand_name=business_name,
        business_type=str(answers.get("business_type") or "").strip(),
        main_language=str(answers.get("main_language") or "").strip().lower(),
        what_they_sell=str(answers.get("what_they_sell") or "").strip(),
        target_audience=str(answers.get("target_audience") or "").strip(),
        brand_tone=str(answers.get("brand_tone") or "").strip(),
        products_examples=str(answers.get("products_examples") or "").strip(),
        city_market=str(answers.get("city_market") or "").strip(),
        words_to_avoid=str(answers.get("words_to_avoid") or "").strip(),
        inspiration_links=str(answers.get("inspiration_links") or "").strip(),
    )
    send_text_message(
        phone,
        (
            f"Final step complete for {_format_client_label(client_id, business_name)}.\n"
            "Jarvis is building the brand profile now. I’ll confirm here automatically when it’s ready."
        ),
    )
    synthesis = _coerce_api_result(await api_synthesize_client(
        SynthesizeRequest(
            client_name=business_name,
            raw_context="",
            quick_intake=quick_intake,
            website_url=None,
            social_url=None,
        )
    ))
    if str(synthesis.get("status") or "").strip().lower() not in {"success", "missing"}:
        _clear_session(phone)
        reason = str(synthesis.get("reason") or synthesis.get("detail") or "Synthesis failed.").strip()
        send_text_message(phone, f"Jarvis could not finish the brand profile for {_format_client_label(client_id, business_name)} yet.\nReason: {reason}")
        return
    profile_json = dict(synthesis.get("data") or {})
    profile_json.setdefault("main_language", str(answers.get("main_language") or "").strip().lower())
    profile_json.setdefault("city_market", str(answers.get("city_market") or "").strip())
    save_result = _coerce_api_result(await api_save_client_profile(
        ProfileSaveRequest(
            client_id=client_id,
            phone_number=None,
            meta_access_token="",
            facebook_page_id="",
            instagram_account_id="",
            profile_json=profile_json,
        )
    ))
    if str(save_result.get("status") or "").strip().lower() != "success":
        _clear_session(phone)
        missing = list(save_result.get("missing_fields") or [])
        if missing:
            send_text_message(
                phone,
                (
                    f"Jarvis could not save {_format_client_label(client_id, business_name)} yet because the profile is still missing:\n"
                    + "\n".join(f"- {item}" for item in missing[:6])
                ),
            )
            return
        reason = str(save_result.get("reason") or save_result.get("detail") or "Save failed.").strip()
        send_text_message(phone, f"Jarvis could not save {_format_client_label(client_id, business_name)} yet.\nReason: {reason}")
        return
    _clear_session(phone)
    _audit(phone, "operator.add_client.completed", {"client_id": client_id, "business_name": business_name})
    send_button_message(
        phone,
        header_text="Client Added",
        body_text=(
            f"{_format_client_label(client_id, business_name)} is ready.\n"
            "Brand profile saved. Trend research is running in the background.\n\n"
            "Choose the next step."
        ),
        buttons=[
            {"id": f"OP_CONNECT_NOW:{client_id}", "title": "Connect Meta"},
            {"id": "OP_MENU:MORE", "title": "Open Menu"},
        ],
        footer_text=f"Client ID: {client_id}",
    )


async def _send_client_picker(phone: str, *, reason: str, session_payload: dict[str, Any]) -> None:
    sections = _build_client_picker_sections()
    if not sections:
        send_text_message(phone, "No clients are saved yet. Send /addclient first.")
        return
    payload = dict(session_payload)
    payload["mode"] = "client_pick"
    payload["selection_reason"] = reason
    _save_session(phone, payload)
    send_list_message(
        phone,
        header_text="Jarvis",
        body_text="Which client is this for?\nIf the buttons do not load, reply with the client name.",
        button_text="Choose client",
        sections=sections,
        footer_text="WhatsApp operator lane",
    )


def _prompt_for_media(phone: str, client_id: str, source_text: str = "") -> None:
    payload = {
        "mode": "awaiting_media",
        "client_id": client_id,
        "source_text": str(source_text or "").strip(),
        "updated_at": _utc_now_iso(),
    }
    _save_session(phone, payload)
    send_text_message(
        phone,
        (
            f"Ready for {_format_client_label(client_id)}.\n"
            "Now send the image or video as WhatsApp Document.\n"
            "You can add post notes in the document caption or send them as a text message first."
        ),
    )


async def _start_post_flow(phone: str) -> None:
    rows = _client_rows()
    if not rows:
        send_text_message(phone, "No clients are saved yet. Send /addclient first.")
        return
    if len(rows) == 1:
        _prompt_for_media(phone, rows[0]["client_id"])
        return
    await _send_client_picker(phone, reason="post_client", session_payload={"mode": "client_pick"})


async def _start_strategy_flow(phone: str) -> None:
    rows = _client_rows()
    if not rows:
        send_text_message(phone, "No clients are saved yet. Send /addclient first.")
        return
    if len(rows) == 1:
        _open_strategy_menu(phone, rows[0]["client_id"])
        return
    await _send_client_picker(phone, reason="strategy_client", session_payload={"mode": "client_pick"})


async def _start_connect_flow(phone: str) -> None:
    rows = _client_rows()
    if not rows:
        send_text_message(phone, "No clients are saved yet. Send /addclient first.")
        return
    if len(rows) == 1:
        await _send_connect_link(phone, rows[0]["client_id"])
        return
    await _send_client_picker(phone, reason="connect", session_payload={"mode": "client_pick"})


async def _materialize_media_bundle(phone: str, session: dict[str, Any], client_id: str) -> None:
    media_refs = list(session.get("media_refs") or [])
    bundle_type, error = _infer_media_bundle(media_refs)
    if error:
        _clear_session(phone)
        send_text_message(phone, error)
        return
    uploaded_items = []
    for index, ref in enumerate(media_refs, start=1):
        media_result = await asyncio.to_thread(fetch_media_bytes, ref.get("media_id"))
        if not media_result.get("success"):
            send_text_message(phone, f"Jarvis could not download one of the WhatsApp documents: {media_result.get('error')}")
            return
        filename = _safe_asset_filename(client_id, ref.get("filename"), index, ref.get("mime_type") or media_result.get("mime_type"))
        asset = await asyncio.to_thread(save_uploaded_asset, client_id, filename, media_result.get("content") or b"")
        uploaded_items.append({"filename": asset.get("filename") or filename, "kind": ref.get("kind") or "image"})

    draft_label = {
        "video": "WhatsApp Reel",
        "image_carousel": "WhatsApp Carousel",
        "image_single": "WhatsApp Image Post",
    }.get(bundle_type, "WhatsApp Draft")
    bundle_name = f"{draft_label} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    topic = _derive_topic(session.get("source_text") or "", client_id, bundle_type, len(uploaded_items))
    media_type = "carousel_post" if bundle_type == "image_carousel" else ("reel_post" if bundle_type == "video" else "image_post")
    caption_payload = await asyncio.to_thread(
        generate_caption_payload,
        client_id,
        topic,
        media_type,
        _recent_client_captions(client_id),
    )
    draft_payload = {
        "bundle_type": bundle_type,
        "items": uploaded_items,
        "caption_mode": "ai",
        "caption_status": "ready" if str(caption_payload.get("status") or "").strip().lower() == "success" else "error",
        "caption_text": str(caption_payload.get("caption") or "").strip(),
        "hashtags": list(caption_payload.get("hashtags") or []),
        "seo_keyword_used": str(caption_payload.get("seo_keyword_used") or "").strip(),
        "topic_hint": topic,
    }
    saved_draft = await asyncio.to_thread(save_draft_payload, client_id, bundle_name, draft_payload)
    preview_session = {
        "mode": "preview",
        "client_id": client_id,
        "bundle_name": bundle_name,
        "draft_id": saved_draft.get("draft_id"),
        "topic": topic,
        "media_kind": bundle_type,
        "item_count": len(uploaded_items),
        "caption_payload": caption_payload,
        "requested_intent": _parse_release_intent(session.get("source_text") or ""),
        "source_text": session.get("source_text") or "",
    }
    _save_session(phone, preview_session)
    _audit(phone, "operator.preview.ready", {"client_id": client_id, "bundle_name": bundle_name, "media_kind": bundle_type})
    send_text_message(phone, _preview_text(client_id, bundle_name, caption_payload, bundle_type, len(uploaded_items)))


async def _finalize_media_collection(phone: str, collection_token: str) -> None:
    await asyncio.sleep(10)
    session = _session_payload(phone)
    if str(session.get("mode") or "") != "media_collect":
        return
    if str(session.get("collection_token") or "") != str(collection_token or ""):
        return
    client_id = str(session.get("client_id") or "").strip()
    if client_id:
        await _materialize_media_bundle(phone, session, client_id)
        return
    rows = _client_rows()
    if len(rows) == 1:
        await _materialize_media_bundle(phone, session, rows[0]["client_id"])
        return
    await _send_client_picker(phone, reason="media", session_payload=session)


async def _handle_onboarding_step(phone: str, text: str, session: dict[str, Any]) -> None:
    index = int(session.get("step_index") or 0)
    key, _prompt = ONBOARDING_STEPS[index]
    answer = _normalize_text(text)
    if answer.startswith("/") and answer.lower() not in {"/cancel", "cancel"}:
        send_text_message(phone, "Jarvis is still in client intake mode. Reply with the requested answer, or type cancel to stop this intake.")
        return
    if answer.lower() == "skip":
        answer = ""
    answers = dict(session.get("answers") or {})
    answers[key] = answer
    next_index = index + 1
    if next_index >= len(ONBOARDING_STEPS):
        build_session = {
            "mode": "onboarding_build",
            "step_index": index,
            "answers": answers,
            "building_client_name": str(answers.get("business_name") or "").strip(),
            "updated_at": _utc_now_iso(),
        }
        _save_session(phone, build_session)
        _spawn_background(_complete_onboarding(phone, answers))
        return
    session["answers"] = answers
    session["step_index"] = next_index
    _save_session(phone, session)
    _send_onboarding_prompt(phone, next_index)


def _start_onboarding(phone: str) -> None:
    session = {"mode": "add_client_mode_picker", "started_at": _utc_now_iso()}
    _save_session(phone, session)
    _audit(phone, "operator.add_client.started", {})
    _send_add_client_mode_picker(phone)


def _send_quick_brief_prompt(phone: str) -> None:
    send_text_message(
        phone,
        (
            "*Send one structured brief* \u2726\n"
            "Language rule: pick one main language first, then give the rest in one message.\n\n"
            "Reply with:\n"
            "1. Brand name\n"
            "2. What they sell\n"
            "3. Target audience\n"
            "4. Tone\n"
            "5. City / market\n"
            "6. Example products or services"
        ),
    )


async def _send_strategy_reply(phone: str, prompt_text: str, client_id_override: str | None = None) -> None:
    request = build_strategy_request_from_prompt(prompt_text)
    client_id = str(client_id_override or request.get("client_id") or _extract_client_id_from_text(prompt_text) or _session_payload(phone).get("client_id") or "").strip()
    if not client_id:
        send_text_message(phone, "Jarvis needs a client mention for strategy requests. Example: /strategy @client next month launch plan")
        return
    send_text_message(phone, f"Building strategy for {_format_client_label(client_id)} \u2726\nJarvis is preparing the plan now.")
    plan = await asyncio.to_thread(
        run_strategy_agent,
        client_id,
        request.get("window") or "next_7_days",
        request.get("goal") or prompt_text,
        request.get("campaign_context") or "",
        request.get("requested_prompt") or prompt_text,
    )
    if str(plan.get("error") or "").strip():
        send_text_message(phone, f"Strategy request failed: {plan.get('error')}")
        return
    send_text_message(phone, f"*Strategy ready* \u2726\n{summarize_strategy_plan_reply(plan)}")


def _update_session_after_regeneration(
    phone: str,
    session: dict[str, Any],
    new_caption_payload: dict[str, Any],
    bundle_name: str,
    client_id: str,
    existing_draft: dict[str, Any],
) -> None:
    updated_session = dict(session)
    updated_session["caption_payload"] = dict(new_caption_payload or {})
    updated_session["generation_state"] = str(new_caption_payload.get("generation_state") or new_caption_payload.get("status") or "success").strip() or "success"
    if new_caption_payload.get("display_direction"):
        updated_session["display_direction"] = str(new_caption_payload.get("display_direction") or "").strip()
    updated_session["updated_at"] = _utc_now_iso()
    updated_session.pop("expected_reply", None)
    save_draft_payload(
        client_id,
        bundle_name,
        {
            **dict(existing_draft or {}),
            "caption_text": str(new_caption_payload.get("caption") or "").strip(),
            "caption_status": "ready" if str(new_caption_payload.get("status") or "").strip().lower() == "success" else "error",
            "caption_metadata": {
                **dict(existing_draft.get("caption_metadata") or {}),
                "caption_payload": dict(new_caption_payload or {}),
            },
        },
    )
    _save_session(phone, updated_session)
    _send_preview_card(phone, updated_session)


async def _send_connect_link(phone: str, client_id: str) -> None:
    resolved = resolve_client_id(client_id)
    store = get_client_store()
    row = store.get_client(resolved) if hasattr(store, "get_client") else None
    if not row:
        send_text_message(phone, f"Jarvis could not find client {client_id}.")
        return
    profile = dict(row.get("profile_json") or row.get("profile") or {})
    link = build_meta_connect_link(resolved, phone)
    if not link:
        send_text_message(phone, "Jarvis cannot build the Meta connect link yet because WEBHOOK_PROXY_URL or META_OAUTH_PUBLIC_BASE_URL is missing.")
        return
    session = _session_payload(phone)
    session.update(
        {
            "mode": "connect_wait",
            "pending_connect_client_id": resolved,
            "pending_connect_link": link,
            "updated_at": _utc_now_iso(),
        }
    )
    _save_session(phone, session)
    _audit(phone, "operator.connect.link_sent", {"client_id": resolved})
    send_text_message(
        phone,
        (
            f"Connect Meta for {_format_client_label(resolved, profile.get('business_name'))} using this link:\n{link}\n\n"
            "Finish the Meta login in your browser. Jarvis will confirm here automatically."
        ),
    )


def _select_client_from_reply(reply_text: str) -> str:
    raw = _normalize_text(reply_text)
    if raw.isdigit():
        rows = _client_rows()
        index = int(raw) - 1
        if 0 <= index < len(rows):
            return rows[index]["client_id"]
    explicit = _extract_client_id_from_text(raw)
    if explicit:
        return explicit
    for row in _client_rows():
        if raw.lower() == row["display_name"].lower():
            return row["client_id"]
    return ""


async def _handle_preview_reply(phone: str, text: str, session: dict[str, Any]) -> None:
    lowered = _normalize_text(text).lower()
    client_id = str(session.get("client_id") or "").strip()
    bundle_name = str(session.get("bundle_name") or "").strip()
    topic = str(session.get("topic") or session.get("content_goal") or bundle_name or "").strip()
    gen_state = str(session.get("generation_state") or str((session.get("caption_payload") or {}).get("generation_state") or "")).strip()
    caption_payload = dict(session.get("caption_payload") or {})
    is_blocked = gen_state == "generation_unavailable"
    if lowered in {"cancel", "/cancel"}:
        _clear_session(phone)
        send_text_message(phone, "*Preview dismissed* \u2716\ufe0f\nThe draft is still saved if you want to return to it later.")
        return
    if lowered == "try again" or lowered == "try_again":
        media_kind = str(session.get("media_kind") or "image_single")
        existing_draft = (list_client_drafts(client_id).get("bundles", {}).get(bundle_name) or {})
        operator_brief = str(session.get("operator_brief") or session.get("source_text") or "").strip()
        send_text_message(phone, "*Regenerating caption* \u270d\ufe0f\nJarvis is generating a fresh batch with a stronger hook strategy.")
        current_caption = str(caption_payload.get("caption") or "").strip()
        quality_gate = dict(caption_payload.get("quality_gate") or {})
        failures = list(quality_gate.get("failures") or (caption_payload.get("retry_memory") or {}).get("failure_reasons") or [])
        if str(caption_payload.get("model_failure_reason") or "").strip():
            failures.append(str(caption_payload.get("model_failure_reason")))
        new_caption_payload = await asyncio.to_thread(
            generate_caption_payload, client_id, topic,
            "carousel_post" if media_kind == "image_carousel" else ("reel_post" if media_kind == "video" else "image_post"),
            _recent_client_captions(client_id, exclude_bundle_name=bundle_name),
            mode="generate", current_caption=current_caption, prior_best_caption=current_caption,
            avoid_repeat_failures=failures, operator_brief=operator_brief,
        )
        _update_session_after_regeneration(phone, session, new_caption_payload, bundle_name, client_id, existing_draft)
        return
    if lowered in {"revise", "revise brief"}:
        _prompt_preview_revise(phone, session)
        return
    if lowered.startswith("edit hashtags"):
        hashtags = _extract_hashtags(text)
        if not hashtags:
            send_text_message(phone, "*Edit hashtags needs hashtags* \u2726\nType: edit hashtags #kuwait #specialtycoffee")
            return
        caption_payload["hashtags"] = hashtags
        caption_payload["generation_source"] = "operator_edited"
        if not caption_payload.get("quality_gate", {}).get("passed"):
            caption_payload.setdefault("quality_gate", {})["passed"] = True
            caption_payload["quality_gate"]["verdict"] = "Approved (operator edit)"
        session["caption_payload"] = caption_payload
        session["generation_state"] = "success"
        existing_draft = (list_client_drafts(client_id).get("bundles", {}).get(bundle_name) or {})
        save_draft_payload(client_id, bundle_name, {
            **existing_draft,
            "caption_text": str(caption_payload.get("caption") or "").strip(),
            "caption_status": "ready",
            "caption_metadata": dict(existing_draft.get("caption_metadata") or {}),
        })
        _save_session(phone, session)
        _send_preview_card(phone, session)
        return
    if lowered.startswith("append hashtags"):
        hashtags = _extract_hashtags(text)
        if not hashtags:
            send_text_message(phone, "*Append hashtags needs hashtags* \u2726\nType: append hashtags #icedcoffee #kuwait")
            return
        current_hashtags = list(caption_payload.get("hashtags") or [])
        for hashtag in hashtags:
            if hashtag not in current_hashtags:
                current_hashtags.append(hashtag)
        caption_payload["hashtags"] = current_hashtags
        caption_payload["generation_source"] = "operator_edited"
        if not caption_payload.get("quality_gate", {}).get("passed"):
            caption_payload.setdefault("quality_gate", {})["passed"] = True
            caption_payload["quality_gate"]["verdict"] = "Approved (operator edit)"
        session["caption_payload"] = caption_payload
        session["generation_state"] = "success"
        existing_draft = (list_client_drafts(client_id).get("bundles", {}).get(bundle_name) or {})
        save_draft_payload(client_id, bundle_name, {
            **existing_draft,
            "caption_text": str(caption_payload.get("caption") or "").strip(),
            "caption_status": "ready",
            "caption_metadata": dict(existing_draft.get("caption_metadata") or {}),
        })
        _save_session(phone, session)
        _send_preview_card(phone, session)
        return
    if lowered.startswith("edit ") and not lowered.startswith("edit hashtags") and not lowered.startswith("edit hashtag"):
        feedback = re.sub(r"^edit\s+", "", _normalize_text(text), count=1, flags=re.IGNORECASE).strip()
        if not feedback:
            send_text_message(phone, "*Edit needs a caption* \u2726\nType: edit [your new caption text]")
            return
        caption_payload["caption"] = feedback
        caption_payload["generation_source"] = "operator_edited"
        if not caption_payload.get("quality_gate", {}).get("passed"):
            caption_payload.setdefault("quality_gate", {})["passed"] = True
            caption_payload["quality_gate"]["verdict"] = "Approved (operator edit)"
        session["caption_payload"] = caption_payload
        session["generation_state"] = "success"
        existing_draft = (list_client_drafts(client_id).get("bundles", {}).get(bundle_name) or {})
        save_draft_payload(client_id, bundle_name, {
            **existing_draft,
            "caption_text": feedback,
            "caption_status": "ready",
            "caption_metadata": dict(existing_draft.get("caption_metadata") or {}),
        })
        _save_session(phone, session)
        _send_preview_card(phone, session)
        return
    if lowered.startswith("change ") or (str(session.get("expected_reply") or "").strip() == "revise" and not lowered.startswith("schedule")):
        feedback = _normalize_text(text)
        if lowered.startswith("change "):
            feedback = feedback[7:].strip()
        media_kind = str(session.get("media_kind") or "image_single")
        existing_draft = (list_client_drafts(client_id).get("bundles", {}).get(bundle_name) or {})
        current_caption = str(caption_payload.get("caption") or "").strip()
        mode = "generate" if is_blocked else "revise"
        new_caption_payload = await asyncio.to_thread(
            generate_caption_payload,
            client_id,
            topic,
            "carousel_post" if media_kind == "image_carousel" else ("reel_post" if media_kind == "video" else "image_post"),
            _recent_client_captions(client_id, exclude_bundle_name=bundle_name),
            mode=mode,
            operator_brief=feedback,
            current_caption=current_caption,
            prior_best_caption="" if is_blocked else current_caption,
        )
        _update_session_after_regeneration(phone, session, new_caption_payload, bundle_name, client_id, existing_draft)
        return
    if lowered in {"post now", "yes now", "yes", "approve", "post it", "go"}:
        if is_blocked:
            send_text_message(phone, "*Release blocked* \u26a0\ufe0f\nJarvis needs a real generated caption before posting or scheduling.\nUse Try Again, Revise, Edit, or Cancel.")
            return
        result = await asyncio.to_thread(TriggerPipelineNowTool().execute, client_id, topic, None, bundle_name)
        result_status = str(result.get("status") or "").strip().lower()
        result_error = str(result.get("error") or "").strip()
        if result_status in ("error", "partial_success") or result_error:
            _save_session(phone, session)
        else:
            _clear_session(phone)
        send_text_message(phone, f"*Published* \U0001f680\n{str(result.get('message') or result.get('error') or 'Post request completed.')}")
        return
    if lowered.startswith("schedule") or str(session.get("expected_reply") or "").strip() == "schedule":
        if is_blocked:
            send_text_message(phone, "*Release blocked* \u26a0\ufe0f\nJarvis needs a real generated caption before posting or scheduling.\nUse Try Again, Revise, Edit, or Cancel.")
            return
        intent = _parse_release_intent(text)
        if str(intent.get("mode") or "") != "schedule":
            _prompt_preview_schedule(phone, session)
            return
        result = await asyncio.to_thread(
            RequestApprovalTool().execute,
            client_id,
            topic,
            intent.get("days") or [],
            intent.get("time") or "",
            bundle_name,
            None,
            intent.get("scheduled_date") or "",
            session.get("draft_id"),
            "whatsapp_only",
        )
        result_status = str(result.get("status") or "").strip().lower()
        result_error = str(result.get("error") or "").strip()
        if result_status == "error" or result_error:
            _save_session(phone, session)
        else:
            _clear_session(phone)
        send_text_message(phone, f"*Scheduled* \U0001f4c5\n{str(result.get('message') or result.get('error') or 'Schedule request completed.')}")
        return
    if is_blocked:
        send_text_message(phone, "*Preview reply not understood* \u26a0\ufe0f\nThis draft is still blocked. Use the buttons, or reply with try again, edit ..., edit hashtags ..., append hashtags ..., change ..., or cancel.")
    else:
        send_text_message(phone, "*Preview reply not understood* \u26a0\ufe0f\nUse the buttons, or reply with post now, schedule ..., edit ..., edit hashtags ..., append hashtags ..., change ..., try again, or cancel.")


async def handle_operator_message(message: dict[str, Any]) -> dict[str, Any]:
    phone = normalize_phone(message.get("from"))
    msg_type = str(message.get("type") or "").strip().lower()
    text = _normalize_text(message.get("text"))
    reply_id = _normalize_text(message.get("interactive_reply_id"))
    session = _session_payload(phone)

    if msg_type == "interactive" and not reply_id and text:
        msg_type = "text"

    if msg_type == "interactive":
        if reply_id.startswith("OP_ONBOARD_LANG:"):
            choice = reply_id.split(":", 1)[1].strip().lower()
            if str(session.get("mode") or "") in {"onboarding", "onboarding_form"}:
                await _handle_onboarding_step(phone, choice, session)
                return {"status": "success", "handled": True}
        if reply_id.startswith("OP_ADD_CLIENT:"):
            action = reply_id.split(":", 1)[1].strip().upper()
            if action == "QUICK":
                _save_session(
                    phone,
                    {
                        "mode": "onboarding_form",
                        "onboarding_mode": "quick_brief",
                        "step_index": 0,
                        "answers": {},
                        "updated_at": _utc_now_iso(),
                    },
                )
                _send_quick_brief_prompt(phone)
                _send_back_button(phone, "Need to go back to the main Jarvis menu?", "ROOT")
                return {"status": "success", "handled": True}
            if action == "IMPORT":
                _save_session(
                    phone,
                    {
                        "mode": "awaiting_client_brief_document",
                        "onboarding_mode": "import_brief",
                        "updated_at": _utc_now_iso(),
                    },
                )
                send_text_message(phone, "*Import Brief* \u2726\nSend the client brief as a PDF, DOCX, TXT, or MD document.")
                _send_back_button(phone, "Need to go back to the main Jarvis menu?", "ROOT")
                return {"status": "success", "handled": True}
            if action == "WEBSITE":
                _save_session(
                    phone,
                    {
                        "mode": "awaiting_client_website_url",
                        "onboarding_mode": "scan_website",
                        "updated_at": _utc_now_iso(),
                    },
                )
                send_text_message(phone, "*Scan a client website* \u2726\nSend one public website URL and Jarvis will build the client profile from the site context.")
                _send_back_button(phone, "Need to go back to the Add Client mode picker?", "ROOT")
                return {"status": "success", "handled": True}
        if reply_id.startswith("OP_META_PICK:"):
            choice_id = reply_id.split(":", 1)[1].strip()
            session = _session_payload(phone)
            client_id = str(session.get("client_id") or "").strip()
            pending = list(session.get("pending_meta_choices") or [])
            selected = next((item for item in pending if str(item.get("page_id") or "").strip() == choice_id), None)
            if not client_id or not selected:
                send_text_message(phone, "Jarvis could not use that Meta choice.")
                return {"status": "error", "handled": True}
            store = get_client_store()
            client = store.get_client(client_id) or {}
            payload = dict(client)
            payload["facebook_page_id"] = str(selected.get("page_id") or "").strip()
            payload["instagram_account_id"] = str(selected.get("instagram_account_id") or "").strip()
            payload["facebook_page_name"] = str(selected.get("page_name") or "").strip()
            payload["instagram_username"] = str(selected.get("instagram_username") or "").strip()
            store.save_client(client_id, payload)
            delete_operator_session_state(normalize_phone(phone))
            send_text_message(phone, "This specific Page/Instagram pair is now bound to this client.")
            return {"status": "success", "handled": True}
        if reply_id.startswith("OP_CONNECT_NOW:"):
            client_id = resolve_client_id(reply_id.split(":", 1)[1])
            if client_id:
                await _send_connect_link(phone, client_id)
                return {"status": "success", "handled": True}
        if reply_id.startswith("OP_MENU:"):
            action = reply_id.split(":", 1)[1].strip().upper()
            if action == "POST":
                await _start_post_flow(phone)
                return {"status": "success", "handled": True}
            if action == "ADD_CLIENT":
                _start_onboarding(phone)
                return {"status": "success", "handled": True}
            if action == "MORE":
                _send_more_menu(phone)
                return {"status": "success", "handled": True}
        if reply_id.startswith("OP_MORE:"):
            action = reply_id.split(":", 1)[1].strip().upper()
            if action == "STRATEGY":
                await _start_strategy_flow(phone)
                return {"status": "success", "handled": True}
            if action == "CONNECT":
                await _start_connect_flow(phone)
                return {"status": "success", "handled": True}
            if action == "CLIENTS":
                send_text_message(phone, _build_clients_summary())
                return {"status": "success", "handled": True}
            if action == "SCHEDULES":
                send_text_message(phone, _build_schedules_summary())
                return {"status": "success", "handled": True}
            if action == "STATUS":
                send_text_message(phone, _build_status_summary())
                return {"status": "success", "handled": True}
            if action == "REFRESH_META":
                _clear_meta_health_cache()
                send_text_message(phone, "Meta status refreshed.")
                send_text_message(phone, _build_status_summary())
                return {"status": "success", "handled": True}
            if action == "HELP":
                _send_root_menu(phone)
                return {"status": "success", "handled": True}
        if reply_id.startswith("OP_CLIENT_PICK:"):
            client_id = resolve_client_id(reply_id.split(":", 1)[1])
            if not client_id:
                send_text_message(phone, "Jarvis could not resolve that client choice.")
                return {"status": "error"}
            reason = str(session.get("selection_reason") or "").strip()
            if reason == "media":
                session["client_id"] = client_id
                await _materialize_media_bundle(phone, session, client_id)
                return {"status": "success", "handled": True}
            if reason == "post_client":
                row = _get_client_row(client_id) or {}
                health = dict(row.get("meta_health") or {})
                status = str(health.get("status") or "").strip().lower()
                if not health.get("ok", True) and status in {"expired_or_invalid", "missing"}:
                    detail = str(health.get("detail") or "Meta credentials are not ready for this client.").strip()
                    _save_session(phone, {"mode": "meta_blocked", "client_id": client_id, "updated_at": _utc_now_iso()})
                    label = _format_client_label(client_id, (row.get("profile") or {}).get("business_name"))
                    send_button_message(
                        phone,
                        header_text="Meta Needs Attention",
                        body_text=f"*{label} cannot start a post yet* \u26a0\ufe0f\nJarvis stopped here to avoid wasting time on uploads before publish is possible.\n\nReason: {detail}",
                        buttons=[{"id": f"OP_CONNECT_NOW:{client_id}", "title": "Connect Meta"}, {"id": "OP_NAV:ROOT", "title": "Go Back"}],
                        footer_text="Reconnect Meta, then try again",
                    )
                    return {"status": "success", "handled": True}
                _prompt_for_media(phone, client_id, str(session.get("source_text") or ""))
                return {"status": "success", "handled": True}
            if reason == "connect":
                await _send_connect_link(phone, client_id)
                return {"status": "success", "handled": True}
            if reason == "strategy_client":
                _open_strategy_menu(phone, client_id)
                return {"status": "success", "handled": True}
        if reply_id.startswith("OP_STRATEGY:"):
            action = reply_id.split(":", 1)[1].strip().upper()
            client_id = str(session.get("client_id") or "").strip()
            if action == "BUILD":
                _save_session(phone, {"mode": "strategy_prompt", "client_id": client_id, "updated_at": _utc_now_iso()})
                send_text_message(phone, f"What strategy should Jarvis build for {_format_client_label(client_id)}?")
                return {"status": "success", "handled": True}
            if action == "VIEW":
                _save_session(phone, {"mode": "strategy_plan_pick", "client_id": client_id, "updated_at": _utc_now_iso()})
                _send_saved_strategy_plans(phone, client_id)
                return {"status": "success", "handled": True}
        if reply_id.startswith("OP_STRATEGY_PLAN:"):
            plan_id = reply_id.split(":", 1)[1].strip()
            _send_strategy_plan_view(phone, plan_id)
            return {"status": "success", "handled": True}
        if reply_id.startswith("OP_PREVIEW:"):
            action = reply_id.split(":", 1)[1].strip().upper()
            if action == "POST_NOW":
                await _handle_preview_reply(phone, "post now", session)
                return {"status": "success", "handled": True}
            if action == "SCHEDULE":
                _prompt_preview_schedule(phone, session)
                return {"status": "success", "handled": True}
            if action == "REVISE":
                _prompt_preview_revise(phone, session)
                return {"status": "success", "handled": True}
            if action == "TRY_AGAIN":
                await _handle_preview_reply(phone, "try again", session)
                return {"status": "success", "handled": True}
            if action == "CANCEL":
                await _handle_preview_reply(phone, "cancel", session)
                return {"status": "success", "handled": True}
        if reply_id.startswith("OP_NAV:"):
            target = reply_id.split(":", 1)[1].strip().upper()
            if target == "ROOT":
                _send_root_menu(phone)
                return {"status": "success", "handled": True}
            if target == "MORE":
                _send_more_menu(phone)
                return {"status": "success", "handled": True}
        send_text_message(phone, "Jarvis could not use that interactive response.")
        return {"status": "error", "handled": True}

    if msg_type in {"image", "video"}:
        send_text_message(phone, "For publish-quality media, resend that file as Document from WhatsApp so Jarvis receives the original quality.")
        return {"status": "success", "handled": True}

    if msg_type == "document":
        if str(session.get("mode") or "") == "preview":
            send_text_message(phone, "Preview still open. Finish the draft first, or use cancel before sending new media.")
            return {"status": "success", "handled": True}
        mime_type = str(message.get("mime_type") or "").strip().lower()
        if not (mime_type.startswith("image/") or mime_type.startswith("video/")):
            send_text_message(phone, "That document is not a supported publishable image or video.")
            return {"status": "success", "handled": True}
        media_kind = "video" if mime_type.startswith("video/") else "image"
        source_text = _normalize_text(message.get("caption")) or _normalize_text(session.get("source_text"))
        client_id = _extract_client_id_from_text(source_text) or str(session.get("client_id") or "").strip()
        collection_token = uuid.uuid4().hex
        media_refs = list(session.get("media_refs") or [])
        media_refs.append(
            {
                "media_id": str(message.get("media_id") or "").strip(),
                "filename": str(message.get("filename") or "").strip(),
                "mime_type": mime_type,
                "kind": media_kind,
                "received_at": _utc_now_iso(),
            }
        )
        new_session = {
            "mode": "media_collect",
            "collection_token": collection_token,
            "client_id": client_id,
            "source_text": source_text,
            "media_refs": media_refs,
            "updated_at": _utc_now_iso(),
        }
        _save_session(phone, new_session)
        _spawn_background(_finalize_media_collection(phone, collection_token))
        if media_kind == "video":
            ack = "Video received"
        elif len(media_refs) > 1:
            ack = "Carousel updated"
        else:
            ack = "Image received"
        send_text_message(
            phone,
            (
                f"*{ack}* \u2726\n"
                f"Jarvis is holding the bundle for {_format_client_label(client_id) if client_id else 'this client'}.\n"
                "Send more documents within 10 seconds or wait 10 more seconds for Jarvis to continue with this set."
            ),
        )
        return {"status": "success", "handled": True}

    if msg_type != "text":
        send_text_message(phone, "Jarvis only handles text, interactive replies, and document media in the operator lane.")
        return {"status": "success", "handled": True}

    lowered = text.lower()
    session_mode = str(session.get("mode") or "").strip()

    if lowered in {"/cancel", "cancel"}:
        if _clear_session(phone):
            send_text_message(phone, "Current operator flow cancelled.")
        else:
            send_text_message(phone, "There was no active operator flow to cancel.")
        return {"status": "success", "handled": True}
    if lowered in {"/help", "/start", "/menu", "help", "menu", "start", "hey jarvis", "hi jarvis", "hello jarvis"}:
        _clear_session(phone)
        _send_root_menu(phone)
        return {"status": "success", "handled": True}
    if session_mode in {"onboarding", "onboarding_form"}:
        await _handle_onboarding_step(phone, text, session)
        return {"status": "success", "handled": True}
    if session_mode == "onboarding_missing_fields":
        await _handle_missing_fields_reply(phone, text, session)
        return {"status": "success", "handled": True}
    if session_mode == "add_client_mode_picker":
        lowered_choice = lowered
        if lowered_choice in {"quick brief", "quick", "structured brief"}:
            _save_session(
                phone,
                {
                    "mode": "onboarding_form",
                    "onboarding_mode": "quick_brief",
                    "step_index": 0,
                    "answers": {},
                    "updated_at": _utc_now_iso(),
                },
            )
            _send_quick_brief_prompt(phone)
            _send_back_button(phone, "Need to go back to the main Jarvis menu?", "ROOT")
            return {"status": "success", "handled": True}
        if lowered_choice in {"import brief", "import", "brief"}:
            _save_session(
                phone,
                {
                    "mode": "awaiting_client_brief_document",
                    "onboarding_mode": "import_brief",
                    "updated_at": _utc_now_iso(),
                },
            )
            send_text_message(phone, "*Import Brief* \u2726\nSend the client brief as a PDF, DOCX, TXT, or MD document.")
            return {"status": "success", "handled": True}
        if lowered_choice in {"scan website", "website", "scan"}:
            _save_session(
                phone,
                {
                    "mode": "awaiting_client_website_url",
                    "onboarding_mode": "scan_website",
                    "updated_at": _utc_now_iso(),
                },
            )
            send_text_message(phone, "*Scan a client website* \u2726\nSend one public website URL and Jarvis will build the client profile from the site context.")
            return {"status": "success", "handled": True}
    if session_mode == "onboarding_build":
        send_text_message(
            phone,
            (
                f"Jarvis is still building {str(session.get('building_client_name') or 'that client').strip() or 'that client'}.\n"
                "I’ll send the result here automatically when it’s ready."
            ),
        )
        return {"status": "success", "handled": True}
    if session_mode == "preview":
        await _handle_preview_reply(phone, text, session)
        return {"status": "success", "handled": True}
    if session_mode == "strategy_prompt":
        await _send_strategy_reply(phone, text, client_id_override=str(session.get("client_id") or "").strip())
        _clear_session(phone)
        return {"status": "success", "handled": True}
    if session_mode == "client_pick":
        if lowered in {"/help", "/start", "/menu", "help", "menu", "start", "hey jarvis", "hi jarvis", "hello jarvis"}:
            _send_root_menu(phone)
            return {"status": "success", "handled": True}
        client_id = _select_client_from_reply(text)
        if not client_id:
            send_text_message(phone, "Reply with the client name or tap one of the client buttons.")
            return {"status": "success", "handled": True}
        reason = str(session.get("selection_reason") or "").strip()
        if reason == "media":
            session["client_id"] = client_id
            await _materialize_media_bundle(phone, session, client_id)
            return {"status": "success", "handled": True}
        if reason == "post_client":
            row = _get_client_row(client_id) or {}
            health = dict(row.get("meta_health") or {})
            status = str(health.get("status") or "").strip().lower()
            if not health.get("ok", True) and status in {"expired_or_invalid", "missing"}:
                detail = str(health.get("detail") or "Meta credentials are not ready for this client.").strip()
                _save_session(phone, {"mode": "meta_blocked", "client_id": client_id, "updated_at": _utc_now_iso()})
                label = _format_client_label(client_id, (row.get("profile") or {}).get("business_name"))
                send_button_message(
                    phone,
                    header_text="Meta Needs Attention",
                    body_text=f"*{label} cannot start a post yet* \u26a0\ufe0f\nJarvis stopped here to avoid wasting time on uploads before publish is possible.\n\nReason: {detail}",
                    buttons=[{"id": f"OP_CONNECT_NOW:{client_id}", "title": "Connect Meta"}, {"id": "OP_NAV:ROOT", "title": "Go Back"}],
                    footer_text="Reconnect Meta, then try again",
                )
                return {"status": "success", "handled": True}
            _prompt_for_media(phone, client_id, str(session.get("source_text") or ""))
            return {"status": "success", "handled": True}
        if reason == "connect":
            await _send_connect_link(phone, client_id)
            return {"status": "success", "handled": True}
        if reason == "strategy_client":
            _open_strategy_menu(phone, client_id)
            return {"status": "success", "handled": True}
    if session_mode == "awaiting_media":
        updated = dict(session)
        updated["source_text"] = " ".join(part for part in [str(session.get("source_text") or "").strip(), text] if part).strip()
        explicit_client = _extract_client_id_from_text(text)
        if explicit_client:
            updated["client_id"] = explicit_client
        _save_session(phone, updated)
        send_text_message(phone, "Notes saved. Now send the image or video as WhatsApp Document.")
        return {"status": "success", "handled": True}
    if session_mode == "media_collect":
        updated = dict(session)
        updated["source_text"] = " ".join(part for part in [str(session.get("source_text") or "").strip(), text] if part).strip()
        explicit_client = _extract_client_id_from_text(text)
        if explicit_client:
            updated["client_id"] = explicit_client
        updated["collection_token"] = uuid.uuid4().hex
        _save_session(phone, updated)
        _spawn_background(_finalize_media_collection(phone, updated["collection_token"]))
        send_text_message(phone, "Jarvis updated the pending media bundle notes. Keep sending documents or wait 10 more seconds for the preview.")
        return {"status": "success", "handled": True}
    if lowered == "/clients":
        send_text_message(phone, _build_clients_summary())
        return {"status": "success", "handled": True}
    if lowered == "/schedules":
        send_text_message(phone, _build_schedules_summary())
        return {"status": "success", "handled": True}
    if lowered == "/status":
        send_text_message(phone, _build_status_summary())
        return {"status": "success", "handled": True}
    if lowered == "/addclient" or "add new client" in lowered or lowered == "add client":
        _start_onboarding(phone)
        return {"status": "success", "handled": True}
    if lowered.startswith("/connect"):
        client_id = _extract_client_id_from_text(text)
        if client_id:
            await _send_connect_link(phone, client_id)
            return {"status": "success", "handled": True}
        await _start_connect_flow(phone)
        return {"status": "success", "handled": True}
    if lowered.startswith("/strategy"):
        await _send_strategy_reply(phone, text)
        return {"status": "success", "handled": True}
    if prompt_requests_strategy(text):
        await _send_strategy_reply(phone, text)
        return {"status": "success", "handled": True}

    if str(session.get("mode") or "") == "onboarding":
        await _handle_onboarding_step(phone, text, session)
        return {"status": "success", "handled": True}

    _send_root_menu(phone)
    return {"status": "success", "handled": True}
