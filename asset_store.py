import mimetypes
import os
import shutil
import subprocess
import tempfile
import json
import time
from urllib.parse import quote
from typing import Any

import requests
from PIL import Image, ImageOps

from client_store import get_data_backend_name, get_supabase_service_client
from queue_store import VIDEO_EXTENSIONS, detect_media_kind
from input_validation import validate_client_id, validate_filename

DEFAULT_ASSET_BUCKET = os.getenv("SUPABASE_ASSET_BUCKET", "client-assets").strip() or "client-assets"
DEFAULT_STORAGE_UPLOAD_TIMEOUT = int(os.getenv("SUPABASE_ASSET_UPLOAD_TIMEOUT_SECONDS", "240"))
DEFAULT_STORAGE_READ_TIMEOUT = int(os.getenv("SUPABASE_ASSET_READ_TIMEOUT_SECONDS", "60"))
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_INSTAGRAM_IMAGE_DIMENSION = 1440
MIN_INSTAGRAM_ASPECT_RATIO = 4 / 5
MAX_INSTAGRAM_ASPECT_RATIO = 1.91
VAULT_PREVIEW_WIDTH = 240
VAULT_PREVIEW_HEIGHT = 240
VAULT_PREVIEW_QUALITY = 72
JSON_METADATA_SUFFIX = ".meta.json"
JSON_THUMBNAIL_SUFFIX = ".thumb.jpg"


def _probe_image_metadata(filename: str, file_bytes: bytes) -> dict[str, Any]:
    try:
        with tempfile.SpooledTemporaryFile() as handle:
            handle.write(file_bytes)
            handle.seek(0)
            with Image.open(handle) as image:
                image_format = str(image.format or "").upper()
                progressive = bool(image.info.get("progressive") or image.info.get("progression"))
                image = ImageOps.exif_transpose(image)
                width, height = image.size
                mode = str(image.mode or "").upper()
    except Exception:
        return {
            "image_inspection_version": 1,
            "image_format": "",
            "image_mode": "",
            "width": 0,
            "height": 0,
            "progressive": False,
            "meta_safe_status": "unknown",
            "needs_meta_repair": False,
            "meta_repair_reason": "",
        }

    reason = ""
    aspect_ratio = (width / height) if width and height else 0.0
    extension = os.path.splitext(str(filename or "").strip())[1].lower()
    if image_format not in {"JPEG", "JPG"}:
        reason = f"{os.path.basename(filename) or 'image'} must be converted to JPEG for Instagram publishing."
    elif mode != "RGB":
        reason = f"{os.path.basename(filename) or 'image'} uses {mode or 'unknown'} color mode and must be converted to RGB JPEG."
    elif progressive:
        reason = f"{os.path.basename(filename) or 'image'} is progressive and must be rewritten as a baseline JPEG."
    elif width > MAX_INSTAGRAM_IMAGE_DIMENSION or height > MAX_INSTAGRAM_IMAGE_DIMENSION:
        reason = (
            f"{os.path.basename(filename) or 'image'} is {width}x{height}. "
            f"Jarvis normalizes Instagram images to a maximum edge of {MAX_INSTAGRAM_IMAGE_DIMENSION}px."
        )
    elif aspect_ratio and not (MIN_INSTAGRAM_ASPECT_RATIO <= aspect_ratio <= MAX_INSTAGRAM_ASPECT_RATIO):
        reason = (
            f"{os.path.basename(filename) or 'image'} uses aspect ratio {aspect_ratio:.3f}. "
            "Instagram feed publishing requires an aspect ratio between 4:5 and 1.91:1."
        )
    elif extension not in {".jpg", ".jpeg"}:
        reason = f"{os.path.basename(filename) or 'image'} must be stored as JPG/JPEG for Instagram publishing."

    return {
        "image_inspection_version": 1,
        "image_format": image_format,
        "image_mode": mode,
        "width": width,
        "height": height,
        "progressive": progressive,
        "meta_safe_status": "needs_repair" if reason else "safe",
        "needs_meta_repair": bool(reason),
        "meta_repair_reason": reason,
    }


def _new_preview_version() -> str:
    return str(int(time.time() * 1000))


