import json
import os
import re
import time
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from caption_quality_gate import score_caption_quality
from client_store import get_client_store
from queue_store import normalize_hashtag_list
from trend_research_service import get_client_trend_dossier

load_dotenv()

CAPTION_MODEL = os.getenv("CAPTION_MODEL", "qwen/qwen3.6-plus-preview:free").strip() or "qwen/qwen3.6-plus-preview:free"
CAPTION_FALLBACK_MODEL = os.getenv("CAPTION_FALLBACK_MODEL", "").strip()
CAPTION_TIMEOUT_SECONDS = float(os.getenv("CAPTION_TIMEOUT_SECONDS", "35"))
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
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


def _build_client() -> tuple[OpenAI, str]:
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if openrouter_key:
        return (
            OpenAI(
                base_url=OPENROUTER_BASE_URL,
                api_key=openrouter_key,
                timeout=CAPTION_TIMEOUT_SECONDS,
                max_retries=0,
            ),
            "openrouter",
        )
    if openai_key:
        return OpenAI(api_key=openai_key, timeout=CAPTION_TIMEOUT_SECONDS, max_retries=0), "openai"
    raise RuntimeError("Missing OPENROUTER_API_KEY or OPENAI_API_KEY in .env")


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
    raise ValueError("Unterminated JSON object in caption response")


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

    payload["caption"] = caption.strip()
    payload["hashtags"] = merged[:7]
    payload["seo_keyword_used"] = str(payload.get("seo_keyword_used") or "").strip()
    payload["status"] = str(payload.get("status") or "success").strip() or "success"
    return payload


def _compact_caption_profile(brand_data: dict[str, Any]) -> dict[str, Any]:
    data = dict(brand_data or {})
    profile = data.get("caption_profile")
    if isinstance(profile, dict) and profile:
        return profile

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
    return {
        "business_name": str(data.get("business_name") or data.get("client_name") or "").strip(),
        "industry": str(data.get("industry") or "general").strip(),
        "main_language": str(data.get("main_language") or "").strip(),
        "city_market": str(data.get("city_market") or data.get("market") or data.get("location") or "").strip(),
        "audience_summary": str(data.get("target_audience") or "").strip(),
        "offer_summary": ", ".join(str(item).strip() for item in services[:6] if str(item).strip()),
        "voice_rules": rules,
        "do_avoid_rules": [str(item).strip() for item in (data.get("dos_and_donts") or [])[:8] if str(item).strip()],
        "seo_keywords": [str(item).strip() for item in (data.get("seo_keywords") or [])[:8] if str(item).strip()],
        "language_profile": data.get("language_profile") or {},
        "website_digest": {
            "title": str(website_digest.get("title") or "").strip(),
            "meta_description": str(website_digest.get("meta_description") or "").strip(),
            "headings": [str(item).strip() for item in (website_digest.get("headings") or [])[:8] if str(item).strip()],
            "service_terms": [str(item).strip() for item in (website_digest.get("service_terms") or [])[:8] if str(item).strip()],
            "brand_keywords": [str(item).strip() for item in (website_digest.get("brand_keywords") or [])[:8] if str(item).strip()],
        },
        "trend_dossier": {
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
        },
        "cta_style": str((data.get("caption_defaults") or {}).get("cta_style") or "Clear, premium, direct, and conversion-aware.").strip(),
    }


def _resolve_caption_language(brand_data: dict[str, Any]) -> str:
    main_language = str(brand_data.get("main_language") or "").strip().lower()
    if main_language in {"arabic", "english", "both"}:
        return main_language
    language_profile = brand_data.get("language_profile") or {}
    caption_language = str(language_profile.get("caption_output_language") or "").strip().lower()
    primary_language = str(language_profile.get("primary_language") or "").strip().lower()
    resolved = caption_language or primary_language
    if resolved in {"arabic", "english"}:
        return resolved
    if resolved in {"bilingual", "both"}:
        return "both"
    return "english"


def _language_directive(language_mode: str) -> str:
    if language_mode == "arabic":
        return (
            "FIRST DIRECTIVE: Write the entire output exclusively in Arabic, including the caption, hook, CTA, and every hashtag. "
            "Do not switch to English even if the topic, brief, or source material is in English."
        )
    if language_mode == "both":
        return (
            "FIRST DIRECTIVE: Write a bilingual caption with Arabic first and English second. "
            "The Arabic section must come first, then a divider line containing exactly --- on its own line, then the English section below it. "
            "Hashtags may be Arabic, English, or mixed, but the caption body must always start in Arabic."
        )
    return "FIRST DIRECTIVE: Write the entire output exclusively in English, including the caption, hook, CTA, and every hashtag."


