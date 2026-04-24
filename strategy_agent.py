import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import requests

from agent import Agent
from client_store import get_client_store
from publish_run_store import list_publish_runs
from schedule_store import load_schedule, split_schedule_views
from strategy_plan_store import get_strategy_plan, list_strategy_plans, normalize_plan, save_strategy_plan
from trend_research_service import get_client_trend_dossier, get_trend_research_health, search_recent

logger = logging.getLogger("StrategyAgent")

ROBUST_CLIENT_MENTION_RE = re.compile(r"@\[(?P<client>[^\]]+)\]", re.IGNORECASE)
RAW_CLIENT_MENTION_RE = re.compile(r"(?<!\[)@(?P<client>[A-Za-z0-9_-]+)", re.IGNORECASE)
EXPLICIT_DRAFT_RE = re.compile(r"\bdraft\b", re.IGNORECASE)
EXECUTION_HINT_RE = re.compile(r"\b(post|publish|schedule|approve|run it|send for approval)\b", re.IGNORECASE)

STRATEGY_POSITIVE_PATTERNS = (
    re.compile(r"\bcontent strategy\b", re.IGNORECASE),
    re.compile(r"\bcontent plan\b", re.IGNORECASE),
    re.compile(r"\bcontent calendar\b", re.IGNORECASE),
    re.compile(r"\bcampaign plan\b", re.IGNORECASE),
    re.compile(r"\bcampaign ideas\b", re.IGNORECASE),
    re.compile(r"\bmonthly plan\b", re.IGNORECASE),
    re.compile(r"\bweekly plan\b", re.IGNORECASE),
    re.compile(r"\bwhat should (?:we|i) post\b", re.IGNORECASE),
    re.compile(r"\bwhat do you recommend\b", re.IGNORECASE),
    re.compile(r"\bcontent ideas\b", re.IGNORECASE),
    re.compile(r"\bposting ideas\b", re.IGNORECASE),
    re.compile(r"\bplan .*next week\b", re.IGNORECASE),
    re.compile(r"\bplan .*next month\b", re.IGNORECASE),
    re.compile(r"\bstrategy\b", re.IGNORECASE),
    re.compile(r"\btrend(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bcompetitor\b", re.IGNORECASE),
    re.compile(r"\bpillar(?:s)?\b", re.IGNORECASE),
)

