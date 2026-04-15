import os
import sys
import json
import logging
import base64
import requests
import io
import time
import socket
import collections
from html import unescape as html_unescape
from io import BytesIO
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse, StreamingResponse, JSONResponse, Response, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio
import shutil
import uuid
import re
import subprocess
import secrets
from typing import Optional, List, Any
from urllib.parse import quote, urlparse
from pypdf import PdfReader
from docx import Document
from input_validation import validate_client_id, validate_filename, InputValidationError

MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB

from schedule_utils import (
    format_display_date,
    normalize_prompt_date_typos,
    parse_iso_date,
    past_time_error_message,
    resolve_date_phrase,
    schedule_request_is_in_past,
)
from asset_store import (
    count_client_assets,
    delete_all_client_assets,
    delete_client_asset,
    get_asset_content,
    get_client_asset_record,
    get_asset_store,
    list_client_assets,
    repair_client_asset_for_meta,
    save_uploaded_asset,
)
from client_store import get_client_store
from draft_store import (
    delete_client_drafts,
    delete_draft_payload,
    get_draft_payload,
    get_draft_payload_by_id,
    resolve_draft_payload,
    list_client_drafts,
    rename_draft_payload,
    save_draft_payload,
)
from approval_store import (
    delete_all_pending_approvals,
    delete_client_pending_approvals,
    delete_pending_approval,
    get_pending_approval,
    list_pending_approvals,
    update_pending_approval,
)
from publish_run_store import delete_client_publish_runs, list_publish_runs
from strategy_plan_store import (
    delete_strategy_plan,
    delete_client_strategy_plans,
    get_strategy_plan,
    list_strategy_plans,
)
from queue_store import (
    SUPPORTED_EXTENSIONS,
    VIDEO_EXTENSIONS,
    detect_media_kind,
    sanitize_topic_hint,
)
from orchestrator_agent import resolve_client_id
from whatsapp_agent import run_whatsapp_agent, run_triage_agent
from whatsapp_operator import build_meta_connect_link, handle_operator_message, is_operator_phone
from whatsapp_transport import (
    normalize_inbound_message,
    send_button_message as transport_send_button_message,
    send_text_message as transport_send_text_message,
)
from publish_agent import publish_agent
from schedule_store import (
    add_scheduled_job,
    cleanup_delivered_jobs,
    delete_client_schedule_jobs,
    load_schedule,
    mark_job_delivered,
    mark_job_failed,
    remove_job,
    split_schedule_views,
)
from trend_research_service import build_client_trend_dossier, extract_website_digest, get_trend_research_health, search_recent
from runtime_state_store import (
    delete_auth_session,
    delete_operator_session_state,
    delete_expired_auth_sessions,
    get_auth_session,
    get_orchestrator_run_state,
    get_runtime_state_store,
    list_orchestrator_run_states,
    load_reschedule_session_map,
    record_operator_audit_event,
    save_auth_session,
    save_operator_session_state,
    save_orchestrator_run_state,
    save_reschedule_session_map,
    touch_auth_session,
)

load_dotenv()
# The synthesizer used to run on Mistral Nemo. With no paid OpenRouter credits available,
# keep intake on the lighter Qwen free route instead of the heavier 80B fallback.
SYNTHESIZER_MODEL = os.getenv("SYNTHESIZER_MODEL", "qwen/qwen3.6-plus-preview:free").strip() or "qwen/qwen3.6-plus-preview:free"
SYNTHESIS_CONNECT_TIMEOUT_SECONDS = float(os.getenv("SYNTHESIS_CONNECT_TIMEOUT_SECONDS", "8"))
SYNTHESIS_READ_TIMEOUT_SECONDS = float(os.getenv("SYNTHESIS_READ_TIMEOUT_SECONDS", "45"))
SYNTHESIS_TOTAL_TIMEOUT_SECONDS = float(os.getenv("SYNTHESIS_TOTAL_TIMEOUT_SECONDS", "90"))
SYNTHESIS_FAST_TIMEOUT_SECONDS = float(os.getenv("SYNTHESIS_FAST_TIMEOUT_SECONDS", "75"))
SMART_DRAFT_REF_RE = re.compile(
    r'@\[(?P<client>[^\]]+)\]\s+(?:draft_id:"(?P<draft_id>[^"]+)"\s+)?draft:"(?P<draft>[^"]+)"',
    re.IGNORECASE,
)
VISIBLE_SMART_DRAFT_RE = re.compile(
    r'@\[(?P<client>[^\]]+)\]\s+draft\s+[·Â·]\s+(?P<draft>.+?)(?=(?:\s+(?:please|post|publish|schedule|delete|move|refine|approve|for|now|today|tomorrow|next)\b)|$)',
    re.IGNORECASE,
)

HEADER_ACCENTS = ["🔵", "🟢", "🟠", "🟣"]


JARVIS_ADMIN_PASSWORD = os.getenv("JARVIS_ADMIN_PASSWORD", "").strip()
JARVIS_AUTH_ENABLED = bool(JARVIS_ADMIN_PASSWORD)
JARVIS_SESSION_TTL_HOURS = max(1, int(os.getenv("JARVIS_SESSION_TTL_HOURS", "12") or "12"))
_auth_sessions: dict[str, float] = {}
JARVIS_STRICT_STARTUP = str(os.getenv("JARVIS_STRICT_STARTUP", "")).strip().lower() in {"1", "true", "yes", "on"}
APPROVAL_ROUTING_MODES = {"desktop_first", "desktop_and_whatsapp", "whatsapp_only"}
VAULT_DRAFT_CACHE_TTL_SECONDS = max(60, int(os.getenv("VAULT_DRAFT_CACHE_TTL_SECONDS", "1800") or "1800"))
_vault_draft_cache: dict[str, tuple[float, dict]] = {}
RATE_LIMIT_WINDOW_SECONDS = max(15, int(os.getenv("JARVIS_RATE_LIMIT_WINDOW_SECONDS", "60") or "60"))
RATE_LIMIT_DEFAULTS = {
    "auth_login": max(3, int(os.getenv("JARVIS_RATE_LIMIT_AUTH_LOGIN", "8") or "8")),
    "orchestrator_chat": max(10, int(os.getenv("JARVIS_RATE_LIMIT_ORCH_CHAT", "60") or "60")),
    "orchestrator_run": max(3, int(os.getenv("JARVIS_RATE_LIMIT_ORCH_RUN", "20") or "20")),
    "strategy_plan": max(2, int(os.getenv("JARVIS_RATE_LIMIT_STRATEGY_PLAN", "20") or "20")),
    "synthesizer": max(1, int(os.getenv("JARVIS_RATE_LIMIT_SYNTH", "10") or "10")),
    "caption": max(2, int(os.getenv("JARVIS_RATE_LIMIT_CAPTION", "30") or "30")),
    "approval_action": max(3, int(os.getenv("JARVIS_RATE_LIMIT_APPROVAL_ACTION", "30") or "30")),
    "default": max(20, int(os.getenv("JARVIS_RATE_LIMIT_DEFAULT", "120") or "120")),
}
_rate_limit_buckets: dict[str, collections.deque[float]] = {}
_startup_validation_snapshot: dict[str, object] = {}


def describe_job_assets(job: dict) -> str:
    videos = list(job.get("videos", []) or [])
    images = list(job.get("images", []) or [])
    media_kind = str(job.get("media_kind", "") or "").strip().lower()

    if videos or media_kind == "video":
        return "1-video post"
    if len(images) > 1 or media_kind == "image_carousel":
        return f"{max(len(images), 2)}-image carousel" if images else "Image Carousel"
    if len(images) == 1 or media_kind == "image_single":
        return "Image Post"
    return "Media ready"


def _store_cached_vault_drafts(client_id: str, payload: dict | None) -> None:
    if not client_id or not isinstance(payload, dict):
        return
    _vault_draft_cache[str(client_id).strip()] = (time.time(), dict(payload))


def _get_cached_vault_drafts(client_id: str) -> dict | None:
    cache_key = str(client_id or "").strip()
    if not cache_key:
        return None
    cached = _vault_draft_cache.get(cache_key)
    if not cached:
        return None
    cached_at, payload = cached
    if (time.time() - cached_at) > VAULT_DRAFT_CACHE_TTL_SECONDS:
        _vault_draft_cache.pop(cache_key, None)
        return None
    return dict(payload or {})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _ensure_request_id(request: Request) -> str:
    existing = str(getattr(request.state, "request_id", "") or "").strip()
    if existing:
        return existing
    request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    return request_id


def _get_request_id(request: Request | None) -> str | None:
    if request is None:
        return None
    request_id = str(getattr(request.state, "request_id", "") or "").strip()
    return request_id or None