def _build_caption_messages(
    client_name: str,
    topic: str,
    media_type: str,
    profile_payload: dict[str, Any],
    language_mode: str,
    recent_captions: list[str],
    failure_context: str = "",
) -> list[dict[str, str]]:
    recent_block = "\n".join(f"- {item}" for item in recent_captions if str(item).strip()) or "- None provided."
    failure_block = str(failure_context or "").strip()
    return [
        {
            "role": "system",
            "content": (
                "You are a sharp social media copywriter for premium agencies.\n"
                f"{_language_directive(language_mode)}\n\n"
                "Return pure JSON only with exactly these fields:\n"
                "{\n"
                '  "caption": "Main caption body without hashtags",\n'
                '  "hashtags": ["#tag1", "#tag2"],\n'
                '  "seo_keyword_used": "keyword used in the caption",\n'
                '  "status": "success"\n'
                "}\n\n"
                "Rules:\n"
                "1. Use the supplied brand profile only. Do not invent brand identity, offers, prices, timelines, or product claims.\n"
                "2. The caption must open with a hook: a question, a bold statement, or a cultural reference. Never use a generic opener.\n"
                "3. The writing must feel like a senior social strategist at a premium agency, not a template filler.\n"
                "4. Keep hashtags out of the caption body.\n"
                "5. Return 5-7 relevant hashtags maximum.\n"
                "6. Hashtags must be a curated mix of 1 broad reach tag, 2 niche category tags, 2 local or market tags, and 1 brand-specific tag when possible.\n"
                "7. Embed at least one real SEO keyword naturally in the caption body.\n"
                "8. Never use banned words or AI-smell filler phrases.\n"
                "9. Match the tone, style, dialect, and constraints in the brand profile exactly.\n"
                "10. For Arabic output, use contemporary Gulf or Levantine social media Arabic that feels native and current, not formal MSA, unless the brand profile explicitly requires formal language.\n"
                "11. Use the trend dossier only as supporting signal. Do not copy it verbatim.\n"
                "12. Prefer concrete details over abstract hype. Name the actual product, offer, mood, texture, result, location, or occasion when possible.\n"
                "13. Keep the rhythm natural. Use shorter sentences, fewer adjectives, and one clear CTA at most.\n"
                "14. Do not sound like a motivational coach, consultant, or generic brand manifesto unless the brand profile explicitly calls for that.\n"
                "15. If the brand voice includes emojis, use them sparingly and deliberately. If not, use none.\n"
                "16. Avoid these stale phrases and close variants entirely: elevate your, discover the, step into, unlock the, transform your, next level, ready to, whether you're, not just, journey.\n"
                "17. If the topic is unrelated to the brand or unsafe, return:\n"
                "{\n"
                '  "caption": "Reason the request should be held.",\n'
                '  "hashtags": [],\n'
                '  "seo_keyword_used": "",\n'
                '  "status": "held_for_review"\n'
                "}\n"
                "18. Keep the caption tight and publish-ready. Usually 35-90 words is enough unless the brand profile clearly requires more.\n"
                "19. For bilingual output, the caption field must contain Arabic first, then a line with exactly --- , then the English version below it.\n"
                "20. The output must read like something a strong human social media manager would actually publish today, not a default LLM sample.\n"
                "21. The following captions have already been used for this client recently. Your output must differ in opening hook style, sentence structure, and hashtag selection. Do not reuse any opening phrase or hashtag from this list:\n"
                f"{recent_block}\n"
                "22. If previous attempts failed the expert quality gate, fix every cited issue explicitly before you return the next draft."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Client: {client_name}\n"
                f"Topic: {topic}\n"
                f"Media Type: {media_type}\n"
                f"Platform: Both (Facebook and Instagram)\n\n"
                f"Do not use any of these tired phrases unless the profile explicitly demands them: {', '.join(AI_SMELL_PHRASES)}.\n"
                f"Quality gate repair context:\n{failure_block or 'None. This is the first attempt.'}\n\n"
                f"Trend dossier JSON:\n{json.dumps(profile_payload.get('trend_dossier') or {}, ensure_ascii=False)}\n\n"
                f"Caption Profile JSON:\n{json.dumps(profile_payload, ensure_ascii=False)}"
            ),
        },
    ]


