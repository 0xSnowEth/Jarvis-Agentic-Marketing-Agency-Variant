import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger("WhatsAppTransport")

GRAPH_API_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0").strip() or "v23.0"


def get_agency_config() -> dict[str, Any]:
    file_config: dict[str, Any] = {}
    if os.path.exists("agency_config.json"):
        try:
            with open("agency_config.json", "r", encoding="utf-8") as handle:
                file_config = json.load(handle)
        except Exception:
            file_config = {}
    env_owner_phone = str(os.getenv("OWNER_PHONE") or "").strip()
    env_whatsapp_token = str(os.getenv("WHATSAPP_TOKEN") or "").strip()
    env_whatsapp_phone_id = str(os.getenv("WHATSAPP_TEST_PHONE_NUMBER_ID") or "").strip()
    return {
        "owner_phone": env_owner_phone or str(file_config.get("owner_phone") or "").strip(),
        # Agency-level WhatsApp runtime secrets are env-managed in production.
        "whatsapp_access_token": env_whatsapp_token,
        "whatsapp_phone_id": env_whatsapp_phone_id,
        "approval_routing": str(file_config.get("approval_routing") or "desktop_first").strip() or "desktop_first",
    }


def normalize_phone(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits or raw.lstrip("+")


def get_runtime_config() -> tuple[str, str]:
    config = get_agency_config()
    token = str(config.get("whatsapp_access_token") or "").strip()
    phone_id = str(config.get("whatsapp_phone_id") or "").strip()
    return token, phone_id


def _build_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _messages_url(phone_id: str) -> str:
    return f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/messages"


def send_whatsapp_payload(payload: dict[str, Any]) -> dict[str, Any]:
    token, phone_id = get_runtime_config()
    if not token or not phone_id:
        logger.error("SYSTEM | ERROR | WHATSAPP RUNTIME SECRETS MISSING FROM ENV")
        return {"success": False, "error": "Missing WhatsApp token or phone ID."}
    try:
        response = requests.post(
            _messages_url(phone_id),
            headers=_build_headers(token),
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        body = response.json() if response.content else {}
        return {"success": True, "status_code": response.status_code, "response": body}
    except Exception as exc:
        detail = ""
        if getattr(exc, "response", None) is not None:
            detail = exc.response.text[:400]
        logger.error("SYSTEM | ERROR | WhatsApp send failed: %s | %s", exc, detail)
        return {"success": False, "error": detail or str(exc)}


def send_text_message(to_phone: str, text: str) -> dict[str, Any]:
    return send_whatsapp_payload(
        {
            "messaging_product": "whatsapp",
            "to": normalize_phone(to_phone),
            "type": "text",
            "text": {"body": str(text or "")},
        }
    )


def send_button_message(
    to_phone: str,
    *,
    header_text: str,
    body_text: str,
    buttons: list[dict[str, str]],
    footer_text: str = "",
) -> dict[str, Any]:
    limited_buttons = []
    for button in (buttons or [])[:3]:
        reply_id = str((button or {}).get("id") or "").strip()
        title = str((button or {}).get("title") or "").strip()
        if not reply_id or not title:
            continue
        limited_buttons.append(
            {
                "type": "reply",
                "reply": {
                    "id": reply_id[:256],
                    "title": title[:20],
                },
            }
        )
    if not limited_buttons:
        return {"success": False, "error": "At least one WhatsApp button is required."}
    payload = {
        "messaging_product": "whatsapp",
        "to": normalize_phone(to_phone),
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": str(header_text or "")[:60]},
            "body": {"text": str(body_text or "")[:1024]},
            "action": {"buttons": limited_buttons},
        },
    }
    footer = str(footer_text or "").strip()
    if footer:
        payload["interactive"]["footer"] = {"text": footer[:60]}
    return send_whatsapp_payload(payload)


def send_list_message(
    to_phone: str,
    *,
    header_text: str,
    body_text: str,
    button_text: str,
    sections: list[dict[str, Any]],
    footer_text: str = "",
) -> dict[str, Any]:
    normalized_sections = []
    for section in (sections or [])[:10]:
        title = str((section or {}).get("title") or "").strip()[:24]
        rows = []
        for row in list((section or {}).get("rows") or [])[:10]:
            row_id = str((row or {}).get("id") or "").strip()
            row_title = str((row or {}).get("title") or "").strip()
            if not row_id or not row_title:
                continue
            rows.append(
                {
                    "id": row_id[:200],
                    "title": row_title[:24],
                    "description": str((row or {}).get("description") or "").strip()[:72],
                }
            )
        if rows:
            normalized_sections.append({"title": title or "Options", "rows": rows})
    if not normalized_sections:
        return {"success": False, "error": "At least one WhatsApp list row is required."}
    payload = {
        "messaging_product": "whatsapp",
        "to": normalize_phone(to_phone),
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": str(header_text or "")[:60]},
            "body": {"text": str(body_text or "")[:1024]},
            "action": {
                "button": str(button_text or "Select")[:20],
                "sections": normalized_sections,
            },
        },
    }
    footer = str(footer_text or "").strip()
    if footer:
        payload["interactive"]["footer"] = {"text": footer[:60]}
    return send_whatsapp_payload(payload)


