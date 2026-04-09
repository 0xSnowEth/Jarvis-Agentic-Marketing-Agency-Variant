import os
from typing import Any

from client_store import ClientStoreError, get_data_backend_name, get_supabase_service_client
from queue_store import get_bundle_payload, normalize_bundle_entry, load_queue_data, save_queue_data


class BaseDraftStore:
    backend_name = "base"

    def list_drafts(self, client_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def get_draft(self, client_id: str, draft_name: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def get_draft_by_id(self, client_id: str, draft_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def save_draft(self, client_id: str, draft_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def delete_draft(self, client_id: str, draft_name: str) -> bool:
        raise NotImplementedError

    def rename_draft(self, client_id: str, draft_name: str, new_name: str) -> dict[str, Any]:
        raise NotImplementedError

    def delete_client_drafts(self, client_id: str) -> int:
        raise NotImplementedError


class JsonDraftStore(BaseDraftStore):
    backend_name = "json"

    def _queue_path(self, client_id: str) -> str:
        return os.path.join("assets", client_id, "queue.json")

    def list_drafts(self, client_id: str) -> dict[str, Any]:
        queue_path = self._queue_path(client_id)
        if not os.path.exists(queue_path):
            return {"bundles": {}}
        return load_queue_data(queue_path)

    def get_draft(self, client_id: str, draft_name: str) -> dict[str, Any] | None:
        queue_path = self._queue_path(client_id)
        if not os.path.exists(queue_path):
            return None
        return get_bundle_payload(queue_path, draft_name)

    def get_draft_by_id(self, client_id: str, draft_id: str) -> dict[str, Any] | None:
        if not draft_id:
            return None
        bundles = self.list_drafts(client_id).get("bundles", {})
        for draft_name, payload in bundles.items():
            if str((payload or {}).get("draft_id") or "").strip() == str(draft_id).strip():
                normalized = normalize_bundle_entry(draft_name, payload)
                normalized["draft_id"] = str(draft_id).strip()
                return normalized
        return None

    def save_draft(self, client_id: str, draft_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        queue_path = self._queue_path(client_id)
        os.makedirs(os.path.dirname(queue_path), exist_ok=True)
        data = load_queue_data(queue_path)
        normalized = normalize_bundle_entry(draft_name, payload)
        data["bundles"][draft_name] = {
            "bundle_type": normalized["bundle_type"],
            "items": normalized["items"],
            "caption_mode": normalized["caption_mode"],
            "caption_status": normalized["caption_status"],
            "caption_text": normalized["caption_text"],
            "hashtags": normalized["hashtags"],
            "seo_keyword_used": normalized["seo_keyword_used"],
            "topic_hint": normalized["topic_hint"],
        }
        save_queue_data(queue_path, data)
        return self.get_draft(client_id, draft_name) or normalized

    def delete_draft(self, client_id: str, draft_name: str) -> bool:
        queue_path = self._queue_path(client_id)
        if not os.path.exists(queue_path):
            return False
        data = load_queue_data(queue_path)
        bundles = data.get("bundles", {})
        if draft_name not in bundles:
            return False
        del bundles[draft_name]
        save_queue_data(queue_path, data)
        return True

    def rename_draft(self, client_id: str, draft_name: str, new_name: str) -> dict[str, Any]:
        queue_path = self._queue_path(client_id)
        if not os.path.exists(queue_path):
            raise ClientStoreError("Queue not found.")
        data = load_queue_data(queue_path)
        bundles = data.get("bundles", {})
        if draft_name not in bundles:
            raise ClientStoreError("Draft not found.")
        if new_name != draft_name and new_name in bundles:
            raise ClientStoreError("A draft with that name already exists.")
        bundles[new_name] = bundles.pop(draft_name)
        save_queue_data(queue_path, data)
        return self.get_draft(client_id, new_name) or normalize_bundle_entry(new_name, bundles[new_name])

    def delete_client_drafts(self, client_id: str) -> int:
        queue_path = self._queue_path(client_id)
        if not os.path.exists(queue_path):
            return 0
        bundles = load_queue_data(queue_path).get("bundles", {})
        removed = len(bundles)
        save_queue_data(queue_path, {"bundles": {}})
        return removed


class SupabaseDraftStore(BaseDraftStore):
    backend_name = "supabase"

    def __init__(self):
        self.client = get_supabase_service_client()

    def _row_to_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        return normalize_bundle_entry(
            str(row.get("draft_name") or "").strip(),
            {
                "bundle_type": row.get("bundle_type"),
                "items": row.get("items", []),
                "caption_mode": row.get("caption_mode"),
                "caption_status": row.get("caption_status"),
                "caption_text": row.get("caption_text"),
                "hashtags": row.get("hashtags", []),
                "seo_keyword_used": row.get("seo_keyword_used"),
                "topic_hint": row.get("topic_hint"),
            },
        )

    def list_drafts(self, client_id: str) -> dict[str, Any]:
        response = (
            self.client.table("creative_drafts")
            .select("*")
            .eq("client_id", client_id)
            .order("created_at")
            .execute()
        )
        bundles = {}
        for row in response.data or []:
            payload = self._row_to_payload(row)
            bundles[payload["bundle_name"]] = {
                "bundle_type": payload["bundle_type"],
                "items": payload["items"],
                "caption_mode": payload["caption_mode"],
                "caption_status": payload["caption_status"],
                "caption_text": payload["caption_text"],
                "hashtags": payload["hashtags"],
                "seo_keyword_used": payload["seo_keyword_used"],
                "topic_hint": payload["topic_hint"],
                "draft_id": row.get("draft_id"),
            }
        return {"bundles": bundles}

    def get_draft(self, client_id: str, draft_name: str) -> dict[str, Any] | None:
        response = (
            self.client.table("creative_drafts")
            .select("*")
            .eq("client_id", client_id)
            .eq("draft_name", draft_name)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None
        payload = self._row_to_payload(rows[0])
        payload["draft_id"] = rows[0].get("draft_id")
        return payload

    def get_draft_by_id(self, client_id: str, draft_id: str) -> dict[str, Any] | None:
        response = (
            self.client.table("creative_drafts")
            .select("*")
            .eq("client_id", client_id)
            .eq("draft_id", draft_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None
        payload = self._row_to_payload(rows[0])
        payload["draft_id"] = rows[0].get("draft_id")
        return payload

    def save_draft(self, client_id: str, draft_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_bundle_entry(draft_name, payload)
        row = {
            "client_id": client_id,
            "draft_name": draft_name,
            "bundle_type": normalized["bundle_type"],
            "items": normalized["items"],
            "caption_mode": normalized["caption_mode"],
            "caption_status": normalized["caption_status"],
            "caption_text": normalized["caption_text"],
            "hashtags": normalized["hashtags"],
            "seo_keyword_used": normalized["seo_keyword_used"],
            "topic_hint": normalized["topic_hint"],
        }
        self.client.table("creative_drafts").upsert(row, on_conflict="client_id,draft_name").execute()
        return self.get_draft(client_id, draft_name) or normalized

    def delete_draft(self, client_id: str, draft_name: str) -> bool:
        existing = self.get_draft(client_id, draft_name)
        if not existing:
            return False
        self.client.table("creative_drafts").delete().eq("client_id", client_id).eq("draft_name", draft_name).execute()
        return True

    def rename_draft(self, client_id: str, draft_name: str, new_name: str) -> dict[str, Any]:
        existing = self.get_draft(client_id, draft_name)
        if not existing:
            raise ClientStoreError("Draft not found.")
        if new_name != draft_name and self.get_draft(client_id, new_name):
            raise ClientStoreError("A draft with that name already exists.")
        self.client.table("creative_drafts").update({"draft_name": new_name}).eq("client_id", client_id).eq("draft_name", draft_name).execute()
        return self.get_draft(client_id, new_name) or normalize_bundle_entry(new_name, existing)

    def delete_client_drafts(self, client_id: str) -> int:
        response = self.client.table("creative_drafts").select("draft_name").eq("client_id", client_id).execute()
        removed = len(response.data or [])
        if removed:
            self.client.table("creative_drafts").delete().eq("client_id", client_id).execute()
        return removed


_store: BaseDraftStore | None = None


def get_draft_store() -> BaseDraftStore:
    global _store
    if _store is not None:
        return _store

    mode = get_data_backend_name()
    if mode == "supabase":
        _store = SupabaseDraftStore()
    else:
        _store = JsonDraftStore()
    return _store


def list_client_drafts(client_id: str) -> dict[str, Any]:
    return get_draft_store().list_drafts(client_id)


def get_draft_payload(client_id: str, draft_name: str) -> dict[str, Any] | None:
    return get_draft_store().get_draft(client_id, draft_name)


def get_draft_payload_by_id(client_id: str, draft_id: str) -> dict[str, Any] | None:
    return get_draft_store().get_draft_by_id(client_id, draft_id)


def _normalize_draft_lookup_key(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    cleaned = cleaned.replace("_", " ").replace("-", " ")
    cleaned = " ".join(cleaned.split())
    return cleaned


def resolve_draft_payload(client_id: str, draft_name: str | None = None, draft_id: str | None = None) -> dict[str, Any] | None:
    payload = None
    normalized_id = str(draft_id or "").strip()
    normalized_name = str(draft_name or "").strip()

    if normalized_id:
        payload = get_draft_payload_by_id(client_id, normalized_id)
        if payload is not None:
            return payload

    if normalized_name:
        payload = get_draft_payload(client_id, normalized_name)
        if payload is not None:
            return payload

    bundles = list_client_drafts(client_id).get("bundles", {})
    if not isinstance(bundles, dict) or not bundles:
        return None

    if normalized_name:
        wanted = _normalize_draft_lookup_key(normalized_name)
        for bundle_name in bundles.keys():
            if _normalize_draft_lookup_key(bundle_name) == wanted:
                payload = get_draft_payload(client_id, bundle_name)
                if payload is not None:
                    return payload

    if len(bundles) == 1:
        only_name = next(iter(bundles.keys()))
        payload = get_draft_payload(client_id, only_name)
        if payload is not None:
            return payload

    return None


def save_draft_payload(client_id: str, draft_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return get_draft_store().save_draft(client_id, draft_name, payload)


def delete_draft_payload(client_id: str, draft_name: str) -> bool:
    return get_draft_store().delete_draft(client_id, draft_name)


def rename_draft_payload(client_id: str, draft_name: str, new_name: str) -> dict[str, Any]:
    return get_draft_store().rename_draft(client_id, draft_name, new_name)


def delete_client_drafts(client_id: str) -> int:
    return get_draft_store().delete_client_drafts(client_id)


def get_draft_media_paths(client_id: str, draft_name: str | None = None, draft_id: str | None = None) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    payload = resolve_draft_payload(client_id, draft_name=draft_name, draft_id=draft_id)
    if payload is None:
        return None, [], []

    images = []
    videos = []
    for item in payload.get("items", []):
        filename = str(item.get("filename") or "").strip()
        if not filename:
            continue
        path = f"assets/{client_id}/{filename}"
        if str(item.get("kind") or "").strip().lower() == "video":
            videos.append(path)
        else:
            images.append(path)
    return payload, images, videos
