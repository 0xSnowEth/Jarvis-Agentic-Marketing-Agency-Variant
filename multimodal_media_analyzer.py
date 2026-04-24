import base64
import json
import mimetypes
import os
import re
import subprocess
import tempfile
from typing import Any

import requests

from asset_store import get_asset_content

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_VISION_MODEL = os.getenv("ANTHROPIC_VISION_MODEL", "claude-3-7-sonnet-latest").strip() or "claude-3-7-sonnet-latest"
VISION_TIMEOUT_SECONDS = float(os.getenv("ANTHROPIC_VISION_TIMEOUT_SECONDS", "45"))
VISION_ANALYSIS_MODE = os.getenv("VISION_ANALYSIS_MODE", "heuristic").strip().lower() or "heuristic"


def _safe_json_loads(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(raw[start : end + 1])
    except Exception:
        return {}


def _extract_keywords(text: str) -> list[str]:
    cleaned = re.sub(r"[^A-Za-z0-9\u0600-\u06FF]+", " ", str(text or "")).strip()
    if not cleaned:
        return []
    words = [part.strip() for part in cleaned.split() if len(part.strip()) >= 3]
    deduped: list[str] = []
    seen: set[str] = set()
    for word in words:
        key = word.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(word)
    return deduped[:8]


def _clean_english_terms_for_arabic(keywords: list[str]) -> list[str]:
    allowed = {
        "iced", "coffee", "cold", "brew", "latte", "matcha", "espresso",
        "beans", "pastry", "croissant", "specialty", "drinks", "chocolate",
    }
    output: list[str] = []
    for item in keywords:
        token = str(item or "").strip()
        if not token:
            continue
        if re.search(r"[\u0600-\u06FF]", token):
            output.append(token)
            continue
        normalized = token.lower()
        if normalized in allowed or len(normalized.split()) <= 2:
            output.append(token)
    return output[:8]


def _content_block_from_image_bytes(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": mime_type,
            "data": base64.b64encode(image_bytes).decode("ascii"),
        },
    }


def _sample_video_frames(video_bytes: bytes, suffix: str) -> list[bytes]:
    source_path = ""
    output_dir = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix or ".mp4") as source_file:
            source_file.write(video_bytes)
            source_path = source_file.name
        output_dir = tempfile.mkdtemp(prefix="jarvis-video-frames-")
        output_pattern = os.path.join(output_dir, "frame_%02d.jpg")
        command = [
            "ffmpeg",
            "-y",
            "-i",
            source_path,
            "-vf",
            "fps=1/2,scale=960:-1",
            "-frames:v",
            "3",
            output_pattern,
        ]
        result = subprocess.run(command, capture_output=True, timeout=30)
        if result.returncode != 0:
            return []
        frames: list[bytes] = []
        for name in sorted(os.listdir(output_dir))[:3]:
            frame_path = os.path.join(output_dir, name)
            if os.path.isfile(frame_path):
                with open(frame_path, "rb") as handle:
                    frames.append(handle.read())
        return frames
    except Exception:
        return []
    finally:
        if source_path and os.path.exists(source_path):
            try:
                os.remove(source_path)
            except OSError:
                pass
        if output_dir and os.path.isdir(output_dir):
            for name in os.listdir(output_dir):
                try:
                    os.remove(os.path.join(output_dir, name))
                except OSError:
                    pass
            try:
                os.rmdir(output_dir)
            except OSError:
                pass