def fetch_media_bytes(media_id: str) -> dict[str, Any]:
    token, _phone_id = get_runtime_config()
    if not token:
        return {"success": False, "error": "Missing WhatsApp token."}
    safe_media_id = str(media_id or "").strip()
    if not safe_media_id:
        return {"success": False, "error": "Media ID is required."}
    try:
        metadata_resp = requests.get(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/{safe_media_id}",
            params={"access_token": token},
            timeout=20,
        )
        metadata_resp.raise_for_status()
        metadata = metadata_resp.json() if metadata_resp.content else {}
        media_url = str(metadata.get("url") or "").strip()
        if not media_url:
            return {"success": False, "error": "Meta did not return a media download URL.", "metadata": metadata}
        binary_resp = requests.get(
            media_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        binary_resp.raise_for_status()
        return {
            "success": True,
            "content": binary_resp.content,
            "mime_type": str(metadata.get("mime_type") or binary_resp.headers.get("Content-Type") or "").strip(),
            "sha256": str(metadata.get("sha256") or "").strip(),
            "file_size": metadata.get("file_size") or len(binary_resp.content),
            "metadata": metadata,
        }
    except Exception as exc:
        detail = ""
        if getattr(exc, "response", None) is not None:
            detail = exc.response.text[:400]
        logger.error("SYSTEM | ERROR | WhatsApp media fetch failed: %s | %s", exc, detail)
        return {"success": False, "error": detail or str(exc)}


def normalize_inbound_message(message: dict[str, Any]) -> dict[str, Any]:
    payload = dict(message or {})
    msg_type = str(payload.get("type") or "").strip().lower()
    interactive = payload.get("interactive") or {}
    button_reply = interactive.get("button_reply") or {}
    list_reply = interactive.get("list_reply") or {}
    normalized = {
        "message_id": str(payload.get("id") or "").strip(),
        "from": normalize_phone(payload.get("from")),
        "timestamp": str(payload.get("timestamp") or "").strip(),
        "type": msg_type,
        "message_type": msg_type,
        "text": "",
        "interactive_reply_id": "",
        "interactive_reply_title": "",
        "media_id": "",
        "filename": "",
        "mime_type": "",
        "caption": "",
        "raw": payload,
    }
    if msg_type == "text":
        normalized["text"] = str((payload.get("text") or {}).get("body") or "").strip()
    elif msg_type == "interactive":
        normalized["interactive_reply_id"] = str(button_reply.get("id") or list_reply.get("id") or "").strip()
        normalized["interactive_reply_title"] = str(button_reply.get("title") or list_reply.get("title") or "").strip()
        normalized["text"] = normalized["interactive_reply_title"]
    elif msg_type in {"document", "image", "video"}:
        media_block = payload.get(msg_type) or {}
        normalized["media_id"] = str(media_block.get("id") or "").strip()
        normalized["filename"] = str(media_block.get("filename") or "").strip()
        normalized["mime_type"] = str(media_block.get("mime_type") or "").strip()
        normalized["caption"] = str(media_block.get("caption") or "").strip()
        normalized["text"] = normalized["caption"]
    return normalized
