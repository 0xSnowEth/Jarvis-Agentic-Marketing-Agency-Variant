import json
import logging
import os
from typing import Any

from openai import OpenAI

logger = logging.getLogger("CaptionQualityGate")

QUALITY_MODEL = os.getenv("CAPTION_QUALITY_MODEL", os.getenv("CAPTION_MODEL", "qwen/qwen3.6-plus-preview:free")).strip() or "qwen/qwen3.6-plus-preview:free"
QUALITY_TIMEOUT_SECONDS = float(os.getenv("CAPTION_TIMEOUT_SECONDS", "35"))
QUALITY_THRESHOLD = float(os.getenv("CAPTION_QUALITY_THRESHOLD", "85"))
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

EXPERTS = [
    (
        "platform_hook_strategist",
        (
            "You are a senior platform and hook strategist for premium Instagram and Facebook accounts in Gulf markets. "
            "Evaluate whether the caption stops the scroll quickly, feels platform-native, fits the intended audience, and uses a sharp hook instead of a generic opener."
        ),
    ),
    (
        "brand_voice_guardian",
        (
            "You are a brand voice guardian. Evaluate whether the caption matches the client's exact tone, avoids forbidden words, and sounds specific to this brand rather than generic agency filler."
        ),
    ),
    (
        "arabic_authenticity_judge",
        (
            "You are a native Gulf and Levant social copywriter. Evaluate Arabic captions for native contemporary social media Arabic, natural rhythm, dialect authenticity, and local hashtag fit. "
            "If the caption is not Arabic or bilingual, score 100 and return no failures."
        ),
    ),
    (
        "anti_generic_filter",
        (
            "You are an anti-generic content gate. Penalize stale phrases, filler CTAs, motivational fluff, spammy hashtags, bland openings, and anything that sounds like default AI output."
        ),
    ),
]


def _build_client() -> tuple[OpenAI, str]:
    openrouter_key = str(os.getenv("OPENROUTER_API_KEY") or "").strip()
    openai_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
    if openrouter_key:
        return (
            OpenAI(
                base_url=OPENROUTER_BASE_URL,
                api_key=openrouter_key,
                timeout=QUALITY_TIMEOUT_SECONDS,
                max_retries=0,
            ),
            QUALITY_MODEL,
        )
    if openai_key:
        return OpenAI(api_key=openai_key, timeout=QUALITY_TIMEOUT_SECONDS, max_retries=0), QUALITY_MODEL
    raise RuntimeError("Missing OPENROUTER_API_KEY or OPENAI_API_KEY in .env")


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json", "", 1).strip()
    start = text.find("{")
    if start == -1:
        return {}
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                snippet = text[start:index + 1]
                try:
                    parsed = json.loads(snippet)
                    return parsed if isinstance(parsed, dict) else {}
                except Exception:
                    return {}
    return {}


def _normalize_result(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    score_value = payload.get("score")
    try:
        score = max(0, min(100, int(float(score_value))))
    except Exception:
        score = 0
    raw_failures = payload.get("failures") or []
    if isinstance(raw_failures, str):
        failures = [raw_failures.strip()] if raw_failures.strip() else []
    else:
        failures = [str(item).strip() for item in raw_failures if str(item).strip()]
    passed = bool(payload.get("passed")) if "passed" in payload else score >= QUALITY_THRESHOLD
    return {
        "name": name,
        "score": score,
        "passed": passed,
        "failures": failures[:8],
    }


def _call_expert(
    client: OpenAI,
    *,
    model: str,
    expert_name: str,
    expert_brief: str,
    caption_payload: dict[str, Any],
    brand_profile: dict[str, Any],
    language_mode: str,
    topic: str,
    media_type: str,
) -> dict[str, Any]:
    prompt = (
        f"{expert_brief}\n\n"
        "Return only valid JSON in this exact shape:\n"
        '{"score": 0, "passed": false, "failures": ["reason 1", "reason 2"]}\n\n'
        "Scoring rules:\n"
        "- 100 means publish-ready premium work.\n"
        "- 85 is the minimum pass threshold.\n"
        "- failures must be concrete, short, and actionable.\n"
        "- If the caption is strong, failures can be an empty list.\n\n"
        f"Topic: {topic}\n"
        f"Media type: {media_type}\n"
        f"Language mode: {language_mode}\n"
        f"Caption payload JSON:\n{json.dumps(caption_payload, ensure_ascii=False)}\n\n"
        f"Brand profile JSON:\n{json.dumps(brand_profile, ensure_ascii=False)}"
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Return only JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        parsed = _extract_json_object(response.choices[0].message.content or "")
        return _normalize_result(expert_name, parsed)
    except Exception as exc:
        logger.warning("Caption quality expert %s failed: %s", expert_name, exc)
        return _normalize_result(
            expert_name,
            {"score": 0, "passed": False, "failures": [f"{expert_name} could not score the caption."]},
        )


def score_caption_quality(
    caption_payload: dict[str, Any],
    brand_profile: dict[str, Any],
    *,
    language_mode: str,
    topic: str = "",
    media_type: str = "image_post",
) -> dict[str, Any]:
    client, model = _build_client()
    active_experts = []
    for expert_name, expert_brief in EXPERTS:
        if expert_name == "arabic_authenticity_judge" and language_mode not in {"arabic", "both"}:
            continue
        active_experts.append((expert_name, expert_brief))

    results = [
        _call_expert(
            client,
            model=model,
            expert_name=name,
            expert_brief=brief,
            caption_payload=caption_payload,
            brand_profile=brand_profile,
            language_mode=language_mode,
            topic=topic,
            media_type=media_type,
        )
        for name, brief in active_experts
    ]
    scores = [item["score"] for item in results] or [0]
    failures: list[str] = []
    for item in results:
        failures.extend(item.get("failures") or [])
    deduped_failures = list(dict.fromkeys(failures))
    average_score = round(sum(scores) / len(scores), 1)
    return {
        "score": average_score,
        "passed": average_score >= QUALITY_THRESHOLD,
        "threshold": QUALITY_THRESHOLD,
        "experts": results,
        "failures": deduped_failures[:12],
    }