def _build_thumbnail_bytes(file_bytes: bytes, width: int = VAULT_PREVIEW_WIDTH, height: int = VAULT_PREVIEW_HEIGHT) -> bytes:
    with tempfile.SpooledTemporaryFile() as handle:
        handle.write(file_bytes)
        handle.seek(0)
        with Image.open(handle) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            if image.mode == "L":
                image = image.convert("RGB")
            thumb = ImageOps.fit(image, (width, height), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            with tempfile.SpooledTemporaryFile() as output:
                thumb.save(output, format="JPEG", quality=VAULT_PREVIEW_QUALITY, optimize=True, progressive=False)
                output.seek(0)
                return output.read()


def _normalize_image_upload(filename: str, file_bytes: bytes) -> tuple[str, bytes, dict[str, Any]]:
    extension = os.path.splitext(str(filename or "").strip())[1].lower()
    if extension not in IMAGE_EXTENSIONS:
        return filename, file_bytes, {}

    with tempfile.SpooledTemporaryFile() as handle:
        handle.write(file_bytes)
        handle.seek(0)
        with Image.open(handle) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode != "RGB":
                image = image.convert("RGB")
            if max(image.size) > MAX_INSTAGRAM_IMAGE_DIMENSION:
                image.thumbnail((MAX_INSTAGRAM_IMAGE_DIMENSION, MAX_INSTAGRAM_IMAGE_DIMENSION), Image.Resampling.LANCZOS)

            with tempfile.SpooledTemporaryFile() as output:
                image.save(output, format="JPEG", quality=92, optimize=True, progressive=False)
                output.seek(0)
                normalized_bytes = output.read()
            stem = os.path.splitext(str(filename or "").strip() or "image")[0]
            normalized_filename = f"{stem}.jpg"
            metadata = {
                "normalized_for_meta": True,
                "original_filename": filename,
                "original_extension": extension,
                "normalization_pipeline": "pillow_rgb_baseline_jpeg",
                **_probe_image_metadata(normalized_filename, normalized_bytes),
                "has_poster": False,
            }
            return normalized_filename, normalized_bytes, metadata


def _safe_normalize_image_upload(filename: str, file_bytes: bytes) -> tuple[str, bytes, dict[str, Any]]:
    try:
        return _normalize_image_upload(filename, file_bytes)
    except Exception:
        return filename, file_bytes, _probe_image_metadata(filename, file_bytes)


def _probe_video_metadata(video_path: str, display_name: str) -> dict[str, Any]:
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        payload = json.loads(probe.stdout or "{}")
    except Exception:
        return {
            "meta_inspection_version": 2,
            "video_codec": "",
            "pixel_format": "",
            "audio_codec": "",
            "audio_profile": "",
            "format_name": "",
            "duration_seconds": 0.0,
            "frame_rate_fps": 0.0,
            "video_bit_rate": 0,
            "audio_bit_rate": 0,
            "width": 0,
            "height": 0,
            "sample_rate": 0,
            "channels": 0,
            "has_audio": False,
            "meta_safe_status": "unknown",
            "needs_meta_repair": False,
            "meta_repair_reason": "",
        }

    streams = payload.get("streams") or []
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)

    video_codec = str((video_stream or {}).get("codec_name") or "").lower()
    pixel_format = str((video_stream or {}).get("pix_fmt") or "").lower()
    audio_codec = str((audio_stream or {}).get("codec_name") or "").lower()
    audio_profile = str((audio_stream or {}).get("profile") or "")
    format_info = payload.get("format") or {}
    format_name = str(format_info.get("format_name") or "").lower()
    width = int((video_stream or {}).get("width") or 0)
    height = int((video_stream or {}).get("height") or 0)
    sample_rate = int(str((audio_stream or {}).get("sample_rate") or "0") or 0)
    channels = int((audio_stream or {}).get("channels") or 0)

    duration_seconds = 0.0
    try:
        duration_seconds = float((video_stream or {}).get("duration") or format_info.get("duration") or 0.0)
    except (TypeError, ValueError):
        duration_seconds = 0.0

    def _parse_fps(raw: str) -> float:
        text = str(raw or "").strip()
        if not text or text in {"0/0", "0", "0.0"}:
            return 0.0
        if "/" in text:
            a, b = text.split("/", 1)
            try:
                num = float(a)
                den = float(b)
                return num / den if den else 0.0
            except (TypeError, ValueError, ZeroDivisionError):
                return 0.0
        try:
            return float(text)
        except (TypeError, ValueError):
            return 0.0

    frame_rate_fps = _parse_fps((video_stream or {}).get("avg_frame_rate") or (video_stream or {}).get("r_frame_rate") or "")

    def _parse_int(raw: Any) -> int:
        try:
            return int(str(raw or "0") or 0)
        except (TypeError, ValueError):
            return 0

    video_bit_rate = _parse_int((video_stream or {}).get("bit_rate"))
    audio_bit_rate = _parse_int((audio_stream or {}).get("bit_rate"))

    reason = ""
    if not video_stream:
        reason = f"{display_name} does not contain a valid video stream."
    elif video_codec != "h264":
        reason = f"{display_name} is encoded as {video_codec or 'unknown'} video."
    elif pixel_format and pixel_format != "yuv420p":
        reason = f"{display_name} uses {pixel_format} pixel format."
    elif audio_stream and audio_codec != "aac":
        reason = f"{display_name} uses {audio_codec or 'unknown'} audio."
    elif audio_profile and "HE-AAC" in audio_profile.upper():
        reason = f"{display_name} uses HE-AAC audio."
    elif duration_seconds and duration_seconds > 90.0:
        reason = f"{display_name} is {duration_seconds:.1f}s long. Jarvis currently publishes reels up to 90 seconds."
    elif frame_rate_fps and frame_rate_fps > 60.0:
        reason = f"{display_name} runs at {frame_rate_fps:.2f}fps, which exceeds Jarvis' Instagram safety ceiling."
    elif audio_stream and sample_rate and sample_rate not in {44100, 48000}:
        reason = f"{display_name} uses {sample_rate}Hz audio, which is outside Jarvis' Instagram-safe range."

    return {
        "meta_inspection_version": 2,
        "video_codec": video_codec,
        "pixel_format": pixel_format,
        "audio_codec": audio_codec,
        "audio_profile": audio_profile,
        "format_name": format_name,
        "duration_seconds": round(duration_seconds, 3),
        "frame_rate_fps": round(frame_rate_fps, 3),
        "video_bit_rate": video_bit_rate,
        "audio_bit_rate": audio_bit_rate,
        "width": width,
        "height": height,
        "sample_rate": sample_rate,
        "channels": channels,
        "has_audio": bool(audio_stream),
        "meta_safe_status": "needs_repair" if reason else "safe",
        "needs_meta_repair": bool(reason),
        "meta_repair_reason": reason,
    }


