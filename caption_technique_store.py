import json
import os
from typing import Any

from client_store import ClientStoreError, get_data_backend_name, get_supabase_service_client


class BaseCaptionTechniqueStore:
    backend_name = "base"

    def get_snapshot(self, snapshot_key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def save_snapshot(self, snapshot_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class JsonCaptionTechniqueStore(BaseCaptionTechniqueStore):
    backend_name = "json"

    def __init__(self, filepath: str | None = None):
        self.filepath = filepath or os.path.join(os.getcwd(), "caption_techniques.json")

    def _load(self) -> dict[str, Any]:
        if not os.path.exists(self.filepath):
            return {"snapshots": {}}
        with open(self.filepath, "r", encoding="utf-8") as handle:
            try:
                data = json.load(handle)
            except Exception:
                data = {"snapshots": {}}
        if not isinstance(data, dict):
            data = {"snapshots": {}}
        snapshots = data.get("snapshots")
        if not isinstance(snapshots, dict):
            data["snapshots"] = {}
        return data

    def _save(self, payload: dict[str, Any]) -> None:
        with open(self.filepath, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

    def get_snapshot(self, snapshot_key: str) -> dict[str, Any] | None:
        return dict(self._load().get("snapshots", {}).get(snapshot_key) or {}) or None

    def save_snapshot(self, snapshot_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._load()
        data.setdefault("snapshots", {})[snapshot_key] = dict(payload or {})
        self._save(data)
        return dict(data["snapshots"][snapshot_key])


class SupabaseCaptionTechniqueStore(BaseCaptionTechniqueStore):
    backend_name = "supabase"

    def __init__(self):
        self.client = get_supabase_service_client()

    def get_snapshot(self, snapshot_key: str) -> dict[str, Any] | None:
        response = (
            self.client.table("caption_technique_snapshots")
            .select("*")
            .eq("snapshot_key", snapshot_key)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None
        snapshot = rows[0].get("snapshot_json")
        return dict(snapshot) if isinstance(snapshot, dict) else None

    def save_snapshot(self, snapshot_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = {"snapshot_key": snapshot_key, "snapshot_json": dict(payload or {})}
        self.client.table("caption_technique_snapshots").upsert(row, on_conflict="snapshot_key").execute()
        return dict(payload or {})


_store: BaseCaptionTechniqueStore | None = None


def get_caption_technique_store() -> BaseCaptionTechniqueStore:
    global _store
    if _store is not None:
        return _store
    mode = get_data_backend_name()
    if mode == "supabase":
        try:
            _store = SupabaseCaptionTechniqueStore()
            return _store
        except ClientStoreError:
            pass
    _store = JsonCaptionTechniqueStore()
    return _store


def get_caption_technique_snapshot(snapshot_key: str) -> dict[str, Any] | None:
    return get_caption_technique_store().get_snapshot(snapshot_key)


def save_caption_technique_snapshot(snapshot_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return get_caption_technique_store().save_snapshot(snapshot_key, payload)
