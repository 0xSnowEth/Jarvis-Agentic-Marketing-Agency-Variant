import json
import os
import re
from typing import Any

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


GENERIC_DRAFT_NAME_RE = re.compile(r'^(image post|carousel|reel)\s+\d+$', re.IGNORECASE)
HASHTAG_SPLIT_RE = re.compile(r"[\n,،;|]+")
HASHTAG_SPACE_RE = re.compile(r"\s+")
INVALID_HASHTAG_CHARS_RE = re.compile(r"[^\w]+", re.UNICODE)


def sanitize_topic_hint(bundle_name: str, topic_hint: str) -> str:
    hint = str(topic_hint or '').strip()
    if not hint:
        return ''
    if hint.lower() == str(bundle_name or '').strip().lower():
        return ''
    if GENERIC_DRAFT_NAME_RE.match(hint):
        return ''
    return hint


def normalize_hashtag_token(raw_tag: str) -> str:
    tag = str(raw_tag or "").strip()
    if not tag:
        return ""
    tag = tag.lstrip("#").strip()
    if not tag:
        return ""
    tag = HASHTAG_SPACE_RE.sub("_", tag)
    tag = INVALID_HASHTAG_CHARS_RE.sub("", tag)
    tag = tag.strip("_")
    if not tag:
        return ""
    return f"#{tag}"


def normalize_hashtag_list(raw_tags: Any) -> list[str]:
    candidates: list[str] = []
    if isinstance(raw_tags, str):
        candidates = [part for part in HASHTAG_SPLIT_RE.split(raw_tags) if part.strip()]
    elif isinstance(raw_tags, list):
        for raw in raw_tags:
            text = str(raw or "").strip()
            if not text:
                continue
            candidates.extend(part for part in HASHTAG_SPLIT_RE.split(text) if part.strip())

    normalized: list[str] = []
    seen = set()
    for raw in candidates:
        tag = normalize_hashtag_token(raw)
        if not tag:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(tag)
    return normalized


def detect_media_kind(filename: str) -> str:
    ext = os.path.splitext(str(filename or "").strip().lower())[1]
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return "image"


def normalize_bundle_entry(bundle_name: str, payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        items = payload.get("items", [])
        normalized_items = []
        for item in items:
            if isinstance(item, dict):
                filename = str(item.get("filename") or "").strip()
                if not filename:
                    continue
                kind = str(item.get("kind") or detect_media_kind(filename)).strip().lower()
            else:
                filename = str(item or "").strip()
                if not filename:
                    continue
                kind = detect_media_kind(filename)
            normalized_items.append({"filename": filename, "kind": kind})

        bundle_type = str(payload.get("bundle_type") or "").strip().lower()
        if not bundle_type:
            if normalized_items and all(item["kind"] == "video" for item in normalized_items):
                bundle_type = "video"
            elif len(normalized_items) > 1:
                bundle_type = "image_carousel"
            else:
                bundle_type = "image_single"

        caption_mode = str(payload.get("caption_mode") or "ai").strip().lower()
        if caption_mode not in {"ai", "manual", "hybrid"}:
            caption_mode = "ai"

        caption_text = str(payload.get("caption_text") or "").strip()
        seo_keyword_used = str(payload.get("seo_keyword_used") or "").strip()
        caption_status = str(payload.get("caption_status") or ("ready" if caption_text else "empty")).strip().lower()
        topic_hint = sanitize_topic_hint(bundle_name, payload.get("topic_hint"))
        hashtags = normalize_hashtag_list(payload.get("hashtags", []))
        caption_metadata = payload.get("caption_metadata") if isinstance(payload.get("caption_metadata"), dict) else {}

        return {
            "bundle_name": bundle_name,
            "bundle_type": bundle_type,
            "items": normalized_items,
            "caption_mode": caption_mode,
            "caption_status": caption_status,
            "caption_text": caption_text,
            "hashtags": hashtags,
            "seo_keyword_used": seo_keyword_used,
            "topic_hint": topic_hint,
            "caption_metadata": caption_metadata,
        }

    legacy_files = [str(item).strip() for item in (payload or []) if str(item).strip()]
    items = [{"filename": filename, "kind": detect_media_kind(filename)} for filename in legacy_files]
    if items and all(item["kind"] == "video" for item in items):
        bundle_type = "video"
    elif len(items) > 1:
        bundle_type = "image_carousel"
    else:
        bundle_type = "image_single"

    return {
        "bundle_name": bundle_name,
        "bundle_type": bundle_type,
        "items": items,
        "caption_mode": "ai",
        "caption_status": "empty",
        "caption_text": "",
        "hashtags": [],
        "seo_keyword_used": "",
        "topic_hint": "",
        "caption_metadata": {},
    }


def normalize_queue_data(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        data = {}
    bundles = data.get("bundles", {})
    normalized_bundles = {}
    if isinstance(bundles, dict):
        for bundle_name, payload in bundles.items():
            normalized = normalize_bundle_entry(str(bundle_name), payload)
            normalized_bundles[str(bundle_name)] = {
                "bundle_type": normalized["bundle_type"],
                "items": normalized["items"],
                "caption_mode": normalized["caption_mode"],
                "caption_status": normalized["caption_status"],
                "caption_text": normalized["caption_text"],
                "hashtags": normalized["hashtags"],
                "seo_keyword_used": normalized["seo_keyword_used"],
                "topic_hint": normalized["topic_hint"],
                "caption_metadata": normalized["caption_metadata"],
            }
    return {"bundles": normalized_bundles}


def load_queue_data(queue_path: str) -> dict[str, Any]:
    if not os.path.exists(queue_path):
        return {"bundles": {}}
    with open(queue_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception:
            data = {"bundles": {}}
    normalized = normalize_queue_data(data)
    if normalized != data:
        save_queue_data(queue_path, normalized)
    return normalized


def save_queue_data(queue_path: str, data: dict[str, Any]) -> None:
    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(normalize_queue_data(data), f, indent=4, ensure_ascii=False)


def get_bundle_payload(queue_path: str, bundle_name: str) -> dict[str, Any] | None:
    bundles = load_queue_data(queue_path).get("bundles", {})
    payload = bundles.get(bundle_name)
    if payload is None:
        return None
    normalized = normalize_bundle_entry(bundle_name, payload)
    return {
        "bundle_name": bundle_name,
        "bundle_type": normalized["bundle_type"],
        "items": normalized["items"],
        "caption_mode": normalized["caption_mode"],
        "caption_status": normalized["caption_status"],
        "caption_text": normalized["caption_text"],
        "hashtags": normalized["hashtags"],
        "seo_keyword_used": normalized["seo_keyword_used"],
        "topic_hint": normalized["topic_hint"],
        "caption_metadata": normalized["caption_metadata"],
    }


def get_bundle_items(queue_path: str, bundle_name: str) -> list[dict[str, Any]] | None:
    payload = get_bundle_payload(queue_path, bundle_name)
    if payload is None:
        return None
    return payload["items"]


def get_bundle_media_paths(client_id: str, queue_path: str, bundle_name: str) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    payload = get_bundle_payload(queue_path, bundle_name)
    if payload is None:
        return None, [], []

    images = []
    videos = []
    for item in payload["items"]:
        path = f"assets/{client_id}/{item['filename']}"
        if item["kind"] == "video":
            videos.append(path)
        else:
            images.append(path)
    return payload, images, videos
