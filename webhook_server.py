import os
import sys
import json
import logging
import requests
import io
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import PlainTextResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio
import shutil
import uuid
import re
import subprocess
from typing import Optional, List
from pypdf import PdfReader
from docx import Document

from schedule_utils import format_display_date, normalize_prompt_date_typos, parse_iso_date, resolve_date_phrase
from queue_store import (
    SUPPORTED_EXTENSIONS,
    VIDEO_EXTENSIONS,
    detect_media_kind,
    get_bundle_payload,
    load_queue_data,
    save_queue_data,
    sanitize_topic_hint,
)
from whatsapp_agent import run_whatsapp_agent, run_triage_agent
from schedule_store import (
    add_scheduled_job,
    cleanup_delivered_jobs,
    load_schedule,
    mark_job_delivered,
    remove_job,
    save_schedule,
    split_schedule_views,
)

load_dotenv()
SMART_DRAFT_REF_RE = re.compile(r'@\[(?P<client>[^\]]+)\]\s+draft:"(?P<draft>[^"]+)"', re.IGNORECASE)

HEADER_ACCENTS = ["🔵", "🟢", "🟠", "🟣"]


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


def normalize_smart_draft_prompt(prompt: str) -> str:
    raw = str(prompt or "")
    if not raw:
        return raw

    def repl(match: re.Match) -> str:
        client = str(match.group("client") or "").strip()
        draft = str(match.group("draft") or "").strip()
        return f"@[{client}] using the saved creative draft named \"{draft}\""

    return SMART_DRAFT_REF_RE.sub(repl, raw)

app = FastAPI(title="Jarvis WhatsApp Listener")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve asset images so Meta's Graph API can download them via the tunnel
os.makedirs("assets", exist_ok=True)
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# --- ENVIRONMENT VARIABLES ---
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_TEST_PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "jarvis_webhook_secret_2026")
GRAPH_API_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")
RUNTIME_PROBE_TTL_SECONDS = 90
_runtime_probe_cache: dict[str, tuple[float, dict]] = {}