def _build_video_poster_bytes(video_path: str) -> bytes:
    poster_path = f"{video_path}.jpg"
    poster_cmd = [
        "ffmpeg",
        "-y",
        "-ss", "00:00:00.500",
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        poster_path,
    ]
    subprocess.run(poster_cmd, capture_output=True, timeout=10)
    if os.path.exists(poster_path):
        with open(poster_path, "rb") as pf:
            return pf.read()
    return b""


def _prepare_video_upload(filename: str, file_bytes: bytes) -> tuple[str, bytes, dict[str, Any]]:
    extension = os.path.splitext(str(filename or "").strip())[1].lower()
    if extension not in VIDEO_EXTENSIONS:
        return filename, file_bytes, {}

    source_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension or ".mp4") as source_file:
            source_file.write(file_bytes)
            source_path = source_file.name

        poster_bytes = _build_video_poster_bytes(source_path)
        probe_metadata = _probe_video_metadata(source_path, os.path.basename(filename) or "video.mp4")
        metadata = {
            "normalized_for_meta": False,
            "original_filename": filename,
            "original_extension": extension,
            "normalization_pipeline": "",
            **probe_metadata,
            "has_poster": bool(poster_bytes),
            "poster_bytes": poster_bytes,
        }
        return filename, file_bytes, metadata
    except FileNotFoundError as exc:
        raise RuntimeError("Jarvis video inspection is unavailable because ffmpeg is not installed on this server.") from exc
    finally:
        for temp_path in (source_path,):
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass


def _normalize_video_upload(filename: str, file_bytes: bytes) -> tuple[str, bytes, dict[str, Any]]:
    extension = os.path.splitext(str(filename or "").strip())[1].lower()
    if extension not in VIDEO_EXTENSIONS:
        return filename, file_bytes, {}

    source_path = ""
    output_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension or ".mp4") as source_file:
            source_file.write(file_bytes)
            source_path = source_file.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as output_file:
            output_path = output_file.name

        command = [
            "ffmpeg",
            "-y",
            "-i",
            source_path,
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            output_path,
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=240)
        if result.returncode != 0 or not os.path.exists(output_path):
            detail = (result.stderr or result.stdout or "").strip()[:300]
            raise RuntimeError(detail or "ffmpeg failed to normalize the uploaded video for Meta.")

        with open(output_path, "rb") as f:
            normalized_bytes = f.read()

        poster_bytes = _build_video_poster_bytes(output_path)
        probe_metadata = _probe_video_metadata(output_path, os.path.basename(filename) or "video.mp4")

        stem = os.path.splitext(str(filename or "").strip() or "video")[0]
        normalized_filename = f"{stem}.mp4"
        metadata = {
            "normalized_for_meta": True,
            "original_filename": filename,
            "original_extension": extension,
            "normalization_pipeline": "ffmpeg_h264_aac_faststart",
            **probe_metadata,
            "has_poster": bool(poster_bytes),
            "poster_bytes": poster_bytes,
        }
        return normalized_filename, normalized_bytes, metadata
    except FileNotFoundError as exc:
        raise RuntimeError("Jarvis video normalization is unavailable because ffmpeg is not installed on this server.") from exc
    finally:
        for temp_path in (source_path, output_path):
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass


def _next_available_filename(filename: str, existing_names: set[str]) -> str:
    cleaned = str(filename or "").strip() or "asset"
    if cleaned not in existing_names:
        return cleaned

    stem, ext = os.path.splitext(cleaned)
    counter = 2
    candidate = f"{stem}-{counter}{ext}"
    while candidate in existing_names:
        counter += 1
        candidate = f"{stem}-{counter}{ext}"
    return candidate


def _safe_prepare_video_upload(filename: str, file_bytes: bytes) -> tuple[str, bytes, dict[str, Any]]:
    try:
        return _prepare_video_upload(filename, file_bytes)
    except Exception:
        return filename, file_bytes, {}


def _safe_normalize_video_upload(filename: str, file_bytes: bytes) -> tuple[str, bytes, dict[str, Any]]:
    try:
        return _normalize_video_upload(filename, file_bytes)
    except Exception:
        return filename, file_bytes, {}


def _json_safe_metadata(value: Any) -> Any:
    if isinstance(value, bytes):
        return None
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            sanitized = _json_safe_metadata(item)
            if sanitized is not None:
                cleaned[key] = sanitized
        return cleaned
    if isinstance(value, (list, tuple, set)):
        cleaned_items = []
        for item in value:
            sanitized = _json_safe_metadata(item)
            if sanitized is not None:
                cleaned_items.append(sanitized)
        return cleaned_items
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _finalize_normalization_meta(normalization_meta: dict[str, Any] | None) -> tuple[dict[str, Any], bytes]:
    raw = dict(normalization_meta or {})
    poster_bytes = raw.pop("poster_bytes", b"")
    if not isinstance(poster_bytes, (bytes, bytearray)):
        poster_bytes = b""
    if "has_poster" not in raw:
        raw["has_poster"] = bool(poster_bytes)
    else:
        raw["has_poster"] = bool(raw.get("has_poster")) and bool(poster_bytes)
    safe = _json_safe_metadata(raw) or {}
    return safe, bytes(poster_bytes)


