import os
import re
from datetime import datetime, timezone
from typing import Any

import requests

from caption_technique_store import get_caption_technique_snapshot, save_caption_technique_snapshot


CAPTION_TECHNIQUE_SNAPSHOT_KEY = "meta_official_caption_techniques"
CAPTION_TECHNIQUE_TTL_SECONDS = max(3600, int(os.getenv("CAPTION_TECHNIQUE_TTL_SECONDS", "86400") or "86400"))
CAPTION_TECHNIQUE_REFRESH_TIME = str(os.getenv("CAPTION_TECHNIQUE_REFRESH_TIME") or "03:15").strip() or "03:15"
CAPTION_TECHNIQUE_FETCH_TIMEOUT = float(os.getenv("CAPTION_TECHNIQUE_FETCH_TIMEOUT", "20") or "20")
OFFICIAL_CAPTION_TECHNIQUE_SOURCES = [
    "https://www.facebook.com/business/ads/carousel-ad-format",
    "https://www.facebook.com/business/ads/stories-ad-format",
    "https://www.facebook.com/business/ads/ad-creative",
    "https://www.facebook.com/business/ads/click-to-message-ads",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_html(value: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _seed_snapshot() -> dict[str, Any]:
    return {
        "snapshot_key": CAPTION_TECHNIQUE_SNAPSHOT_KEY,
        "platform_scope": ["instagram_carousel", "instagram_feed", "facebook_feed", "reels"],
        "source_summary": [
            "The first line is the hook, and it has to earn the tap before the caption truncates.",
            "Hooks that work now are curiosity, contrarian, story, how-to, and social proof.",
            "Carousel captions should create progression or an open loop, not just restate the product.",
            "Instagram search rewards relevant keywords and location cues used naturally.",
            "Human tone, useful details, and save/share value beat generic hype.",
        ],
        "techniques": {
            "hook_types": [
                "Curiosity gap: hint at the answer without giving it away.",
                "Contrarian: challenge a common assumption in a brand-safe way.",
                "Story: open mid-action or with a real moment that already has motion.",
                "How-to: promise a specific useful outcome or step.",
                "Social proof: lead with a result, proof point, or customer signal.",
            ],
            "hook_rules": [
                "Use a real audience tension, contrast, mood, benefit, or curiosity gap in the opener.",
                "Keep the first line compressed and worth reading before the brand appears.",
                "Avoid generic setup lines and direct brand-name openings unless the hook family demands it.",
            ],
            "caption_rules": [
                "Put the hook in the first line and keep the body human and specific.",
                "Keep captions succinct unless the post needs teaching, narrative detail, or a multi-step explanation.",
                "Avoid AI-slop phrasing and empty hype.",
            ],
            "search_rules": [
                "Work relevant keywords into captions, profile text, hashtags, and location cues naturally.",
                "Optimize for audience search intent instead of keyword stuffing.",
            ],
            "carousel_rules": [
                "Slide 1 is the hook; later slides should progress, explain, or deepen the story.",
                "Write as if the caption is supporting a sequence, not a single image.",
                "Reference progression, comparison, or layered detail when the media is a carousel.",
                "Use a sequence or open loop so people want to keep swiping.",
            ],
            "reel_rules": [
                "Pair the caption hook with the first-second visual or spoken hook.",
                "Use the caption to reinforce the core value, keyword, and CTA.",
            ],
            "cta_rules": [
                "Use one short natural CTA.",
                "Prefer save, try, visit, order, or share language over generic hype.",
                "Keep the CTA low-friction and aligned with the brand voice.",
            ],
            "arabic_rules": [
                "Prefer native Arabic rhythm and local phrasing.",
                "Use English menu words only when they are genuine offer terms.",
                "Avoid awkward mixed English-Arabic openings and forced translations.",
            ],
            "voice_rules": [
                "Let brand voice stay specific, premium, and locally grounded.",
                "Keep the opening direct and emotionally legible.",
            ],
        },
        "source_links": [{"title": "Meta official caption technique seed", "url": url, "published_at": ""} for url in OFFICIAL_CAPTION_TECHNIQUE_SOURCES],
        "refreshed_at": "",
        "last_good_refresh_at": "",
        "refresh_status": "seed",
    }


def _extract_source_title_and_headings(html: str) -> tuple[str, list[str]]:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    title = _strip_html(title_match.group(1)) if title_match else "Meta for Business"
    headings: list[str] = []
    for match in re.finditer(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, flags=re.IGNORECASE | re.DOTALL):
        text = _strip_html(match.group(1))
        if text and text not in headings:
            headings.append(text)
        if len(headings) >= 5:
            break
    return title, headings


def _fetch_source_snapshot(url: str) -> dict[str, Any]:
    response = requests.get(
        url,
        timeout=CAPTION_TECHNIQUE_FETCH_TIMEOUT,
        headers={"User-Agent": "JarvisCaptionTechniqueRefresh/1.0"},
    )
    response.raise_for_status()
    title, headings = _extract_source_title_and_headings(response.text or "")
    return {"title": title, "headings": headings, "url": url}


def _snapshot_is_fresh(snapshot: dict[str, Any]) -> bool:
    refreshed_at = str(snapshot.get("refreshed_at") or snapshot.get("last_good_refresh_at") or "").strip()
    if not refreshed_at:
        return False
    try:
        built_at = datetime.fromisoformat(refreshed_at.replace("Z", "+00:00"))
    except Exception:
        return False
    age = (datetime.now(timezone.utc) - built_at).total_seconds()
    return age < CAPTION_TECHNIQUE_TTL_SECONDS


def refresh_caption_technique_snapshot(*, force: bool = False) -> dict[str, Any]:
    current = get_caption_technique_snapshot(CAPTION_TECHNIQUE_SNAPSHOT_KEY) or {}
    if current and not force and _snapshot_is_fresh(current):
        return current

    snapshot = _seed_snapshot()
    source_links: list[dict[str, Any]] = []
    source_summary: list[str] = []
    success_count = 0
    for url in OFFICIAL_CAPTION_TECHNIQUE_SOURCES:
        try:
            source = _fetch_source_snapshot(url)
            success_count += 1
            source_links.append({"title": source["title"], "url": source["url"], "published_at": ""})
            if source["headings"]:
                source_summary.extend(source["headings"][:2])
        except Exception:
            continue

    if success_count == 0 and current:
        return current

    snapshot["source_links"] = source_links or snapshot["source_links"]
    snapshot["source_summary"] = source_summary[:8] or snapshot["source_summary"]
    snapshot["refreshed_at"] = _utc_now_iso()
    snapshot["last_good_refresh_at"] = snapshot["refreshed_at"]
    snapshot["refresh_status"] = "ok" if success_count else "seed"
    return save_caption_technique_snapshot(CAPTION_TECHNIQUE_SNAPSHOT_KEY, snapshot)


def get_caption_technique_snapshot_payload(*, force_refresh: bool = False) -> dict[str, Any]:
    current = get_caption_technique_snapshot(CAPTION_TECHNIQUE_SNAPSHOT_KEY) or {}
    if current and not force_refresh:
        return current
    if force_refresh:
        return refresh_caption_technique_snapshot(force=True)
    seed = _seed_snapshot()
    if current:
        merged = dict(seed)
        merged.update(current)
        return merged
    return save_caption_technique_snapshot(CAPTION_TECHNIQUE_SNAPSHOT_KEY, seed)
