import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import httpx

from client_store import get_data_backend_name, get_supabase_service_client
from file_lock import file_lock
from schedule_utils import coerce_days, parse_iso_date

SCHEDULE_PATH = "schedule.json"
NON_EXECUTABLE_STATUSES = {"pending_approval", "delivered", "rejected", "failed"}
HISTORY_STATUSES = {"delivered", "rejected", "failed"}
DELIVERED_RETENTION_HOURS = 24
logger = logging.getLogger("ScheduleStore")


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
            logger.warning(
                "Supabase transport error during %s (attempt %s/%s): %s",
                label,
                attempt,
                attempts,
                exc,
            )
            time.sleep(base_delay * attempt)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"Supabase request failed during {label}.")


def _coerce_days(value: Any) -> list[str]:
    return coerce_days(value)


def _coerce_images(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _coerce_videos(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _parse_timestamp(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_job(job: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(job) if isinstance(job, dict) else {}
    normalized["job_id"] = str(normalized.get("job_id") or uuid.uuid4().hex[:12]).strip()

    status = str(normalized.get("status") or "approved").strip().lower()
    normalized["status"] = status or "approved"
    normalized["days"] = _coerce_days(normalized.get("days"))
    scheduled_date = str(normalized.get("scheduled_date") or "").strip()
    parsed_date = parse_iso_date(scheduled_date)
    normalized["scheduled_date"] = parsed_date.isoformat() if parsed_date else ""
    normalized["delivered_at"] = str(normalized.get("delivered_at") or "").strip()
    normalized["failed_at"] = str(normalized.get("failed_at") or "").strip()
    normalized["media_kind"] = str(normalized.get("media_kind") or "").strip().lower()

    if "images" in normalized:
        normalized["images"] = _coerce_images(normalized.get("images"))
    if "videos" in normalized:
        normalized["videos"] = _coerce_videos(normalized.get("videos"))

    return normalized


def prune_expired_delivered_jobs(
    jobs: Iterable[dict[str, Any]],
    retention_hours: int = DELIVERED_RETENTION_HOURS,
) -> tuple[list[dict[str, Any]], int]:
    cutoff = _utc_now() - timedelta(hours=retention_hours)
    kept: list[dict[str, Any]] = []
    removed = 0

    for job in jobs:
        normalized = normalize_job(job)
        if normalized.get("status") != "delivered":
            kept.append(normalized)
            continue

        delivered_at = _parse_timestamp(normalized.get("delivered_at"))
        if delivered_at and delivered_at < cutoff:
            removed += 1
            continue
        kept.append(normalized)

    return kept, removed


def split_schedule_views(jobs: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    active: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    today = datetime.now().date()

    for job in jobs:
        normalized = normalize_job(job)
        status = str(normalized.get("status") or "").strip().lower()
        scheduled_date = parse_iso_date(normalized.get("scheduled_date"))
        is_past_one_off = bool(scheduled_date and scheduled_date < today)
        if status in {"delivered", "failed", "rejected"} or is_past_one_off:
            history.append(normalized)
        else:
            active.append(normalized)

    history.sort(
        key=lambda item: str(
            item.get("delivered_at")
            or item.get("failed_at")
            or item.get("scheduled_date")
            or ""
        ),
        reverse=True,
    )
    return active, history


def schedule_signature(job: dict[str, Any]) -> tuple[Any, ...]:
    days = tuple(sorted(day.lower() for day in _coerce_days(job.get("days"))))
    images = tuple(sorted(_coerce_images(job.get("images"))))
    videos = tuple(sorted(_coerce_videos(job.get("videos"))))
    return (
        str(job.get("client") or "").strip().lower(),
        str(job.get("topic") or "").strip().lower(),
        str(job.get("media_kind") or "").strip().lower(),
        str(job.get("scheduled_date") or "").strip(),
        str(job.get("time") or "").strip().lower(),
        days,
        images,
        videos,
    )


def is_schedulable_job(job: dict[str, Any]) -> bool:
    status = str(job.get("status") or "approved").strip().lower()
    return status not in NON_EXECUTABLE_STATUSES


def find_duplicate_active_job(
    jobs: Iterable[dict[str, Any]], candidate: dict[str, Any]
) -> dict[str, Any] | None:
    candidate_signature = schedule_signature(candidate)
    candidate_job_id = str(candidate.get("job_id") or "").strip()

    for job in jobs:
        if not is_schedulable_job(job):
            continue
        if str(job.get("job_id") or "").strip() == candidate_job_id:
            continue
        if schedule_signature(job) == candidate_signature:
            return job
    return None


class BaseScheduleStore:
    backend_name = "base"

    def list_jobs(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def replace_jobs(self, jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        raise NotImplementedError

    def remove_job(self, job_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        raise NotImplementedError

    def mark_job_delivered(self, job_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        raise NotImplementedError

    def mark_job_failed(
        self,
        job_id: str,
        reason: str | None = None,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        raise NotImplementedError

    def cleanup_delivered_jobs(self) -> tuple[int, list[dict[str, Any]]]:
        raise NotImplementedError

    def delete_client_jobs(self, client_id: str) -> int:
        raise NotImplementedError


class JsonScheduleStore(BaseScheduleStore):
    backend_name = "json"

    def __init__(self, path: str = SCHEDULE_PATH):
        self.path = path

    def _list_jobs_unsafe(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            try:
                raw = json.load(f)
            except json.JSONDecodeError:
                return []
        if isinstance(raw, dict):
            raw_jobs = raw.get("schedule", []) if isinstance(raw.get("schedule"), list) else []
        elif isinstance(raw, list):
            raw_jobs = raw
        else:
            raw_jobs = []
        return [normalize_job(job) for job in raw_jobs if isinstance(job, dict)]
        
    def list_jobs(self) -> list[dict[str, Any]]:
        with file_lock(self.path):
            normalized_jobs = self._list_jobs_unsafe()
            pruned_jobs, _ = prune_expired_delivered_jobs(normalized_jobs)
            if pruned_jobs != normalized_jobs:
                self._replace_jobs_unsafe(pruned_jobs)
            return pruned_jobs

    def _replace_jobs_unsafe(self, jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_jobs = [normalize_job(job) for job in jobs if isinstance(job, dict)]
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(normalized_jobs, f, indent=4, ensure_ascii=False)
        return normalized_jobs

    def replace_jobs(self, jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        with file_lock(self.path):
            return self._replace_jobs_unsafe(jobs)

    def remove_job(self, job_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        target_job_id = str(job_id or "").strip()
        if not target_job_id:
            return None, self.list_jobs()

        with file_lock(self.path):
            jobs = self._list_jobs_unsafe()
            removed = None
            kept: list[dict[str, Any]] = []
            for job in jobs:
                if removed is None and str(job.get("job_id") or "").strip() == target_job_id:
                    removed = job
                    continue
                kept.append(job)

            if removed:
                self._replace_jobs_unsafe(kept)

            return removed, kept

    def cleanup_delivered_jobs(self) -> tuple[int, list[dict[str, Any]]]:
        with file_lock(self.path):
            jobs = self._list_jobs_unsafe()
            kept = [
                job
                for job in jobs
                if str(job.get("status") or "").strip().lower() not in ("delivered", "failed")
            ]
            removed = len(jobs) - len(kept)
            if removed > 0:
                self._replace_jobs_unsafe(kept)
            return removed, kept

    def mark_job_status(self, job_id: str, status: str, **extras) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        target_job_id = str(job_id or "").strip()
        if not target_job_id:
            return None, self.list_jobs()

        with file_lock(self.path):
            jobs = self._list_jobs_unsafe()
            updated = None
            for job in jobs:
                if str(job.get("job_id") or "").strip() == target_job_id:
                    job["status"] = status
                    job.update(extras)
                    updated = job
                    break

            if updated:
                self._replace_jobs_unsafe(jobs)

            return updated, jobs

    def mark_job_delivered(self, job_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        return self.mark_job_status(job_id, "delivered", delivered_at=_utc_now().isoformat())

    def mark_job_failed(
        self,
        job_id: str,
        reason: str | None = None,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        extras = {"failed_at": _utc_now().isoformat()}
        if reason:
            extras["failure_reason"] = str(reason).strip()
        return self.mark_job_status(job_id, "failed", **extras)

    def delete_client_jobs(self, client_id: str) -> int:
        with file_lock(self.path):
            jobs = self._list_jobs_unsafe()
            kept = [job for job in jobs if str(job.get("client") or "").strip() != client_id]
            removed = len(jobs) - len(kept)
            if removed > 0:
                self._replace_jobs_unsafe(kept)
            return removed


class SupabaseScheduleStore(BaseScheduleStore):
    backend_name = "supabase"

    def __init__(self):
        self.client = get_supabase_service_client()

    def _row_to_job(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row.get("payload_json") or {})
        payload.update(
            {
                "job_id": row.get("job_id"),
                "client": payload.get("client") or row.get("client_id"),
                "draft_name": payload.get("draft_name") or row.get("draft_name") or "",
                "topic": payload.get("topic") or row.get("topic") or "",
                "status": payload.get("status") or row.get("status") or "approved",
                "media_kind": payload.get("media_kind") or row.get("media_kind") or "",
                "days": payload.get("days") or row.get("days") or [],
                "scheduled_date": payload.get("scheduled_date") or (row.get("scheduled_date").isoformat() if row.get("scheduled_date") else ""),
                "time": payload.get("time") or row.get("time_text") or "",
                "images": payload.get("images") or row.get("images") or [],
                "videos": payload.get("videos") or row.get("videos") or [],
                "approval_id": payload.get("approval_id") or row.get("approval_id") or "",
                "delivered_at": payload.get("delivered_at") or (row.get("delivered_at").isoformat() if row.get("delivered_at") else ""),
            }
        )
        return normalize_job(payload)

    def _job_to_row(self, job: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_job(job)
        payload_json = dict(normalized)
        row = {
            "job_id": normalized["job_id"],
            "client_id": str(normalized.get("client") or "").strip(),
            "draft_name": str(normalized.get("draft_name") or "").strip() or None,
            "topic": str(normalized.get("topic") or "").strip() or None,
            "status": str(normalized.get("status") or "approved").strip().lower(),
            "media_kind": str(normalized.get("media_kind") or "").strip().lower() or None,
            "days": normalized.get("days", []),
            "scheduled_date": normalized.get("scheduled_date") or None,
            "time_text": str(normalized.get("time") or "").strip() or None,
            "images": normalized.get("images", []),
            "videos": normalized.get("videos", []),
            "approval_id": str(normalized.get("approval_id") or "").strip() or None,
            "payload_json": payload_json,
            "delivered_at": normalized.get("delivered_at") or None,
        }
        return row

    def list_jobs(self) -> list[dict[str, Any]]:
        response = _execute_supabase_with_retry(
            self.client.table("schedule_jobs").select("*").order("created_at"),
            "list_jobs",
        )
        normalized_jobs = [self._row_to_job(row) for row in (response.data or [])]
        kept, removed = prune_expired_delivered_jobs(normalized_jobs)
        if removed:
            stale_ids = {
                str(job.get("job_id") or "").strip()
                for job in normalized_jobs
                if job.get("status") == "delivered"
                and str(job.get("job_id") or "").strip()
                and job not in kept
            }
            for stale_id in stale_ids:
                _execute_supabase_with_retry(
                    self.client.table("schedule_jobs").delete().eq("job_id", stale_id),
                    f"delete stale delivered job {stale_id}",
                )
        return kept

    def replace_jobs(self, jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_jobs = [normalize_job(job) for job in jobs if isinstance(job, dict)]
        existing = self.client.table("schedule_jobs").select("job_id").execute()
        existing_ids = {str(row.get("job_id") or "").strip() for row in (existing.data or []) if str(row.get("job_id") or "").strip()}
        incoming_ids = {job["job_id"] for job in normalized_jobs}
        stale_ids = existing_ids - incoming_ids
        if stale_ids:
            for stale_id in stale_ids:
                self.client.table("schedule_jobs").delete().eq("job_id", stale_id).execute()
        if normalized_jobs:
            rows = [self._job_to_row(job) for job in normalized_jobs]
            self.client.table("schedule_jobs").upsert(rows, on_conflict="job_id").execute()
        return normalized_jobs

    def remove_job(self, job_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        existing = next((job for job in self.list_jobs() if str(job.get("job_id") or "").strip() == str(job_id or "").strip()), None)
        if not existing:
            return None, self.list_jobs()
        self.client.table("schedule_jobs").delete().eq("job_id", str(job_id or "").strip()).execute()
        return existing, self.list_jobs()

    def cleanup_delivered_jobs(self) -> tuple[int, list[dict[str, Any]]]:
        jobs = self.list_jobs()
        delivered_ids = [
            str(job.get("job_id") or "").strip()
            for job in jobs
            if str(job.get("status") or "").strip().lower() in HISTORY_STATUSES
        ]
        removed = 0
        for job_id in delivered_ids:
            if job_id:
                self.client.table("schedule_jobs").delete().eq("job_id", job_id).execute()
                removed += 1
        return removed, self.list_jobs()

    def mark_job_delivered(self, job_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        existing = next((job for job in self.list_jobs() if str(job.get("job_id") or "").strip() == str(job_id or "").strip()), None)
        if not existing:
            return None, self.list_jobs()
        existing["status"] = "delivered"
        existing["delivered_at"] = _utc_now().isoformat()
        self.client.table("schedule_jobs").update(self._job_to_row(existing)).eq("job_id", str(job_id or "").strip()).execute()
        return normalize_job(existing), self.list_jobs()

    def mark_job_failed(
        self,
        job_id: str,
        reason: str | None = None,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        existing = next((job for job in self.list_jobs() if str(job.get("job_id") or "").strip() == str(job_id or "").strip()), None)
        if not existing:
            return None, self.list_jobs()
        existing["status"] = "failed"
        existing["failed_at"] = _utc_now().isoformat()
        if reason:
            existing["failure_reason"] = str(reason).strip()
        self.client.table("schedule_jobs").update(self._job_to_row(existing)).eq("job_id", str(job_id or "").strip()).execute()
        return normalize_job(existing), self.list_jobs()

    def delete_client_jobs(self, client_id: str) -> int:
        response = self.client.table("schedule_jobs").select("job_id").eq("client_id", client_id).execute()
        removed = len(response.data or [])
        if removed:
            self.client.table("schedule_jobs").delete().eq("client_id", client_id).execute()
        return removed


_store: BaseScheduleStore | None = None


def get_schedule_store() -> BaseScheduleStore:
    global _store
    if _store is not None:
        return _store
    mode = get_data_backend_name()
    if mode == "supabase":
        _store = SupabaseScheduleStore()
    else:
        _store = JsonScheduleStore()
    return _store


def load_schedule(path: str = SCHEDULE_PATH) -> list[dict[str, Any]]:
    return get_schedule_store().list_jobs()


def save_schedule(jobs: Iterable[dict[str, Any]], path: str = SCHEDULE_PATH) -> None:
    get_schedule_store().replace_jobs(jobs)


def add_scheduled_job(
    job: dict[str, Any], path: str = SCHEDULE_PATH
) -> tuple[bool, dict[str, Any] | None, dict[str, Any]]:
    jobs = load_schedule(path)
    normalized = normalize_job(job)
    normalized["status"] = str(normalized.get("status") or "approved").strip().lower() or "approved"

    duplicate = find_duplicate_active_job(jobs, normalized)
    if duplicate:
        return False, duplicate, normalized

    jobs.append(normalized)
    save_schedule(jobs, path)
    return True, None, normalized


def remove_job(job_id: str, path: str = SCHEDULE_PATH) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    return get_schedule_store().remove_job(job_id)


def cleanup_delivered_jobs(path: str = SCHEDULE_PATH) -> tuple[int, list[dict[str, Any]]]:
    return get_schedule_store().cleanup_delivered_jobs()


def mark_job_delivered(job_id: str, path: str = SCHEDULE_PATH) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    return get_schedule_store().mark_job_delivered(job_id)


def mark_job_failed(
    job_id: str,
    path: str = SCHEDULE_PATH,
    reason: str | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    return get_schedule_store().mark_job_failed(job_id, reason=reason)


def delete_client_schedule_jobs(client_id: str) -> int:
    return get_schedule_store().delete_client_jobs(client_id)
