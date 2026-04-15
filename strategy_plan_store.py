import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from client_store import get_data_backend_name, get_supabase_service_client
from file_lock import file_lock

STRATEGY_PLANS_PATH = "strategy_plans.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_item(item: dict[str, Any], position: int) -> dict[str, Any]:
    normalized = dict(item) if isinstance(item, dict) else {}
    normalized["item_id"] = str(normalized.get("item_id") or f"item-{position + 1}").strip()
    normalized["topic"] = str(normalized.get("topic") or "").strip()
    normalized["format"] = str(normalized.get("format") or "").strip()
    platforms = normalized.get("platforms")
    if isinstance(platforms, list):
        normalized["platforms"] = [str(platform).strip() for platform in platforms if str(platform).strip()]
    elif isinstance(platforms, str) and platforms.strip():
        normalized["platforms"] = [part.strip() for part in platforms.split(",") if part.strip()]
    else:
        normalized["platforms"] = []
    normalized["recommended_time"] = str(normalized.get("recommended_time") or "").strip()
    normalized["hook_direction"] = str(normalized.get("hook_direction") or "").strip()
    normalized["rationale"] = str(normalized.get("rationale") or "").strip()
    source_signals = normalized.get("source_signals")
    if isinstance(source_signals, list):
        normalized["source_signals"] = [str(signal).strip() for signal in source_signals if str(signal).strip()]
    elif isinstance(source_signals, str) and source_signals.strip():
        normalized["source_signals"] = [source_signals.strip()]
    else:
        normalized["source_signals"] = []
    raw_source_links = normalized.get("source_links")
    normalized_source_links: list[dict[str, str]] = []
    if isinstance(raw_source_links, list):
        for raw_link in raw_source_links:
            if isinstance(raw_link, dict):
                url = str(raw_link.get("url") or "").strip()
                if not url:
                    continue
                normalized_source_links.append(
                    {
                        "title": str(raw_link.get("title") or "").strip(),
                        "url": url,
                        "published_at": str(raw_link.get("published_at") or "").strip(),
                    }
                )
            elif isinstance(raw_link, str) and raw_link.strip():
                normalized_source_links.append({"title": "", "url": raw_link.strip(), "published_at": ""})
    elif isinstance(raw_source_links, str) and raw_source_links.strip():
        normalized_source_links = [{"title": "", "url": raw_source_links.strip(), "published_at": ""}]
    normalized["source_links"] = normalized_source_links[:3]
    normalized["needs_review"] = bool(normalized.get("needs_review"))
    confidence = normalized.get("confidence")
    try:
        normalized["confidence"] = max(0.0, min(float(confidence), 1.0))
    except (TypeError, ValueError):
        normalized["confidence"] = 0.5
    normalized["status"] = str(normalized.get("status") or "planned").strip().lower()
    normalized["materialized_at"] = str(normalized.get("materialized_at") or "").strip()
    return normalized


def normalize_plan(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload) if isinstance(payload, dict) else {}
    normalized["plan_id"] = str(normalized.get("plan_id") or uuid.uuid4().hex[:12]).strip()
    normalized["client_id"] = str(normalized.get("client_id") or "").strip()
    normalized["window"] = str(normalized.get("window") or "next_7_days").strip()
    normalized["goal"] = str(normalized.get("goal") or "").strip()
    normalized["campaign_context"] = str(normalized.get("campaign_context") or "").strip()
    normalized["status"] = str(normalized.get("status") or "ready").strip().lower()
    normalized["summary"] = str(normalized.get("summary") or "").strip()
    normalized["objective"] = str(normalized.get("objective") or "").strip()
    normalized["timeframe"] = str(normalized.get("timeframe") or normalized["window"]).strip()
    raw_items = normalized.get("items") if isinstance(normalized.get("items"), list) else []
    normalized["items"] = [_normalize_item(item, idx) for idx, item in enumerate(raw_items)]
    normalized["sources_used"] = [
        str(source).strip()
        for source in (normalized.get("sources_used") or [])
        if str(source).strip()
    ] if isinstance(normalized.get("sources_used"), list) else []
    normalized["research_snapshot"] = normalized.get("research_snapshot") if isinstance(normalized.get("research_snapshot"), dict) else {}
    normalized["created_at"] = str(normalized.get("created_at") or _utc_now_iso()).strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or normalized["created_at"]).strip()
    normalized["materialized_at"] = str(normalized.get("materialized_at") or "").strip()
    return normalized