def _get_rate_limit_identity(request: Request) -> str:
    token = _extract_session_token(request)
    if token:
        return f"session:{token}"
    forwarded = str(request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        first_hop = forwarded.split(",", 1)[0].strip()
        if first_hop:
            return f"ip:{first_hop}"
    host = getattr(getattr(request, "client", None), "host", None)
    return f"ip:{host or 'unknown'}"


def _rate_limit_bucket_name(request: Request) -> str:
    path = request.url.path or "/"
    if path == "/api/auth/login":
        return "auth_login"
    if path == "/api/orchestrator-chat":
        return "orchestrator_chat"
    if path == "/api/orchestrator/run":
        return "orchestrator_run"
    if path.startswith("/api/strategy/"):
        return "strategy_plan"
    if path == "/api/synthesize-client":
        return "synthesizer"
    if path == "/api/caption/generate":
        return "caption"
    if path.startswith("/api/approvals/") and request.method.upper() == "POST":
        return "approval_action"
    return "default"


def _check_rate_limit(request: Request) -> dict | None:
    if not (request.url.path or "/").startswith("/api/"):
        return None
    bucket_name = _rate_limit_bucket_name(request)
    limit = RATE_LIMIT_DEFAULTS.get(bucket_name, RATE_LIMIT_DEFAULTS["default"])
    window_seconds = RATE_LIMIT_WINDOW_SECONDS
    identity = _get_rate_limit_identity(request)
    key = f"{bucket_name}:{identity}"
    now = time.time()
    bucket = _rate_limit_buckets.setdefault(key, collections.deque())
    while bucket and (now - bucket[0]) > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        retry_after = max(1, int(window_seconds - (now - bucket[0])))
        return {
            "bucket": bucket_name,
            "limit": limit,
            "window_seconds": window_seconds,
            "retry_after_seconds": retry_after,
            "identity": identity,
        }
    bucket.append(now)
    return None


def _audit_event(
    event_type: str,
    payload: dict | None = None,
    *,
    request: Request | None = None,
    actor: str | None = None,
) -> None:
    try:
        record_operator_audit_event(
            event_type=event_type,
            payload=dict(payload or {}),
            actor=actor,
            request_id=_get_request_id(request),
        )
    except Exception as exc:
        logger.warning("Audit event failure for %s: %s", event_type, exc)


def _load_orchestrator_run(run_id: str) -> dict | None:
    key = str(run_id or "").strip()
    if not key:
        return None
    cached = _orchestrator_runs.get(key)
    if isinstance(cached, dict):
        return cached
    persisted = get_orchestrator_run_state(key)
    if isinstance(persisted, dict):
        _orchestrator_runs[key] = persisted
        return persisted
    return None


def _save_orchestrator_run(run: dict) -> dict:
    persisted = save_orchestrator_run_state(dict(run or {}))
    run_id = str(persisted.get("run_id") or "").strip()
    if run_id:
        _orchestrator_runs[run_id] = persisted
    return persisted


def normalize_smart_draft_prompt(prompt: str) -> str:
    raw = str(prompt or "")
    if not raw:
        return raw

    def repl(match: re.Match) -> str:
        client = str(match.group("client") or "").strip()
        draft = str(match.group("draft") or "").strip()
        return f"@[{client}] using the saved creative draft named \"{draft}\""

    normalized = SMART_DRAFT_REF_RE.sub(repl, raw)
    return VISIBLE_SMART_DRAFT_RE.sub(repl, normalized)


def extract_smart_draft_refs(prompt: str) -> list[dict]:
    refs = []
    raw = str(prompt or "")
    for match in SMART_DRAFT_REF_RE.finditer(raw):
        client = str(match.group("client") or "").strip()
        draft = str(match.group("draft") or "").strip()
        draft_id = str(match.group("draft_id") or "").strip()
        if client and draft_id:
            refs.append({"client_id": client, "draft_name": draft, "draft_id": draft_id})
    return refs

def normalize_prompt_with_known_draft_refs(prompt: str, draft_refs: list[dict]) -> str:
    normalized = str(prompt or "")
    if not normalized or not draft_refs:
        return normalized
    ordered_refs = sorted(
        [ref for ref in draft_refs if isinstance(ref, dict)],
        key=lambda ref: len(str(ref.get("draft_name") or "")),
        reverse=True,
    )
    for ref in ordered_refs:
        client_id = str(ref.get("client_id") or "").strip()
        draft_id = str(ref.get("draft_id") or "").strip()
        draft_name = str(ref.get("draft_name") or "").strip()
        if not client_id or not draft_name:
            continue
        visible_tokens = [
            f"@[{client_id.lower()}] Draft · {draft_name}",
            f"@[{client_id.lower()}] Draft · {draft_name}",
            f"@[{client_id.lower()}] Draft - {draft_name}",
        ]
        canonical = f'@[{client_id}] draft_id:"{draft_id}" draft:"{draft_name}"' if draft_id else f'@[{client_id}] draft:"{draft_name}"'
        for visible_token in visible_tokens:
            normalized = re.sub(re.escape(visible_token), canonical, normalized, flags=re.IGNORECASE)
    return normalized


def _approval_matches_schedule(job: dict, schedule_jobs: list[dict]) -> bool:
    approval_id = str(job.get("approval_id") or "").strip().upper()
    client_id = str(job.get("client") or "").strip()
    draft_id = str(job.get("draft_id") or "").strip()
    draft_name = str(job.get("draft_name") or "").strip()
    scheduled_date = str(job.get("scheduled_date") or "").strip()
    time_text = str(job.get("time") or "").strip()
    for scheduled_job in schedule_jobs:
        if approval_id and str(scheduled_job.get("approval_id") or "").strip().upper() == approval_id:
            return True
        if client_id and str(scheduled_job.get("client") or "").strip() != client_id:
            continue
        if draft_id and str(scheduled_job.get("draft_id") or "").strip() == draft_id:
            if scheduled_date == str(scheduled_job.get("scheduled_date") or "").strip() and time_text == str(scheduled_job.get("time") or "").strip():
                return True
        elif draft_name and str(scheduled_job.get("draft_name") or "").strip() == draft_name:
            if scheduled_date == str(scheduled_job.get("scheduled_date") or "").strip() and time_text == str(scheduled_job.get("time") or "").strip():
                return True
    return False


def list_live_pending_approvals() -> list[dict]:
    approvals = list_pending_approvals()
    if not approvals:
        return []
    schedule_jobs = load_schedule("schedule.json")
    live = []
    for approval in approvals:
        approval_id = str(approval.get("approval_id") or "").strip()
        if schedule_request_is_in_past(
            str(approval.get("time") or "").strip(),
            scheduled_date=str(approval.get("scheduled_date") or "").strip() or None,
            raw_days=approval.get("days", []),
        ):
            if approval_id:
                delete_pending_approval(approval_id)
            continue
        if _approval_matches_schedule(approval, schedule_jobs):
            if approval_id:
                delete_pending_approval(approval_id)
            continue
        live.append(approval)
    return live


ORCHESTRATOR_BATCH_ACTIONS = {"post_now", "send_for_approval", "schedule"}
_orchestrator_runs: dict[str, dict] = {}


def _resolve_orchestrator_client_id(raw_client_id: str) -> str:
    candidate = str(raw_client_id or "").strip()
    if not candidate:
        return ""
    try:
        for known_client in get_client_store().list_client_ids():
            if str(known_client).lower() == candidate.lower():
                return str(known_client)
        normalized_candidate = _normalize_orchestrator_client_key(candidate)
        for known_client in get_client_store().list_client_ids():
            if _normalize_orchestrator_client_key(str(known_client)) == normalized_candidate:
                return str(known_client)
    except Exception:
        pass
    return candidate


def _infer_orchestrator_platforms(client_payload: dict, requested_platforms: list[str] | None = None) -> list[str]:
    available = []
    if str((client_payload or {}).get("facebook_page_id") or "").strip():
        available.append("facebook")
    if str((client_payload or {}).get("instagram_account_id") or "").strip():
        available.append("instagram")
    if requested_platforms:
        normalized = [str(item).strip().lower() for item in requested_platforms if str(item).strip()]
        filtered = [item for item in available if item in normalized]
        if filtered:
            return filtered
    return available


def _resolve_orchestrator_draft(client_id: str, draft_name: str | None = None, draft_id: str | None = None) -> dict | None:
    draft_payload = resolve_draft_payload(client_id, draft_name=draft_name, draft_id=draft_id)
    if draft_payload is None:
        return None
    resolved_name = str(
        draft_payload.get("bundle_name")
        or draft_payload.get("draft_name")
        or draft_name
        or ""
    ).strip()
    resolved_id = str(draft_payload.get("draft_id") or draft_id or "").strip()
    items = list(draft_payload.get("items", []) or [])
    return {
        "draft_name": resolved_name,
        "draft_id": resolved_id,
        "payload": draft_payload,
        "items": items,
        "media_kind": str(draft_payload.get("bundle_type") or "image_single").strip(),
    }


def _collect_orchestrator_media_warnings(client_id: str, draft_resolution: dict | None, platforms: list[str]) -> list[str]:
    normalized_platforms = [str(item).strip().lower() for item in (platforms or []) if str(item).strip()]
    if not client_id or not draft_resolution or "instagram" not in normalized_platforms:
        return []

    image_paths: list[str] = []
    video_paths: list[str] = []
    for item in list(draft_resolution.get("items", []) or []):
        filename = str((item or {}).get("filename") or "").strip()
        if not filename:
            continue
        media_kind = str((item or {}).get("kind") or draft_resolution.get("media_kind") or "").strip().lower() or "image"
        managed_path = f"assets/{client_id}/{filename}"
        if media_kind == "video":
            video_paths.append(managed_path)
        else:
            image_paths.append(managed_path)

    preflight = publish_agent.preflight_media(image_paths, video_paths, instagram_enabled=True)
    instagram_error = str(preflight.get("instagram_error") or "").strip()
    if instagram_error:
        return [instagram_error]

    asset_index: dict[str, dict] = {}
    try:
        for asset in list_client_assets(client_id):
            filename = str(asset.get("filename") or asset.get("original_filename") or "").strip()
            if filename:
                asset_index[filename] = asset
    except Exception:
        return []

    warnings: list[str] = []
    seen: set[str] = set()
    for item in list(draft_resolution.get("items", []) or []):
        filename = str((item or {}).get("filename") or "").strip()
        if not filename:
            continue
        asset = asset_index.get(filename) or {}
        metadata = (asset.get("metadata") or {}) if isinstance(asset, dict) else {}
        media_kind = str((item or {}).get("kind") or draft_resolution.get("media_kind") or "").strip().lower() or "image"
        is_valid_ig, warning = get_instagram_asset_warning(client_id, filename, media_kind, metadata)
        if is_valid_ig:
            continue
        message = str(warning or f"{filename} needs Instagram-safe formatting before feed publishing.").strip()
        if message and message not in seen:
            warnings.append(message)
            seen.add(message)
    return warnings


def _render_orchestrator_platform_label(platforms: list[str]) -> str:
    if not platforms:
        return "No platforms configured"
    return " + ".join(item.capitalize() for item in platforms)


def _normalize_orchestrator_schedule_payload(schedule: dict | None = None) -> dict:
    return {
        "scheduled_date": str((schedule or {}).get("scheduled_date") or "").strip(),
        "time": str((schedule or {}).get("time") or "").strip(),
    }


def _normalize_orchestrator_client_key(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    cleaned = re.sub(r"[_\-]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _build_orchestrator_task_entry(raw_task: dict, index: int) -> tuple[dict, list[str], bool]:
    raw_client_id = str(raw_task.get("client_id") or "").strip()
    raw_draft_name = str(raw_task.get("draft_name") or raw_task.get("draft_label") or "").strip()
    raw_draft_id = str(raw_task.get("draft_id") or "").strip()
    normalized_action = str(raw_task.get("action") or "").strip().lower()
    schedule_payload = _normalize_orchestrator_schedule_payload(raw_task.get("schedule") or raw_task)
    parser_status = str(raw_task.get("status") or "").strip().lower()
    parser_warning = str(raw_task.get("warning") or "").strip()
    client_id = _resolve_orchestrator_client_id(raw_client_id)
    item_warnings: list[str] = []
    blocked_reason = parser_warning if parser_status in {"ambiguous", "invalid", "blocked"} else ""

    if normalized_action not in ORCHESTRATOR_BATCH_ACTIONS and not blocked_reason:
        blocked_reason = f"Unsupported task action '{normalized_action or 'unknown'}'."

    client_payload = get_client_store().get_client(client_id) if client_id and not blocked_reason else None
    if not blocked_reason and (not client_id or not client_payload):
        blocked_reason = f"Client '{raw_client_id or client_id}' could not be resolved."

    draft_resolution = None
    if not blocked_reason:
        draft_resolution = _resolve_orchestrator_draft(client_id, draft_name=raw_draft_name, draft_id=raw_draft_id)
        if not draft_resolution:
            blocked_reason = f"Draft '{raw_draft_name or raw_draft_id}' was not found for {client_id}."

    platforms = _infer_orchestrator_platforms(client_payload or {}, raw_task.get("platforms"))
    if not blocked_reason and normalized_action == "post_now" and not platforms:
        blocked_reason = f"{client_id} is missing publishable Facebook or Instagram credentials."

    if not blocked_reason and normalized_action in {"send_for_approval", "schedule"}:
        if not schedule_payload["scheduled_date"] or not schedule_payload["time"]:
            blocked_reason = "A release date and time are required for scheduled or approval tasks."

    if not blocked_reason and normalized_action == "schedule" and not platforms:
        blocked_reason = f"{client_id} is missing publishable Facebook or Instagram credentials."

    if not blocked_reason and normalized_action in {"post_now", "schedule"}:
        from orchestrator_agent import verify_meta_token
        token_issue = verify_meta_token(client_id)
        if token_issue:
            blocked_reason = token_issue

    if blocked_reason:
        item_warnings.insert(0, blocked_reason)

    draft_name = raw_draft_name
    draft_id = raw_draft_id
    media_kind = "unknown"
    item_count = 0
    media_warnings: list[str] = []
    if draft_resolution:
        draft_name = draft_resolution["draft_name"]
        draft_id = draft_resolution["draft_id"]
        media_kind = draft_resolution["media_kind"]
        item_count = len(draft_resolution["items"])
        media_warnings = _collect_orchestrator_media_warnings(client_id, draft_resolution, platforms)

    entry = {
        "item_id": f"{client_id or raw_client_id}::{draft_id or draft_name or index}",
        "index": index,
        "client_id": client_id or raw_client_id,
        "draft_name": draft_name,
        "draft_id": draft_id,
        "media_kind": media_kind,
        "asset_count": item_count,
        "platforms": platforms,
        "platform_label": _render_orchestrator_platform_label(platforms),
        "action": normalized_action,
        "schedule": schedule_payload,
        "status": "blocked" if blocked_reason else "ready",
        "warning": " ".join(warning for warning in item_warnings if warning).strip(),
        "preflight_warnings": [],
        "has_media_warnings": False,
        "summary": f"{client_id or raw_client_id} · {draft_name or 'Draft'}",
        "source_text": str(raw_task.get("source_text") or "").strip(),
    }
    return entry, item_warnings, not blocked_reason


def _build_orchestrator_task_plan(tasks: list[dict]) -> dict:
    if not tasks:
        raise HTTPException(status_code=400, detail="At least one task must be supplied.")

    warnings: list[str] = []
    plan_items: list[dict] = []
    ready_count = 0
    action_counts: dict[str, int] = {}

    for index, raw_task in enumerate(tasks, start=1):
        entry, item_warnings, is_ready = _build_orchestrator_task_entry(raw_task, index)
        plan_items.append(entry)
        warnings.extend(item_warnings)
        if is_ready:
            ready_count += 1
        action_key = str(entry.get("action") or "").strip().lower()
        if action_key:
            action_counts[action_key] = action_counts.get(action_key, 0) + 1

    distinct_actions = [action for action in action_counts.keys() if action]
    plan_action = distinct_actions[0] if len(distinct_actions) == 1 else "mixed"
    has_blocked = any(str(item.get("status") or "").lower() == "blocked" for item in plan_items)

    return {
        "action": plan_action,
        "tasks": plan_items,
        "items": plan_items,
        "warnings": warnings,
        "can_run": ready_count > 0 and not has_blocked,
        "totals": {
            "total": len(plan_items),
            "ready": ready_count,
            "blocked": max(len(plan_items) - ready_count, 0),
            "post_now": action_counts.get("post_now", 0),
            "schedule": action_counts.get("schedule", 0),
            "send_for_approval": action_counts.get("send_for_approval", 0),
        },
    }


def _build_orchestrator_batch_plan(
    action: str | None = None,
    items: list[dict] | None = None,
    schedule: dict | None = None,
    tasks: list[dict] | None = None,
) -> dict:
    if tasks:
        return _build_orchestrator_task_plan(tasks)

    normalized_action = str(action or "").strip().lower()
    if normalized_action not in ORCHESTRATOR_BATCH_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported orchestrator action: {action}")
    if not items:
        raise HTTPException(status_code=400, detail="At least one draft must be selected.")

    schedule_payload = _normalize_orchestrator_schedule_payload(schedule)
    task_payloads = [
        {
            "client_id": raw_item.get("client_id"),
            "draft_name": raw_item.get("draft_name"),
            "draft_id": raw_item.get("draft_id"),
            "platforms": raw_item.get("platforms"),
            "action": normalized_action,
            "scheduled_date": schedule_payload["scheduled_date"],
            "time": schedule_payload["time"],
            "status": "ready",
        }
        for raw_item in items
    ]
    plan = _build_orchestrator_task_plan(task_payloads)
    plan["schedule"] = schedule_payload
    return plan


def _summarize_orchestrator_task_preview(plan: dict) -> str:
    totals = dict(plan.get("totals") or {})
    ready = int(totals.get("ready") or 0)
    total = int(totals.get("total") or 0)
    scheduled = int(totals.get("schedule") or 0)
    immediate = int(totals.get("post_now") or 0)
    blocked = int(totals.get("blocked") or 0)
    parts = [f"I parsed {total} release task{'s' if total != 1 else ''}."]
    if immediate:
        parts.append(f"{immediate} will post now")
    if scheduled:
        parts.append(f"{scheduled} will be scheduled")
    if blocked:
        parts.append(f"{blocked} need{'s' if blocked == 1 else ''} clarification")
    summary = ". ".join(parts).strip().rstrip(".") + "."
    if ready and not blocked:
        summary += ' Review the parsed release cards below, then say "run it" when you are ready.'
    elif blocked:
        summary += " Fix the flagged clause before Jarvis can execute the full set safely."
    return summary


def _normalize_orchestrator_item_result(action: str, result: dict | str) -> dict:
    if isinstance(result, dict):
        enriched = {
            "approval_id": str(result.get("approval_id") or "").strip(),
            "job_id": str(result.get("job_id") or "").strip(),
            "whatsapp_sent": bool(result.get("whatsapp_sent")) if "whatsapp_sent" in result else None,
            "job": result.get("job"),
        }
        if result.get("error"):
            return {
                "status": "failed",
                "message": str(result.get("error") or "").strip(),
                "raw": result,
                **{key: value for key, value in enriched.items() if value not in ("", None)},
            }
        raw_status = str(result.get("status") or "").strip().lower()
        if action == "post_now":
            if raw_status == "partial_success":
                return {
                    "status": "partial_success",
                    "message": str(result.get("message") or "Partial success.").strip(),
                    "raw": result,
                }
            if raw_status == "success":
                return {
                    "status": "published",
                    "message": str(result.get("message") or "Published.").strip(),
                    "raw": result,
                    **{key: value for key, value in enriched.items() if value not in ("", None)},
                }
        if action == "send_for_approval" and raw_status in {"success", "partial_success"}:
            approval_status = "approval_sent_whatsapp" if result.get("whatsapp_sent") else "approval_ready"
            default_message = "Approval sent to WhatsApp." if result.get("whatsapp_sent") else "Approval ready for review."
            return {
                "status": approval_status,
                "message": str(result.get("message") or default_message).strip(),
                "raw": result,
                **{key: value for key, value in enriched.items() if value not in ("", None)},
            }
        if action == "schedule" and raw_status == "success":
            return {
                "status": "scheduled",
                "message": str(result.get("message") or "Scheduled.").strip(),
                "raw": result,
                **{key: value for key, value in enriched.items() if value not in ("", None)},
            }
        if raw_status == "success":
            completion_label = "Approval requested." if action == "send_for_approval" else "Scheduled."
            return {
                "status": "completed",
                "message": str(result.get("message") or completion_label).strip(),
                "raw": result,
                **{key: value for key, value in enriched.items() if value not in ("", None)},
            }
        if raw_status:
            return {
                "status": raw_status,
                "message": str(result.get("message") or raw_status.replace("_", " ")).strip(),
                "raw": result,
                **{key: value for key, value in enriched.items() if value not in ("", None)},
            }
    return {
        "status": "completed",
        "message": str(result or "").strip() or "Completed.",
        "raw": result,
    }


def _effective_orchestrator_approval_routing(run: dict, item: dict) -> str:
    return normalize_approval_routing_mode(
        item.get("approval_routing")
        or run.get("approval_routing_override")
        or get_approval_routing_mode()
    )


def _recompute_orchestrator_run_totals(run: dict) -> None:
    items = list(run.get("items") or [])
    totals = {
        "total": len(items),
        "ready": 0,
        "blocked": 0,
        "post_now": 0,
        "schedule": 0,
        "send_for_approval": 0,
        "queued": 0,
        "preflight": 0,
        "publishing": 0,
        "published": 0,
        "scheduled_complete": 0,
        "approval_ready": 0,
        "approval_sent_whatsapp": 0,
        "failed": 0,
    }
    for item in items:
        action = str(item.get("action") or "").strip().lower()
        status = str(item.get("status") or "").strip().lower()
        if action in {"post_now", "schedule", "send_for_approval"}:
            totals[action] += 1
        if status == "ready":
            totals["ready"] += 1
        elif status == "blocked":
            totals["blocked"] += 1
        elif status == "queued":
            totals["queued"] += 1
        elif status == "preflight":
            totals["preflight"] += 1
        elif status == "publishing":
            totals["publishing"] += 1
        elif status == "published":
            totals["published"] += 1
        elif status == "scheduled":
            totals["scheduled_complete"] += 1
        elif status == "approval_ready":
            totals["approval_ready"] += 1
        elif status == "approval_sent_whatsapp":
            totals["approval_sent_whatsapp"] += 1
        elif status == "failed":
            totals["failed"] += 1
    run["totals"] = totals


async def _execute_orchestrator_batch_run(run_id: str) -> None:
    run = _load_orchestrator_run(run_id)
    if not run:
        return

    from orchestrator_agent import AutonomousScheduleTool, RequestApprovalTool, TriggerPipelineNowTool
    from approval_store import get_pending_approval

    trigger_tool = TriggerPipelineNowTool()
    approval_tool = RequestApprovalTool()
    schedule_tool = AutonomousScheduleTool()

    run["status"] = "running"
    run["started_at"] = _utc_now_iso()
    _recompute_orchestrator_run_totals(run)
    run = _save_orchestrator_run(run)
    _audit_event(
        "orchestrator.run_started",
        {
            "run_id": run_id,
            "action": run.get("action"),
            "item_count": len(run.get("items") or []),
        },
        actor="jarvis-orchestrator",
    )

    try:
        for item in run["items"]:
            if item.get("status") == "blocked":
                item["status"] = "failed"
                item["message"] = str(item.get("warning") or "Blocked by plan validation.").strip()
                item["completed_at"] = _utc_now_iso()
                _recompute_orchestrator_run_totals(run)
                run = _save_orchestrator_run(run)
                continue

            item["status"] = "preflight"
            item["phase"] = "Preflight"
            item["message"] = "Checking the selected draft, credentials, and release route."
            _recompute_orchestrator_run_totals(run)
            run = _save_orchestrator_run(run)
            await asyncio.sleep(0)

            try:
                action = str(item.get("action") or run["action"] or "").strip().lower()
                item_schedule = _normalize_orchestrator_schedule_payload(item.get("schedule") or run.get("schedule"))
                approval_routing_mode = _effective_orchestrator_approval_routing(run, item)
                effective_action = "send_for_approval" if action == "schedule" and approval_routing_mode == "whatsapp_only" else action
                schedule_days = [] if item_schedule["scheduled_date"] else ["today"]
                _audit_event(
                    "orchestrator.item_started",
                    {
                        "run_id": run_id,
                        "client_id": item.get("client_id"),
                        "draft_id": item.get("draft_id"),
                        "draft_name": item.get("draft_name"),
                        "action": action,
                        "effective_action": effective_action,
                        "approval_routing": approval_routing_mode,
                        "scheduled_date": item_schedule.get("scheduled_date"),
                        "time": item_schedule.get("time"),
                    },
                    actor="jarvis-orchestrator",
                )
                if action == "post_now":
                    item["status"] = "publishing"
                    item["phase"] = "Publishing"
                    item["message"] = "Jarvis is sending this draft to the publish pipeline now."
                    tool_result = await asyncio.to_thread(
                        trigger_tool.execute,
                        client_id=item["client_id"],
                        bundle_name=item.get("draft_name"),
                        draft_id=item.get("draft_id") or None,
                        topic=item.get("draft_name") or "",
                    )
                elif effective_action == "send_for_approval":
                    item["status"] = "publishing"
                    item["phase"] = "Routing Approval"
                    item["message"] = (
                        "Jarvis is routing this release into the WhatsApp owner approval lane."
                        if approval_routing_mode == "whatsapp_only"
                        else "Jarvis is creating the approval card and preparing the review route."
                    )
                    tool_result = await asyncio.to_thread(
                        approval_tool.execute,
                        client_id=item["client_id"],
                        topic=item.get("draft_name") or "Scheduled release",
                        days=schedule_days,
                        time=item_schedule["time"],
                        bundle_name=item.get("draft_name"),
                        draft_id=item.get("draft_id") or None,
                        scheduled_date=item_schedule["scheduled_date"],
                        approval_routing_override=approval_routing_mode,
                    )
                else:
                    item["status"] = "publishing"
                    item["phase"] = "Scheduling"
                    item["message"] = "Jarvis is writing this release into the schedule."
                    tool_result = await asyncio.to_thread(
                        schedule_tool.execute,
                        client_id=item["client_id"],
                        topic=item.get("draft_name") or "Scheduled release",
                        days=schedule_days,
                        post_time=item_schedule["time"],
                        bundle_name=item.get("draft_name"),
                        draft_id=item.get("draft_id") or None,
                        scheduled_date=item_schedule["scheduled_date"],
                    )

                normalized_result = _normalize_orchestrator_item_result(effective_action, tool_result)
                if effective_action == "send_for_approval" and isinstance(normalized_result.get("raw"), dict):
                    approval_id = str(normalized_result["raw"].get("approval_id") or "").strip()
                    if approval_id:
                        approval_job = get_pending_approval(approval_id)
                        normalized_result["raw"]["job"] = approval_job
                        normalized_result["job"] = approval_job
                item["status"] = normalized_result["status"]
                item["message"] = normalized_result["message"]
                item["result"] = normalized_result["raw"]
                if normalized_result.get("approval_id"):
                    item["approval_id"] = normalized_result["approval_id"]
                if normalized_result.get("job_id"):
                    item["job_id"] = normalized_result["job_id"]
                if normalized_result.get("job"):
                    item["job"] = normalized_result["job"]
                if normalized_result.get("whatsapp_sent") is not None:
                    item["whatsapp_sent"] = normalized_result["whatsapp_sent"]
                item["completed_at"] = _utc_now_iso()
                _recompute_orchestrator_run_totals(run)
                run = _save_orchestrator_run(run)
                _audit_event(
                    "orchestrator.item_completed",
                    {
                        "run_id": run_id,
                        "client_id": item.get("client_id"),
                        "draft_id": item.get("draft_id"),
                        "draft_name": item.get("draft_name"),
                        "action": action,
                        "effective_action": effective_action,
                        "status": item.get("status"),
                        "message": item.get("message"),
                    },
                    actor="jarvis-orchestrator",
                )
            except Exception as exc:
                logger.error(
                    "Orchestrator item execution failed for %s / %s: %s",
                    item.get("client_id"),
                    item.get("draft_name"),
                    exc,
                    exc_info=True,
                )
                item["status"] = "failed"
                item["message"] = f"{type(exc).__name__}: {str(exc)}"
                item["completed_at"] = _utc_now_iso()
                _recompute_orchestrator_run_totals(run)
                run = _save_orchestrator_run(run)
                _audit_event(
                    "orchestrator.item_failed",
                    {
                        "run_id": run_id,
                        "client_id": item.get("client_id"),
                        "draft_id": item.get("draft_id"),
                        "draft_name": item.get("draft_name"),
                        "action": item.get("action") or run.get("action"),
                        "message": item.get("message"),
                    },
                    actor="jarvis-orchestrator",
                )

        final_statuses = [str(item.get("status") or "").strip().lower() for item in run["items"]]
        successful_statuses = {"published", "scheduled", "approval_ready", "approval_sent_whatsapp", "completed", "partial_success"}
        if any(status == "failed" for status in final_statuses) and any(status in successful_statuses for status in final_statuses):
            run["status"] = "partial_success"
        elif any(status == "failed" for status in final_statuses):
            run["status"] = "failed"
        elif any(status == "partial_success" for status in final_statuses):
            run["status"] = "partial_success"
        else:
            run["status"] = "completed"
        _recompute_orchestrator_run_totals(run)
    finally:
        run["completed_at"] = _utc_now_iso()
        run = _save_orchestrator_run(run)
        _audit_event(
            "orchestrator.run_finished",
            {
                "run_id": run_id,
                "status": run.get("status"),
                "totals": dict(run.get("totals") or {}),
            },
            actor="jarvis-orchestrator",
        )

app = FastAPI(title="Jarvis WhatsApp Listener")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DASHBOARD_PATH = os.path.join(os.path.dirname(__file__), "jarvis-dashboard.html")
LOCKSCREEN_DIST_DIR = os.path.join(os.path.dirname(__file__), "jarvis-lockscreen-vite", "dist")
LOCKSCREEN_INDEX_PATH = os.path.join(LOCKSCREEN_DIST_DIR, "index.html")

if os.path.isdir(LOCKSCREEN_DIST_DIR):
    app.mount("/lockscreen-static", StaticFiles(directory=LOCKSCREEN_DIST_DIR), name="jarvis_lockscreen_static")


@app.get("/")
async def serve_lockscreen_root():
    if not os.path.exists(LOCKSCREEN_INDEX_PATH):
        raise HTTPException(status_code=404, detail="Lockscreen build missing")
    return FileResponse(
        LOCKSCREEN_INDEX_PATH,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/app")
async def serve_dashboard_app():
    if not os.path.exists(DASHBOARD_PATH):
        raise HTTPException(status_code=404, detail="Dashboard file missing")
    return FileResponse(
        DASHBOARD_PATH,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/jarvis-dashboard.html")
async def serve_dashboard_file():
    return await serve_dashboard_app()


@app.middleware("http")
async def jarvis_request_middleware(request: Request, call_next):
    request_id = _ensure_request_id(request)
    if (request.url.path or "/").startswith("/api/"):
        limited = _check_rate_limit(request)
        if limited:
            _audit_event(
                "security.rate_limit_exceeded",
                {
                    "path": request.url.path,
                    "method": request.method,
                    **limited,
                },
                request=request,
                actor=limited.get("identity"),
            )
            response = JSONResponse(
                status_code=429,
                content={
                    "status": "error",
                    "reason": "Rate limit exceeded.",
                    "retry_after_seconds": limited["retry_after_seconds"],
                    "request_id": request_id,
                },
            )
            response.headers["x-request-id"] = request_id
            response.headers["Retry-After"] = str(limited["retry_after_seconds"])
            return response
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.middleware("http")
async def jarvis_auth_middleware(request: Request, call_next):
    _ensure_request_id(request)
    path = request.url.path or "/"
    if request.method == "OPTIONS" or not path.startswith("/api/") or _is_public_path(path):
        return await call_next(request)

    if JARVIS_AUTH_ENABLED and not _is_valid_session(_extract_session_token(request)):
        _audit_event(
            "auth.denied",
            {"path": path, "method": request.method},
            request=request,
            actor=_get_rate_limit_identity(request),
        )
        return JSONResponse(
            status_code=401,
            content={
                "status": "auth_required",
                "reason": "Jarvis admin authentication is required for this route.",
                "request_id": _get_request_id(request),
            },
        )

    return await call_next(request)

# Serve asset images so Meta's Graph API can download them via the tunnel
os.makedirs("assets", exist_ok=True)

# --- ENVIRONMENT VARIABLES ---
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_TEST_PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "jarvis_webhook_secret_2026")
GRAPH_API_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")
RUNTIME_PROBE_TTL_SECONDS = 90
_runtime_probe_cache: dict[str, tuple[float, dict]] = {}


def _cleanup_auth_sessions() -> None:
    _auth_sessions.clear()
    delete_expired_auth_sessions(now_iso=_utc_now_iso())


def _extract_session_token(request: Request) -> str:
    token = str(request.headers.get("x-jarvis-auth") or "").strip()
    if token:
        return token

    auth_header = str(request.headers.get("authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    return str(request.query_params.get("session_token") or "").strip()


def _is_valid_session(token: str) -> bool:
    if not JARVIS_AUTH_ENABLED:
        return True
    if not token:
        return False
    _cleanup_auth_sessions()
    session = get_auth_session(token)
    if not session:
        return False
    expires_at = _parse_iso_datetime(session.get("expires_at"))
    if not expires_at or expires_at <= _utc_now():
        delete_auth_session(token)
        return False
    touch_auth_session(token, seen_at=_utc_now_iso())
    _auth_sessions[token] = expires_at.timestamp()
    return True


def _issue_session_token(payload: dict | None = None) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    expires_at = _utc_now() + timedelta(hours=JARVIS_SESSION_TTL_HOURS)
    save_auth_session(token, expires_at.isoformat(), payload=payload or {})
    _auth_sessions[token] = expires_at.timestamp()
    return token, expires_at.isoformat()


def _is_public_path(path: str) -> bool:
    if path.startswith("/webhook"):
        return True
    if path.startswith("/assets"):
        return True
    if path.startswith("/api/auth/"):
        return True
    if path == "/api/health":
        return True
    if path == "/api/data-backend":
        return True
    return False


def _build_asset_headers(content: bytes, mime_type: str) -> dict[str, str]:
    headers = {
        "Cache-Control": "public, max-age=300",
        "Content-Length": str(len(content)),
    }
    if mime_type.startswith("video/"):
        headers["Accept-Ranges"] = "bytes"
    return headers


def _parse_range_header(range_header: str, content_length: int) -> tuple[int, int] | None:
    value = str(range_header or "").strip().lower()
    if not value.startswith("bytes="):
        return None
    spec = value[6:].strip()
    if "," in spec or "-" not in spec:
        return None
    start_raw, end_raw = spec.split("-", 1)
    start_raw = start_raw.strip()
    end_raw = end_raw.strip()
    try:
        if start_raw == "":
            suffix = int(end_raw)
            if suffix <= 0:
                return None
            start = max(content_length - suffix, 0)
            end = content_length - 1
        else:
            start = int(start_raw)
            end = int(end_raw) if end_raw else content_length - 1
    except ValueError:
        return None

    if start < 0 or end < start or start >= content_length:
        return None
    end = min(end, content_length - 1)
    return start, end


@app.api_route("/assets/{client_id}/{filename:path}", methods=["GET", "HEAD"])
async def api_serve_asset(request: Request, client_id: str, filename: str):
    asset = get_asset_content(client_id, filename)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")
    content, mime_type = asset
    headers = _build_asset_headers(content, mime_type)
    if request.method == "HEAD":
        return Response(status_code=200, media_type=mime_type, headers=headers)
    if mime_type.startswith("video/"):
        range_header = request.headers.get("range")
        if range_header:
            parsed = _parse_range_header(range_header, len(content))
            if not parsed:
                invalid_headers = {
                    **headers,
                    "Content-Range": f"bytes */{len(content)}",
                }
                return Response(status_code=416, headers=invalid_headers)
            start, end = parsed
            chunk = content[start:end + 1]
            range_headers = {
                **headers,
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {start}-{end}/{len(content)}",
            }
            return Response(status_code=206, content=chunk, media_type=mime_type, headers=range_headers)
    return StreamingResponse(
        io.BytesIO(content),
        media_type=mime_type,
        headers=headers,
    )

def get_agency_config() -> dict:
    file_config = {}
    if os.path.exists("agency_config.json"):
        try:
            with open("agency_config.json", "r", encoding="utf-8") as f:
                file_config = json.load(f)
        except Exception:
            file_config = {}
    env_owner_phone = os.getenv("OWNER_PHONE", "").strip()
    env_whatsapp_token = os.getenv("WHATSAPP_TOKEN", "").strip()
    env_whatsapp_phone_id = os.getenv("WHATSAPP_TEST_PHONE_NUMBER_ID", "").strip()
    return {
        "owner_phone": env_owner_phone or str(file_config.get("owner_phone") or "").strip(),
        # Agency-level WhatsApp runtime secrets are env-managed in production.
        "whatsapp_access_token": env_whatsapp_token,
        "whatsapp_phone_id": env_whatsapp_phone_id,
        "approval_routing": str(file_config.get("approval_routing") or "desktop_first").strip() or "desktop_first",
    }


def get_whatsapp_runtime_config() -> tuple[str, str]:
    config = get_agency_config()
    token = str(config.get("whatsapp_access_token", "")).strip()
    phone_id = str(config.get("whatsapp_phone_id", "")).strip()
    return token, phone_id


def _meta_oauth_redirect_uri() -> str:
    explicit = str(os.getenv("META_OAUTH_REDIRECT_URI") or "").strip()
    if explicit:
        return explicit
    public_base = str(os.getenv("META_OAUTH_PUBLIC_BASE_URL") or os.getenv("WEBHOOK_PROXY_URL") or "").strip().rstrip("/")
    return f"{public_base}/api/meta-oauth-callback" if public_base else ""


def _decode_meta_oauth_state(raw_state: str) -> dict[str, Any]:
    text = str(raw_state or "").strip()
    if not text:
        return {}
    padding = "=" * (-len(text) % 4)
    try:
        decoded = base64.urlsafe_b64decode(f"{text}{padding}".encode("ascii")).decode("utf-8")
        payload = json.loads(decoded)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _score_meta_page_match(client_id: str, page: dict[str, Any], profile: dict[str, Any]) -> int:
    business_name = str((profile or {}).get("business_name") or "").strip().lower()
    client_tokens = {token for token in re.split(r"[^a-z0-9]+", str(client_id or "").lower()) if token}
    business_tokens = {token for token in re.split(r"[^a-z0-9]+", business_name) if token}
    wanted = client_tokens | business_tokens
    page_name = str((page or {}).get("name") or "").strip().lower()
    page_tokens = {token for token in re.split(r"[^a-z0-9]+", page_name) if token}
    overlap = len(wanted & page_tokens)
    ig_block = page.get("instagram_business_account") or {}
    return overlap + (20 if ig_block.get("id") else 0)


def normalize_approval_routing_mode(value: str | None) -> str:
    mode = str(value or "").strip().lower()
    if mode not in APPROVAL_ROUTING_MODES:
        return "desktop_first"
    return mode


def get_approval_routing_mode() -> str:
    return normalize_approval_routing_mode(get_agency_config().get("approval_routing"))


def _probe_cache(cache_key: str, builder):
    now = time.time()
    cached = _runtime_probe_cache.get(cache_key)
    if cached and now - cached[0] <= RUNTIME_PROBE_TTL_SECONDS:
        return cached[1]
    value = builder()
    _runtime_probe_cache[cache_key] = (now, value)
    return value


def _is_process_running(patterns: list[str]) -> tuple[bool, str]:
    for pattern in patterns:
        try:
            proc = subprocess.run(
                ["pgrep", "-f", pattern],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return True, pattern
        except Exception:
            continue
    return False, ""


def _meta_graph_get(path: str, token: str, params: dict | None = None) -> tuple[bool, dict]:
    query = {"access_token": token}
    if params:
        query.update(params)
    try:
        response = requests.get(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/{path}",
            params=query,
            timeout=6,
        )
        payload = response.json()
    except Exception as exc:
        return False, {"error": {"message": f"Meta probe failed: {exc}"}}

    if response.status_code >= 400 or "error" in payload:
        return False, payload
    return True, payload


def _validate_demo_meta_client(client_id: str, profile: dict) -> dict:
    token = str(profile.get("meta_access_token") or "").strip()
    page_id = str(profile.get("facebook_page_id") or "").strip()
    ig_id = str(profile.get("instagram_account_id") or "").strip()
    if not token or not page_id or not ig_id:
        return {"ok": False, "detail": "Missing Meta token, Facebook Page ID, or Instagram Account ID."}

    cache_key = f"meta:{client_id}:{hash((token, page_id, ig_id))}"

    def builder():
        page_ok, page_payload = _meta_graph_get(page_id, token, {"fields": "id,name,instagram_business_account{id,username}"})
        if not page_ok:
            message = page_payload.get("error", {}).get("message", "Facebook Page validation failed.")
            return {"ok": False, "detail": message}

        linked_ig = (page_payload.get("instagram_business_account") or {})
        linked_ig_id = str(linked_ig.get("id") or "").strip()
        linked_ig_username = str(linked_ig.get("username") or "").strip()
        if not linked_ig_id:
            return {"ok": False, "detail": f"Facebook Page {page_payload.get('name', page_id)} is not linked to an Instagram professional account."}
        if linked_ig_id != ig_id:
            return {
                "ok": False,
                "detail": (
                    f"Stored Instagram Account ID does not match the page-linked account. "
                    f"Page is linked to {linked_ig_username or linked_ig_id}, but Jarvis has {ig_id}."
                ),
            }

        ig_ok, ig_payload = _meta_graph_get(ig_id, token, {"fields": "id,username"})
        if not ig_ok:
            message = ig_payload.get("error", {}).get("message", "Instagram Account validation failed.")
            return {"ok": False, "detail": message}

        return {
            "ok": True,
            "detail": (
                f"Facebook Page {page_payload.get('name', page_id)} and Instagram account "
                f"{ig_payload.get('username', ig_id)} are linked and publish-ready."
            ),
        }

    return _probe_cache(cache_key, builder)


def _validate_demo_whatsapp_runtime() -> dict:
    token, phone_id = get_whatsapp_runtime_config()
    if not token or not phone_id:
        return {"ok": False, "configured": False, "detail": "Agency WhatsApp token or phone number ID is missing."}

    cache_key = f"wa:{hash((token, phone_id))}"

    def builder():
        ok, payload = _meta_graph_get(phone_id, token, {"fields": "id,display_phone_number"})
        if not ok:
            message = payload.get("error", {}).get("message", "WhatsApp runtime validation failed.")
            return {"ok": False, "configured": True, "detail": message}
        return {
            "ok": True,
            "configured": True,
            "detail": f"WhatsApp runtime is live on {payload.get('display_phone_number', phone_id)}.",
        }

    return _probe_cache(cache_key, builder)


def format_client_label(client_name: str) -> str:
    label = str(client_name or "").replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in label.split()) or "Client"


def build_caption_preview_line(job: dict, max_chars: int = 110) -> str:
    preview_text = str(job.get("caption_text") or "").strip()
    if not preview_text:
        return ""
    clipped = preview_text[:max_chars].strip()
    if len(preview_text) > max_chars:
        clipped += "..."
    return f"Caption Preview: {clipped}\n"


def build_approval_preview(job: dict) -> str:
    scheduling_label = format_schedule_label(job.get("days", []), job.get("time", ""), scheduled_date=job.get("scheduled_date"))
    focus = str(job.get("topic") or job.get("draft_name") or "Creative draft").strip()
    return (
        f"{format_client_label(job.get('client', ''))}\n"
        f"Your next creative is staged and ready for final approval.\n\n"
        f"Go-live: {scheduling_label}\n"
        f"Assets: {describe_job_assets(job)}\n"
        f"Focus: {focus}\n"
        f"{build_caption_preview_line(job)}"
        f"Select the release path below."
    )


def mark_approval_whatsapp_sent(job: dict, success: bool) -> dict:
    updated = dict(job)
    updated["whatsapp_sent"] = bool(success)
    updated["whatsapp_last_sent_at"] = datetime.now().isoformat(timespec="seconds") if success else updated.get("whatsapp_last_sent_at", "")
    return updated


def send_pending_approval_to_whatsapp(approval_id: str, phone: str | None = None) -> dict:
    job = get_pending_approval(approval_id)
    if not job:
        return {"success": False, "error": f"Approval ID {approval_id} not found."}

    target_phone = _normalize_whatsapp_phone(phone or get_agency_config().get("owner_phone", ""))
    if not target_phone:
        return {"success": False, "error": "OWNER_PHONE is missing from Agency Settings."}

    result = send_interactive_whatsapp_approval(target_phone, approval_id, build_approval_preview(job))
    if not result.get("success"):
        window_open, window_reason = whatsapp_reply_window_open(target_phone)
        error_text = str(result.get("error") or "").strip()
        if (not window_open) and (
            "131047" in error_text
            or "Re-engagement message" in error_text
            or "24 hour" in error_text
            or "24-hour" in error_text
        ):
            result["error"] = window_reason
    updated = mark_approval_whatsapp_sent(job, result.get("success"))
    update_pending_approval(approval_id, updated)
    return result


def build_scheduled_job_from_approval(job: dict) -> dict:
    new_job = {
        "job_id": job.get("job_id"),
        "client": job["client"],
        "topic": job["topic"],
        "days": job["days"],
        "scheduled_date": job.get("scheduled_date", ""),
        "time": job["time"],
        "status": "approved",
    }
    if "images" in job:
        new_job["images"] = job["images"]
    if "videos" in job:
        new_job["videos"] = job["videos"]
    if "media_kind" in job:
        new_job["media_kind"] = job["media_kind"]
    if "draft_name" in job:
        new_job["draft_name"] = job["draft_name"]
    if "approval_id" in job:
        new_job["approval_id"] = job["approval_id"]
    if "draft_id" in job:
        new_job["draft_id"] = job["draft_id"]
    if "caption_text" in job:
        new_job["caption_text"] = job["caption_text"]
        new_job["hashtags"] = job.get("hashtags", [])
        new_job["seo_keyword_used"] = job.get("seo_keyword_used", "")
        new_job["caption_mode"] = job.get("caption_mode", "ai")
        new_job["caption_status"] = job.get("caption_status", "ready")
    return new_job


def approve_pending_approval(approval_id: str, notify_phone: str | None = None) -> dict:
    job = get_pending_approval(approval_id)
    if not job:
        return {"status": "error", "reason": f"Approval ID {approval_id} not found or already processed."}

    client_id = str(job.get("client") or "").strip()
    profile = get_client_store().get_client(client_id) or {}
    meta_probe = _validate_demo_meta_client(client_id, profile)
    if not meta_probe.get("ok"):
        reason = meta_probe.get("detail", "Meta credentials are not ready for this client.")
        if notify_phone:
            send_whatsapp_message(
                notify_phone,
                (
                    f"JARVIS | Approval Blocked\n\n"
                    f"{format_client_label(client_id)} could not be scheduled because Meta credentials failed preflight.\n\n"
                    f"Reason: {reason}"
                ),
            )
        return {
            "status": "error",
            "reason": reason,
            "job": job,
            "code": "meta_credentials_invalid",
        }

    repair_result = publish_agent.prepare_managed_media(
        list(job.get("images") or []),
        list(job.get("videos") or []),
        instagram_enabled=bool(str(profile.get("instagram_account_id") or "").strip()),
    )
    repair_reason = str(repair_result.get("reason") or "").strip()
    if repair_reason:
        if notify_phone:
            send_whatsapp_message(
                notify_phone,
                (
                    f"JARVIS | Approval Blocked\n\n"
                    f"{format_client_label(client_id)} could not be scheduled because Jarvis could not repair the media for Instagram.\n\n"
                    f"Reason: {repair_reason}"
                ),
            )
        return {
            "status": "error",
            "reason": repair_reason,
            "job": job,
            "code": "media_repair_failed",
        }

    media_preflight = publish_agent.preflight_media(
        list(job.get("images") or []),
        list(job.get("videos") or []),
        instagram_enabled=bool(str(profile.get("instagram_account_id") or "").strip()),
    )
    media_reason = str(
        media_preflight.get("transport_error")
        or media_preflight.get("instagram_error")
        or ""
    ).strip()
    if media_reason:
        if notify_phone:
            send_whatsapp_message(
                notify_phone,
                (
                    f"JARVIS | Approval Blocked\n\n"
                    f"{format_client_label(client_id)} could not be scheduled because the media failed preflight.\n\n"
                    f"Reason: {media_reason}"
                ),
            )
        return {
            "status": "error",
            "reason": media_reason,
            "job": job,
            "code": "media_preflight_failed",
        }

    if schedule_request_is_in_past(
        str(job.get("time") or "").strip(),
        scheduled_date=str(job.get("scheduled_date") or "").strip() or None,
        raw_days=job.get("days", []),
    ):
        return {
            "status": "error",
            "reason": past_time_error_message(
                str(job.get("time") or "").strip(),
                scheduled_date=str(job.get("scheduled_date") or "").strip() or None,
                days=job.get("days", []),
            ),
            "job": job,
        }

    added, duplicate, saved_job = add_scheduled_job(build_scheduled_job_from_approval(job))
    delete_pending_approval(approval_id)

    if notify_phone:
        if added:
            send_whatsapp_message(
                notify_phone,
                (
                    f"JARVIS | Confirmed 🟢\n\n"
                    f"{format_client_label(job['client'])} is locked for "
                    f"{format_schedule_label(job.get('days', []), job['time'], scheduled_date=job.get('scheduled_date'))}.\n"
                    f"Status: Approved and added to the live schedule."
                ),
            )
        else:
            existing_job_id = duplicate.get("job_id", "unknown") if duplicate else "unknown"
            send_whatsapp_message(
                notify_phone,
                f"Duplicate prevented. A matching active job already exists for {job['client']} at {job['time']}. Existing Job ID: {existing_job_id}.",
            )

    if added:
        return {"status": "success", "saved_job": saved_job, "job": job}
    return {"status": "duplicate", "existing_job": duplicate, "job": job}


def reject_pending_approval(approval_id: str, notify_phone: str | None = None) -> dict:
    job = get_pending_approval(approval_id)
    if not job:
        return {"status": "error", "reason": f"Approval ID {approval_id} not found or already processed."}

    delete_pending_approval(approval_id)
    if notify_phone:
        send_whatsapp_message(
            notify_phone,
            (
                f"JARVIS | Refine Requested 🔴\n\n"
                f"{format_client_label(job['client'])}\n"
                f"This draft has been removed from the live approval queue and will not publish.\n\n"
                f"Status: Waiting for a cleaner rewrite.\n"
                f"Agency OS · Ref {approval_id}"
            ),
        )
    return {"status": "success", "job": job}


def discard_all_pending_approvals() -> dict:
    removed = delete_all_pending_approvals()
    return {"status": "success", "removed": removed}


def move_pending_approval(approval_id: str, release_window_text: str, reopen_whatsapp: bool = False, notify_phone: str | None = None) -> dict:
    job = get_pending_approval(approval_id)
    if not job:
        return {"status": "error", "reason": f"Approval ID {approval_id} not found or already processed."}

    _, new_time, new_days, new_scheduled_date = parse_owner_reschedule_command(release_window_text)
    if not new_time:
        return {
            "status": "error",
            "reason": "Jarvis could not understand that release window. Try something like `Tomorrow 6:30 PM` or `Friday April 3 11:10 PM`.",
        }

    job["time"] = new_time
    if new_days:
        job["days"] = new_days
    if new_scheduled_date is not None:
        job["scheduled_date"] = new_scheduled_date
    job["status"] = "pending_approval"
    updated = update_pending_approval(approval_id, job) or job

    if reopen_whatsapp:
        result = send_pending_approval_to_whatsapp(approval_id, phone=notify_phone)
        if not result.get("success"):
            return {"status": "error", "reason": result.get("error", "Failed to send WhatsApp approval card."), "job": updated}

    return {"status": "success", "job": updated}


def format_schedule_label(days: list, time_str: str, scheduled_date: str | None = None) -> str:
    parsed_date = parse_iso_date(scheduled_date)
    if parsed_date:
        return f"{format_display_date(parsed_date)} at {time_str}"
    if not days:
        return time_str
    return f"{', '.join(str(day).title() for day in days)} at {time_str}"


def load_reschedule_sessions() -> dict:
    return load_reschedule_session_map()


def save_reschedule_sessions(data: dict) -> None:
    save_reschedule_session_map(data)


def _normalize_whatsapp_phone(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits or raw.lstrip("+")


def load_whatsapp_contact_windows() -> dict:
    if os.path.exists("whatsapp_contact_windows.json"):
        try:
            with open("whatsapp_contact_windows.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_whatsapp_contact_windows(data: dict) -> None:
    with open("whatsapp_contact_windows.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def record_whatsapp_inbound(phone: str, timestamp_value: str | int | None = None) -> None:
    target_phone = _normalize_whatsapp_phone(phone)
    if not target_phone:
        return
    recorded_at = datetime.now(timezone.utc)
    raw = str(timestamp_value or "").strip()
    if raw:
        try:
            if raw.isdigit():
                recorded_at = datetime.utcfromtimestamp(int(raw))
            else:
                recorded_at = datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            recorded_at = datetime.now(timezone.utc)
    windows = load_whatsapp_contact_windows()
    windows[target_phone] = {"last_inbound_at": recorded_at.isoformat(timespec="seconds")}
    save_whatsapp_contact_windows(windows)


def get_last_whatsapp_inbound_at(phone: str) -> datetime | None:
    target_phone = _normalize_whatsapp_phone(phone)
    if not target_phone:
        return None
    windows = load_whatsapp_contact_windows()
    entry = windows.get(target_phone) or {}
    value = str(entry.get("last_inbound_at") or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def whatsapp_reply_window_open(phone: str) -> tuple[bool, str]:
    last_inbound_at = get_last_whatsapp_inbound_at(phone)
    if not last_inbound_at:
        return (
            False,
            "Jarvis has no recorded inbound WhatsApp reply from this number in the last 24 hours. Ask the owner to send any WhatsApp message first, then try again.",
        )
    if datetime.now(timezone.utc) - last_inbound_at > timedelta(hours=24):
        return (
            False,
            "The WhatsApp 24-hour reply window is closed for this number. Ask the owner to send any WhatsApp message first, then try again.",
        )
    return True, ""


def parse_owner_reschedule_command(msg_body: str) -> tuple[Optional[str], Optional[str], Optional[list[str]], Optional[str]]:
    text = msg_body.strip()
    def _clean_date_phrase(value: str) -> str:
        return re.sub(r"\bat\s*$", "", str(value or "").strip(), flags=re.IGNORECASE).strip()

    explicit = re.match(
        r"^\s*TIME[\s_-]+([A-Z0-9]+)\s+(.+?)\s+(\d{1,2}:\d{2}\s*[AP]M)\s*$",
        text,
        re.IGNORECASE,
    )
    if explicit:
        date_phrase = _clean_date_phrase(explicit.group(2))
        resolved_date = resolve_date_phrase(date_phrase)
        parsed_days = [resolved_date.strftime("%A")] if resolved_date else None
        return explicit.group(1).upper(), explicit.group(3).strip().upper(), parsed_days, (resolved_date.isoformat() if resolved_date else None)

    date_and_time = re.match(
        r"^\s*(.+?)(?:\s+at)?\s+(\d{1,2}:\d{2}\s*[AP]M)\s*$",
        text,
        re.IGNORECASE,
    )
    if date_and_time:
        date_phrase = _clean_date_phrase(date_and_time.group(1))
        resolved_date = resolve_date_phrase(date_phrase)
        if resolved_date:
            return None, date_and_time.group(2).strip().upper(), [resolved_date.strftime("%A")], resolved_date.isoformat()

    simple = re.match(r"^\s*(\d{1,2}:\d{2}\s*[AP]M)\s*$", text, re.IGNORECASE)
    if simple:
        return None, simple.group(1).strip().upper(), None, None

    return None, None, None, None

# --- AUDIT LOGGING ---
logger = logging.getLogger("WhatsAppAudit")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("whatsapp_audit.log", encoding="utf-8")
formatter = logging.Formatter("%(asctime)s | %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(logging.StreamHandler(sys.stdout))

def load_phone_map() -> dict:
    if os.path.exists("phone_map.json"):
        with open("phone_map.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


class JarvisLoginRequest(BaseModel):
    password: str


@app.get("/api/auth/status")
async def api_auth_status(request: Request):
    if not JARVIS_AUTH_ENABLED:
        return {
            "status": "success",
            "auth_enabled": False,
            "authenticated": True,
            "expires_in_seconds": None,
        }

    token = _extract_session_token(request)
    authenticated = _is_valid_session(token)
    session = get_auth_session(token) if authenticated else None
    expires_at = _parse_iso_datetime((session or {}).get("expires_at"))
    expires_in_seconds = max(0, int((expires_at - _utc_now()).total_seconds())) if expires_at else None
    return {
        "status": "success",
        "auth_enabled": True,
        "authenticated": authenticated,
        "expires_in_seconds": expires_in_seconds,
    }


@app.post("/api/auth/login")
async def api_auth_login(req: JarvisLoginRequest, request: Request):
    if not JARVIS_AUTH_ENABLED:
        return {
            "status": "success",
            "auth_enabled": False,
            "authenticated": True,
            "token": None,
            "expires_at": None,
        }

    submitted = str(req.password or "")
    if not secrets.compare_digest(submitted, JARVIS_ADMIN_PASSWORD):
        _audit_event(
            "auth.login_failed",
            {"path": request.url.path, "method": request.method},
            request=request,
            actor=_get_rate_limit_identity(request),
        )
        return JSONResponse(
            status_code=401,
            content={
                "status": "error",
                "reason": "Invalid Jarvis admin password.",
                "request_id": _get_request_id(request),
            },
        )

    token, expires_at = _issue_session_token(
        {
            "issued_from": _get_rate_limit_identity(request),
            "user_agent": str(request.headers.get("user-agent") or "").strip(),
        }
    )
    _audit_event(
        "auth.login_succeeded",
        {"expires_at": expires_at},
        request=request,
        actor=_get_rate_limit_identity(request),
    )
    return {
        "status": "success",
        "auth_enabled": True,
        "authenticated": True,
        "token": token,
        "expires_at": expires_at,
    }


@app.post("/api/auth/logout")
async def api_auth_logout(request: Request):
    token = _extract_session_token(request)
    if token:
        _auth_sessions.pop(token, None)
        delete_auth_session(token)
    _audit_event("auth.logout", {"token_present": bool(token)}, request=request, actor=_get_rate_limit_identity(request))
    return {"status": "success"}

def send_whatsapp_message(to_phone: str, text: str):
    """
    Uses the Meta API to send an outbound WhatsApp reply directly to a phone number.
    """
    return transport_send_text_message(to_phone, text)


def send_interactive_whatsapp_approval(to_phone: str, approval_id: str, preview_text: str):
    safe_text = preview_text[:700] + "..." if len(preview_text) > 700 else preview_text
    accent = HEADER_ACCENTS[sum(ord(ch) for ch in approval_id) % len(HEADER_ACCENTS)]
    result = transport_send_button_message(
        to_phone,
        header_text=f"JARVIS | Campaign Ready {accent}",
        body_text=safe_text,
        footer_text=f"Agency OS • Ref {approval_id}",
        buttons=[
            {"id": f"APPROVE_{approval_id}", "title": "Approve"},
            {"id": f"REJECT_{approval_id}", "title": "Refine"},
            {"id": f"MOVE_{approval_id}", "title": "Move Time"},
        ],
    )
    if result.get("success"):
        logger.info(
            "SYSTEM | INTERACTIVE APPROVAL SENT TO %s FOR ID %s | RESPONSE %s",
            to_phone,
            approval_id,
            json.dumps(result.get("response") or {}, ensure_ascii=False),
        )
        result.setdefault("fallback_text_sent", False)
        result.setdefault("fallback_error", None)
    return result

# =========================================================
# WEBHOOK ENDPOINTS
# =========================================================
# =========================================================
# WEBHOOK ENDPOINTS
# =========================================================
# =========================================================
# WEBHOOK ENDPOINTS
# =========================================================

@app.get("/webhook")
async def verify_webhook(request: Request):
    """
    Meta Developer Portal calls this GET route once to verify you own the server.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("SYSTEM | Validated Meta Webhook handshake successfully.")
        return PlainTextResponse(content=challenge)
        
    raise HTTPException(status_code=403, detail="Forbidden: Invalid token.")


@app.get("/api/meta-oauth/start")
async def api_meta_oauth_start(client_id: str, phone: str = "", state: str = ""):
    app_id = str(os.getenv("META_APP_ID") or "").strip()
    redirect_uri = _meta_oauth_redirect_uri()
    if not app_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="META_APP_ID or META_OAUTH_REDIRECT_URI is not configured.")
    safe_client_id = resolve_client_id(client_id)
    safe_phone = _normalize_whatsapp_phone(phone)
    oauth_state = str(state or "").strip()
    if not oauth_state:
        generated_link = build_meta_connect_link(safe_client_id, safe_phone)
        if "state=" in generated_link:
            oauth_state = generated_link.split("state=", 1)[-1].split("&", 1)[0]
    if not oauth_state:
        raise HTTPException(status_code=500, detail="Jarvis could not generate a Meta OAuth state token.")
    if safe_phone:
        save_operator_session_state(
            safe_phone,
            {
                "mode": "connect_wait",
                "pending_connect_client_id": safe_client_id,
                "pending_connect_state": oauth_state,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    auth_url = (
        f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth"
        f"?client_id={quote(app_id)}"
        f"&redirect_uri={quote(redirect_uri, safe='')}"
        f"&state={quote(oauth_state, safe='')}"
        f"&scope={quote(str(os.getenv('META_OAUTH_SCOPES') or 'pages_show_list,pages_read_engagement,pages_manage_posts,instagram_basic,instagram_content_publish,business_management'), safe=',')}"
    )
    return RedirectResponse(auth_url)


@app.get("/api/meta-oauth-callback")
async def api_meta_oauth_callback(code: str | None = None, state: str = "", error: str | None = None, error_description: str | None = None):
    decoded_state = _decode_meta_oauth_state(state)
    client_id = resolve_client_id(str(decoded_state.get("client_id") or "").strip())
    operator_phone = _normalize_whatsapp_phone(decoded_state.get("operator_phone"))
    if error:
        if operator_phone:
            send_whatsapp_message(operator_phone, f"Meta connect failed for {client_id or 'that client'}: {error_description or error}")
        return PlainTextResponse("Meta connection failed. You can return to WhatsApp.")
    if not code or not client_id:
        raise HTTPException(status_code=400, detail="Missing OAuth code or client context.")

    app_id = str(os.getenv("META_APP_ID") or "").strip()
    app_secret = str(os.getenv("META_APP_SECRET") or "").strip()
    redirect_uri = _meta_oauth_redirect_uri()
    if not app_id or not app_secret or not redirect_uri:
        raise HTTPException(status_code=500, detail="Meta OAuth environment is incomplete.")

    token_response = requests.get(
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token",
        params={
            "client_id": app_id,
            "client_secret": app_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=20,
    )
    token_response.raise_for_status()
    access_payload = token_response.json() if token_response.content else {}
    user_token = str(access_payload.get("access_token") or "").strip()
    if not user_token:
        raise HTTPException(status_code=400, detail="Meta OAuth did not return an access token.")

    pages_response = requests.get(
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/accounts",
        params={
            "access_token": user_token,
            "fields": "id,name,access_token,instagram_business_account{id,username}",
        },
        timeout=20,
    )
    pages_response.raise_for_status()
    pages = list((pages_response.json() or {}).get("data") or [])
    client_payload = get_client_store().get_client(client_id) or {}
    profile = dict(client_payload.get("profile_json") or {})
    if not pages:
        if operator_phone:
            send_whatsapp_message(operator_phone, f"Meta connect failed for {client_id}: no manageable Facebook Pages were found on that login.")
        return PlainTextResponse("No manageable Meta Pages were found. You can return to WhatsApp.")

    best_page = max(pages, key=lambda item: _score_meta_page_match(client_id, item, profile))
    ig_block = best_page.get("instagram_business_account") or {}
    if not ig_block.get("id"):
        if operator_phone:
            send_whatsapp_message(operator_phone, f"Meta connect failed for {client_id}: the selected Facebook Page has no linked Instagram professional account.")
        return PlainTextResponse("Selected Meta Page has no linked Instagram professional account.")

    updated_client = dict(client_payload)
    updated_client["client_id"] = client_id
    updated_client["meta_access_token"] = str(best_page.get("access_token") or user_token).strip()
    updated_client["facebook_page_id"] = str(best_page.get("id") or "").strip()
    updated_client["instagram_account_id"] = str(ig_block.get("id") or "").strip()
    profile["instagram_connected"] = True
    profile["connected_facebook_page_name"] = str(best_page.get("name") or "").strip()
    profile["connected_instagram_username"] = str(ig_block.get("username") or "").strip()
    updated_client["profile_json"] = profile
    get_client_store().save_client(client_id, updated_client)
    if operator_phone:
        delete_operator_session_state(operator_phone)
        send_whatsapp_message(
            operator_phone,
            (
                f"{format_client_label(client_id)} is now connected.\n"
                f"Facebook Page: {best_page.get('name')}\n"
                f"Instagram: {ig_block.get('username') or ig_block.get('id')}\n"
                "You can go back to WhatsApp and continue posting."
            ),
        )
    return PlainTextResponse("Meta account connected. You can return to WhatsApp.")

@app.post("/webhook")
async def receive_message(request: Request):
    """
    Meta Cloud API continuously posts incoming messages wrapped in deep JSON arrays here.
    """
    body = await request.json()
    
    # Strictly isolate WhatsApp Business API events
    if body.get("object") == "whatsapp_business_account":
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                if "statuses" in value:
                    for status in value["statuses"]:
                        status_name = status.get("status", "unknown")
                        recipient_id = status.get("recipient_id", "unknown")
                        message_id = status.get("id", "unknown")
                        errors = status.get("errors") or []
                        if errors:
                            logger.error(
                                f"SYSTEM | STATUS | {status_name.upper()} | TO {recipient_id} | MSG {message_id} | ERRORS {json.dumps(errors, ensure_ascii=False)}"
                            )
                        else:
                            logger.info(
                                f"SYSTEM | STATUS | {status_name.upper()} | TO {recipient_id} | MSG {message_id}"
                            )
                 
                if "messages" in value:
                    for message in value["messages"]:
                        normalized_message = normalize_inbound_message(message)
                        sender_phone = normalized_message.get("from")
                        record_whatsapp_inbound(sender_phone, normalized_message.get("timestamp"))
                        msg_type = normalized_message.get("type")

                        if is_operator_phone(sender_phone):
                            if msg_type == "interactive":
                                reply_id = str(normalized_message.get("interactive_reply_id") or "").strip()
                                if reply_id.startswith(("APPROVE_", "REJECT_", "MOVE_")):
                                    await handle_interactive_reply(sender_phone, reply_id)
                                elif reply_id:
                                    await handle_operator_message(normalized_message)
                                continue
                            if msg_type == "text":
                                raw_text = str(normalized_message.get("text") or "").strip()
                                command_match = re.match(r"^\s*(APPROVE|REJECT)[\s_-]+([A-Z0-9]+)\s*$", raw_text, re.IGNORECASE)
                                reschedule_session = load_reschedule_sessions().get(sender_phone) or {}
                                _, new_time, _new_days, _new_scheduled_date = parse_owner_reschedule_command(raw_text)
                                if command_match or new_time or reschedule_session:
                                    await handle_inbound_text(sender_phone, raw_text)
                                else:
                                    await handle_operator_message(normalized_message)
                                continue
                            if msg_type in {"document", "image", "video"}:
                                await handle_operator_message(normalized_message)
                                continue

                        if msg_type == "text":
                            await handle_inbound_text(sender_phone, str(normalized_message.get("text") or ""))
                        elif msg_type == "interactive":
                            reply_id = str(normalized_message.get("interactive_reply_id") or "").strip()
                            if reply_id:
                                await handle_interactive_reply(sender_phone, reply_id)
                            
    return {"status": "ok"}

async def handle_interactive_reply(phone: str, reply_id: str):
    """
    Handles approval actions from WhatsApp.
    Format: APPROVE_ABCD, REJECT_ABCD, MOVE_ABCD
    """
    logger.info(f"{phone} | SYSTEM | INTERACTIVE | {reply_id}")

    if "_" not in reply_id:
        return

    action, approval_id = reply_id.split("_", 1)

    if action not in ["APPROVE", "REJECT", "MOVE"]:
        return

    pending = list_live_pending_approvals()
    job = next((j for j in pending if str(j.get("approval_id") or "").strip().upper() == approval_id.strip().upper()), None)
    if not job:
        send_whatsapp_message(phone, f"?? Error: Approval ID {approval_id} not found or already processed.")
        return

    if action == "MOVE":
        job["status"] = "pending_reschedule"
        update_pending_approval(approval_id, job)
        sessions = load_reschedule_sessions()
        sessions[phone] = {
            "approval_id": approval_id,
            "client": job["client"],
            "requested_at": datetime.now().isoformat(timespec="seconds"),
        }
        save_reschedule_sessions(sessions)
        send_whatsapp_message(
            phone,
            (
                f"JARVIS | Reschedule Requested\n\n"
                f"{format_client_label(job['client'])} is currently lined up for {format_schedule_label(job.get('days', []), job['time'], scheduled_date=job.get('scheduled_date'))}.\n\n"
                f"Reply with a new release window such as:\n"
                f"`Friday April 3 11:10 PM`\n"
                f"or\n"
                f"`TIME {approval_id} Tomorrow 11:10 PM`\n\n"
                f"The next day/time reply you send will update this draft automatically."
            ),
        )
        logger.info(f"SYSTEM | RESCHEDULE_REQUESTED | {approval_id}")
        return

    if action == "APPROVE":
        result = approve_pending_approval(approval_id, notify_phone=phone)
        if result.get("status") == "success":
            saved_job = result.get("saved_job") or {}
            logger.info(f"SYSTEM | APPROVED | {approval_id} migrated to schedule as {saved_job.get('job_id', 'unknown')}")
        elif result.get("status") == "duplicate":
            existing_job = result.get("existing_job") or {}
            logger.warning(f"SYSTEM | DUPLICATE_APPROVAL | {approval_id} matched existing job {existing_job.get('job_id', 'unknown')}")
        sessions = load_reschedule_sessions()
        if phone in sessions and str(sessions[phone].get("approval_id", "")).upper() == approval_id:
            del sessions[phone]
            save_reschedule_sessions(sessions)
        return

    if action == "REJECT":
        reject_pending_approval(approval_id, notify_phone=phone)
        logger.info(f"SYSTEM | REJECTED | {approval_id} discarded.")
        sessions = load_reschedule_sessions()
        if phone in sessions and str(sessions[phone].get("approval_id", "")).upper() == approval_id:
            del sessions[phone]
            save_reschedule_sessions(sessions)
        return

    if action == "APPROVE":
        new_job = {
            "job_id": job.get("job_id"),
            "client": job["client"],
            "topic": job["topic"],
            "days": job["days"],
            "scheduled_date": job.get("scheduled_date", ""),
            "time": job["time"],
            "status": "approved",
        }
        if "images" in job:
            new_job["images"] = job["images"]
        if "videos" in job:
            new_job["videos"] = job["videos"]
        if "media_kind" in job:
            new_job["media_kind"] = job["media_kind"]
        if "draft_name" in job:
            new_job["draft_name"] = job["draft_name"]
        if "caption_text" in job:
            new_job["caption_text"] = job["caption_text"]
            new_job["hashtags"] = job.get("hashtags", [])
            new_job["seo_keyword_used"] = job.get("seo_keyword_used", "")
            new_job["caption_mode"] = job.get("caption_mode", "ai")
            new_job["caption_status"] = job.get("caption_status", "ready")

        added, duplicate, saved_job = add_scheduled_job(new_job)
        if added:
            send_whatsapp_message(
                phone,
                (
                    f"JARVIS | Confirmed 🟢\n\n"
                    f"{format_client_label(job['client'])} is locked for "
                    f"{format_schedule_label(job.get('days', []), job['time'], scheduled_date=job.get('scheduled_date'))}.\n"
                    f"Status: Approved and added to the live schedule."
                ),
            )
            logger.info(f"SYSTEM | APPROVED | {approval_id} migrated to schedule.json as {saved_job['job_id']}")
        else:
            existing_job_id = duplicate.get("job_id", "unknown") if duplicate else "unknown"
            send_whatsapp_message(
                phone,
                f"?? Duplicate prevented. A matching active job already exists for {job['client']} at {job['time']}. Existing Job ID: {existing_job_id}.",
            )
            logger.warning(f"SYSTEM | DUPLICATE_APPROVAL | {approval_id} matched existing job {existing_job_id}")
    else:
        send_whatsapp_message(
            phone,
            (
                f"JARVIS | Refine Requested 🔴\n\n"
                f"{format_client_label(job['client'])}\n"
                f"This draft has been removed from the live approval queue and will not publish.\n\n"
                f"Status: Waiting for a cleaner rewrite.\n"
                f"Agency OS · Ref {approval_id}"
            ),
        )
        logger.info(f"SYSTEM | REJECTED | {approval_id} discarded.")

    delete_pending_approval(approval_id)
    sessions = load_reschedule_sessions()
    if phone in sessions and str(sessions[phone].get("approval_id", "")).upper() == approval_id:
        del sessions[phone]
        save_reschedule_sessions(sessions)

async def handle_inbound_text(phone: str, msg_body: str):
    """
    Applies the logical architecture mapping to inbound text streams.
    """
    normalized_phone = _normalize_whatsapp_phone(phone)
    agency_phone = _normalize_whatsapp_phone(get_agency_config().get("owner_phone", ""))
    command_match = re.match(r"^\s*(APPROVE|REJECT)[\s_-]+([A-Z0-9]+)\s*$", msg_body.strip(), re.IGNORECASE)
    if agency_phone and normalized_phone == agency_phone and command_match:
        action = command_match.group(1).upper()
        approval_id = command_match.group(2).upper()
        logger.info(f"{phone} | SYSTEM | TEXT_APPROVAL | {action}_{approval_id}")
        await handle_interactive_reply(phone, f"{action}_{approval_id}")
        return

    if agency_phone and normalized_phone == agency_phone:
        approval_id, new_time, new_days, new_scheduled_date = parse_owner_reschedule_command(msg_body)
        if new_time:
            pending = list_pending_approvals()
            sessions = load_reschedule_sessions()
            session = sessions.get(phone, {})
            session_approval_id = str(session.get("approval_id", "")).upper().strip()
            candidates = [job for job in pending if job.get("status") == "pending_reschedule"]
            target_job = None
            if session_approval_id:
                target_job = next((job for job in candidates if job.get("approval_id") == session_approval_id), None)
            if target_job is None and approval_id:
                target_job = next((job for job in candidates if job.get("approval_id") == approval_id), None)
            elif target_job is None and len(candidates) == 1:
                target_job = candidates[0]

            if target_job:
                target_job["time"] = new_time
                if new_days:
                    target_job["days"] = new_days
                if new_scheduled_date is not None:
                    target_job["scheduled_date"] = new_scheduled_date
                target_job["status"] = "pending_approval"
                update_pending_approval(target_job["approval_id"], target_job)
                if phone in sessions:
                    del sessions[phone]
                    save_reschedule_sessions(sessions)

                if get_approval_routing_mode() in {"desktop_and_whatsapp", "whatsapp_only"}:
                    send_pending_approval_to_whatsapp(target_job["approval_id"], phone=phone)
                logger.info(
                    f"SYSTEM | RESCHEDULE_UPDATED | {target_job['approval_id']} -> {format_schedule_label(target_job.get('days', []), new_time, scheduled_date=target_job.get('scheduled_date'))}"
                )
                return

            if candidates:
                send_whatsapp_message(
                    phone,
                    "Multiple drafts are waiting for new times. Tap `Move Time` on the exact draft you want to adjust, then send the new release window. If needed, you can still use `TIME <approval_id> Friday April 3 11:10 PM` as a fallback.",
                )
                return

    phone_map = load_phone_map()
    client_name = phone_map.get(phone, "UNKNOWN")
    
    # 1. Audit Requirement 4
    logger.info(f"{phone} | {client_name} | IN  | {msg_body}")
    
    if client_name == "UNKNOWN":
        logger.warning(f"SYSTEM | WARNING | Message from unregistered number ({phone}) discarded.")
        return

    # 2. Agentic Safety Triage
    logger.info(f"SYSTEM | INFO | Scanning '{client_name}' message via Triage Agent...")
    triage_decision = await asyncio.to_thread(run_triage_agent, msg_body)
    
    if "ESCALATE" in triage_decision:
        logger.warning(f"{phone} | {client_name} | SYSTEM | [ESCALATED] Triage Agent flagged issue. Halting auto-reply.")
        
        agency_phone = get_agency_config().get("owner_phone", "")
        if agency_phone:
            timestamp = datetime.now().strftime("%I:%M %p")
            alert_msg = (
                f"🚨 *ESCALATION ALERT* 🚨\n\n"
                f"🏢 *Client:* {client_name}\n"
                f"📱 *Phone:* {phone}\n"
                f"⏰ *Time:* {timestamp}\n\n"
                f"💬 *Message:*\n_{msg_body}_\n\n"
                f"🛑 *System:* AI Halted. Manual override required."
            )
            # Send the emergency ping instantly
            send_whatsapp_message(agency_phone, alert_msg)
            logger.info(f"SYSTEM | OWNER ESCALATION PING FIRED TO {agency_phone}")
            
        calming_message = "أبشر طال عمرك، تم تحويل موضوعك للإدارة فوراً. أحد الزملاء بيتواصل معاك في أقرب وقت لخدمتك بشكل كامل."
        send_whatsapp_message(phone, calming_message)
        logger.info(f"{phone} | {client_name} | OUT | [CALMING_MSG] {calming_message}")
        return

    logger.info(f"SYSTEM | INFO | Triage Agent cleared message as SAFE.")

    # 3. Agent Processing
    logger.info(f"SYSTEM | INFO | Handing '{client_name}' state over to Agent #3...")
    agent_response = await asyncio.to_thread(run_whatsapp_agent, client_name, msg_body)
    
    # 4. Outbound Auto-Reply Execution
    send_whatsapp_message(phone, agent_response)
    
    # 5. Audit Requirement 4
    logger.info(f"{phone} | {client_name} | OUT | {agent_response}")

# =========================================================
# AGENCY OS API (ZERO-CODE DASHBOARD)
# =========================================================

os.makedirs("clients", exist_ok=True)
os.makedirs("assets", exist_ok=True)

class QuickIntakeRequest(BaseModel):
    brand_name: Optional[str] = None
    business_type: Optional[str] = None
    what_they_sell: Optional[str] = None
    target_audience: Optional[str] = None
    main_language: Optional[str] = None
    brand_tone: Optional[str] = None
    products_examples: Optional[str] = None
    city_market: Optional[str] = None
    offer_focus: Optional[str] = None
    words_to_avoid: Optional[str] = None
    inspiration_links: Optional[str] = None


class SynthesizeRequest(BaseModel):
    client_name: str
    raw_context: str = ""
    quick_intake: Optional[QuickIntakeRequest] = None
    website_url: Optional[str] = None
    social_url: Optional[str] = None


def _as_clean_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _detect_brief_language(text: str) -> str:
    raw = str(text or "")
    arabic_chars = len(re.findall(r"[\u0600-\u06FF]", raw))
    latin_chars = len(re.findall(r"[A-Za-z]", raw))
    if arabic_chars and latin_chars:
        return "bilingual"
    if arabic_chars:
        return "arabic"
    return "english"


def _extract_first_json_object(raw: str) -> dict:
    text = str(raw or "").strip()
    if not text:
        raise ValueError("Empty synthesis response")
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in synthesis response")
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        ch = text[index]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:index + 1]
                return json.loads(candidate)
    if depth > 0 and not in_string:
        candidate = text[start:] + ("}" * depth)
        try:
            return json.loads(candidate)
        except Exception:
            pass
    raise ValueError("Unterminated JSON object in synthesis response")


def _prepare_brief_for_synthesis(raw: str) -> str:
    text = str(raw or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= 12000:
        return text

    # Most client briefs put the key brand facts up front. Keep the opening section and a small
    # tail for extra examples/constraints so free-model intake stays responsive.
    head = text[:9500].rstrip()
    tail = text[-1800:].lstrip()
    return f"{head}\n\n[... brief truncated for synthesis speed ...]\n\n{tail}"


def _normalize_public_source_url(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if not re.match(r"^https?://", raw, re.IGNORECASE):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return raw


def _html_to_readable_text(raw_html: str) -> str:
    text = str(raw_html or "")
    if not text:
        return ""
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", text)
    text = re.sub(r"(?is)<(br|/p|/div|/section|/article|/li|/h[1-6])[^>]*>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html_unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(\b\w+\b)( \1\b){3,}", r"\1", text, flags=re.IGNORECASE)
    return text.strip()


def _fetch_public_reference_text(url: str, label: str) -> tuple[str, str]:
    normalized = _normalize_public_source_url(url)
    if not normalized:
        return "", f"{label} URL is invalid."
    try:
        response = requests.get(
            normalized,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Jarvis/1.0; +https://localhost)",
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
            },
            timeout=(6, 12),
        )
    except Exception as exc:
        return "", f"{label} could not be reached automatically: {exc}"

    if response.status_code >= 400:
        return "", f"{label} returned HTTP {response.status_code}."

    content_type = str(response.headers.get("content-type") or "").lower()
    payload = response.text or ""
    if "text/html" in content_type or "<html" in payload.lower():
        extracted = _html_to_readable_text(payload)
    else:
        extracted = str(payload).strip()
    extracted = re.sub(r"\n{3,}", "\n\n", extracted).strip()
    if not extracted:
        return "", f"{label} was reachable but did not expose readable text."
    if len(extracted) > 5000:
        extracted = extracted[:5000].rstrip()
    return extracted, ""


def _prepare_quick_intake_section(quick_intake: QuickIntakeRequest | dict | None) -> str:
    if isinstance(quick_intake, BaseModel):
        data = quick_intake.model_dump(exclude_none=True)
    elif isinstance(quick_intake, dict):
        data = {str(key): value for key, value in quick_intake.items() if str(value or "").strip()}
    else:
        data = {}
    if not data:
        return ""

    label_map = {
        "brand_name": "Brand / product name",
        "business_type": "Business type",
        "what_they_sell": "What they sell / service",
        "target_audience": "Target audience",
        "main_language": "Main language",
        "brand_tone": "Brand tone",
        "products_examples": "Products / services / examples",
        "city_market": "City / market",
        "offer_focus": "Offer / promo focus",
        "words_to_avoid": "Words to avoid",
        "inspiration_links": "Competitor / inspiration links",
    }
    lines = []
    for key in (
        "brand_name",
        "business_type",
        "what_they_sell",
        "target_audience",
        "main_language",
        "brand_tone",
        "products_examples",
        "city_market",
        "offer_focus",
        "words_to_avoid",
        "inspiration_links",
    ):
        value = str(data.get(key) or "").strip()
        if value:
            lines.append(f"- {label_map[key]}: {value}")
    if not lines:
        return ""
    return "Operator Quick Setup (primary source of truth)\n" + "\n".join(lines)


def _prepare_synthesis_context(
    raw_context: str,
    quick_intake: QuickIntakeRequest | dict | None,
    website_url: str | None,
    social_url: str | None,
) -> tuple[str, list[str], dict[str, Any]]:
    sections: list[str] = []
    warnings: list[str] = []
    enrichments: dict[str, Any] = {}

    quick_section = _prepare_quick_intake_section(quick_intake)
    if quick_section:
        sections.append(quick_section)

    notes = str(raw_context or "").strip()
    if notes:
        sections.append(f"Additional operator notes / brief material\n{notes}")

    normalized_website = _normalize_public_source_url(website_url)
    if normalized_website:
        website_digest = extract_website_digest(normalized_website)
        if isinstance(website_digest, dict) and str(website_digest.get("status") or "").strip() == "success":
            enrichments["website_digest"] = website_digest
            enrichments["website_url"] = normalized_website
            sections.append(
                "Website digest (structured enrichment)\n"
                f"URL: {normalized_website}\n"
                f"{json.dumps(website_digest, ensure_ascii=False)}"
            )
        else:
            website_reason = str((website_digest or {}).get("reason") or "Website digest extraction failed.").strip()
            if website_reason:
                warnings.append(website_reason)
        website_text, website_warning = _fetch_public_reference_text(normalized_website, "Website")
        if website_text:
            sections.append(f"Website reference (secondary source)\nURL: {normalized_website}\n{website_text}")
        else:
            sections.append(f"Website reference (secondary source)\nURL: {normalized_website}")
            if website_warning:
                warnings.append(website_warning)
    elif str(website_url or "").strip():
        warnings.append("Website URL could not be normalized.")

    normalized_social = _normalize_public_source_url(social_url)
    if normalized_social:
        social_text, social_warning = _fetch_public_reference_text(normalized_social, "Social page")
        if social_text:
            sections.append(f"Social page reference (secondary source)\nURL: {normalized_social}\n{social_text}")
        else:
            sections.append(f"Social page reference (secondary source)\nURL: {normalized_social}")
            if social_warning:
                warnings.append(social_warning)
    elif str(social_url or "").strip():
        warnings.append("Social page URL could not be normalized.")

    combined = "\n\n".join(section for section in sections if str(section or "").strip())
    return _prepare_brief_for_synthesis(combined), warnings, enrichments


def _normalize_language_profile(profile: dict, raw_context: str) -> dict:
    existing = profile.get("language_profile") or {}
    if not isinstance(existing, dict):
        existing = {}

    brief_language = str(existing.get("brief_language") or "").strip().lower()
    primary_language = str(existing.get("primary_language") or "").strip().lower()
    caption_output_language = str(existing.get("caption_output_language") or "").strip().lower()
    arabic_mode = str(existing.get("arabic_mode") or "").strip().lower()
    legacy_target = str(existing.get("target_voice_language") or "").strip().lower()

    if not brief_language:
        brief_language = _detect_brief_language(raw_context)

    if legacy_target:
        if legacy_target == "arabic_gulf":
            primary_language = primary_language or "arabic"
            caption_output_language = caption_output_language or "arabic"
            arabic_mode = arabic_mode or "gulf"
        elif legacy_target == "arabic_msa":
            primary_language = primary_language or "arabic"
            caption_output_language = caption_output_language or "arabic"
            arabic_mode = arabic_mode or "msa"
        elif legacy_target == "english":
            primary_language = primary_language or "english"
            caption_output_language = caption_output_language or "english"
        elif legacy_target == "bilingual":
            primary_language = primary_language or "bilingual"
            caption_output_language = caption_output_language or "bilingual"

    if not primary_language:
        if brief_language == "bilingual":
            primary_language = "bilingual"
        elif brief_language == "arabic":
            primary_language = "arabic"
        else:
            primary_language = "english"

    if not caption_output_language:
        caption_output_language = "arabic" if primary_language == "arabic" else primary_language

    if caption_output_language == "arabic" and not arabic_mode:
        arabic_mode = "gulf"

    return {
        "brief_language": brief_language,
        "primary_language": primary_language,
        "caption_output_language": caption_output_language,
        "arabic_mode": arabic_mode or ("gulf" if caption_output_language == "arabic" else ""),
    }


def _normalize_synthesized_profile_result(result: dict, raw_context: str) -> dict:
    parsed = result if isinstance(result, dict) else {}
    if "data" in parsed and isinstance(parsed.get("data"), dict):
        data = dict(parsed.get("data") or {})
        status = str(parsed.get("status") or "success").strip() or "success"
        missing_fields = _as_clean_list(parsed.get("missing_fields"))
    else:
        data = dict(parsed)
        status = "success"
        missing_fields = _as_clean_list(parsed.get("missing_fields"))

    data["language_profile"] = _normalize_language_profile(data, raw_context)
    return {
        "status": status,
        "missing_fields": missing_fields,
        "data": data,
    }


def build_brand_profile(client_id: str, profile: dict) -> dict:
    profile = profile or {}
    voice = profile.get("brand_voice") or {}
    tone = voice.get("tone", profile.get("tone", []))
    if isinstance(tone, list):
        tone = ", ".join([str(item).strip() for item in tone if str(item).strip()])
    language_profile = profile.get("language_profile", {
        "brief_language": "english",
        "primary_language": "arabic",
        "caption_output_language": "arabic",
        "arabic_mode": "gulf"
    })
    main_language = str(profile.get("main_language") or "").strip().lower()
    if main_language not in {"arabic", "english", "both"}:
        caption_language = str(language_profile.get("caption_output_language") or "").strip().lower()
        main_language = "both" if caption_language == "bilingual" else (caption_language or "english")
    city_market = str(
        profile.get("city_market")
        or profile.get("market")
        or profile.get("city")
        or profile.get("location")
        or ""
    ).strip()
    services = _as_clean_list(profile.get("services"))
    dos_and_donts = _as_clean_list(profile.get("dos_and_donts"))
    voice_examples = _as_clean_list(profile.get("brand_voice_examples"))
    website_digest = profile.get("website_digest") or {}
    if not isinstance(website_digest, dict):
        website_digest = {}
    trend_dossier = profile.get("trend_dossier") or {}
    if not isinstance(trend_dossier, dict):
        trend_dossier = {}

    caption_profile = {
        "business_name": profile.get("business_name", client_id),
        "industry": profile.get("industry", "general"),
        "main_language": main_language,
        "city_market": city_market,
        "audience_summary": str(profile.get("target_audience", "")).strip(),
        "offer_summary": ", ".join(services[:6]),
        "voice_rules": [
            f"Tone: {str(tone or 'professional, friendly, engaging').strip()}",
            f"Style: {str(voice.get('style') or profile.get('style') or 'conversational').strip()}",
            f"Dialect: {str(voice.get('dialect') or profile.get('dialect') or 'gulf_arabic_khaleeji').strip()}",
            *voice_examples[:2],
        ],
        "do_avoid_rules": dos_and_donts[:8],
        "seo_keywords": _as_clean_list(profile.get("seo_keywords"))[:8],
        "language_profile": language_profile,
        "website_url": str(profile.get("website_url") or website_digest.get("url") or "").strip(),
        "website_digest": {
            "url": str(website_digest.get("url") or "").strip(),
            "title": str(website_digest.get("title") or "").strip(),
            "meta_description": str(website_digest.get("meta_description") or "").strip(),
            "headings": _as_clean_list(website_digest.get("headings") or [*(website_digest.get("h1") or []), *(website_digest.get("h2") or [])])[:8],
            "service_terms": _as_clean_list(website_digest.get("service_terms"))[:8],
            "brand_keywords": _as_clean_list(website_digest.get("brand_keywords"))[:8],
        },
        "trend_dossier": {
            "status": str(trend_dossier.get("status") or "").strip(),
            "provider": str(trend_dossier.get("provider") or "").strip(),
            "recency_days": trend_dossier.get("recency_days") or 30,
            "source_coverage": str(trend_dossier.get("source_coverage") or "").strip(),
            "recent_signals": _as_clean_list(trend_dossier.get("recent_signals"))[:12],
            "trend_angles": trend_dossier.get("trend_angles") if isinstance(trend_dossier.get("trend_angles"), list) else [],
            "hook_patterns": _as_clean_list(trend_dossier.get("hook_patterns"))[:8],
            "hashtag_candidates": _as_clean_list(trend_dossier.get("hashtag_candidates"))[:10],
            "topical_language": _as_clean_list(trend_dossier.get("topical_language"))[:10],
            "anti_cliche_guidance": _as_clean_list(trend_dossier.get("anti_cliche_guidance"))[:8],
            "source_links": [
                {
                    "title": str(item.get("title") or item.get("label") or "Source").strip(),
                    "url": str(item.get("url") or item.get("link") or "").strip(),
                    "published_at": str(item.get("published_at") or "").strip(),
                }
                for item in (trend_dossier.get("source_link_details") or trend_dossier.get("source_links") or [])
                if isinstance(item, dict) and str(item.get("url") or item.get("link") or "").strip()
            ][:6] or [
                {
                    "title": "Source",
                    "url": str(item).strip(),
                    "published_at": "",
                }
                for item in (trend_dossier.get("source_links") or [])
                if not isinstance(item, dict) and str(item).strip()
            ][:6],
            "fetched_at": str(trend_dossier.get("fetched_at") or "").strip(),
            "expires_at": str(trend_dossier.get("expires_at") or "").strip(),
        },
        "cta_style": str(
            profile.get("cta_style")
            or profile.get("conversion_goal")
            or "Clear, premium, direct, and conversion-aware."
        ).strip(),
    }
    return {
        "client_name": client_id,
        "business_name": profile.get("business_name", client_id),
        "industry": profile.get("industry", "general"),
        "main_language": main_language,
        "city_market": city_market,
        "brand_voice": {
            "tone": str(tone or "professional, friendly, engaging").strip(),
            "style": str(voice.get("style") or profile.get("style") or "conversational").strip(),
            "dialect": str(voice.get("dialect") or profile.get("dialect") or "gulf_arabic_khaleeji").strip(),
            "dialect_notes": str(voice.get("dialect_notes") or profile.get("dialect_notes") or "Use Khaleeji Gulf Arabic vocabulary.").strip(),
        },
        "brand_voice_examples": _as_clean_list(profile.get("brand_voice_examples")),
        "services": services,
        "target_audience": str(profile.get("target_audience", "")).strip(),
        "seo_keywords": _as_clean_list(profile.get("seo_keywords")),
        "hashtag_bank": _as_clean_list(profile.get("hashtag_bank")),
        "banned_words": _as_clean_list(profile.get("banned_words")),
        "language_profile": language_profile,
        "identity": str(profile.get("identity", "")).strip(),
        "dos_and_donts": dos_and_donts,
        "website_url": str(profile.get("website_url") or website_digest.get("url") or "").strip(),
        "caption_profile": caption_profile,
        "website_digest": caption_profile["website_digest"],
        "trend_dossier": caption_profile["trend_dossier"],
        "caption_defaults": profile.get("caption_defaults", {
            "min_length": 150,
            "max_length": 300,
            "hashtag_count_min": 3,
            "hashtag_count_max": 5
        })
    }


def validate_synthesized_profile(profile: dict) -> list[str]:
    profile = profile or {}
    voice = profile.get("brand_voice") or {}
    missing = []

    if not str(profile.get("business_name", "")).strip():
        missing.append("Business name")
    if not str(profile.get("industry", "")).strip():
        missing.append("Industry")
    if not _as_clean_list(profile.get("services")):
        missing.append("Services or offers")
    if not str(profile.get("target_audience", "")).strip():
        missing.append("Target audience")
    if not str(profile.get("identity", "")).strip():
        missing.append("Brand identity summary")
    if not str(voice.get("tone", "")).strip():
        missing.append("Brand voice tone")
    if not str(voice.get("style", "")).strip():
        missing.append("Brand voice style")
    return missing


def extract_brief_text(file_name: str, file_bytes: bytes) -> tuple[str, str]:
    ext = os.path.splitext(file_name or "")[1].lower()
    if ext in {".txt", ".md"}:
        return file_bytes.decode("utf-8", errors="ignore"), ext[1:]
    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        text_parts = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            if extracted.strip():
                text_parts.append(extracted.strip())
        return "\n\n".join(text_parts).strip(), "pdf"
    if ext == ".docx":
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
        return "\n".join(paragraphs).strip(), "docx"
    raise ValueError(f"Unsupported brief file type: {ext}")


@app.post("/api/parse-client-brief")
async def api_parse_client_brief(file: UploadFile = File(...)):
    file_bytes = await file.read()
    if not file.filename:
        return JSONResponse(status_code=400, content={"status": "error", "reason": "Missing filename."})

    try:
        extracted_text, source_type = extract_brief_text(file.filename, file_bytes)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"status": "error", "reason": str(exc)})
    except Exception as exc:
        logger.error(f"API | PARSE BRIEF | Failed to parse {file.filename}: {exc}")
        return JSONResponse(status_code=400, content={"status": "error", "reason": f"Could not parse {file.filename}. If it is scanned or image-only, paste extracted text manually."})

    if not extracted_text.strip():
        return JSONResponse(status_code=400, content={"status": "error", "reason": f"No readable text was extracted from {file.filename}. If it is scanned or image-only, paste extracted text manually."})

    return {
        "status": "success",
        "file_name": file.filename,
        "source_type": source_type,
        "char_count": len(extracted_text),
        "text": extracted_text,
    }


def _read_json_file(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _read_log_tail(path: str, limit: int = 6) -> list[str]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            tail = collections.deque(f, maxlen=limit)
        return [line.strip() for line in tail if line.strip()]
    except Exception:
        return []


def _job_sort_key(job: dict) -> tuple:
    scheduled_date = parse_iso_date(str(job.get("scheduled_date") or "").strip())
    raw_time = str(job.get("time") or "").strip()
    try:
        parsed_time = datetime.strptime(raw_time, "%I:%M %p").time()
    except ValueError:
        parsed_time = datetime.min.time()

    if scheduled_date:
        return (0, datetime.combine(scheduled_date, parsed_time))
    return (1, datetime.combine(datetime.now().date(), parsed_time))


def _collect_dashboard_state() -> dict:
    clients = []
    store = get_client_store()
    client_ids = store.list_client_ids()

    schedule_jobs = load_schedule("schedule.json")
    active_jobs, history_jobs = split_schedule_views(schedule_jobs)
    pending_approvals = list_live_pending_approvals()
    agency_config = get_agency_config()

    heartbeat_age_seconds = None
    scheduler_online = False
    heartbeat_path = ".daemon_heartbeat"
    if os.path.exists(heartbeat_path):
        try:
            with open(heartbeat_path, "r", encoding="utf-8") as f:
                last_heartbeat = float((f.read() or "0").strip())
            heartbeat_age_seconds = max(0, int(time.time() - last_heartbeat))
            scheduler_online = heartbeat_age_seconds <= 30
        except Exception:
            heartbeat_age_seconds = None
            scheduler_online = False

    total_assets = 0
    total_drafts = 0

    for client_id in client_ids:
        profile = store.get_client(client_id) or {}
        profile_json = profile.get("profile_json", {}) or {}
        missing_fields = validate_synthesized_profile(profile_json)

        asset_count = 0
        draft_count = 0
        latest_drafts = []
        asset_count = count_client_assets(client_id)
        queue_payload = list_client_drafts(client_id)
        bundles = queue_payload.get("bundles", {})
        draft_count = len(bundles)
        latest_drafts = list(bundles.keys())[:3]

        total_assets += asset_count
        total_drafts += draft_count

        client_active_jobs = [job for job in active_jobs if str(job.get("client") or "") == client_id]
        creds_ready = all([
            str(profile.get("meta_access_token") or "").strip(),
            str(profile.get("facebook_page_id") or "").strip(),
            str(profile.get("instagram_account_id") or "").strip(),
        ])

        clients.append({
            "client_id": client_id,
            "display_name": str(profile_json.get("business_name") or client_id).strip(),
            "asset_count": asset_count,
            "draft_count": draft_count,
            "active_job_count": len(client_active_jobs),
            "credentials_ready": creds_ready,
            "profile_ready": len(missing_fields) == 0,
            "missing_fields": missing_fields,
            "latest_drafts": latest_drafts,
            "profile": profile,
            "profile_json": profile_json,
        })

    next_job = None
    if active_jobs:
        ordered_jobs = sorted(active_jobs, key=_job_sort_key)
        candidate = ordered_jobs[0]
        client_display = str(candidate.get("client") or "").replace("_", " ").title()
        if candidate.get("scheduled_date"):
            display_window = f"{format_display_date(candidate.get('scheduled_date'))} at {candidate.get('time')}"
        else:
            display_window = f"{', '.join(candidate.get('days', []))} at {candidate.get('time')}"
        next_job = {
            "client": client_display,
            "topic": candidate.get("topic") or "Untitled",
            "display_window": display_window,
            "media_kind": candidate.get("media_kind") or "",
        }

    recent_failed_publish_runs = []
    failed_runs = [
        run for run in list_publish_runs()
        if str(run.get("status") or "").strip().lower() in {"error", "failed"}
    ]
    failed_runs.sort(key=lambda run: _parse_run_timestamp(run.get("created_at")) or datetime.min, reverse=True)
    for run in failed_runs[:6]:
        raw_output = {}
        try:
            raw_output = json.loads(str(run.get("raw_output") or "{}"))
        except Exception:
            raw_output = {}
        platform_results = run.get("platform_results") if isinstance(run.get("platform_results"), dict) else {}
        if not platform_results and isinstance(raw_output.get("platform_results"), dict):
            platform_results = raw_output.get("platform_results") or {}
        platform_errors = []
        for platform_name, platform_data in platform_results.items():
            if str((platform_data or {}).get("status") or "").strip().lower() != "error":
                continue
            error_message = str((platform_data or {}).get("error_message") or "").strip()
            if not error_message:
                continue
            platform_errors.append({
                "platform": str(platform_name or "").strip(),
                "message": error_message,
                "step": str((platform_data or {}).get("step") or "").strip(),
            })
        summary = str(raw_output.get("message") or run.get("failure_step") or "Scheduled publish failed.").strip()
        if platform_errors:
            primary = platform_errors[0]
            step_label = f" ({primary['step']})" if primary.get("step") else ""
            summary = f"{primary['platform'].capitalize()}: {primary['message']}{step_label}"
        recent_failed_publish_runs.append({
            "run_id": str(run.get("run_id") or "").strip(),
            "client_id": str(run.get("client_id") or "").strip(),
            "topic": str(run.get("topic") or "").strip(),
            "draft_id": str(run.get("draft_id") or "").strip(),
            "job_id": str(run.get("job_id") or "").strip(),
            "created_at": run.get("created_at"),
            "failure_step": str(run.get("failure_step") or "").strip(),
            "summary": summary,
            "platform_errors": platform_errors[:3],
        })

    return {
        "clients": clients,
        "client_count": len(client_ids),
        "asset_count": total_assets,
        "draft_count": total_drafts,
        "active_jobs": active_jobs,
        "history_jobs": history_jobs,
        "active_job_count": len(active_jobs),
        "history_count": len(history_jobs),
        "pending_approvals": pending_approvals,
        "pending_approval_count": len(pending_approvals),
        "scheduler_online": scheduler_online,
        "heartbeat_age_seconds": heartbeat_age_seconds,
        "agency_notifications_ready": bool(str(agency_config.get("owner_phone") or "").strip() and str(agency_config.get("whatsapp_access_token") or "").strip()),
        "agency_config": agency_config,
        "next_job": next_job,
        "recent_activity": _read_log_tail("pipeline_stream.log", limit=6),
        "recent_failed_publish_runs": recent_failed_publish_runs,
    }


def _parse_run_timestamp(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _recent_activity_mentions(lines: list[str], needles: list[str]) -> bool:
    haystack = "\n".join(str(line or "") for line in lines).lower()
    return any(needle.lower() in haystack for needle in needles)


def _build_agent_status_cards(state: dict) -> list[dict]:
    activity = list(state.get("recent_activity") or [])
    client_count = int(state.get("client_count") or 0)
    draft_count = int(state.get("draft_count") or 0)
    active_job_count = int(state.get("active_job_count") or 0)
    pending_approval_count = int(state.get("pending_approval_count") or 0)
    scheduler_online = bool(state.get("scheduler_online"))
    agency_notifications_ready = bool(state.get("agency_notifications_ready"))

    clients = state.get("clients") or []
    profile_ready_count = sum(1 for client in clients if client.get("profile_ready"))

    def card(key: str, name: str, file_name: str, state_name: str, tone: str, detail: str) -> dict:
        return {
            "key": key,
            "name": name,
            "file": file_name,
            "state": state_name,
            "tone": tone,
            "detail": detail,
        }

    return [
        card(
            "orchestrator",
            "Lead Orchestrator",
            "orchestrator_agent.py",
            "Live" if _recent_activity_mentions(activity, ["API | ORCHESTRATOR"]) else "Ready",
            "on",
            "Routes operator intent into drafting, approvals, scheduling, and immediate publish actions.",
        ),
        card(
            "synthesizer",
            "Brand Profile Synthesis",
            "webhook_server.py",
            "Live" if _recent_activity_mentions(activity, ["API | SYNTHESIZE"]) else ("Ready" if client_count else "Waiting"),
            "on" if client_count else "warn",
            f"{profile_ready_count} client profile{'s' if profile_ready_count != 1 else ''} are structurally complete and ready for brand-memory use.",
        ),
        card(
            "caption",
            "Caption Service",
            "caption_agent.py",
            "Live" if _recent_activity_mentions(activity, ["GENERATED TEXT", "Caption", "caption"]) else ("Ready" if draft_count else "Waiting"),
            "on" if draft_count else "warn",
            f"{draft_count} stored draft{'s' if draft_count != 1 else ''} are available for caption generation or refinement.",
        ),
        card(
            "publish",
            "Publishing Engine",
            "publish_agent.py",
            "Live" if _recent_activity_mentions(activity, ["PUBLISHING RESULTS", "PIPELINE FINAL REPORT", "PIPELINE_STATUS"]) else ("Ready" if client_count else "Waiting"),
            "on" if client_count else "warn",
            "Handles the live Meta publish handoff, media delivery, and platform result reporting.",
        ),
        card(
            "scheduler",
            "Scheduler Daemon",
            "scheduler.py",
            "Live" if scheduler_online else "Attention",
            "on" if scheduler_online else "warn",
            f"{active_job_count} active release job{'s' if active_job_count != 1 else ''} are currently being tracked by the execution loop.",
        ),
        card(
            "whatsapp",
            "WhatsApp Approval Router",
            "whatsapp_agent.py",
            "Live" if agency_notifications_ready else "Setup",
            "on" if agency_notifications_ready else "warn",
            f"{pending_approval_count} pending mobile approval{'s' if pending_approval_count != 1 else ''} can be routed through the agency WhatsApp lane.",
        ),
    ]


def _build_client_value_brief(client_id: str) -> dict | None:
    store = get_client_store()
    profile = store.get_client(client_id)
    if not profile:
        return None

    profile_json = profile.get("profile_json") or {}
    brand_profile = store.get_brand_profile(client_id) or build_brand_profile(client_id, profile_json)
    display_name = str(profile_json.get("business_name") or client_id).replace("_", " ").strip()

    missing_fields = validate_synthesized_profile(profile_json)
    profile_ready = len(missing_fields) == 0
    credentials_ready = all(
        str(profile.get(key) or "").strip()
        for key in ("meta_access_token", "facebook_page_id", "instagram_account_id")
    )

    assets_count = count_client_assets(client_id)
    draft_payload = list_client_drafts(client_id)
    bundles = draft_payload.get("bundles", {}) or {}
    draft_count = len(bundles)
    stored_caption_count = sum(1 for payload in bundles.values() if str((payload or {}).get("caption_text") or "").strip())

    schedule_jobs = load_schedule("schedule.json")
    active_jobs, history_jobs = split_schedule_views(schedule_jobs)
    client_active_jobs = [job for job in active_jobs if str(job.get("client") or "").strip() == client_id]
    client_history_jobs = [job for job in history_jobs if str(job.get("client") or "").strip() == client_id]
    pending_approvals = [job for job in list_live_pending_approvals() if str(job.get("client") or "").strip() == client_id]

    publish_runs = [run for run in list_publish_runs() if str(run.get("client_id") or "").strip() == client_id]
    publish_runs.sort(key=lambda run: _parse_run_timestamp(run.get("created_at")) or datetime.min, reverse=True)
    now = datetime.now(timezone.utc)
    recent_runs = []
    for run in publish_runs:
        ts = _parse_run_timestamp(run.get("created_at"))
        if ts and (now - ts.replace(tzinfo=None)).days <= 30:
            recent_runs.append(run)
    successful_recent_runs = [run for run in recent_runs if str(run.get("status") or "").lower() in {"success", "partial_success"}]
    successful_all_runs = [run for run in publish_runs if str(run.get("status") or "").lower() in {"success", "partial_success"}]
    publish_health = round((len(successful_recent_runs) / len(recent_runs)) * 100) if recent_runs else None
    last_success = successful_all_runs[0] if successful_all_runs else None

    agency_config = get_agency_config()
    approval_routing = normalize_approval_routing_mode(agency_config.get("approval_routing"))
    routing_label = {
        "desktop_first": "Desktop First",
        "desktop_and_whatsapp": "Desktop + WhatsApp",
        "whatsapp_only": "WhatsApp Only",
    }.get(approval_routing, "Desktop First")
    owner_phone = str(agency_config.get("owner_phone") or "").strip()
    agency_token = str(agency_config.get("whatsapp_access_token") or "").strip()
    agency_phone_id = str(agency_config.get("whatsapp_phone_id") or "").strip()
    mobile_control_ready = bool(owner_phone and agency_token and agency_phone_id)

    seo_keywords = profile_json.get("seo_keywords") or []
    voice_examples = profile_json.get("brand_voice_examples") or []
    copy_rules = profile_json.get("dos_and_donts") or []
    services = profile_json.get("services") or []
    focus_label = str((seo_keywords[0] if seo_keywords else services[0] if services else profile_json.get("industry") or "brand operations")).strip()

    readiness_score = 0
    readiness_score += 30 if profile_ready else 0
    readiness_score += 25 if credentials_ready else 0
    readiness_score += 10 if assets_count else 0
    readiness_score += 10 if draft_count else 0
    readiness_score += 10 if mobile_control_ready else 0
    readiness_score += 15 if recent_runs or client_active_jobs or pending_approvals else 0

    if readiness_score >= 90:
        readiness_label = "Production Lane Ready"
    elif readiness_score >= 70:
        readiness_label = "Operationally Strong"
    elif readiness_score >= 45:
        readiness_label = "Foundation Built"
    else:
        readiness_label = "Needs Setup"

    next_release = None
    if client_active_jobs:
        next_job = sorted(client_active_jobs, key=_job_sort_key)[0]
        if next_job.get("scheduled_date"):
            next_release = f"{format_display_date(next_job.get('scheduled_date'))} at {next_job.get('time')}"
        elif next_job.get("time"):
            next_release = f"{', '.join(next_job.get('days', []))} at {next_job.get('time')}"

    proof_points = []
    if profile_ready:
        proof_points.append(
            f"Brand memory is locked with {len(voice_examples)} voice example{'s' if len(voice_examples) != 1 else ''}, {len(copy_rules)} copy rule{'s' if len(copy_rules) != 1 else ''}, and a clear audience definition."
        )
    else:
        proof_points.append(
            f"Jarvis already captured the client profile, but {len(missing_fields)} critical brand detail{'s' if len(missing_fields) != 1 else ''} still need to be tightened."
        )
    proof_points.append(
        f"{assets_count} asset{'s' if assets_count != 1 else ''} and {draft_count} creative draft{'s' if draft_count != 1 else ''} are staged inside the client vault."
    )
    proof_points.append(
        f"{stored_caption_count} stored caption{'s' if stored_caption_count != 1 else ''} already exist, which means Jarvis can preserve approved copy instead of regenerating everything from scratch."
    )
    if recent_runs:
        proof_points.append(
            f"Execution health over the last 30 days is {publish_health}% across {len(recent_runs)} tracked publish run{'s' if len(recent_runs) != 1 else ''}."
        )
    elif last_success:
        proof_points.append("Jarvis has already completed at least one live publish run for this client.")
    else:
        proof_points.append("The publish path is ready for the first live release once the agency pushes this account live.")
    if mobile_control_ready:
        proof_points.append(f"Approval routing is set to {routing_label}, so desktop stays primary while WhatsApp acts as the mobile control lane.")
    else:
        proof_points.append(f"Approval routing is set to {routing_label}, but the agency WhatsApp runtime still needs to be finalized for mobile control.")

    next_actions = []
    if not profile_ready:
        next_actions.append(f"Complete the missing brand intelligence: {', '.join(missing_fields[:3])}.")
    if not credentials_ready:
        next_actions.append("Finish the live Meta credentials so Jarvis can publish without operator patchwork.")
    if not assets_count:
        next_actions.append("Upload at least one asset so the client starts with a real creative object inside Jarvis.")
    if not draft_count:
        next_actions.append("Create at least one creative draft so approvals, captions, and scheduling can run from a real workflow.")
    if not mobile_control_ready:
        next_actions.append("Complete the agency WhatsApp runtime if you want mobile control and exception handling to stay live.")
    if not next_actions:
        next_actions.append("Use this operating brief to show that the client already has a managed operating lane inside Jarvis.")

    summary = (
        f"Jarvis has already turned {display_name} into a managed operating lane: "
        f"{assets_count} asset{'s' if assets_count != 1 else ''}, "
        f"{draft_count} draft{'s' if draft_count != 1 else ''}, "
        f"{len(pending_approvals)} pending approval{'s' if len(pending_approvals) != 1 else ''}, "
        f"and {len(client_active_jobs)} live scheduled job{'s' if len(client_active_jobs) != 1 else ''} tracked from one control surface."
    )
    operator_pitch = (
        f"For {display_name}, the agency is no longer selling isolated posts. Jarvis keeps the brand memory, copy workflow, approvals, "
        f"release queue, and publishing credentials controlled in one operating system."
    )
    client_pitch = (
        f"This client can now be managed from one lane: the desktop acts as the workstation, {routing_label.lower()} handles approvals, "
        f"and every asset, draft, caption, and release window stays mapped to the same account."
    )
    copy_text = "\n".join([
        f"{display_name} | Client Success Brief",
        summary,
        operator_pitch,
        client_pitch,
        "",
        "Proof Points:",
        *[f"- {point}" for point in proof_points],
        "",
        "Next Actions:",
        *[f"- {action}" for action in next_actions],
    ])

    return {
        "client_id": client_id,
        "display_name": display_name,
        "focus_label": focus_label,
        "readiness": {
            "score": readiness_score,
            "label": readiness_label,
            "profile_ready": profile_ready,
            "credentials_ready": credentials_ready,
            "mobile_control_ready": mobile_control_ready,
            "approval_routing": approval_routing,
            "approval_routing_label": routing_label,
        },
        "metrics": {
            "assets_count": assets_count,
            "draft_count": draft_count,
            "stored_caption_count": stored_caption_count,
            "pending_approval_count": len(pending_approvals),
            "active_job_count": len(client_active_jobs),
            "delivered_job_count": len(client_history_jobs),
            "publish_run_count": len(publish_runs),
            "publish_run_count_30d": len(recent_runs),
            "publish_health_30d": publish_health,
            "seo_keyword_count": len(seo_keywords),
            "voice_example_count": len(voice_examples),
            "copy_rule_count": len(copy_rules),
        },
        "timeline": {
            "next_release_window": next_release,
            "last_success_at": last_success.get("created_at") if last_success else None,
        },
        "narrative": {
            "summary": summary,
            "operator_pitch": operator_pitch,
            "client_pitch": client_pitch,
        },
        "proof_points": proof_points,
        "next_actions": next_actions,
        "copy_text": copy_text,
    }


@app.get("/api/dashboard-summary")
async def api_dashboard_summary():
    state = _collect_dashboard_state()
    agent_cards = _build_agent_status_cards(state)
    return {
        "status": "success",
        "summary": {
            "client_count": state["client_count"],
            "asset_count": state["asset_count"],
            "draft_count": state["draft_count"],
            "active_job_count": state["active_job_count"],
            "history_count": state["history_count"],
            "pending_approval_count": state["pending_approval_count"],
            "approval_routing": normalize_approval_routing_mode(state["agency_config"].get("approval_routing")),
            "scheduler_online": state["scheduler_online"],
            "heartbeat_age_seconds": state["heartbeat_age_seconds"],
            "agency_notifications_ready": state["agency_notifications_ready"],
            "next_job": state["next_job"],
            "clients": [
                {
                    "client_id": client["client_id"],
                    "display_name": client["display_name"],
                    "asset_count": client["asset_count"],
                    "draft_count": client["draft_count"],
                    "active_job_count": client["active_job_count"],
                    "credentials_ready": client["credentials_ready"],
                    "profile_ready": client["profile_ready"],
                    "missing_fields": client["missing_fields"],
                    "latest_drafts": client["latest_drafts"],
                }
                for client in state["clients"]
            ],
            "recent_activity": state["recent_activity"],
            "recent_failed_publish_runs": state["recent_failed_publish_runs"],
            "agent_cards": agent_cards,
        }
    }


@app.get("/api/client-value-brief/{client_id}")
async def api_client_value_brief(client_id: str):
    brief = _build_client_value_brief(client_id)
    if not brief:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "reason": f"Client '{client_id}' was not found in the active data backend."},
        )
    return {"status": "success", "brief": brief}


def _validate_runtime_state_backend() -> dict:
    backend_name = str(getattr(get_client_store(), "backend_name", "json") or "json").strip().lower()
    if backend_name != "supabase":
        return {
            "ok": True,
            "configured": True,
            "backend": backend_name,
            "detail": "Runtime state is using the local JSON backend. Supabase remains the recommended production store.",
        }
    try:
        runtime_store = get_runtime_state_store()
        if getattr(runtime_store, "backend_name", "") == "fallback" and hasattr(runtime_store, "primary"):
            try:
                runtime_store.primary.list_orchestrator_runs(limit=1)
            except Exception as exc:
                return {
                    "ok": False,
                    "configured": True,
                    "backend": "supabase",
                    "detail": (
                        "Supabase runtime tables are not ready yet; Jarvis is currently using JSON fallback for runtime state. "
                        f"Apply the runtime schema migration to remove fallback mode. Details: {exc}"
                    ),
                }
        list_orchestrator_run_states(limit=1)
        return {
            "ok": True,
            "configured": True,
            "backend": backend_name,
            "detail": "Supabase runtime state backend is reachable.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "configured": True,
            "backend": backend_name,
            "detail": f"Supabase runtime state backend is not reachable: {exc}",
        }


def _validate_public_media_runtime() -> dict:
    media_base = str(
        os.getenv("PUBLISH_MEDIA_BASE_URL")
        or os.getenv("PUBLIC_ASSET_BASE_URL")
        or os.getenv("WEBHOOK_PROXY_URL")
        or ""
    ).strip().rstrip("/")
    if not media_base:
        return {"ok": False, "configured": False, "detail": "No public media host is configured."}
    lowered = media_base.lower()
    if "localhost" in lowered or "127.0.0.1" in lowered:
        return {"ok": False, "configured": True, "detail": f"Public media host points to a local-only address: {media_base}"}
    if not media_base.startswith("https://"):
        return {"ok": False, "configured": True, "detail": f"Public media host must use HTTPS: {media_base}"}
    try:
        parsed = urlparse(media_base)
        hostname = str(parsed.hostname or "").strip()
        if not hostname:
            return {"ok": False, "configured": True, "detail": f"Public media host has no valid hostname: {media_base}"}
        socket.getaddrinfo(hostname, parsed.port or 443)
    except Exception as exc:
        return {"ok": False, "configured": True, "detail": f"Public media host is configured but not resolvable right now: {media_base} ({exc})"}
    return {"ok": True, "configured": True, "detail": f"Public media host is set to {media_base}."}


def _collect_runtime_readiness(force: bool = False) -> dict:
    if force:
        _runtime_probe_cache.clear()
    state = _collect_dashboard_state()
    tunnel_running, tunnel_provider = _is_process_running(["cloudflared", "ngrok http", "ngrok"])
    runtime_state = _validate_runtime_state_backend()
    public_media = _validate_public_media_runtime()
    whatsapp = _validate_demo_whatsapp_runtime()
    ready_clients = [client for client in state["clients"] if client["credentials_ready"]]
    checks = {
        "api": {"ok": True, "detail": "FastAPI process is serving requests."},
        "runtime_state": runtime_state,
        "scheduler": {
            "ok": bool(state["scheduler_online"]),
            "detail": (
                f"Scheduler heartbeat seen {state['heartbeat_age_seconds']}s ago."
                if state["scheduler_online"]
                else "No recent scheduler heartbeat detected."
            ),
        },
        "public_media_host": public_media,
        "whatsapp_runtime": whatsapp,
        "meta_client_credentials": {
            "ok": bool(ready_clients),
            "detail": (
                f"{len(ready_clients)} client(s) have Meta credentials configured."
                if ready_clients
                else "No client currently has publish-ready Meta credentials."
            ),
        },
        "tunnel_runtime": {
            "ok": bool(tunnel_running),
            "detail": (
                f"Public tunnel process detected via {tunnel_provider}."
                if tunnel_running
                else "No public tunnel process detected."
            ),
        },
    }
    required_keys = ("api", "runtime_state", "scheduler", "public_media_host")
    overall_ok = all(bool(checks[key]["ok"]) for key in required_keys)
    return {
        "ok": overall_ok,
        "generated_at": _utc_now_iso(),
        "checks": checks,
        "summary": {
            "client_count": state["client_count"],
            "draft_count": state["draft_count"],
            "pending_approval_count": state["pending_approval_count"],
            "publish_run_count": len(list_publish_runs()),
            "scheduler_online": state["scheduler_online"],
            "heartbeat_age_seconds": state["heartbeat_age_seconds"],
        },
    }


@app.on_event("startup")
async def jarvis_startup_validation() -> None:
    global _startup_validation_snapshot
    delete_expired_auth_sessions(now_iso=_utc_now_iso())
    try:
        for run in list_orchestrator_run_states(limit=100):
            run_id = str(run.get("run_id") or "").strip()
            if run_id:
                _orchestrator_runs[run_id] = run
    except Exception as exc:
        logger.warning("Failed to hydrate orchestrator runtime state on startup: %s", exc)
    _startup_validation_snapshot = _collect_runtime_readiness(force=True)
    logger.info("Jarvis startup readiness: %s", json.dumps(_startup_validation_snapshot, ensure_ascii=False))
    if JARVIS_STRICT_STARTUP and not _startup_validation_snapshot.get("ok"):
        failed = [
            key
            for key, probe in (_startup_validation_snapshot.get("checks") or {}).items()
            if isinstance(probe, dict) and not probe.get("ok")
        ]
        raise RuntimeError(f"Jarvis strict startup validation failed: {', '.join(failed) or 'unknown checks'}")


@app.exception_handler(RequestValidationError)
async def jarvis_validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = _ensure_request_id(request)
    logger.warning("Validation error [%s] on %s: %s", request_id, request.url.path, exc)
    if (request.url.path or "/").startswith("/api/"):
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "reason": "Request validation failed.",
                "details": exc.errors(),
                "request_id": request_id,
            },
        )
    return PlainTextResponse("Request validation failed.", status_code=422, headers={"x-request-id": request_id})


@app.exception_handler(Exception)
async def jarvis_unhandled_exception_handler(request: Request, exc: Exception):
    request_id = _ensure_request_id(request)
    logger.error("Unhandled error [%s] on %s: %s", request_id, request.url.path, exc, exc_info=True)
    if (request.url.path or "/").startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "reason": "Internal server error.",
                "request_id": request_id,
            },
        )
    return PlainTextResponse("Internal server error.", status_code=500, headers={"x-request-id": request_id})


@app.get("/api/health")
async def api_health():
    state = _collect_dashboard_state()
    tunnel_running, tunnel_provider = _is_process_running(["cloudflared", "ngrok http", "ngrok"])
    readiness = _collect_runtime_readiness()
    return {
        "status": "success",
        "health": {
            "api": "online",
            "scheduler_online": state["scheduler_online"],
            "heartbeat_age_seconds": state["heartbeat_age_seconds"],
            "tunnel_running": tunnel_running,
            "tunnel_provider": tunnel_provider or None,
            "client_count": state["client_count"],
            "draft_count": state["draft_count"],
            "pending_approval_count": state["pending_approval_count"],
            "trend_research": get_trend_research_health(),
        },
        "readiness": readiness,
        "startup_validation": _startup_validation_snapshot,
    }


@app.get("/api/data-backend")
async def api_data_backend():
    store = get_client_store()
    return {
        "status": "success",
        "backend": store.backend_name,
        "supabase_configured": bool(str(os.getenv("SUPABASE_URL") or "").strip() and str(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()),
    }


@app.get("/api/demo-readiness")
async def api_demo_readiness(force: int = 0):
    if force:
        _runtime_probe_cache.clear()
    state = _collect_dashboard_state()
    tunnel_running, tunnel_provider = _is_process_running(["cloudflared", "ngrok http", "ngrok"])
    ready_clients = [
        client for client in state["clients"]
        if client["profile_ready"] and client["credentials_ready"]
    ]
    draft_ready_clients = [
        client for client in ready_clients
        if client["draft_count"] > 0
    ]
    draft_ready_clients.sort(key=lambda client: (client["draft_count"], client["asset_count"]), reverse=True)
    demo_client = draft_ready_clients[0] if draft_ready_clients else None

    checks = []

    def add_check(key: str, label: str, status: str, detail: str, critical: bool):
        checks.append({
            "key": key,
            "label": label,
            "status": status,
            "detail": detail,
            "critical": critical,
        })

    add_check(
        "api_backend",
        "API backend",
        "pass",
        "FastAPI is online and serving the command surface.",
        True,
    )
    add_check(
        "scheduler_daemon",
        "Scheduler daemon",
        "pass" if state["scheduler_online"] else "fail",
        f"Heartbeat seen {state['heartbeat_age_seconds']}s ago." if state["scheduler_online"] else "No recent heartbeat was detected from scheduler.py.",
        True,
    )
    add_check(
        "client_inventory",
        "Client inventory",
        "pass" if state["client_count"] else "fail",
        f"{state['client_count']} client profile(s) are loaded." if state["client_count"] else "No clients have been saved yet.",
        True,
    )
    add_check(
        "creative_library",
        "Creative library",
        "pass" if draft_ready_clients else "fail",
        f"{len(draft_ready_clients)} client(s) have credentials, brand profiles, and live drafts ready." if draft_ready_clients else "No client currently has a complete profile, live credentials, and at least one creative draft.",
        True,
    )

    whatsapp_probe = _validate_demo_whatsapp_runtime()
    add_check(
        "agency_whatsapp",
        "Agency WhatsApp runtime",
        "pass" if whatsapp_probe.get("ok") else ("warn" if not whatsapp_probe.get("configured") else "fail"),
        whatsapp_probe.get("detail", "Agency WhatsApp runtime is not configured."),
        False,
    )

    add_check(
        "public_tunnel",
        "Public webhook tunnel",
        "pass" if tunnel_running else "warn",
        f"{tunnel_provider} process detected on this machine." if tunnel_running else "No cloudflared/ngrok process was detected. WhatsApp approval callbacks may fail if the tunnel is down.",
        False,
    )

    if demo_client:
        meta_probe = _validate_demo_meta_client(demo_client["client_id"], demo_client["profile"])
        add_check(
            "demo_client_meta",
            f"Demo client publish path ({demo_client['display_name']})",
            "pass" if meta_probe.get("ok") else "fail",
            meta_probe.get("detail", "Meta credentials could not be validated."),
            True,
        )
    else:
        add_check(
            "demo_client_meta",
            "Demo client publish path",
            "fail",
            "No draft-ready client exists yet, so Jarvis cannot validate a live publish path.",
            True,
        )

    add_check(
        "brief_parser",
        "Brief parser",
        "pass",
        "TXT, MD, PDF, and DOCX intake parsing is installed on this machine.",
        False,
    )
    add_check(
        "approval_queue",
            "Release approvals",
            "warn" if state["pending_approval_count"] else "pass",
            f"{state['pending_approval_count']} release approval(s) are still waiting." if state["pending_approval_count"] else "Release approvals are clear.",
        False,
    )

    overall_status = "ready"
    if any(check["critical"] and check["status"] == "fail" for check in checks):
        overall_status = "blocked"
    elif any(check["status"] != "pass" for check in checks):
        overall_status = "attention"

    suggestions = []
    if not state["scheduler_online"]:
        suggestions.append("Start scheduler.py before the demo so scheduled posts and delivery state stay live.")
    if not tunnel_running:
        suggestions.append("Launch cloudflared or ngrok before demonstrating WhatsApp approvals and callbacks.")
    if not draft_ready_clients:
        suggestions.append("Prepare at least one client with live credentials and one creative draft before demoing Jarvis.")
    elif demo_client:
        suggestions.append(f"Lead with {demo_client['display_name']}: it already has {demo_client['draft_count']} live draft(s) prepared.")
    if state["pending_approval_count"]:
        suggestions.append("Clear or resolve pending approvals so the demo surface looks intentional and clean.")
    if not whatsapp_probe.get("ok"):
        suggestions.append("Verify the agency WhatsApp token/phone ID if you want the mobile approval loop in the demo.")

    startup = {
        "start_script": "scripts/start_demo.sh",
        "stop_script": "scripts/stop_demo.sh",
        "status_script": "scripts/demo_status.sh",
    }

    return {
        "status": "success",
        "readiness": {
            "overall_status": overall_status,
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "client_count": state["client_count"],
                "draft_count": state["draft_count"],
                "active_job_count": state["active_job_count"],
                "pending_approval_count": state["pending_approval_count"],
                "recommended_demo_client": {
                    "client_id": demo_client["client_id"],
                    "display_name": demo_client["display_name"],
                    "draft_count": demo_client["draft_count"],
                    "asset_count": demo_client["asset_count"],
                } if demo_client else None,
            },
            "checks": checks,
            "suggestions": suggestions,
            "startup": startup,
        },
    }

@app.post("/api/synthesize-client")
async def api_synthesize_client(req: SynthesizeRequest):
    logger.info(f"API | SYNTHESIZE | Extracting profile for {req.client_name} using {SYNTHESIZER_MODEL}")
    
    # Use OpenRouter for synthesis because the direct OpenAI key currently has no paid quota.
    api_key = os.getenv("OPENROUTER_API_KEY")
    base_url = "https://openrouter.ai/api/v1"

    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OPENROUTER_API_KEY in .env")

    synthesis_context, source_warnings, enrichments = await asyncio.to_thread(
        _prepare_synthesis_context,
        req.raw_context,
        req.quick_intake,
        req.website_url,
        req.social_url,
    )
    if not synthesis_context.strip():
        return {
            "status": "error",
            "reason": "Add a few quick client details, a website/social page, or extra notes before Jarvis can build the profile.",
        }

    quick_intake_only = bool(
        req.quick_intake
        and not str(req.raw_context or "").strip()
        and not str(req.website_url or "").strip()
        and not str(req.social_url or "").strip()
    )

    if quick_intake_only:
        prompt = f"""You are a brand profile extractor.
Read the client intake and return one JSON object only.

Client Name: {req.client_name}
Client Intake:
{synthesis_context}

Rules:
- Operator answers are the source of truth.
- Do not invent important details.
- If a field is unknown, leave it empty or [] and include it in missing_fields.
- Keep the response compact and usable.
- For language_profile:
  - brief_language: english, arabic, or bilingual
  - primary_language: english, arabic, or bilingual
  - caption_output_language: english, arabic, or bilingual
  - arabic_mode: gulf or msa when Arabic output is chosen, else ""

Return valid JSON only in this exact shape:
{{
  "status": "success",
  "missing_fields": [],
  "data": {{
    "business_name": "",
    "industry": "",
    "language_profile": {{
      "brief_language": "",
      "primary_language": "",
      "caption_output_language": "",
      "arabic_mode": ""
    }},
    "brand_voice": {{
      "tone": "",
      "style": "",
      "dialect": "",
      "dialect_notes": ""
    }},
    "services": [],
    "target_audience": "",
    "brand_voice_examples": [],
    "seo_keywords": [],
    "hashtag_bank": [],
    "banned_words": [],
    "caption_defaults": {{
      "min_length": 150,
      "max_length": 300,
      "hashtag_count_min": 3,
      "hashtag_count_max": 5
    }},
    "identity": "",
    "dos_and_donts": []
  }}
}}
"""
    else:
        prompt = f"""You are an expert Brand Strategist AND Data Extraction Specialist.
Your job is to read raw notes/documents from a business owner and extract a complete brand profile.

Client Name: {req.client_name}
Raw Information:
{synthesis_context}

CRITICAL: Direct operator answers are the primary source of truth. Website/social content and uploaded notes are secondary enrichment only. You may infer minor supporting details, but you must NOT invent critical brand intelligence. If services, target audience, identity, or brand voice examples are missing, mark them in missing_fields instead of hallucinating them.

For the `language_profile` block:
- "brief_language": choose "english", "arabic", or "bilingual" based on the input brief.
- "primary_language": choose "english", "arabic", or "bilingual" based on the brand's real communication lane.
- "caption_output_language": choose the language Jarvis should generate captions in: "english", "arabic", or "bilingual".
- "arabic_mode": if caption_output_language is arabic, choose "gulf" or "msa". Default to "gulf" for gulf market brands.

If generating an Arabic profile, generate seo_keywords and hashtag_bank in Arabic. For Gulf markets, use Khaleeji vocabulary for dialect_notes.

Return ONLY valid JSON matching this exact schema. Do not wrap in markdown tags:
{{
  "status": "success",
  "missing_fields": [],
  "data": {{
    "business_name": "The Arabic or English business name",
    "industry": "e.g. food_beverage, real_estate, fashion, etc.",
    "language_profile": {{
      "brief_language": "english",
      "primary_language": "arabic",
      "caption_output_language": "arabic",
      "arabic_mode": "gulf"
    }},
    "brand_voice": {{
      "tone": "3 adjectives describing their voice",
      "style": "overall communication style description",
      "dialect": "gulf_arabic_khaleeji",
      "dialect_notes": "Specific vocabulary guidance for this brand"
    }},
    "services": ["service_1", "service_2", "service_3"],
    "target_audience": "Who they are selling to",
    "brand_voice_examples": ["Real caption example 1", "Real caption example 2", "Real caption example 3"],
    "seo_keywords": ["SEO keyword 1", "keyword 2", "keyword 3", "keyword 4", "keyword 5"],
    "hashtag_bank": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5"],
    "banned_words": ["word1", "word2", "word3"],
    "caption_defaults": {{
      "min_length": 150,
      "max_length": 300,
      "hashtag_count_min": 3,
      "hashtag_count_max": 5
    }},
    "identity": "A 1-2 sentence description of who they are",
    "dos_and_donts": ["Rule 1", "Rule 2", "Rule 3"]
  }}
}}
"""
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url:
        headers["HTTP-Referer"] = "https://localhost"
        headers["X-Title"] = "Agency OS"

    data = {
        "model": SYNTHESIZER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "max_tokens": 1000 if quick_intake_only else 1600,
    }
    
    try:
        total_timeout_seconds = SYNTHESIS_FAST_TIMEOUT_SECONDS if quick_intake_only else SYNTHESIS_TOTAL_TIMEOUT_SECONDS
        started_at = time.monotonic()
        fallback_models = []
        if SYNTHESIZER_MODEL:
            fallback_models.append(SYNTHESIZER_MODEL)
        if not quick_intake_only and "qwen/qwen3.6-plus-preview:free" not in fallback_models:
            fallback_models.append("qwen/qwen3.6-plus-preview:free")
        if not quick_intake_only and "qwen/qwen3-next-80b-a3b-instruct:free" not in fallback_models:
            fallback_models.append("qwen/qwen3-next-80b-a3b-instruct:free")

        provider_error = None
        token_budgets = (1000,) if quick_intake_only else (1600, 2200)
        for candidate_model in fallback_models:
            for token_budget in token_budgets:
                elapsed = time.monotonic() - started_at
                remaining = total_timeout_seconds - elapsed
                if remaining <= 0:
                    provider_error = "Jarvis stopped the profile build because the provider took too long on the current model path."
                    logger.warning(
                        "Synthesis budget exhausted for %s after %.2fs.",
                        req.client_name,
                        elapsed,
                    )
                    return {"status": "error", "reason": provider_error}

                request_payload = dict(data)
                request_payload["model"] = candidate_model
                request_payload["max_tokens"] = token_budget
                request_timeout = (
                    min(SYNTHESIS_CONNECT_TIMEOUT_SECONDS, 5.0) if quick_intake_only else SYNTHESIS_CONNECT_TIMEOUT_SECONDS,
                    max(8.0, min(45.0 if quick_intake_only else SYNTHESIS_READ_TIMEOUT_SECONDS, remaining)),
                )
                try:
                    response = await asyncio.to_thread(
                        requests.post,
                        f"{base_url}/chat/completions",
                        headers=headers,
                        json=request_payload,
                        timeout=request_timeout,
                    )
                except requests.Timeout:
                    provider_error = "Jarvis stopped the profile build because the provider took too long on the current model path."
                    logger.warning(
                        "Synthesis provider timeout for %s on %s at max_tokens=%s after %.2fs total elapsed.",
                        req.client_name,
                        candidate_model,
                        token_budget,
                        time.monotonic() - started_at,
                    )
                    continue
                except requests.RequestException as request_exc:
                    provider_error = f"Provider connection failed: {type(request_exc).__name__}"
                    logger.warning(
                        "Synthesis provider request failed for %s on %s at max_tokens=%s: %s",
                        req.client_name,
                        candidate_model,
                        token_budget,
                        request_exc,
                    )
                    continue

                if response.status_code != 200:
                    provider_error = f"Provider rejected the request: {response.status_code}"
                    logger.error(f"LLM API Error ({candidate_model}): {response.text}")
                    break

                payload = response.json()
                choice = payload.get("choices", [{}])[0] or {}
                finish_reason = str(choice.get("finish_reason") or choice.get("native_finish_reason") or "").strip().lower()
                content = str(choice.get("message", {}).get("content", "") or "").strip()
                try:
                    parsed = _extract_first_json_object(content)
                except Exception as parse_exc:
                    if finish_reason == "length" and token_budget < 2200:
                        logger.warning(
                            "Synthesis response truncated for %s on %s at max_tokens=%s; retrying with a larger budget.",
                            req.client_name,
                            candidate_model,
                            token_budget,
                        )
                        continue
                    logger.error(
                        "Synthesis parse failed for %s on %s at max_tokens=%s (finish_reason=%s): %s",
                        req.client_name,
                        candidate_model,
                        token_budget,
                        finish_reason or "unknown",
                        parse_exc,
                    )
                    provider_error = "Provider returned an incomplete synthesis payload."
                    break

                result = _normalize_synthesized_profile_result(parsed, synthesis_context)
                profile_data = result.get("data") or {}
                normalized_website = _normalize_public_source_url(req.website_url)
                normalized_social = _normalize_public_source_url(req.social_url)
                if normalized_website:
                    profile_data["website_url"] = normalized_website
                if normalized_social:
                    profile_data["social_url"] = normalized_social
                if isinstance(enrichments, dict) and enrichments.get("website_digest"):
                    profile_data["website_digest"] = enrichments["website_digest"]
                result["data"] = profile_data
                missing_fields = validate_synthesized_profile(profile_data)
                if missing_fields:
                    return {
                        "status": "missing",
                        "missing_fields": missing_fields,
                        "data": profile_data,
                        "source_warnings": source_warnings,
                    }
                result["source_warnings"] = source_warnings
                return result

        return {"status": "error", "reason": provider_error or "Provider returned no valid synthesis result."}
    except requests.Timeout:
        logger.error("Synthesis provider timed out before returning a profile.")
        return {"status": "error", "reason": "Jarvis could not finish synthesis before the provider timed out. The brief is still too slow on the current model path."}
    except Exception as e:
        logger.error(f"Failed to parse LLM JSON: {e}")
        return {"status": "error", "reason": "Failed to synthesize profile via AI. Check backend logs."}


async def _background_build_client_trend_dossier(client_id: str) -> None:
    safe_client_id = str(client_id or "").strip()
    if not safe_client_id:
        return
    try:
        logger.info("API | TREND DOSSIER | Background build queued for %s", safe_client_id)
        result = await asyncio.to_thread(build_client_trend_dossier, safe_client_id)
        if str((result or {}).get("status") or "").strip().lower() == "success":
            logger.info(
                "API | TREND DOSSIER | Background build completed for %s with %s recent signals",
                safe_client_id,
                result.get("total_recent_results") or result.get("source_count") or 0,
            )
        else:
            logger.warning("API | TREND DOSSIER | Background build returned non-success for %s: %s", safe_client_id, result)
    except Exception:
        logger.exception("API | TREND DOSSIER | Background build failed for %s", safe_client_id)


def _get_recent_client_captions(client_id: str, *, limit: int = 5, exclude_bundle_name: str | None = None) -> list[str]:
    bundles = list_client_drafts(client_id).get("bundles", {})
    entries: list[tuple[str, str]] = []
    for bundle_name, payload in bundles.items():
        if exclude_bundle_name and str(bundle_name).strip() == str(exclude_bundle_name).strip():
            continue
        if not isinstance(payload, dict):
            continue
        caption_text = str(payload.get("caption_text") or "").strip()
        if caption_text:
            entries.append((str(bundle_name).strip(), caption_text))
    return [caption for _bundle, caption in entries[-limit:]][::-1]

class ProfileSaveRequest(BaseModel):
    client_id: str
    phone_number: Optional[str] = None
    meta_access_token: str
    whatsapp_token: Optional[str] = None
    facebook_page_id: str
    instagram_account_id: str
    profile_json: dict

@app.post("/api/save-client-profile")
async def api_save_client_profile(req: ProfileSaveRequest):
    logger.info(f"API | SAVE | Writing profile for {req.client_id} to disk")

    profile = dict(req.profile_json or {})
    website_url = _normalize_public_source_url(profile.get("website_url"))
    social_url = _normalize_public_source_url(profile.get("social_url"))
    if website_url:
        profile["website_url"] = website_url
    if social_url:
        profile["social_url"] = social_url
    if website_url and not isinstance(profile.get("website_digest"), dict):
        website_digest = extract_website_digest(website_url)
        if isinstance(website_digest, dict) and str(website_digest.get("status") or "").strip() == "success":
            profile["website_digest"] = website_digest

    missing_fields = validate_synthesized_profile(profile)
    if missing_fields:
        return JSONResponse(status_code=400, content={"status": "missing", "missing_fields": missing_fields, "reason": "Client profile is missing critical brand intelligence."})

    full_data = req.model_dump(exclude_none=True)
    full_data["profile_json"] = profile
    store = get_client_store()
    saved_client = store.save_client(req.client_id, full_data)
    brand_data = build_brand_profile(req.client_id, profile)
    store.save_brand_profile(req.client_id, brand_data)
    
    logger.info(f"API | SAVE | Brand profile synced for {req.client_id} via {store.backend_name} backend")
        
    # 3. Relegate phone_map explicitly to simple phone->clientID lookups
    if req.phone_number:
        phone_map = load_phone_map()
        phone_map[req.phone_number] = req.client_id
        with open("phone_map.json", "w", encoding="utf-8") as f:
            json.dump(phone_map, f, indent=4)

    asyncio.create_task(_background_build_client_trend_dossier(req.client_id))
        
    return {
        "status": "success",
        "message": f"Client {req.client_id} securely registered. Brand profile persisted via {store.backend_name} backend.",
        "client": saved_client,
    }

def _ensure_instagram_compliant_image(file_bytes: bytearray, filename: str) -> tuple[bytes, str]:
    """
    Seamlessly format-converts PNG and WEBP arrays into Instagram-compliant JPEGs.
    Flattens alpha transparency onto a white background to prevent rejection.
    """
    extension = os.path.splitext(filename)[1].lower()
    if extension in {".mp4", ".mov", ".m4v", ".webm"}:
        return bytes(file_bytes), filename
        
    try:
        from PIL import Image
        with Image.open(BytesIO(file_bytes)) as img:
            needs_conversion = img.format != "JPEG" or img.mode in ("RGBA", "P", "LA")
            if not needs_conversion:
                return bytes(file_bytes), filename
                
            if img.mode in ("RGBA", "P", "LA"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                if img.mode in ("RGBA", "LA"):
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            else:
                img = img.convert("RGB")
                
            out = BytesIO()
            img.save(out, format="JPEG", quality=92)
            
            new_filename = os.path.splitext(filename)[0] + ".jpg"
            logger.info("IMAGE NORMALIZER | Converted %s to Instagram-compliant %s", filename, new_filename)
            return out.getvalue(), new_filename
    except ImportError:
        logger.warning("IMAGE NORMALIZER | Pillow not installed. Skipping automatic format normalization.")
    except Exception as e:
        logger.error("IMAGE NORMALIZER | Failed to normalize %s: %s", filename, e)
        
    return bytes(file_bytes), filename

@app.post("/api/upload-image")
async def api_upload_image(client_id: str = Form(...), file: UploadFile = File(...)):
    if not client_id:
        client_id = "unassigned"
    try:
        client_id = validate_client_id(client_id)
        filename = validate_filename(file.filename or "")
    except InputValidationError as e:
        return JSONResponse(status_code=400, content={"status": "error", "reason": str(e)})
    extension = os.path.splitext(filename)[1].lower()
    if extension not in SUPPORTED_EXTENSIONS:
        return JSONResponse(status_code=400, content={"status": "error", "reason": "Unsupported media type. Use JPG, PNG, WEBP, MP4, MOV, M4V, or WEBM."})

    file_bytes = bytearray()
    while True:
        chunk = await file.read(5 * 1024 * 1024)
        if not chunk:
            break
        file_bytes.extend(chunk)
        if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
            return JSONResponse(status_code=413, content={"status": "error", "reason": f"File exceeds maximum upload size of {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB."})
    
    final_bytes, final_filename = _ensure_instagram_compliant_image(file_bytes, filename)
    asset = save_uploaded_asset(client_id, final_filename, final_bytes)
    asset_preview = _asset_preview_payload(client_id, asset)
    
    stored_name = str(asset.get("filename") or final_filename).strip()
    file_path = f"assets/{client_id}/{stored_name}"
    return {"status": "success", "file_path": file_path, "asset": asset_preview}

@app.post("/api/upload-bulk")
async def api_upload_bulk(client_id: str = Form(...), files: List[UploadFile] = File(...)):
    if not client_id:
        client_id = "unassigned"
    try:
        client_id = validate_client_id(client_id)
    except InputValidationError as e:
        return JSONResponse(status_code=400, content={"status": "error", "reason": str(e)})

    uploaded_paths = []
    uploaded_assets = []
    try:
        for file in files:
            filename = validate_filename(file.filename or "")
            extension = os.path.splitext(filename)[1].lower()
            if extension not in SUPPORTED_EXTENSIONS:
                return JSONResponse(status_code=400, content={"status": "error", "reason": f"Unsupported media type for {filename}. Use JPG, PNG, WEBP, MP4, MOV, M4V, or WEBM."})
            
            file_bytes = bytearray()
            while True:
                chunk = await file.read(5 * 1024 * 1024)
                if not chunk:
                    break
                file_bytes.extend(chunk)
                if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
                    return JSONResponse(status_code=413, content={"status": "error", "reason": f"File '{filename}' exceeds maximum upload size of {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB."})
                    
            final_bytes, final_filename = _ensure_instagram_compliant_image(file_bytes, filename)
            asset = save_uploaded_asset(client_id, final_filename, final_bytes)
            asset_preview = _asset_preview_payload(client_id, asset)
            
            stored_name = str(asset.get("filename") or final_filename).strip()
            file_path = f"assets/{client_id}/{stored_name}"
            uploaded_paths.append(file_path)
            uploaded_assets.append(asset_preview)
    except InputValidationError as e:
        return JSONResponse(status_code=400, content={"status": "error", "reason": str(e)})
    except Exception as e:
        logger.exception("API | UPLOAD BULK | Failed while storing uploaded assets for %s", client_id)
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(e)})

    return {"status": "success", "uploaded_paths": uploaded_paths, "assets": uploaded_assets}

@app.get("/api/client/{client_id}")
async def api_get_client(client_id: str):
    """Read a single client's full profile from the active persistence backend."""
    payload = get_client_store().get_client(client_id)
    if not payload:
        return JSONResponse(status_code=404, content={"status": "error", "reason": f"Profile '{client_id}' was not found in the active data backend."})
    return payload

class ClientUpdateRequest(BaseModel):
    phone_number: Optional[str] = None
    meta_access_token: Optional[str] = None
    whatsapp_token: Optional[str] = None
    facebook_page_id: Optional[str] = None
    instagram_account_id: Optional[str] = None
    profile_json: Optional[dict] = None

@app.put("/api/client/{client_id}")
async def api_update_client(client_id: str, req: ClientUpdateRequest):
    """Partially update a client's credentials or brand profile."""
    store = get_client_store()
    data = store.get_client(client_id)
    if not data:
        return JSONResponse(status_code=404, content={"status": "error", "reason": f"Profile '{client_id}' not found."})
    
    updates = req.model_dump(exclude_none=True)
    
    # If profile_json is being updated, merge it into existing profile_json
    if "profile_json" in updates:
        existing_profile = data.get("profile_json", {})
        existing_profile.update(updates["profile_json"])
        data["profile_json"] = existing_profile
        del updates["profile_json"]
        updates["profile_json_merged"] = True
    
    data.update({k: v for k, v in updates.items() if k != "profile_json_merged"})

    if updates.get("profile_json_merged"):
        missing_fields = validate_synthesized_profile(data.get("profile_json", {}))
        if missing_fields:
            return JSONResponse(status_code=400, content={"status": "missing", "missing_fields": missing_fields, "reason": "Client profile is missing critical brand intelligence."})
    
    saved_client = store.save_client(client_id, data)
    
    # Sync phone_map if phone changed
    if req.phone_number:
        phone_map = load_phone_map()
        phone_map[req.phone_number] = client_id
        with open("phone_map.json", "w", encoding="utf-8") as f:
            json.dump(phone_map, f, indent=4)
    
    # If brand profile was updated, sync to brands/ for the Caption Service
    if updates.get("profile_json_merged"):
        profile = data.get("profile_json", {})
        brand_data = build_brand_profile(client_id, profile)
        store.save_brand_profile(client_id, brand_data)
        logger.info(f"API | UPDATE | Brand profile synced for {client_id} via {store.backend_name} backend")
    
    updated_keys = [k for k in req.model_dump(exclude_none=True).keys()]
    logger.info(f"API | UPDATE | Client {client_id} updated: {updated_keys}")
    return {
        "status": "success",
        "message": f"Updated {updated_keys} for {client_id}",
        "updated_fields": updated_keys,
        "client": saved_client,
    }


@app.delete("/api/client/{client_id}")
async def api_delete_client(client_id: str):
    vault_dir = f"assets/{client_id}"
    store = get_client_store()
    existing_profile = store.get_client(client_id)

    if not existing_profile:
        return JSONResponse(status_code=404, content={"status": "error", "reason": f"Client '{client_id}' was not found."})

    removed = {
        "client_id": client_id,
        "profile": False,
        "brand_profile": False,
        "vault": False,
        "phone_map_entries": 0,
        "schedule_jobs": 0,
        "pending_approvals": 0,
        "publish_runs": 0,
        "strategy_plans": 0,
        "drafts": 0,
        "reschedule_sessions": 0,
    }

    try:
        profile = existing_profile
        phone_number = str(profile.get("phone_number") or "").strip()

        store.delete_client(client_id)
        removed["profile"] = True
        removed["brand_profile"] = True

        def _remove_vault_and_assets() -> bool:
            removed_asset_count = delete_all_client_assets(client_id)
            if os.path.exists(vault_dir):
                shutil.rmtree(vault_dir, ignore_errors=True)
            return removed_asset_count > 0 or not os.path.exists(vault_dir)

        def _remove_phone_map_entries() -> int:
            phone_map = load_phone_map()
            filtered_map = {}
            removed_phone_entries = 0
            for phone, mapped_client in phone_map.items():
                if mapped_client == client_id or (phone_number and phone == phone_number):
                    removed_phone_entries += 1
                    continue
                filtered_map[phone] = mapped_client
            with open("phone_map.json", "w", encoding="utf-8") as f:
                json.dump(filtered_map, f, indent=4, ensure_ascii=False)
            return removed_phone_entries

        def _remove_reschedule_sessions() -> int:
            sessions = load_reschedule_sessions()
            filtered_sessions = {}
            removed_sessions = 0
            for phone, session in sessions.items():
                if str(session.get("client") or "") == client_id:
                    removed_sessions += 1
                    continue
                filtered_sessions[phone] = session
            if removed_sessions:
                save_reschedule_sessions(filtered_sessions)
            return removed_sessions

        (
            removed["vault"],
            removed["phone_map_entries"],
            removed["schedule_jobs"],
            removed["pending_approvals"],
            removed["publish_runs"],
            removed["strategy_plans"],
            removed["drafts"],
            removed["reschedule_sessions"],
        ) = await asyncio.gather(
            asyncio.to_thread(_remove_vault_and_assets),
            asyncio.to_thread(_remove_phone_map_entries),
            asyncio.to_thread(delete_client_schedule_jobs, client_id),
            asyncio.to_thread(delete_client_pending_approvals, client_id),
            asyncio.to_thread(delete_client_publish_runs, client_id),
            asyncio.to_thread(delete_client_strategy_plans, client_id),
            asyncio.to_thread(delete_client_drafts, client_id),
            asyncio.to_thread(_remove_reschedule_sessions),
        )

        logger.info(f"API | DELETE | Removed client {client_id}: {removed}")
        return {"status": "success", "removed": removed}
    except Exception as e:
        logger.error(f"API | DELETE | Failed to remove client {client_id}: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(e)})

@app.get("/api/vaults")
async def api_get_vaults():
    vaults = {}
    for cid in get_client_store().list_client_ids():
        vaults[cid] = count_client_assets(cid)
    return {"status": "success", "vaults": vaults}


def get_instagram_asset_warning(client_id: str, filename: str, media_kind: str, metadata: dict | None = None) -> tuple[bool, str]:
    cleaned_name = str(filename or "").strip()
    kind = str(media_kind or detect_media_kind(cleaned_name)).strip().lower()
    ext = os.path.splitext(cleaned_name.lower())[1]
    metadata = metadata or {}

    if kind == "video":
        if str(metadata.get("meta_safe_status") or "").strip().lower() == "safe":
            return True, ""
        if bool(metadata.get("needs_meta_repair")):
            reason = str(metadata.get("meta_repair_reason") or "").strip()
            return (
                False,
                reason or "Jarvis will repair this video for Instagram before publishing.",
            )
        if ext != ".mp4":
            return (
                False,
                "Instagram publishing in Jarvis currently supports MP4 video only. Jarvis will repair this video before publishing.",
            )
        return True, ""

    status = str(metadata.get("meta_safe_status") or "").strip().lower()
    if bool(metadata.get("normalized_for_meta")) or status == "safe":
        return True, ""

    if ext not in {".jpg", ".jpeg"}:
        return (
            False,
            "Instagram publishing in Jarvis currently supports JPG/JPEG images only. Jarvis should normalize this asset before posting.",
        )

    if status == "needs_repair" or bool(metadata.get("needs_meta_repair")):
        reason = str(metadata.get("meta_repair_reason") or "").strip()
        return False, reason or "Jarvis should normalize this image before Instagram publishing."

    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    if width > 0 and height > 0:
        ratio = width / height
        if ratio < 0.79 or ratio > 1.92:
            return False, f"Ratio {ratio:.2f} is outside Jarvis' Instagram-safe feed range."

    return True, ""


def _asset_preview_payload(client_id: str, asset: dict) -> dict:
    store = get_asset_store()
    filename = str(asset.get("filename") or "").strip()
    media_kind = str(asset.get("kind") or detect_media_kind(filename)).strip().lower()
    metadata = asset.get("metadata") or {}
    has_poster = bool(metadata.get("has_poster")) and media_kind == "video"
    encoded_client = quote(client_id, safe="")
    encoded_filename = "/".join(quote(part, safe="") for part in filename.split("/"))
    preview_path = f"/assets/{encoded_client}/{encoded_filename}"
    poster_path = f"{preview_path}.jpg" if has_poster else None
    version_token = str(
        metadata.get("preview_version")
        or asset.get("updated_at")
        or asset.get("created_at")
        or asset.get("asset_id")
        or int(time.time() * 1000)
    ).strip()

    def _with_version(url: str | None) -> str | None:
        raw = str(url or "").strip()
        if not raw:
            return None
        separator = "&" if "?" in raw else "?"
        return f"{raw}{separator}v={quote(version_token, safe='')}"

    full_url = _with_version(store.public_asset_url(client_id, filename)) or _with_version(preview_path)
    poster_full_url = (_with_version(store.public_poster_url(client_id, filename)) or _with_version(poster_path)) if has_poster else None
    thumb_url = _with_version(store.preview_asset_url(client_id, asset)) or full_url
    poster_thumb_url = (_with_version(store.preview_poster_url(client_id, asset)) or poster_full_url) if has_poster else None
    is_valid_ig, warning = get_instagram_asset_warning(client_id, filename, media_kind, metadata)
    storage_available = bool(asset.get("storage_path") or filename)
    return {
        "filename": filename,
        "kind": media_kind,
        "is_valid_ig": is_valid_ig,
        "warning": warning,
        "is_video": media_kind == "video",
        "can_repair_meta": media_kind == "video" and not is_valid_ig and storage_available,
        "storage_available": storage_available,
        "has_poster": has_poster,
        "width": int(metadata.get("width") or 0),
        "height": int(metadata.get("height") or 0),
        "mime_type": str(metadata.get("mime_type") or ""),
        "size_bytes": int(metadata.get("byte_size") or metadata.get("size_bytes") or 0),
        "version_token": version_token,
        "thumb_url": thumb_url,
        "full_url": full_url,
        "poster_thumb_url": poster_thumb_url,
        "poster_full_url": poster_full_url,
        "preview_url": thumb_url,
        "poster_url": poster_thumb_url,
    }


def _list_vault_asset_previews(client_id: str) -> list[dict]:
    files_with_meta = []
    for asset in list_client_assets(client_id):
        if str(asset.get("filename") or "").strip():
            files_with_meta.append(_asset_preview_payload(client_id, asset))
    return files_with_meta


def _annotate_vault_bundles(client_id: str, bundles: dict, schedule_payload: dict | None = None) -> dict:
    active_jobs, _ = split_schedule_views(schedule_payload or load_schedule("schedule.json"))
    scheduled_refs: dict[tuple[str, str], str] = {}
    asset_index: dict[str, dict] = {}
    try:
        for asset in list_client_assets(client_id):
            filename = str(asset.get("filename") or asset.get("original_filename") or "").strip()
            if filename:
                asset_index[filename] = asset
    except Exception:
        asset_index = {}

    for job in active_jobs:
        if str(job.get("client") or "").strip() != client_id:
            continue
        draft_name = str(job.get("draft_name") or "").strip()
        draft_id = str(job.get("draft_id") or "").strip()
        job_id = str(job.get("job_id") or "").strip()
        if draft_name:
            scheduled_refs[("name", draft_name)] = job_id
        if draft_id:
            scheduled_refs[("id", draft_id)] = job_id

    annotated_bundles = {}
    for draft_name, payload in (bundles or {}).items():
        bundle_payload = dict(payload or {})
        bundle_items = list(bundle_payload.get("items") or [])
        draft_id = str(bundle_payload.get("draft_id") or "").strip()
        locked_job_id = scheduled_refs.get(("name", draft_name)) or (scheduled_refs.get(("id", draft_id)) if draft_id else "")
        if locked_job_id:
            bundle_payload["scheduled_locked"] = True
            bundle_payload["scheduled_job_id"] = locked_job_id

        image_paths: list[str] = []
        video_paths: list[str] = []
        for item in bundle_items:
            filename = str((item or {}).get("filename") or "").strip()
            if not filename:
                continue
            media_kind = str((item or {}).get("kind") or bundle_payload.get("bundle_type") or "").strip().lower() or "image"
            managed_path = f"assets/{client_id}/{filename}"
            if media_kind == "video":
                video_paths.append(managed_path)
            else:
                image_paths.append(managed_path)

        preflight = publish_agent.preflight_media(image_paths, video_paths, instagram_enabled=True)
        instagram_error = str(preflight.get("instagram_error") or "").strip()

        ig_warnings: list[str] = [instagram_error] if instagram_error else []
        if not ig_warnings:
            seen_warnings: set[str] = set()
            for item in bundle_items:
                filename = str((item or {}).get("filename") or "").strip()
                if not filename:
                    continue
                asset = asset_index.get(filename) or {}
                metadata = (asset.get("metadata") or {}) if isinstance(asset, dict) else {}
                media_kind = str((item or {}).get("kind") or bundle_payload.get("bundle_type") or "").strip().lower() or "image"
                is_valid_ig, warning = get_instagram_asset_warning(client_id, filename, media_kind, metadata)
                if not is_valid_ig:
                    warning_text = str(warning or "").strip()
                    if warning_text and warning_text not in seen_warnings:
                        ig_warnings.append(warning_text)
                        seen_warnings.add(warning_text)

        bundle_payload["has_instagram_warning"] = bool(ig_warnings)
        bundle_payload["instagram_warnings"] = ig_warnings
        bundle_payload["instagram_warning"] = ig_warnings[0] if ig_warnings else ""
        annotated_bundles[draft_name] = bundle_payload
    return annotated_bundles


@app.get("/api/vault/{client_id}/assets")
async def api_get_vault_assets(client_id: str):
    files_with_meta = await asyncio.to_thread(_list_vault_asset_previews, client_id)
    return {"status": "success", "files": files_with_meta}


@app.get("/api/vault/{client_id}/drafts")
async def api_get_vault_drafts(client_id: str):
    try:
        draft_payload = await asyncio.to_thread(list_client_drafts, client_id)
        _store_cached_vault_drafts(client_id, draft_payload)
        try:
            schedule_payload = await asyncio.to_thread(load_schedule, "schedule.json")
        except Exception as schedule_exc:
            logger.warning(
                "VAULT | DRAFTS | Schedule annotation degraded for %s: %s",
                client_id,
                schedule_exc,
            )
            schedule_payload = []
        bundles = _annotate_vault_bundles(client_id, draft_payload.get("bundles", {}), schedule_payload)
        return {"status": "success", "bundles": bundles}
    except Exception as e:
        cached_drafts = _get_cached_vault_drafts(client_id)
        if cached_drafts is not None:
            logger.warning("VAULT | DRAFTS | Serving cached drafts for %s after live load failure: %s", client_id, e)
            return {
                "status": "success",
                "bundles": cached_drafts.get("bundles", {}),
                "cached": True,
                "stale_warning": "Jarvis served the last known draft state because the live draft service briefly degraded.",
            }
        logger.exception("VAULT | DRAFTS | Failed to load drafts for %s", client_id)
        return JSONResponse(status_code=500, content={"status": "error", "reason": f"Creative drafts unavailable right now: {str(e)}"})


@app.get("/api/vault/{client_id}")
async def api_get_vault_contents(client_id: str):
    try:
        assets_task = asyncio.to_thread(_list_vault_asset_previews, client_id)
        drafts_task = asyncio.to_thread(list_client_drafts, client_id)
        files_with_meta, draft_payload = await asyncio.gather(
            assets_task,
            drafts_task,
        )
        _store_cached_vault_drafts(client_id, draft_payload)
        try:
            schedule_payload = await asyncio.to_thread(load_schedule, "schedule.json")
        except Exception as schedule_exc:
            logger.warning(
                "VAULT | CONTENTS | Schedule annotation degraded for %s: %s",
                client_id,
                schedule_exc,
            )
            schedule_payload = []
        annotated_bundles = _annotate_vault_bundles(client_id, draft_payload.get("bundles", {}), schedule_payload)
        return {"status": "success", "files": files_with_meta, "bundles": annotated_bundles}
    except Exception as e:
        cached_drafts = _get_cached_vault_drafts(client_id)
        if cached_drafts is not None:
            logger.warning("VAULT | CONTENTS | Serving cached drafts for %s after live load failure: %s", client_id, e)
            try:
                files_with_meta = await asyncio.to_thread(_list_vault_asset_previews, client_id)
            except Exception:
                files_with_meta = []
            return {
                "status": "success",
                "files": files_with_meta,
                "bundles": cached_drafts.get("bundles", {}),
                "cached": True,
                "stale_warning": "Jarvis served the last known draft state because the live draft service briefly degraded.",
            }
        logger.exception("VAULT | CONTENTS | Failed to load contents for %s", client_id)
        return JSONResponse(status_code=500, content={"status": "error", "reason": f"Vault contents unavailable right now: {str(e)}"})

@app.delete("/api/vault/{client_id}/{filename}")
async def api_delete_vault_file(client_id: str, filename: str):
    try:
        client_id = validate_client_id(client_id)
        filename = validate_filename(filename)
    except InputValidationError as e:
        return JSONResponse(status_code=400, content={"status": "error", "reason": str(e)})
    try:
        if delete_client_asset(client_id, filename):
            return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(e)})
    return JSONResponse(status_code=404, content={"status": "error", "reason": "File not found"})


@app.post("/api/vault/{client_id}/{filename}/repair-meta")
async def api_repair_vault_file_for_meta(client_id: str, filename: str):
    try:
        client_id = validate_client_id(client_id)
        filename = validate_filename(filename)
    except InputValidationError as e:
        return JSONResponse(status_code=400, content={"status": "error", "reason": str(e)})
    try:
        asset = repair_client_asset_for_meta(client_id, filename)
        return {"status": "success", "asset": asset}
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={"status": "error", "reason": "File not found"})
    except Exception as e:
        message = str(e)
        if "Supabase Storage download failed: 400" in message and "Object not found" in message:
            message = "The asset record exists, but the underlying file is missing from Supabase Storage. Re-upload the file instead of repairing it."
        return JSONResponse(status_code=500, content={"status": "error", "reason": message})

class BundleRequest(BaseModel):
    bundle_name: str
    files: List[str]
    bundle_type: Optional[str] = None


class RenameBundleRequest(BaseModel):
    new_name: str


class ManualCaptionRequest(BaseModel):
    caption_text: str
    hashtags: Optional[List[str]] = None
    seo_keyword_used: Optional[str] = None
    caption_mode: Optional[str] = "manual"


class GenerateCaptionRequest(BaseModel):
    topic: Optional[str] = None
    caption_mode: Optional[str] = "ai"

@app.post("/api/vault/{client_id}/bundles")
async def api_create_bundle(client_id: str, req: BundleRequest):
    items = []
    for filename in req.files:
        cleaned = str(filename).strip()
        if not cleaned:
            continue
        kind = detect_media_kind(cleaned)
        items.append({"filename": cleaned, "kind": kind})

    if not items:
        return JSONResponse(status_code=400, content={"status": "error", "reason": "A bundle needs at least one media file."})

    media_kinds = {item["kind"] for item in items}
    if len(media_kinds) > 1:
        return JSONResponse(status_code=400, content={"status": "error", "reason": "Mixed image/video bundles are not supported yet. Queue either images or a single video."})
    if "video" in media_kinds and len(items) > 1:
        return JSONResponse(status_code=400, content={"status": "error", "reason": "Video bundles currently support a single video only."})

    inferred_type = "video" if "video" in media_kinds else ("image_carousel" if len(items) > 1 else "image_single")
    bundle_type = str(req.bundle_type or inferred_type).strip().lower()

    saved = save_draft_payload(client_id, req.bundle_name, {
        "bundle_type": bundle_type,
        "items": items,
        "caption_mode": "ai",
        "caption_status": "empty",
        "caption_text": "",
        "hashtags": [],
        "seo_keyword_used": "",
        "topic_hint": "",
    })

    return {
        "status": "success",
        "message": f"Saved creative draft {req.bundle_name}",
        "draft": saved,
    }

@app.delete("/api/vault/{client_id}/bundles/{bundle_name}")
async def api_delete_bundle(client_id: str, bundle_name: str):
    if delete_draft_payload(client_id, bundle_name):
        return {"status": "success", "message": f"Deleted draft {bundle_name}"}
    return {"status": "error", "message": "Draft not found"}


@app.put("/api/vault/{client_id}/bundles/{bundle_name}/rename")
async def api_rename_bundle(client_id: str, bundle_name: str, req: RenameBundleRequest):
    new_name = str(req.new_name or "").strip()
    if not new_name:
        return JSONResponse(status_code=400, content={"status": "error", "reason": "Draft name cannot be empty."})

    try:
        rename_draft_payload(client_id, bundle_name, new_name)
    except Exception as exc:
        reason = str(exc)
        status_code = 404 if "not found" in reason.lower() else 400
        return JSONResponse(status_code=status_code, content={"status": "error", "reason": reason})
    return {"status": "success", "old_name": bundle_name, "new_name": new_name, "bundles": list_client_drafts(client_id).get("bundles", {})}


@app.post("/api/vault/{client_id}/bundles/{bundle_name}/generate-caption")
async def api_generate_draft_caption(client_id: str, bundle_name: str, req: GenerateCaptionRequest):
    draft = get_draft_payload(client_id, bundle_name)
    if not draft:
        return JSONResponse(status_code=404, content={"status": "error", "reason": "Draft not found"})

    topic = str(req.topic or draft.get("topic_hint") or "").strip()
    if not topic:
        return JSONResponse(status_code=400, content={"status": "error", "reason": "Add a campaign angle first. Example: push the late-night burger combo, spotlight the reel energy, or highlight the new offer."})
    if topic.lower() == str(bundle_name).strip().lower():
        return JSONResponse(status_code=400, content={"status": "error", "reason": "Make the campaign angle more specific than the draft name. Tell Jarvis what this post should push, highlight, or sell."})
    media_type = str(draft.get("bundle_type") or "image_single").strip().lower()

    try:
        from caption_agent import generate_caption_payload

        recent_captions = await asyncio.to_thread(
            _get_recent_client_captions,
            client_id,
            limit=5,
            exclude_bundle_name=bundle_name,
        )
        result = await asyncio.to_thread(generate_caption_payload, client_id, topic, media_type, recent_captions)
        if result.get("status") != "success":
            return JSONResponse(
                status_code=400,
                content={"status": "error", "reason": result.get("caption") or "Caption generation failed."},
            )

        draft["caption_mode"] = str(req.caption_mode or "ai").strip().lower() or "ai"
        draft["caption_status"] = "ready"
        draft["caption_text"] = str(result.get("caption") or "").strip()
        draft["hashtags"] = [str(tag).strip() for tag in result.get("hashtags", []) if str(tag).strip()]
        draft["seo_keyword_used"] = str(result.get("seo_keyword_used") or "").strip()
        draft["topic_hint"] = topic
        saved = save_draft_payload(client_id, bundle_name, draft)
        return {"status": "success", "draft": saved, "generated": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(e)})


@app.put("/api/vault/{client_id}/bundles/{bundle_name}/caption")
async def api_save_manual_caption(client_id: str, bundle_name: str, req: ManualCaptionRequest):
    draft = get_draft_payload(client_id, bundle_name)
    if not draft:
        return JSONResponse(status_code=404, content={"status": "error", "reason": "Draft not found"})

    caption_text = str(req.caption_text or "").strip()
    if not caption_text:
        return JSONResponse(status_code=400, content={"status": "error", "reason": "Caption text cannot be empty."})

    hashtags = req.hashtags or []
    if not isinstance(hashtags, list):
        hashtags = []

    draft["caption_mode"] = str(req.caption_mode or "manual").strip().lower() or "manual"
    draft["caption_status"] = "ready"
    draft["caption_text"] = caption_text
    draft["hashtags"] = [str(tag).strip() for tag in hashtags if str(tag).strip()]
    draft["seo_keyword_used"] = str(req.seo_keyword_used or "").strip()
    draft["topic_hint"] = sanitize_topic_hint(bundle_name, draft.get("topic_hint"))
    saved = save_draft_payload(client_id, bundle_name, draft)
    return {"status": "success", "draft": saved}

class TriggerRequest(BaseModel):
    client_id: str
    topic: str
    image_path: Optional[str] = None

class DeliveryMarkRequest(BaseModel):
    job_id: str

async def background_pipeline(client_id: str, topic: str, image_path: Optional[str], exec_id: str):
    cmd = [sys.executable, "pipeline.py", "--client", client_id, "--topic", topic]
    if image_path:
        cmd.extend(["--image", image_path])
        
    # We append to pipeline_stream.log for real-time terminal stdout mirroring (Endpoint 5)
    with open("pipeline_stream.log", "a", encoding="utf-8") as f:
        f.write(f"SYSTEM | INFO | --- PIPELINE EXECUTION STARTED [{exec_id}] ---\n")
        f.flush()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        
        full_output = []
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            decoded = line.decode('utf-8', errors='replace')
            full_output.append(decoded)
            f.write(decoded)
            f.flush()
            
        await proc.wait()
        f.write(f"SYSTEM | INFO | --- PIPELINE EXECUTION COMPLETED [{exec_id}] ---\n")
        f.flush()
        
    return proc.returncode == 0, "".join(full_output)

@app.post("/api/trigger-pipeline")
async def api_trigger_pipeline(req: TriggerRequest):
    logger.info(f"API | TRIGGER | Starting pipeline for {req.client_id} -> '{req.topic}'")
    
    exec_id = f"uuid-{uuid.uuid4().hex[:8]}"
    
    # Await execution to provide immediate HTTP UI feedback (Phase 0)
    success, output = await background_pipeline(req.client_id, req.topic, req.image_path, exec_id)
    
    if success:
        return {"status": "success", "execution_id": exec_id, "output": output}
    else:
        # Provide the tail end of stdout to isolate the crash
        short_reason = output[-300:] if len(output) > 300 else output
        return {"status": "error", "execution_id": exec_id, "reason": short_reason}

@app.get("/api/schedule")
async def api_get_schedule():
    try:
        jobs = load_schedule("schedule.json")
        active, history = split_schedule_views(jobs)
        return {
            "status": "success",
            "schedule": active,
            "history": history,
            "counts": {
                "active": len(active),
                "history": len(history),
                "total": len(jobs),
            },
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}

@app.delete("/api/schedule/clear-delivered")
async def api_clear_delivered_schedule():
    try:
        cleared, _ = cleanup_delivered_jobs("schedule.json")
        return {"status": "success", "cleared": cleared}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(e)})

@app.delete("/api/schedule/job/{job_id}")
async def api_delete_schedule_job(job_id: str):
    try:
        removed, _ = remove_job(job_id, "schedule.json")
        if not removed:
            return {"status": "error", "reason": "Job not found."}
        return {"status": "success", "removed": removed}
    except Exception as e:
        return {"status": "error", "reason": str(e)}

@app.delete("/api/schedule/{index}")
async def api_delete_schedule(index: int):
    try:
        data = load_schedule("schedule.json")
        if index < 0 or index >= len(data):
            return {"status": "error", "reason": "Invalid index."}
        removed = data[index]
        remove_job(str(removed.get("job_id") or ""), "schedule.json")
        return {"status": "success", "removed": removed}
    except Exception as e:
        return {"status": "error", "reason": str(e)}

@app.post("/api/schedule/mark-delivered")
async def api_mark_delivered(req: DeliveryMarkRequest):
    matched_rule, _ = mark_job_delivered(req.job_id, "schedule.json")
    if not matched_rule:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "reason": f"Job '{req.job_id}' not found."},
        )

    if get_asset_store().backend_name == "json":
        media_paths = list(matched_rule.get("images", [])) + list(matched_rule.get("videos", []))
        for media_path in media_paths:
            if os.path.exists(media_path):
                filename = os.path.basename(media_path)
                delivered_dir = os.path.join(os.path.dirname(media_path), "delivered")
                os.makedirs(delivered_dir, exist_ok=True)
                new_path = os.path.join(delivered_dir, filename)
                try:
                    shutil.move(media_path, new_path)
                except Exception as e:
                    logger.error(f"Failed to move delivered media {media_path}: {e}")

    bundle_name = str(matched_rule.get("draft_name") or "").strip()
    if not bundle_name:
        bundle_name = matched_rule.get("topic", "").replace("Scheduled ", "").replace("Auto-post for ", "")
    if bundle_name:
        try:
            delete_draft_payload(str(matched_rule.get("client") or "").strip(), bundle_name)
        except Exception as e:
            logger.error(f"Failed to clear bundle from queue: {e}")

    return {"status": "success", "job": matched_rule}


class DeliveryFailureRequest(BaseModel):
    job_id: str
    reason: Optional[str] = None


@app.post("/api/schedule/mark-failed")
async def api_mark_failed(req: DeliveryFailureRequest):
    matched_rule, _ = mark_job_failed(req.job_id, "schedule.json", reason=req.reason)
    if not matched_rule:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "reason": f"Job '{req.job_id}' not found."},
        )
    return {"status": "success", "job": matched_rule}

class DraftRefPayload(BaseModel):
    client_id: str
    draft_name: str
    draft_id: str
    visible_token: Optional[str] = None


class OrchestratorRequest(BaseModel):
    prompt: str
    draft_refs: Optional[List[DraftRefPayload]] = None


class JarvisBatchItemPayload(BaseModel):
    client_id: str
    draft_name: str
    draft_id: Optional[str] = None
    platforms: Optional[List[str]] = None


class JarvisBatchSchedulePayload(BaseModel):
    scheduled_date: Optional[str] = None
    time: Optional[str] = None


class JarvisBatchTaskPayload(BaseModel):
    client_id: str
    draft_name: str
    draft_id: Optional[str] = None
    action: str
    scheduled_date: Optional[str] = None
    time: Optional[str] = None
    platforms: Optional[List[str]] = None
    source_text: Optional[str] = None
    status: Optional[str] = None
    warning: Optional[str] = None


class JarvisBatchPlanRequest(BaseModel):
    action: Optional[str] = None
    items: Optional[List[JarvisBatchItemPayload]] = None
    schedule: Optional[JarvisBatchSchedulePayload] = None
    tasks: Optional[List[JarvisBatchTaskPayload]] = None


class JarvisBatchRunRequest(BaseModel):
    plan: dict


class StrategyPlanRequest(BaseModel):
    client_id: str
    window: str = "next_7_days"
    goal: Optional[str] = None
    campaign_context: Optional[str] = None


class StrategyMaterializeRequest(BaseModel):
    item_ids: Optional[List[str]] = None


@app.post("/api/orchestrator-chat")
async def api_orchestrator_chat(req: OrchestratorRequest):
    try:
        from orchestrator_agent import parse_multi_clause_release_request, run_orchestrator
        from strategy_agent import prompt_requests_strategy
        draft_refs = []
        if req.draft_refs:
            for ref in req.draft_refs:
                client_id = str(ref.client_id or "").strip()
                draft_id = str(ref.draft_id or "").strip()
                draft_name = str(ref.draft_name or "").strip()
                if client_id and draft_id:
                    draft_refs.append({"client_id": client_id, "draft_id": draft_id, "draft_name": draft_name})
        if not draft_refs:
            draft_refs = extract_smart_draft_refs(req.prompt)
        normalized_prompt = normalize_prompt_date_typos(req.prompt)
        normalized_prompt = normalize_prompt_with_known_draft_refs(normalized_prompt, draft_refs) if draft_refs else normalize_smart_draft_prompt(normalized_prompt)
        logger.info(f"API | ORCHESTRATOR | Received natural language operation constraint: {req.prompt}")
        if normalized_prompt != req.prompt:
            logger.info(f"API | ORCHESTRATOR | Normalized prompt for scheduling clarity: {normalized_prompt}")

        is_strategy_request = prompt_requests_strategy(normalized_prompt)
        parsed_release = None if is_strategy_request else parse_multi_clause_release_request(normalized_prompt, draft_refs)
        if parsed_release:
            parsed_tasks = list(parsed_release.get("tasks") or [])
            ready_tasks = [
                task for task in parsed_tasks
                if str(task.get("status") or "").strip().lower() == "ready"
            ]
            single_immediate_ready = (
                len(parsed_tasks) == 1
                and len(ready_tasks) == 1
                and str(ready_tasks[0].get("action") or "").strip().lower() == "post_now"
                and not parsed_release.get("requires_confirmation")
            )
            if not single_immediate_ready:
                plan = _build_orchestrator_batch_plan(tasks=parsed_tasks)
                return {
                    "status": "success",
                    "reply": _summarize_orchestrator_task_preview(plan),
                    "task_preview": plan,
                    "parser_warnings": list(parsed_release.get("warnings") or []),
                    "requires_confirmation": True,
                }

        orchestrator_result = await asyncio.to_thread(run_orchestrator, normalized_prompt, draft_refs, req.prompt)
        if isinstance(orchestrator_result, dict):
            reply = str(orchestrator_result.get("reply") or orchestrator_result.get("message") or "").strip()
            action = orchestrator_result.get("action")
            if isinstance(action, dict) and action.get("type") == "approval_request":
                approval_id = str(action.get("approval_id") or "").strip()
                if approval_id:
                    job = get_pending_approval(approval_id)
                    if job:
                        action = dict(action)
                        action["job"] = job
                        action["approval_routing"] = get_approval_routing_mode()
            if isinstance(action, dict) and action.get("type") == "approval_request":
                reply = str(action.get("message") or reply).strip()
            payload = {"status": "success", "reply": reply}
            if action:
                payload["action"] = action
            if orchestrator_result.get("task_preview"):
                payload["task_preview"] = orchestrator_result.get("task_preview")
            if orchestrator_result.get("draft_refs"):
                payload["draft_refs"] = orchestrator_result.get("draft_refs")
            if orchestrator_result.get("parser_warnings"):
                payload["parser_warnings"] = orchestrator_result.get("parser_warnings")
            if orchestrator_result.get("requires_confirmation") is not None:
                payload["requires_confirmation"] = bool(orchestrator_result.get("requires_confirmation"))
            if orchestrator_result.get("strategy_plan"):
                payload["strategy_plan"] = orchestrator_result.get("strategy_plan")
            return payload
        return {"status": "success", "reply": str(orchestrator_result or "")}
    except Exception as e:
        logger.error(f"Orchestrator routing failure: {e}")
        return {"status": "error", "reason": str(e)}


@app.post("/api/orchestrator/plan")
async def api_orchestrator_plan(req: JarvisBatchPlanRequest):
    try:
        if req.tasks:
            plan = _build_orchestrator_batch_plan(tasks=[task.model_dump() for task in req.tasks])
        else:
            plan = _build_orchestrator_batch_plan(
                req.action,
                [item.model_dump() for item in (req.items or [])],
                req.schedule.model_dump() if req.schedule else None,
            )
        return {"status": "success", "plan": plan}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Mission Control plan failure: {exc}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(exc)})


@app.post("/api/orchestrator/run")
async def api_orchestrator_run(req: JarvisBatchRunRequest, request: Request):
    try:
        raw_plan = dict(req.plan or {})
        if raw_plan.get("tasks"):
            plan = _build_orchestrator_batch_plan(tasks=list(raw_plan.get("tasks") or []))
        else:
            action = str(raw_plan.get("action") or "").strip().lower()
            raw_items = list(raw_plan.get("items") or [])
            raw_schedule = dict(raw_plan.get("schedule") or {})
            plan = _build_orchestrator_batch_plan(action, raw_items, raw_schedule)
        seeded_items = []
        for raw_item in (plan.get("tasks") or plan.get("items") or []):
            item = dict(raw_item)
            if str(item.get("status") or "").strip().lower() != "blocked":
                action_name = str(item.get("action") or plan.get("action") or "").strip().lower()
                item["status"] = "queued"
                item["phase"] = "Queued"
                if action_name == "post_now":
                    item["message"] = "Queued for publish."
                elif action_name == "send_for_approval":
                    item["message"] = "Queued for approval routing."
                else:
                    item["message"] = "Queued for scheduling."
            seeded_items.append(item)
        run_id = str(uuid.uuid4())
        run = {
            "run_id": run_id,
            "action": plan["action"],
            "status": "queued",
            "created_at": _utc_now_iso(),
            "schedule": dict(plan.get("schedule") or {}),
            "approval_routing_override": str(raw_plan.get("approval_routing_override") or "").strip(),
            "warnings": list(plan.get("warnings") or []),
            "totals": dict(plan.get("totals") or {}),
            "items": seeded_items,
            "request_id": _get_request_id(request),
        }
        run = _save_orchestrator_run(run)
        _audit_event(
            "orchestrator.run_queued",
            {
                "run_id": run_id,
                "action": run.get("action"),
                "item_count": len(run.get("items") or []),
            },
            request=request,
            actor=_get_rate_limit_identity(request),
        )
        asyncio.create_task(_execute_orchestrator_batch_run(run_id))
        return {"status": "success", "run_id": run_id, "run": run}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Mission Control run failure: {exc}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(exc)})


