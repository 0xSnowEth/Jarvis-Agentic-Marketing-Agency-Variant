import hashlib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape as html_unescape
from typing import Any
from urllib.parse import urlparse
from llm_config import build_sync_client


import requests
from dotenv import load_dotenv
from openai import OpenAI

from client_store import get_client_store
from external_context_safety import sanitize_website_digest

load_dotenv()

logger = logging.getLogger("TrendResearch")

TREND_RESEARCH_RECENCY_DAYS = max(1, int(os.getenv("TREND_RESEARCH_RECENCY_DAYS", "30") or "30"))
TREND_DOSSIER_TTL_SECONDS = max(900, int(os.getenv("TREND_DOSSIER_TTL_SECONDS", str(24 * 60 * 60)) or str(24 * 60 * 60)))
TREND_QUERY_CACHE_TTL_SECONDS = max(120, int(os.getenv("TREND_QUERY_CACHE_TTL_SECONDS", "900") or "900"))
TREND_MAX_RESULTS_PER_QUERY = max(2, min(int(os.getenv("TREND_MAX_RESULTS_PER_QUERY", "5") or "5"), 8))
TREND_MAX_QUERIES = max(2, min(int(os.getenv("TREND_MAX_QUERIES", "5") or "5"), 6))
TREND_MIN_RECENT_RESULTS = max(2, min(int(os.getenv("TREND_MIN_RECENT_RESULTS", "3") or "3"), 10))
TREND_TAVILY_TIMEOUT_SECONDS = max(5, int(os.getenv("TREND_TAVILY_TIMEOUT_SECONDS", "18") or "18"))
TREND_DDGS_TIMEOUT_SECONDS = max(5, int(os.getenv("TREND_DDGS_TIMEOUT_SECONDS", "12") or "12"))
TREND_LLM_TIMEOUT_SECONDS = max(10, int(os.getenv("TREND_LLM_TIMEOUT_SECONDS", "28") or "28"))
TREND_DOSSIER_MODEL = str(os.getenv("TREND_DOSSIER_MODEL") or "").strip()
TREND_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_QUERY_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_HEALTH_LOCK = threading.Lock()
_HEALTH: dict[str, Any] = {
    "provider": "",
    "available": False,
    "degraded": False,
    "last_success_at": "",
    "last_error": "",
}