WINDOW_NAMES = {"next_7_days", "next_30_days"}
STRATEGY_RESEARCH_RECENCY_DAYS = 30
STRATEGY_MIN_RECENT_SOURCES = 3
STRATEGY_MIN_DISTINCT_DOMAINS = 2
STRATEGY_REQUIRED_TOOLS = [
    "read_brand_profile",
    "read_recent_publish_history",
    "read_schedule_context",
    "web_search",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_strategy_model_name(configured: str | None = None) -> str:
    raw = str(configured or os.getenv("STRATEGY_AGENT_MODEL") or "").strip()
    if not raw:
        return "groq:llama-3.3-70b-versatile"
    if ":" in raw:
        return raw
    if raw.startswith("openai/gpt-oss-"):
        return f"groq:{raw}"
    return raw


def _normalize_client_match_text(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    cleaned = re.sub(r"[_\-]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def resolve_client_id(raw_id: str) -> str:
    raw = str(raw_id or "").strip()
    if not raw:
        return ""
    store = get_client_store()
    try:
        client_ids = store.list_client_ids()
    except Exception:
        client_ids = []
    for client_id in client_ids:
        if client_id.lower() == raw.lower():
            return client_id
    normalized_raw = _normalize_client_match_text(raw)
    for client_id in client_ids:
        if _normalize_client_match_text(client_id) == normalized_raw:
            return client_id
    return raw


def extract_strategy_client_id(prompt: str) -> str:
    raw = str(prompt or "").strip()
    if not raw:
        return ""
    robust = ROBUST_CLIENT_MENTION_RE.search(raw)
    if robust:
        return resolve_client_id(str(robust.group("client") or "").strip())
    store = get_client_store()
    try:
        client_ids = sorted(store.list_client_ids(), key=len, reverse=True)
    except Exception:
        client_ids = []
    normalized_raw = _normalize_client_match_text(raw)
    for client_id in client_ids:
        normalized_client = _normalize_client_match_text(client_id)
        if normalized_client and f"@{normalized_client}" in normalized_raw:
            return client_id
    loose = RAW_CLIENT_MENTION_RE.search(raw)
    if loose:
        return resolve_client_id(str(loose.group("client") or "").strip())
    return ""


def derive_strategy_window(prompt: str, explicit_window: str | None = None) -> str:
    normalized = str(explicit_window or "").strip().lower()
    if normalized in WINDOW_NAMES:
        return normalized
    text = str(prompt or "").strip().lower()
    if any(token in text for token in ("next month", "this month", "monthly", "30 day", "30-day")):
        return "next_30_days"
    if any(token in text for token in ("next week", "this week", "weekly", "7 day", "7-day")):
        return "next_7_days"
    if any(token in text for token in ("calendar", "campaign", "strategy", "plan")):
        return "next_30_days"
    return "next_7_days"


def prompt_requests_strategy(prompt: str) -> bool:
    raw = str(prompt or "").strip()
    if not raw:
        return False
    lowered = raw.lower()
    if EXPLICIT_DRAFT_RE.search(lowered) and EXECUTION_HINT_RE.search(lowered):
        return False
    if EXECUTION_HINT_RE.search(lowered) and not any(pattern.search(raw) for pattern in STRATEGY_POSITIVE_PATTERNS):
        return False
    return any(pattern.search(raw) for pattern in STRATEGY_POSITIVE_PATTERNS)


def build_strategy_request_from_prompt(prompt: str, default_client_id: str | None = None) -> dict[str, str]:
    raw = str(prompt or "").strip()
    client_id = extract_strategy_client_id(raw) or resolve_client_id(str(default_client_id or "").strip())
    return {
        "client_id": client_id,
        "window": derive_strategy_window(raw),
        "goal": raw,
        "campaign_context": "",
        "requested_prompt": raw,
    }


def _extract_first_json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    candidate = fenced_match.group(1) if fenced_match else text
    start = candidate.find("{")
    if start == -1:
        return {}
    depth = 0
    for idx in range(start, len(candidate)):
        char = candidate[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                snippet = candidate[start: idx + 1]
                try:
                    parsed = json.loads(snippet)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    return {}
    return {}


def _parse_iso_datetime(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _source_domain(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        hostname = str(urlparse(raw).hostname or "").strip().lower()
    except Exception:
        hostname = ""
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def _normalize_strategy_fingerprint_text(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = ROBUST_CLIENT_MENTION_RE.sub("", text)
    text = re.sub(r"(?<!\[)@[a-z0-9 _-]+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^/strategy\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,.-")


def _strategy_request_fingerprint(*, window: str, goal: str, requested_prompt: str) -> str:
    core = _normalize_strategy_fingerprint_text(requested_prompt) or _normalize_strategy_fingerprint_text(goal)
    return f"{str(window or '').strip().lower()}::{core}"


def _match_existing_strategy_plan(
    client_id: str,
    *,
    window: str,
    goal: str,
    requested_prompt: str,
) -> dict[str, Any] | None:
    target = _strategy_request_fingerprint(window=window, goal=goal, requested_prompt=requested_prompt)
    if not target or target.endswith("::"):
        return None
    for plan in list_strategy_plans(client_id):
        existing = _strategy_request_fingerprint(
            window=str(plan.get("window") or plan.get("timeframe") or "").strip(),
            goal=str(plan.get("goal") or "").strip(),
            requested_prompt=str(plan.get("requested_prompt") or "").strip(),
        )
        if existing == target:
            return plan
    return None


def _collect_research_source_details(snapshot: dict[str, Any] | None) -> list[dict[str, str]]:
    payload = snapshot if isinstance(snapshot, dict) else {}
    prepared: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    candidates = []
    candidates.extend(payload.get("source_link_details") or [])
    queries = payload.get("queries") if isinstance(payload.get("queries"), list) else []
    for packet in queries:
        if not isinstance(packet, dict):
            continue
        candidates.extend(packet.get("results") or [])
    for item in candidates:
        if isinstance(item, dict):
            url = str(item.get("url") or item.get("link") or "").strip()
            title = str(item.get("title") or item.get("label") or item.get("source") or "Source").strip()
            published_at = str(item.get("published_at") or "").strip()
        else:
            url = str(item or "").strip()
            title = "Source"
            published_at = ""
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        prepared.append({"title": title or "Source", "url": url, "published_at": published_at})
    return prepared


def _format_window_label(window: str) -> str:
    raw = str(window or "").replace("_", " ").strip()
    return " ".join(part.capitalize() for part in raw.split()) or "Next 7 Days"


def _research_quality_report(snapshot: dict[str, Any] | None, *, recency_days: int = STRATEGY_RESEARCH_RECENCY_DAYS) -> dict[str, Any]:
    payload = snapshot if isinstance(snapshot, dict) else {}
    details = _collect_research_source_details(payload)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(recency_days or STRATEGY_RESEARCH_RECENCY_DAYS)))
    recent_details: list[dict[str, str]] = []
    stale_details: list[dict[str, str]] = []
    distinct_domains: set[str] = set()
    for item in details:
        published_at = _parse_iso_datetime(item.get("published_at") or "")
        if published_at is not None and published_at < cutoff:
            stale_details.append(item)
            continue
        recent_details.append(item)
        domain = _source_domain(item.get("url") or "")
        if domain:
            distinct_domains.add(domain)
    errors: list[str] = []
    if str(payload.get("status") or "").strip().lower() != "success":
        errors.append(str(payload.get("reason") or "Live research did not complete successfully.").strip())
    if payload.get("insufficient_recent_sources"):
        errors.append("Live research returned too few recent signals.")
    if len(recent_details) < STRATEGY_MIN_RECENT_SOURCES:
        errors.append(
            f"Jarvis needs at least {STRATEGY_MIN_RECENT_SOURCES} recent sources, but only found {len(recent_details)}."
        )
    if len(distinct_domains) < STRATEGY_MIN_DISTINCT_DOMAINS:
        errors.append(
            f"Jarvis needs research from at least {STRATEGY_MIN_DISTINCT_DOMAINS} domains, but only found {len(distinct_domains)}."
        )
    if stale_details:
        errors.append(
            f"{len(stale_details)} research source(s) fell outside the last {recency_days} days."
        )
    provider = str(payload.get("provider") or "").strip()
    freshness = (
        f"{len(recent_details)} recent source(s) across {len(distinct_domains)} domain(s)"
        + (f" via {provider}" if provider else "")
    )
    return {
        "ok": not errors,
        "errors": list(dict.fromkeys(error for error in errors if error)),
        "recent_details": recent_details,
        "stale_details": stale_details,
        "distinct_domains": sorted(distinct_domains),
        "provider": provider or "unavailable",
        "freshness": freshness,
        "source_count": len(recent_details),
        "domain_count": len(distinct_domains),
    }


def _strategy_error(message: str, *, client_id: str = "", research_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"error": str(message or "Strategy planning failed.").strip()}
    if client_id:
        payload["client_id"] = client_id
    if isinstance(research_snapshot, dict) and research_snapshot:
        payload["research_snapshot"] = research_snapshot
    return payload


def _strategy_query_phrase(value: Any) -> str:
    phrase = re.sub(r"\s+", " ", str(value or "").strip())
    return phrase[:120].strip(" ,.-")


def _build_strategy_search_queries(client_id: str, brand_context: dict[str, Any], goal_text: str, window_name: str) -> list[str]:
    business_name = _strategy_query_phrase(
        brand_context.get("business_name") or brand_context.get("brand_name") or client_id
    )
    industry = _strategy_query_phrase(brand_context.get("industry") or brand_context.get("business_type"))
    market = _strategy_query_phrase(brand_context.get("city_market") or brand_context.get("market"))
    audience = _strategy_query_phrase(brand_context.get("target_audience") or brand_context.get("audience_summary"))
    services = [
        _strategy_query_phrase(item)
        for item in (brand_context.get("services") or [])
        if _strategy_query_phrase(item)
    ][:3]
    goal = _strategy_query_phrase(goal_text)

    base_terms = [term for term in [business_name, industry, market] if term]
    category_focus = ", ".join(services[:2]) if services else (industry or business_name)
    demand_focus = goal or f"{category_focus} demand"
    audience_focus = audience or "customer behavior"
    freshness_hint = "last 30 days"
    window_focus = "next month" if str(window_name or "").strip() == "next_30_days" else "next week"

    queries = [
        " ".join(
            part
            for part in [
                business_name,
                category_focus,
                market,
                "consumer demand trends social media",
                freshness_hint,
            ]
            if part
        ).strip(),
        " ".join(
            part
            for part in [
                market or business_name,
                category_focus,
                audience_focus,
                "buying behavior campaign ideas",
                freshness_hint,
            ]
            if part
        ).strip(),
        " ".join(
            part
            for part in [
                market,
                demand_focus,
                "instagram facebook content trends",
                window_focus,
                freshness_hint,
            ]
            if part
        ).strip(),
    ]
    if services:
        queries.append(
            " ".join(
                part
                for part in [
                    business_name,
                    services[0],
                    market,
                    "seasonal trend audience reaction",
                    freshness_hint,
                ]
                if part
            ).strip()
        )

    prepared: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = re.sub(r"\s+", " ", str(query or "").strip())
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        prepared.append(normalized)

    if not prepared:
        fallback = " ".join(base_terms + [goal, "social media trends", freshness_hint]).strip()
        if fallback:
            prepared.append(fallback)
    return prepared[:4]


def _merge_strategy_search_packets(search_packets: list[dict[str, Any]]) -> dict[str, Any]:
    seen_urls: set[str] = set()
    merged_results: list[dict[str, Any]] = []
    query_packets: list[dict[str, Any]] = []
    providers: list[str] = []
    errors: list[str] = []

    for packet in search_packets:
        if not isinstance(packet, dict):
            continue
        provider = str(packet.get("provider") or "").strip()
        if provider:
            providers.append(provider)
        if str(packet.get("last_error") or "").strip():
            errors.append(str(packet.get("last_error") or "").strip())
        raw_results = []
        for item in (packet.get("results") or []):
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            normalized = {
                "title": str(item.get("title") or "").strip(),
                "url": url,
                "published_at": str(item.get("published_at") or "").strip(),
                "snippet": str(item.get("snippet") or item.get("body") or "").strip(),
            }
            merged_results.append(normalized)
            raw_results.append(normalized)
        query_packets.append(
            {
                "query": str(packet.get("query") or "").strip(),
                "provider": provider,
                "results": raw_results,
            }
        )

    provider_label = ", ".join(list(dict.fromkeys(provider for provider in providers if provider)))
    return {
        "status": "success" if merged_results else "error",
        "provider": provider_label,
        "results": merged_results[:8],
        "queries": query_packets,
        "last_error": " | ".join(dict.fromkeys(errors)),
    }


def _build_research_snapshot_from_search(search_packet: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(search_packet, list):
        packet = _merge_strategy_search_packets(search_packet)
    else:
        packet = search_packet if isinstance(search_packet, dict) else {}
    results = [item for item in (packet.get("results") or []) if isinstance(item, dict)]
    return {
        "status": "success" if results else "error",
        "provider": str(packet.get("provider") or "").strip(),
        "summary": " ".join(str(item.get("title") or "").strip() for item in results[:3] if str(item.get("title") or "").strip()),
        "trend_angles": [str(item.get("title") or "").strip() for item in results[:4] if str(item.get("title") or "").strip()],
        "hook_patterns": [],
        "source_signals": [str(item.get("snippet") or item.get("title") or "").strip()[:180] for item in results[:5] if str(item.get("snippet") or item.get("title") or "").strip()],
        "source_link_details": [
            {
                "title": str(item.get("title") or "Source").strip(),
                "url": str(item.get("url") or "").strip(),
                "published_at": str(item.get("published_at") or "").strip(),
            }
            for item in results
            if str(item.get("url") or "").strip()
        ],
        "queries": packet.get("queries") if isinstance(packet.get("queries"), list) else [],
        "insufficient_recent_sources": bool(packet.get("status") != "success"),
    }


def _compact_brand_context_snapshot(brand_context: dict[str, Any]) -> dict[str, Any]:
    payload = dict(brand_context or {})
    voice = payload.get("brand_voice") if isinstance(payload.get("brand_voice"), dict) else {}
    return {
        "business_name": str(payload.get("business_name") or "").strip(),
        "industry": str(payload.get("industry") or payload.get("business_type") or "").strip(),
        "city_market": str(payload.get("city_market") or payload.get("market") or "").strip(),
        "target_audience": str(payload.get("target_audience") or payload.get("audience_summary") or "").strip(),
        "brand_tone": str(payload.get("brand_tone") or voice.get("tone") or "").strip(),
        "services": [str(item).strip() for item in (payload.get("services") or []) if str(item).strip()][:6],
        "words_to_avoid": [str(item).strip() for item in (payload.get("words_to_avoid") or []) if str(item).strip()][:8],
    }


def _compact_research_snapshot(research_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    payload = research_snapshot if isinstance(research_snapshot, dict) else {}
    compact = {
        "provider": str(payload.get("provider") or "").strip(),
        "summary": str(payload.get("summary") or payload.get("research_summary") or "").strip(),
        "trend_angles": [str(item).strip() for item in (payload.get("trend_angles") or []) if str(item).strip()][:5],
        "hook_patterns": [str(item).strip() for item in (payload.get("hook_patterns") or []) if str(item).strip()][:5],
        "recent_signals": [str(item).strip() for item in (payload.get("source_signals") or payload.get("recent_signals") or []) if str(item).strip()][:6],
        "website_digest": {},
        "source_links": [],
    }
    website_digest = payload.get("website_digest") if isinstance(payload.get("website_digest"), dict) else {}
    compact["website_digest"] = {
        "title": str(website_digest.get("title") or "").strip(),
        "meta_description": str(website_digest.get("meta_description") or "").strip()[:220],
        "service_terms": [str(item).strip() for item in (website_digest.get("service_terms") or []) if str(item).strip()][:6],
    }
    for item in _collect_research_source_details(payload)[:5]:
        compact["source_links"].append(
            {
                "title": str(item.get("title") or "Source").strip(),
                "url": str(item.get("url") or "").strip(),
                "published_at": str(item.get("published_at") or "").strip(),
            }
        )
    return compact


def _build_strategy_prompt(
    *,
    client_id: str,
    window_name: str,
    goal_text: str,
    campaign_text: str,
    research_health: dict[str, Any],
    brand_profile: dict[str, Any],
    publish_history: dict[str, Any],
    schedule_context: dict[str, Any],
    web_research: dict[str, Any],
    meta_insights: dict[str, Any],
) -> str:
    health_payload = {
        "tavily": (research_health.get("tavily") if isinstance(research_health.get("tavily"), dict) else {}),
        "ddgs": (research_health.get("ddgs") if isinstance(research_health.get("ddgs"), dict) else {}),
    }
    compact_brand = brand_profile if isinstance(brand_profile, dict) else {}
    compact_publish = publish_history if isinstance(publish_history, dict) else {}
    compact_schedule = schedule_context if isinstance(schedule_context, dict) else {}
    compact_research = _compact_research_snapshot(web_research)
    compact_meta = meta_insights if isinstance(meta_insights, dict) else {}
    return (
        f"Build a strategy plan for client '{client_id}'. "
        f"Window: {window_name}. "
        f"Goal: {goal_text or 'No explicit goal provided.'} "
        f"Campaign context: {campaign_text or 'No extra campaign context provided.'}\n\n"
        f"Brand profile:\n{json.dumps(compact_brand, ensure_ascii=False)}\n\n"
        f"Recent publish history:\n{json.dumps(compact_publish, ensure_ascii=False)}\n\n"
        f"Schedule context:\n{json.dumps(compact_schedule, ensure_ascii=False)}\n\n"
        f"Research health:\n{json.dumps(health_payload, ensure_ascii=False)}\n\n"
        f"Live web research:\n{json.dumps(compact_research, ensure_ascii=False)}\n\n"
        f"Meta insights:\n{json.dumps(compact_meta, ensure_ascii=False)}\n\n"
        "Instructions:\n"
        "- Treat the live web research as mandatory primary evidence. Prefer repeating patterns that appear across multiple fresh sources or domains.\n"
        "- Use the brand profile, market, services, and operator goal to infer what the audience currently cares about.\n"
        "- Keep the plan concrete, specific, and execution-ready.\n"
        "- Every item must contain source_signals and source_links.\n"
        "- Keep the JSON compact enough to fit in one response: 6 items max for next_30_days, 4 items max for next_7_days.\n"
        "- Keep each topic under 10 words, each hook_direction under 22 words, and each rationale under 32 words.\n"
        "- Use at most 2 source_signals per item and at most 1 source_link per item.\n"
        "- Do not rely on generic content pillars unless the brand profile and recent research directly support them.\n"
        "- Prioritize fresh signals from the last 30 days, especially local demand, seasonal behavior, competitor movement, and platform-native content patterns."
    )


class StrategyClientBriefTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "read_brand_profile",
                "description": "Read the client's saved brand profile and credentials context. Use this first before making strategy recommendations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string", "description": "The target client ID."}
                    },
                    "required": ["client_id"],
                },
            },
        }

    def execute(self, client_id: str):
        resolved = resolve_client_id(client_id)
        payload = get_client_store().get_client(resolved)
        if not payload:
            return {"error": f"Profile '{client_id}' not found."}
        profile = payload.get("profile_json") if isinstance(payload.get("profile_json"), dict) else {}
        return {
            "client_id": resolved,
            "profile_json": _compact_brand_context_snapshot(profile),
            "has_meta_credentials": bool(payload.get("meta_access_token")),
        }


class StrategyPublishHistoryTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "read_recent_publish_history",
                "description": "Read recent publish outcomes for a client. Use this for performance-informed planning and to avoid repeating failing patterns.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string", "description": "The target client ID."},
                        "limit": {"type": "integer", "description": "Maximum runs to inspect. Default 8, max 20."},
                    },
                    "required": ["client_id"],
                },
            },
        }

    def execute(self, client_id: str, limit: int = 8):
        resolved = resolve_client_id(client_id)
        safe_limit = max(1, min(int(limit or 8), 20))
        runs = [
            run for run in list_publish_runs()
            if str(run.get("client_id") or "").strip().lower() == resolved.lower()
        ][:safe_limit]
        summary = {
            "total_runs": len(runs),
            "published": 0,
            "partial_success": 0,
            "failed": 0,
            "recent_topics": [],
        }
        prepared = []
        for run in runs:
            status = str(run.get("status") or "").strip().lower()
            if status in summary:
                summary[status] += 1
            topic = str(run.get("topic") or "").strip()
            if topic:
                summary["recent_topics"].append(topic)
            prepared.append(
                {
                    "run_id": str(run.get("run_id") or "").strip(),
                    "status": status or "unknown",
                    "topic": topic[:80],
                    "created_at": str(run.get("created_at") or "").strip(),
                    "platform_results": {
                        str(name): str((result or {}).get("status") or "").strip()
                        for name, result in (run.get("platform_results") or {}).items()
                        if isinstance(result, dict)
                    } if isinstance(run.get("platform_results"), dict) else {},
                }
            )
        return {"client_id": resolved, "summary": summary, "runs": prepared[:5]}


class StrategyScheduleContextTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "read_schedule_context",
                "description": "Read scheduled and recently delivered releases for a client. Use this to avoid duplicates and understand current calendar load.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string", "description": "The target client ID."}
                    },
                    "required": ["client_id"],
                },
            },
        }

    def execute(self, client_id: str):
        resolved = resolve_client_id(client_id)
        jobs = load_schedule("schedule.json")
        active, history = split_schedule_views(jobs)
        normalize = lambda row: {
            "job_id": str(row.get("job_id") or "").strip(),
            "topic": str(row.get("topic") or "").strip(),
            "draft_name": str(row.get("draft_name") or "").strip(),
            "scheduled_date": str(row.get("scheduled_date") or "").strip(),
            "time": str(row.get("time") or "").strip(),
            "status": str(row.get("status") or "").strip(),
        }
        active_rows = [normalize(job) for job in active if str(job.get("client") or "").strip().lower() == resolved.lower()]
        history_rows = [normalize(job) for job in history if str(job.get("client") or "").strip().lower() == resolved.lower()][:6]
        return {"client_id": resolved, "active": active_rows[:4], "history": history_rows[:4]}


class StrategyWebSearchTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for trend, market, or competitor context. Use only when current external context materially improves the plan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "What to search for."},
                        "max_results": {"type": "integer", "description": "Default 5, max 8."},
                    },
                    "required": ["query"],
                },
            },
        }

    def execute(self, query: str, max_results: int = 5):
        safe_limit = max(1, min(int(max_results or 5), 8))
        pack = search_recent(query, max_results=safe_limit, recency_days=30, force_refresh=True)
        prepared_results = []
        for item in (pack.get("results") or [])[:5]:
            if not isinstance(item, dict):
                continue
            prepared_results.append(
                {
                    "title": str(item.get("title") or "").strip()[:140],
                    "url": str(item.get("url") or "").strip(),
                    "published_at": str(item.get("published_at") or "").strip(),
                    "snippet": str(item.get("snippet") or item.get("body") or "").strip()[:220],
                }
            )
        return {
            "query": query,
            "provider": pack.get("provider"),
            "status": "success" if prepared_results else "insufficient_recent_sources",
            "recency_days": 30,
            "results": prepared_results,
            "total": len(prepared_results),
            "last_error": pack.get("error", ""),
        }


class StrategyMetaInsightsTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "read_meta_insights",
                "description": "Read live Instagram and Facebook insight context for a client when Meta credentials are available.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string", "description": "The target client ID."},
                        "limit": {"type": "integer", "description": "Recent post limit. Default 5, max 12."},
                    },
                    "required": ["client_id"],
                },
            },
        }

    def execute(self, client_id: str, limit: int = 5):
        resolved = resolve_client_id(client_id)
        cdata = get_client_store().get_client(resolved) or {}
        access_token = str(cdata.get("meta_access_token") or "").strip()
        ig_user_id = str(cdata.get("instagram_account_id") or "").strip()
        fb_page_id = str(cdata.get("facebook_page_id") or "").strip()
        if not access_token:
            return {"error": f"No Meta access token is configured for {resolved}."}
        safe_limit = max(1, min(int(limit or 5), 12))
        payload: dict[str, Any] = {"client_id": resolved, "instagram": None, "facebook": None}

        if ig_user_id:
            try:
                media_resp = requests.get(
                    f"https://graph.facebook.com/v19.0/{ig_user_id}/media",
                    params={
                        "fields": "id,caption,timestamp,like_count,comments_count,media_type",
                        "limit": safe_limit,
                        "access_token": access_token,
                    },
                    timeout=10,
                ).json()
                if "error" in media_resp:
                    payload["instagram"] = {"error": media_resp["error"].get("message", "Unknown API error")}
                else:
                    posts = media_resp.get("data", []) or []
                    prepared = []
                    for post in posts:
                        prepared.append(
                            {
                                "id": str(post.get("id") or "").strip(),
                                "caption_preview": str(post.get("caption") or "")[:90].strip(),
                                "timestamp": str(post.get("timestamp") or "").strip(),
                                "likes": int(post.get("like_count") or 0),
                                "comments": int(post.get("comments_count") or 0),
                                "media_type": str(post.get("media_type") or "IMAGE").strip(),
                            }
                        )
                    payload["instagram"] = {
                        "total_posts_analyzed": len(prepared),
                        "recent_posts": prepared,
                    }
            except Exception as exc:
                payload["instagram"] = {"error": f"Failed to fetch Instagram insights: {str(exc)}"}

        if fb_page_id:
            try:
                fb_resp = requests.get(
                    f"https://graph.facebook.com/v19.0/{fb_page_id}",
                    params={"fields": "fan_count,name", "access_token": access_token},
                    timeout=10,
                ).json()
                if "error" in fb_resp:
                    payload["facebook"] = {"error": fb_resp["error"].get("message", "Unknown API error")}
                else:
                    payload["facebook"] = {
                        "page_name": str(fb_resp.get("name") or "").strip(),
                        "total_followers": int(fb_resp.get("fan_count") or 0),
                    }
            except Exception as exc:
                payload["facebook"] = {"error": f"Failed to fetch Facebook insights: {str(exc)}"}
        return payload