@app.get("/api/orchestrator/runs/{run_id}")
async def api_orchestrator_run_status(run_id: str):
    run = _load_orchestrator_run(str(run_id).strip())
    if not run:
        raise HTTPException(status_code=404, detail="Mission Control run not found.")
    return {"status": "success", "run": run}


@app.get("/api/strategy/plans")
async def api_list_strategy_plans(client_id: str | None = None):
    try:
        plans = list_strategy_plans(client_id=str(client_id or "").strip() or None)
        return {"status": "success", "plans": plans}
    except Exception as exc:
        logger.error("Strategy plan listing failure: %s", exc, exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(exc)})


@app.delete("/api/strategy/plans")
async def api_delete_strategy_plans(client_id: str):
    try:
        normalized_client = str(client_id or "").strip()
        if not normalized_client:
            return JSONResponse(status_code=400, content={"status": "error", "reason": "Client id is required."})
        removed = delete_client_strategy_plans(normalized_client)
        return {"status": "success", "removed": removed, "client_id": normalized_client}
    except Exception as exc:
        logger.error("Strategy client plan deletion failure: %s", exc, exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(exc)})


@app.post("/api/strategy/plans")
async def api_create_strategy_plan(req: StrategyPlanRequest, request: Request):
    try:
        from strategy_agent import run_strategy_agent

        plan = await asyncio.to_thread(
            run_strategy_agent,
            req.client_id,
            req.window,
            str(req.goal or "").strip(),
            str(req.campaign_context or "").strip(),
            " ".join(part for part in [str(req.goal or "").strip(), str(req.campaign_context or "").strip()] if part),
        )
        if isinstance(plan, dict) and plan.get("error"):
            return JSONResponse(status_code=400, content={"status": "error", "reason": str(plan.get("error") or "").strip()})
        _audit_event(
            "strategy.plan_created",
            {
                "plan_id": str(plan.get("plan_id") or "").strip(),
                "client_id": str(plan.get("client_id") or "").strip(),
                "window": str(plan.get("window") or "").strip(),
                "item_count": len(plan.get("items") or []),
            },
            request=request,
            actor=_get_rate_limit_identity(request),
        )
        return {"status": "success", "plan": plan}
    except Exception as exc:
        logger.error("Strategy plan creation failure: %s", exc, exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(exc)})


