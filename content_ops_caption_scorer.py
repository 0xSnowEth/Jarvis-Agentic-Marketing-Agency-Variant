from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

QUALITY_THRESHOLD = float(os.getenv("CAPTION_QUALITY_THRESHOLD", "85"))

DEFAULT_WEIGHTS = {
    "voice_similarity": 0.35,
    "specificity": 0.25,
    "humanizer": 0.20,
    "length_appropriateness": 0.10,
    "engagement_potential": 0.10,
}

MEDIA_LIMITS = {
    "image_post": {"min": 45, "max": 520, "optimal_min": 80, "optimal_max": 220},
    "carousel_post": {"min": 60, "max": 700, "optimal_min": 110, "optimal_max": 320},
    "reel_post": {"min": 35, "max": 420, "optimal_min": 70, "optimal_max": 180},
}

UPSTREAM_ASSET_ROOT = Path(__file__).resolve().parent / "third_party" / "ai_marketing_skills" / "content_ops"
UPSTREAM_ASSETS = {
    "readme": str(UPSTREAM_ASSET_ROOT / "README.md"),
    "scorer_script": str(UPSTREAM_ASSET_ROOT / "scripts" / "content-quality-scorer.py"),
    "gate_script": str(UPSTREAM_ASSET_ROOT / "scripts" / "content-quality-gate.py"),
    "humanizer_rubric": str(UPSTREAM_ASSET_ROOT / "experts" / "humanizer.md"),
    "instagram_expert": str(UPSTREAM_ASSET_ROOT / "experts" / "instagram.md"),
    "content_quality_rubric": str(UPSTREAM_ASSET_ROOT / "scoring-rubrics" / "content-quality.md"),
}

BANNED_WORDS = [
    "leverage",
    "synergy",
    "ecosystem",
    "holistic",
    "at the end of the day",
    "delve",
    "tapestry",
    "landscape",
    "multifaceted",
    "nuanced",
    "pivotal",
    "realm",
    "robust",
    "seamless",
    "testament",
    "transformative",
    "underscore",
    "utilize",
    "whilst",
    "keen",
    "embark",
    "comprehensive",
    "intricate",
    "commendable",
    "meticulous",
    "paramount",
    "groundbreaking",
    "innovative",
    "cutting-edge",
    "paradigm",
    "additionally",
    "crucial",
    "enduring",
    "enhance",
    "fostering",
    "garner",
    "highlight",
    "interplay",
    "intricacies",
    "showcase",
    "vibrant",
    "valuable",
    "profound",
    "renowned",
    "breathtaking",
    "nestled",
    "stunning",
    "i'm excited to share",
    "i think maybe",
    "it could potentially",
    "dive into",
    "game-changer",
    "unlock",
    "elevate your",
    "experience the difference",
    "take your",
    "next level",
]

ARABIC_BANNED_PHRASES = [
    "لا تفوت الفرصة",
    "تجربة فريدة",
    "تجربة مميزة",
    "لحظات منعشة",
    "زورنا اليوم",
    "اكتشف",
    "ارتق",
    "الأفضل على الإطلاق",
]

AI_PATTERNS = [
    (r"pivotal moment|is a testament|stands as", "significance inflation"),
    (r"boasts|vibrant|commitment to", "promotional language"),
    (r"experts believe|industry reports|studies show", "vague attribution"),
    (r"despite.{1,50}continues to", "formulaic challenge framing"),
    (r"serves as|stands as|acts as|functions as", "copula avoidance"),
    (r"it's not just .{1,30}, it's", "negative parallelism"),
    (r"could potentially|might possibly|may perhaps", "excessive hedging"),
    (r"the future looks bright|exciting times ahead|stay tuned", "generic conclusion"),
]

CORPORATE_PATTERNS = [
    r"i'm excited to share",
    r"it is important to note",
    r"in order to",
    r"we are pleased to announce",
    r"stay tuned for",
]

ENGAGEMENT_PATTERNS = [
    r"\?$",
    r"\؟$",
    r"\bcomment\b",
    r"\breply\b",
    r"\bdm\b",
    r"\bvisit\b",
    r"\bbook\b",
    r"\btry\b",
    r"\border\b",
    r"\bshare\b",
    r"\bsave\b",
    r"\btag\b",
    r"وش رايكم",
    r"شنو رايكم",
    r"قولوا لنا",
    r"تعالوا",
    r"تعال",
    r"مر",
    r"مروا",
    r"زورونا",
    r"جر(?:ّ)?ب",
    r"احجز",
    r"اطلب",
]

