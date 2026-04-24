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
    prompt_requests_strategy,
    run_strategy_agent,
    summarize_strategy_plan_reply,
)
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

TIME_WINDOW_RE = re.compile(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", re.IGNORECASE)
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
    for client in (get_client_store().list_clients() or []):
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
            }
        )
    rows.sort(key=lambda item: item["display_name"].lower())
    return rows


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
    for row in _client_rows():
        if normalized == row["display_name"].lower():
            return row["client_id"]
    return ""


def _build_client_picker_sections(prefix: str = "OP_CLIENT_PICK") -> list[dict[str, Any]]:
    rows = []
    for row in _client_rows()[:10]:
        rows.append(
            {
                "id": f"{prefix}:{row['client_id']}",
                "title": row["display_name"],
                "description": "Connected" if row["connected"] else "Needs Meta connection",
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


def _send_root_menu(phone: str) -> None:
    result = send_button_message(
        phone,
        header_text="Jarvis",
        body_text=(
            "Choose what Jarvis should do next.\n"
            "Use the buttons below, or type a command if you prefer."
        ),
        buttons=[
            {"id": "OP_MENU:POST", "title": "New Post"},
            {"id": "OP_MENU:ADD_CLIENT", "title": "Add Client"},
            {"id": "OP_MENU:MORE", "title": "More"},
        ],
        footer_text="You can also type /clients, /status, /strategy, or /connect",
    )
    if not result.get("success"):
        send_text_message(phone, _help_text())


def _send_more_menu(phone: str) -> None:
    result = send_list_message(
        phone,
        header_text="Jarvis Menu",
        body_text="Choose another operator action.",
        button_text="Open actions",
        sections=[
            {
                "title": "Operator Actions",
                "rows": [
                    {"id": "OP_MORE:STRATEGY", "title": "Strategy", "description": "Build or refresh a client plan"},
                    {"id": "OP_MORE:CONNECT", "title": "Connect Meta", "description": "Attach Facebook and Instagram"},
                    {"id": "OP_MORE:CLIENTS", "title": "Clients", "description": "List saved clients"},
                    {"id": "OP_MORE:SCHEDULES", "title": "Schedules", "description": "Show active scheduled posts"},
                    {"id": "OP_MORE:STATUS", "title": "Status", "description": "Show operator and backend status"},
                    {"id": "OP_MORE:HELP", "title": "Help", "description": "Show the main Jarvis menu again"},
                ],
            }
        ],
        footer_text="WhatsApp operator lane",
    )
    if not result.get("success"):
        send_text_message(phone, _help_text())


def _build_clients_summary() -> str:
    rows = _client_rows()
    if not rows:
        return "No clients are saved yet. Send /addclient to create the first one."
    lines = ["Saved clients:"]
    for index, row in enumerate(rows[:20], start=1):
        status = "Connected" if row["connected"] else "Needs connect"
        lines.append(f"{index}. {row['display_name']} [{row['client_id']}] - {status}")
    return "\n".join(lines)


def _build_schedules_summary() -> str:
    schedule = load_schedule("schedule.json")
    views = split_schedule_views(schedule)
    active = list(views.get("active") or [])
    if not active:
        return "No active scheduled posts are queued right now."
    lines = ["Active schedule:"]
    for item in active[:12]:
        client_id = str(item.get("client") or "").strip()
        topic = str(item.get("topic") or item.get("draft_name") or "Untitled").strip()
        date_label = str(item.get("scheduled_date") or "").strip() or ", ".join(item.get("days") or [])
        time_label = str(item.get("time") or "").strip()
        lines.append(f"- {_format_client_label(client_id)}: {topic} | {date_label} {time_label}".strip())
    return "\n".join(lines)


def _build_status_summary() -> str:
    rows = _client_rows()
    connected = sum(1 for row in rows if row["connected"])
    schedule = load_schedule("schedule.json")
    views = split_schedule_views(schedule)
    active_count = len(views.get("active") or [])
    history_count = len(views.get("history") or [])
    return (
        "Jarvis operator status:\n"
        f"- Clients: {len(rows)} total\n"
        f"- Connected Meta accounts: {connected}\n"
        f"- Active scheduled jobs: {active_count}\n"
        f"- Schedule history rows: {history_count}\n"
        f"- Operator phone: {normalize_phone(get_agency_config().get('owner_phone')) or 'not configured'}"
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
    quality_line = f"Quality Gate: {quality.get('score', 0)}/{quality.get('threshold', 85)}"
    media_label = {
        "image_single": "1 image post",
        "image_carousel": f"{item_count} image carousel",
        "video": "1 video reel",
    }.get(media_kind, f"{item_count} media item(s)")
    return (
        f"Preview ready for {_format_client_label(client_id)}\n"
        f"Draft: {bundle_name}\n"
        f"Media: {media_label}\n"
        f"{quality_line}\n\n"
        f"{caption_payload.get('caption', '').strip()}\n\n"
        f"{hashtags}\n\n"
        "Reply with:\n"
        "- yes\n"
        "- change make it more casual\n"
        "- schedule tomorrow 7pm\n"
        "- cancel"
    ).strip()


def _parse_release_intent(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
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
    public_base = str(os.getenv("META_OAUTH_PUBLIC_BASE_URL") or os.getenv("WEBHOOK_PROXY_URL") or "").strip().rstrip("/")
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
        _save_session(
            phone,
            {
                "mode": "strategy_prompt",
                "client_id": rows[0]["client_id"],
                "updated_at": _utc_now_iso(),
            },
        )
        send_text_message(phone, f"What strategy should Jarvis build for {_format_client_label(rows[0]['client_id'])}?")
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
    session = {"mode": "onboarding", "step_index": 0, "answers": {}, "started_at": _utc_now_iso()}
    _save_session(phone, session)
    _audit(phone, "operator.add_client.started", {})
    _send_onboarding_prompt(phone, 0)


async def _send_strategy_reply(phone: str, prompt_text: str) -> None:
    request = build_strategy_request_from_prompt(prompt_text)
    client_id = str(request.get("client_id") or "").strip()
    if not client_id:
        send_text_message(phone, "Jarvis needs a client mention for strategy requests. Example: /strategy @client next month launch plan")
        return
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
    send_text_message(phone, summarize_strategy_plan_reply(plan))


async def _send_connect_link(phone: str, client_id: str) -> None:
    resolved = resolve_client_id(client_id)
    row = _get_client_row(resolved)
    if not row:
        send_text_message(phone, f"Jarvis could not find client {client_id}.")
        return
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
            f"Connect {_format_client_label(resolved, row['profile'].get('business_name'))} using this link:\n{link}\n\n"
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
    topic = str(session.get("topic") or bundle_name or "").strip()
    if lowered in {"cancel", "/cancel"}:
        _clear_session(phone)
        send_text_message(phone, "Preview cancelled.")
        return
    if lowered.startswith("change "):
        feedback = _normalize_text(text)[7:].strip()
        revised_topic = f"{topic}. Revision request: {feedback}"
        media_kind = str(session.get("media_kind") or "image_single")
        caption_payload = await asyncio.to_thread(
            generate_caption_payload,
            client_id,
            revised_topic,
            "carousel_post" if media_kind == "image_carousel" else ("reel_post" if media_kind == "video" else "image_post"),
            _recent_client_captions(client_id, exclude_bundle_name=bundle_name),
        )
        existing_draft = (list_client_drafts(client_id).get("bundles", {}).get(bundle_name) or {})
        save_draft_payload(
            client_id,
            bundle_name,
            {
                "bundle_type": media_kind,
                "items": list(existing_draft.get("items") or []),
                "caption_mode": "ai",
                "caption_status": "ready" if str(caption_payload.get("status") or "").strip().lower() == "success" else "error",
                "caption_text": str(caption_payload.get("caption") or "").strip(),
                "hashtags": list(caption_payload.get("hashtags") or []),
                "seo_keyword_used": str(caption_payload.get("seo_keyword_used") or "").strip(),
                "topic_hint": revised_topic,
            },
        )
        session["topic"] = revised_topic
        session["caption_payload"] = caption_payload
        _save_session(phone, session)
        send_text_message(phone, _preview_text(client_id, bundle_name, caption_payload, media_kind, int(session.get("item_count") or 1)))
        return

    requested_intent = dict(session.get("requested_intent") or {})
    if lowered.startswith("schedule "):
        requested_intent = _parse_release_intent(text)
    elif lowered in {"yes", "approve", "post it", "go", "yes now"} and not requested_intent:
        requested_intent = _parse_release_intent(text)

    mode = str(requested_intent.get("mode") or "").strip()
    if lowered in {"yes", "approve", "post it", "go", "yes now"} and mode == "post_now":
        result = await asyncio.to_thread(TriggerPipelineNowTool().execute, client_id, topic, None, bundle_name)
        _clear_session(phone)
        send_text_message(phone, str(result.get("message") or result.get("error") or "Post request completed."))
        return
    if lowered.startswith("schedule ") or (lowered in {"yes", "approve", "post it", "go"} and mode == "schedule"):
        if mode != "schedule":
            send_text_message(phone, "Jarvis needs an exact date and time. Example: schedule tomorrow 7pm")
            return
        result = await asyncio.to_thread(
            RequestApprovalTool().execute,
            client_id,
            topic,
            requested_intent.get("days") or [],
            requested_intent.get("time") or "",
            bundle_name,
            None,
            requested_intent.get("scheduled_date") or "",
            session.get("draft_id"),
            "whatsapp_only",
        )
        _clear_session(phone)
        send_text_message(phone, str(result.get("message") or result.get("error") or "Schedule request completed."))
        return
    if lowered in {"yes", "approve", "post it", "go"}:
        send_text_message(phone, "Jarvis needs the release mode. Reply with yes now or schedule tomorrow 7pm.")
        return
    send_text_message(phone, "Jarvis did not understand that preview reply. Use yes, change ..., schedule ..., or cancel.")


async def handle_operator_message(message: dict[str, Any]) -> dict[str, Any]:
    phone = normalize_phone(message.get("from"))
    msg_type = str(message.get("type") or "").strip().lower()
    text = _normalize_text(message.get("text"))
    reply_id = _normalize_text(message.get("interactive_reply_id"))
    session = _session_payload(phone)

    if msg_type == "interactive":
        if reply_id.startswith("OP_ONBOARD_LANG:"):
            choice = reply_id.split(":", 1)[1].strip().lower()
            if str(session.get("mode") or "") == "onboarding":
                await _handle_onboarding_step(phone, choice, session)
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
                _prompt_for_media(phone, client_id, str(session.get("source_text") or ""))
                return {"status": "success", "handled": True}
            if reason == "connect":
                await _send_connect_link(phone, client_id)
                return {"status": "success", "handled": True}
            if reason == "strategy_client":
                _save_session(
                    phone,
                    {
                        "mode": "strategy_prompt",
                        "client_id": client_id,
                        "updated_at": _utc_now_iso(),
                    },
                )
                send_text_message(phone, f"What strategy should Jarvis build for {_format_client_label(client_id)}?")
                return {"status": "success", "handled": True}
        send_text_message(phone, "Jarvis could not use that interactive response.")
        return {"status": "error", "handled": True}

    if msg_type in {"image", "video"}:
        send_text_message(phone, "For publish-quality media, resend that file as Document from WhatsApp so Jarvis receives the original quality.")
        return {"status": "success", "handled": True}

    if msg_type == "document":
        mime_type = str(message.get("mime_type") or "").strip().lower()
        if not (mime_type.startswith("image/") or mime_type.startswith("video/")):
            send_text_message(phone, "That document is not a supported publishable image or video.")
            return {"status": "success", "handled": True}
        media_kind = "video" if mime_type.startswith("video/") else "image"
        source_text = _normalize_text(message.get("caption")) or _normalize_text(session.get("source_text"))
        client_id = _extract_client_id_from_text(source_text) or str(session.get("client_id") or "").strip()
        collection_token = str(session.get("collection_token") or uuid.uuid4().hex)
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
        send_text_message(phone, "Got the document.\nSend more documents within 10 seconds for the same post bundle, or Jarvis will continue with this set.")
        return {"status": "success", "handled": True}

    if msg_type != "text":
        send_text_message(phone, "Jarvis only handles text, interactive replies, and document media in the operator lane.")
        return {"status": "success", "handled": True}

    lowered = text.lower()
    if lowered in {"/cancel", "cancel"}:
        if _clear_session(phone):
            send_text_message(phone, "Current operator flow cancelled.")
        else:
            send_text_message(phone, "There was no active operator flow to cancel.")
        return {"status": "success", "handled": True}

    if str(session.get("mode") or "") == "onboarding":
        await _handle_onboarding_step(phone, text, session)
        return {"status": "success", "handled": True}
    if str(session.get("mode") or "") == "onboarding_build":
        send_text_message(
            phone,
            (
                f"Jarvis is still building {str(session.get('building_client_name') or 'that client').strip() or 'that client'}.\n"
                "I’ll send the result here automatically when it’s ready."
            ),
        )
        return {"status": "success", "handled": True}
    if str(session.get("mode") or "") == "preview":
        await _handle_preview_reply(phone, text, session)
        return {"status": "success", "handled": True}
    if str(session.get("mode") or "") == "strategy_prompt":
        strategy_prompt = f"/strategy @{session.get('client_id')} {text}".strip()
        await _send_strategy_reply(phone, strategy_prompt)
        _clear_session(phone)
        return {"status": "success", "handled": True}
    if str(session.get("mode") or "") == "client_pick":
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
            _prompt_for_media(phone, client_id, str(session.get("source_text") or ""))
            return {"status": "success", "handled": True}
        if reason == "connect":
            await _send_connect_link(phone, client_id)
            return {"status": "success", "handled": True}
        if reason == "strategy_client":
            _save_session(
                phone,
                {
                    "mode": "strategy_prompt",
                    "client_id": client_id,
                    "updated_at": _utc_now_iso(),
                },
            )
            send_text_message(phone, f"What strategy should Jarvis build for {_format_client_label(client_id)}?")
            return {"status": "success", "handled": True}
    if str(session.get("mode") or "") == "awaiting_media":
        updated = dict(session)
        updated["source_text"] = " ".join(part for part in [str(session.get("source_text") or "").strip(), text] if part).strip()
        explicit_client = _extract_client_id_from_text(text)
        if explicit_client:
            updated["client_id"] = explicit_client
        _save_session(phone, updated)
        send_text_message(phone, "Notes saved. Now send the image or video as WhatsApp Document.")
        return {"status": "success", "handled": True}
    if str(session.get("mode") or "") == "media_collect":
        updated = dict(session)
        updated["source_text"] = " ".join(part for part in [str(session.get("source_text") or "").strip(), text] if part).strip()
        explicit_client = _extract_client_id_from_text(text)
        if explicit_client:
            updated["client_id"] = explicit_client
        _save_session(phone, updated)
        send_text_message(phone, "Jarvis updated the pending media bundle notes. Keep sending documents or wait for the preview.")
        return {"status": "success", "handled": True}

    if lowered in {"/help", "/start", "/menu", "help", "menu", "start", "hey jarvis", "hi jarvis", "hello jarvis"}:
        _send_root_menu(phone)
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

    _send_root_menu(phone)
    return {"status": "success", "handled": True}