def get_agency_config() -> dict:
    config = {}
    if os.path.exists("agency_config.json"):
        try:
            with open("agency_config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass
    config.setdefault("owner_phone", os.getenv("OWNER_PHONE", "").strip())
    config.setdefault("whatsapp_access_token", os.getenv("WHATSAPP_TOKEN", "").strip())
    config.setdefault("whatsapp_phone_id", os.getenv("WHATSAPP_TEST_PHONE_NUMBER_ID", "").strip())
    return config


def get_whatsapp_runtime_config() -> tuple[str, str]:
    config = get_agency_config()
    token = str(config.get("whatsapp_access_token", "")).strip()
    phone_id = str(config.get("whatsapp_phone_id", "")).strip()
    return token, phone_id


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
        page_ok, page_payload = _meta_graph_get(page_id, token, {"fields": "id,name"})
        if not page_ok:
            message = page_payload.get("error", {}).get("message", "Facebook Page validation failed.")
            return {"ok": False, "detail": message}

        ig_ok, ig_payload = _meta_graph_get(ig_id, token, {"fields": "id,username"})
        if not ig_ok:
            message = ig_payload.get("error", {}).get("message", "Instagram Account validation failed.")
            return {"ok": False, "detail": message}

        return {
            "ok": True,
            "detail": f"Facebook Page {page_payload.get('name', page_id)} and Instagram account {ig_payload.get('username', ig_id)} are reachable.",
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


def format_schedule_label(days: list, time_str: str, scheduled_date: str | None = None) -> str:
    parsed_date = parse_iso_date(scheduled_date)
    if parsed_date:
        return f"{format_display_date(parsed_date)} at {time_str}"
    if not days:
        return time_str
    return f"{', '.join(str(day).title() for day in days)} at {time_str}"


def load_reschedule_sessions() -> dict:
    if os.path.exists("reschedule_sessions.json"):
        try:
            with open("reschedule_sessions.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_reschedule_sessions(data: dict) -> None:
    with open("reschedule_sessions.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def parse_owner_reschedule_command(msg_body: str) -> tuple[Optional[str], Optional[str], Optional[list[str]], Optional[str]]:
    text = msg_body.strip()
    explicit = re.match(
        r"^\s*TIME[\s_-]+([A-Z0-9]+)\s+(.+?)\s+(\d{1,2}:\d{2}\s*[AP]M)\s*$",
        text,
        re.IGNORECASE,
    )
    if explicit:
        date_phrase = explicit.group(2).strip()
        resolved_date = resolve_date_phrase(date_phrase)
        parsed_days = [resolved_date.strftime("%A")] if resolved_date else None
        return explicit.group(1).upper(), explicit.group(3).strip().upper(), parsed_days, (resolved_date.isoformat() if resolved_date else None)

    date_and_time = re.match(
        r"^\s*(.+?)\s+(\d{1,2}:\d{2}\s*[AP]M)\s*$",
        text,
        re.IGNORECASE,
    )
    if date_and_time:
        date_phrase = date_and_time.group(1).strip()
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

def send_whatsapp_message(to_phone: str, text: str):
    """
    Uses the Meta API to send an outbound WhatsApp reply directly to a phone number.
    """
    whatsapp_token, whatsapp_phone_id = get_whatsapp_runtime_config()
    if not whatsapp_token or not whatsapp_phone_id:
        logger.error("SYSTEM | ERROR | META CREDENTIALS MISSING IN AGENCY CONFIG OR .ENV")
        return {"success": False, "error": "Missing WhatsApp token or phone ID."}

    url = f"https://graph.facebook.com/v22.0/{whatsapp_phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text}
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return {"success": True, "status_code": response.status_code}
    except Exception as e:
        detail = ""
        if getattr(e, "response", None) is not None:
            detail = e.response.text[:200]
        logger.error(f"SYSTEM | ERROR | FB Graph API Failed to send message: {e} | {detail}")
        return {"success": False, "error": detail or str(e)}


def send_interactive_whatsapp_approval(to_phone: str, approval_id: str, preview_text: str):
    whatsapp_token, whatsapp_phone_id = get_whatsapp_runtime_config()
    if not whatsapp_token or not whatsapp_phone_id:
        logger.error("SYSTEM | ERROR | META CREDENTIALS MISSING IN AGENCY CONFIG OR .ENV")
        return {"success": False, "error": "Missing WhatsApp token or phone ID."}

    url = f"https://graph.facebook.com/v22.0/{whatsapp_phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
        "Content-Type": "application/json"
    }

    safe_text = preview_text[:700] + "..." if len(preview_text) > 700 else preview_text
    accent = HEADER_ACCENTS[sum(ord(ch) for ch in approval_id) % len(HEADER_ACCENTS)]

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {
                "type": "text",
                "text": f"JARVIS | Campaign Ready {accent}"
            },
            "body": {
                "text": safe_text
            },
            "footer": {
                "text": f"Agency OS • Ref {approval_id}"
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"APPROVE_{approval_id}",
                            "title": "Approve"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"REJECT_{approval_id}",
                            "title": "Refine"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"MOVE_{approval_id}",
                            "title": "Move Time"
                        }
                    }
                ]
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        logger.info(
            f"SYSTEM | INTERACTIVE APPROVAL SENT TO {to_phone} FOR ID {approval_id} | RESPONSE {json.dumps(response_data, ensure_ascii=False)}"
        )
        return {
            "success": True,
            "status_code": response.status_code,
            "response": response_data,
            "fallback_text_sent": False,
            "fallback_error": None,
        }
    except Exception as e:
        detail = ""
        if getattr(e, "response", None) is not None:
            detail = e.response.text[:200]
        logger.error(f"SYSTEM | ERROR | FB Graph Interactive Failed: {e} | {detail}")
        return {"success": False, "error": detail or str(e)}

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
                        # Extract the exact payload requirements
                        sender_phone = message.get("from")
                        msg_type = message.get("type")
                        
                        # We only analyze standard text interactions to prevent crashing on Voice notes/Images
                        if msg_type == "text":
                            msg_body = message["text"]["body"]
                            await handle_inbound_text(sender_phone, msg_body)
                        elif msg_type == "interactive":
                            # Phase 14: Interactive Buttons
                            reply = message["interactive"].get("button_reply", {})
                            reply_id = reply.get("id")
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

    pending_path = "pending_approvals.json"
    if not os.path.exists(pending_path):
        send_whatsapp_message(phone, "? Error: Pending approvals database not found.")
        return

    with open(pending_path, "r", encoding="utf-8") as f:
        try:
            pending = json.load(f)
        except Exception:
            pending = []

    job = next((j for j in pending if j.get("approval_id") == approval_id), None)
    if not job:
        send_whatsapp_message(phone, f"?? Error: Approval ID {approval_id} not found or already processed.")
        return

    if action == "MOVE":
        job["status"] = "pending_reschedule"
        with open(pending_path, "w", encoding="utf-8") as f:
            json.dump(pending, f, indent=4)
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

    pending = [j for j in pending if j.get("approval_id") != approval_id]
    with open(pending_path, "w", encoding="utf-8") as f:
        json.dump(pending, f, indent=4)
    sessions = load_reschedule_sessions()
    if phone in sessions and str(sessions[phone].get("approval_id", "")).upper() == approval_id:
        del sessions[phone]
        save_reschedule_sessions(sessions)

async def handle_inbound_text(phone: str, msg_body: str):
    """
    Applies the logical architecture mapping to inbound text streams.
    """
    agency_phone = str(get_agency_config().get("owner_phone", "")).strip()
    command_match = re.match(r"^\s*(APPROVE|REJECT)[\s_-]+([A-Z0-9]+)\s*$", msg_body.strip(), re.IGNORECASE)
    if agency_phone and phone == agency_phone and command_match:
        action = command_match.group(1).upper()
        approval_id = command_match.group(2).upper()
        logger.info(f"{phone} | SYSTEM | TEXT_APPROVAL | {action}_{approval_id}")
        await handle_interactive_reply(phone, f"{action}_{approval_id}")
        return

    if agency_phone and phone == agency_phone:
        approval_id, new_time, new_days, new_scheduled_date = parse_owner_reschedule_command(msg_body)
        if new_time:
            pending_path = "pending_approvals.json"
            pending = []
            if os.path.exists(pending_path):
                with open(pending_path, "r", encoding="utf-8") as f:
                    try:
                        pending = json.load(f)
                    except Exception:
                        pending = []

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
                with open(pending_path, "w", encoding="utf-8") as f:
                    json.dump(pending, f, indent=4)
                if phone in sessions:
                    del sessions[phone]
                    save_reschedule_sessions(sessions)

                summary = (
                    f"{format_client_label(target_job['client'])}\n"
                    f"Your next creative is staged and ready for final approval.\n\n"
                    f"Go-live: {format_schedule_label(target_job.get('days', []), target_job['time'], scheduled_date=target_job.get('scheduled_date'))}\n"
                    f"Assets: {describe_job_assets(target_job)}\n"
                    f"Focus: {target_job.get('topic', 'Creative draft')}\n\n"
                    f"Select the release path below."
                )
                send_interactive_whatsapp_approval(phone, target_job["approval_id"], summary)
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

class SynthesizeRequest(BaseModel):
    client_name: str
    raw_context: str


def _as_clean_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def build_brand_profile(client_id: str, profile: dict) -> dict:
    profile = profile or {}
    voice = profile.get("brand_voice") or {}
    tone = voice.get("tone", profile.get("tone", []))
    if isinstance(tone, list):
        tone = ", ".join([str(item).strip() for item in tone if str(item).strip()])
    return {
        "client_name": client_id,
        "business_name": profile.get("business_name", client_id),
        "industry": profile.get("industry", "general"),
        "brand_voice": {
            "tone": str(tone or "professional, friendly, engaging").strip(),
            "style": str(voice.get("style") or profile.get("style") or "conversational").strip(),
            "dialect": str(voice.get("dialect") or profile.get("dialect") or "gulf_arabic_khaleeji").strip(),
            "dialect_notes": str(voice.get("dialect_notes") or profile.get("dialect_notes") or "Use Khaleeji Gulf Arabic vocabulary.").strip(),
        },
        "brand_voice_examples": _as_clean_list(profile.get("brand_voice_examples")),
        "services": _as_clean_list(profile.get("services")),
        "target_audience": str(profile.get("target_audience", "")).strip(),
        "seo_keywords": _as_clean_list(profile.get("seo_keywords")),
        "hashtag_bank": _as_clean_list(profile.get("hashtag_bank")),
        "banned_words": _as_clean_list(profile.get("banned_words")),
        "identity": str(profile.get("identity", "")).strip(),
        "dos_and_donts": _as_clean_list(profile.get("dos_and_donts")),
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
    if len(_as_clean_list(profile.get("brand_voice_examples"))) < 3:
        missing.append("3-5 real brand voice examples")
    if len(_as_clean_list(profile.get("dos_and_donts"))) < 3:
        missing.append("At least 3 copy rules (do / avoid)")
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
            lines = [line.strip() for line in f.readlines() if line.strip()]
        return lines[-limit:]
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
    client_ids = []
    if os.path.exists("clients"):
        for filename in sorted(os.listdir("clients")):
            if filename.endswith(".json"):
                client_ids.append(filename[:-5])

    schedule_jobs = load_schedule("schedule.json")
    active_jobs, history_jobs = split_schedule_views(schedule_jobs)
    pending_approvals = _read_json_file("pending_approvals.json", [])
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
        profile_path = f"clients/{client_id}.json"
        profile = _read_json_file(profile_path, {})
        profile_json = profile.get("profile_json", {}) or {}
        missing_fields = validate_synthesized_profile(profile_json)

        vault_dir = f"assets/{client_id}"
        asset_count = 0
        draft_count = 0
        latest_drafts = []
        if os.path.exists(vault_dir):
            asset_count = len([
                f for f in os.listdir(vault_dir)
                if f != "queue.json" and os.path.isfile(os.path.join(vault_dir, f))
            ])
            queue_payload = load_queue_data(os.path.join(vault_dir, "queue.json"))
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
            display_window = format_display_date(candidate.get("scheduled_date"), candidate.get("time"))
        else:
            display_window = f"{', '.join(candidate.get('days', []))} at {candidate.get('time')}"
        next_job = {
            "client": client_display,
            "topic": candidate.get("topic") or "Untitled",
            "display_window": display_window,
            "media_kind": candidate.get("media_kind") or "",
        }

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
    }


@app.get("/api/dashboard-summary")
async def api_dashboard_summary():
    state = _collect_dashboard_state()
    return {
        "status": "success",
        "summary": {
            "client_count": state["client_count"],
            "asset_count": state["asset_count"],
            "draft_count": state["draft_count"],
            "active_job_count": state["active_job_count"],
            "history_count": state["history_count"],
            "pending_approval_count": state["pending_approval_count"],
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
        }
    }


@app.get("/api/health")
async def api_health():
    state = _collect_dashboard_state()
    tunnel_running, tunnel_provider = _is_process_running(["cloudflared", "ngrok http", "ngrok"])
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
        },
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
        "Approval queue",
        "warn" if state["pending_approval_count"] else "pass",
        f"{state['pending_approval_count']} approval request(s) are still waiting." if state["pending_approval_count"] else "Approval queue is clear.",
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
            "validated_at": datetime.utcnow().isoformat() + "Z",
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
    logger.info(f"API | SYNTHESIZE | Extracting profile for {req.client_name}")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenRouter API Key in .env")
        
    prompt = f"""You are an expert Brand Strategist AND Data Extraction Specialist.
Your job is to read raw notes/documents from a business owner and extract a complete brand profile.

Client Name: {req.client_name}
Raw Information:
{req.raw_context}

CRITICAL: Extract ALL of the following fields. You may infer minor supporting details, but you must NOT invent critical brand intelligence. If services, target audience, identity, brand voice, or brand voice examples are missing, mark them in missing_fields instead of hallucinating them.

For Arabic-speaking Gulf markets: generate seo_keywords and hashtag_bank in Gulf Arabic (خليجي). Generate dialect_notes with Khaleeji vocabulary guidance.

Return ONLY valid JSON matching this exact schema. No markdown wrapping, no trailing commas:
{{
  "status": "success",
  "missing_fields": [],
  "data": {{
    "business_name": "The Arabic or English business name",
    "industry": "e.g. food_beverage, real_estate, fashion, etc.",
    "brand_voice": {{
      "tone": "3 adjectives describing their voice",
      "style": "overall communication style description",
      "dialect": "gulf_arabic_khaleeji",
      "dialect_notes": "Specific Khaleeji vocabulary guidance for this brand"
    }},
    "services": ["service_1", "service_2", "service_3"],
    "target_audience": "Who they are selling to",
    "brand_voice_examples": ["Real caption example 1", "Real caption example 2", "Real caption example 3"],
    "seo_keywords": ["Arabic SEO keyword 1", "keyword 2", "keyword 3", "keyword 4", "keyword 5"],
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
        "HTTP-Referer": "https://localhost",
        "X-Title": "Agency OS",
    }
    data = {
        "model": "mistralai/mistral-nemo",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    
    response = await asyncio.to_thread(requests.post, "https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
    if response.status_code != 200:
        logger.error(f"OpenRouter Error: {response.text}")
        raise HTTPException(status_code=500, detail="Failed to synthesize client context via OpenRouter.")
        
    try:
        content = response.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        result = json.loads(content)
        if result.get("status") == "success":
            profile_data = result.get("data") or {}
            missing_fields = validate_synthesized_profile(profile_data)
            if missing_fields:
                return {"status": "missing", "missing_fields": missing_fields, "data": profile_data}
        return result
    except Exception as e:
        logger.error(f"Failed to parse LLM JSON: {e} -> {content}")
        raise HTTPException(status_code=500, detail="LLM did not return valid JSON.")

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
    
    missing_fields = validate_synthesized_profile(req.profile_json)
    if missing_fields:
        return JSONResponse(status_code=400, content={"status": "missing", "missing_fields": missing_fields, "reason": "Client profile is missing critical brand intelligence."})

    # 1. Write the full client JSON (credentials + profile) to clients/
    client_file = f"clients/{req.client_id}.json"
    full_data = req.dict(exclude_none=True)
    
    with open(client_file, "w", encoding="utf-8") as f:
        json.dump(full_data, f, indent=4)
        
    # 2. Write the brand profile to brands/ for the Caption Agent
    os.makedirs("brands", exist_ok=True)
    brand_file = f"brands/{req.client_id}.json"
    profile = req.profile_json
    brand_data = build_brand_profile(req.client_id, profile)
    
    with open(brand_file, "w", encoding="utf-8") as f:
        json.dump(brand_data, f, indent=4, ensure_ascii=False)
    
    logger.info(f"API | SAVE | Brand profile written to {brand_file}")
        
    # 3. Relegate phone_map explicitly to simple phone->clientID lookups
    if req.phone_number:
        phone_map = load_phone_map()
        phone_map[req.phone_number] = req.client_id
        with open("phone_map.json", "w", encoding="utf-8") as f:
            json.dump(phone_map, f, indent=4)
        
    return {"status": "success", "message": f"Client {req.client_id} securely registered. Brand profile written to brands/."}

@app.post("/api/upload-image")
async def api_upload_image(client_id: str = Form(...), file: UploadFile = File(...)):
    if not client_id:
        client_id = "unassigned"
    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in SUPPORTED_EXTENSIONS:
        return JSONResponse(status_code=400, content={"status": "error", "reason": "Unsupported media type. Use JPG, PNG, WEBP, MP4, MOV, M4V, or WEBM."})
        
    vault_dir = f"assets/{client_id}"
    os.makedirs(vault_dir, exist_ok=True)
    
    file_path = f"{vault_dir}/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"status": "success", "file_path": file_path}

@app.post("/api/upload-bulk")
async def api_upload_bulk(client_id: str = Form(...), files: List[UploadFile] = File(...)):
    import os
    if not client_id:
        client_id = "unassigned"
        
    vault_dir = f"assets/{client_id}"
    os.makedirs(vault_dir, exist_ok=True)
    
    uploaded_paths = []
    for file in files:
        extension = os.path.splitext(file.filename or "")[1].lower()
        if extension not in SUPPORTED_EXTENSIONS:
            return JSONResponse(status_code=400, content={"status": "error", "reason": f"Unsupported media type for {file.filename}. Use JPG, PNG, WEBP, MP4, MOV, M4V, or WEBM."})
        file_path = f"{vault_dir}/{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        uploaded_paths.append(file_path)
        
    return {"status": "success", "uploaded_paths": uploaded_paths}

@app.get("/api/client/{client_id}")
async def api_get_client(client_id: str):
    """Read a single client's full profile from disk."""
    profile_path = f"clients/{client_id}.json"
    if not os.path.exists(profile_path):
        return JSONResponse(status_code=404, content={"status": "error", "reason": f"Profile '{client_id}' not found on disk."})
    with open(profile_path, "r", encoding="utf-8") as f:
        return json.load(f)

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
    profile_path = f"clients/{client_id}.json"
    if not os.path.exists(profile_path):
        return JSONResponse(status_code=404, content={"status": "error", "reason": f"Profile '{client_id}' not found."})
    
    with open(profile_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    updates = req.dict(exclude_none=True)
    
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
    
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    # Sync phone_map if phone changed
    if req.phone_number:
        phone_map = load_phone_map()
        phone_map[req.phone_number] = client_id
        with open("phone_map.json", "w", encoding="utf-8") as f:
            json.dump(phone_map, f, indent=4)
    
    # If brand profile was updated, sync to brands/ for Caption Agent
    if updates.get("profile_json_merged"):
        os.makedirs("brands", exist_ok=True)
        brand_file = f"brands/{client_id}.json"
        profile = data.get("profile_json", {})
        brand_data = build_brand_profile(client_id, profile)
        with open(brand_file, "w", encoding="utf-8") as f:
            json.dump(brand_data, f, indent=4, ensure_ascii=False)
        logger.info(f"API | UPDATE | Brand profile synced to {brand_file}")
    
    updated_keys = [k for k in req.dict(exclude_none=True).keys()]
    logger.info(f"API | UPDATE | Client {client_id} updated: {updated_keys}")
    return {"status": "success", "message": f"Updated {updated_keys} for {client_id}", "updated_fields": updated_keys}


@app.delete("/api/client/{client_id}")
async def api_delete_client(client_id: str):
    profile_path = f"clients/{client_id}.json"
    brand_path = f"brands/{client_id}.json"
    vault_dir = f"assets/{client_id}"

    if not os.path.exists(profile_path):
        return JSONResponse(status_code=404, content={"status": "error", "reason": f"Client '{client_id}' was not found."})

    removed = {
        "client_id": client_id,
        "profile": False,
        "brand_profile": False,
        "vault": False,
        "phone_map_entries": 0,
        "schedule_jobs": 0,
        "pending_approvals": 0,
        "reschedule_sessions": 0,
    }

    try:
        profile = _read_json_file(profile_path, {})
        phone_number = str(profile.get("phone_number") or "").strip()

        if os.path.exists(profile_path):
            os.remove(profile_path)
            removed["profile"] = True

        if os.path.exists(brand_path):
            os.remove(brand_path)
            removed["brand_profile"] = True

        if os.path.exists(vault_dir):
            shutil.rmtree(vault_dir, ignore_errors=True)
            removed["vault"] = True

        phone_map = load_phone_map()
        filtered_map = {}
        removed_phone_entries = 0
        for phone, mapped_client in phone_map.items():
            if mapped_client == client_id or (phone_number and phone == phone_number):
                removed_phone_entries += 1
                continue
            filtered_map[phone] = mapped_client
        removed["phone_map_entries"] = removed_phone_entries
        with open("phone_map.json", "w", encoding="utf-8") as f:
            json.dump(filtered_map, f, indent=4, ensure_ascii=False)

        schedule_jobs = load_schedule("schedule.json")
        filtered_jobs = [job for job in schedule_jobs if str(job.get("client") or "") != client_id]
        removed["schedule_jobs"] = len(schedule_jobs) - len(filtered_jobs)
        if len(filtered_jobs) != len(schedule_jobs):
            save_schedule(filtered_jobs, "schedule.json")

        pending_path = "pending_approvals.json"
        pending = _read_json_file(pending_path, [])
        filtered_pending = [job for job in pending if str(job.get("client") or "") != client_id]
        removed["pending_approvals"] = len(pending) - len(filtered_pending)
        if len(filtered_pending) != len(pending):
            with open(pending_path, "w", encoding="utf-8") as f:
                json.dump(filtered_pending, f, indent=4, ensure_ascii=False)

        sessions = load_reschedule_sessions()
        filtered_sessions = {}
        removed_sessions = 0
        for phone, session in sessions.items():
            if str(session.get("client") or "") == client_id:
                removed_sessions += 1
                continue
            filtered_sessions[phone] = session
        removed["reschedule_sessions"] = removed_sessions
        if removed_sessions:
            save_reschedule_sessions(filtered_sessions)

        logger.info(f"API | DELETE | Removed client {client_id}: {removed}")
        return {"status": "success", "removed": removed}
    except Exception as e:
        logger.error(f"API | DELETE | Failed to remove client {client_id}: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(e)})

@app.get("/api/vaults")
async def api_get_vaults():
    import os
    vaults = {}
    if os.path.exists("clients"):
        for filename in os.listdir("clients"):
            if filename.endswith(".json"):
                cid = filename[:-5]
                vault_dir = f"assets/{cid}"
                if os.path.exists(vault_dir):
                    vaults[cid] = len([f for f in os.listdir(vault_dir) if f != "queue.json" and os.path.isfile(os.path.join(vault_dir, f))])
                else:
                    vaults[cid] = 0
    return {"status": "success", "vaults": vaults}

@app.get("/api/vault/{client_id}")
async def api_get_vault_contents(client_id: str):
    vault_dir = f"assets/{client_id}"
    if not os.path.exists(vault_dir):
        return {"status": "success", "files": [], "bundles": {}}
    
    files_with_meta = []
    try:
        from PIL import Image
    except ImportError:
        Image = None

    for f in os.listdir(vault_dir):
        file_path = os.path.join(vault_dir, f)
        if os.path.isfile(file_path) and f not in ["queue.json"]:
            is_valid_ig = True
            warning = ""
            media_kind = detect_media_kind(f)
            if Image:
                try:
                    if media_kind == "image":
                        with Image.open(file_path) as img:
                            w, h = img.size
                            ratio = w / h
                            if ratio < 0.79 or ratio > 1.92:
                                is_valid_ig = False
                                warning = f"Ratio {ratio:.2f} violates IG rules (0.8 - 1.91)"
                except Exception:
                    pass
            files_with_meta.append({
                "filename": f,
                "kind": media_kind,
                "is_valid_ig": is_valid_ig,
                "warning": warning,
                "is_video": media_kind == "video",
            })
            
    queue_path = os.path.join(vault_dir, "queue.json")
    bundles = {}
    if os.path.exists(queue_path):
        bundles = load_queue_data(queue_path).get("bundles", {})
                
    return {"status": "success", "files": files_with_meta, "bundles": bundles}

@app.delete("/api/vault/{client_id}/{filename}")
async def api_delete_vault_file(client_id: str, filename: str):
    file_path = f"assets/{client_id}/{filename}"
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return {"status": "success"}
        except Exception as e:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=500, content={"status": "error", "reason": str(e)})
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=404, content={"status": "error", "reason": "File not found"})

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
    vault_dir = f"assets/{client_id}"
    os.makedirs(vault_dir, exist_ok=True)
    queue_path = os.path.join(vault_dir, "queue.json")

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

    data = load_queue_data(queue_path)
    data["bundles"][req.bundle_name] = {
        "bundle_type": bundle_type,
        "items": items,
        "caption_mode": "ai",
        "caption_status": "empty",
        "caption_text": "",
        "hashtags": [],
        "seo_keyword_used": "",
        "topic_hint": "",
    }
    save_queue_data(queue_path, data)

    return {"status": "success", "message": f"Saved creative draft {req.bundle_name}", "bundles": data["bundles"]}

