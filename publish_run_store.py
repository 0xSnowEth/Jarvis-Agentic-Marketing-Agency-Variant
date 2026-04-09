import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from client_store import get_data_backend_name, get_supabase_service_client
from file_lock import file_lock

PUBLISH_RUNS_PATH = "publish_runs.json"


class BasePublishRunStore:
    backend_name = "base"

    def list_runs(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def save_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def delete_client_runs(self, client_id: str) -> int:
        raise NotImplementedError


class JsonPublishRunStore(BasePublishRunStore):
    backend_name = "json"

    def _list_runs_unsafe(self) -> list[dict[str, Any]]:
        if not os.path.exists(PUBLISH_RUNS_PATH):
            return []
        try:
            with open(PUBLISH_RUNS_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return []
        return [dict(item) for item in payload if isinstance(item, dict)]

    def list_runs(self) -> list[dict[str, Any]]:
        with file_lock(PUBLISH_RUNS_PATH, shared=True):
            return self._list_runs_unsafe()

    def save_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized.setdefault("run_id", uuid.uuid4().hex)
        normalized.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        with file_lock(PUBLISH_RUNS_PATH):
            runs = self._list_runs_unsafe()
            runs.append(normalized)
            with open(PUBLISH_RUNS_PATH, "w", encoding="utf-8") as f:
                json.dump(runs, f, indent=4, ensure_ascii=False)
        return normalized

    def delete_client_runs(self, client_id: str) -> int:
        with file_lock(PUBLISH_RUNS_PATH):
            runs = self._list_runs_unsafe()
            kept = [run for run in runs if str(run.get("client_id") or "").strip() != client_id]
            removed = len(runs) - len(kept)
            if removed:
                with open(PUBLISH_RUNS_PATH, "w", encoding="utf-8") as f:
                    json.dump(kept, f, indent=4, ensure_ascii=False)
            return removed


class SupabasePublishRunStore(BasePublishRunStore):
    backend_name = "supabase"

    def __init__(self):
        self.client = get_supabase_service_client()

    def list_runs(self) -> list[dict[str, Any]]:
        response = self.client.table("publish_runs").select("*").order("created_at", desc=True).execute()
        return response.data or []

    def save_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = {
            "run_id": str(payload.get("run_id") or uuid.uuid4()),
            "client_id": str(payload.get("client_id") or "").strip(),
            "job_id": str(payload.get("job_id") or "").strip() or None,
            "draft_id": str(payload.get("draft_id") or "").strip() or None,
            "topic": str(payload.get("topic") or "").strip() or None,
            "status": str(payload.get("status") or "unknown").strip().lower(),
            "failure_step": str(payload.get("failure_step") or "").strip() or None,
            "platform_results": payload.get("platform_results") if isinstance(payload.get("platform_results"), dict) else {},
            "raw_output": str(payload.get("raw_output") or "").strip() or None,
        }
        self.client.table("publish_runs").insert(normalized).execute()
        return normalized

    def delete_client_runs(self, client_id: str) -> int:
        response = self.client.table("publish_runs").select("run_id").eq("client_id", client_id).execute()
        removed = len(response.data or [])
        if removed:
            self.client.table("publish_runs").delete().eq("client_id", client_id).execute()
        return removed


_store: BasePublishRunStore | None = None


def get_publish_run_store() -> BasePublishRunStore:
    global _store
    if _store is not None:
        return _store
    mode = get_data_backend_name()
    if mode == "supabase":
        _store = SupabasePublishRunStore()
    else:
        _store = JsonPublishRunStore()
    return _store


def record_publish_run(payload: dict[str, Any]) -> dict[str, Any]:
    return get_publish_run_store().save_run(payload)


def list_publish_runs() -> list[dict[str, Any]]:
    return get_publish_run_store().list_runs()


def delete_client_publish_runs(client_id: str) -> int:
    return get_publish_run_store().delete_client_runs(client_id)