class BaseAssetStore:
    backend_name = "base"

    def list_assets(self, client_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def save_asset(self, client_id: str, filename: str, file_bytes: bytes) -> dict[str, Any]:
        raise NotImplementedError

    def delete_asset(self, client_id: str, filename: str) -> bool:
        raise NotImplementedError

    def delete_client_assets(self, client_id: str) -> int:
        raise NotImplementedError

    def get_asset_content(self, client_id: str, filename: str) -> tuple[bytes, str] | None:
        raise NotImplementedError

    def repair_asset_for_meta(self, client_id: str, filename: str) -> dict[str, Any]:
        raise NotImplementedError

    def asset_exists(self, client_id: str, filename: str) -> bool:
        raise NotImplementedError

    def poster_exists(self, client_id: str, filename: str) -> bool:
        raise NotImplementedError

    def public_asset_url(self, client_id: str, filename: str) -> str:
        return ""

    def public_poster_url(self, client_id: str, filename: str) -> str:
        return ""

    def preview_asset_url(self, client_id: str, asset: dict[str, Any]) -> str:
        filename = str(asset.get("filename") or "").strip()
        return self.public_asset_url(client_id, filename)

    def preview_poster_url(self, client_id: str, asset: dict[str, Any]) -> str:
        filename = str(asset.get("filename") or "").strip()
        return self.public_poster_url(client_id, filename)


class JsonAssetStore(BaseAssetStore):
    backend_name = "json"

    def _client_dir(self, client_id: str) -> str:
        return os.path.join("assets", client_id)

    def _asset_path(self, client_id: str, filename: str) -> str:
        return os.path.join(self._client_dir(client_id), filename)

    def _metadata_path(self, client_id: str, filename: str) -> str:
        return self._asset_path(client_id, filename) + JSON_METADATA_SUFFIX

    def _thumbnail_path(self, client_id: str, filename: str) -> str:
        return self._asset_path(client_id, filename) + JSON_THUMBNAIL_SUFFIX

    def _poster_path(self, client_id: str, filename: str) -> str:
        return self._asset_path(client_id, filename) + ".jpg"

    def _poster_thumbnail_path(self, client_id: str, filename: str) -> str:
        return self._poster_path(client_id, filename) + JSON_THUMBNAIL_SUFFIX

    def _write_metadata(self, client_id: str, filename: str, metadata: dict[str, Any]) -> None:
        with open(self._metadata_path(client_id, filename), "w", encoding="utf-8") as handle:
            json.dump(_json_safe_metadata(metadata) or {}, handle, ensure_ascii=False, indent=2)

    def _load_metadata(self, client_id: str, filename: str) -> dict[str, Any]:
        path = self._metadata_path(client_id, filename)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _is_sidecar_filename(self, filename: str) -> bool:
        lowered = str(filename or "").strip().lower()
        if not lowered or lowered == "queue.json" or lowered.endswith(JSON_METADATA_SUFFIX) or lowered.endswith(JSON_THUMBNAIL_SUFFIX):
            return True
        return any(lowered.endswith(f"{ext}.jpg") for ext in VIDEO_EXTENSIONS)

    def _relative_asset_url(self, client_id: str, filename: str) -> str:
        encoded_client = quote(client_id, safe="")
        encoded_filename = "/".join(quote(part, safe="") for part in str(filename or "").split("/"))
        return f"/assets/{encoded_client}/{encoded_filename}"

    def _fallback_preview_version(self, paths: list[str]) -> str:
        mtimes = [os.path.getmtime(path) for path in paths if path and os.path.exists(path)]
        if not mtimes:
            return _new_preview_version()
        return str(int(max(mtimes) * 1000))

    def _ensure_preview_artifacts(self, client_id: str, filename: str, kind: str, metadata: dict[str, Any]) -> None:
        asset_path = self._asset_path(client_id, filename)
        if kind == "image" and os.path.exists(asset_path):
            thumb_path = self._thumbnail_path(client_id, filename)
            if not os.path.exists(thumb_path):
                with open(asset_path, "rb") as handle:
                    thumb_bytes = _build_thumbnail_bytes(handle.read())
                with open(thumb_path, "wb") as handle:
                    handle.write(thumb_bytes)
        elif kind == "video" and metadata.get("has_poster"):
            poster_path = self._poster_path(client_id, filename)
            poster_thumb_path = self._poster_thumbnail_path(client_id, filename)
            if os.path.exists(poster_path) and not os.path.exists(poster_thumb_path):
                with open(poster_path, "rb") as handle:
                    thumb_bytes = _build_thumbnail_bytes(handle.read())
                with open(poster_thumb_path, "wb") as handle:
                    handle.write(thumb_bytes)

    def list_assets(self, client_id: str) -> list[dict[str, Any]]:
        client_dir = self._client_dir(client_id)
        if not os.path.exists(client_dir):
            return []

        assets = []
        for name in sorted(os.listdir(client_dir)):
            path = os.path.join(client_dir, name)
            if not os.path.isfile(path) or self._is_sidecar_filename(name):
                continue
            mime_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
            kind = detect_media_kind(name)
            has_poster = os.path.exists(self._poster_path(client_id, name)) if kind == "video" else False
            metadata = {
                **self._load_metadata(client_id, name),
                "mime_type": mime_type,
                "byte_size": os.path.getsize(path),
                "has_poster": has_poster,
            }
            if not str(metadata.get("preview_version") or "").strip():
                metadata["preview_version"] = self._fallback_preview_version(
                    [
                        path,
                        self._poster_path(client_id, name),
                        self._thumbnail_path(client_id, name),
                        self._poster_thumbnail_path(client_id, name),
                    ]
                )
            self._ensure_preview_artifacts(client_id, name, kind, metadata)
            assets.append(
                {
                    "filename": name,
                    "kind": kind,
                    "storage_path": path.replace("\\", "/"),
                    "metadata": metadata,
                }
            )
        return assets

    def save_asset(self, client_id: str, filename: str, file_bytes: bytes) -> dict[str, Any]:
        client_dir = self._client_dir(client_id)
        os.makedirs(client_dir, exist_ok=True)
        kind = detect_media_kind(filename)
        if kind == "image":
            filename, file_bytes, normalization_meta = _safe_normalize_image_upload(filename, file_bytes)
        else:
            filename, file_bytes, normalization_meta = _safe_prepare_video_upload(filename, file_bytes)
        existing_names = {
            name
            for name in os.listdir(client_dir)
            if os.path.isfile(os.path.join(client_dir, name)) and not self._is_sidecar_filename(name)
        }
        filename = _next_available_filename(filename, existing_names)
        path = self._asset_path(client_id, filename)
        with open(path, "wb") as f:
            f.write(file_bytes)

        normalization_meta, poster_bytes = _finalize_normalization_meta(normalization_meta)
        normalization_meta["preview_version"] = _new_preview_version()
        if poster_bytes:
            with open(self._poster_path(client_id, filename), "wb") as pf:
                pf.write(poster_bytes)
            with open(self._poster_thumbnail_path(client_id, filename), "wb") as pf:
                pf.write(_build_thumbnail_bytes(poster_bytes))
        elif os.path.exists(self._poster_thumbnail_path(client_id, filename)):
            os.remove(self._poster_thumbnail_path(client_id, filename))
        if kind == "image":
            with open(self._thumbnail_path(client_id, filename), "wb") as tf:
                tf.write(_build_thumbnail_bytes(file_bytes))
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        metadata = {
            "mime_type": mime_type,
            "byte_size": len(file_bytes),
            **normalization_meta,
        }
        self._write_metadata(client_id, filename, metadata)

        return {
            "filename": filename,
            "kind": detect_media_kind(filename),
            "storage_path": path.replace("\\", "/"),
            "metadata": metadata,
        }

    def delete_asset(self, client_id: str, filename: str) -> bool:
        path = self._asset_path(client_id, filename)
        if not os.path.exists(path):
            return False
        os.remove(path)
        poster_path = self._poster_path(client_id, filename)
        if os.path.exists(poster_path):
            os.remove(poster_path)
        for sidecar in (
            self._thumbnail_path(client_id, filename),
            self._poster_thumbnail_path(client_id, filename),
            self._metadata_path(client_id, filename),
        ):
            if os.path.exists(sidecar):
                os.remove(sidecar)
        return True

    def delete_client_assets(self, client_id: str) -> int:
        assets = self.list_assets(client_id)
        client_dir = self._client_dir(client_id)
        if os.path.exists(client_dir):
            shutil.rmtree(client_dir, ignore_errors=True)
        return len(assets)

    def get_asset_content(self, client_id: str, filename: str) -> tuple[bytes, str] | None:
        path = self._asset_path(client_id, filename)
        if not os.path.exists(path):
            return None
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            return f.read(), mime_type

    def asset_exists(self, client_id: str, filename: str) -> bool:
        return os.path.exists(self._asset_path(client_id, filename))

    def poster_exists(self, client_id: str, filename: str) -> bool:
        return os.path.exists(self._poster_path(client_id, filename))

    def public_asset_url(self, client_id: str, filename: str) -> str:
        return self._relative_asset_url(client_id, filename)

    def public_poster_url(self, client_id: str, filename: str) -> str:
        if not self.poster_exists(client_id, filename):
            return ""
        return self._relative_asset_url(client_id, f"{filename}.jpg")

    def preview_asset_url(self, client_id: str, asset: dict[str, Any]) -> str:
        filename = str(asset.get("filename") or "").strip()
        if not filename:
            return ""
        return self._relative_asset_url(client_id, f"{filename}{JSON_THUMBNAIL_SUFFIX}")

    def preview_poster_url(self, client_id: str, asset: dict[str, Any]) -> str:
        filename = str(asset.get("filename") or "").strip()
        metadata = asset.get("metadata") or {}
        if not filename or not metadata.get("has_poster"):
            return ""
        return self._relative_asset_url(client_id, f"{filename}.jpg{JSON_THUMBNAIL_SUFFIX}")

    def repair_asset_for_meta(self, client_id: str, filename: str) -> dict[str, Any]:
        current = self.get_asset_content(client_id, filename)
        if not current:
            raise FileNotFoundError(f"Asset '{filename}' was not found for client '{client_id}'.")
        file_bytes, _mime_type = current
        kind = detect_media_kind(filename)
        if kind == "video":
            _normalized_name, normalized_bytes, normalization_meta = _normalize_video_upload(filename, file_bytes)
        elif kind == "image":
            _normalized_name, normalized_bytes, normalization_meta = _normalize_image_upload(filename, file_bytes)
        else:
            raise RuntimeError("Only image or video assets can be repaired for Meta.")
        path = self._asset_path(client_id, filename)
        with open(path, "wb") as f:
            f.write(normalized_bytes)
        normalization_meta, poster_bytes = _finalize_normalization_meta(normalization_meta)
        normalization_meta["preview_version"] = _new_preview_version()
        if poster_bytes:
            with open(self._poster_path(client_id, filename), "wb") as pf:
                pf.write(poster_bytes)
            with open(self._poster_thumbnail_path(client_id, filename), "wb") as pf:
                pf.write(_build_thumbnail_bytes(poster_bytes))
        elif os.path.exists(self._poster_path(client_id, filename)):
            os.remove(self._poster_path(client_id, filename))
        if kind == "image":
            with open(self._thumbnail_path(client_id, filename), "wb") as tf:
                tf.write(_build_thumbnail_bytes(normalized_bytes))
        elif os.path.exists(self._thumbnail_path(client_id, filename)):
            os.remove(self._thumbnail_path(client_id, filename))
        if not poster_bytes and os.path.exists(self._poster_thumbnail_path(client_id, filename)):
            os.remove(self._poster_thumbnail_path(client_id, filename))
        mime_type = "video/mp4" if kind == "video" else "image/jpeg"
        metadata = {
            "mime_type": mime_type,
            "byte_size": len(normalized_bytes),
            **normalization_meta,
            "repaired_for_meta": True,
        }
        self._write_metadata(client_id, filename, metadata)
            
        return {
            "filename": filename,
            "kind": detect_media_kind(filename),
            "storage_path": path.replace("\\", "/"),
            "metadata": metadata,
        }


class SupabaseAssetStore(BaseAssetStore):
    backend_name = "supabase"

    def __init__(self):
        self.client = get_supabase_service_client()
        self.bucket = DEFAULT_ASSET_BUCKET
        self.project_url = str(os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
        self.service_role_key = str(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        self.storage_headers = {
            "Authorization": f"Bearer {self.service_role_key}",
            "apikey": self.service_role_key,
        }

    def _list_rows(self, client_id: str, filename: str | None = None) -> list[dict[str, Any]]:
        query = self.client.table("assets").select("*").eq("client_id", client_id)
        if filename:
            query = query.eq("original_filename", filename)
        response = query.order("created_at").execute()
        return response.data or []

    def _row_to_asset(self, row: dict[str, Any]) -> dict[str, Any]:
        metadata = row.get("metadata") or {}
        mime_type = str(metadata.get("mime_type") or mimetypes.guess_type(str(row.get("original_filename") or ""))[0] or "application/octet-stream")
        return {
            "asset_id": row.get("asset_id"),
            "filename": str(row.get("original_filename") or "").strip(),
            "kind": str(row.get("media_kind") or detect_media_kind(str(row.get("original_filename") or ""))).strip().lower(),
            "storage_path": str(row.get("storage_path") or "").strip(),
            "created_at": row.get("created_at"),
            "metadata": {
                **metadata,
                "mime_type": mime_type,
            },
        }

    def list_assets(self, client_id: str) -> list[dict[str, Any]]:
        return [self._row_to_asset(row) for row in self._list_rows(client_id)]

    def save_asset(self, client_id: str, filename: str, file_bytes: bytes) -> dict[str, Any]:
        kind = detect_media_kind(filename)
        if kind == "image":
            filename, file_bytes, normalization_meta = _safe_normalize_image_upload(filename, file_bytes)
        else:
            filename, file_bytes, normalization_meta = _safe_prepare_video_upload(filename, file_bytes)
        normalization_meta, poster_bytes = _finalize_normalization_meta(normalization_meta)
        existing_names = {
            str(row.get("original_filename") or "").strip()
            for row in self._list_rows(client_id)
            if str(row.get("original_filename") or "").strip()
        }
        filename = _next_available_filename(filename, existing_names)
        storage_path = f"{client_id}/{filename}"
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        self._upload_bytes(storage_path, filename, file_bytes, mime_type)
        if poster_bytes:
            self._upload_bytes(storage_path + ".jpg", filename + ".jpg", poster_bytes, "image/jpeg")
        normalization_meta["preview_version"] = _new_preview_version()
        row = {
            "client_id": client_id,
            "storage_bucket": self.bucket,
            "storage_path": storage_path,
            "original_filename": filename,
            "media_kind": "video" if os.path.splitext(filename.lower())[1] in VIDEO_EXTENSIONS else "image",
            "metadata": {
                "mime_type": mime_type,
                "byte_size": len(file_bytes),
                **normalization_meta,
            },
        }
        self.client.table("assets").insert(row).execute()
        return self._row_to_asset(row)

    def delete_asset(self, client_id: str, filename: str) -> bool:
        rows = self._list_rows(client_id, filename)
        if not rows:
            return False
        paths = [str(row.get("storage_path") or "").strip() for row in rows if str(row.get("storage_path") or "").strip()]
        for row in rows:
            metadata = row.get("metadata") or {}
            storage_path = str(row.get("storage_path") or "").strip()
            if storage_path and metadata.get("has_poster"):
                paths.append(storage_path + ".jpg")
        if paths:
            self._remove_paths(paths)
        self.client.table("assets").delete().eq("client_id", client_id).eq("original_filename", filename).execute()
        return True

    def delete_client_assets(self, client_id: str) -> int:
        rows = self._list_rows(client_id)
        count = len(rows)
        paths = [str(row.get("storage_path") or "").strip() for row in rows if str(row.get("storage_path") or "").strip()]
        for row in rows:
            metadata = row.get("metadata") or {}
            storage_path = str(row.get("storage_path") or "").strip()
            if storage_path and metadata.get("has_poster"):
                paths.append(storage_path + ".jpg")
        if paths:
            self._remove_paths(paths)
        if count:
            self.client.table("assets").delete().eq("client_id", client_id).execute()
        return count

    def get_asset_content(self, client_id: str, filename: str) -> tuple[bytes, str] | None:
        rows = self._list_rows(client_id, filename)
        if not rows:
            return None
        row = rows[-1]
        storage_path = str(row.get("storage_path") or "").strip()
        if not storage_path:
            return None
        content = self._download_bytes(storage_path)
        mime_type = str((row.get("metadata") or {}).get("mime_type") or mimetypes.guess_type(filename)[0] or "application/octet-stream")
        return content, mime_type

    def asset_exists(self, client_id: str, filename: str) -> bool:
        rows = self._list_rows(client_id, filename)
        if not rows:
            return False
        storage_path = str(rows[-1].get("storage_path") or "").strip()
        if not storage_path:
            return False
        response = requests.head(
            self._storage_url(storage_path),
            headers=self.storage_headers,
            timeout=(10, DEFAULT_STORAGE_READ_TIMEOUT),
        )
        return response.status_code < 400

    def poster_exists(self, client_id: str, filename: str) -> bool:
        rows = self._list_rows(client_id, filename)
        if not rows:
            return False
        row = rows[-1]
        metadata = row.get("metadata") or {}
        if not metadata.get("has_poster"):
            return False
        storage_path = str(row.get("storage_path") or "").strip()
        if not storage_path:
            return False
        response = requests.head(
            self._storage_url(storage_path + ".jpg"),
            headers=self.storage_headers,
            timeout=(10, DEFAULT_STORAGE_READ_TIMEOUT),
        )
        return response.status_code < 400

    def public_asset_url(self, client_id: str, filename: str) -> str:
        rows = self._list_rows(client_id, filename)
        if not rows:
            return ""
        storage_path = str(rows[-1].get("storage_path") or "").strip()
        if not storage_path:
            return ""
        return f"{self.project_url}/storage/v1/object/public/{self.bucket}/{quote(storage_path, safe='/')}"

    def public_poster_url(self, client_id: str, filename: str) -> str:
        rows = self._list_rows(client_id, filename)
        if not rows:
            return ""
        row = rows[-1]
        metadata = row.get("metadata") or {}
        if not metadata.get("has_poster"):
            return ""
        storage_path = str(row.get("storage_path") or "").strip()
        if not storage_path:
            return ""
        return f"{self.project_url}/storage/v1/object/public/{self.bucket}/{quote(storage_path + '.jpg', safe='/')}"

    def preview_asset_url(self, client_id: str, asset: dict[str, Any]) -> str:
        storage_path = str(asset.get("storage_path") or "").strip()
        if not storage_path:
            return ""
        return (
            f"{self.project_url}/storage/v1/render/image/public/"
            f"{self.bucket}/{quote(storage_path, safe='/')}?width={VAULT_PREVIEW_WIDTH}&height={VAULT_PREVIEW_HEIGHT}"
            f"&resize=cover&quality={VAULT_PREVIEW_QUALITY}"
        )

    def preview_poster_url(self, client_id: str, asset: dict[str, Any]) -> str:
        metadata = asset.get("metadata") or {}
        if not metadata.get("has_poster"):
            return ""
        storage_path = str(asset.get("storage_path") or "").strip()
        if not storage_path:
            return ""
        return (
            f"{self.project_url}/storage/v1/render/image/public/"
            f"{self.bucket}/{quote(storage_path + '.jpg', safe='/')}?width={VAULT_PREVIEW_WIDTH}&height={VAULT_PREVIEW_HEIGHT}"
            f"&resize=cover&quality={VAULT_PREVIEW_QUALITY}"
        )

    def repair_asset_for_meta(self, client_id: str, filename: str) -> dict[str, Any]:
        rows = self._list_rows(client_id, filename)
        if not rows:
            raise FileNotFoundError(f"Asset '{filename}' was not found for client '{client_id}'.")
        row = rows[-1]
        storage_path = str(row.get("storage_path") or "").strip()
        if not storage_path:
            raise RuntimeError("The asset is missing a storage path.")
        current = self.get_asset_content(client_id, filename)
        if not current:
            raise FileNotFoundError(f"Asset '{filename}' could not be downloaded for repair.")
        file_bytes, _mime_type = current
        kind = detect_media_kind(filename)
        if kind == "video":
            _normalized_name, normalized_bytes, normalization_meta = _normalize_video_upload(filename, file_bytes)
        elif kind == "image":
            _normalized_name, normalized_bytes, normalization_meta = _normalize_image_upload(filename, file_bytes)
        else:
            raise RuntimeError("Only image or video assets can be repaired for Meta.")
        normalization_meta, poster_bytes = _finalize_normalization_meta(normalization_meta)
        remove_paths = [storage_path]
        if (row.get("metadata") or {}).get("has_poster"):
            remove_paths.append(storage_path + ".jpg")
        self._remove_paths(remove_paths)
        mime_type = "video/mp4" if kind == "video" else "image/jpeg"
        self._upload_bytes(storage_path, filename, normalized_bytes, mime_type)
        if poster_bytes:
            self._upload_bytes(storage_path + ".jpg", filename + ".jpg", poster_bytes, "image/jpeg")
        normalization_meta["preview_version"] = _new_preview_version()
        metadata = {
            **(row.get("metadata") or {}),
            "mime_type": mime_type,
            "byte_size": len(normalized_bytes),
            **normalization_meta,
            "repaired_for_meta": True,
        }
        self.client.table("assets").update({"metadata": metadata}).eq("client_id", client_id).eq("original_filename", filename).execute()
        updated_row = dict(row)
        updated_row["metadata"] = metadata
        return self._row_to_asset(updated_row)

    def _storage_url(self, storage_path: str) -> str:
        return f"{self.project_url}/storage/v1/object/{self.bucket}/{quote(storage_path, safe='/')}"

    def _upload_bytes(self, storage_path: str, filename: str, file_bytes: bytes, mime_type: str) -> None:
        # CRITICAL FIX for Instagram API graph ingestion:
        # We must push raw bytes and force the Content-Type header. If we use multipart `files=`, 
        # Supabase defaults to application/octet-stream, which causes Instagram Graph API to fail with 
        # "Only photo or video can be accepted as media type" because it strictly validates headers.
        headers = {
            **self.storage_headers, 
            "x-upsert": "true",
            "Content-Type": mime_type or "application/octet-stream",
            "Content-Disposition": f'inline; filename="{quote(os.path.basename(filename), safe="")}"'
        }
        response = requests.post(
            self._storage_url(storage_path),
            headers=headers,
            data=file_bytes,
            timeout=(20, DEFAULT_STORAGE_UPLOAD_TIMEOUT),
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase Storage upload failed: {response.status_code} {response.text[:300]}")

    def _download_bytes(self, storage_path: str) -> bytes:
        response = requests.get(
            self._storage_url(storage_path),
            headers=self.storage_headers,
            timeout=(10, DEFAULT_STORAGE_READ_TIMEOUT),
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase Storage download failed: {response.status_code} {response.text[:300]}")
        return response.content

    def _remove_paths(self, paths: list[str]) -> None:
        response = requests.delete(
            f"{self.project_url}/storage/v1/object/{self.bucket}",
            headers={**self.storage_headers, "Content-Type": "application/json"},
            json={"prefixes": paths},
            timeout=(10, DEFAULT_STORAGE_READ_TIMEOUT),
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase Storage delete failed: {response.status_code} {response.text[:300]}")


_store: BaseAssetStore | None = None


def get_asset_store() -> BaseAssetStore:
    global _store
    if _store is not None:
        return _store
    mode = get_data_backend_name()
    if mode == "supabase":
        _store = SupabaseAssetStore()
    else:
        _store = JsonAssetStore()
    return _store


def list_client_assets(client_id: str) -> list[dict[str, Any]]:
    return get_asset_store().list_assets(client_id)


def get_client_asset_record(client_id: str, filename: str) -> dict[str, Any] | None:
    target = str(filename or "").strip()
    if not target:
        return None
    for asset in list_client_assets(client_id):
        if str(asset.get("filename") or "").strip() == target:
            return asset
    return None


def count_client_assets(client_id: str) -> int:
    return len(list_client_assets(client_id))


def save_uploaded_asset(client_id: str, filename: str, file_bytes: bytes) -> dict[str, Any]:
    client_id = validate_client_id(client_id)
    filename = validate_filename(filename)
    return get_asset_store().save_asset(client_id, filename, file_bytes)


def delete_client_asset(client_id: str, filename: str) -> bool:
    client_id = validate_client_id(client_id)
    filename = validate_filename(filename)
    return get_asset_store().delete_asset(client_id, filename)


def delete_all_client_assets(client_id: str) -> int:
    return get_asset_store().delete_client_assets(client_id)


def get_asset_content(client_id: str, filename: str) -> tuple[bytes, str] | None:
    return get_asset_store().get_asset_content(client_id, filename)


def repair_client_asset_for_meta(client_id: str, filename: str) -> dict[str, Any]:
    client_id = validate_client_id(client_id)
    filename = validate_filename(filename)
    return get_asset_store().repair_asset_for_meta(client_id, filename)


def asset_storage_exists(client_id: str, filename: str) -> bool:
    return get_asset_store().asset_exists(client_id, filename)


def poster_storage_exists(client_id: str, filename: str) -> bool:
    return get_asset_store().poster_exists(client_id, filename)