@app.delete("/api/strategy/plans/{plan_id}")
async def api_delete_strategy_plan(plan_id: str):
    try:
        normalized_plan = str(plan_id or "").strip()
        if not normalized_plan:
            return JSONResponse(status_code=400, content={"status": "error", "reason": "Plan id is required."})
        removed = delete_strategy_plan(normalized_plan)
        if not removed:
            return JSONResponse(status_code=404, content={"status": "error", "reason": "Strategy plan not found."})
        return {"status": "success", "removed": 1, "plan_id": normalized_plan}
    except Exception as exc:
        logger.error("Strategy plan deletion failure: %s", exc, exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(exc)})


@app.post("/api/strategy/plans/{plan_id}/materialize")
async def api_materialize_strategy_plan(plan_id: str, req: StrategyMaterializeRequest, request: Request):
    try:
        from strategy_agent import materialize_strategy_plan

        existing = get_strategy_plan(str(plan_id).strip())
        if not existing:
            return JSONResponse(status_code=404, content={"status": "error", "reason": "Strategy plan not found."})
        updated = await asyncio.to_thread(materialize_strategy_plan, str(plan_id).strip(), list(req.item_ids or []))
        if isinstance(updated, dict) and updated.get("error"):
            return JSONResponse(status_code=400, content={"status": "error", "reason": str(updated.get("error") or "").strip()})
        _audit_event(
            "strategy.plan_materialized",
            {
                "plan_id": str(updated.get("plan_id") or plan_id).strip(),
                "client_id": str(updated.get("client_id") or "").strip(),
                "item_count": len(updated.get("items") or []),
            },
            request=request,
            actor=_get_rate_limit_identity(request),
        )
        return {"status": "success", "plan": updated}
    except Exception as exc:
        logger.error("Strategy plan materialization failure: %s", exc, exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(exc)})


