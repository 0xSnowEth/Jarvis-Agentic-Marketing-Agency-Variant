import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from schedule_utils import coerce_days, parse_iso_date

SCHEDULE_PATH = "schedule.json"
NON_EXECUTABLE_STATUSES = {"pending_approval", "delivered", "rejected", "failed"}
DELIVERED_RETENTION_HOURS = 24


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


def load_schedule(path: str = SCHEDULE_PATH) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
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

    normalized_jobs = [normalize_job(job) for job in raw_jobs if isinstance(job, dict)]
    normalized_jobs, _ = prune_expired_delivered_jobs(normalized_jobs)
    if normalized_jobs != raw_jobs:
        save_schedule(normalized_jobs, path)

    return normalized_jobs


def save_schedule(jobs: Iterable[dict[str, Any]], path: str = SCHEDULE_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list(jobs), f, indent=4, ensure_ascii=False)


def split_schedule_views(jobs: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    active: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    for job in jobs:
        normalized = normalize_job(job)
        if normalized.get("status") == "delivered":
            history.append(normalized)
        else:
            active.append(normalized)

    history.sort(key=lambda item: str(item.get("delivered_at") or ""), reverse=True)
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
    target_job_id = str(job_id or "").strip()
    if not target_job_id:
        return None, load_schedule(path)

    jobs = load_schedule(path)
    removed = None
    kept: list[dict[str, Any]] = []
    for job in jobs:
        if removed is None and str(job.get("job_id") or "").strip() == target_job_id:
            removed = job
            continue
        kept.append(job)

    if removed:
        save_schedule(kept, path)

    return removed, kept


def cleanup_delivered_jobs(path: str = SCHEDULE_PATH) -> tuple[int, list[dict[str, Any]]]:
    jobs = load_schedule(path)
    kept = [job for job in jobs if job.get("status") != "delivered"]
    removed = len(jobs) - len(kept)
    if removed:
        save_schedule(kept, path)
    return removed, kept


def mark_job_delivered(job_id: str, path: str = SCHEDULE_PATH) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    target_job_id = str(job_id or "").strip()
    if not target_job_id:
        return None, load_schedule(path)

    jobs = load_schedule(path)
    matched = None
    for job in jobs:
        if str(job.get("job_id") or "").strip() == target_job_id:
            job["status"] = "delivered"
            job["delivered_at"] = _utc_now().isoformat()
            matched = job
            break

    if matched:
        save_schedule(jobs, path)

    return matched, jobs
