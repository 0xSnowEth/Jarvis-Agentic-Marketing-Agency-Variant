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

BRIEF_FIELD_MAP = {
    "business_name": "Business name",
    "industry": "Industry",
    "business_type": "Industry",
    "services": "Services",
    "what_they_sell": "Services",
    "target_audience": "Target audience",
    "identity": "Identity",
    "brand_voice.tone": "Brand tone",
    "brand_tone": "Brand tone",
}

TIME_WINDOW_RE = re.compile(r"\b(?:\d{1,2}:\d{2}(?:\s*(?:am|pm))?|\d{1,2}\s*(?:am|pm))\b", re.IGNORECASE)
ROBUST_CLIENT_MENTION_RE = re.compile(r"@\[(?P<client>[^\]]+)\]")
RAW_CLIENT_MENTION_RE = re.compile(r"(?<!\[)@(?P<client>[A-Za-z0-9_-]+)")
DATE_PATTERNS = [
    re.compile(r"\b(?:today|tonight|tomorrow)\b", re.IGNORECASE),
    re.compile(r"\bnext\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.IGNORECASE),
    re.compile(r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.IGNORECASE),
    re.compile(r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}\b", re.IGNORECASE),
]
CONNECT_SCOPE = ",".join([
    "pages_show_list", "pages_read_engagement", "pages_manage_posts",
    "instagram_basic", "instagram_content_publish", "business_management",
])

_BACKGROUND_TASKS: set[asyncio.Task] = set()
_OPERATOR_LOCKS: dict[str, asyncio.Lock] = {}
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
        record_operator_audit_event(event_type=event_type, payload=payload or {}, actor=normalize_phone(phone))
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
        rows.append({
            "client_id": client_id,
            "display_name": _format_client_label(client_id, business_name),
            "connected": bool(str(client.get("instagram_account_id") or "").strip()),
            "profile": profile,
            "meta_health": _client_meta_health(client_id, client),
        })
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
        base = "\u2705 Meta connected"
    elif status == "expired_or_invalid":
        base = "\u26a0\ufe0f Meta expired"
    elif status == "missing":
        base = "\U0001f517 Meta not linked"
    else:
        base = "\u2753 Meta unknown"
    if str((health or {}).get("probe_source") or "").strip() == "cached":
        base += " (cached)"
    return base


def _provisional_name_from_file(file_name: str, caption_hint: str = "") -> str:
    stem = re.sub(r"[_\-]+", " ", os.path.splitext(str(file_name or "").strip())[0]).strip()
    if not stem or stem.lower() in {"imported client", "website client", "brief", "document"}:
        stem = re.sub(r"[_\-]+", " ", str(caption_hint or "").strip()).strip()
    if not stem:
        return "Imported Client"
    stem = re.sub(r"^https?://", "", stem).strip()
    return " ".join(part.capitalize() for part in stem.split()[:4]) or "Imported Client"


def _build_missing_fields_template(display_name: str, missing_fields: list[str]) -> str:
    header = f"*Almost there for {display_name}*\n"
    body = "Most of the profile is built. I just need these details to finish:\n"
    for field in missing_fields:
        body += f"- {field}\n"
    body += "\nReply with all answers in one message."
    return header + body


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
        health = row.get("meta_health") or {}
        status_str = str(health.get("status") or "").strip().lower()
        if status_str == "connected":
            desc = "Meta connected"
        elif status_str == "expired_or_invalid":
            desc = "Meta expired"
        elif status_str == "missing":
            desc = "Meta not linked"
        elif row["connected"]:
            desc = "Connected"
        else:
            desc = "Needs Meta connection"
        rows.append({"id": f"{prefix}:{row['client_id']}", "title": row["display_name"], "description": desc})
    return [{"title": "Clients", "rows": rows}] if rows else []


def _send_button_card(phone: str, *, header_text: str = "", body_text: str = "", buttons: list[dict] | None = None, footer_text: str = "", fallback_text: str = "", audit_event: str = "") -> dict[str, Any]:
    if audit_event:
        _audit(phone, f"operator.interactive.button", {"event": audit_event})
    result = send_button_message(phone, header_text=header_text, body_text=body_text, buttons=buttons or [], footer_text=footer_text)
    if not result.get("success") and fallback_text:
        send_text_message(phone, fallback_text)
    return result


def _send_list_card(phone: str, *, header_text: str = "", body_text: str = "", button_text: str = "", sections: list[dict] | None = None, footer_text: str = "", fallback_text: str = "", audit_event: str = "") -> dict[str, Any]:
    if audit_event:
        _audit(phone, f"operator.interactive.list", {"event": audit_event})
    result = send_list_message(phone, header_text=header_text, body_text=body_text, button_text=button_text, sections=sections or [], footer_text=footer_text)
    if not result.get("success") and fallback_text:
        send_text_message(phone, fallback_text)
    return result


def _send_back_button(phone: str, label: str = "", target: str = "") -> dict[str, Any]:
    body = label or "Need to go back without restarting the flow?"
    nav_id = f"OP_NAV:{target}" if target else "OP_NAV:ROOT"
    return send_button_message(
        phone, header_text="Navigation", body_text=body,
        buttons=[{"id": nav_id, "title": "Go Back"}],
        footer_text="Jarvis \u00b7 Navigation",
    )


def _help_text() -> str:
    return (
        "\u26a1 *Jarvis \u00b7 Agency OS*\n\n"
        "\U0001f1f0\U0001f1fc  *United Marketing Agency*\n"
        "_Your dedicated AI operator is online and standing by._\n\n"
        "Here\u2019s what I can do for you:\n"
        "\u25b8 Create posts with AI-generated captions\n"
        "\u25b8 Onboard new clients in seconds\n"
        "\u25b8 Connect Meta (Facebook + Instagram)\n"
        "\u25b8 Schedule and publish releases\n"
        "\u25b8 Build research-backed strategy plans\n\n"
        "If buttons do not load, reply with one of these:\n"
        "1. New Post\n"
        "2. Add Client\n"
        "3. More\n\n"
        "Shortcuts: /clients, /schedules, /status, /strategy, /connect, /cancel"
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
