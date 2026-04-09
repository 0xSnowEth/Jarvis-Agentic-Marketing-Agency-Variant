import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from client_store import get_data_backend_name, get_supabase_service_client
from file_lock import file_lock

logger = logging.getLogger("JarvisRuntimeState")


def _runtime_state_path(filename: str) -> str:
    base_dir = str(os.getenv("JARVIS_RUNTIME_STATE_DIR") or "").strip()
    if base_dir:
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, filename)
    return filename


AUTH_SESSIONS_PATH = _runtime_state_path("auth_sessions.json")
ORCHESTRATOR_RUNS_PATH = _runtime_state_path("orchestrator_runs.json")
RESCHEDULE_SESSIONS_PATH = _runtime_state_path("reschedule_sessions.json")
AUDIT_EVENTS_PATH = _runtime_state_path("operator_audit_events.jsonl")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _execute_supabase_with_retry(builder, label: str, attempts: int = 3, base_delay: float = 0.25):
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = builder() if callable(builder) else builder
            return request.execute()
        except (httpx.RemoteProtocolError, httpx.TransportError) as exc:
            last_exc = exc
            if attempt >= attempts:
                raise
            time.sleep(base_delay * attempt)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"Supabase request failed during {label}.")


class BaseRuntimeStateStore:
    backend_name = "base"

    def get_auth_session(self, token: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def save_auth_session(self, token: str, expires_at: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def delete_auth_session(self, token: str) -> bool:
        raise NotImplementedError

    def delete_expired_auth_sessions(self, now_iso: str | None = None) -> int:
        raise NotImplementedError

    def touch_auth_session(self, token: str, seen_at: str | None = None) -> dict[str, Any] | None:
        raise NotImplementedError

    def get_orchestrator_run(self, run_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def save_orchestrator_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def list_orchestrator_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError

    def replace_reschedule_sessions(self, sessions: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def load_reschedule_sessions(self) -> dict[str, Any]:
        raise NotImplementedError

    def record_audit_event(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        actor: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError


class JsonRuntimeStateStore(BaseRuntimeStateStore):
    backend_name = "json"

    def _load_json_unsafe(self, path: str, fallback: Any):
        if not os.path.exists(path):
            return fallback
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return fallback

    def _save_json_unsafe(self, path: str, payload: Any) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=4, ensure_ascii=False)

    def get_auth_session(self, token: str) -> dict[str, Any] | None:
        key = str(token or "").strip()
        if not key:
            return None
        with file_lock(AUTH_SESSIONS_PATH, shared=True):
            sessions = self._load_json_unsafe(AUTH_SESSIONS_PATH, {})
            record = sessions.get(key)
            return dict(record) if isinstance(record, dict) else None

    def save_auth_session(self, token: str, expires_at: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        key = str(token or "").strip()
        record = {
            "session_token": key,
            "expires_at": str(expires_at or "").strip(),
            "payload_json": dict(payload or {}),
            "created_at": _utc_now_iso(),
            "last_seen_at": None,
        }
        with file_lock(AUTH_SESSIONS_PATH):
            sessions = self._load_json_unsafe(AUTH_SESSIONS_PATH, {})
            existing = sessions.get(key) or {}
            if existing.get("created_at"):
                record["created_at"] = existing["created_at"]
            if existing.get("last_seen_at"):
                record["last_seen_at"] = existing["last_seen_at"]
            sessions[key] = record
            self._save_json_unsafe(AUTH_SESSIONS_PATH, sessions)
        return dict(record)

    def delete_auth_session(self, token: str) -> bool:
        key = str(token or "").strip()
        if not key:
            return False
        with file_lock(AUTH_SESSIONS_PATH):
            sessions = self._load_json_unsafe(AUTH_SESSIONS_PATH, {})
            if key not in sessions:
                return False
            sessions.pop(key, None)
            self._save_json_unsafe(AUTH_SESSIONS_PATH, sessions)
        return True

    def delete_expired_auth_sessions(self, now_iso: str | None = None) -> int:
        current = datetime.fromisoformat((now_iso or _utc_now_iso()).replace("Z", "+00:00"))
        removed = 0
        with file_lock(AUTH_SESSIONS_PATH):
            sessions = self._load_json_unsafe(AUTH_SESSIONS_PATH, {})
            kept = {}
            for token, record in sessions.items():
                expires_at = str((record or {}).get("expires_at") or "").strip()
                try:
                    expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                except Exception:
                    removed += 1
                    continue
                if expiry <= current:
                    removed += 1
                    continue
                kept[token] = record
            if removed:
                self._save_json_unsafe(AUTH_SESSIONS_PATH, kept)
        return removed

    def touch_auth_session(self, token: str, seen_at: str | None = None) -> dict[str, Any] | None:
        key = str(token or "").strip()
        if not key:
            return None
        touched = None
        with file_lock(AUTH_SESSIONS_PATH):
            sessions = self._load_json_unsafe(AUTH_SESSIONS_PATH, {})
            record = sessions.get(key)
            if not isinstance(record, dict):
                return None
            record["last_seen_at"] = str(seen_at or _utc_now_iso())
            sessions[key] = record
            self._save_json_unsafe(AUTH_SESSIONS_PATH, sessions)
            touched = dict(record)
        return touched

    def get_orchestrator_run(self, run_id: str) -> dict[str, Any] | None:
        key = str(run_id or "").strip()
        if not key:
            return None
        with file_lock(ORCHESTRATOR_RUNS_PATH, shared=True):
            runs = self._load_json_unsafe(ORCHESTRATOR_RUNS_PATH, {})
            payload = runs.get(key)
            return dict(payload) if isinstance(payload, dict) else None

    def save_orchestrator_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload or {})
        run_id = str(normalized.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run_id is required to save orchestrator run state.")
        normalized["run_id"] = run_id
        normalized.setdefault("created_at", _utc_now_iso())
        normalized["updated_at"] = _utc_now_iso()
        with file_lock(ORCHESTRATOR_RUNS_PATH):
            runs = self._load_json_unsafe(ORCHESTRATOR_RUNS_PATH, {})
            existing = runs.get(run_id) or {}
            if existing.get("created_at"):
                normalized["created_at"] = existing["created_at"]
            runs[run_id] = normalized
            self._save_json_unsafe(ORCHESTRATOR_RUNS_PATH, runs)
        return dict(normalized)

    def list_orchestrator_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with file_lock(ORCHESTRATOR_RUNS_PATH, shared=True):
            runs = self._load_json_unsafe(ORCHESTRATOR_RUNS_PATH, {})
            payloads = [dict(item) for item in runs.values() if isinstance(item, dict)]
        payloads.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
        return payloads[: max(1, int(limit or 100))]

    def replace_reschedule_sessions(self, sessions: dict[str, Any]) -> dict[str, Any]:
        normalized = {str(phone).strip(): dict(data or {}) for phone, data in (sessions or {}).items() if str(phone).strip()}
        with file_lock(RESCHEDULE_SESSIONS_PATH):
            self._save_json_unsafe(RESCHEDULE_SESSIONS_PATH, normalized)
        return normalized

    def load_reschedule_sessions(self) -> dict[str, Any]:
        with file_lock(RESCHEDULE_SESSIONS_PATH, shared=True):
            payload = self._load_json_unsafe(RESCHEDULE_SESSIONS_PATH, {})
            return dict(payload) if isinstance(payload, dict) else {}

    def record_audit_event(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        actor: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "event_id": uuid.uuid4().hex,
            "event_type": str(event_type or "").strip(),
            "actor": str(actor or "").strip() or None,
            "request_id": str(request_id or "").strip() or None,
            "payload_json": dict(payload or {}),
            "created_at": _utc_now_iso(),
        }
        os.makedirs(os.path.dirname(AUDIT_EVENTS_PATH) or ".", exist_ok=True)
        with file_lock(AUDIT_EVENTS_PATH):
            with open(AUDIT_EVENTS_PATH, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event


class SupabaseRuntimeStateStore(BaseRuntimeStateStore):
    backend_name = "supabase"

    def __init__(self):
        self.client = get_supabase_service_client()

    def get_auth_session(self, token: str) -> dict[str, Any] | None:
        response = _execute_supabase_with_retry(
            self.client.table("auth_sessions").select("*").eq("session_token", str(token or "").strip()).limit(1),
            "get_auth_session",
        )
        rows = response.data or []
        if not rows:
            return None
        row = rows[0]
        return {
            "session_token": row.get("session_token"),
            "expires_at": row.get("expires_at"),
            "payload_json": row.get("payload_json") or {},
            "created_at": row.get("created_at"),
            "last_seen_at": row.get("last_seen_at"),
        }

    def save_auth_session(self, token: str, expires_at: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        normalized = {
            "session_token": str(token or "").strip(),
            "expires_at": str(expires_at or "").strip(),
            "payload_json": dict(payload or {}),
        }
        _execute_supabase_with_retry(
            self.client.table("auth_sessions").upsert(normalized, on_conflict="session_token"),
            "save_auth_session",
        )
        return self.get_auth_session(normalized["session_token"]) or normalized

    def delete_auth_session(self, token: str) -> bool:
        key = str(token or "").strip()
        existing = self.get_auth_session(key)
        if not existing:
            return False
        _execute_supabase_with_retry(
            self.client.table("auth_sessions").delete().eq("session_token", key),
            "delete_auth_session",
        )
        return True

    def delete_expired_auth_sessions(self, now_iso: str | None = None) -> int:
        current = str(now_iso or _utc_now_iso())
        existing = _execute_supabase_with_retry(
            self.client.table("auth_sessions").select("session_token").lte("expires_at", current),
            "list_expired_auth_sessions",
        )
        removed = len(existing.data or [])
        if removed:
            _execute_supabase_with_retry(
                self.client.table("auth_sessions").delete().lte("expires_at", current),
                "delete_expired_auth_sessions",
            )
        return removed

    def touch_auth_session(self, token: str, seen_at: str | None = None) -> dict[str, Any] | None:
        key = str(token or "").strip()
        existing = self.get_auth_session(key)
        if not existing:
            return None
        _execute_supabase_with_retry(
            self.client.table("auth_sessions").update({"last_seen_at": str(seen_at or _utc_now_iso())}).eq("session_token", key),
            "touch_auth_session",
        )
        return self.get_auth_session(key)

    def get_orchestrator_run(self, run_id: str) -> dict[str, Any] | None:
        response = _execute_supabase_with_retry(
            self.client.table("orchestrator_runs").select("*").eq("run_id", str(run_id or "").strip()).limit(1),
            "get_orchestrator_run",
        )
        rows = response.data or []
        if not rows:
            return None
        row = rows[0]
        payload = dict(row.get("payload_json") or {})
        payload.setdefault("run_id", row.get("run_id"))
        payload.setdefault("status", row.get("status"))
        payload.setdefault("created_at", row.get("created_at"))
        payload["updated_at"] = row.get("updated_at")
        if row.get("completed_at"):
            payload["completed_at"] = row.get("completed_at")
        return payload

    def save_orchestrator_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload or {})
        run_id = str(normalized.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run_id is required to save orchestrator run state.")
        normalized["run_id"] = run_id
        row = {
            "run_id": run_id,
            "status": str(normalized.get("status") or "queued").strip().lower(),
            "payload_json": normalized,
            "completed_at": normalized.get("completed_at") or None,
        }
        _execute_supabase_with_retry(
            self.client.table("orchestrator_runs").upsert(row, on_conflict="run_id"),
            "save_orchestrator_run",
        )
        return self.get_orchestrator_run(run_id) or normalized

    def list_orchestrator_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        response = _execute_supabase_with_retry(
            self.client.table("orchestrator_runs").select("*").order("updated_at", desc=True).limit(max(1, int(limit or 100))),
            "list_orchestrator_runs",
        )
        payloads = []
        for row in (response.data or []):
            payload = dict(row.get("payload_json") or {})
            payload.setdefault("run_id", row.get("run_id"))
            payload.setdefault("status", row.get("status"))
            payload.setdefault("created_at", row.get("created_at"))
            payload["updated_at"] = row.get("updated_at")
            if row.get("completed_at"):
                payload["completed_at"] = row.get("completed_at")
            payloads.append(payload)
        return payloads

    def replace_reschedule_sessions(self, sessions: dict[str, Any]) -> dict[str, Any]:
        normalized = {str(phone).strip(): dict(data or {}) for phone, data in (sessions or {}).items() if str(phone).strip()}
        response = _execute_supabase_with_retry(
            self.client.table("reschedule_sessions").select("phone"),
            "list_reschedule_sessions",
        )
        existing = {str(row.get("phone") or "").strip() for row in (response.data or []) if str(row.get("phone") or "").strip()}
        incoming = set(normalized.keys())
        stale = existing - incoming
        for phone in stale:
            _execute_supabase_with_retry(
                self.client.table("reschedule_sessions").delete().eq("phone", phone),
                f"delete_reschedule_session:{phone}",
            )
        if normalized:
            rows = [{"phone": phone, "payload_json": payload} for phone, payload in normalized.items()]
            _execute_supabase_with_retry(
                self.client.table("reschedule_sessions").upsert(rows, on_conflict="phone"),
                "replace_reschedule_sessions",
            )
        return normalized

    def load_reschedule_sessions(self) -> dict[str, Any]:
        response = _execute_supabase_with_retry(
            self.client.table("reschedule_sessions").select("*"),
            "load_reschedule_sessions",
        )
        return {
            str(row.get("phone") or "").strip(): dict(row.get("payload_json") or {})
            for row in (response.data or [])
            if str(row.get("phone") or "").strip()
        }

    def record_audit_event(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        actor: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "event_type": str(event_type or "").strip(),
            "actor": str(actor or "").strip() or None,
            "request_id": str(request_id or "").strip() or None,
            "payload_json": dict(payload or {}),
        }
        _execute_supabase_with_retry(
            self.client.table("operator_audit_events").insert(event),
            "record_audit_event",
        )
        return event


class FallbackRuntimeStateStore(BaseRuntimeStateStore):
    backend_name = "fallback"

    def __init__(self, primary: BaseRuntimeStateStore, fallback: BaseRuntimeStateStore):
        self.primary = primary
        self.fallback = fallback

    def _call(self, method_name: str, *args, **kwargs):
        primary_method = getattr(self.primary, method_name)
        try:
            return primary_method(*args, **kwargs)
        except Exception as exc:
            logger.warning(
                "Runtime state primary backend failed for %s; falling back to %s: %s",
                method_name,
                getattr(self.fallback, "backend_name", "json"),
                exc,
            )
            fallback_method = getattr(self.fallback, method_name)
            return fallback_method(*args, **kwargs)

    def get_auth_session(self, token: str) -> dict[str, Any] | None:
        return self._call("get_auth_session", token)

    def save_auth_session(self, token: str, expires_at: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._call("save_auth_session", token, expires_at, payload)

    def delete_auth_session(self, token: str) -> bool:
        return self._call("delete_auth_session", token)

    def delete_expired_auth_sessions(self, now_iso: str | None = None) -> int:
        return self._call("delete_expired_auth_sessions", now_iso)

    def touch_auth_session(self, token: str, seen_at: str | None = None) -> dict[str, Any] | None:
        return self._call("touch_auth_session", token, seen_at)

    def get_orchestrator_run(self, run_id: str) -> dict[str, Any] | None:
        return self._call("get_orchestrator_run", run_id)

    def save_orchestrator_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call("save_orchestrator_run", payload)

    def list_orchestrator_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._call("list_orchestrator_runs", limit)

    def replace_reschedule_sessions(self, sessions: dict[str, Any]) -> dict[str, Any]:
        return self._call("replace_reschedule_sessions", sessions)

    def load_reschedule_sessions(self) -> dict[str, Any]:
        return self._call("load_reschedule_sessions")

    def record_audit_event(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        actor: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        return self._call("record_audit_event", event_type, payload, actor, request_id)


_store: BaseRuntimeStateStore | None = None


def get_runtime_state_store() -> BaseRuntimeStateStore:
    global _store
    if _store is not None:
        return _store
    mode = get_data_backend_name()
    if mode == "supabase":
        _store = FallbackRuntimeStateStore(SupabaseRuntimeStateStore(), JsonRuntimeStateStore())
    else:
        _store = JsonRuntimeStateStore()
    return _store


def get_auth_session(token: str) -> dict[str, Any] | None:
    return get_runtime_state_store().get_auth_session(token)


def save_auth_session(token: str, expires_at: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_runtime_state_store().save_auth_session(token, expires_at, payload)


def delete_auth_session(token: str) -> bool:
    return get_runtime_state_store().delete_auth_session(token)


def delete_expired_auth_sessions(now_iso: str | None = None) -> int:
    return get_runtime_state_store().delete_expired_auth_sessions(now_iso=now_iso)


def touch_auth_session(token: str, seen_at: str | None = None) -> dict[str, Any] | None:
    return get_runtime_state_store().touch_auth_session(token, seen_at=seen_at)


def get_orchestrator_run_state(run_id: str) -> dict[str, Any] | None:
    return get_runtime_state_store().get_orchestrator_run(run_id)


def save_orchestrator_run_state(payload: dict[str, Any]) -> dict[str, Any]:
    return get_runtime_state_store().save_orchestrator_run(payload)


def list_orchestrator_run_states(limit: int = 100) -> list[dict[str, Any]]:
    return get_runtime_state_store().list_orchestrator_runs(limit=limit)


def load_reschedule_session_map() -> dict[str, Any]:
    return get_runtime_state_store().load_reschedule_sessions()


def save_reschedule_session_map(sessions: dict[str, Any]) -> dict[str, Any]:
    return get_runtime_state_store().replace_reschedule_sessions(sessions)


def record_operator_audit_event(
    event_type: str,
    payload: dict[str, Any] | None = None,
    actor: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    return get_runtime_state_store().record_audit_event(
        event_type=event_type,
        payload=payload,
        actor=actor,
        request_id=request_id,
    )