def _generate_caption_candidate(
    client: OpenAI,
    *,
    provider: str,
    client_name: str,
    topic: str,
    media_type: str,
    compact_profile: dict[str, Any],
    language_mode: str,
    recent_captions: list[str],
    failure_context: str = "",
) -> dict:
    model_candidates = []
    if CAPTION_MODEL:
        model_candidates.append(CAPTION_MODEL)
    if CAPTION_FALLBACK_MODEL and CAPTION_FALLBACK_MODEL not in model_candidates:
        model_candidates.append(CAPTION_FALLBACK_MODEL)
    elif provider == "openrouter" and CAPTION_MODEL != "qwen/qwen3.6-plus-preview:free":
        model_candidates.append("qwen/qwen3.6-plus-preview:free")

    last_error = None
    for attempt, candidate_model in enumerate(model_candidates):
        try:
            response = client.chat.completions.create(
                model=candidate_model,
                messages=_build_caption_messages(
                    client_name,
                    topic,
                    media_type,
                    compact_profile,
                    language_mode,
                    [str(item).strip() for item in (recent_captions or []) if str(item).strip()][:5],
                    failure_context,
                ),
                temperature=0.35,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
            data = normalize_caption_payload(_extract_caption_json(content))
            data["client_name"] = client_name
            return data
        except Exception as exc:
            last_error = exc
            if attempt < len(model_candidates) - 1:
                time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s...
            continue

    return {
        "caption": f"Caption generation failed: {last_error}" if last_error else "Caption generation failed.",
        "hashtags": [],
        "seo_keyword_used": "",
        "status": "error",
        "client_name": client_name,
    }


def generate_caption_payload(client_name: str, topic: str, media_type: str = "image_post", recent_captions: list[str] = []) -> dict:
    profile_payload = _load_brand_profile_payload(client_name)
    if profile_payload.get("status") != "success":
        return {
            "caption": str(profile_payload.get("message") or "Brand profile missing."),
            "hashtags": [],
            "seo_keyword_used": "",
            "status": "error",
            "client_name": client_name,
        }

    client, provider = _build_client()
    brand_data = dict(profile_payload["brand_data"] or {})
    compact_profile = _compact_caption_profile(brand_data)
    language_mode = _resolve_caption_language(brand_data)
    trend_dossier = get_client_trend_dossier(client_name, goal=topic, campaign_context="", force_refresh=False)
    compact_profile["trend_dossier"] = trend_dossier
    if not compact_profile.get("main_language"):
        compact_profile["main_language"] = language_mode

    failure_context = ""
    best_payload: dict[str, Any] | None = None
    best_quality: dict[str, Any] | None = None
    for _attempt in range(3):
        candidate = _generate_caption_candidate(
            client,
            provider=provider,
            client_name=client_name,
            topic=topic,
            media_type=media_type,
            compact_profile=compact_profile,
            language_mode=language_mode,
            recent_captions=recent_captions,
            failure_context=failure_context,
        )
        if str(candidate.get("status") or "").strip().lower() != "success":
            return candidate
        try:
            quality = score_caption_quality(
                candidate,
                compact_profile,
                language_mode=language_mode,
                topic=topic,
                media_type=media_type,
            )
        except Exception as exc:
            quality = {
                "score": 0,
                "passed": False,
                "threshold": 85,
                "experts": [],
                "failures": [f"Quality gate failed: {type(exc).__name__}: {exc}"],
            }
        candidate["quality_gate"] = quality
        if not best_quality or float(quality.get("score") or 0) >= float(best_quality.get("score") or 0):
            best_payload = candidate
            best_quality = quality
        if quality.get("passed"):
            return candidate
        failure_list = [str(item).strip() for item in (quality.get("failures") or []) if str(item).strip()]
        failure_context = (
            "Previous attempt failed the expert panel quality gate. Fix every issue below in the next draft:\n- "
            + "\n- ".join(failure_list[:10])
        ) if failure_list else "Previous attempt failed the expert panel quality gate. Improve hook quality, brand specificity, and hashtag freshness."

    return best_payload or {
        "caption": "Caption generation failed quality review.",
        "hashtags": [],
        "seo_keyword_used": "",
        "status": "error",
        "client_name": client_name,
    }