QUESTION_RE = re.compile(r"[?؟]")
NUMBER_PATTERNS = [
    r"\$[\d,]+[KkMmBb]?(?:\+)?",
    r"\d+%",
    r"\d+x",
    r"\d+[\.,]?\d*\s*(?:hours?|minutes?|days?|weeks?|months?|years?)",
    r"\d+\s*(?:pages?|pieces?|tools?|agents?|companies|founders?|members)",
]
ARABIC_CHAR_RE = re.compile(r"[\u0600-\u06FF]")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _is_arabic(text: str) -> bool:
    return bool(ARABIC_CHAR_RE.search(text or ""))


def _contains_term(text: str, term: str) -> bool:
    haystack = _normalize_text(text).lower()
    needle = _normalize_text(term).lower()
    if not haystack or not needle:
        return False
    if _is_arabic(needle) or " " in needle or "-" in needle or "_" in needle:
        return needle in haystack
    return bool(re.search(rf"\b{re.escape(needle)}\b", haystack))


def _caption_text(caption_payload: dict[str, Any]) -> str:
    return _normalize_text(caption_payload.get("caption"))


def _hashtags(caption_payload: dict[str, Any]) -> list[str]:
    return [tag for tag in _as_list(caption_payload.get("hashtags")) if tag.startswith("#")]


def _topic_terms(topic: str) -> list[str]:
    raw = _normalize_text(topic)
    if not raw:
        return []
    parts = re.split(r"[^A-Za-z0-9\u0600-\u06FF]+", raw)
    tokens = [part.strip() for part in parts if len(part.strip()) >= 4]
    phrases = [raw]
    if len(tokens) >= 2:
        phrases.extend(" ".join(tokens[i:i + 2]) for i in range(len(tokens) - 1))
    return _dedupe(phrases + tokens)[:8]


def _collect_brand_terms(brand_profile: dict[str, Any], topic: str = "") -> dict[str, list[str]]:
    business_name = _normalize_text(brand_profile.get("business_name"))
    city_market = _normalize_text(brand_profile.get("city_market"))
    offer_terms = _as_list(brand_profile.get("offer_summary"))
    seo_keywords = _as_list(brand_profile.get("seo_keywords"))

    website_digest = brand_profile.get("website_digest") or {}
    if not isinstance(website_digest, dict):
        website_digest = {}
    trend_dossier = brand_profile.get("trend_dossier") or {}
    if not isinstance(trend_dossier, dict):
        trend_dossier = {}

    offer_terms.extend(_as_list(website_digest.get("service_terms")))
    offer_terms.extend(_as_list(website_digest.get("brand_keywords")))
    seo_keywords.extend(_as_list(trend_dossier.get("topical_language")))
    seo_keywords.extend(tag.lstrip("#") for tag in _as_list(trend_dossier.get("hashtag_candidates")))
    seo_keywords.extend(_topic_terms(topic))

    cleaned_offer_terms = []
    for term in offer_terms:
        stripped = _normalize_text(term)
        if len(stripped) < 3:
            continue
        cleaned_offer_terms.append(stripped)

    cleaned_keywords = []
    for term in seo_keywords:
        stripped = _normalize_text(term)
        if len(stripped) < 3:
            continue
        cleaned_keywords.append(stripped)

    return {
        "brand": _dedupe([business_name])[:1],
        "market": _dedupe([city_market])[:2],
        "offer": _dedupe(cleaned_offer_terms)[:8],
        "keywords": _dedupe(cleaned_keywords)[:10],
        "topic": _topic_terms(topic),
    }