@app.get("/api/research/smoke")
async def api_research_smoke(query: str, max_results: int = 5, recency_days: int = 30):
    try:
        pack = search_recent(query, max_results=max_results, recency_days=recency_days)
        results = list(pack.get("results") or [])
        published_dates = [str(item.get("published_at") or "").strip() for item in results if str(item.get("published_at") or "").strip()]
        return {
            "status": "success",
            "provider": pack.get("provider") or "unavailable",
            "recent_count": len(results),
            "insufficient_recent_sources": bool(pack.get("insufficient_recent_sources")),
            "date_range": {
                "newest": max(published_dates) if published_dates else "",
                "oldest": min(published_dates) if published_dates else "",
            },
            "pack": pack,
        }
    except Exception as exc:
        logger.error("Research smoke failure: %s", exc, exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(exc)})


@app.get("/api/stream-logs")
async def stream_logs(request: Request):
    """
    SSE stream capturing raw terminal stdout natively from pipeline_stream.log 
    so frontend types out agent thoughts.
    """
    MAX_STREAM_SECONDS = 300  # 5 minute max connection lifetime

    async def log_generator():
        # Ensure file exists safely
        if not os.path.exists("pipeline_stream.log"):
            with open("pipeline_stream.log", "w") as f:
                pass
        start_time = time.time()
        try:
            with open("pipeline_stream.log", "r", encoding="utf-8") as f:
                f.seek(0, 2)
                while True:
                    # Check for client disconnect
                    if await request.is_disconnected():
                        break
                    # Check max connection lifetime
                    if time.time() - start_time > MAX_STREAM_SECONDS:
                        yield f"data: {{ \"message\": \"Stream timeout reached. Reconnect to continue.\" }}\n\n"
                        break
                    line = f.readline()
                    if line:
                        yield f"data: {{ \"message\": {json.dumps(line.strip())} }}\n\n"
                    else:
                        await asyncio.sleep(0.4)
        except Exception as e:
            yield f"data: {{ \"message\": \"Log stream unavailable: {str(e)}\" }}\n\n"

    return StreamingResponse(log_generator(), media_type="text/event-stream")

