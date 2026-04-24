import os
import threading
from typing import Any
from urllib.parse import urlparse


_PUBLIC_BASE_LOCK = threading.Lock()
_OBSERVED_PUBLIC_BASE_URL = ""

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
_EPHEMERAL_HOST_HINTS = ("trycloudflare.com", "ngrok-free.app", "ngrok.app", "ngrok.io")


def _normalize_public_base(value: str | None) -> str:
    raw = str(value or "").strip().rstrip("/")
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.netloc or parsed.path or "").strip().rstrip("/")
    if not host:
        return ""
    scheme = parsed.scheme or "https"
    if scheme not in {"http", "https"}:
        scheme = "https"
    return f"{scheme}://{host}"


def _host_for_base(value: str | None) -> str:
    normalized = _normalize_public_base(value)
    if not normalized:
        return ""
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").strip().lower()
    return host


def _is_public_host(host: str) -> bool:
    candidate = str(host or "").strip().lower()
    return bool(candidate) and candidate not in _LOCAL_HOSTS


def _is_ephemeral_base(value: str | None) -> bool:
    host = _host_for_base(value)
    return any(hint in host for hint in _EPHEMERAL_HOST_HINTS)


def remember_public_base_url(value: str | None) -> str:
    normalized = _normalize_public_base(value)
    if not normalized or not _is_public_host(_host_for_base(normalized)):
        return ""
    with _PUBLIC_BASE_LOCK:
        global _OBSERVED_PUBLIC_BASE_URL
        _OBSERVED_PUBLIC_BASE_URL = normalized
    return normalized


def remember_public_base_from_request(request: Any) -> str:
    if request is None:
        return ""
    forwarded_host = str(request.headers.get("x-forwarded-host") or "").strip()
    host_header = forwarded_host or str(request.headers.get("host") or "").strip()
    proto = str(request.headers.get("x-forwarded-proto") or request.url.scheme or "https").strip().lower() or "https"
    if proto not in {"http", "https"}:
        proto = "https"
    host = host_header.split(",", 1)[0].strip()
    if not _is_public_host(host.split(":", 1)[0]):
        return ""
    return remember_public_base_url(f"{proto}://{host}")


def get_observed_public_base_url() -> str:
    with _PUBLIC_BASE_LOCK:
        return _OBSERVED_PUBLIC_BASE_URL


def get_public_base_url() -> str:
    observed = get_observed_public_base_url()
    if observed:
        return observed
    explicit = _normalize_public_base(os.getenv("META_OAUTH_PUBLIC_BASE_URL"))
    webhook = _normalize_public_base(os.getenv("WEBHOOK_PROXY_URL"))
    if explicit and not _is_ephemeral_base(explicit):
        return explicit
    if webhook and not _is_ephemeral_base(webhook):
        return webhook
    return explicit or webhook or ""


def get_meta_oauth_redirect_uri() -> str:
    observed = get_observed_public_base_url()
    if observed:
        return f"{observed}/api/meta-oauth-callback"
    explicit = str(os.getenv("META_OAUTH_REDIRECT_URI") or "").strip()
    if explicit and not _is_ephemeral_base(explicit):
        return explicit
    public_base = get_public_base_url()
    if public_base:
        return f"{public_base}/api/meta-oauth-callback"
    return explicit


def reset_observed_public_base_url() -> None:
    with _PUBLIC_BASE_LOCK:
        global _OBSERVED_PUBLIC_BASE_URL
        _OBSERVED_PUBLIC_BASE_URL = ""