def _heuristic_media_analysis(media_assets: list[dict[str, Any]], operator_brief: str, media_type_context: str) -> dict[str, Any]:
    filenames = [str(item.get("filename") or "").strip() for item in media_assets if str(item.get("filename") or "").strip()]
    keywords = _extract_keywords(" ".join(filenames + [operator_brief]))
    kind = str(media_type_context or (media_assets[0].get("kind") if media_assets else "") or "").strip().lower()
    lower_brief = str(operator_brief or "").lower()
    arabic_mode = bool(re.search(r"[\u0600-\u06FF]", operator_brief or ""))
    cleaned_keywords = _clean_english_terms_for_arabic(keywords) if arabic_mode else keywords
    image_count = len(media_assets)
    if kind == "image_carousel":
        if image_count >= 3 and any(term in lower_brief for term in ["menu", "variety", "selection", "options"]):
            arc = "menu variety story"
            hook_opportunities = ["three reasons", "menu variety", "your next order"]
        elif image_count >= 3:
            arc = "hero item with supporting frames"
            hook_opportunities = ["one mood three frames", "from first sip to slow finish", "your afternoon reset"]
        else:
            arc = "product showcase sequence"
            hook_opportunities = ["hero item first", "closer look", "save this carousel"]
        platform_fit_hints = ["lead with frame-one tension", "write for a swipeable caption", "land one clear CTA at the end"]
    elif kind == "video":
        arc = "motion-driven product reveal"
        hook_opportunities = ["stop-the-scroll opener", "what the movement reveals", "watch then visit"]
        platform_fit_hints = ["lead with the motion payoff", "keep the first line tight", "use one natural CTA"]
    else:
        arc = "single-frame hero product feature"
        hook_opportunities = ["hero product first", "one premium detail", "quick visual payoff"]
        platform_fit_hints = ["short visual-first hook", "strong first sentence", "clear CTA"]
    return {
        "status": "heuristic",
        "visual_narrative": operator_brief or "Product-focused visual with commercial intent.",
        "emotional_tone": "premium, clear, local",
        "product_signals": cleaned_keywords[:4],
        "hook_opportunities": hook_opportunities,
        "cta_opportunities": ["visit today", "save this", "send this to someone"],
        "platform_fit_hints": platform_fit_hints,
        "story_arc": arc,
        "analysis_summary": f"{arc.capitalize()} with {len(media_assets)} asset(s).",
    }


def analyze_media_bundle(
    client_id: str,
    media_assets: list[dict[str, Any]] | None,
    *,
    operator_brief: str = "",
    media_type_context: str = "",
) -> dict[str, Any]:
    assets = [dict(item or {}) for item in (media_assets or [])]
    if not assets:
        return _heuristic_media_analysis([], operator_brief, media_type_context)

    if VISION_ANALYSIS_MODE != "anthropic":
        return _heuristic_media_analysis(assets, operator_brief, media_type_context)

    anthropic_key = str(os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not anthropic_key:
        return _heuristic_media_analysis(assets, operator_brief, media_type_context)

    content_blocks: list[dict[str, Any]] = []
    for asset in assets[:3]:
        filename = str(asset.get("filename") or "").strip()
        kind = str(asset.get("kind") or "").strip().lower()
        if not filename:
            continue
        downloaded = get_asset_content(client_id, filename)
        if not downloaded:
            continue
        file_bytes, mime_type = downloaded
        mime_type = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        if kind == "video":
            suffix = os.path.splitext(filename)[1] or ".mp4"
            for frame_bytes in _sample_video_frames(file_bytes, suffix):
                content_blocks.append(_content_block_from_image_bytes(frame_bytes, "image/jpeg"))
        elif mime_type.startswith("image/"):
            content_blocks.append(_content_block_from_image_bytes(file_bytes, mime_type))

    if not content_blocks:
        return _heuristic_media_analysis(assets, operator_brief, media_type_context)

    prompt = (
        "Analyze these social-post media assets for caption generation.\n"
        "Return JSON only with keys: visual_narrative, emotional_tone, product_signals, hook_opportunities, "
        "cta_opportunities, platform_fit_hints, story_arc, analysis_summary.\n"
        f"Operator brief: {operator_brief or 'None provided'}\n"
        f"Media context: {media_type_context or 'image_single'}\n"
        "Be concrete, commercial, and visually grounded."
    )
    payload = {
        "model": DEFAULT_VISION_MODEL,
        "max_tokens": 1200,
        "messages": [
            {
                "role": "user",
                "content": [*content_blocks, {"type": "text", "text": prompt}],
            }
        ],
    }
    try:
        response = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": anthropic_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json=payload,
            timeout=VISION_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
        text_blocks = [str(item.get("text") or "") for item in (body.get("content") or []) if item.get("type") == "text"]
        parsed = _safe_json_loads("\n".join(text_blocks))
        if parsed:
            parsed["status"] = "success"
            return parsed
    except Exception:
        pass
    return _heuristic_media_analysis(assets, operator_brief, media_type_context)
