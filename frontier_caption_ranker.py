import re
from typing import Any
from brand_voice_validator import score_brand_voice_fit


AI_SLOP_PATTERNS = [
    "elevate your",
    "discover the",
    "unlock the",
    "next level",
    "journey",
    "transform your",
]
INTERNAL_LABEL_PATTERNS = ["whatsapp", "carousel concept", "reel concept", "draft", "image post"]
RANKING_THRESHOLD = 78.0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _contains_any(text: str, values: list[str]) -> int:
    lowered = str(text or "").lower()
    return sum(1 for value in values if str(value or "").strip() and str(value).lower() in lowered)


def _score_variant(variant: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    caption = str(variant.get("caption") or "").strip()
    hashtags = [str(item).strip() for item in (variant.get("hashtags") or []) if str(item).strip()]
    profile = dict(context.get("profile") or {})
    media_analysis = dict(context.get("media_analysis") or {})
    platform_strategy = dict(context.get("platform_strategy") or {})
    trend_terms = [str(item).strip() for item in (context.get("trend_terms") or []) if str(item).strip()]
    offers = [str(item).strip() for item in (profile.get("offers") or []) if str(item).strip()]
    brand = str(profile.get("business_name") or "").strip()
    market = str(profile.get("market") or "").strip()
    audience = str(profile.get("audience") or "").strip()
    visual_terms = [str(item).strip() for item in (media_analysis.get("product_signals") or []) if str(item).strip()]

    visual_grounding = min(100.0, 45.0 + 18.0 * _contains_any(caption, visual_terms[:4] + offers[:3]) + (8.0 if market and market.lower() in caption.lower() else 0.0))
    brand_voice_fidelity, voice_failures = score_brand_voice_fit(caption, context)
    realism = max(0.0, 92.0 - 18.0 * _contains_any(caption, AI_SLOP_PATTERNS) - 25.0 * _contains_any(caption, INTERNAL_LABEL_PATTERNS))
    first_line = caption.split("\n", 1)[0].strip()
    curiosity_patterns = ["لكن", "instead of", "not just", "مو", "between", "from", "before", "rather than"]
    emotional_patterns = ["حر", "رشفة", "وقفة", "reset", "rush", "calm", "slow", "fresh", "premium", "local"]
    natural_cta_patterns = ["جرّب", "زرنا", "خلها", "خذها", "visit", "save", "share", "send", "drop by"]
    opener_score = 14.0 if first_line and len(first_line) <= 85 else 0.0
    compression_score = 12.0 if 4 <= len(first_line.split()) <= 11 else 0.0
    contrast_score = min(12.0, 6.0 * _contains_any(first_line, curiosity_patterns[:6]))
    emotional_score = min(12.0, 6.0 * _contains_any(caption[:160], emotional_patterns[:8]))
    cta_score = 10.0 if any(call in caption.lower() for call in natural_cta_patterns) else 0.0
    question_score = 10.0 if "?" in first_line[:120] else 0.0
    hook_strength = min(100.0, 38.0 + opener_score + compression_score + contrast_score + emotional_score + question_score + cta_score)
    local_terms = [market, audience, *offers[:3], *(media_analysis.get("hook_opportunities") or [])]
    trend_relevance = min(
        100.0,
        42.0
        + 10.0 * _contains_any(caption + " " + " ".join(hashtags), trend_terms[:4])
        + 8.0 * _contains_any(caption, [term for term in local_terms if str(term).strip()][:4]),
    )
    audience_platform_fit = min(100.0, 55.0 + (10.0 if len(caption) <= int(platform_strategy.get("max_caption_length") or 360) else -8.0) + (10.0 if hashtags and len(hashtags) <= int(platform_strategy.get("hashtag_ceiling") or 7) else 0.0) + (8.0 if platform_strategy.get("cta_style") and any(term in caption.lower() for term in natural_cta_patterns) else 0.0))

    weights = {
        "visual_grounding": 0.20,
        "brand_voice_fidelity": 0.20,
        "audience_platform_fit": 0.14,
        "realism": 0.14,
        "hook_strength": 0.22,
        "trend_relevance": 0.10,
    }
    total = (
        visual_grounding * weights["visual_grounding"]
        + brand_voice_fidelity * weights["brand_voice_fidelity"]
        + audience_platform_fit * weights["audience_platform_fit"]
        + realism * weights["realism"]
        + hook_strength * weights["hook_strength"]
        + trend_relevance * weights["trend_relevance"]
    )
    failures: list[str] = []
    if visual_grounding < 70:
        failures.append("Visual grounding is weak. Use clearer product and scene details from the media.")
    failures.extend(voice_failures)
    if audience_platform_fit < 70:
        failures.append("Audience/platform fit is weak. Tighten the structure for Instagram/Facebook behavior.")
    if realism < 78:
        failures.append("The draft still feels synthetic. Reduce templated phrasing and internal-sounding wording.")
    if hook_strength < 72:
        failures.append("The opening hook and CTA need more pull.")
    if trend_relevance < 60:
        failures.append("Trend relevance is light. Weave in one cleaner trend or market signal naturally.")

    return {
        "score": round(total, 1),
        "passed": total >= RANKING_THRESHOLD,
        "threshold": RANKING_THRESHOLD,
        "dimensions": {
            "visual_grounding": round(visual_grounding, 1),
            "brand_voice_fidelity": round(brand_voice_fidelity, 1),
            "audience_platform_fit": round(audience_platform_fit, 1),
            "realism": round(realism, 1),
            "hook_strength": round(hook_strength, 1),
            "trend_relevance": round(trend_relevance, 1),
        },
        "dimension_weights": weights,
        "failures": failures,
        "verdict": "Approved" if total >= RANKING_THRESHOLD else "Needs another pass",
        "notes": {
            "brand_mentions": _contains_any(caption, [brand] if brand else []),
            "offer_mentions": _contains_any(caption, offers[:3]),
            "visual_mentions": _contains_any(caption, visual_terms[:4]),
        },
    }


def rank_caption_variants(variants: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for index, variant in enumerate(variants):
        quality_gate = _score_variant(variant, context)
        enriched = dict(variant)
        enriched["quality_gate"] = quality_gate
        enriched["variant_id"] = str(variant.get("variant_id") or f"variant_{index + 1}")
        ranked.append(enriched)
    ranked.sort(key=lambda item: float(((item.get("quality_gate") or {}).get("score") or 0)), reverse=True)
    return ranked