@app.get("/api/clients")
async def api_get_clients():
    """
    Returns a unified layout of all active CRM profiles securely registered in the system.
    """
    clients = get_client_store().list_client_ids()
    return {"status": "success", "clients": clients}


@app.get("/api/clients/full")
async def api_get_clients_full():
    """
    Returns the full saved client payloads so the Clients workspace can hydrate
    cards in one pass instead of making multiple per-client round trips.
    """
    store = get_client_store()
    clients = store.list_clients()
    return {"status": "success", "clients": clients}


@app.get("/api/export-state")
async def api_export_state():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    store = get_client_store()
    clients_payload = {}
    brands_payload = {}
    vault_manifest = {}

    for client_id in store.list_client_ids():
        clients_payload[client_id] = store.get_client(client_id) or {}
        brands_payload[client_id] = store.get_brand_profile(client_id) or {}

        files = sorted(asset["filename"] for asset in list_client_assets(client_id))
        vault_manifest[client_id] = {
            "files": files,
            "queue": list_client_drafts(client_id),
        }

    # Redact sensitive tokens from export payload (C-08)
    safe_agency_config = dict(get_agency_config())
    if "whatsapp_access_token" in safe_agency_config:
        safe_agency_config["whatsapp_access_token"] = "[REDACTED]"
    safe_clients = {}
    for cid, cdata in clients_payload.items():
        safe_client = dict(cdata) if isinstance(cdata, dict) else {}
        if "meta_access_token" in safe_client:
            safe_client["meta_access_token"] = "[REDACTED]"
        safe_clients[cid] = safe_client

    payload = {
        "status": "success",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_backend": store.backend_name,
        "agency_config": safe_agency_config,
        "phone_map": load_phone_map(),
        "schedule": load_schedule("schedule.json"),
        "pending_approvals": list_live_pending_approvals(),
        "publish_runs": list_publish_runs(),
        "strategy_plans": list_strategy_plans(),
        "reschedule_sessions": load_reschedule_sessions(),
        "clients": safe_clients,
        "brands": brands_payload,
        "vault_manifest": vault_manifest,
    }
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="jarvis-backup-{timestamp}.json"'},
    )