class StrategyAgent(Agent):
    def __init__(self):
        strategy_model = _resolve_strategy_model_name()
        super().__init__([], model=strategy_model)
        self.system_message = (
            "You are Jarvis Strategy Agent, a research-first strategist for marketing agencies. "
            "You do not publish, you do not schedule, and you do not invent fake certainty. "
            "You will receive a prefetched context bundle containing the brand profile, publish history, schedule context, live web research, and Meta insights when available. "
            "Plans must be client-specific, execution-ready, and grounded in recent evidence. "
            "Do not output generic content pillars unless the brand profile and research directly support them. "
            "Every item must include source signals and source links. "
            "If evidence is thin, mark needs_review=true, lower confidence, and say why without fabricating certainty. "
            "Return ONLY valid JSON with this exact top-level shape: "
            "{"
            "\"summary\": string, "
            "\"objective\": string, "
            "\"timeframe\": string, "
            "\"items\": ["
            "{"
            "\"topic\": string, "
            "\"format\": string, "
            "\"platforms\": [string], "
            "\"recommended_time\": string, "
            "\"hook_direction\": string, "
            "\"rationale\": string, "
            "\"source_signals\": [string], "
            "\"source_links\": [{\"title\": string, \"url\": string, \"published_at\": string}], "
            "\"needs_review\": boolean, "
            "\"confidence\": number"
            "}"
            "]"
            "}. "
            "Prefer 4 items for next_7_days and exactly 6 items for next_30_days unless the user explicitly asks for fewer. "
            "Keep the JSON compact so it fits in one response. "
            "Each topic should stay under 10 words. "
            "Each hook_direction should stay under 22 words. "
            "Each rationale should stay under 32 words. "
            "Use at most 2 source_signals per item and at most 1 source_link per item. "
            "Do not include markdown fences or prose outside the JSON object."
        )