@app.delete("/api/vault/{client_id}/bundles/{bundle_name}")
async def api_delete_bundle(client_id: str, bundle_name: str):
    queue_path = f"assets/{client_id}/queue.json"
    if not os.path.exists(queue_path):
        return {"status": "error", "message": "Queue not found"}

    data = load_queue_data(queue_path)
            
    if bundle_name in data.get("bundles", {}):
        del data["bundles"][bundle_name]
        save_queue_data(queue_path, data)
        return {"status": "success", "message": f"Deleted draft {bundle_name}"}
    return {"status": "error", "message": "Draft not found"}


@app.put("/api/vault/{client_id}/bundles/{bundle_name}/rename")
async def api_rename_bundle(client_id: str, bundle_name: str, req: RenameBundleRequest):
    queue_path = f"assets/{client_id}/queue.json"
    if not os.path.exists(queue_path):
        return JSONResponse(status_code=404, content={"status": "error", "reason": "Queue not found"})

    new_name = str(req.new_name or "").strip()
    if not new_name:
        return JSONResponse(status_code=400, content={"status": "error", "reason": "Draft name cannot be empty."})

    data = load_queue_data(queue_path)
    bundles = data.get("bundles", {})
    if bundle_name not in bundles:
        return JSONResponse(status_code=404, content={"status": "error", "reason": "Draft not found"})
    if new_name != bundle_name and new_name in bundles:
        return JSONResponse(status_code=400, content={"status": "error", "reason": "A draft with that name already exists."})

    bundles[new_name] = bundles.pop(bundle_name)
    save_queue_data(queue_path, data)
    return {"status": "success", "old_name": bundle_name, "new_name": new_name, "bundles": bundles}