@app.get("/api/agency/config")
async def api_get_agency_config():
    config = dict(get_agency_config())
    config["whatsapp_access_token"] = ""
    config["whatsapp_access_token_configured"] = bool(str(os.getenv("WHATSAPP_TOKEN") or "").strip())
    config["whatsapp_phone_id_configured"] = bool(str(os.getenv("WHATSAPP_TEST_PHONE_NUMBER_ID") or "").strip())
    config["whatsapp_runtime_managed_by"] = "env"
    return config

class AgencyConfigRequest(BaseModel):
    owner_phone: str
    whatsapp_access_token: Optional[str] = None
    approval_routing: Optional[str] = "desktop_first"

@app.post("/api/agency/config")
async def api_post_agency_config(req: AgencyConfigRequest):
    config = {
        "owner_phone": req.owner_phone.strip(),
        "approval_routing": normalize_approval_routing_mode(req.approval_routing),
    }
    with open("agency_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    return {
        "status": "success",
        "detail": "Agency phone and approval routing saved. WhatsApp runtime secrets are managed through environment variables.",
    }


class ApprovalMoveRequest(BaseModel):
    release_window: str


def _approval_requires_whatsapp_owner_lane(approval_id: str) -> bool:
    job = get_pending_approval(approval_id)
    if not job:
        return False
    return normalize_approval_routing_mode(job.get("approval_routing")) == "whatsapp_only"


