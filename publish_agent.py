import os
import time
import json
import subprocess
import tempfile
import mimetypes
import requests
import logging
from typing import Dict, Any
from urllib.parse import quote, urlparse
from dotenv import load_dotenv
from client_store import get_client_store
from asset_store import get_asset_content, get_client_asset_record, repair_client_asset_for_meta
from queue_store import normalize_hashtag_list

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MetaPublisher")

class PublishAgent:
    """
    Agent #2: The Python Execution Layer for Meta Graph API.
    """
    
    def __init__(self, api_version: str = "v19.0"):
        self.api_version = api_version
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        self.ig_poll_attempts_image = 6
        self.ig_poll_attempts_video = 24
        self.ig_poll_interval_image = 3
        self.ig_poll_interval_video = 5

    def _poll_instagram_container(self, creation_id: str, token: str) -> tuple[dict[str, Any], str]:
        status_url = f"{self.base_url}/{creation_id}"
        field_candidates = [
            "status_code,status",
            "status_code",
        ]
        last_payload: dict[str, Any] = {}
        last_fields = field_candidates[-1]
        for fields in field_candidates:
            last_fields = fields
            resp = requests.get(status_url, params={"fields": fields, "access_token": token}, timeout=30)
            payload = resp.json()
            if "error" in payload and "Tried accessing nonexisting field" in str(payload.get("error", {}).get("message") or ""):
                logger.info(f"Instagram poll fields '{fields}' unsupported for container {creation_id}; trying fallback.")
                last_payload = payload
                continue
            return payload, fields
        return last_payload, last_fields

    def _instagram_media_preflight(self, image_paths: list[str], video_paths: list[str]) -> str:
        if video_paths:
            for path in video_paths:
                compatibility_issue = self._inspect_video_compatibility(path)
                if compatibility_issue:
                    return compatibility_issue

        for path in image_paths:
            compatibility_issue = self._inspect_image_compatibility(path)
            if compatibility_issue:
                return compatibility_issue
        return ""

    def _parse_managed_asset_path(self, media_path: str) -> tuple[str, str] | None:
        normalized = str(media_path or "").replace("\\", "/").lstrip("/")
        if not normalized.startswith("assets/"):
            return None
        relative = normalized[len("assets/"):]
        parts = relative.split("/")
        if len(parts) < 2:
            return None
        client_id = parts[0]
        filename = "/".join(parts[1:])
        if not client_id or not filename:
            return None
        return client_id, filename

    def prepare_managed_media(self, image_paths: list[str], video_paths: list[str], instagram_enabled: bool = True) -> dict[str, Any]:
        repaired: list[str] = []
        if not instagram_enabled:
            return {"status": "success", "repaired": repaired}

        for path in image_paths:
            managed = self._parse_managed_asset_path(path)
            if not managed:
                continue
            client_id, filename = managed
            asset = get_client_asset_record(client_id, filename) or {}
            metadata = asset.get("metadata") or {}
            needs_repair = bool(metadata.get("needs_meta_repair"))
            if not needs_repair and not metadata.get("image_inspection_version"):
                needs_repair = True
            if not needs_repair:
                continue
            try:
                repair_client_asset_for_meta(client_id, filename)
                repaired.append(filename)
            except Exception as exc:
                return {
                    "status": "error",
                    "reason": f"Jarvis could not repair {filename} for Instagram delivery: {exc}",
                    "repaired": repaired,
                }

        for path in video_paths:
            managed = self._parse_managed_asset_path(path)
            if not managed:
                continue
            client_id, filename = managed
            asset = get_client_asset_record(client_id, filename) or {}
            metadata = asset.get("metadata") or {}
            needs_repair = bool(metadata.get("needs_meta_repair"))
            if not needs_repair:
                needs_repair = bool(self._inspect_video_compatibility(path))
            if not needs_repair:
                continue
            try:
                repair_client_asset_for_meta(client_id, filename)
                repaired.append(filename)
            except Exception as exc:
                return {
                    "status": "error",
                    "reason": f"Jarvis could not repair {filename} for Instagram delivery: {exc}",
                    "repaired": repaired,
                }

        return {"status": "success", "repaired": repaired}

    def _inspect_image_compatibility(self, path: str) -> str:
        resolved_path = str(path or "").strip()
        if not resolved_path:
            return ""
        display_name = os.path.basename(resolved_path.replace("\\", "/")) or "image.jpg"
        managed = self._parse_managed_asset_path(resolved_path)
        if managed:
            client_id, filename = managed
            asset = get_client_asset_record(client_id, filename) or {}
            metadata = asset.get("metadata") or {}
            if metadata:
                if not bool(metadata.get("needs_meta_repair")) and str(metadata.get("meta_safe_status") or "").strip().lower() == "safe":
                    return ""
                reason = str(metadata.get("meta_repair_reason") or "").strip()
                if reason:
                    return f"Instagram publish blocked before delivery: {reason}"

        extension = os.path.splitext(display_name.lower())[1]
        if extension not in {".jpg", ".jpeg"}:
            return (
                "Instagram publish blocked before delivery: "
                f"{display_name} must be converted to JPG/JPEG before Jarvis can post this draft."
            )
        return ""

    def _build_public_media_urls(self, image_paths: list[str], video_paths: list[str]) -> tuple[list[str], list[str], str]:
        preferred_base = str(
            os.getenv("PUBLISH_MEDIA_BASE_URL")
            or os.getenv("PUBLIC_ASSET_BASE_URL")
            or ""
        ).strip().rstrip("/")
        if preferred_base:
            image_urls = [f"{preferred_base}/{quote(path.lstrip('/'), safe='/')}" for path in image_paths]
            video_urls = [f"{preferred_base}/{quote(path.lstrip('/'), safe='/')}" for path in video_paths]
            return image_urls, video_urls, preferred_base

        data_backend = os.getenv("JARVIS_DATA_BACKEND", "json").strip().lower()
        if data_backend == "supabase":
            bucket = str(os.getenv("SUPABASE_ASSET_BUCKET") or "client-assets").strip()
            if bucket:
                try:
                    from client_store import get_supabase_service_client
                    client = get_supabase_service_client()
                    
                    def _supabase_path(p: str) -> str:
                        cp = p.replace("\\", "/").lstrip("/")
                        if cp.startswith("assets/"): cp = cp[7:]
                        
                        # CRITICAL FIX for Instagram API "media type" rejection:
                        # Instagram's Graph API frequently rejects Supabase signed URLs because it 
                        # gets confused by the ?token= query parameters and strips the file extensions.
                        # To resolve this, we ensure the bucket is completely public and return the native 
                        # clean URL directly from the Supabase CDN.
                        # Note: The database MUST be configured with public: true for this bucket.
                            
                        supabase_url = str(os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
                        base_public_url = f"{supabase_url}/storage/v1/object/public/{bucket}"
                        return f"{base_public_url}/{quote(cp, safe='/')}"

                    image_urls = [_supabase_path(p) for p in image_paths]
                    video_urls = [_supabase_path(p) for p in video_paths]
                    return image_urls, video_urls, str(os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
                except Exception as e:
                    logger.error(f"Failed to generate Supabase signed URLs: {e}")

        tunnel = os.getenv("WEBHOOK_PROXY_URL", "").strip().rstrip("/")
        if not tunnel:
            return [], [], ""
        image_urls = [f"{tunnel}/{quote(path.lstrip('/'), safe='/')}" for path in image_paths]
        video_urls = [f"{tunnel}/{quote(path.lstrip('/'), safe='/')}" for path in video_paths]
        return image_urls, video_urls, tunnel

    def _instagram_image_host_guard(self, image_urls: list[str], video_urls: list[str]) -> str:
        if video_urls or not image_urls:
            return ""

        preferred_base = str(
            os.getenv("PUBLISH_MEDIA_BASE_URL")
            or os.getenv("PUBLIC_ASSET_BASE_URL")
            or ""
        ).strip().rstrip("/")
        if preferred_base:
            return ""

        current_url = str((image_urls or [""])[0] or "").strip()
        current_host = (urlparse(current_url).netloc or "").strip().lower()
        if not current_host:
            return ""

        if "trycloudflare.com" in current_host or current_host.endswith("supabase.co"):
            return (
                f"Instagram image publishing is blocked on the current temporary media host ({current_host}). "
                "Facebook image publishing can still proceed. "
                "For the demo environment, use a reel/video for Instagram. "
                "For full Instagram image reliability later, move media delivery to a stable first-party HTTPS domain "
                "and set PUBLISH_MEDIA_BASE_URL to that host."
            )
        return ""

    def _read_media_bytes(self, media_path: str) -> tuple[bytes, str] | None:
        resolved_path = str(media_path or "").strip()
        if not resolved_path:
            return None

        managed = self._parse_managed_asset_path(resolved_path)
        if managed:
            client_id, filename = managed
            asset = get_asset_content(client_id, filename)
            if asset:
                return asset

        if os.path.exists(resolved_path):
            mime_type = mimetypes.guess_type(resolved_path)[0] or "application/octet-stream"
            with open(resolved_path, "rb") as handle:
                return handle.read(), mime_type

        candidate = os.path.join(os.getcwd(), resolved_path)
        if os.path.exists(candidate):
            mime_type = mimetypes.guess_type(candidate)[0] or "application/octet-stream"
            with open(candidate, "rb") as handle:
                return handle.read(), mime_type

        return None

    def _mirror_media_to_catbox(self, media_path: str, fallback_suffix: str) -> str:
        media = self._read_media_bytes(media_path)
        if not media:
            raise RuntimeError("Jarvis could not load the media bytes for Instagram mirroring.")
        content, _mime_type = media
        suffix = os.path.splitext(str(media_path or "").replace("\\", "/"))[1] or fallback_suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(content)
            temp_path = handle.name
        try:
            with open(temp_path, "rb") as upload_handle:
                response = requests.post(
                    "https://catbox.moe/user/api.php",
                    data={"reqtype": "fileupload"},
                    files={"fileToUpload": upload_handle},
                    timeout=120,
                )
            if response.status_code >= 400:
                raise RuntimeError(f"Catbox upload failed with HTTP {response.status_code}.")
            mirrored_url = str(response.text or "").strip()
            if not mirrored_url.startswith("https://"):
                raise RuntimeError(f"Catbox upload returned an invalid URL: {mirrored_url[:120]}")
            return mirrored_url
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    def _mirror_instagram_image_to_catbox(self, media_path: str) -> str:
        return self._mirror_media_to_catbox(media_path, ".jpg")

    def _mirror_instagram_video_to_catbox(self, media_path: str) -> str:
        return self._mirror_media_to_catbox(media_path, ".mp4")

    def _prepare_instagram_image_urls(self, image_paths: list[str], image_urls: list[str], current_host: str) -> tuple[list[str], str]:
        if not image_paths or not image_urls:
            return image_urls, ""

        preferred_base = str(
            os.getenv("PUBLISH_MEDIA_BASE_URL")
            or os.getenv("PUBLIC_ASSET_BASE_URL")
            or ""
        ).strip().rstrip("/")
        if preferred_base:
            return image_urls, ""

        normalized_host = str(current_host or "").strip().lower()
        mirror_mode = str(os.getenv("INSTAGRAM_IMAGE_MIRROR_MODE") or "auto").strip().lower()
        should_mirror = False
        if mirror_mode == "catbox":
            should_mirror = True
        elif mirror_mode == "auto":
            should_mirror = ("trycloudflare.com" in normalized_host) or normalized_host.endswith("supabase.co")

        if not should_mirror:
            return image_urls, ""

        try:
            mirrored_urls = [self._mirror_instagram_image_to_catbox(path) for path in image_paths]
            logger.info(f"Mirrored Instagram image assets away from host {current_host} using Catbox.")
            return mirrored_urls, ""
        except Exception as exc:
            return image_urls, (
                f"Instagram image publishing is blocked on the current temporary media host ({current_host}), "
                f"and Jarvis could not mirror the image to the demo fallback host: {exc}"
            )

    def _prepare_instagram_video_urls(self, video_paths: list[str], video_urls: list[str], current_host: str) -> tuple[list[str], str]:
        if not video_paths or not video_urls:
            return video_urls, ""

        preferred_base = str(
            os.getenv("PUBLISH_MEDIA_BASE_URL")
            or os.getenv("PUBLIC_ASSET_BASE_URL")
            or ""
        ).strip().rstrip("/")
        if preferred_base:
            return video_urls, ""

        normalized_host = str(current_host or "").strip().lower()
        mirror_mode = str(os.getenv("INSTAGRAM_VIDEO_MIRROR_MODE") or "auto").strip().lower()
        should_mirror = False
        if mirror_mode == "catbox":
            should_mirror = True
        elif mirror_mode == "auto":
            should_mirror = ("trycloudflare.com" in normalized_host) or normalized_host.endswith("supabase.co")

        if not should_mirror:
            return video_urls, ""

        try:
            mirrored_urls = [self._mirror_instagram_video_to_catbox(path) for path in video_paths]
            logger.info(f"Mirrored Instagram video assets away from host {current_host} using Catbox.")
            return mirrored_urls, ""
        except Exception as exc:
            return video_urls, (
                f"Instagram reel publishing failed on the current temporary media host ({current_host}), "
                f"and Jarvis could not mirror the video to the demo fallback host: {exc}"
            )

    def _format_instagram_fetch_error(self, raw_error: dict[str, Any] | None, media_urls: list[str]) -> str:
        raw_error = raw_error or {}
        default_message = str(raw_error.get("message") or "Instagram could not fetch the media from the provided URL.").strip()
        subcode = str(raw_error.get("error_subcode") or "").strip()
        user_message = str(raw_error.get("error_user_msg") or "").strip()
        current_url = str((media_urls or [""])[0] or "").strip()
        current_host = urlparse(current_url).netloc or "unknown-host"

        if subcode == "2207052":
            detail = (
                f"Instagram could not fetch the media from the current delivery host ({current_host}). "
                "The draft/media payload itself is valid, but this host is not meeting Meta's fetch requirements. "
                "Move media delivery to a stable public domain and set PUBLISH_MEDIA_BASE_URL to that host before retrying."
            )
            if user_message:
                detail += f" Meta says: {user_message}"
            return detail

        if user_message:
            return f"{default_message} Meta says: {user_message}"
        return default_message

    def _public_media_preflight(self, image_paths: list[str], video_paths: list[str]) -> str:
        image_urls, video_urls, tunnel = self._build_public_media_urls(image_paths, video_paths)
        if not tunnel:
            return "Jarvis cannot publish because WEBHOOK_PROXY_URL (or Supabase URL) is not configured for external media delivery."
        if "localhost" in tunnel or "127.0.0.1" in tunnel:
            return f"Jarvis cannot publish because the host points to a local address ({tunnel}). Meta cannot fetch media from localhost."
        if not tunnel.lower().startswith("https://"):
            return f"Jarvis cannot publish because the host must be HTTPS for Meta media delivery ({tunnel})."
        if "trycloudflare.com" in tunnel.lower() and "supabase.co" not in tunnel.lower():
            logger.warning(f"Media URL uses trycloudflare ({tunnel}), which blocks Instagram crawlers with HTML interstitial pages.")

        is_video_probe = bool(video_urls)
        sample_urls = (video_urls or image_urls)[:1]
        for url in sample_urls:
            try:
                # Supabase and some CDNs reject bare HEAD requests with 400 Bad Request.
                response = requests.get(url, stream=True, timeout=10, allow_redirects=True)
            except Exception as exc:
                return f"Jarvis cannot publish because the public media host is unreachable: {exc}"
            
            status = response.status_code
            content_type = str(response.headers.get("content-type") or "").lower()
            content_length = str(response.headers.get("content-length") or "").strip()
            response.close()
            
            if status >= 400:
                return f"Jarvis cannot publish because the public media host returned HTTP {status} for {url}."
            if not content_length.isdigit() or int(content_length) <= 0:
                return f"Jarvis cannot publish because the public media URL did not return a valid content length for {url}."
            if is_video_probe and not content_type.startswith("video/"):
                return f"Jarvis cannot publish because the public video URL did not return a video content type ({content_type or 'unknown'})."
            if not is_video_probe and not content_type.startswith("image/"):
                return f"Jarvis cannot publish because the public image URL did not return an image content type ({content_type or 'unknown'})."
            if is_video_probe:
                if str(response.headers.get("accept-ranges") or "").lower() != "bytes":
                    return f"Jarvis cannot publish because the public video URL did not advertise byte-range support for {url}."
                try:
                    range_probe = requests.get(
                        url,
                        headers={"Range": "bytes=0-1023"},
                        timeout=15,
                        allow_redirects=True,
                    )
                except Exception as exc:
                    return f"Jarvis cannot publish because the public video URL failed a byte-range probe: {exc}"
                if range_probe.status_code != 206:
                    return f"Jarvis cannot publish because the public video URL did not honor byte-range requests (HTTP {range_probe.status_code}) for {url}."
                content_range = str(range_probe.headers.get("content-range") or "").lower()
                if not content_range.startswith("bytes 0-"):
                    return f"Jarvis cannot publish because the public video URL returned an invalid Content-Range header for {url}."
        return ""

    def preflight_media(self, image_paths: list[str], video_paths: list[str], instagram_enabled: bool = True) -> dict:
        instagram_error = self._instagram_media_preflight(image_paths, video_paths) if instagram_enabled else ""
        transport_error = self._public_media_preflight(image_paths, video_paths)
        return {
            "ok": not bool(instagram_error or transport_error),
            "instagram_error": instagram_error,
            "transport_error": transport_error,
        }

    def _inspect_video_compatibility(self, path: str) -> str:
        resolved_path = str(path or "").strip()
        if not resolved_path:
            return ""
        display_name = os.path.basename(resolved_path.replace("\\", "/")) or "video.mp4"
        managed = self._parse_managed_asset_path(resolved_path)
        if managed:
            client_id, filename = managed
            asset = get_client_asset_record(client_id, filename) or {}
            metadata = asset.get("metadata") or {}
            if metadata:
                inspection_version = int(metadata.get("meta_inspection_version") or 0)
                if inspection_version >= 2 and not bool(metadata.get("needs_meta_repair")) and str(metadata.get("meta_safe_status") or "").strip().lower() == "safe":
                    return ""
                reason = str(metadata.get("meta_repair_reason") or "").strip()
                if reason:
                    if "audio" in reason.lower():
                        reason = f"{reason} Re-export it with AAC-LC audio before Jarvis posts it."
                    return (
                        "Instagram publish blocked before delivery: "
                        f"{reason}"
                    )
        temp_path = ""
        if not os.path.exists(resolved_path):
            candidate = os.path.join(os.getcwd(), resolved_path)
            if os.path.exists(candidate):
                resolved_path = candidate
        if not os.path.exists(resolved_path):
            normalized = resolved_path.replace("\\", "/").lstrip("/")
            if normalized.startswith("assets/"):
                relative = normalized[len("assets/"):]
                parts = relative.split("/")
                if len(parts) >= 2:
                    client_id = parts[0]
                    filename = "/".join(parts[1:])
                    display_name = os.path.basename(filename) or display_name
                    try:
                        asset = get_asset_content(client_id, filename)
                    except Exception as exc:
                        logger.warning(f"Asset lookup failed for compatibility check {resolved_path}: {exc}")
                        asset = None
                    if asset:
                        content, _mime = asset
                        suffix = os.path.splitext(filename)[1] or ".mp4"
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
                            handle.write(content)
                            temp_path = handle.name
                            resolved_path = temp_path
        if not os.path.exists(resolved_path):
            return ""

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
                    resolved_path,
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=True,
            )
            payload = json.loads(probe.stdout or "{}")
        except Exception as exc:
            logger.warning(f"ffprobe compatibility check failed for {resolved_path}: {exc}")
            return ""
        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

        streams = payload.get("streams") or []
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
        if not video_stream:
            return (
                "Instagram publish blocked before delivery: "
                f"{display_name} does not contain a valid video stream."
            )

        video_codec = str(video_stream.get("codec_name") or "").lower()
        pixel_format = str(video_stream.get("pix_fmt") or "").lower()
        duration_seconds = 0.0
        try:
            duration_seconds = float(video_stream.get("duration") or (payload.get("format") or {}).get("duration") or 0.0)
        except (TypeError, ValueError):
            duration_seconds = 0.0
        frame_rate_raw = str(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "").strip()
        frame_rate = 0.0
        if frame_rate_raw and "/" in frame_rate_raw:
            try:
                num, den = frame_rate_raw.split("/", 1)
                frame_rate = float(num) / float(den) if float(den) else 0.0
            except (ValueError, ZeroDivisionError):
                frame_rate = 0.0
        if video_codec != "h264":
            return (
                "Instagram publish blocked before delivery: "
                f"{display_name} is encoded as {video_codec or 'unknown'} video. Re-export it as H.264 MP4 before Jarvis posts it."
            )
        if pixel_format and pixel_format != "yuv420p":
            return (
                "Instagram publish blocked before delivery: "
                f"{display_name} uses {pixel_format} pixel format. Re-export it as H.264 + yuv420p MP4 before Jarvis posts it."
            )

        if audio_stream:
            audio_codec = str(audio_stream.get("codec_name") or "").lower()
            audio_profile = str(audio_stream.get("profile") or "").upper()
            if audio_codec != "aac":
                return (
                    "Instagram publish blocked before delivery: "
                    f"{display_name} uses {audio_codec or 'unknown'} audio. Re-export it with AAC-LC audio before Jarvis posts it."
                )
            if audio_profile and "HE-AAC" in audio_profile:
                return (
                    "Instagram publish blocked before delivery: "
                    f"{display_name} uses HE-AAC audio. Re-export it with AAC-LC audio before Jarvis posts it."
                )
            try:
                sample_rate = int(str(audio_stream.get("sample_rate") or "0") or 0)
            except (TypeError, ValueError):
                sample_rate = 0
            if sample_rate and sample_rate not in {44100, 48000}:
                return (
                    "Instagram publish blocked before delivery: "
                    f"{display_name} uses {sample_rate}Hz audio. Re-export it at 44.1kHz or 48kHz before Jarvis posts it."
                )
        if duration_seconds and duration_seconds > 90.0:
            return (
                "Instagram publish blocked before delivery: "
                f"{display_name} is {duration_seconds:.1f}s long. Jarvis currently publishes reels up to 90 seconds."
            )
        if frame_rate and frame_rate > 60.0:
            return (
                "Instagram publish blocked before delivery: "
                f"{display_name} runs at {frame_rate:.2f}fps. Re-export it at 60fps or below before Jarvis posts it."
            )

        return ""

    def _format_hashtag_block(self, raw_hashtags: list, platform: str) -> str:
        hashtags = normalize_hashtag_list(raw_hashtags)
        if not hashtags:
            return ""
        if platform == "instagram":
            return f"\n.\n.\n.\n{' '.join(hashtags)}"
        return ""

    def publish(self, agent1_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution method for publishing.
        """
        # 1. Validation 
        if agent1_output.get("status") != "success":
            logger.warning(f"Agent #1 did not return success. Status: {agent1_output.get('status')}. Aborting publish.")
            return {
                "status": "error",
                "message": "Caption generation failed or was held for review.",
                "agent1_status": agent1_output.get("status")
            }

        client_name = agent1_output.get("client_name", "unknown_client")
        
        # 2. Extract configuration (Prefer vault isolation, fallback to .env for testing)
        fb_page_id = os.getenv("META_PAGE_ID")
        ig_user_id = os.getenv("META_IG_USER_ID")
        access_token = os.getenv("META_ACCESS_TOKEN")
        
        try:
            cdata = get_client_store().get_client(client_name) or {}
            access_token = cdata.get("meta_access_token", access_token)
            fb_page_id = cdata.get("facebook_page_id", fb_page_id)
            ig_user_id = cdata.get("instagram_account_id", ig_user_id)
        except Exception as e:
            logger.error(f"Client credential lookup failed for {client_name}: {e}")

        # 3. Handle media URL Asset Mapping
        images = agent1_output.get("images", [])
        videos = agent1_output.get("videos", [])
        if "image_path" in agent1_output and agent1_output["image_path"] and not images:
            val = agent1_output["image_path"]
            images = val if isinstance(val, list) else [val]
            
        image_urls, video_urls, tunnel = self._build_public_media_urls(images, videos)

        logger.info(f"Resolved media URLs for publish: images={image_urls}, videos={video_urls}")

        if image_urls and video_urls:
            return {"status": "error", "message": "Mixed image and video publishing is not supported yet."}
        if len(video_urls) > 1:
            return {"status": "error", "message": "Only a single video is supported per post in this version."}
        if not image_urls and not video_urls:
            return {"status": "error", "message": "No media assets were provided for publish."}

        if not access_token:
            logger.error("Missing META_ACCESS_TOKEN.")
            return {"status": "error", "message": "Missing META_ACCESS_TOKEN in environment."}

        # 4. Format Content
        caption = str(agent1_output.get("caption", "") or "").strip()
        raw_hashtags = agent1_output.get("hashtags", [])
        if not isinstance(raw_hashtags, list):
            raw_hashtags = []

        fb_message = caption.strip()
        ig_caption = f"{caption}{self._format_hashtag_block(raw_hashtags, 'instagram')}".strip()

        # 5. Execute API Calls
        # Extract client_name if available from context, otherwise use default
        client_name = agent1_output.get("client_name", "unknown_client")
        results = {
            "status": "success",
            "client_name": client_name,
            "platform_results": {}
        }
        
        repair_result = self.prepare_managed_media(images, videos, instagram_enabled=bool(ig_user_id))
        if repair_result.get("status") != "success":
            message = str(repair_result.get("reason") or "Jarvis could not prepare the media for publish.").strip()
            if fb_page_id:
                results["platform_results"]["facebook"] = {"status": "error", "error_message": message, "step": "media_repair"}
            if ig_user_id:
                results["platform_results"]["instagram"] = {"status": "error", "error_message": message, "step": "media_repair"}
            results["status"] = "error"
            results["message"] = message
            return results

        preflight = self.preflight_media(images, videos, instagram_enabled=bool(ig_user_id))
        ig_preflight_error = str(preflight.get("instagram_error") or "").strip()
        transport_error = str(preflight.get("transport_error") or "").strip()

        # Publish to Facebook
        if fb_page_id:
            media_count = len(video_urls) if video_urls else len(image_urls)
            if transport_error:
                logger.warning(f"Facebook publish blocked locally: {transport_error}")
                fb_res = {"status": "error", "error_message": transport_error, "step": "preflight_media"}
            else:
                logger.info(f"Publishing to Facebook Page: {fb_page_id} ({media_count} items)")
                fb_res = self._publish_to_facebook(fb_page_id, access_token, fb_message, image_urls, video_urls)
            results["platform_results"]["facebook"] = fb_res
        else:
            logger.warning("No META_PAGE_ID defined. Skipping Facebook.")

        # Publish to Instagram
        if ig_user_id:
            media_count = len(video_urls) if video_urls else len(image_urls)
            if transport_error:
                logger.warning(f"Instagram publish blocked locally: {transport_error}")
                ig_res = {
                    "status": "error",
                    "error_message": transport_error,
                    "step": "preflight_media",
                }
            elif ig_preflight_error:
                logger.warning(f"Instagram publish blocked locally: {ig_preflight_error}")
                ig_res = {
                    "status": "error",
                    "error_message": ig_preflight_error,
                    "step": "preflight_media",
                }
            else:
                current_host = (urlparse(str((image_urls or video_urls or [""])[0] or "")).netloc or "").strip().lower()
                ig_image_urls = list(image_urls)
                ig_video_urls = list(video_urls)
                ig_res = None
                if image_urls and not video_urls:
                    ig_image_urls, mirror_error = self._prepare_instagram_image_urls(images, image_urls, current_host or "unknown-host")
                    if mirror_error:
                        logger.warning(f"Instagram image mirror preparation failed: {mirror_error}")
                        ig_res = {
                            "status": "error",
                            "error_message": mirror_error,
                            "step": "image_mirror",
                        }
                    else:
                        current_host = (urlparse(str((ig_image_urls or [""])[0] or "")).netloc or current_host or "unknown-host").strip().lower()
                elif video_urls:
                    ig_video_urls, mirror_error = self._prepare_instagram_video_urls(videos, video_urls, current_host or "unknown-host")
                    if mirror_error:
                        logger.warning(f"Instagram video mirror preparation failed: {mirror_error}")
                        ig_res = {
                            "status": "error",
                            "error_message": mirror_error,
                            "step": "video_mirror",
                        }
                    else:
                        current_host = (urlparse(str((ig_video_urls or [""])[0] or "")).netloc or current_host or "unknown-host").strip().lower()
                image_host_guard = "" if ig_res is not None else self._instagram_image_host_guard(ig_image_urls, video_urls)
                if image_host_guard and ig_res is None:
                    logger.warning(f"Instagram image publish blocked by environment guard: {image_host_guard}")
                    ig_res = {
                        "status": "error",
                        "error_message": image_host_guard,
                        "step": "image_host_guard",
                    }
                elif ig_res is None:
                    logger.info(f"Publishing to Instagram Account: {ig_user_id} ({media_count} items)")
                    ig_res = self._publish_to_instagram(ig_user_id, access_token, ig_caption, ig_image_urls, ig_video_urls)
            results["platform_results"]["instagram"] = ig_res
        else:
            logger.warning("No META_IG_USER_ID defined. Skipping Instagram.")

        # Post-analysis of results
        statuses = [res.get("status") for res in results["platform_results"].values()]
        if statuses and all(status == "error" for status in statuses):
            results["status"] = "error"
            results["message"] = "Publishing failed on all configured platforms."
        elif statuses and any(status == "published" for status in statuses) and any(status == "error" for status in statuses):
            results["status"] = "partial_success"
            results["message"] = "Publishing succeeded on at least one platform but failed on another."

        return results

    def _publish_to_facebook(self, page_id: str, token: str, message: str, image_urls: list, video_urls: list) -> dict:
        try:
            if video_urls:
                url = f"{self.base_url}/{page_id}/videos"
                payload = {"file_url": video_urls[0], "description": message, "access_token": token}
                response = requests.post(url, data=payload).json()
                if "error" in response:
                    return {"status": "error", "error_message": response["error"]["message"], "step": "upload_video"}
                return {"status": "published", "post_id": response.get("id")}

            if len(image_urls) == 1:
                url = f"{self.base_url}/{page_id}/photos"
                payload = {"url": image_urls[0], "message": message, "access_token": token}
                response = requests.post(url, data=payload).json()
                if "error" in response: return {"status": "error", "error_message": response["error"]["message"]}
                return {"status": "published", "post_id": response.get("id")}
            else:
                # Multi-photo FB post
                attached_media = []
                for murl in image_urls:
                    res = requests.post(
                        f"{self.base_url}/{page_id}/photos",
                        data={"url": murl, "published": "false", "access_token": token},
                    ).json()
                    logger.info(f"Facebook child photo upload response for {murl}: {res}")
                    if "error" in res:
                        return {
                            "status": "error",
                            "error_message": res["error"]["message"],
                            "step": "upload_carousel_photo",
                        }
                    media_id = res.get("id")
                    if not media_id:
                        return {
                            "status": "error",
                            "error_message": "Facebook did not return a media ID for a carousel child upload.",
                            "step": "upload_carousel_photo",
                        }
                    attached_media.append({"media_fbid": media_id})

                if len(attached_media) != len(image_urls) or not attached_media:
                    return {
                        "status": "error",
                        "error_message": "Facebook carousel child uploads did not complete successfully.",
                        "step": "upload_carousel_photo",
                    }
                
                payload = {"message": message, "access_token": token}
                for i, m in enumerate(attached_media):
                    payload[f"attached_media[{i}]"] = str(m).replace("'", '"')
                    
                final_res = requests.post(f"{self.base_url}/{page_id}/feed", data=payload).json()
                if "error" in final_res:
                    return {"status": "error", "error_message": final_res["error"]["message"], "step": "publish_carousel"}
                return {"status": "published", "post_id": final_res.get("id")}
        except Exception as e:
            return {"status": "error", "error_message": str(e)}

    def _publish_to_instagram(self, ig_user_id: str, token: str, caption: str, image_urls: list, video_urls: list) -> dict:
        try:
            is_video_post = bool(video_urls)
            media_urls = video_urls if video_urls else image_urls
            if video_urls:
                create_payload = {"media_type": "REELS", "video_url": video_urls[0], "caption": caption, "access_token": token}
                create_resp = requests.post(f"{self.base_url}/{ig_user_id}/media", data=create_payload).json()
                logger.info(f"Instagram video container response: {create_resp}")
                if "error" in create_resp:
                    return {
                        "status": "error",
                        "error_message": self._format_instagram_fetch_error(create_resp["error"], media_urls),
                        "step": "create_video_container",
                        "raw_error": create_resp["error"],
                    }
                creation_id = create_resp.get("id")
            elif len(image_urls) == 1:
                create_payload = {"image_url": image_urls[0], "caption": caption, "access_token": token}
                create_resp = requests.post(f"{self.base_url}/{ig_user_id}/media", data=create_payload).json()
                logger.info(f"Instagram create container response: {create_resp}")
                if "error" in create_resp:
                    return {
                        "status": "error",
                        "error_message": self._format_instagram_fetch_error(create_resp["error"], media_urls),
                        "step": "create_container",
                        "raw_error": create_resp["error"],
                    }
                creation_id = create_resp.get("id")
            else:
                # Instagram Carousel
                child_ids = []
                for murl in image_urls:
                    res = requests.post(f"{self.base_url}/{ig_user_id}/media", data={"image_url": murl, "is_carousel_item": "true", "access_token": token}).json()
                    logger.info(f"Instagram child container response for {murl}: {res}")
                    if "error" in res:
                        return {
                            "status": "error",
                            "error_message": self._format_instagram_fetch_error(res["error"], [murl]),
                            "step": "create_child_container",
                            "raw_error": res["error"],
                        }
                    child_ids.append(res["id"])
                    
                time.sleep(3) # Wait for children containers to parse
                create_payload = {"media_type": "CAROUSEL", "children": ",".join(child_ids), "caption": caption, "access_token": token}
                create_resp = requests.post(f"{self.base_url}/{ig_user_id}/media", data=create_payload).json()
                logger.info(f"Instagram carousel container response: {create_resp}")
                if "error" in create_resp:
                    return {
                        "status": "error",
                        "error_message": self._format_instagram_fetch_error(create_resp["error"], media_urls),
                        "step": "create_carousel_container",
                        "raw_error": create_resp["error"],
                    }
                creation_id = create_resp.get("id")
                
            logger.info(f"Insta Container {creation_id} created. Polling readiness...")
            
            # Step 2: Poll container status
            max_retries = self.ig_poll_attempts_video if is_video_post else self.ig_poll_attempts_image
            poll_interval = self.ig_poll_interval_video if is_video_post else self.ig_poll_interval_image
            is_finished = False
            last_status_code = None
            last_status_payload: dict[str, Any] = {}
            started_polling_at = time.time()
            
            for attempt in range(max_retries):
                status_data, status_fields = self._poll_instagram_container(creation_id, token)
                last_status_payload = status_data
                logger.info(f"Instagram status poll payload ({status_fields}): {status_data}")
                
                if "error" in status_data:
                    logger.error(f"Instagram status check error: {status_data['error']['message']}")
                    return {
                        "status": "error",
                        "error_message": status_data["error"]["message"],
                        "step": "poll_status",
                        "creation_id": creation_id,
                        "raw_error": status_data.get("error"),
                        "last_status_payload": status_data,
                    }
                
                status_code = status_data.get("status_code")
                last_status_code = status_code
                logger.info(f"Polling attempt {attempt + 1}: Status is {status_code}")
                
                if status_code == "FINISHED":
                    is_finished = True
                    break
                elif status_code == "IN_PROGRESS":
                    time.sleep(poll_interval)
                else:
                    # Could be "ERROR" or something else
                    logger.error(f"Container {creation_id} failed with status payload: {status_data}")
                    extra_detail = ""
                    status_text = str(status_data.get("status") or "").strip()
                    if status_text and status_text.upper() != str(status_code or "").upper():
                        extra_detail = f" ({status_text})"
                    extra_payload = {
                        key: value
                        for key, value in status_data.items()
                        if key not in {"status_code", "status"}
                    }
                    if extra_payload:
                        try:
                            extra_detail += f" | payload={json.dumps(extra_payload, ensure_ascii=False)}"
                        except Exception:
                            pass
                    return {
                        "status": "error",
                        "error_message": f"Container failed with status: {status_code}{extra_detail}",
                        "step": "poll_status",
                        "creation_id": creation_id,
                        "last_status_payload": status_data,
                    }
            
            if not is_finished:
                elapsed = int(time.time() - started_polling_at)
                logger.error(
                    f"Container polling timed out after {elapsed}s. Last status: {last_status_code}. Halting Instagram publish."
                )
                media_label = "video" if is_video_post else "media"
                return {
                    "status": "error",
                    "error_message": f"Instagram {media_label} processing timed out after {elapsed}s. Last status: {last_status_code or 'unknown'}.",
                    "step": "poll_status",
                    "last_status": last_status_code,
                    "last_status_payload": last_status_payload,
                    "poll_elapsed_seconds": elapsed,
                    "creation_id": creation_id,
                }

            # Step 3: Publish Media Container
            logger.info(f"Container {creation_id} finished. Publishing to feed.")
            publish_url = f"{self.base_url}/{ig_user_id}/media_publish"
            publish_payload = {
                "creation_id": creation_id,
                "access_token": token
            }
            
            pub_resp = requests.post(publish_url, data=publish_payload)
            pub_data = pub_resp.json()
            logger.info(f"Instagram publish response: {pub_data}")
            
            if "error" in pub_data:
                logger.error(f"Instagram Publish Media Error: {pub_data['error']['message']}")
                return {"status": "error", "error_message": pub_data["error"]["message"], "step": "publish_container"}
                
            return {
                "status": "published",
                "media_id": pub_data.get("id")
            }
            
        except Exception as e:
            logger.error(f"Instagram Request Failed: {str(e)}")
            return {"status": "error", "error_message": str(e)}

# Singleton instance
publish_agent = PublishAgent()
