import json
import os
import re
import time
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from client_store import get_client_store
from queue_store import normalize_hashtag_list

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
    payload["hashtags"] = merged
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
    return {
        "business_name": str(data.get("business_name") or data.get("client_name") or "").strip(),
        "industry": str(data.get("industry") or "general").strip(),
        "audience_summary": str(data.get("target_audience") or "").strip(),
        "offer_summary": ", ".join(str(item).strip() for item in services[:6] if str(item).strip()),
        "voice_rules": rules,
        "do_avoid_rules": [str(item).strip() for item in (data.get("dos_and_donts") or [])[:8] if str(item).strip()],
        "seo_keywords": [str(item).strip() for item in (data.get("seo_keywords") or [])[:8] if str(item).strip()],
        "language_profile": data.get("language_profile") or {},
        "cta_style": str((data.get("caption_defaults") or {}).get("cta_style") or "Clear, premium, direct, and conversion-aware.").strip(),
    }


def _build_caption_messages(client_name: str, topic: str, media_type: str, profile_payload: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": """You are a sharp social media copywriter for premium agencies.

Return pure JSON only with exactly these fields:
{
  "caption": "Main caption body without hashtags",
  "hashtags": ["#tag1", "#tag2"],
  "seo_keyword_used": "keyword used in the caption",
  "status": "success"
}

Rules:
1. Use the supplied brand profile only. Do not invent brand identity.
2. Follow language_profile.caption_output_language exactly.
3. If caption_output_language is Arabic and arabic_mode is gulf, use Gulf Arabic.
4. If caption_output_language is English, write clean premium English, not translated Arabic.
5. Keep hashtags out of the caption body.
6. Return 3-5 relevant hashtags matching the output language.
7. Embed at least one real SEO keyword naturally in the caption body.
8. Never use banned words.
9. The caption must feel human, current, and publishable. Avoid generic AI-marketing cadence.
10. Avoid these stale phrases and close variants entirely: elevate your, discover the, step into, unlock the, transform your, next level, ready to, whether you're, not just, journey.
11. Prefer concrete details over abstract hype. Name the actual product, offer, mood, texture, result, location, or occasion when possible.
12. Keep the rhythm natural. Use shorter sentences, fewer adjectives, and one clear CTA at most.
13. Do not sound like a motivational coach, consultant, or generic brand manifesto unless the brand profile explicitly calls for that.
14. If the brand voice includes emojis, use them sparingly and deliberately. If not, use none.
15. For English output, default to crisp, modern, social-first phrasing. For Arabic output, sound native and current, not formal translation-speak.
9. If the topic is unrelated to the brand or unsafe, return:
{
  "caption": "Reason the request should be held.",
  "hashtags": [],
  "seo_keyword_used": "",
  "status": "held_for_review"
}
10. Keep the caption tight and publish-ready. Usually 35-90 words is enough unless the brand profile clearly requires more.
11. The output must read like something a strong human social media manager would actually publish today, not a default LLM sample.""",
        },
        {
            "role": "user",
            "content": (
                f"Client: {client_name}\n"
                f"Topic: {topic}\n"
                f"Media Type: {media_type}\n"
                f"Platform: Both (Facebook and Instagram)\n\n"
                f"Do not use any of these tired phrases unless the profile explicitly demands them: {', '.join(AI_SMELL_PHRASES)}.\n"
                f"Caption Profile JSON:\n{json.dumps(profile_payload, ensure_ascii=False)}"
            ),
        },
    ]


def generate_caption_payload(client_name: str, topic: str, media_type: str = "image_post") -> dict:
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
    compact_profile = _compact_caption_profile(profile_payload["brand_data"])
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
                messages=_build_caption_messages(client_name, topic, media_type, compact_profile),
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