def _score_voice_similarity(caption_text: str, hashtags: list[str], brand_profile: dict[str, Any], topic: str = "") -> tuple[int, list[str]]:
    markers = _collect_brand_terms(brand_profile, topic)
    searchable = f"{caption_text}\n{' '.join(hashtags)}"
    matches: list[str] = []
    score = 0.0

    for term in markers["brand"]:
        if _contains_term(searchable, term):
            score += 25
            matches.append(f"brand:{term}")
    for term in markers["market"]:
        if _contains_term(searchable, term):
            score += 16
            matches.append(f"market:{term}")

    offer_hits = 0
    for term in markers["offer"]:
        if _contains_term(searchable, term):
            offer_hits += 1
            matches.append(f"offer:{term}")
    score += min(offer_hits * 10, 32)

    keyword_hits = 0
    for term in markers["keywords"]:
        if _contains_term(searchable, term):
            keyword_hits += 1
            matches.append(f"keyword:{term}")
    score += min(keyword_hits * 6, 18)

    topic_hits = 0
    for term in markers["topic"]:
        if _contains_term(searchable, term):
            topic_hits += 1
            matches.append(f"topic:{term}")
    score += min(topic_hits * 8, 16)

    hashtag_hits = sum(1 for tag in hashtags if any(_contains_term(tag, marker) for marker in markers["brand"] + markers["market"]))
    score += min(hashtag_hits * 6, 12)

    return min(100, round(score)), matches[:10]


def _score_specificity(caption_text: str, brand_profile: dict[str, Any], topic: str = "") -> tuple[int, list[str]]:
    markers = _collect_brand_terms(brand_profile, topic)
    details: list[str] = []
    score = 0.0

    number_hits = 0
    for pattern in NUMBER_PATTERNS:
        found = re.findall(pattern, caption_text, re.IGNORECASE)
        number_hits += len(found)
    if number_hits:
        score += min(number_hits * 8, 16)
        details.append(f"numeric_details:{number_hits}")

    concrete_hits = 0
    for term in markers["offer"][:6]:
        if _contains_term(caption_text, term):
            concrete_hits += 1
    if concrete_hits:
        score += min(concrete_hits * 12, 36)
        details.append(f"offer_mentions:{concrete_hits}")

    keyword_hits = 0
    for term in markers["keywords"][:6]:
        if _contains_term(caption_text, term):
            keyword_hits += 1
    if keyword_hits:
        score += min(keyword_hits * 7, 21)
        details.append(f"topic_terms:{keyword_hits}")

    market_hits = 0
    for term in markers["market"]:
        if _contains_term(caption_text, term):
            market_hits += 1
    if market_hits:
        score += min(market_hits * 12, 20)
        details.append(f"market_signals:{market_hits}")

    topic_hits = 0
    for term in markers["topic"][:6]:
        if _contains_term(caption_text, term):
            topic_hits += 1
    if topic_hits:
        score += min(topic_hits * 10, 20)
        details.append(f"topic_matches:{topic_hits}")

    if QUESTION_RE.search(caption_text):
        score += 6
        details.append("hook_question")

    if (concrete_hits or topic_hits) and market_hits:
        score += 18
        details.append("anchor_combo")

    return min(100, round(score)), details


def _score_humanizer(caption_text: str, hashtags: list[str], language_mode: str) -> tuple[int, list[str]]:
    text_lower = caption_text.lower()
    score = 100
    issues: list[str] = []

    for word in BANNED_WORDS:
        if word.lower() in text_lower:
            score -= 8
            issues.append(f"banned:{word}")

    if language_mode == "arabic":
        for phrase in ARABIC_BANNED_PHRASES:
            if phrase in caption_text:
                score -= 7
                issues.append(f"generic_ar:{phrase}")

    for pattern, label in AI_PATTERNS:
        if re.search(pattern, caption_text, re.IGNORECASE):
            score -= 10
            issues.append(f"pattern:{label}")

    for pattern in CORPORATE_PATTERNS:
        if re.search(pattern, caption_text, re.IGNORECASE):
            score -= 12
            issues.append("corporate_speak")

    if caption_text.count("—") > 1:
        score -= 5
        issues.append("em_dash_overuse")

    if len(hashtags) > 7:
        score -= 8
        issues.append("hashtag_stuffing")

    if caption_text.count("!") > 1:
        score -= 4
        issues.append("excessive_exclamations")

    if QUESTION_RE.search(caption_text) and len(caption_text.split()) < 8:
        score += 4

    return max(0, min(100, round(score))), issues[:12]


