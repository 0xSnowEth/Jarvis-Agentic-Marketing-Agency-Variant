import json
import os
import re
import sys
import time
from collections.abc import Callable
import random
from typing import Any
from llm_config import build_sync_client


from dotenv import load_dotenv
from openai import OpenAI
import requests

from caption_playbook import build_caption_playbook
from caption_technique_service import get_caption_technique_snapshot_payload
from client_store import get_client_store
from draft_store import list_client_drafts
from frontier_caption_ranker import rank_caption_variants
from multimodal_media_analyzer import analyze_media_bundle
from queue_store import normalize_hashtag_list
from trend_research_service import get_client_trend_dossier
from external_context_safety import sanitize_operator_brief

load_dotenv()

CAPTION_MODEL = os.getenv("CAPTION_MODEL", "qwen/qwen3.6-plus-preview:free").strip() or "qwen/qwen3.6-plus-preview:free"
CAPTION_FALLBACK_MODEL = os.getenv("CAPTION_FALLBACK_MODEL", "").strip()
CAPTION_TIMEOUT_SECONDS = float(os.getenv("CAPTION_TIMEOUT_SECONDS", "35"))
CAPTION_RESPONSE_MAX_TOKENS = max(120, int(os.getenv("CAPTION_RESPONSE_MAX_TOKENS", "260") or "260"))
CAPTION_MAX_ATTEMPTS = 1
CAPTION_JSON_TEMPERATURE = min(1.0, max(0.0, float(os.getenv("CAPTION_JSON_TEMPERATURE", "0.72") or "0.72")))
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_CAPTION_MODEL = os.getenv("ANTHROPIC_CAPTION_MODEL", "claude-3-7-sonnet-latest").strip() or "claude-3-7-sonnet-latest"
ANTHROPIC_TIMEOUT_SECONDS = float(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", "50"))
CAPTION_VARIANT_COUNT = 1
HASHTAG_RE = re.compile(r"#[^\s#]+", re.UNICODE)
AI_SMELL_PHRASES = [
    "elevate your",
    "elevate",
    "discover the",
    "step into",
    "unlock the",
    "unlock your",
    "transform your",
    "take your",
    "next level",
    "whether you're",
    "ready to",
    "not just",
    "journey",
]
INTERNAL_WORKFLOW_PATTERNS = [
    r"\bwhatsapp\b",
    r"\bcarousel concept\b",
    r"\breel concept\b",
    r"\bimage post\b",
    r"\bcarousel\b",
    r"\breel\b",
    r"\bdraft\b",
    r"\bconcept\b",
]


def _truncate_text(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _truncate_list(values: Any, *, limit: int = 6, item_limit: int = 80) -> list[str]:
    if isinstance(values, list):
        items = values
    else:
        items = [values]
    output: list[str] = []
    for item in items:
        text = _truncate_text(item, item_limit)
        if text:
            output.append(text)
        if len(output) >= limit:
            break
    return output


def _emit_progress(progress_callback: Callable[[dict[str, Any]], Any] | None, event: str, **payload: Any) -> None:
    if not callable(progress_callback):
        return
    try:
        progress_callback({"event": event, **payload})
    except Exception:
        return


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


def _auto_close_truncated_json(fragment: str) -> str:
    """Attempt to close truncated JSON by appending missing delimiters.

    Walks the fragment tracking open braces, brackets, and string state,
    then appends the necessary closing characters in reverse order.
    Returns the repaired string or empty string if unrecoverable.
    """
    raw = str(fragment or "").strip()
    if not raw:
        return ""
    start = raw.find("{")
    if start == -1:
        return ""
    stack: list[str] = []
    in_string = False
    escape = False
    last_key_or_value = False
    for ch in raw[start:]:
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
                last_key_or_value = True
            continue
        if ch == '"':
            in_string = True
            last_key_or_value = False
            continue
        if ch == "{":
            stack.append("}")
            last_key_or_value = False
        elif ch == "[":
            stack.append("]")
            last_key_or_value = False
        elif ch == "}":
            if stack and stack[-1] == "}":
                stack.pop()
            last_key_or_value = True
        elif ch == "]":
            if stack and stack[-1] == "]":
                stack.pop()
            last_key_or_value = True
    if not stack:
        return ""
    repaired = raw[start:]
    if in_string:
        repaired += '"'
    closing = "".join(reversed(stack))
    repaired += closing
    try:
        json.loads(repaired)
        return repaired
    except Exception:
        pass
    repaired_with_null = raw[start:]
    if in_string:
        repaired_with_null += '"'
    trail = repaired_with_null.rstrip()
    if trail and trail[-1] in (",", ":"):
        repaired_with_null += "null"
    repaired_with_null += closing
    try:
        json.loads(repaired_with_null)
        return repaired_with_null
    except Exception:
        return ""


def _build_openrouter_client() -> OpenAI | None:
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        return None
    return build_sync_client("openrouter", timeout=CAPTION_TIMEOUT_SECONDS, max_retries=0)

def _build_groq_client() -> OpenAI | None:
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        return None
    return build_sync_client("groq", timeout=CAPTION_TIMEOUT_SECONDS, max_retries=0)

def _build_openai_client() -> OpenAI | None:
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return None
    return build_sync_client("openai", timeout=CAPTION_TIMEOUT_SECONDS, max_retries=0)

def _build_nvidia_client() -> OpenAI | None:
    nvidia_key = str(os.getenv("NVIDIA_API_KEY") or "").strip()
    if not nvidia_key:
        return None
    return build_sync_client("nvidia", timeout=CAPTION_TIMEOUT_SECONDS, max_retries=0)



def _resolve_model_routes() -> list[tuple[str, OpenAI, str]]:
    routes: list[tuple[str, OpenAI, str]] = []
    seen: set[tuple[str, str]] = set()
    nvidia_client = _build_nvidia_client()
    openrouter_client = _build_openrouter_client()
    groq_client = _build_groq_client()
    openai_client = _build_openai_client()

    raw_models = [CAPTION_MODEL]
    if CAPTION_FALLBACK_MODEL:
        raw_models.append(CAPTION_FALLBACK_MODEL)

    for raw_model in raw_models:
        model_name = str(raw_model or "").strip()
        if not model_name:
            continue
        if model_name.startswith("groq:"):
            groq_model_name = model_name.split(":", 1)[1].strip()
            if not groq_client or not groq_model_name:
                continue
            route = ("groq", groq_model_name)
            if route in seen:
                continue
            seen.add(route)
            routes.append(("groq", groq_client, groq_model_name))
            continue
        if model_name.startswith("openrouter:"):
            openrouter_model_name = model_name.split(":", 1)[1].strip()
            if not openrouter_client or not openrouter_model_name:
                continue
            route = ("openrouter", openrouter_model_name)
            if route in seen:
                continue
            seen.add(route)
            routes.append(("openrouter", openrouter_client, openrouter_model_name))
            continue
        if model_name.startswith("nvidia/") and not model_name.endswith(":free"):
            if not nvidia_client:
                continue
            route = ("nvidia", model_name)
            if route in seen:
                continue
            seen.add(route)
            routes.append(("nvidia", nvidia_client, model_name))
            continue
        if "/" in model_name:
            if not openrouter_client:
                continue
            route = ("openrouter", model_name)
            if route in seen:
                continue
            seen.add(route)
            routes.append(("openrouter", openrouter_client, model_name))
            continue
        if groq_client:
            route = ("groq", model_name)
            if route not in seen:
                seen.add(route)
                routes.append(("groq", groq_client, model_name))
            continue
        if not openai_client:
            continue
        route = ("openai", model_name)
        if route in seen:
            continue
        seen.add(route)
        routes.append(("openai", openai_client, model_name))

    if not routes:
        raise RuntimeError("Missing usable caption model route. Configure NVIDIA_API_KEY, OPENROUTER_API_KEY, or OPENAI_API_KEY in .env")
    return routes


def _load_brand_profile_payload(client_name: str) -> dict[str, Any]:
    store = get_client_store()
    data = store.get_brand_profile(client_name)
    if not data:
        return {
            "status": "error",
            "message": f"No brand profile for {client_name}. Create one before running.",
        }
    return {"status": "success", "brand_data": data}


def _extract_caption_json(output: str) -> dict[str, Any]:
    clean_output = (output or "").strip()
    if clean_output.startswith("```json"):
        clean_output = clean_output[7:]
    if clean_output.startswith("```"):
        clean_output = clean_output[3:]
    if clean_output.endswith("```"):
        clean_output = clean_output[:-3]
    clean_output = clean_output.strip()

    try:
        return json.loads(clean_output)
    except Exception:
        pass

    start = clean_output.find("{")
    if start == -1:
        raise ValueError("No JSON object found in caption response")
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(clean_output)):
        ch = clean_output[index]
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
                return json.loads(clean_output[start:index + 1])

    # Truncated JSON — attempt auto-close repair before giving up
    repaired = _auto_close_truncated_json(clean_output[start:])
    if repaired:
        try:
            return json.loads(repaired)
        except Exception:
            pass
    raise ValueError("Unterminated JSON object in caption response")


def _strip_reasoning_blocks(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"<think>.*?</think>", " ", value, flags=re.DOTALL | re.IGNORECASE)
    value = re.sub(r"```json", "```", value, flags=re.IGNORECASE)
    return value.strip()


def _response_format_not_supported(exc: Exception) -> bool:
    lowered = str(exc or "").lower()
    indicators = [
        "response_format",
        "json_schema",
        "json object",
        "json_object",
        "not supported",
        "unsupported",
        "invalid parameter",
        "unknown parameter",
    ]
    return any(item in lowered for item in indicators)


def _build_hook_json_schema() -> dict[str, Any]:
    return {
        "name": "caption_hooks_response",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["hooks"],
            "properties": {
                "hooks": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": CAPTION_VARIANT_COUNT,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["variant_id", "hook_style", "hook_text", "rationale"],
                        "properties": {
                            "variant_id": {"type": "string"},
                            "hook_style": {"type": "string"},
                            "hook_text": {"type": "string"},
                            "rationale": {"type": "string"},
                        },
                    },
                }
            },
        },
    }


def _build_variant_json_schema() -> dict[str, Any]:
    return {
        "name": "caption_variants_response",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["variants"],
            "properties": {
                "variants": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": CAPTION_VARIANT_COUNT,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "variant_id",
                            "selected_hook_family",
                            "hook_text",
                            "caption",
                            "hashtags",
                            "seo_keyword_used",
                            "direction_label",
                            "rationale",
                        ],
                        "properties": {
                            "variant_id": {"type": "string"},
                            "selected_hook_family": {"type": "string"},
                            "hook_text": {"type": "string"},
                            "caption": {"type": "string"},
                            "hashtags": {"type": "array", "items": {"type": "string"}},
                            "seo_keyword_used": {"type": "string"},
                            "direction_label": {"type": "string"},
                            "rationale": {"type": "string"},
                        },
                    },
                }
            },
        },
    }