_STOPWORDS = {
    "about", "after", "against", "along", "also", "among", "and", "around", "because", "been",
    "before", "being", "between", "bring", "business", "campaign", "client", "content", "could",
    "deliver", "during", "each", "from", "into", "just", "more", "most", "need", "next", "over",
    "page", "plan", "post", "posts", "service", "services", "should", "that", "their", "them",
    "there", "these", "they", "this", "through", "today", "very", "want", "week", "with", "your",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _domain_from_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except Exception:
        return ""
    return str(parsed.netloc or "").strip().lower()


def _parse_date_candidate(value: Any) -> str:
    raw = _clean_text(value)
    if not raw:
        return ""
    normalized = raw.replace("Z", "+00:00")
    for candidate in (
        normalized,
        normalized.split("T", 1)[0],
    ):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except Exception:
            continue
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    for pattern in ("%Y-%m-%d", "%d %b %Y", "%b %d, %Y", "%d %B %Y", "%B %d, %Y"):
        try:
            parsed = datetime.strptime(raw, pattern).replace(tzinfo=timezone.utc)
            return parsed.isoformat()
        except Exception:
            continue
    date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", raw)
    if date_match:
        try:
            parsed = datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return parsed.isoformat()
        except Exception:
            return ""
    return ""


def _is_recent_enough(published_at: str, recency_days: int) -> bool:
    raw = str(published_at or "").strip()
    if not raw:
        return False
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return False
    return parsed >= (_utc_now() - timedelta(days=max(1, int(recency_days or TREND_RESEARCH_RECENCY_DAYS))))


def _normalize_result(item: dict[str, Any], provider: str) -> dict[str, Any]:
    title = _clean_text(
        item.get("title")
        or item.get("name")
    )
    url = _clean_text(item.get("url") or item.get("href") or item.get("link"))
    snippet = _clean_text(
        item.get("content")
        or item.get("snippet")
        or item.get("body")
        or item.get("description")
    )
    published_at = (
        _parse_date_candidate(item.get("published_date"))
        or _parse_date_candidate(item.get("published_at"))
        or _parse_date_candidate(item.get("date"))
        or _parse_date_candidate(item.get("source_date"))
    )
    return {
        "title": title,
        "url": url,
        "snippet": snippet,
        "domain": _domain_from_url(url),
        "published_at": published_at,
        "provider": provider,
    }


def _cache_key(query: str, max_results: int, recency_days: int) -> str:
    return f"{_clean_text(query).lower()}::{int(max_results)}::{int(recency_days)}"


def _get_cached_query(query: str, max_results: int, recency_days: int) -> dict[str, Any] | None:
    key = _cache_key(query, max_results, recency_days)
    cached = _QUERY_CACHE.get(key)
    if not cached:
        return None
    cached_at, payload = cached
    if (time.time() - cached_at) > TREND_QUERY_CACHE_TTL_SECONDS:
        _QUERY_CACHE.pop(key, None)
        return None
    return dict(payload)


def _store_cached_query(query: str, max_results: int, recency_days: int, payload: dict[str, Any]) -> None:
    _QUERY_CACHE[_cache_key(query, max_results, recency_days)] = (time.time(), dict(payload))


def _set_health_success(provider: str, *, degraded: bool = False) -> None:
    with _HEALTH_LOCK:
        _HEALTH["provider"] = provider
        _HEALTH["available"] = True
        _HEALTH["degraded"] = bool(degraded)
        _HEALTH["last_success_at"] = _utc_now_iso()
        _HEALTH["last_error"] = ""


def _set_health_error(provider: str, error: str) -> None:
    with _HEALTH_LOCK:
        _HEALTH["provider"] = provider
        _HEALTH["available"] = False
        _HEALTH["degraded"] = provider == "ddgs"
        _HEALTH["last_error"] = _clean_text(error)


def get_trend_research_health() -> dict[str, Any]:
    with _HEALTH_LOCK:
        return dict(_HEALTH)


def _search_tavily(query: str, max_results: int, recency_days: int) -> dict[str, Any]:
    api_key = str(os.getenv("TAVILY_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured.")
    try:
        from tavily import TavilyClient  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"Tavily SDK unavailable: {exc}") from exc

    client = TavilyClient(api_key=api_key)
    payload = client.search(
        query=query,
        topic="news",
        search_depth="advanced",
        max_results=max_results,
        include_answer=False,
        include_raw_content=False,
        days=max(1, min(int(recency_days), 30)),
    )
    results = [_normalize_result(item, "tavily") for item in (payload.get("results") or [])]
    recent_results = [item for item in results if item["url"] and _is_recent_enough(item["published_at"], recency_days)]
    _set_health_success("tavily", degraded=False)
    return {
        "query": query,
        "provider": "tavily",
        "degraded": False,
        "results": recent_results,
        "total_results": len(recent_results),
        "insufficient_recent_sources": len(recent_results) < TREND_MIN_RECENT_RESULTS,
        "fetched_at": _utc_now_iso(),
    }


def _search_ddgs(query: str, max_results: int, recency_days: int) -> dict[str, Any]:
    try:
        from ddgs import DDGS  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"DDGS unavailable: {exc}") from exc

    timelimit = "m" if int(recency_days or TREND_RESEARCH_RECENCY_DAYS) <= 31 else "y"
    with DDGS(timeout=TREND_DDGS_TIMEOUT_SECONDS) as ddgs:
        raw_results: list[dict[str, Any]] = []
        try:
            raw_results.extend(list(ddgs.news(query, max_results=max_results, timelimit=timelimit)))
        except Exception:
            logger.debug("DDGS news lookup failed for %s", query, exc_info=True)
        if len(raw_results) < max_results:
            try:
                raw_results.extend(
                    list(ddgs.text(query, max_results=max_results, timelimit=timelimit))
                )
            except Exception:
                logger.debug("DDGS text lookup failed for %s", query, exc_info=True)
    results = [_normalize_result(item, "ddgs") for item in raw_results]
    deduped_results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in results:
        url = str(item.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        deduped_results.append(item)
    recent_results = [item for item in deduped_results if item["url"] and _is_recent_enough(item["published_at"], recency_days)]
    _set_health_success("ddgs", degraded=True)
    return {
        "query": query,
        "provider": "ddgs",
        "degraded": True,
        "results": recent_results,
        "total_results": len(recent_results),
        "insufficient_recent_sources": len(recent_results) < TREND_MIN_RECENT_RESULTS,
        "fetched_at": _utc_now_iso(),
    }


def search_recent(query: str, *, max_results: int | None = None, recency_days: int | None = None, force_refresh: bool = False) -> dict[str, Any]:
    safe_query = _clean_text(query)
    safe_limit = max(1, min(int(max_results or TREND_MAX_RESULTS_PER_QUERY), 8))
    safe_days = max(1, min(int(recency_days or TREND_RESEARCH_RECENCY_DAYS), 30))
    if not safe_query:
        return {
            "query": "",
            "provider": "",
            "degraded": False,
            "results": [],
            "total_results": 0,
            "insufficient_recent_sources": True,
            "error": "Query is empty.",
            "recency_days": safe_days,
        }
    if not force_refresh:
        cached = _get_cached_query(safe_query, safe_limit, safe_days)
        if cached:
            return cached

    errors: list[str] = []
    for provider in ("tavily", "ddgs"):
        try:
            if provider == "tavily":
                payload = _search_tavily(safe_query, safe_limit, safe_days)
            else:
                payload = _search_ddgs(safe_query, safe_limit, safe_days)
            payload = {**payload, "recency_days": safe_days}
            _store_cached_query(safe_query, safe_limit, safe_days, payload)
            return payload
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
            _set_health_error(provider, str(exc))
            continue

    return {
        "query": safe_query,
        "provider": "",
        "degraded": True,
        "results": [],
        "total_results": 0,
        "insufficient_recent_sources": True,
        "error": " | ".join(errors) if errors else "Trend research unavailable.",
        "fetched_at": _utc_now_iso(),
        "recency_days": safe_days,
    }


def _extract_html_text(raw_html: str) -> str:
    text = str(raw_html or "")
    if not text:
        return ""
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", text)
    text = re.sub(r"(?is)<(br|/p|/div|/section|/article|/li|/h[1-6])[^>]*>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html_unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_tag_content(raw_html: str, pattern: str) -> list[str]:
    matches = re.findall(pattern, raw_html or "", flags=re.IGNORECASE | re.DOTALL)
    return [_clean_text(re.sub(r"<[^>]+>", " ", html_unescape(match))) for match in matches if _clean_text(match)]


def _extract_keyword_candidates(text: str, limit: int = 10) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9&'’/-]{2,}", str(text or ""))
    counts: dict[str, int] = {}
    for token in tokens:
        key = token.lower()
        if key in _STOPWORDS:
            continue
        counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token.replace("-", " ") for token, _count in ranked[:limit]]


def extract_website_digest(url: str) -> dict[str, Any]:
    safe_url = _clean_text(url)
    if not safe_url:
        return {"status": "error", "reason": "Website URL is empty."}
    if not re.match(r"^https?://", safe_url, re.IGNORECASE):
        safe_url = f"https://{safe_url}"
    started_at = time.perf_counter()
    try:
        response = requests.get(
            safe_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Jarvis/1.0; +https://localhost)",
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
            },
            timeout=(4, 8),
        )
    except Exception as exc:
        return {"status": "error", "reason": f"Website fetch failed: {exc}"}
    if response.status_code >= 400:
        return {"status": "error", "reason": f"Website returned HTTP {response.status_code}."}
    html = response.text or ""
    text = _extract_html_text(html)
    title_matches = _extract_tag_content(html, r"<title[^>]*>(.*?)</title>")
    meta_matches = re.findall(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, flags=re.IGNORECASE | re.DOTALL)
    h1_matches = _extract_tag_content(html, r"<h1[^>]*>(.*?)</h1>")
    h2_matches = _extract_tag_content(html, r"<h2[^>]*>(.*?)</h2>")
    excerpt = "\n".join(line.strip() for line in text.splitlines() if line.strip())[:1200]
    digest = {
        "status": "success",
        "url": safe_url,
        "title": title_matches[0] if title_matches else "",
        "meta_description": _clean_text(meta_matches[0]) if meta_matches else "",
        "h1": h1_matches[:4],
        "h2": h2_matches[:8],
        "headings": [item for item in [*h1_matches[:4], *h2_matches[:8]] if _clean_text(item)][:10],
        "service_terms": _extract_keyword_candidates(" ".join(h1_matches + h2_matches + [excerpt]), limit=12),
        "brand_keywords": _extract_keyword_candidates(" ".join(filter(None, [title_matches[0] if title_matches else "", meta_matches[0] if meta_matches else "", excerpt])), limit=12),
        "excerpt": excerpt,
        "fetched_at": _utc_now_iso(),
        "fetch_ms": round((time.perf_counter() - started_at) * 1000),
    }
    digest, _report = sanitize_website_digest(digest)
    return digest


