from typing import Any
import re


def _normalize_for_matching(text: str) -> str:
    """Normalize text for cross-script substring matching."""
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _contains_any(text: str, values: list[str]) -> bool:
    lowered = _normalize_for_matching(text)
    return any(_normalize_for_matching(value) in lowered for value in values if _normalize_for_matching(value))


def score_brand_voice_fit(caption: str, context: dict[str, Any]) -> tuple[float, list[str]]:
    profile = dict(context.get("profile") or {})
    brand = str(profile.get("business_name") or context.get("client_name") or "").strip()
    market = str(profile.get("market") or profile.get("city_market") or "").strip()
    offers = [str(item).strip() for item in (profile.get("offers") or profile.get("services") or []) if str(item).strip()]
    audience = str(profile.get("target_audience") or "").strip()
    normalized_caption = _normalize_for_matching(caption)

    # Base score starts at 60 (not 40) so reasonable captions pass
    score = 60.0
    if brand and _normalize_for_matching(brand) in normalized_caption:
        score += 15.0
    if market and _normalize_for_matching(market) in normalized_caption:
        score += 10.0
    if offers and _contains_any(caption, offers[:3]):
        score += 8.0
    if audience and any(_normalize_for_matching(term) in normalized_caption for term in audience.split()[:2] if len(term) >= 3):
        score += 7.0

    score = min(100.0, score)
    failures: list[str] = []
    if score < 65:
        failures.append("Brand voice fit is weak. Anchor the caption more clearly to the saved brand, market, and offer set.")
    return round(score, 1), failures