@app.post("/api/vault/{client_id}/bundles/{bundle_name}/generate-caption")
async def api_generate_draft_caption(client_id: str, bundle_name: str, req: GenerateCaptionRequest):
    queue_path = f"assets/{client_id}/queue.json"
    if not os.path.exists(queue_path):
        return JSONResponse(status_code=404, content={"status": "error", "reason": "Queue not found"})

    data = load_queue_data(queue_path)
    bundles = data.get("bundles", {})
    draft = bundles.get(bundle_name)
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

        result = await asyncio.to_thread(generate_caption_payload, client_id, topic, media_type)
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
        save_queue_data(queue_path, data)
        return {"status": "success", "draft": bundles.get(bundle_name), "generated": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "reason": str(e)})


@app.put("/api/vault/{client_id}/bundles/{bundle_name}/caption")
async def api_save_manual_caption(client_id: str, bundle_name: str, req: ManualCaptionRequest):
    queue_path = f"assets/{client_id}/queue.json"
    if not os.path.exists(queue_path):
        return JSONResponse(status_code=404, content={"status": "error", "reason": "Queue not found"})

    data = load_queue_data(queue_path)
    bundles = data.get("bundles", {})
    draft = bundles.get(bundle_name)
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
    save_queue_data(queue_path, data)
    return {"status": "success", "draft": bundles.get(bundle_name)}

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
        removed = data.pop(index)
        save_schedule(data, "schedule.json")
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
    if media_paths:
        vault_dir = os.path.dirname(media_paths[0])
        queue_path = os.path.join(vault_dir, "queue.json")
        if os.path.exists(queue_path):
            try:
                qdata = load_queue_data(queue_path)
                if "bundles" in qdata and bundle_name in qdata["bundles"]:
                    del qdata["bundles"][bundle_name]
                    save_queue_data(queue_path, qdata)
            except Exception as e:
                logger.error(f"Failed to clear bundle from queue: {e}")

    return {"status": "success", "job": matched_rule}