def _request_json_completion(
    client: OpenAI,
    *,
    candidate_model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    use_json_mode: bool,
    response_schema: dict[str, Any] | None = None,
) -> Any:
    request_kwargs: dict[str, Any] = {
        "model": candidate_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": CAPTION_JSON_TEMPERATURE,
        "max_tokens": max_tokens,
    }
    if use_json_mode:
        if response_schema:
            request_kwargs["response_format"] = {"type": "json_schema", "json_schema": response_schema}
        else:
            request_kwargs["response_format"] = {"type": "json_object"}
    return client.chat.completions.create(**request_kwargs)


def _repair_json_response(
    client: OpenAI,
    *,
    candidate_model: str,
    system_prompt: str,
    raw_content: str,
    max_tokens: int,
    response_schema: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    repair_system_prompt = (
        "You are a strict JSON repair formatter. Return exactly one valid JSON object and nothing else. "
        "Do not add prose, markdown fences, or commentary."
    )
    # Keep the repair prompt lean — only send a short schema hint and the raw content,
    # not the full original system prompt which can be thousands of tokens.
    schema_hint = ""
    if response_schema:
        required = (response_schema.get("schema") or {}).get("required") or []
        schema_hint = f"Required top-level keys: {', '.join(required)}.\n" if required else ""
    repair_user_prompt = (
        f"{schema_hint}"
        f"Malformed model output (may be truncated):\n{raw_content[:1200]}\n\n"
        "Repair the malformed output into a single valid JSON object. "
        "Close any truncated strings, arrays, or objects. "
        "If the output is unusable, return {}."
    )
    response = _request_json_completion(
        client,
        candidate_model=candidate_model,
        system_prompt=repair_system_prompt,
        user_prompt=repair_user_prompt,
        max_tokens=max(200, min(max_tokens, CAPTION_RESPONSE_MAX_TOKENS * 2)),
        use_json_mode=True,
        response_schema=response_schema,
    )
    repaired_content = _strip_reasoning_blocks(response.choices[0].message.content or "")
    return _extract_caption_json(repaired_content), repaired_content


def normalize_caption_payload(output: dict) -> dict:
    payload = dict(output or {})
    caption = str(payload.get("caption") or "").strip()

    raw_hashtags = payload.get("hashtags", [])
    if not isinstance(raw_hashtags, list):
        raw_hashtags = []

    extracted = HASHTAG_RE.findall(caption)
    merged = normalize_hashtag_list(raw_hashtags + extracted)

    if extracted:
        caption = HASHTAG_RE.sub("", caption)
        caption = re.sub(r"[ \t]+", " ", caption)
        caption = re.sub(r"\n\s*\n\s*\n+", "\n\n", caption)
        caption = "\n".join(line.strip() for line in caption.splitlines())
        caption = caption.strip(" \n-")
    caption = re.sub(r"^[\s:：؛،,.\-–—]+", "", caption).strip()

    raw_status = str(payload.get("status") or "success").strip()
    normalized_status = raw_status.lower()
    if normalized_status in {"success", "published", "ready", "done", "complete", "completed", "ok"}:
        normalized_status = "success"
    elif raw_status in {"نشر", "تم", "جاهز", "مكتمل", "نجاح"}:
        normalized_status = "success"
    elif normalized_status in {"held_for_review", "hold", "review"}:
        normalized_status = "held_for_review"
    else:
        normalized_status = normalized_status or "success"

    payload["caption"] = caption.strip()
    payload["hashtags"] = merged[:7]
    payload["seo_keyword_used"] = str(payload.get("seo_keyword_used") or "").strip()
    payload["status"] = normalized_status
    return payload


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _dedupe_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in values:
        normalized = str(item or "").strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(normalized)
    return output


def _strip_internal_workflow_labels(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for pattern in INTERNAL_WORKFLOW_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -:,.")
    return text


def _filter_trend_terms(values: list[str], language_mode: str = "") -> list[str]:
    output: list[str] = []
    banned = {phrase.lower() for phrase in AI_SMELL_PHRASES}
    for item in values:
        text = _strip_internal_workflow_labels(item)
        if not text:
            continue
        lowered = text.lower()
        if any(phrase in lowered for phrase in banned):
            continue
        if len(text.split()) > 10:
            continue
        if re.search(r"[{}<>]|```|^\W+$", text):
            continue
        if language_mode == "arabic" and not re.search(r"[\u0600-\u06FF]", text) and len(text.split()) > 3:
            continue
        output.append(text)
    return _dedupe_list(output)


def _normalize_caption_mode(value: str) -> str:
    lowered = str(value or "").strip().lower()
    return lowered if lowered in {"generate", "revise"} else "generate"


def _compact_caption_profile(brand_data: dict[str, Any]) -> dict[str, Any]:
    data = dict(brand_data or {})
    profile = data.get("caption_profile")
    if not isinstance(profile, dict):
        profile = {}

    voice = data.get("brand_voice") or {}
    tone = str(voice.get("tone") or "").strip()
    style = str(voice.get("style") or "").strip()
    dialect = str(voice.get("dialect") or "").strip()
    examples = data.get("brand_voice_examples") or []
    if not isinstance(examples, list):
        examples = []
    rules = [item for item in [
        f"Tone: {tone}" if tone else "",
        f"Style: {style}" if style else "",
        f"Dialect: {dialect}" if dialect else "",
        *(str(item).strip() for item in examples[:2]),
    ] if item]
    services = data.get("services") or []
    if not isinstance(services, list):
        services = []
    website_digest = data.get("website_digest") or {}
    if not isinstance(website_digest, dict):
        website_digest = {}
    trend_dossier = data.get("trend_dossier") or {}
    if not isinstance(trend_dossier, dict):
        trend_dossier = {}
    raw_source_links = trend_dossier.get("source_link_details") or trend_dossier.get("source_links") or []
    normalized_source_links = []
    if isinstance(raw_source_links, list):
        for item in raw_source_links[:8]:
            if isinstance(item, dict):
                url = str(item.get("url") or "").strip()
                if not url:
                    continue
                normalized_source_links.append(
                    {
                        "title": str(item.get("title") or item.get("label") or "Source").strip(),
                        "url": url,
                        "published_at": str(item.get("published_at") or "").strip(),
                    }
                )
            else:
                url = str(item or "").strip()
                if url:
                    normalized_source_links.append({"title": "Source", "url": url, "published_at": ""})
    profile_trend = profile.get("trend_dossier") or {}
    if not isinstance(profile_trend, dict):
        profile_trend = {}
    merged_trend = dict(profile_trend)
    for key, value in {
        "status": str(trend_dossier.get("status") or "").strip(),
        "provider": str(trend_dossier.get("provider") or "").strip(),
        "recency_days": trend_dossier.get("recency_days") or 30,
        "source_coverage": str(trend_dossier.get("source_coverage") or "").strip(),
        "recent_signals": [str(item).strip() for item in (trend_dossier.get("recent_signals") or [])[:12] if str(item).strip()],
        "trend_angles": trend_dossier.get("trend_angles") if isinstance(trend_dossier.get("trend_angles"), list) else [],
        "hook_patterns": [str(item).strip() for item in (trend_dossier.get("hook_patterns") or [])[:8] if str(item).strip()],
        "hashtag_candidates": [str(item).strip() for item in (trend_dossier.get("hashtag_candidates") or [])[:12] if str(item).strip()],
        "topical_language": [str(item).strip() for item in (trend_dossier.get("topical_language") or [])[:12] if str(item).strip()],
        "anti_cliche_guidance": [str(item).strip() for item in (trend_dossier.get("anti_cliche_guidance") or [])[:8] if str(item).strip()],
        "source_links": normalized_source_links,
        "fetched_at": str(trend_dossier.get("fetched_at") or "").strip(),
        "expires_at": str(trend_dossier.get("expires_at") or "").strip(),
    }.items():
        if _has_value(value):
            merged_trend[key] = value

    merged_profile = {
        "business_name": str(profile.get("business_name") or data.get("business_name") or data.get("client_name") or "").strip(),
        "industry": str(profile.get("industry") or data.get("industry") or "general").strip(),
        "main_language": str(profile.get("main_language") or data.get("main_language") or "").strip(),
        "city_market": str(profile.get("city_market") or data.get("city_market") or data.get("market") or data.get("location") or "").strip(),
        "audience_summary": str(profile.get("audience_summary") or data.get("target_audience") or "").strip(),
        "offer_summary": str(profile.get("offer_summary") or ", ".join(str(item).strip() for item in services[:6] if str(item).strip())).strip(),
        "voice_rules": _dedupe_list([*(profile.get("voice_rules") or []), *rules])[:8],
        "do_avoid_rules": _dedupe_list(
            [*(profile.get("do_avoid_rules") or []), *(str(item).strip() for item in (data.get("dos_and_donts") or []) if str(item).strip()), *(str(item).strip() for item in (data.get("banned_words") or []) if str(item).strip())]
        )[:10],
        "seo_keywords": _dedupe_list([*(profile.get("seo_keywords") or []), *(str(item).strip() for item in (data.get("seo_keywords") or []) if str(item).strip())])[:8],
        "language_profile": profile.get("language_profile") or data.get("language_profile") or {},
        "website_digest": {
            "title": str((profile.get("website_digest") or {}).get("title") or website_digest.get("title") or "").strip(),
            "meta_description": str((profile.get("website_digest") or {}).get("meta_description") or website_digest.get("meta_description") or "").strip(),
            "headings": _dedupe_list([*(((profile.get("website_digest") or {}).get("headings")) or []), *(str(item).strip() for item in (website_digest.get("headings") or []) if str(item).strip())])[:8],
            "service_terms": _dedupe_list([*(((profile.get("website_digest") or {}).get("service_terms")) or []), *(str(item).strip() for item in (website_digest.get("service_terms") or []) if str(item).strip())])[:8],
            "brand_keywords": _dedupe_list([*(((profile.get("website_digest") or {}).get("brand_keywords")) or []), *(str(item).strip() for item in (website_digest.get("brand_keywords") or []) if str(item).strip())])[:8],
        },
        "trend_dossier": merged_trend,
        "cta_style": str(profile.get("cta_style") or (data.get("caption_defaults") or {}).get("cta_style") or "Clear, premium, direct, and conversion-aware.").strip(),
    }
    return merged_profile


def _resolve_caption_language(brand_data: dict[str, Any]) -> str:
    main_language = str(brand_data.get("main_language") or "").strip().lower()
    if main_language in {"arabic", "english"}:
        return main_language
    language_profile = brand_data.get("language_profile") or {}
    caption_language = str(language_profile.get("caption_output_language") or "").strip().lower()
    primary_language = str(language_profile.get("primary_language") or "").strip().lower()
    resolved = caption_language or primary_language
    if resolved in {"arabic", "english"}:
        return resolved
    return "english"


def _language_directive(language_mode: str) -> str:
    if language_mode == "arabic":
        return (
            "FIRST DIRECTIVE: Write the entire output exclusively in Arabic, including the caption, hook, CTA, and every hashtag. "
            "Do not switch to English even if the topic, brief, or source material is in English."
        )
    return "FIRST DIRECTIVE: Write the entire output exclusively in English, including the caption, hook, CTA, and every hashtag."


def _align_profile_language(profile_payload: dict[str, Any], language_mode: str) -> dict[str, Any]:
    aligned = dict(profile_payload or {})
    language_profile = dict(aligned.get("language_profile") or {})
    aligned["main_language"] = language_mode
    if language_mode == "arabic":
        language_profile["primary_language"] = "arabic"
        language_profile["caption_output_language"] = "arabic"
        if not str(language_profile.get("arabic_mode") or "").strip():
            language_profile["arabic_mode"] = "gulf"
    else:
        language_profile["primary_language"] = "english"
        language_profile["caption_output_language"] = "english"
        language_profile["arabic_mode"] = ""
    aligned["language_profile"] = language_profile
    return aligned


def _split_terms(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raw = str(value or "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _repair_anchors(profile_payload: dict[str, Any]) -> dict[str, list[str]]:
    trend = profile_payload.get("trend_dossier") or {}
    if not isinstance(trend, dict):
        trend = {}
    return {
        "brand": [str(profile_payload.get("business_name") or "").strip()],
        "market": [str(profile_payload.get("city_market") or "").strip()],
        "offers": _split_terms(profile_payload.get("offer_summary"))[:5],
        "keywords": _split_terms(profile_payload.get("seo_keywords"))[:5] or [str(item).strip() for item in (trend.get("topical_language") or [])[:5] if str(item).strip()],
    }


def _build_repair_context(
    *,
    failure_list: list[str],
    quality: dict[str, Any],
    profile_payload: dict[str, Any],
    previous_candidate: dict[str, Any],
    attempt_index: int,
) -> str:
    dimensions = dict(quality.get("dimensions") or {})
    anchors = _repair_anchors(profile_payload)
    previous_caption = str(previous_candidate.get("caption") or "").strip()
    score = quality.get("score")
    threshold = quality.get("threshold")

    directives: list[str] = [
        "Rewrite from scratch. Do not lightly edit the previous draft.",
        f"Last score: {score}/{threshold}. The next pass must materially improve the weak dimensions.",
        "Do not use internal workflow labels such as WhatsApp, carousel concept, reel concept, draft, or image post.",
        "Use natural brand phrasing. Do not repeat the exact brand name awkwardly in the opening.",
    ]
    if previous_caption:
        directives.append(f"Do not reuse this opening or sentence structure: {previous_caption[:220]}")
    if float(dimensions.get("voice_similarity") or 0) < 70:
        if anchors["brand"][0]:
            directives.append(f"Explicitly anchor the caption to the brand name: {anchors['brand'][0]}.")
        if anchors["market"][0]:
            directives.append(f"Explicitly anchor the caption to the market or city: {anchors['market'][0]}.")
        if anchors["offers"]:
            directives.append(f"Name at least one real offer or product clearly: {', '.join(anchors['offers'][:3])}.")
    if float(dimensions.get("specificity") or 0) < 70:
        directives.append("Add one concrete product, seasonal, or local detail instead of generic hype.")
        if anchors["keywords"]:
            directives.append(f"Work in one real topical term naturally: {', '.join(anchors['keywords'][:3])}.")
    if str(profile_payload.get("main_language") or "").strip().lower() == "arabic":
        directives.append("Write in culturally native Arabic. Avoid mixed English workflow wording unless it is a real menu item.")
    if float(dimensions.get("engagement_potential") or 0) < 70:
        directives.append("Use a stronger first-line hook: a sharp question, bold statement, or culturally native prompt.")
    if float(dimensions.get("humanizer") or 0) < 80:
        directives.append("Use shorter, more natural sentences. Remove promotional fluff, generic CTAs, and templated rhythm.")
    if attempt_index >= 2:
        directives.append("Be more decisive and direct on this pass. Prioritize clarity and specificity over flourish.")

    bullets = "\n- ".join(item for item in failure_list if item)
    if bullets:
        directives.append(f"Fix these specific issues:\n- {bullets}")

    return "\n".join(directives)


def _normalize_topic_phrase(topic: str) -> str:
    raw = _strip_internal_workflow_labels(topic)
    if not raw:
        return ""
    lowered = raw.lower()
    if "iced chocolate" in lowered:
        return "iced chocolate"
    return raw


def _build_scaffold_repair_candidate(
    profile_payload: dict[str, Any],
    *,
    topic: str,
    language_mode: str,
) -> dict[str, Any]:
    brand = str(profile_payload.get("business_name") or "").strip() or "the brand"
    market = str(profile_payload.get("city_market") or "").strip() or "the market"
    offers = _split_terms(profile_payload.get("offer_summary"))
    sanitized_topic = _normalize_topic_phrase(topic)
    offer = offers[0] if offers else sanitized_topic or "the new drop"
    secondary_offer = offers[1] if len(offers) > 1 else ""
    tertiary_offer = offers[2] if len(offers) > 2 else ""
    topic_phrase = sanitized_topic or offer
    audience_summary = str(profile_payload.get("audience_summary") or "").strip()
    audience_hook = ""
    audience_context = ""
    audience_lower = audience_summary.lower()
    if "student" in audience_lower:
        audience_hook = "للطلاب"
        audience_context = "بين الجامعة"
    if "professional" in audience_lower or "work" in audience_lower or "office" in audience_lower:
        audience_hook = f"{audience_hook} وناس الدوام".strip()
        audience_context = "بين الدوام والجامعة" if audience_context else "بعد الدوام"
    if not audience_hook:
        audience_hook = "للي يدور وقفة مرتبة"
    if not audience_context:
        audience_context = f"في {market}"

    media_type = str(profile_payload.get("_fallback_media_type") or "").strip()
    variation_seed = 0
    if media_type == "video":
        variation_seed = 2
    elif media_type == "carousel":
        variation_seed = 1

    if language_mode == "arabic":
        if variation_seed == 2:
            caption = (
                f"إذا كنت تدور على وقفة أخف في {market}، فـ {brand} يقدّم {offer}"
                f"{f' مع {secondary_offer}' if secondary_offer else ''}"
                f" بصياغة أقرب لذوق {audience_hook}. نكهة واضحة، إيقاع أسرع، وحضور يناسب يومك {audience_context}."
            )
        elif variation_seed == 1:
            caption = (
                f"بين {audience_context}، يطلع {offer} من {brand} كخيار أهدأ وأوضح."
                f"{f' ومعه {secondary_offer}' if secondary_offer else ''}"
                f" الطعم مرتب، والإحساس محلي، والنتيجة تجربة تنفع لحر {market} بدون مبالغة."
            )
        else:
            caption = (
                f"في {market}، {brand} يقرّب لك {offer}"
                f"{f' و{secondary_offer}' if secondary_offer else ''}"
                f"{f' وحتى {tertiary_offer}' if tertiary_offer else ''}"
                f" بروح أوضح وأقرب لناس {audience_hook}. جرّبه كوقفتك السريعة إذا كنت تبي شيء مرتب وطعمه حاضر."
            )
        hashtags = [
            f"#{brand.replace(' ', '')}",
            "#KuwaitCity",
            "#IcedChocolate",
            "#IcedDrinks",
            "#قهوة_مختصة",
            "#مشروب_بارد",
        ]
    else:
        if variation_seed == 2:
            caption = (
                f"For a cleaner reset in {market}, {brand} is leaning into {offer}"
                f"{f' with {secondary_offer}' if secondary_offer else ''}"
                f" in a way that feels sharper, lighter, and more local to the day-to-day crowd."
            )
        elif variation_seed == 1:
            caption = (
                f"{offer} from {brand} lands with a more grounded local feel in {market}."
                f"{f' {secondary_offer.capitalize()} backs it up.' if secondary_offer else ''}"
                f" The angle is simple: strong flavor, cleaner positioning, and an easier everyday pull."
            )
        else:
            caption = (
                f"{brand} is putting {offer}"
                f"{f', {secondary_offer}' if secondary_offer else ''}"
                f"{f', and {tertiary_offer}' if tertiary_offer else ''}"
                f" into a sharper market-ready frame for {market}, built for people who want something cleaner and more memorable."
            )
        hashtags = [
            f"#{brand.replace(' ', '')}",
            "#KuwaitCity",
            "#IcedChocolate",
            "#IcedDrinks",
            "#SpecialtyCoffee",
            "#LocalBrand",
        ]

    return {
        "caption": caption,
        "hashtags": hashtags,
        "seo_keyword_used": topic_phrase,
        "status": "success",
        "provider": "scaffold_repair",
        "model": "template",
    }


def _build_prompt_profile(profile_payload: dict[str, Any]) -> dict[str, Any]:
    trend_dossier = profile_payload.get("trend_dossier") or {}
    if not isinstance(trend_dossier, dict):
        trend_dossier = {}
    website_digest = profile_payload.get("website_digest") or {}
    if not isinstance(website_digest, dict):
        website_digest = {}
    language_profile = profile_payload.get("language_profile") or {}
    if not isinstance(language_profile, dict):
        language_profile = {}

    raw_trend_angles = trend_dossier.get("trend_angles") or []
    summarized_angles: list[str] = []
    if isinstance(raw_trend_angles, list):
        for item in raw_trend_angles[:4]:
            if isinstance(item, dict):
                label = _truncate_text(
                    item.get("angle")
                    or item.get("title")
                    or item.get("hook")
                    or item.get("summary")
                    or "",
                    110,
                )
            else:
                label = _truncate_text(item, 110)
            if label:
                summarized_angles.append(label)

    topical_language = _filter_trend_terms(
        _truncate_list(trend_dossier.get("topical_language") or [], limit=6, item_limit=35),
        str(profile_payload.get("main_language") or "").strip().lower(),
    )
    hashtag_candidates = _filter_trend_terms(
        _truncate_list(trend_dossier.get("hashtag_candidates") or [], limit=8, item_limit=35),
        "",
    )
    anti_cliche_guidance = _filter_trend_terms(
        _truncate_list(trend_dossier.get("anti_cliche_guidance") or [], limit=5, item_limit=85),
        "",
    )

    return {
        "business_name": _truncate_text(profile_payload.get("business_name"), 80),
        "industry": _truncate_text(profile_payload.get("industry"), 40),
        "main_language": _truncate_text(profile_payload.get("main_language"), 20),
        "city_market": _truncate_text(profile_payload.get("city_market"), 60),
        "audience_summary": _truncate_text(profile_payload.get("audience_summary"), 140),
        "offer_summary": _truncate_text(profile_payload.get("offer_summary"), 180),
        "voice_rules": _truncate_list(profile_payload.get("voice_rules") or [], limit=5, item_limit=90),
        "do_avoid_rules": _truncate_list(profile_payload.get("do_avoid_rules") or [], limit=6, item_limit=70),
        "seo_keywords": _truncate_list(profile_payload.get("seo_keywords") or [], limit=6, item_limit=35),
        "language_profile": {
            "primary_language": _truncate_text(language_profile.get("primary_language"), 20),
            "caption_output_language": _truncate_text(language_profile.get("caption_output_language"), 20),
            "arabic_mode": _truncate_text(language_profile.get("arabic_mode"), 20),
        },
        "website_digest": {
            "title": _truncate_text(website_digest.get("title"), 90),
            "meta_description": _truncate_text(website_digest.get("meta_description"), 160),
            "headings": _truncate_list(website_digest.get("headings") or [], limit=4, item_limit=80),
            "service_terms": _truncate_list(website_digest.get("service_terms") or [], limit=6, item_limit=40),
            "brand_keywords": _truncate_list(website_digest.get("brand_keywords") or [], limit=6, item_limit=35),
        },
        "trend_dossier": {
            "status": _truncate_text(trend_dossier.get("status"), 24),
            "provider": _truncate_text(trend_dossier.get("provider"), 24),
            "recent_signals": _truncate_list(trend_dossier.get("recent_signals") or [], limit=5, item_limit=120),
            "trend_angles": summarized_angles,
            "hook_patterns": _truncate_list(trend_dossier.get("hook_patterns") or [], limit=5, item_limit=80),
            "hashtag_candidates": hashtag_candidates,
            "topical_language": topical_language,
            "anti_cliche_guidance": anti_cliche_guidance,
        },
        "cta_style": _truncate_text(profile_payload.get("cta_style"), 100),
    }


def _build_anchor_requirements(profile_payload: dict[str, Any]) -> str:
    business_name = str(profile_payload.get("business_name") or "").strip()
    market = str(profile_payload.get("city_market") or "").strip()
    offers = _split_terms(profile_payload.get("offer_summary"))[:4]
    voice_rules = [str(item).strip() for item in (profile_payload.get("voice_rules") or [])[:4] if str(item).strip()]
    trend = profile_payload.get("trend_dossier") or {}
    if not isinstance(trend, dict):
        trend = {}
    hook_patterns = _filter_trend_terms([str(item).strip() for item in (trend.get("hook_patterns") or [])[:3] if str(item).strip()], str(profile_payload.get("main_language") or "").strip().lower())
    topical_terms = _filter_trend_terms([str(item).strip() for item in (trend.get("topical_language") or [])[:4] if str(item).strip()], str(profile_payload.get("main_language") or "").strip().lower())
    banned = [str(item).strip() for item in (profile_payload.get("do_avoid_rules") or [])[:8] if str(item).strip()]

    lines = [
        "Required anchors for this draft:",
        f"- Mention the brand name exactly as: {business_name}" if business_name else "- Mention the brand name clearly.",
        f"- Mention the market/city clearly: {market}" if market else "- Mention the real market/city if relevant.",
        f"- Mention one real offer/product from this list: {', '.join(offers)}" if offers else "- Mention one real offer or product from the client profile.",
        "- Open with a sharp question or line that feels native to the market, not generic.",
        "- End with one short CTA that fits a premium coffee brand.",
        "- Do not invent prices, discounts, or claims unless they are explicitly in the profile.",
    ]
    if voice_rules:
        lines.append(f"- Match this voice exactly: {' | '.join(voice_rules)}")
    if hook_patterns:
        lines.append(f"- Useful hook direction: {' | '.join(hook_patterns)}")
    if topical_terms:
        lines.append(f"- Useful topical terms: {' | '.join(topical_terms)}")
    if banned:
        lines.append(f"- Avoid these words/phrases: {', '.join(banned)}")
    return "\n".join(lines)


def _load_client_memory_examples(client_name: str, *, media_type_context: str, language_mode: str) -> list[dict[str, Any]]:
    bundles = dict((list_client_drafts(client_name) or {}).get("bundles") or {})
    examples: list[dict[str, Any]] = []
    for payload in bundles.values():
        if not isinstance(payload, dict):
            continue
        caption_text = str(payload.get("caption_text") or "").strip()
        if not caption_text:
            continue
        metadata = dict(payload.get("caption_metadata") or {})
        quality_gate = dict(metadata.get("quality_gate") or {})
        ranking_summary = dict(metadata.get("ranking_summary") or {})
        score = float(quality_gate.get("score") or ranking_summary.get("winner_score") or 0)
        passed = bool(quality_gate.get("passed")) or score >= 78.0 or str(payload.get("caption_status") or "").strip().lower() in {"approved", "published"}
        if not passed:
            continue
        bundle_type = str(payload.get("bundle_type") or "").strip()
        if media_type_context and bundle_type and bundle_type != media_type_context:
            continue
        examples.append(
            {
                "caption": _truncate_text(caption_text, 220),
                "direction_label": _truncate_text(metadata.get("display_direction") or ranking_summary.get("winner_variant_id"), 80),
                "selected_hook_family": _truncate_text(metadata.get("selected_hook_family"), 60),
                "media_kind": bundle_type,
                "language_mode": language_mode,
                "score": score,
            }
        )
    examples.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
    return examples[:3]


def _build_attempt_strategy(mode: str, attempt_index: int, language_mode: str) -> dict[str, str]:
    if mode == "revise":
        families = {
            1: {
                "label": "precision revise",
                "goal": "Preserve the strongest parts of the current caption while applying the requested changes cleanly.",
                "cta": "Use a more natural CTA that feels earned, not pasted on.",
            },
            2: {
                "label": "sharper revise",
                "goal": "Keep the same core idea but make it tighter, more premium, and more emotionally specific.",
                "cta": "End with a stronger but still natural call to action.",
            },
            3: {
                "label": "local refine",
                "goal": "Push harder into culturally native phrasing and local market relevance without sounding forced.",
                "cta": "Keep the CTA minimal and confident.",
            },
        }
    else:
        families = {
            1: {
                "label": "brand-safe premium",
                "goal": "Write a polished premium caption with a clean, appealing first line.",
                "cta": "Use a soft premium CTA.",
            },
            2: {
                "label": "hook-led punchier",
                "goal": "Find a sharper hook family with more pull, tension, and immediate curiosity.",
                "cta": "Use a higher-pull CTA without sounding spammy.",
            },
            3: {
                "label": "local emotional",
                "goal": "Make the caption feel more native, more local, and more emotionally specific to the audience moment.",
                "cta": "Use a short CTA that feels local and natural.",
            },
        }
    strategy = families.get(attempt_index, families[max(families)])
    if language_mode == "arabic":
        strategy = dict(strategy)
        strategy["goal"] += " Use natural Gulf-friendly Arabic rhythm and avoid awkward English-led openings."
    return strategy


def _build_anti_repeat_block(
    *,
    previous_caption: str,
    avoid_repeat_failures: list[str],
    current_caption: str,
) -> str:
    lines: list[str] = []
    prior = _truncate_text(previous_caption, 180)
    current = _truncate_text(current_caption, 180)
    if current:
        lines.append(f"- Do not repeat this current draft structure or opening: {current}")
    elif prior:
        lines.append(f"- Do not repeat this previously rejected draft structure or opening: {prior}")
    for item in [str(entry).strip() for entry in (avoid_repeat_failures or []) if str(entry).strip()][:4]:
        lines.append(f"- Avoid repeating this failure: {item}")
    return "\n".join(lines) if lines else "- No prior failure memory."


def _build_caption_technique_guidance(context: dict[str, Any]) -> str:
    snapshot = dict(context.get("technique_snapshot") or {})
    techniques = dict(snapshot.get("techniques") or {})
    playbook = dict(context.get("playbook") or {})
    language_mode = str((context.get("platform_strategy") or {}).get("language_mode") or "english").strip().lower()

    source_summary = [
        str(item).strip()
        for item in (snapshot.get("source_summary") or [])
        if str(item).strip()
    ][:5]

    hook_types = [
        str(item).strip()
        for item in (techniques.get("hook_types") or [])
        if str(item).strip()
    ][:6]
    search_rules = [
        str(item).strip()
        for item in (techniques.get("search_rules") or [])
        if str(item).strip()
    ][:3]
    carousel_rules = [
        str(item).strip()
        for item in (techniques.get("carousel_rules") or [])
        if str(item).strip()
    ][:3]
    reel_rules = [
        str(item).strip()
        for item in (techniques.get("reel_rules") or [])
        if str(item).strip()
    ][:3]
    caption_rules = [
        str(item).strip()
        for item in (techniques.get("caption_rules") or [])
        if str(item).strip()
    ][:4]
    cta_rules = [
        str(item).strip()
        for item in (techniques.get("cta_rules") or [])
        if str(item).strip()
    ][:3]
    arabic_rules = [
        str(item).strip()
        for item in (techniques.get("arabic_rules") or [])
        if str(item).strip()
    ][:3]
    variant_briefs = playbook.get("variant_briefs") or []
    family_notes = [
        f"{str(item.get('hook_style') or '').strip()}: {str(item.get('instruction') or '').strip()}"
        for item in variant_briefs
        if isinstance(item, dict) and (str(item.get("hook_style") or "").strip() or str(item.get("instruction") or "").strip())
    ][:4]

    lines = [
        "Current caption technique priorities:",
        "- The first line is the hook. Do not waste it on the brand name or a label prefix.",
        "- Lead with curiosity, contrast, story, how-to, or social proof depending on the media and brand voice.",
        "- Keep the opener short enough to survive caption truncation and worth tapping 'more' for.",
        "- Use relevant keywords and location cues naturally for Instagram search, not stuffed lists.",
        "- Make carousels feel like progression or a useful sequence; slide 1 must do the hook work.",
        "- For Reels, make the caption reinforce the first-second visual or spoken hook.",
        "- Keep the post human and specific. Avoid AI-slop phrasing, empty hype, and brand-name openers.",
        "- Write in a social cadence, not a brochure cadence: short hook, short body, short CTA.",
        "- Use sentence fragments when they sound natural. Do not force every line into a full sentence.",
        "- Vary sentence length. Avoid long strings of similarly paced full sentences.",
        "- Use one natural CTA and a small relevant hashtag set.",
    ]
    if source_summary:
        lines.append(f"- Current source cues: {' | '.join(source_summary)}")
    if hook_types:
        lines.append(f"- Hook families to favor: {' | '.join(hook_types)}")
    if search_rules:
        lines.append(f"- Search/SEO cues: {' | '.join(search_rules)}")
    if carousel_rules:
        lines.append(f"- Carousel cues: {' | '.join(carousel_rules)}")
    if reel_rules:
        lines.append(f"- Reel cues: {' | '.join(reel_rules)}")
    if caption_rules:
        lines.append(f"- Caption rules: {' | '.join(caption_rules)}")
    if cta_rules:
        lines.append(f"- CTA cues: {' | '.join(cta_rules)}")
    if language_mode == "arabic" and arabic_rules:
        lines.append(f"- Arabic cues: {' | '.join(arabic_rules)}")
    if family_notes:
        lines.append(f"- This draft's hook families: {' | '.join(family_notes)}")
    return "\n".join(lines)


def _build_platform_strategy(media_type: str, media_type_context: str, language_mode: str) -> dict[str, Any]:
    is_video = str(media_type_context or "").strip().lower() == "video" or media_type == "reel_post"
    is_carousel = str(media_type_context or "").strip().lower() == "image_carousel" or media_type == "carousel_post"
    return {
        "format": "video" if is_video else ("carousel" if is_carousel else "single_image"),
        "max_caption_length": 280 if is_video else (340 if is_carousel else 260),
        "hashtag_ceiling": 6,
        "cta_style": "conversation-starting" if is_video else "save/share focused",
        "language_mode": language_mode,
    }


def _build_frontier_context(
    *,
    client_name: str,
    topic: str,
    media_type: str,
    media_type_context: str,
    compact_profile: dict[str, Any],
    recent_captions: list[str],
    operator_brief: str,
    media_analysis: dict[str, Any],
    mode: str,
    current_caption: str,
    prior_best_caption: str,
    avoid_repeat_failures: list[str],
) -> dict[str, Any]:
    trend = dict(compact_profile.get("trend_dossier") or {})
    story_angles = []
    for raw in trend.get("trend_angles") or []:
        if isinstance(raw, dict):
            label = str(raw.get("angle") or raw.get("title") or raw.get("hook") or "").strip()
        else:
            label = str(raw or "").strip()
        label = _strip_internal_workflow_labels(label)
        if label:
            story_angles.append(label)
    story_angles = _dedupe_list(story_angles)[:4]
    hook_terms = _filter_trend_terms([*(trend.get("hook_patterns") or []), *(media_analysis.get("hook_opportunities") or [])], str(compact_profile.get("main_language") or ""))
    trend_terms = _filter_trend_terms([*(trend.get("topical_language") or []), *(trend.get("hashtag_candidates") or [])], str(compact_profile.get("main_language") or ""))
    technique_snapshot = get_caption_technique_snapshot_payload(force_refresh=False)
    client_memory_examples = _load_client_memory_examples(
        client_name,
        media_type_context=media_type_context,
        language_mode=str(compact_profile.get("main_language") or "english").lower(),
    )
    playbook = build_caption_playbook(
        profile=compact_profile,
        language_mode=str(compact_profile.get("main_language") or "english").lower(),
        media_analysis=media_analysis,
        attempt_label="brand-safe premium" if mode == "generate" else "precision revise",
        variant_count=CAPTION_VARIANT_COUNT,
    )
    return {
        "client_name": client_name,
        "content_goal": _strip_internal_workflow_labels(topic),
        "operator_brief": sanitize_operator_brief(_strip_internal_workflow_labels(operator_brief))[0],
        "profile": {
            "business_name": str(compact_profile.get("business_name") or client_name).strip(),
            "market": str(compact_profile.get("city_market") or "").strip(),
            "audience": str(compact_profile.get("audience_summary") or "").strip(),
            "offers": _split_terms(compact_profile.get("offer_summary"))[:5],
            "voice_rules": [str(item).strip() for item in (compact_profile.get("voice_rules") or []) if str(item).strip()][:5],
        },
        "platform_strategy": _build_platform_strategy(media_type, media_type_context, str(compact_profile.get("main_language") or "english").lower()),
        "media_analysis": media_analysis,
        "recent_captions": recent_captions[:5],
        "story_angles": story_angles or [str(media_analysis.get("story_arc") or "").strip()],
        "hook_terms": hook_terms[:6],
        "trend_terms": trend_terms[:8],
        "prompt_profile": _build_prompt_profile(compact_profile),
        "anchor_requirements": _build_anchor_requirements(compact_profile),
        "mode": mode,
        "playbook": playbook,
        "technique_snapshot": technique_snapshot,
        "client_memory_examples": client_memory_examples,
        "current_caption": _truncate_text(current_caption, 260),
        "prior_best_caption": _truncate_text(prior_best_caption, 260),
        "avoid_repeat_failures": [str(item).strip() for item in (avoid_repeat_failures or []) if str(item).strip()][:6],
    }


def _build_brand_voice_examples(client_name: str, language_mode: str, profile: dict[str, Any]) -> str:
    """Build few-shot brand voice examples for the unified prompt.

    Priority: recent approved drafts > playbook examples > inline fallback.
    These are STYLE references only — the model must never copy them.
    """
    # 1. Recent approved captions from draft store
    examples: list[str] = []
    try:
        bundles = list_client_drafts(client_name).get("bundles", {})
        for _name, payload in list(bundles.items())[-5:]:
            caption_text = str((payload or {}).get("caption_text") or "").strip()
            if caption_text and len(caption_text) > 30:
                examples.append(caption_text)
            if len(examples) >= 2:
                break
    except Exception:
        pass
    if examples:
        return (
            "(These are STYLE references ONLY. Do NOT copy phrases, structure, or wording. "
            "Write something completely fresh that matches only the tone and energy.)\n\n"
            + "\n\n".join(f"Style ref {i + 1}:\n{c}" for i, c in enumerate(examples))
        )
    # 2. Playbook examples for the language and industry
    playbook = build_caption_playbook(
        profile=profile,
        language_mode=language_mode,
        media_analysis={},
        attempt_label="brand-safe premium",
        variant_count=1,
    )
    playbook_examples = playbook.get("examples") or []
    if playbook_examples:
        return (
            "(These are STYLE references ONLY. Do NOT copy phrases, structure, or wording.)\n\n"
            + "\n\n".join(
                f"Style ref {i + 1} ({e.get('hook_style', '')}):\n{e.get('caption', '')}"
                for i, e in enumerate(playbook_examples[:3])
            )
        )
    return "No prior examples available. Write in a premium, locally grounded tone."


def _build_unified_caption_prompt(context: dict[str, Any], *, mode: str = "generate") -> tuple[str, str]:
    """Build a single unified prompt that produces one caption in one API call."""
    profile = context["profile"]
    strategy = context["platform_strategy"]
    media_analysis = context["media_analysis"]
    language_mode = str(strategy.get("language_mode") or "english")
    brand_name = str(profile.get("business_name") or context["client_name"]).strip()
    market = str(profile.get("market") or "").strip()
    offers = [str(item).strip() for item in (profile.get("offers") or []) if str(item).strip()]
    audience = str(profile.get("audience") or "").strip()
    voice_rules = [str(item).strip() for item in (profile.get("voice_rules") or []) if str(item).strip()]

    # Pick a RANDOM hook family from the playbook (never the same one twice in a row)
    playbook = dict(context.get("playbook") or {})
    variant_briefs = playbook.get("variant_briefs") or []
    hook_instruction = ""
    hook_style = ""
    if variant_briefs:
        brief = random.choice(variant_briefs)
        hook_style = str(brief.get("hook_style") or "").strip()
        hook_instruction = str(brief.get("instruction") or "").strip()

    # Brand voice few-shot examples
    brand_voice_examples = _build_brand_voice_examples(
        context["client_name"],
        language_mode,
        context.get("prompt_profile") or profile,
    )
    technique_guidance = _build_caption_technique_guidance(context)

    # Compact media description
    story_arc = str(media_analysis.get("story_arc") or "").strip()
    product_signals = [str(s).strip() for s in (media_analysis.get("product_signals") or []) if str(s).strip()]
    media_desc = f"{story_arc}. Visual cues: {', '.join(product_signals[:4]) or 'product-focused scene'}." if story_arc else "Product-focused visual content."

    # Mode directive
    mode_directive = ""
    if mode == "revise":
        current = str(context.get("current_caption") or "").strip()
        mode_directive = f"\nREVISE THIS DRAFT (keep what works, improve the rest):\n{current}\n" if current else ""

    system_prompt = (
        f"You are the caption writer for {brand_name}.\n"
        f"{_language_directive(language_mode)}\n\n"
        f"BRAND VOICE REFERENCE (match this energy and structure):\n{brand_voice_examples}\n\n"
        f"CAPTION TECHNIQUE GUIDE:\n{technique_guidance}\n\n"
        f"BRAND CONTEXT:\n"
        f"- Brand: {brand_name}\n"
        f"- Market: {market or 'not specified'}\n"
        f"- Offers: {', '.join(offers[:3]) or 'see profile'}\n"
        f"- Audience: {audience or 'not specified'}\n"
        + (f"- Voice rules: {'; '.join(voice_rules[:3])}\n" if voice_rules else "")
        + f"\nRULES:\n"
        f"- Open with a {hook_style or 'compelling'} hook: {hook_instruction or 'lead with tension, contrast, or a specific benefit — not the brand name'}\n"
        f"- Never begin the caption with a colon, dash, bullet, or other label prefix.\n"
        f"- Prefer 1 to 3 short lines when possible. Let the caption breathe with line breaks.\n"
        f"- Keep the opener punchy. If the first line can be a question or a bold fragment, use that.\n"
        f"- Mention at least one real offer or product naturally\n"
        f"- One short CTA at the end (visit, try, save, order — not generic hype)\n"
        f"- 3-5 relevant hashtags\n"
        f"- Do NOT open with the brand name\n"
        f"- Do NOT write like an essay or an ad paragraph. Make it feel native to Instagram.\n"
        f"- Do NOT use: elevate, unlock, journey, discover, transform, next level\n"
        f"- Write like a real social post, not a marketing template\n"
        f"\nReturn ONLY valid JSON with keys: caption, hashtags, hook_style, direction_label, seo_keyword_used\n"
        f"No markdown fences, no prose, no commentary."
    )
    # Build anti-repeat block from recent captions
    recent_captions = context.get("recent_captions") or []
    anti_repeat_block = ""
    if recent_captions:
        recent_lines = "\n".join(f"- {_truncate_text(c, 100)}" for c in recent_captions[:5])
        anti_repeat_block = (
            f"\nDO NOT REPEAT — these are recent captions already posted for this brand. "
            f"Your caption MUST use a completely different opening, structure, and angle:\n{recent_lines}\n"
        )

    user_prompt = (
        f"Write one UNIQUE caption for {brand_name}.\n"
        f"Content goal: {context['content_goal']}\n"
        f"Operator notes: {context['operator_brief'] or 'None provided'}\n"
        f"Media: {media_desc}\n"
        f"Format: {str(strategy.get('format') or 'single_image')}\n"
        + anti_repeat_block
        + mode_directive
    )
    return system_prompt, user_prompt


def _build_single_caption_schema() -> dict[str, Any]:
    """JSON schema for a single caption response."""
    return {
        "name": "single_caption_response",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["caption", "hashtags", "hook_style", "direction_label", "seo_keyword_used"],
            "properties": {
                "caption": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
                "hook_style": {"type": "string"},
                "direction_label": {"type": "string"},
                "seo_keyword_used": {"type": "string"},
            },
        },
    }


def _caption_word_set(text: str) -> set[str]:
    """Normalize a caption into a word set for overlap comparison."""
    cleaned = re.sub(r"[#@]\S+", "", str(text or ""))  # strip hashtags/mentions
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)  # strip punctuation
    return {w.lower() for w in cleaned.split() if len(w) >= 2}


def _is_duplicate(new_caption: str, recent_captions: list[str], threshold: float = 0.60) -> bool:
    """Return True if new_caption shares >threshold word overlap with any recent caption."""
    new_words = _caption_word_set(new_caption)
    if not new_words:
        return False
    for existing in recent_captions:
        existing_words = _caption_word_set(existing)
        if not existing_words:
            continue
        overlap = len(new_words & existing_words) / max(len(new_words), len(existing_words))
        if overlap >= threshold:
            return True
    return False


def _caption_has_substance(text: str) -> bool:
    """Return True if the text contains at least some real word characters.

    Rejects hashtag-only, punctuation-only, whitespace-only, and empty strings.
    """
    value = str(text or "").strip()
    # Must contain at least one Latin letter, Arabic letter, or digit
    return bool(re.search(r"[A-Za-z\u0600-\u06FF0-9]", value))


def _build_hook_generation_payload(context: dict[str, Any], *, attempt_index: int, failure_context: str = "") -> tuple[str, str]:
    strategy = context["platform_strategy"]
    playbook = dict(context.get("playbook") or {})
    technique_snapshot = dict(context.get("technique_snapshot") or {})
    client_memory_examples = list(context.get("client_memory_examples") or [])
    attempt_strategy = _build_attempt_strategy(
        _normalize_caption_mode(context.get("mode") or "generate"),
        attempt_index,
        str(strategy.get("language_mode") or "english"),
    )
    anti_repeat_block = _build_anti_repeat_block(
        previous_caption=str(context.get("prior_best_caption") or "").strip(),
        avoid_repeat_failures=list(context.get("avoid_repeat_failures") or []),
        current_caption=str(context.get("current_caption") or "").strip(),
    )
    system_prompt = (
        "You are generating opening hooks for high-performance social captions.\n"
        f"{_language_directive(str(strategy.get('language_mode') or 'english'))}\n"
        "Return JSON only with keys: hooks.\n"
        "Each hook must be an object with keys: variant_id, hook_style, hook_text, rationale.\n"
        f"Produce exactly {CAPTION_VARIANT_COUNT} hooks.\n"
        "Each hook must use a different hook family.\n"
        "Do not open with the brand name unless the assigned hook family explicitly calls for it.\n"
        "Keep each hook compressed, native, and worth reading before the brand appears.\n"
    )
    user_prompt = (
        f"Client: {context['client_name']}\n"
        f"Attempt Strategy: {json.dumps(attempt_strategy, ensure_ascii=False)}\n"
        f"Content Goal: {context['content_goal']}\n"
        f"Operator Brief: {context['operator_brief'] or 'None provided'}\n"
        f"Media Analysis JSON: {json.dumps(context['media_analysis'], ensure_ascii=False)}\n"
        f"Technique Snapshot JSON: {json.dumps(technique_snapshot, ensure_ascii=False)}\n"
        f"Client Memory Examples JSON: {json.dumps(client_memory_examples, ensure_ascii=False)}\n"
        f"Caption Playbook JSON: {json.dumps(playbook, ensure_ascii=False)}\n"
        f"Anti-Repeat Rules:\n{anti_repeat_block}\n"
        f"Repair Context:\n{failure_context or 'None. This is the first pass.'}\n"
        "Execution Rules:\n"
        "- Match each variant_id from the playbook variant briefs.\n"
        "- Keep hook_text short and sharp.\n"
        "- Every hook should feel different in energy and structure.\n"
        "- The hooks must feel native to the audience and platform.\n"
    )
    return system_prompt, user_prompt


def _build_caption_expansion_payload(
    context: dict[str, Any],
    *,
    hook_candidates: list[dict[str, Any]],
    attempt_index: int,
    failure_context: str = "",
) -> tuple[str, str]:
    strategy = context["platform_strategy"]
    attempt_strategy = _build_attempt_strategy(
        _normalize_caption_mode(context.get("mode") or "generate"),
        attempt_index,
        str(strategy.get("language_mode") or "english"),
    )
    system_prompt = (
        "You are expanding approved hook candidates into full social captions.\n"
        f"{_language_directive(str(strategy.get('language_mode') or 'english'))}\n"
        "Return JSON only with keys: variants.\n"
        "Each variant must be an object with keys: variant_id, selected_hook_family, hook_text, caption, hashtags, seo_keyword_used, direction_label, rationale.\n"
        f"Produce exactly {len(hook_candidates)} variants.\n"
        "Preserve the assigned hook family in the opening line.\n"
        "Do not copy the reference examples verbatim.\n"
        "Do not open with awkward mixed English-Arabic location-brand phrasing.\n"
        "Use one natural CTA only.\n"
    )
    # Keep the expansion prompt lean to maximise output token budget.
    # Technique snapshot and client memory examples are already reflected in the
    # hook candidates and playbook, so omit the full dumps here.
    compact_media = {
        k: context['media_analysis'][k]
        for k in ('analysis_summary', 'product_signals', 'hook_opportunities', 'story_arc')
        if k in context['media_analysis']
    }
    user_prompt = (
        f"Client: {context['client_name']}\n"
        f"Attempt Strategy: {json.dumps(attempt_strategy, ensure_ascii=False)}\n"
        f"Content Goal: {context['content_goal']}\n"
        f"Operator Brief: {context['operator_brief'] or 'None provided'}\n"
        f"Media Analysis JSON: {json.dumps(compact_media, ensure_ascii=False)}\n"
        f"Anchor Requirements:\n{context['anchor_requirements']}\n"
        f"Hook Candidates JSON: {json.dumps(hook_candidates, ensure_ascii=False)}\n"
        f"Repair Context:\n{failure_context or 'None. This is the first pass.'}\n"
        "Execution Rules:\n"
        "- Expand each hook into a complete caption while keeping the hook family intact.\n"
        "- Mention at least one real offer, market cue, audience use case, or visual cue naturally.\n"
        "- Make each caption feel like a real social post, not a template description.\n"
    )
    return system_prompt, user_prompt


def _parse_hook_payload(raw_payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_hooks = raw_payload.get("hooks") or []
    if not isinstance(raw_hooks, list):
        return []
    output: list[dict[str, Any]] = []
    seen_styles: set[str] = set()
    for index, item in enumerate(raw_hooks, start=1):
        if not isinstance(item, dict):
            continue
        hook_text = str(item.get("hook_text") or item.get("text") or "").strip()
        hook_style = str(item.get("hook_style") or item.get("style") or "").strip()
        if not hook_text or not hook_style:
            continue
        style_key = hook_style.lower()
        if style_key in seen_styles:
            continue
        seen_styles.add(style_key)
        output.append(
            {
                "variant_id": str(item.get("variant_id") or f"variant_{index}"),
                "hook_style": hook_style,
                "hook_text": _truncate_text(hook_text, 120),
                "rationale": _truncate_text(item.get("rationale"), 160),
            }
        )
        if len(output) >= CAPTION_VARIANT_COUNT:
            break
    return output


def _parse_variant_payload(raw_payload: dict[str, Any], client_name: str) -> list[dict[str, Any]]:
    raw_variants = raw_payload.get("variants") or []
    if not isinstance(raw_variants, list):
        return []
    output: list[dict[str, Any]] = []
    for index, item in enumerate(raw_variants, start=1):
        if not isinstance(item, dict):
            continue
        normalized = normalize_caption_payload(item)
        if not str(normalized.get("caption") or "").strip():
            continue
        normalized["client_name"] = client_name
        normalized["variant_id"] = str(item.get("variant_id") or f"variant_{index}")
        normalized["direction_label"] = _truncate_text(item.get("direction_label"), 80)
        normalized["rationale"] = _truncate_text(item.get("rationale"), 140)
        normalized["selected_hook_family"] = _truncate_text(item.get("selected_hook_family") or item.get("hook_style"), 60)
        normalized["hook_text"] = _truncate_text(item.get("hook_text"), 120)
        output.append(normalized)
    return output


def _call_model_json_payload(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int,
    response_schema: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    attempts: list[dict[str, Any]] = []
    last_error = ""
    model_routes = _resolve_model_routes()
    for attempt, (provider, client, candidate_model) in enumerate(model_routes, start=1):
        try:
            used_json_mode = True
            try:
                response = _request_json_completion(
                    client,
                    candidate_model=candidate_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    use_json_mode=True,
                    response_schema=response_schema,
                )
            except Exception as exc:
                if not _response_format_not_supported(exc):
                    raise
                used_json_mode = False
                response = _request_json_completion(
                    client,
                    candidate_model=candidate_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    use_json_mode=False,
                    response_schema=None,
                )
            content = response.choices[0].message.content or ""
            finish_reason = getattr(response.choices[0], "finish_reason", None) or ""
            cleaned_content = _strip_reasoning_blocks(content)

            # Detect output truncation via finish_reason
            was_truncated = finish_reason == "length"
            if was_truncated:
                print(
                    f"[caption_agent] OUTPUT TRUNCATED ({provider}/{candidate_model}, "
                    f"max_tokens={max_tokens}, finish_reason=length): "
                    f"{cleaned_content[:300]!r}...",
                    file=sys.stderr,
                )

            try:
                payload = _extract_caption_json(cleaned_content)
            except ValueError as parse_exc:
                # Log raw content on every parse failure for diagnostics
                print(
                    f"[caption_agent] RAW PARSE FAILURE ({provider}/{candidate_model}): "
                    f"{cleaned_content[:500]!r}",
                    file=sys.stderr,
                )

                # Try auto-close repair first (no API call needed)
                auto_closed = _auto_close_truncated_json(cleaned_content)
                if auto_closed:
                    try:
                        payload = json.loads(auto_closed)
                        attempts.append(
                            {
                                "provider": provider,
                                "model": candidate_model,
                                "attempt": attempt,
                                "status": "auto_closed_success",
                                "detail": "Truncated JSON recovered via auto-close",
                                "json_mode": used_json_mode,
                                "was_truncated": was_truncated,
                            }
                        )
                        return payload, attempts, ""
                    except Exception:
                        pass

                # Fall back to model-based repair
                try:
                    payload, repaired_content = _repair_json_response(
                        client,
                        candidate_model=candidate_model,
                        system_prompt=system_prompt,
                        raw_content=cleaned_content,
                        max_tokens=max_tokens,
                        response_schema=response_schema,
                    )
                    attempts.append(
                        {
                            "provider": provider,
                            "model": candidate_model,
                            "attempt": attempt,
                            "status": "repaired_success",
                            "detail": _truncate_text(repaired_content, 160),
                            "json_mode": used_json_mode,
                            "was_truncated": was_truncated,
                        }
                    )
                    return payload, attempts, ""
                except Exception:
                    raise parse_exc
            if payload:
                attempts.append(
                    {
                        "provider": provider,
                        "model": candidate_model,
                        "attempt": attempt,
                        "status": "success",
                        "json_mode": used_json_mode,
                        "was_truncated": was_truncated,
                    }
                )
                return payload, attempts, ""
            last_error = "Model response did not contain valid JSON."
            attempts.append(
                {
                    "provider": provider,
                    "model": candidate_model,
                    "attempt": attempt,
                    "status": "invalid_payload",
                    "detail": _truncate_text(cleaned_content, 160),
                    "json_mode": used_json_mode,
                }
            )
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            attempts.append(
                {
                    "provider": provider,
                    "model": candidate_model,
                    "attempt": attempt,
                    "status": "error",
                    "detail": _truncate_text(last_error, 220),
                }
            )
            if attempt < len(model_routes):
                time.sleep(2 ** (attempt - 1))
    return {}, attempts, last_error or "No usable model payload was returned."


def _call_anthropic_json_payload(system_prompt: str, user_prompt: str, *, max_tokens: int) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    anthropic_key = str(os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not anthropic_key:
        return {}, [], "Anthropic key not configured."
    try:
        response = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": anthropic_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": ANTHROPIC_CAPTION_MODEL,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=ANTHROPIC_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
        text_blocks = [str(item.get("text") or "") for item in (body.get("content") or []) if item.get("type") == "text"]
        payload = _safe_json_loads("\n".join(text_blocks))
        if payload:
            return payload, [{"provider": "anthropic", "model": ANTHROPIC_CAPTION_MODEL, "attempt": 1, "status": "success"}], ""
        return {}, [{"provider": "anthropic", "model": ANTHROPIC_CAPTION_MODEL, "attempt": 1, "status": "invalid_payload"}], "Anthropic payload did not contain valid JSON."
    except Exception as exc:
        return {}, [{"provider": "anthropic", "model": ANTHROPIC_CAPTION_MODEL, "attempt": 1, "status": "error", "detail": _truncate_text(f'{type(exc).__name__}: {exc}', 220)}], f"{type(exc).__name__}: {exc}"


def _call_text_model_hooks(system_prompt: str, user_prompt: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    payload, attempts, error = _call_model_json_payload(
        system_prompt,
        user_prompt,
        max_tokens=CAPTION_RESPONSE_MAX_TOKENS * 2,
        response_schema=_build_hook_json_schema(),
    )
    return _parse_hook_payload(payload), attempts, error


def _call_text_model_variants(system_prompt: str, user_prompt: str, client_name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    payload, attempts, error = _call_model_json_payload(
        system_prompt,
        user_prompt,
        max_tokens=CAPTION_RESPONSE_MAX_TOKENS * 3,
        response_schema=_build_variant_json_schema(),
    )
    variants = _parse_variant_payload(payload, client_name)
    if variants:
        provider = attempts[-1]["provider"] if attempts else "unknown"
        model = attempts[-1]["model"] if attempts else ""
        for variant in variants:
            variant["provider"] = provider
            variant["model"] = model
            variant["generation_source"] = "model_generated"
    return variants, attempts, error


def _build_fallback_variants(context: dict[str, Any]) -> list[dict[str, Any]]:
    profile = context["profile"]
    market = str(profile.get("market") or "").strip()
    audience = str(profile.get("audience") or "").strip()
    offers = [str(item).strip() for item in (profile.get("offers") or []) if str(item).strip()]
    brand = str(profile.get("business_name") or context["client_name"]).strip()
    media_analysis = dict(context.get("media_analysis") or {})
    media_format = str((context.get("platform_strategy") or {}).get("format") or "single_image").strip().lower()
    story_arc = str(media_analysis.get("story_arc") or "").strip()
    hook_terms = [str(item).strip() for item in (media_analysis.get("hook_opportunities") or []) if str(item).strip()]
    primary_offer = offers[0] if offers else context["content_goal"] or "the new release"
    secondary_offer = offers[1] if len(offers) > 1 else ""
    language_mode = str(context["platform_strategy"].get("language_mode") or "english").lower()
    variants: list[dict[str, Any]] = []
    if language_mode == "arabic":
        local_market = market or "الكويت"
        use_case = "بعد الدوام" if "professional" in audience.lower() else "في طلعاتك اليومية"
        if media_format == "carousel":
            candidates = [
                f"{brand} يجمع في هذا الكاروسيل بين {primary_offer} ولمسة أهدأ تناسب {local_market}. {secondary_offer and f'و{secondary_offer} يكمل المزاج لمن يبي تنويعًا مرتبًا.'}",
                f"من أول صورة لآخر رشفة، {brand} يقدّم {primary_offer} بشكل أهدأ وأغنى للي يدور وقفة مرتبة في {local_market}.",
                f"إذا كان مزاجك {use_case}، فـ {primary_offer} من {brand} يعطيك حضورًا أوضح ونكهة تشدّك بدون مبالغة.",
            ]
        elif media_format == "video":
            candidates = [
                f"هذا المشهد من {brand} يفتح لك {primary_offer} بإيقاع أخف ولمسة أوضح تناسب {local_market}.",
                f"لقطة سريعة، لكن أثرها أطول. {primary_offer} من {brand} يبان هنا بشكل يحرّك المزاج من أول ثانية.",
                f"إذا كنت تبي شيئًا يبرد يومك ويرفع المستوى، {brand} يقرّب لك {primary_offer} بطريقة أقرب لذوق {local_market}.",
            ]
        else:
            candidates = [
                f"{brand} يقدّم {primary_offer} بروح أهدأ وأوضح للي يبي شيئًا مرتبًا يناسب {local_market}.",
                f"لجلسة أخف وأذكى، {primary_offer} من {brand} يثبت حضوره من أول رشفة.",
                f"إذا كنت تدور على خيار أنظف للمزاج اليومي، {brand} يقرّب لك {primary_offer} بطريقة أقرب لذوقك.",
            ]
        hashtags = [f"#{brand.replace(' ', '')}", "#الكويت", "#قهوة_مختصة", "#مشروب_بارد", "#ايسد"]
    else:
        local_market = market or "the local market"
        use_case = audience or "everyday premium coffee routines"
        if media_format == "carousel":
            candidates = [
                f"Three frames, one clearer pull: {brand} is building this carousel around {primary_offer} with a sharper, more premium angle for {local_market}.",
                f"From the hero pour to the supporting details, {brand} gives {primary_offer} a cleaner story built for people who want more than generic coffee content.",
                f"If your audience wants a calmer but still premium reset, this {brand} carousel puts {primary_offer} into a story that feels grounded, local, and worth the swipe.",
            ]
        elif media_format == "video":
            candidates = [
                f"{brand} turns {primary_offer} into a motion-led premium moment that lands fast and still feels grounded in {local_market}.",
                f"This video gives {primary_offer} a sharper first-second hook, then lets the product do the rest.",
                f"For {use_case}, {brand} frames {primary_offer} as a cleaner, more immediate pull instead of another generic product clip.",
            ]
        else:
            candidates = [
                f"{brand} puts {primary_offer} into a cleaner, sharper frame for people in {local_market} who want something that actually feels premium.",
                f"If you want a more grounded everyday reset, {primary_offer} from {brand} lands with a clearer hook and a stronger finish.",
                f"{brand} gives {primary_offer} a more local, more specific angle built for people who care about detail, not filler.",
            ]
        hashtags = [f"#{brand.replace(' ', '')}", "#LocalBrand", "#SpecialtyCoffee", "#SeasonalDrop", "#MarketReady"]
    for index, text in enumerate(candidates[:CAPTION_VARIANT_COUNT], start=1):
        variants.append(
            {
                "caption": re.sub(r"\s+", " ", text.replace("None", "")).strip(),
                "hashtags": hashtags,
                "seo_keyword_used": primary_offer,
                "status": "success",
                "variant_id": f"fallback_{index}",
                "direction_label": story_arc or hook_terms[0] if hook_terms else (context["content_goal"] or primary_offer),
                "rationale": "Fallback variant generated from brand, offer, audience, market, and media context.",
                "provider": "local_fallback",
                "model": "template",
            }
        )
    return variants


def _humanize_variant(variant: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    caption = str(variant.get("caption") or "").strip()
    caption = re.sub(r"\b(whatsapp|carousel concept|reel concept|draft)\b", " ", caption, flags=re.IGNORECASE)
    caption = re.sub(r"\s+", " ", caption).strip()
    cleaned = dict(variant)
    cleaned["caption"] = caption
    return cleaned


def _promote_quality_gate(ranked_variants: list[dict[str, Any]]) -> dict[str, Any]:
    best = ranked_variants[0]
    quality = dict(best.get("quality_gate") or {})
    if not quality:
        return {"score": 0, "passed": False, "threshold": 78.0, "dimensions": {}, "dimension_weights": {}, "failures": [], "verdict": "Needs another pass", "notes": {}}
    return quality


def _annotate_provider_attempts(attempts: list[dict[str, Any]], *, stage: str, round_index: int) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for item in attempts:
        payload = dict(item or {})
        payload["stage"] = stage
        payload["round"] = round_index
        annotated.append(payload)
    return annotated


def generate_caption_payload(
    client_name: str,
    topic: str,
    media_type: str = "image_post",
    recent_captions: list[str] | None = None,
    progress_callback: Callable[[dict[str, Any]], Any] | None = None,
    *,
    operator_brief: str = "",
    media_type_context: str = "",
    media_assets: list[dict[str, Any]] | None = None,
    prior_hidden_variants: list[dict[str, Any]] | None = None,
    mode: str = "generate",
    current_caption: str = "",
    prior_best_caption: str = "",
    avoid_repeat_failures: list[str] | None = None,
) -> dict:
    profile_payload = _load_brand_profile_payload(client_name)
    if profile_payload.get("status") != "success":
        return {
            "caption": str(profile_payload.get("message") or "Brand profile missing."),
            "hashtags": [],
            "seo_keyword_used": "",
            "error": str(profile_payload.get("message") or "Brand profile missing."),
            "reason": str(profile_payload.get("message") or "Brand profile missing."),
            "status": "error",
            "client_name": client_name,
        }

    brand_data = dict(profile_payload["brand_data"] or {})
    language_mode = _resolve_caption_language(brand_data)
    compact_profile = _align_profile_language(_compact_caption_profile(brand_data), language_mode)
    trend_dossier = get_client_trend_dossier(client_name, goal=topic, campaign_context="", force_refresh=False)
    compact_profile["trend_dossier"] = trend_dossier
    recent_captions = [str(item).strip() for item in (recent_captions or []) if str(item).strip()][:5]
    sanitized_topic = _strip_internal_workflow_labels(topic)
    sanitized_brief, _brief_report = sanitize_operator_brief(_strip_internal_workflow_labels(operator_brief))
    compact_profile["_fallback_media_type"] = media_type_context or media_type
    _emit_progress(progress_callback, "media_analysis_started", client_name=client_name, media_type=media_type)
    media_analysis = analyze_media_bundle(
        client_name,
        media_assets or [],
        operator_brief=sanitized_brief,
        media_type_context=media_type_context or media_type,
    )
    generation_mode = _normalize_caption_mode(mode)
    failure_memory = [str(item).strip() for item in (avoid_repeat_failures or []) if str(item).strip()]
    context = _build_frontier_context(
        client_name=client_name,
        topic=sanitized_topic,
        media_type=media_type,
        media_type_context=media_type_context or media_type,
        compact_profile=compact_profile,
        recent_captions=recent_captions,
        operator_brief=sanitized_brief,
        media_analysis=media_analysis,
        mode=generation_mode,
        current_caption=current_caption,
        prior_best_caption=prior_best_caption,
        avoid_repeat_failures=failure_memory,
    )

    # --- Single-pass generation ---
    _emit_progress(
        progress_callback,
        "drafting_started",
        attempt=1,
        max_attempts=1,
        client_name=client_name,
        media_type=media_type,
        language_mode=language_mode,
    )
    system_prompt, user_prompt = _build_unified_caption_prompt(context, mode=generation_mode)
    payload, provider_attempts, model_error = _call_model_json_payload(
        system_prompt,
        user_prompt,
        max_tokens=CAPTION_RESPONSE_MAX_TOKENS * 2,
        response_schema=_build_single_caption_schema(),
    )
    # Anthropic fallback if primary models fail
    if not payload or not str(payload.get("caption") or "").strip():
        anthropic_payload, anthropic_attempts, anthropic_error = _call_anthropic_json_payload(
            system_prompt,
            user_prompt,
            max_tokens=CAPTION_RESPONSE_MAX_TOKENS * 2,
        )
        if anthropic_payload and str(anthropic_payload.get("caption") or "").strip():
            payload = anthropic_payload
            provider_attempts.extend(anthropic_attempts)
        else:
            model_error = model_error or anthropic_error or "No usable caption was generated."

    # --- Deduplication check: if too similar to recent captions, retry once ---
    caption_text_candidate = str(payload.get("caption") or "").strip()
    if caption_text_candidate and _is_duplicate(caption_text_candidate, recent_captions):
        print(f"[caption_agent] Dedup triggered — caption too similar to recent post. Retrying with stronger anti-repeat.", file=sys.stderr)
        dedup_user_prompt = (
            user_prompt
            + f"\n\nCRITICAL: Your previous output was nearly identical to a recent post. "
            f"The duplicate was: \"{_truncate_text(caption_text_candidate, 120)}\"\n"
            f"You MUST write a completely different caption with a different opening, "
            f"different structure, different angle, and different CTA. "
            f"Do NOT reuse any phrases from the duplicate."
        )
        retry_payload, retry_attempts, retry_error = _call_model_json_payload(
            system_prompt,
            dedup_user_prompt,
            max_tokens=CAPTION_RESPONSE_MAX_TOKENS * 2,
            response_schema=_build_single_caption_schema(),
        )
        provider_attempts.extend(retry_attempts)
        retry_caption = str(retry_payload.get("caption") or "").strip()
        if retry_caption and not _is_duplicate(retry_caption, recent_captions):
            payload = retry_payload
        elif retry_caption:
            # Even the retry is similar — use it anyway, it's better than blocking
            payload = retry_payload

    # Guard 1: raw model caption must have substance before we do anything
    caption_text = str(payload.get("caption") or "").strip()
    if not _caption_has_substance(caption_text):
        fallback_variants = _build_fallback_variants(context)
        return {
            "caption": "",
            "hashtags": [],
            "seo_keyword_used": "",
            "error": model_error or "Model returned an empty or unusable caption.",
            "reason": model_error or "Model returned an empty or unusable caption.",
            "status": "generation_unavailable",
            "generation_state": "generation_unavailable",
            "generation_source": "fallback_generated",
            "used_fallback": True,
            "provider_attempts": list(provider_attempts),
            "model_failure_reason": model_error or "No real model caption was produced.",
            "hook_candidates": [],
            "selected_hook_family": "",
            "client_memory_examples": list(context.get("client_memory_examples") or []),
            "internal_fallback_variants": fallback_variants,
            "analysis_summary": str(media_analysis.get("analysis_summary") or "").strip(),
            "media_analysis": media_analysis,
            "client_name": client_name,
        }

    # Normalize the single caption into the standard variant shape
    normalized = normalize_caption_payload(payload)
    normalized["client_name"] = client_name
    normalized["variant_id"] = "variant_1"
    normalized["direction_label"] = _truncate_text(payload.get("direction_label"), 80)
    normalized["selected_hook_family"] = str(payload.get("hook_style") or "").strip()
    normalized["hook_text"] = ""
    normalized["rationale"] = ""
    normalized["provider"] = provider_attempts[-1]["provider"] if provider_attempts else "unknown"
    normalized["model"] = provider_attempts[-1].get("model", "") if provider_attempts else ""
    normalized["generation_source"] = "model_generated"
    normalized = _humanize_variant(normalized, context)

    # Guard 2: after normalization/humanization, caption must still have substance
    normalized_caption_text = str(normalized.get("caption") or "").strip()
    if not _caption_has_substance(normalized_caption_text):
        print(f"[caption_agent] Normalized caption has no substance — falling back.", file=sys.stderr)
        fallback_variants = _build_fallback_variants(context)
        return {
            "caption": "",
            "hashtags": [],
            "seo_keyword_used": "",
            "error": "Caption was empty after normalization.",
            "reason": "Caption was empty after normalization.",
            "status": "generation_unavailable",
            "generation_state": "generation_unavailable",
            "generation_source": "fallback_generated",
            "used_fallback": True,
            "provider_attempts": list(provider_attempts),
            "model_failure_reason": "Caption had no substance after normalization.",
            "hook_candidates": [],
            "selected_hook_family": "",
            "client_memory_examples": list(context.get("client_memory_examples") or []),
            "internal_fallback_variants": fallback_variants,
            "analysis_summary": str(media_analysis.get("analysis_summary") or "").strip(),
            "media_analysis": media_analysis,
            "client_name": client_name,
        }

    # Advisory scoring (never blocks posting)
    ranked = rank_caption_variants([normalized], context)
    quality = _promote_quality_gate(ranked) if ranked else {
        "score": 0, "passed": True, "threshold": 78.0,
        "dimensions": {}, "dimension_weights": {}, "failures": [],
        "verdict": "Approved", "notes": {},
    }
    # Quality gate is advisory-only — always allow posting for a real caption
    quality["passed"] = True
    quality["verdict"] = quality.get("verdict") or "Approved"

    winner = ranked[0] if ranked else normalized
    winner["quality_gate"] = quality
    winner["hidden_variants"] = []
    winner["analysis_summary"] = str(media_analysis.get("analysis_summary") or "").strip()
    winner["media_analysis"] = media_analysis
    winner["generation_state"] = "success"
    winner["generation_source"] = "model_generated"
    winner["used_fallback"] = False
    winner["provider_attempts"] = list(provider_attempts)
    winner["model_failure_reason"] = ""
    winner["hook_candidates"] = []
    winner["selected_hook_family"] = str(winner.get("selected_hook_family") or "").strip()
    winner["client_memory_examples"] = list(context.get("client_memory_examples") or [])
    winner["ranking_summary"] = {
        "winner_variant_id": winner.get("variant_id"),
        "winner_score": quality.get("score"),
        "failure_reasons": list(quality.get("failures") or []),
        "selected_hook_family": winner.get("selected_hook_family"),
        "variant_scores": [{
            "variant_id": winner.get("variant_id"),
            "score": quality.get("score"),
            "direction_label": winner.get("direction_label"),
            "selected_hook_family": winner.get("selected_hook_family"),
        }],
    }
    winner["retry_memory"] = {
        "failure_reasons": list(quality.get("failures") or []),
        "last_hook_family": str(winner.get("selected_hook_family") or "").strip(),
        "last_direction_label": str(winner.get("direction_label") or "").strip(),
    }
    winner["display_direction"] = str(winner.get("direction_label") or sanitized_brief or sanitized_topic).strip()
    _emit_progress(
        progress_callback,
        "finalized",
        attempt=1,
        max_attempts=1,
        client_name=client_name,
        score=quality.get("score"),
        quality_gate=quality,
    )
    return winner
