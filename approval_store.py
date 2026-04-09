import json
import os
from typing import Any

from client_store import get_data_backend_name, get_supabase_service_client
from file_lock import file_lock

PENDING_APPROVALS_PATH = "pending_approvals.json"


class BaseApprovalStore:
    backend_name = "base"

    def list_approvals(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def save_approval(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def update_approval(self, approval_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        raise NotImplementedError

    def delete_approval(self, approval_id: str) -> bool:
        raise NotImplementedError

    def delete_client_approvals(self, client_id: str) -> int:
        raise NotImplementedError

    def delete_all_approvals(self) -> int:
        raise NotImplementedError


class JsonApprovalStore(BaseApprovalStore):
    backend_name = "json"

    def _list_approvals_unsafe(self) -> list[dict[str, Any]]:
        if not os.path.exists(PENDING_APPROVALS_PATH):
            return []
        try:
            with open(PENDING_APPROVALS_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return []
        return [dict(item) for item in payload if isinstance(item, dict)]

    def list_approvals(self) -> list[dict[str, Any]]:
        with file_lock(PENDING_APPROVALS_PATH, shared=True):
            return self._list_approvals_unsafe()

    def _save_all_unsafe(self, approvals: list[dict[str, Any]]) -> None:
        with open(PENDING_APPROVALS_PATH, "w", encoding="utf-8") as f:
            json.dump(approvals, f, indent=4, ensure_ascii=False)

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        for approval in self.list_approvals():
            if str(approval.get("approval_id") or "").strip().upper() == str(approval_id or "").strip().upper():
                return approval
        return None

    def save_approval(self, payload: dict[str, Any]) -> dict[str, Any]:
        with file_lock(PENDING_APPROVALS_PATH):
            approvals = self._list_approvals_unsafe()
            approval_id = str(payload.get("approval_id") or "").strip().upper()
            approvals = [item for item in approvals if str(item.get("approval_id") or "").strip().upper() != approval_id]
            approvals.append(dict(payload))
            self._save_all_unsafe(approvals)
            return dict(payload)

    def update_approval(self, approval_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        with file_lock(PENDING_APPROVALS_PATH):
            approvals = self._list_approvals_unsafe()
            updated = None
            approval_key = str(approval_id or "").strip().upper()
            for idx, item in enumerate(approvals):
                if str(item.get("approval_id") or "").strip().upper() == approval_key:
                    updated = dict(payload)
                    approvals[idx] = updated
                    break
            if updated is None:
                return None
            self._save_all_unsafe(approvals)
            return updated

    def delete_approval(self, approval_id: str) -> bool:
        return removed


class SupabaseApprovalStore(BaseApprovalStore):
    backend_name = "supabase"

    def __init__(self):
        self.client = get_supabase_service_client()

    def _row_to_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row.get("payload_json") or {})
        payload["approval_id"] = row.get("approval_id")
        payload["client"] = payload.get("client") or row.get("client_id")
        payload["status"] = payload.get("status") or row.get("status") or "pending_approval"
        if row.get("job_id") and not payload.get("job_id"):
            payload["job_id"] = row.get("job_id")
        return payload

    def list_approvals(self) -> list[dict[str, Any]]:
        response = (
            self.client.table("approval_requests")
            .select("*")
            .order("requested_at")
            .execute()
        )
        return [self._row_to_payload(row) for row in (response.data or [])]

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        response = (
            self.client.table("approval_requests")
            .select("*")
            .eq("approval_id", approval_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None
        return self._row_to_payload(rows[0])

    def save_approval(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            "approval_id": str(payload.get("approval_id") or "").strip().upper(),
            "client_id": str(payload.get("client") or "").strip(),
            "job_id": str(payload.get("job_id") or "").strip() or None,
            "status": str(payload.get("status") or "pending_approval").strip().lower(),
            "payload_json": dict(payload),
        }
        self.client.table("approval_requests").upsert(row, on_conflict="approval_id").execute()
        return dict(payload)

    def update_approval(self, approval_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        existing = self.get_approval(approval_id)
        if not existing:
            return None
        row = {
            "client_id": str(payload.get("client") or existing.get("client") or "").strip(),
            "job_id": str(payload.get("job_id") or existing.get("job_id") or "").strip() or None,
            "status": str(payload.get("status") or existing.get("status") or "pending_approval").strip().lower(),
            "payload_json": dict(payload),
        }
        self.client.table("approval_requests").update(row).eq("approval_id", approval_id).execute()
        return dict(payload)

    def delete_approval(self, approval_id: str) -> bool:
        existing = self.get_approval(approval_id)
        if not existing:
            return False
        self.client.table("approval_requests").delete().eq("approval_id", approval_id).execute()
        return True

    def delete_client_approvals(self, client_id: str) -> int:
        response = self.client.table("approval_requests").select("approval_id").eq("client_id", client_id).execute()
        removed = len(response.data or [])
        if removed:
            self.client.table("approval_requests").delete().eq("client_id", client_id).execute()
        return removed

    def delete_all_approvals(self) -> int:
        response = self.client.table("approval_requests").select("approval_id").execute()
        removed = len(response.data or [])
        if removed:
            self.client.table("approval_requests").delete().neq("approval_id", "").execute()
        return removed


_store: BaseApprovalStore | None = None


def get_approval_store() -> BaseApprovalStore:
    global _store
    if _store is not None:
        return _store
    mode = get_data_backend_name()
    if mode == "supabase":
        _store = SupabaseApprovalStore()
    else:
        _store = JsonApprovalStore()
    return _store


def list_pending_approvals() -> list[dict[str, Any]]:
    return get_approval_store().list_approvals()


def get_pending_approval(approval_id: str) -> dict[str, Any] | None:
    return get_approval_store().get_approval(approval_id)


def save_pending_approval(payload: dict[str, Any]) -> dict[str, Any]:
    return get_approval_store().save_approval(payload)


def update_pending_approval(approval_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    return get_approval_store().update_approval(approval_id, payload)


def delete_pending_approval(approval_id: str) -> bool:
    return get_approval_store().delete_approval(approval_id)


def delete_client_pending_approvals(client_id: str) -> int:
    return get_approval_store().delete_client_approvals(client_id)


def delete_all_pending_approvals() -> int:
    return get_approval_store().delete_all_approvals()
