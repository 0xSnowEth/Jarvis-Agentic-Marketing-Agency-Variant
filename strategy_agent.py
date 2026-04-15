import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import requests

from agent import Agent
from client_store import get_client_store
from publish_run_store import list_publish_runs
from schedule_store import load_schedule, split_schedule_views
from strategy_plan_store import get_strategy_plan, normalize_plan, save_strategy_plan
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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def build_strategy_request_from_prompt(prompt: str) -> dict[str, str]:
    raw = str(prompt or "").strip()
    return {
        "client_id": extract_strategy_client_id(raw),
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
        return {
            "client_id": resolved,
            "profile_json": payload.get("profile_json") or {},
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
                    "topic": topic,
                    "created_at": str(run.get("created_at") or "").strip(),
                    "platform_results": run.get("platform_results") if isinstance(run.get("platform_results"), dict) else {},
                }
            )
        return {"client_id": resolved, "summary": summary, "runs": prepared}


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
        return {"client_id": resolved, "active": active_rows, "history": history_rows}


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
        return {
            "query": query,
            "provider": pack.get("provider"),
            "status": "success" if pack.get("results") else "insufficient_recent_sources",
            "recency_days": 30,
            "results": pack.get("results", []),
            "total": len(pack.get("results") or []),
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
        access_token = str(cdata.get("meta_access_token") or os.getenv("META_ACCESS_TOKEN") or "").strip()
        ig_user_id = str(cdata.get("instagram_account_id") or os.getenv("META_IG_USER_ID") or "").strip()
        fb_page_id = str(cdata.get("facebook_page_id") or os.getenv("META_PAGE_ID") or "").strip()
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
        strategy_model = os.getenv("STRATEGY_AGENT_MODEL", "").strip()
        if not strategy_model:
            strategy_model = "openai/gpt-4o-mini" if os.getenv("OPENROUTER_API_KEY") else "gpt-4o-mini"
        super().__init__(
            [
                StrategyClientBriefTool(),
                StrategyPublishHistoryTool(),
                StrategyScheduleContextTool(),
                StrategyMetaInsightsTool(),
                StrategyWebSearchTool(),
            ],
            model=strategy_model,
        )
        self.system_message = (
            "You are Jarvis Strategy Agent, a specialist planner for marketing agencies. "
            "You do not publish, you do not schedule, and you do not invent fake certainty. "
            "Use the available tools to understand the brand profile, current calendar load, recent publish outcomes, "
            "and external trend context when needed. "
            "You will also receive a recent research snapshot derived from the last 30 days. "
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
            "Prefer 4-6 items for next_7_days and 6-10 items for next_30_days. "
            "If context is thin, still produce a usable plan but mark assumptions with needs_review=true."
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
    normalized = normalize_plan(
        {
            "client_id": client_id,
            "window": derive_strategy_window(requested_prompt, window),
            "goal": goal,
            "campaign_context": campaign_context,
            "summary": str(payload.get("summary") or "").strip(),
            "objective": str(payload.get("objective") or goal or "Build a practical cross-platform content plan.").strip(),
            "timeframe": str(payload.get("timeframe") or derive_strategy_window(requested_prompt, window)).strip(),
            "items": payload.get("items") if isinstance(payload.get("items"), list) else [],
            "sources_used": payload.get("sources_used") if isinstance(payload.get("sources_used"), list) else used_tools,
            "research_snapshot": research_payload or payload_research,
            "status": "ready",
        }
    )
    if not normalized["summary"]:
        normalized["summary"] = f"Strategy plan prepared for {client_id} across {normalized['timeframe']}."
    if not normalized["items"]:
        normalized["items"] = [
            {
                "item_id": "item-1",
                "topic": goal or "Brand introduction and offer positioning",
                "format": "carousel",
                "platforms": ["facebook", "instagram"],
                "recommended_time": "Needs operator confirmation",
                "hook_direction": "Introduce the offer with a clear local relevance angle.",
                "rationale": "Generated fallback item because the model returned an incomplete plan.",
                "source_signals": used_tools or ["brand_profile"],
                "source_links": [],
                "needs_review": True,
                "confidence": 0.3,
                "status": "planned",
                "materialized_at": "",
            }
        ]
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
    return normalized


def summarize_strategy_plan_reply(plan: dict[str, Any]) -> str:
    items = list(plan.get("items") or [])
    summary = str(plan.get("summary") or "").strip()
    window = str(plan.get("timeframe") or plan.get("window") or "").replace("_", " ").strip()
    lead = summary or f"Strategy plan ready for {plan.get('client_id') or 'this client'}."
    lines = [lead]
    if window:
        lines.append(f"Window: {window}.")
    if items:
        preview = []
        for index, item in enumerate(items[:4], start=1):
            topic = str(item.get("topic") or "Untitled topic").strip()
            format_name = str(item.get("format") or "content").strip()
            recommended_time = str(item.get("recommended_time") or "").strip()
            suffix = f" at {recommended_time}" if recommended_time else ""
            preview.append(f"{index}. {topic} ({format_name}{suffix})")
        lines.append("Top directions:")
        lines.extend(preview)
    return "\n".join(lines).strip()


def run_strategy_agent(
    client_id: str,
    window: str = "next_7_days",
    goal: str = "",
    campaign_context: str = "",
    requested_prompt: str = "",
) -> dict[str, Any]:
    resolved_client = resolve_client_id(client_id)
    if not resolved_client:
        return {"error": "Jarvis needs an explicit client before it can build a strategy plan."}
    if not get_client_store().get_client(resolved_client):
        return {"error": f"Profile '{client_id}' not found."}

    window_name = derive_strategy_window(requested_prompt or goal, window)
    goal_text = str(goal or "").strip()
    campaign_text = str(campaign_context or "").strip()
    brand_context = get_client_store().get_brand_profile(resolved_client) or (get_client_store().get_client(resolved_client) or {}).get("profile_json") or {}
    brand_context = dict(brand_context or {})
    research_snapshot = get_client_trend_dossier(
        resolved_client,
        brand_context,
        goal=goal_text,
        campaign_context=campaign_text,
        window=window_name,
        recency_days=30,
        force_refresh=True,
    )
    research_health = get_trend_research_health()

    prompt_text = (
        f"Build a strategy plan for client '{resolved_client}'. "
        f"Window: {window_name}. "
        f"Goal: {goal_text or 'No explicit goal provided.'} "
        f"Campaign context: {campaign_text or 'No extra campaign context provided.'}\n\n"
        f"Research health snapshot:\n{json.dumps(research_health, ensure_ascii=False)}\n\n"
        f"Recent research snapshot (last 30 days):\n{json.dumps(research_snapshot, ensure_ascii=False)}\n\n"
        f"Instructions:\n"
        f"- Cite recent source signals and source links in each item when available.\n"
        f"- If the research snapshot is weak or sparse, mark needs_review=true instead of forcing certainty.\n"
        f"- Keep the plan concrete, specific, and execution-ready."
    )

    agent = StrategyAgent()
    max_turns = 6
    used_tools: list[str] = []
    for _turn in range(max_turns):
        response = agent.chat(prompt_text)
        if not response.choices:
            return {"error": "Strategy Agent did not return a response."}
        message = response.choices[0].message
        if message.tool_calls:
            agent.messages.append(message)
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                used_tools.append(tool_name)
                try:
                    tool_input = json.loads(tool_call.function.arguments or "{}")
                except Exception:
                    tool_input = {}
                tool = agent.tool_map.get(tool_name)
                try:
                    tool_result = tool.execute(**tool_input) if tool else {"error": f"Tool {tool_name} not mounted."}
                except Exception as exc:
                    logger.error("Strategy tool %s failed: %s", tool_name, exc, exc_info=True)
                    tool_result = {"error": f"{tool_name} failed: {type(exc).__name__}: {str(exc)}"}
                agent.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )
            prompt_text = ""
            continue
        payload = _extract_first_json_object(str(message.content or ""))
        if payload:
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
            return save_strategy_plan(plan)
        prompt_text = "Return only valid JSON matching the required schema. Do not include prose or markdown fences."

    return {"error": "Strategy Agent reached its safety limit without producing a valid plan."}


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