def _coerce_plan_payload(
    payload: dict[str, Any],
    *,
    client_id: str,
    window: str,
    goal: str,
    campaign_context: str,
    requested_prompt: str,
    used_tools: list[str],
    research_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    research_payload = research_snapshot if isinstance(research_snapshot, dict) else {}
    payload_research = payload.get("research_snapshot") if isinstance(payload.get("research_snapshot"), dict) else {}
    raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    if not raw_items:
        for candidate_key in (
            derive_strategy_window(requested_prompt, window),
            str(payload.get("timeframe") or "").strip(),
            "next_30_days",
            "next_7_days",
        ):
            if isinstance(payload.get(candidate_key), list):
                raw_items = payload.get(candidate_key)
                break
    normalized_items: list[dict[str, Any]] = []
    for item in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(item, dict):
            continue
        normalized_links = item.get("source_links") if isinstance(item.get("source_links"), list) else []
        if not normalized_links and str(item.get("source_link") or "").strip():
            normalized_links = [
                {
                    "title": str(item.get("source_link_title") or "Source").strip(),
                    "url": str(item.get("source_link") or "").strip(),
                    "published_at": str(item.get("published_at") or "").strip(),
                }
            ]
        platforms = item.get("platforms") if isinstance(item.get("platforms"), list) else []
        if not platforms and str(item.get("platform") or "").strip():
            platforms = [str(item.get("platform") or "").strip()]
        normalized_items.append(
            {
                **item,
                "platforms": platforms,
                "recommended_time": str(item.get("recommended_time") or item.get("time") or "").strip(),
                "source_links": normalized_links,
            }
        )
    normalized = normalize_plan(
        {
            "client_id": client_id,
            "window": derive_strategy_window(requested_prompt, window),
            "goal": goal,
            "campaign_context": campaign_context,
            "summary": str(payload.get("summary") or "").strip(),
            "objective": str(payload.get("objective") or goal or "Build a practical cross-platform content plan.").strip(),
            "timeframe": str(payload.get("timeframe") or derive_strategy_window(requested_prompt, window)).strip(),
            "items": normalized_items,
            "sources_used": payload.get("sources_used") if isinstance(payload.get("sources_used"), list) else used_tools,
            "research_snapshot": research_payload or payload_research,
            "status": "ready",
        }
    )
    if not normalized["summary"]:
        normalized["summary"] = f"Strategy plan prepared for {client_id} across {normalized['timeframe']}."
    snapshot_links = []
    raw_snapshot_links = research_payload.get("source_link_details") or research_payload.get("source_links") or []
    if isinstance(raw_snapshot_links, list):
        for item in raw_snapshot_links[:6]:
            if isinstance(item, dict):
                url = str(item.get("url") or item.get("link") or "").strip()
                if not url:
                    continue
                snapshot_links.append(
                    {
                        "title": str(item.get("title") or item.get("label") or "Source").strip(),
                        "url": url,
                        "published_at": str(item.get("published_at") or "").strip(),
                    }
                )
            else:
                url = str(item or "").strip()
                if url:
                    snapshot_links.append({"title": "Source", "url": url, "published_at": ""})
    snapshot_signals = [
        str(signal).strip()
        for signal in ((research_payload.get("recent_signals") or []) or (research_payload.get("source_signals") or []))
        if str(signal).strip()
    ]
    for item in normalized["items"]:
        if not item.get("source_signals"):
            item["source_signals"] = list(dict.fromkeys([*(used_tools or []), *(snapshot_signals[:3] or []), "recent_research"]))
        if not item.get("source_links"):
            item["source_links"] = snapshot_links[:3]
    normalized["item_count"] = len(normalized["items"])
    quality = _research_quality_report(research_payload)
    normalized["research_freshness"] = quality.get("freshness") or ""
    normalized["research_provider"] = quality.get("provider") or ""
    return normalized


def _strategy_tool_enforcement_status(used_tools: list[str]) -> tuple[bool, list[str]]:
    seen = list(dict.fromkeys(tool for tool in used_tools if tool in STRATEGY_REQUIRED_TOOLS))
    expected_prefix = STRATEGY_REQUIRED_TOOLS[: len(seen)]
    if seen[: len(expected_prefix)] != expected_prefix:
        return False, STRATEGY_REQUIRED_TOOLS
    missing = [tool for tool in STRATEGY_REQUIRED_TOOLS if tool not in seen]
    return not missing, missing


def _validate_strategy_plan_payload(plan: dict[str, Any]) -> str:
    items = list(plan.get("items") or [])
    minimum_items = 6 if str(plan.get("window") or "").strip() == "next_30_days" else 4
    if len(items) < minimum_items:
        return f"Jarvis needs at least {minimum_items} strategy item(s) for this window."
    for index, item in enumerate(items, start=1):
        topic = str(item.get("topic") or "").strip()
        hook_direction = str(item.get("hook_direction") or "").strip()
        rationale = str(item.get("rationale") or "").strip()
        source_links = [link for link in (item.get("source_links") or []) if isinstance(link, dict) and str(link.get("url") or "").strip()]
        if not topic:
            return f"Strategy item {index} is missing a topic."
        if not hook_direction:
            return f"Strategy item {index} is missing a hook direction."
        if not rationale:
            return f"Strategy item {index} is missing a rationale."
        if not source_links:
            return f"Strategy item {index} is missing cited source links."
    return ""


def _iter_plan_source_details(plan: dict[str, Any]) -> list[dict[str, str]]:
    seen_urls: set[str] = set()
    prepared: list[dict[str, str]] = []
    snapshot = plan.get("research_snapshot") if isinstance(plan.get("research_snapshot"), dict) else {}
    candidates = _collect_research_source_details(snapshot)
    for item in plan.get("items") or []:
        if not isinstance(item, dict):
            continue
        candidates.extend(link for link in (item.get("source_links") or []) if isinstance(link, dict))
    for item in candidates:
        url = str(item.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        prepared.append(
            {
                "title": str(item.get("title") or "Source").strip() or "Source",
                "url": url,
                "published_at": str(item.get("published_at") or "").strip(),
            }
        )
    return prepared


def format_strategy_plan_messages(plan: dict[str, Any]) -> list[str]:
    normalized = normalize_plan(plan)
    client_label = resolve_client_id(str(normalized.get("client_id") or "").strip()) or str(normalized.get("client_id") or "Client").strip()
    window_label = _format_window_label(str(normalized.get("window") or normalized.get("timeframe") or ""))
    objective = str(normalized.get("objective") or "").strip() or "Build an execution-ready plan."
    summary = str(normalized.get("summary") or "").strip()
    research_quality = _research_quality_report(normalized.get("research_snapshot") if isinstance(normalized.get("research_snapshot"), dict) else {})
    messages: list[str] = [
        "\n".join(
            [
                f"*Strategy for {client_label}* ✦",
                f"*Objective:* {objective}",
                f"*Window:* {window_label}",
                f"*Research freshness:* {research_quality.get('freshness') or 'Live research attached'}",
                f"*Why this plan matters:* {summary or 'Recent research and brand context were combined into an execution-ready plan.'}",
            ]
        ).strip()
    ]

    research_snapshot = normalized.get("research_snapshot") if isinstance(normalized.get("research_snapshot"), dict) else {}
    opportunity_lines = [f"*What the research says* ✦"]
    trend_angles = [str(item).strip() for item in (research_snapshot.get("trend_angles") or []) if str(item).strip()]
    source_signals = [str(item).strip() for item in (research_snapshot.get("source_signals") or []) if str(item).strip()]
    hook_patterns = [str(item).strip() for item in (research_snapshot.get("hook_patterns") or []) if str(item).strip()]
    top_opportunities = list(dict.fromkeys([*trend_angles[:2], *source_signals[:2], *hook_patterns[:2]]))
    for item in top_opportunities[:5]:
        opportunity_lines.append(f"• {item}")
    if len(opportunity_lines) == 1:
        opportunity_lines.append("• Live research found relevant recent signals, but the strongest opportunities are embedded in the plan items below.")
    messages.append("\n".join(opportunity_lines).strip())

    items = list(normalized.get("items") or [])
    for start in range(0, len(items), 2):
        chunk = items[start: start + 2]
        chunk_lines = [f"*Plan items {start + 1}-{start + len(chunk)} of {len(items)}* ✦"]
        for index, item in enumerate(chunk, start=start + 1):
            platforms = ", ".join(str(platform).strip().title() for platform in (item.get("platforms") or []) if str(platform).strip()) or "Instagram, Facebook"
            signals = [str(signal).strip() for signal in (item.get("source_signals") or []) if str(signal).strip()]
            signal_preview = "; ".join(signals[:2]) or "Recent live research"
            chunk_lines.extend(
                [
                    f"{index}. *{str(item.get('topic') or 'Untitled topic').strip()}*",
                    f"Format: {str(item.get('format') or 'content').strip()}",
                    f"Platforms: {platforms}",
                    f"Recommended time: {str(item.get('recommended_time') or 'Needs operator confirmation').strip()}",
                    f"Hook direction: {str(item.get('hook_direction') or '').strip()}",
                    f"Why it matters: {str(item.get('rationale') or '').strip()}",
                    f"Source signals: {signal_preview}",
                ]
            )
            if bool(item.get("needs_review")):
                chunk_lines.append("Confidence: needs review before execution")
            chunk_lines.append("")
        messages.append("\n".join(line for line in chunk_lines if line is not None).strip())

    source_lines = ["*Sources* ✦"]
    for index, item in enumerate(_iter_plan_source_details(normalized), start=1):
        published_at = str(item.get("published_at") or "").strip()
        date_suffix = f" ({published_at[:10]})" if published_at else ""
        source_lines.append(f"{index}. {str(item.get('title') or 'Source').strip()}{date_suffix}")
        source_lines.append(str(item.get("url") or "").strip())
    if len(source_lines) == 1:
        source_lines.append("No source links were saved with this plan.")
    messages.append("\n".join(source_lines).strip())
    return [message for message in messages if str(message).strip()]


def summarize_strategy_plan_reply(plan: dict[str, Any]) -> str:
    normalized = normalize_plan(plan)
    item_count = len(normalized.get("items") or [])
    research_quality = _research_quality_report(normalized.get("research_snapshot") if isinstance(normalized.get("research_snapshot"), dict) else {})
    client_label = resolve_client_id(str(normalized.get("client_id") or "").strip()) or "this client"
    window_label = _format_window_label(str(normalized.get("window") or normalized.get("timeframe") or ""))
    return (
        f"Strategy ready for {client_label}. "
        f"Window: {window_label}. "
        f"{item_count} plan item(s). "
        f"Research: {research_quality.get('freshness') or 'live research attached'}."
    )


def run_strategy_agent(
    client_id: str,
    window: str = "next_7_days",
    goal: str = "",
    campaign_context: str = "",
    requested_prompt: str = "",
) -> dict[str, Any]:
    try:
        resolved_client = resolve_client_id(client_id)
        if not resolved_client:
            return _strategy_error("Jarvis needs an explicit client before it can build a strategy plan.")
        if not get_client_store().get_client(resolved_client):
            return _strategy_error(f"Profile '{client_id}' not found.", client_id=resolved_client)

        window_name = derive_strategy_window(requested_prompt or goal, window)
        goal_text = str(goal or "").strip()
        campaign_text = str(campaign_context or "").strip()
        brand_context = get_client_store().get_brand_profile(resolved_client) or (get_client_store().get_client(resolved_client) or {}).get("profile_json") or {}
        brand_context = dict(brand_context or {})
        brand_profile = StrategyClientBriefTool().execute(resolved_client)
        publish_history = StrategyPublishHistoryTool().execute(resolved_client, limit=6)
        schedule_context = StrategyScheduleContextTool().execute(resolved_client)
        search_queries = _build_strategy_search_queries(resolved_client, brand_context, goal_text, window_name)
        web_research_packets = [StrategyWebSearchTool().execute(query, 5) for query in search_queries]
        research_snapshot = _build_research_snapshot_from_search(web_research_packets)
        research_quality = _research_quality_report(research_snapshot, recency_days=STRATEGY_RESEARCH_RECENCY_DAYS)
        if not research_quality["ok"]:
            return _strategy_error(
                "Strategy planning requires live web research first. "
                + " ".join(research_quality["errors"]),
                client_id=resolved_client,
                research_snapshot=research_snapshot,
            )
        research_health = get_trend_research_health()
        meta_insights = {}
        if bool(brand_profile.get("has_meta_credentials")):
            meta_result = StrategyMetaInsightsTool().execute(resolved_client, limit=4)
            meta_insights = meta_result if isinstance(meta_result, dict) else {}

        prompt_text = _build_strategy_prompt(
            client_id=resolved_client,
            window_name=window_name,
            goal_text=goal_text,
            campaign_text=campaign_text,
            research_health=research_health,
            brand_profile=brand_profile,
            publish_history=publish_history,
            schedule_context=schedule_context,
            web_research=research_snapshot,
            meta_insights=meta_insights,
        )

        agent = StrategyAgent()
        used_tools = ["read_brand_profile", "read_recent_publish_history", "read_schedule_context", "web_search"]
        if meta_insights:
            used_tools.append("read_meta_insights")

        attempts = [
            prompt_text,
            (
                prompt_text
                + "\n\nReturn only valid compact JSON. "
                "No markdown fences. Exactly 6 items for next_30_days or 4 items for next_7_days. "
                "Each item: short topic, short hook_direction, short rationale, max 1 source_link."
            ),
        ]
        for attempt_prompt in attempts:
            response = agent.chat(attempt_prompt)
            if not response.choices:
                continue
            payload = _extract_first_json_object(str(response.choices[0].message.content or ""))
            if not payload:
                continue
            plan = _coerce_plan_payload(
                payload,
                client_id=resolved_client,
                window=window_name,
                goal=goal_text,
                campaign_context=campaign_text,
                requested_prompt=requested_prompt or goal_text,
                used_tools=list(dict.fromkeys(used_tools)),
                research_snapshot=research_snapshot,
            )
            validation_error = _validate_strategy_plan_payload(plan)
            if not validation_error:
                existing_plan = _match_existing_strategy_plan(
                    resolved_client,
                    window=window_name,
                    goal=goal_text,
                    requested_prompt=requested_prompt or goal_text,
                )
                if existing_plan:
                    plan["plan_id"] = str(existing_plan.get("plan_id") or "").strip() or plan["plan_id"]
                    plan["created_at"] = str(existing_plan.get("created_at") or "").strip() or str(plan.get("created_at") or "")
                plan["requested_prompt"] = str(requested_prompt or goal_text or "").strip()
                return save_strategy_plan(plan)

        return _strategy_error(
            "Strategy Agent could not produce a valid research-backed plan after multiple attempts.",
            client_id=resolved_client,
            research_snapshot=research_snapshot,
        )
    except Exception as exc:
        logger.error("run_strategy_agent failed: %s", exc, exc_info=True)
        return _strategy_error(f"Strategy agent failed: {type(exc).__name__}: {exc}", client_id=resolve_client_id(client_id))



def materialize_strategy_plan(plan_id: str, item_ids: list[str] | None = None) -> dict[str, Any]:
    stored = get_strategy_plan(plan_id)
    if not stored:
        return {"error": "Strategy plan not found."}
    target_ids = {str(item_id).strip() for item_id in (item_ids or []) if str(item_id).strip()}
    plan = normalize_plan(stored)
    now_iso = _utc_now_iso()
    changed = False
    for item in plan["items"]:
        item_id = str(item.get("item_id") or "").strip()
        if target_ids and item_id not in target_ids:
            continue
        if str(item.get("status") or "").strip().lower() in {"suggested", "scheduled", "published"}:
            continue
        item["status"] = "suggested"
        item["materialized_at"] = now_iso
        changed = True
    if changed:
        plan["status"] = "materialized"
        plan["materialized_at"] = now_iso
        plan["updated_at"] = now_iso
        return save_strategy_plan(plan)
    return plan
