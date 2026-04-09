import json
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()


class ClientStoreError(RuntimeError):
    pass


_supabase_client = None


class BaseClientStore:
    backend_name = "base"

    def list_client_ids(self) -> list[str]:
        raise NotImplementedError

    def list_clients(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_client(self, client_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def save_client(self, client_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def save_brand_profile(self, client_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def get_brand_profile(self, client_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def delete_client(self, client_id: str) -> None:
        raise NotImplementedError


class JsonClientStore(BaseClientStore):
    backend_name = "json"

    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or os.getcwd()
        self.clients_dir = os.path.join(self.base_dir, "clients")
        self.brands_dir = os.path.join(self.base_dir, "brands")
        os.makedirs(self.clients_dir, exist_ok=True)
        os.makedirs(self.brands_dir, exist_ok=True)

    def _client_path(self, client_id: str) -> str:
        return os.path.join(self.clients_dir, f"{client_id}.json")

    def _brand_path(self, client_id: str) -> str:
        return os.path.join(self.brands_dir, f"{client_id}.json")

    def list_client_ids(self) -> list[str]:
        if not os.path.exists(self.clients_dir):
            return []
        return sorted(
            filename[:-5]
            for filename in os.listdir(self.clients_dir)
            if filename.endswith(".json")
        )

    def list_clients(self) -> list[dict[str, Any]]:
        items = []
        for client_id in self.list_client_ids():
            payload = self.get_client(client_id)
            if payload:
                items.append(payload)
        return items

    def get_client(self, client_id: str) -> dict[str, Any] | None:
        path = self._client_path(client_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_client(self, client_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        path = self._client_path(client_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        return payload

    def save_brand_profile(self, client_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        path = self._brand_path(client_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        return payload

    def get_brand_profile(self, client_id: str) -> dict[str, Any] | None:
        path = self._brand_path(client_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def delete_client(self, client_id: str) -> None:
        for path in (self._client_path(client_id), self._brand_path(client_id)):
            if os.path.exists(path):
                os.remove(path)


class SupabaseClientStore(BaseClientStore):
    backend_name = "supabase"

    def __init__(self):
        self.client = get_supabase_service_client()

    def _row_to_client(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "client_id": str(row.get("client_id") or "").strip(),
            "phone_number": str(row.get("phone_number") or "").strip(),
            "meta_access_token": str(row.get("meta_access_token") or "").strip(),
            "facebook_page_id": str(row.get("facebook_page_id") or "").strip(),
            "instagram_account_id": str(row.get("instagram_account_id") or "").strip(),
            "profile_json": row.get("profile_json") or {},
        }

    def _payload_to_row(self, client_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "client_id": client_id,
            "phone_number": str(payload.get("phone_number") or "").strip() or None,
            "meta_access_token": str(payload.get("meta_access_token") or "").strip() or None,
            "facebook_page_id": str(payload.get("facebook_page_id") or "").strip() or None,
            "instagram_account_id": str(payload.get("instagram_account_id") or "").strip() or None,
            "profile_json": payload.get("profile_json") if isinstance(payload.get("profile_json"), dict) else {},
        }

    def list_client_ids(self) -> list[str]:
        response = self.client.table("clients").select("client_id").order("client_id").execute()
        return [str(row.get("client_id") or "").strip() for row in (response.data or []) if str(row.get("client_id") or "").strip()]

    def list_clients(self) -> list[dict[str, Any]]:
        response = self.client.table("clients").select("*").order("client_id").execute()
        return [self._row_to_client(row) for row in (response.data or [])]

    def get_client(self, client_id: str) -> dict[str, Any] | None:
        response = self.client.table("clients").select("*").eq("client_id", client_id).limit(1).execute()
        rows = response.data or []
        return self._row_to_client(rows[0]) if rows else None

    def save_client(self, client_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = self._payload_to_row(client_id, payload)
        self.client.table("clients").upsert(row, on_conflict="client_id").execute()
        return self._row_to_client(row)

    def save_brand_profile(self, client_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = {"client_id": client_id, "brand_json": payload}
        self.client.table("client_brand_profiles").upsert(row, on_conflict="client_id").execute()
        return row

    def get_brand_profile(self, client_id: str) -> dict[str, Any] | None:
        response = self.client.table("client_brand_profiles").select("brand_json").eq("client_id", client_id).limit(1).execute()
        rows = response.data or []
        if not rows:
            return None
        return rows[0].get("brand_json")

    def delete_client(self, client_id: str) -> None:
        self.client.table("client_brand_profiles").delete().eq("client_id", client_id).execute()
        self.client.table("clients").delete().eq("client_id", client_id).execute()


_store: BaseClientStore | None = None


def get_data_backend_name() -> str:
    return str(os.getenv("JARVIS_DATA_BACKEND", "json") or "json").strip().lower()


def get_supabase_service_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise ClientStoreError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for Supabase mode.")
    try:
        from supabase import create_client
    except ImportError as exc:
        raise ClientStoreError(
            "Supabase backend requested but the supabase package is not installed. Add it to the environment first."
        ) from exc

    _supabase_client = create_client(url, key)
    return _supabase_client


def get_client_store() -> BaseClientStore:
    global _store
    if _store is not None:
        return _store

    mode = get_data_backend_name()
    if mode == "supabase":
        _store = SupabaseClientStore()
    else:
        _store = JsonClientStore()
    return _store