@app.get("/api/approvals/pending")
async def api_get_pending_approvals():
    approvals = list_live_pending_approvals()
    sorted_approvals = sorted(
        approvals,
        key=lambda item: (
            str(item.get("scheduled_date") or "9999-12-31"),
            str(item.get("time") or "99:99 PM"),
            str(item.get("approval_id") or ""),
        ),
    )
    return {
        "status": "success",
        "approval_routing": get_approval_routing_mode(),
        "approvals": sorted_approvals,
    }


@app.post("/api/approvals/{approval_id}/approve")
async def api_approve_pending_approval(approval_id: str, request: Request):
    if _approval_requires_whatsapp_owner_lane(approval_id):
        return {
            "status": "error",
            "reason": "This approval is locked to the WhatsApp owner lane. The owner must approve it from WhatsApp before Jarvis schedules it.",
            "code": "whatsapp_only_locked",
        }
    result = approve_pending_approval(approval_id)
    _audit_event(
        "approval.approve",
        {"approval_id": approval_id, "status": result.get("status"), "reason": result.get("reason")},
        request=request,
        actor=_get_rate_limit_identity(request),
    )
    return result


@app.post("/api/approvals/{approval_id}/reject")
async def api_reject_pending_approval(approval_id: str, request: Request):
    if _approval_requires_whatsapp_owner_lane(approval_id):
        return {
            "status": "error",
            "reason": "This approval is locked to the WhatsApp owner lane. The owner must decline it from WhatsApp.",
            "code": "whatsapp_only_locked",
        }
    result = reject_pending_approval(approval_id)
    _audit_event(
        "approval.reject",
        {"approval_id": approval_id, "status": result.get("status"), "reason": result.get("reason")},
        request=request,
        actor=_get_rate_limit_identity(request),
    )
    return result


@app.post("/api/approvals/discard-all")
async def api_discard_all_pending_approvals(request: Request):
    result = discard_all_pending_approvals()
    _audit_event(
        "approval.discard_all",
        {"status": result.get("status"), "discarded_count": result.get("discarded_count")},
        request=request,
        actor=_get_rate_limit_identity(request),
    )
    return result


@app.post("/api/approvals/{approval_id}/move")
async def api_move_pending_approval(approval_id: str, req: ApprovalMoveRequest, request: Request):
    if _approval_requires_whatsapp_owner_lane(approval_id):
        return {
            "status": "error",
            "reason": "This approval is locked to the WhatsApp owner lane. The owner must change the release time from WhatsApp.",
            "code": "whatsapp_only_locked",
        }
    reopen_whatsapp = get_approval_routing_mode() in {"desktop_and_whatsapp", "whatsapp_only"}
    result = move_pending_approval(approval_id, req.release_window, reopen_whatsapp=reopen_whatsapp)
    _audit_event(
        "approval.move",
        {
            "approval_id": approval_id,
            "release_window": req.release_window,
            "status": result.get("status"),
            "reason": result.get("reason"),
            "reopen_whatsapp": reopen_whatsapp,
        },
        request=request,
        actor=_get_rate_limit_identity(request),
    )
    return result


@app.post("/api/approvals/{approval_id}/send-whatsapp")
async def api_send_pending_approval_to_whatsapp(approval_id: str, request: Request):
    result = send_pending_approval_to_whatsapp(approval_id)
    _audit_event(
        "approval.send_whatsapp",
        {"approval_id": approval_id, "success": bool(result.get("success")), "error": result.get("error")},
        request=request,
        actor=_get_rate_limit_identity(request),
    )
    if result.get("success"):
        return {"status": "success"}
    return {"status": "error", "reason": result.get("error", "Failed to send WhatsApp approval card.")}