class OrchestratorRequest(BaseModel):
    prompt: str

@app.post("/api/orchestrator-chat")
async def api_orchestrator_chat(req: OrchestratorRequest):
    try:
        from orchestrator_agent import run_orchestrator
        normalized_prompt = normalize_prompt_date_typos(req.prompt)
        normalized_prompt = normalize_smart_draft_prompt(normalized_prompt)
        logger.info(f"API | ORCHESTRATOR | Received natural language operation constraint: {req.prompt}")
        if normalized_prompt != req.prompt:
            logger.info(f"API | ORCHESTRATOR | Normalized prompt for scheduling clarity: {normalized_prompt}")

        reply = await asyncio.to_thread(run_orchestrator, normalized_prompt)
        return {"status": "success", "reply": reply}
    except Exception as e:
        logger.error(f"Orchestrator routing failure: {e}")
        return {"status": "error", "reason": str(e)}

@app.get("/api/stream-logs")
async def stream_logs():
    """
    SSE stream capturing raw terminal stdout natively from pipeline_stream.log 
    so frontend types out agent thoughts.
    """
    async def log_generator():
        # Ensure file exists
        open("pipeline_stream.log", "a").close()
        try:
            with open("pipeline_stream.log", "r", encoding="utf-8") as f:
                f.seek(0, 2) 
                while True:
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
    import os
    clients = []
    if os.path.exists("clients"):
        for filename in os.listdir("clients"):
            if filename.endswith(".json"):
                clients.append(filename[:-5])
    return {"status": "success", "clients": clients}

@app.get("/api/agency/config")
async def api_get_agency_config():
    return get_agency_config()

class AgencyConfigRequest(BaseModel):
    owner_phone: str
    whatsapp_access_token: Optional[str] = None

@app.post("/api/agency/config")
async def api_post_agency_config(req: AgencyConfigRequest):
    current = get_agency_config()
    config = {
        "owner_phone": req.owner_phone.strip(),
        "whatsapp_access_token": (req.whatsapp_access_token or "").strip(),
        "whatsapp_phone_id": current.get("whatsapp_phone_id", "").strip(),
    }
    with open("agency_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    return {"status": "success"}
    return {"status": "success"}