def _profile_signature(profile: dict[str, Any], goal: str = "", campaign_context: str = "") -> str:
    seed = {
        "business_name": str(profile.get("business_name") or "").strip(),
        "industry": str(profile.get("industry") or "").strip(),
        "services": [str(item).strip() for item in (profile.get("services") or []) if str(item).strip()],
        "target_audience": str(profile.get("target_audience") or "").strip(),
        "identity": str(profile.get("identity") or "").strip(),
        "seo_keywords": [str(item).strip() for item in (profile.get("seo_keywords") or []) if str(item).strip()],
        "brand_voice": profile.get("brand_voice") or {},
        "language_profile": profile.get("language_profile") or {},
        "website_url": str(profile.get("website_url") or "").strip(),
        "goal": _clean_text(goal),
        "campaign_context": _clean_text(campaign_context),
    }
    return hashlib.sha1(json.dumps(seed, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _load_client_payloads(client_id: str) -> tuple[dict[str, Any], dict[str, Any], Any]:
    store = get_client_store()
    client = store.get_client(client_id) or {}
    profile = dict(client.get("profile_json") or {})
    brand = store.get_brand_profile(client_id) or {}
    return client, profile, brand


def _persist_client_research(client_id: str, *, profile: dict[str, Any], brand: dict[str, Any]) -> None:
    store = get_client_store()
    client = store.get_client(client_id) or {}
    if client:
        client["profile_json"] = dict(profile)
        store.save_client(client_id, client)
    if brand:
        store.save_brand_profile(client_id, dict(brand))


def save_client_trend_dossier(client_id: str, dossier: dict[str, Any]) -> dict[str, Any]:
    safe_client_id = str(client_id or "").strip()
    safe_dossier = dict(dossier or {})
    if not safe_client_id:
        return safe_dossier
    safe_dossier["client_id"] = safe_client_id
    if not _clean_text(safe_dossier.get("built_at")):
        safe_dossier["built_at"] = _clean_text(safe_dossier.get("fetched_at")) or _utc_now_iso()
    store = get_client_store()
    return store.save_trend_dossier(safe_client_id, safe_dossier)


def _load_saved_client_trend_dossier(client_id: str) -> dict[str, Any] | None:
    safe_client_id = str(client_id or "").strip()
    if not safe_client_id:
        return None
    store = get_client_store()
    payload = store.get_trend_dossier(safe_client_id)
    if not isinstance(payload, dict) or not payload:
        return None
    saved = dict(payload)
    saved["client_id"] = safe_client_id
    if not _clean_text(saved.get("built_at")):
        saved["built_at"] = _clean_text(saved.get("fetched_at")) or _utc_now_iso()
    return saved


def ensure_client_website_digest(client_id: str, *, force_refresh: bool = False) -> dict[str, Any] | None:
    client, profile, brand = _load_client_payloads(client_id)
    if not client:
        return None
    website_url = _clean_text(profile.get("website_url"))
    if not website_url:
        return None
    current_digest = profile.get("website_digest") if isinstance(profile.get("website_digest"), dict) else {}
    if not force_refresh and current_digest and _clean_text(current_digest.get("url")) == website_url:
        return current_digest
    digest = extract_website_digest(website_url)
    if digest.get("status") != "success":
        return current_digest or None
    profile["website_digest"] = digest
    brand["website_digest"] = digest
    _persist_client_research(client_id, profile=profile, brand=brand)
    return digest


def _build_research_queries(client_id: str, profile: dict[str, Any], website_digest: dict[str, Any] | None, goal: str, campaign_context: str) -> list[str]:
    business_name = _clean_text(profile.get("business_name") or client_id.replace("_", " "))
    industry = _clean_text(profile.get("industry") or profile.get("business_type") or "brand")
    services = [str(item).strip() for item in (profile.get("services") or []) if str(item).strip()]
    audience = _clean_text(profile.get("target_audience"))
    market = _clean_text(
        profile.get("city_market")
        or profile.get("market")
        or profile.get("city")
        or profile.get("location")
    )
    main_language = _clean_text(profile.get("main_language"))
    lang = profile.get("language_profile") or {}
    caption_language = str(lang.get("caption_output_language") or "").strip().lower()
    if not main_language:
        if caption_language == "bilingual":
            main_language = "both"
        elif caption_language:
            main_language = caption_language
    locale_hint = market or ("gulf market" if caption_language == "arabic" else "english market")
    keyword_seed = [str(item).strip() for item in (profile.get("seo_keywords") or []) if str(item).strip()][:3]
    website_terms = [str(item).strip() for item in ((website_digest or {}).get("service_terms") or []) if str(item).strip()][:3]
    service_seed = ", ".join((services[:3] or website_terms[:3]))
    service_or_offer = _clean_text(service_seed or profile.get("what_they_sell") or industry or business_name)
    language_hint = {
        "arabic": "arabic social media",
        "both": "arabic and english social media",
        "bilingual": "arabic and english social media",
    }.get(main_language.lower(), "english social media") if main_language else ("arabic social media" if caption_language == "arabic" else "english social media")
    audience_hint = audience or service_or_offer or business_name

    candidates = [
        f"{industry} trending captions and hooks last 30 days {locale_hint} {language_hint}",
        f"{industry} trending hashtags last 30 days {locale_hint}",
        f"{industry} best performing social content formats last 30 days {audience_hint} {locale_hint}",
        f"{business_name} {service_or_offer} social media trends last 30 days {locale_hint}",
        f"{business_name} {goal or campaign_context or industry} campaign ideas last 30 days {locale_hint}",
    ]
    if keyword_seed:
        candidates.append(f"{' '.join(keyword_seed)} trending conversations last 30 days {locale_hint} {language_hint}")
    if campaign_context:
        candidates.append(f"{campaign_context} consumer trends last 30 days {business_name} {locale_hint}")
    if audience:
        candidates.append(f"{industry} content performing well with {audience} last 30 days {locale_hint}")
    if market:
        candidates.append(f"{industry} local hashtags and social trends {market} last 30 days")

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _clean_text(candidate)
        lowered = normalized.lower()
        if not normalized or lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(normalized)
        if len(deduped) >= TREND_MAX_QUERIES:
            break
    return deduped


def _build_llm_client() -> tuple[OpenAI, str] | tuple[None, str]:
    openrouter_key = str(os.getenv("OPENROUTER_API_KEY") or "").strip()
    openai_key = str(os.getenv("OPENAI_API_KEY") or "").strip()

    if openrouter_key:
        model = TREND_DOSSIER_MODEL or "openai/gpt-4o-mini"
        return build_sync_client("openrouter", timeout=TREND_LLM_TIMEOUT_SECONDS, max_retries=0), model

    if openai_key:
        model = TREND_DOSSIER_MODEL or "gpt-4o-mini"
        return build_sync_client("openai", timeout=TREND_LLM_TIMEOUT_SECONDS, max_retries=0), model

    return None, ""



def _extract_json_object(raw: str) -> dict[str, Any]:
    text = _clean_text(raw)
    if not text:
        return {}
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    if start == -1:
        return {}
    depth = 0
    for index, char in enumerate(text[start:], start=start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                snippet = text[start:index + 1]
                try:
                    parsed = json.loads(snippet)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    return {}
    return {}


def _heuristic_dossier(results: list[dict[str, Any]], goal: str, campaign_context: str) -> dict[str, Any]:
    snippets = " ".join(filter(None, [item.get("title") or "" for item in results] + [item.get("snippet") or "" for item in results]))
    keywords = _extract_keyword_candidates(snippets, limit=8)
    source_links = [
        {"title": item.get("title") or item.get("domain") or "Source", "url": item.get("url"), "published_at": item.get("published_at") or ""}
        for item in results[:6]
        if item.get("url")
    ]
    angles = keywords[:4] or [_clean_text(goal or campaign_context or "Current customer demand")]
    hooks = [f"Lead with {angle.lower()} in the opening line." for angle in angles[:4]]
    hashtags = [f"#{re.sub(r'[^A-Za-z0-9]+', '', keyword.title())}" for keyword in keywords[:6] if keyword]
    return {
        "research_summary": _clean_text(goal or campaign_context) or "Recent signals were gathered, but Jarvis used fallback heuristics to distill them.",
        "trend_angles": angles[:6],
        "hook_patterns": hooks[:5],
        "hashtag_candidates": hashtags[:8],
        "topical_language": keywords[:8],
        "anti_cliche_guidance": [
            "Avoid generic hype words.",
            "Use product-specific language from the brand profile and recent market signals.",
        ],
        "source_links": source_links[:6],
        "source_signals": [_clean_text(item.get("title") or item.get("domain")) for item in results[:6] if _clean_text(item.get("title") or item.get("domain"))],
        "recent_signals": [_clean_text(item.get("title") or item.get("domain")) for item in results[:6] if _clean_text(item.get("title") or item.get("domain"))],
    }


def _distill_trend_dossier(client_id: str, profile: dict[str, Any], results: list[dict[str, Any]], goal: str, campaign_context: str, website_digest: dict[str, Any] | None) -> dict[str, Any]:
    if not results:
        return _heuristic_dossier([], goal, campaign_context)
    client, model = _build_llm_client()
    if not client or not model:
        return _heuristic_dossier(results, goal, campaign_context)
    compact_profile = {
        "business_name": profile.get("business_name") or client_id,
        "industry": profile.get("industry") or "",
        "services": profile.get("services") or [],
        "target_audience": profile.get("target_audience") or "",
        "brand_voice": profile.get("brand_voice") or {},
        "seo_keywords": profile.get("seo_keywords") or [],
        "language_profile": profile.get("language_profile") or {},
        "website_digest": website_digest or {},
    }
    search_brief = [
        {
            "title": item.get("title"),
            "url": item.get("url"),
            "domain": item.get("domain"),
            "published_at": item.get("published_at"),
            "snippet": item.get("snippet"),
        }
        for item in results[:10]
    ]
    prompt = (
        "You are Jarvis Trend Dossier. Distill the research into a compact JSON object for premium social media planning.\n"
        "Return ONLY valid JSON with exactly these keys: "
        "{\"research_summary\": string, \"trend_angles\": [string], \"hook_patterns\": [string], "
        "\"hashtag_candidates\": [string], \"topical_language\": [string], \"anti_cliche_guidance\": [string], "
        "\"source_links\": [{\"title\": string, \"url\": string, \"published_at\": string}], "
        "\"source_signals\": [string]}.\n"
        "Rules:\n"
        "- Use only the supplied recent sources.\n"
        "- Keep everything grounded in the brand voice.\n"
        "- Prefer specific current angles over generic marketing language.\n"
        "- Hashtags must be realistic and usable, not inflated spam.\n"
        "- anti_cliche_guidance must explicitly reduce AI-smell.\n\n"
        f"Client profile JSON:\n{json.dumps(compact_profile, ensure_ascii=False)}\n\n"
        f"Goal: {_clean_text(goal) or 'No explicit goal provided.'}\n"
        f"Campaign context: {_clean_text(campaign_context) or 'No explicit campaign context provided.'}\n\n"
        f"Recent source pack JSON:\n{json.dumps(search_brief, ensure_ascii=False)}"
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Return only JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=700,
            response_format={"type": "json_object"},
        )
        payload = _extract_json_object(response.choices[0].message.content or "")
        if not payload:
            return _heuristic_dossier(results, goal, campaign_context)
        return {
            "research_summary": _clean_text(payload.get("research_summary")) or "Recent market signals distilled for Jarvis.",
            "trend_angles": [item for item in [_clean_text(v) for v in (payload.get("trend_angles") or [])] if item][:6],
            "hook_patterns": [item for item in [_clean_text(v) for v in (payload.get("hook_patterns") or [])] if item][:6],
            "hashtag_candidates": [item for item in [_clean_text(v) for v in (payload.get("hashtag_candidates") or [])] if item][:10],
            "topical_language": [item for item in [_clean_text(v) for v in (payload.get("topical_language") or [])] if item][:10],
            "anti_cliche_guidance": [item for item in [_clean_text(v) for v in (payload.get("anti_cliche_guidance") or [])] if item][:8],
            "source_links": [
                {
                    "title": _clean_text(item.get("title")),
                    "url": _clean_text(item.get("url")),
                    "published_at": _clean_text(item.get("published_at")),
                }
                for item in (payload.get("source_links") or [])
                if _clean_text((item or {}).get("url"))
            ][:6],
            "source_signals": [item for item in [_clean_text(v) for v in (payload.get("source_signals") or [])] if item][:8],
            "recent_signals": [item for item in [_clean_text(v) for v in (payload.get("source_signals") or [])] if item][:8],
        }
    except Exception as exc:
        logger.warning("Trend dossier distillation fallback for %s: %s", client_id, exc)
        return _heuristic_dossier(results, goal, campaign_context)


def _merge_unique_results(query_packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for packet in query_packets:
        for item in (packet.get("results") or []):
            key = str(item.get("url") or "").strip()
            if not key:
                continue
            merged.setdefault(key, item)
    return list(merged.values())


def build_client_trend_dossier(client_id: str) -> dict[str, Any]:
    safe_client_id = str(client_id or "").strip()
    if not safe_client_id:
        return {"status": "error", "reason": "Client ID is required."}
    existing = _load_saved_client_trend_dossier(safe_client_id)
    if existing:
        logger.info("TREND DOSSIER | Reusing existing saved dossier for %s", safe_client_id)
        return existing
    logger.info("TREND DOSSIER | Building permanent dossier for %s", safe_client_id)
    return get_client_trend_dossier(safe_client_id, force_refresh=True)


def get_client_trend_dossier(
    client_id: str,
    profile_hint: dict[str, Any] | None = None,
    *,
    goal: str = "",
    campaign_context: str = "",
    window: str = "",
    recency_days: int | None = None,
    force_refresh: bool = False,
    force: bool | None = None,
) -> dict[str, Any]:
    client, profile, brand = _load_client_payloads(client_id)
    if not client:
        return {"status": "error", "reason": f"Profile '{client_id}' not found."}
    for key in ("main_language", "city_market", "industry", "target_audience", "identity"):
        if profile.get(key) in (None, "", [], {}) and brand.get(key) not in (None, "", [], {}):
            profile[key] = brand.get(key)
    if not profile.get("services") and isinstance(brand.get("services"), list):
        profile["services"] = list(brand.get("services") or [])
    if not isinstance(profile.get("language_profile"), dict) and isinstance(brand.get("language_profile"), dict):
        profile["language_profile"] = dict(brand.get("language_profile") or {})
    if isinstance(profile_hint, dict):
        for key, value in profile_hint.items():
            if value not in (None, "", [], {}):
                profile[key] = value
    if force is not None:
        force_refresh = bool(force)

    saved_dossier = None if force_refresh else _load_saved_client_trend_dossier(client_id)
    if saved_dossier:
        return saved_dossier

    website_digest = ensure_client_website_digest(client_id, force_refresh=force_refresh)
    signature = _profile_signature(profile, goal=goal, campaign_context=campaign_context)
    existing = profile.get("trend_dossier") if isinstance(profile.get("trend_dossier"), dict) else {}
    if not force_refresh and existing:
        expires_at = _clean_text(existing.get("expires_at"))
        existing_signature = _clean_text(existing.get("profile_signature"))
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00")) if expires_at else None
        except Exception:
            expiry = None
        if expiry and expiry >= _utc_now() and existing_signature == signature:
            return existing

    safe_days = max(1, min(int(recency_days or TREND_RESEARCH_RECENCY_DAYS), 30))
    queries = _build_research_queries(client_id, profile, website_digest, goal, campaign_context)
    query_packets = [
        search_recent(query, max_results=TREND_MAX_RESULTS_PER_QUERY, recency_days=safe_days, force_refresh=force_refresh)
        for query in queries
    ]
    merged_results = _merge_unique_results(query_packets)
    distilled = _distill_trend_dossier(client_id, profile, merged_results, goal, campaign_context, website_digest)
    provider = next((packet.get("provider") for packet in query_packets if packet.get("provider")), "")
    degraded = any(bool(packet.get("degraded")) for packet in query_packets if packet)
    insufficient = len(merged_results) < TREND_MIN_RECENT_RESULTS or all(bool(packet.get("insufficient_recent_sources")) for packet in query_packets if packet)
    source_link_details = list(distilled.get("source_links") or [])
    source_links = [
        _clean_text(item.get("url"))
        for item in source_link_details
        if _clean_text((item or {}).get("url"))
    ]
    dossier = {
        "status": "success",
        "client_id": str(client_id or "").strip(),
        "provider": provider or "unavailable",
        "degraded": degraded,
        "insufficient_recent_sources": insufficient,
        "recency_days": safe_days,
        "fetched_at": _utc_now_iso(),
        "expires_at": (_utc_now() + timedelta(seconds=TREND_DOSSIER_TTL_SECONDS)).isoformat(),
        "profile_signature": signature,
        "window": _clean_text(window),
        "queries": query_packets,
        "source_count": len(merged_results),
        "total_recent_results": len(merged_results),
        "website_digest": website_digest or {},
        "source_coverage": f"{len(merged_results)} recent signals" if merged_results else "No recent research signals",
        "summary": distilled.get("research_summary", ""),
        "research_summary": distilled.get("research_summary", ""),
        "trend_angles": list(distilled.get("trend_angles") or []),
        "hook_patterns": list(distilled.get("hook_patterns") or []),
        "hashtag_candidates": list(distilled.get("hashtag_candidates") or []),
        "topical_language": list(distilled.get("topical_language") or []),
        "anti_cliche_guidance": list(distilled.get("anti_cliche_guidance") or []),
        "source_links": source_links,
        "source_link_details": source_link_details,
        "source_signals": list(distilled.get("source_signals") or []),
    }
    if "recent_signals" not in dossier:
        dossier["recent_signals"] = list(dossier.get("source_signals") or [])
    dossier["built_at"] = _utc_now_iso()

    profile["trend_dossier"] = dossier
    if website_digest:
        profile["website_digest"] = website_digest
    brand["trend_dossier"] = dossier
    if website_digest:
        brand["website_digest"] = website_digest
    _persist_client_research(client_id, profile=profile, brand=brand)
    return save_client_trend_dossier(client_id, dossier)