class BaseStrategyPlanStore:
    backend_name = "base"

    def list_plans(self, client_id: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_plan(self, plan_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def save_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def delete_plan(self, plan_id: str) -> bool:
        raise NotImplementedError

    def delete_client_plans(self, client_id: str) -> int:
        raise NotImplementedError


class JsonStrategyPlanStore(BaseStrategyPlanStore):
    backend_name = "json"

    def _list_plans_unsafe(self) -> list[dict[str, Any]]:
        if not os.path.exists(STRATEGY_PLANS_PATH):
            return []
        try:
            with open(STRATEGY_PLANS_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return []
        return [normalize_plan(item) for item in payload if isinstance(item, dict)]

    def list_plans(self, client_id: str | None = None) -> list[dict[str, Any]]:
        with file_lock(STRATEGY_PLANS_PATH, shared=True):
            plans = self._list_plans_unsafe()
        if client_id:
            client_key = str(client_id).strip().lower()
            plans = [plan for plan in plans if str(plan.get("client_id") or "").strip().lower() == client_key]
        return sorted(plans, key=lambda item: str(item.get("updated_at") or ""), reverse=True)

    def get_plan(self, plan_id: str) -> dict[str, Any] | None:
        target = str(plan_id or "").strip()
        if not target:
            return None
        with file_lock(STRATEGY_PLANS_PATH, shared=True):
            for plan in self._list_plans_unsafe():
                if str(plan.get("plan_id") or "").strip() == target:
                    return plan
        return None

    def save_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_plan(payload)
        normalized["updated_at"] = _utc_now_iso()
        with file_lock(STRATEGY_PLANS_PATH):
            plans = self._list_plans_unsafe()
            replaced = False
            for index, plan in enumerate(plans):
                if str(plan.get("plan_id") or "").strip() == normalized["plan_id"]:
                    plans[index] = normalized
                    replaced = True
                    break
            if not replaced:
                plans.append(normalized)
            with open(STRATEGY_PLANS_PATH, "w", encoding="utf-8") as f:
                json.dump(plans, f, indent=4, ensure_ascii=False)
        return normalized

    def delete_plan(self, plan_id: str) -> bool:
        target = str(plan_id or "").strip()
        if not target:
            return False
        with file_lock(STRATEGY_PLANS_PATH):
            plans = self._list_plans_unsafe()
            kept = [plan for plan in plans if str(plan.get("plan_id") or "").strip() != target]
            removed = len(plans) != len(kept)
            if removed:
                with open(STRATEGY_PLANS_PATH, "w", encoding="utf-8") as f:
                    json.dump(kept, f, indent=4, ensure_ascii=False)
            return removed

    def delete_client_plans(self, client_id: str) -> int:
        target = str(client_id or "").strip()
        if not target:
            return 0
        with file_lock(STRATEGY_PLANS_PATH):
            plans = self._list_plans_unsafe()
            kept = [plan for plan in plans if str(plan.get("client_id") or "").strip() != target]
            removed = len(plans) - len(kept)
            if removed:
                with open(STRATEGY_PLANS_PATH, "w", encoding="utf-8") as f:
                    json.dump(kept, f, indent=4, ensure_ascii=False)
            return removed


class SupabaseStrategyPlanStore(BaseStrategyPlanStore):
    backend_name = "supabase"

    def __init__(self):
        self.client = get_supabase_service_client()

    def _row_to_plan(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row.get("payload_json") or {})
        payload.update(
            {
                "plan_id": str(row.get("plan_id") or "").strip(),
                "client_id": str(row.get("client_id") or "").strip(),
                "window": str(row.get("window_name") or payload.get("window") or "next_7_days").strip(),
                "status": str(row.get("status") or payload.get("status") or "ready").strip().lower(),
                "summary": str(row.get("summary") or payload.get("summary") or "").strip(),
                "materialized_at": str(row.get("materialized_at") or payload.get("materialized_at") or "").strip(),
                "created_at": str(row.get("created_at") or payload.get("created_at") or "").strip(),
                "updated_at": str(row.get("updated_at") or payload.get("updated_at") or "").strip(),
            }
        )
        return normalize_plan(payload)

    def list_plans(self, client_id: str | None = None) -> list[dict[str, Any]]:
        query = self.client.table("strategy_plans").select("*").order("updated_at", desc=True)
        if client_id:
            query = query.eq("client_id", client_id)
        response = query.execute()
        return [self._row_to_plan(row) for row in (response.data or [])]

    def get_plan(self, plan_id: str) -> dict[str, Any] | None:
        response = self.client.table("strategy_plans").select("*").eq("plan_id", plan_id).limit(1).execute()
        rows = response.data or []
        return self._row_to_plan(rows[0]) if rows else None

    def save_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_plan(payload)
        normalized["updated_at"] = _utc_now_iso()
        normalized["created_at"] = str(normalized.get("created_at") or normalized["updated_at"]).strip()
        row = {
            "plan_id": normalized["plan_id"],
            "client_id": normalized["client_id"],
            "window_name": normalized["window"],
            "status": normalized["status"],
            "summary": normalized["summary"] or None,
            "materialized_at": normalized["materialized_at"] or None,
            "created_at": normalized["created_at"],
            "updated_at": normalized["updated_at"],
            "payload_json": normalized,
        }
        self.client.table("strategy_plans").upsert(row, on_conflict="plan_id").execute()
        return normalized

    def delete_plan(self, plan_id: str) -> bool:
        response = self.client.table("strategy_plans").select("plan_id").eq("plan_id", plan_id).limit(1).execute()
        rows = response.data or []
        if not rows:
            return False
        self.client.table("strategy_plans").delete().eq("plan_id", plan_id).execute()
        return True

    def delete_client_plans(self, client_id: str) -> int:
        response = self.client.table("strategy_plans").select("plan_id").eq("client_id", client_id).execute()
        removed = len(response.data or [])
        if removed:
            self.client.table("strategy_plans").delete().eq("client_id", client_id).execute()
        return removed


_store: BaseStrategyPlanStore | None = None


def get_strategy_plan_store() -> BaseStrategyPlanStore:
    global _store
    if _store is not None:
        return _store
    if get_data_backend_name() == "supabase":
        _store = SupabaseStrategyPlanStore()
    else:
        _store = JsonStrategyPlanStore()
    return _store


def list_strategy_plans(client_id: str | None = None) -> list[dict[str, Any]]:
    return get_strategy_plan_store().list_plans(client_id=client_id)


def get_strategy_plan(plan_id: str) -> dict[str, Any] | None:
    return get_strategy_plan_store().get_plan(plan_id)


def save_strategy_plan(payload: dict[str, Any]) -> dict[str, Any]:
    return get_strategy_plan_store().save_plan(payload)


def delete_strategy_plan(plan_id: str) -> bool:
    return get_strategy_plan_store().delete_plan(plan_id)


def delete_client_strategy_plans(client_id: str) -> int:
    return get_strategy_plan_store().delete_client_plans(client_id)