def _score_length_appropriateness(caption_text: str, media_type: str) -> int:
    limits = MEDIA_LIMITS.get(media_type, MEDIA_LIMITS["image_post"])
    char_count = len(caption_text)
    if char_count < limits["min"]:
        return round(max((char_count / max(limits["min"], 1)) * 100, 20))
    if char_count > limits["max"]:
        return round(max((limits["max"] / char_count) * 100, 25))
    if limits["optimal_min"] <= char_count <= limits["optimal_max"]:
        return 100
    return 86


def _score_engagement_potential(caption_text: str, hashtags: list[str]) -> tuple[int, list[str]]:
    score = 0
    details: list[str] = []
    hook_window = caption_text[:120]

    if QUESTION_RE.search(hook_window):
        score += 28
        details.append("question_hook")
    elif re.match(r"^\s*(most|why|how|stop|think|imagine|هل|ليش|شنو|وش)\b", caption_text, re.IGNORECASE):
        score += 24
        details.append("strong_opening")

    for pattern in ENGAGEMENT_PATTERNS:
        if re.search(pattern, caption_text, re.IGNORECASE):
            score += 22
            details.append("cta_present")
            break

    if 4 <= len(hashtags) <= 7:
        score += 10
        details.append("hashtag_mix")

    if len(caption_text.split()) <= 22:
        score += 12
        details.append("tight_length")
    else:
        score += 6

    if "\n" in caption_text:
        score += 8
        details.append("readable_structure")

    if any(token in caption_text for token in ["Kuwait", "الكويت", "Kuwait City"]):
        score += 8
        details.append("market_context")

    return min(100, score), details


def _failure_messages(dimensions: dict[str, int], notes: dict[str, list[str]]) -> list[str]:
    failures: list[str] = []
    if dimensions["voice_similarity"] < 75:
        failures.append("Brand voice match is weak. Use clearer brand, market, and offer anchors from the client profile.")
    if dimensions["specificity"] < 70:
        failures.append("Caption needs more concrete specificity. Name the real product, context, or local detail instead of generic hype.")
    if dimensions["humanizer"] < 80:
        failures.append("Caption still reads templated. Remove AI-sounding filler, soft hype, and generic phrasing.")
    if dimensions["length_appropriateness"] < 70:
        failures.append("Caption length does not fit the post format cleanly.")
    if dimensions["engagement_potential"] < 70:
        failures.append("Hook and CTA are not strong enough for a scroll-stopping social caption.")

    if not failures and notes.get("humanizer"):
        failures.append("Clean up the remaining humanizer flags before publishing.")
    return failures[:8]


def score_caption_with_content_ops(
    caption_payload: dict[str, Any],
    brand_profile: dict[str, Any],
    *,
    language_mode: str,
    topic: str = "",
    media_type: str = "image_post",
) -> dict[str, Any]:
    caption_text = _caption_text(caption_payload)
    hashtags = _hashtags(caption_payload)

    voice_similarity, voice_notes = _score_voice_similarity(caption_text, hashtags, brand_profile, topic)
    specificity, specificity_notes = _score_specificity(caption_text, brand_profile, topic)
    humanizer, humanizer_notes = _score_humanizer(caption_text, hashtags, language_mode)
    length_appropriateness = _score_length_appropriateness(caption_text, media_type)
    engagement_potential, engagement_notes = _score_engagement_potential(caption_text, hashtags)

    dimensions = {
        "voice_similarity": voice_similarity,
        "specificity": specificity,
        "humanizer": humanizer,
        "length_appropriateness": length_appropriateness,
        "engagement_potential": engagement_potential,
    }
    weighted_score = round(
        sum(dimensions[key] * DEFAULT_WEIGHTS[key] for key in DEFAULT_WEIGHTS),
        1,
    )
    notes = {
        "voice_similarity": voice_notes[:8],
        "specificity": specificity_notes[:8],
        "humanizer": humanizer_notes[:8],
        "engagement_potential": engagement_notes[:8],
        "topic": _normalize_text(topic),
        "source_assets": dict(UPSTREAM_ASSETS),
    }
    failures = _failure_messages(dimensions, notes)
    passed = weighted_score >= QUALITY_THRESHOLD
    return {
        "score": weighted_score,
        "passed": passed,
        "threshold": QUALITY_THRESHOLD,
        "dimensions": dimensions,
        "dimension_weights": dict(DEFAULT_WEIGHTS),
        "failures": failures,
        "verdict": "Approved" if passed else "Needs another pass",
        "notes": notes,
    }
