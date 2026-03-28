import os
import json
import logging
import time
import re
from datetime import datetime
from agent import Agent
from schedule_store import add_scheduled_job, load_schedule
from schedule_utils import (
    format_schedule_label,
    normalize_schedule_request,
    past_time_error_message,
    schedule_request_is_in_past,
)
from queue_store import get_bundle_media_paths, load_queue_data

logger = logging.getLogger("Orchestrator")


SCHEDULE_WORDS = (
    "schedule",
    "today",
    "tomorrow",
    "next ",
    "this ",
    " monday",
    " tuesday",
    " wednesday",
    " thursday",
    " friday",
    " saturday",
    " sunday",
    "/",
)
IMMEDIATE_WORDS = ("post now", "right now", "immediately", "asap", "instantly")
TIME_WINDOW_RE = re.compile(r"\b\d{1,2}(?::\d{2})?\s*(am|pm)\b", re.IGNORECASE)


def prompt_implies_scheduling(prompt: str) -> bool:
    text = f" {str(prompt or '').strip().lower()} "
    if not text.strip():
        return False
    if any(keyword in text for keyword in IMMEDIATE_WORDS):
        return False
    if " at " in text and TIME_WINDOW_RE.search(text):
        return True
    return any(keyword in text for keyword in SCHEDULE_WORDS)


def describe_release_window(time_str: str) -> str:
    scheduled_time = datetime.strptime(time_str.strip().upper(), "%I:%M %p")
    hour = scheduled_time.hour
    if hour < 11:
        return "morning attention"
    if hour < 15:
        return "midday engagement"
    if hour < 18:
        return "afternoon visibility"
    if hour < 22:
        return "dinner-time engagement"
    return "late-evening reach"

def resolve_client_id(raw_id: str) -> str:
    """
    Case-insensitive resolver. Scans the physical clients/ directory
    and returns the EXACT casing that exists on disk.
    e.g. input 'burger_grillz' -> returns 'Burger_grillz' if that's on disk.
    """
    raw_id = raw_id.strip()
    # Direct match first (fast path)
    if os.path.exists(f"clients/{raw_id}.json"):
        return raw_id
    # Case-insensitive scan
    if os.path.exists("clients"):
        for f in os.listdir("clients"):
            if f.lower() == f"{raw_id.lower()}.json":
                return f[:-5]  # strip .json
    return raw_id  # fallback to raw input

def verify_meta_token(client_id: str):
    import requests
    access_token = os.getenv("META_ACCESS_TOKEN")
    client_vault = f"clients/{client_id}.json"
    if os.path.exists(client_vault):
        try:
            with open(client_vault, "r", encoding="utf-8") as f:
                cdata = json.load(f)
            access_token = cdata.get("meta_access_token", access_token)
        except:
            pass
            
    if not access_token:
        return "No Meta Access Token configured. Add it in the Dashboard Live Credentials first."
        
    try:
        res = requests.get(f"https://graph.facebook.com/v19.0/me?access_token={access_token}", timeout=5).json()
        if "error" in res:
            return f"Expired/Invalid Meta Token: {res['error'].get('message', 'Unknown Error')}."
        return None
    except Exception as e:
        return f"Failed to reach Meta servers for pre-flight validation."


def extract_pipeline_failure_reason(output: str) -> str:
    raw = str(output or "").strip()
    if not raw:
        return "Pipeline failed before returning any diagnostic output."

    lines = [line.strip() for line in raw.splitlines() if line.strip()]

    for line in lines:
        lowered = line.lower()
        if "error validating access token" in lowered:
            return line
        if "requires more credits" in lowered or "402 payment required" in lowered:
            return "Caption generation failed because the current LLM gateway account does not have enough credits for this request."

    global_note = next((line for line in lines if "=> Global Note:" in line), None)
    if global_note:
        return global_note.replace("=> Global Note:", "").strip()

    error_line = next((line for line in lines if line.startswith("Error:")), None)
    if error_line:
        step_line = next((line for line in lines if line.startswith("Step:")), None)
        if step_line:
            return f"{error_line} ({step_line})"
        return error_line

    instagram_error = next((line for line in lines if line.startswith("Instagram:") and "error" in line.lower()), None)
    if instagram_error:
        step_line = next((line for line in lines if line.startswith("Step:")), None)
        if step_line:
            return f"{instagram_error} ({step_line})"
        return instagram_error

    facebook_error = next((line for line in lines if line.startswith("Facebook:") and "error" in line.lower()), None)
    if facebook_error:
        return facebook_error

    traceback_tail = next((line for line in reversed(lines) if "Error" in line or "Exception" in line), None)
    if traceback_tail:
        return traceback_tail

    return lines[-1]


def resolve_saved_draft_reference(client_id: str, bundle_name: str | None = None, topic: str | None = None) -> dict | None:
    queue_path = f"assets/{client_id}/queue.json"
    if not os.path.exists(queue_path):
        return None

    bundles = load_queue_data(queue_path).get("bundles", {})
    if not isinstance(bundles, dict) or not bundles:
        return None

    draft_names = {str(name).strip().lower(): str(name) for name in bundles.keys() if str(name).strip()}
    for candidate, source in ((bundle_name, "bundle_name"), (topic, "topic")):
        cleaned = str(candidate or "").strip()
        if not cleaned:
            continue
        matched_name = draft_names.get(cleaned.lower())
        if not matched_name:
            continue
        payload, images, videos = get_bundle_media_paths(client_id, queue_path, matched_name)
        if not payload:
            continue
        return {
            "bundle_name": matched_name,
            "payload": payload,
            "images": images,
            "videos": videos,
            "matched_from": source,
        }

    return None

class ListClientVaultTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "list_client_vault",
                "description": "List all image assets available in a specific client's isolated vault.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string", "description": "The target CRM Client ID"}
                    },
                    "required": ["client_id"]
                }
            }
        }
    def execute(self, client_id):
        client_id = resolve_client_id(client_id)
        vault_path = f"assets/{client_id}"
        if not os.path.exists(vault_path):
            return {"error": f"Vault '{vault_path}' does not exist. No images found for '{client_id}'."}
        files = os.listdir(vault_path)
        if not files:
            return {"images": [], "message": "Vault is currently empty."}
        return {"client_id": client_id, "images": files}

class ReadVaultQueueTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "read_vault_queue",
                "description": "Read the explicitly created creative drafts for a client. Use this to see what queued draft names the user has prepared for scheduling or posting.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string", "description": "The target CRM Client ID"}
                    },
                    "required": ["client_id"]
                }
            }
        }
    def execute(self, client_id):
        client_id = resolve_client_id(client_id)
        queue_path = f"assets/{client_id}/queue.json"
        if not os.path.exists(queue_path):
            return {"client_id": client_id, "bundles": {}, "message": "No creative drafts are currently queued."}
        try:
            data = load_queue_data(queue_path).get("bundles", {})
            return {"client_id": client_id, "bundles": data}
        except Exception:
            return {"error": "Failed to parse queue.json"}

class ReadClientBriefTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "read_client_brief",
                "description": "Read the JSON profile of a client to understand their constraints, identity, and tone.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string", "description": "The target CRM Client ID"}
                    },
                    "required": ["client_id"]
                }
            }
        }
    def execute(self, client_id):
        client_id = resolve_client_id(client_id)
        profile_path = f"clients/{client_id}.json"
        if not os.path.exists(profile_path):
            return {"error": f"Profile '{profile_path}' not found."}
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)

class AutonomousScheduleTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "commit_autonomous_schedule",
                "description": "DANGEROUS: Schedules a post directly into schedule.json for autonomous execution. Use ONLY if the user explicitly says 'force', 'autonomous', or 'skip approval'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string", "description": "The target CRM Client ID"},
                        "topic": {"type": "string", "description": "The focus/topic of the scheduled post"},
                        "image": {"type": "string", "description": "(Legacy) The exact image filename from the vault to attach (e.g. img_123.jpg)"},
                        "bundle_name": {"type": "string", "description": "The exact creative draft name from the vault queue to attach (for example 'Reel 1', 'Carousel 2', or 'Image Post 3'). Use this instead of raw filenames when a saved draft is requested."},
                        "days": {
                            "type": "array", 
                            "items": {"type": "string"},
                            "description": "Legacy weekday list for recurring schedules or relative phrases. Use this only when the user truly means a weekly recurring pattern or gives a simple relative phrase like ['today']."
                        },
                        "scheduled_date": {
                            "type": "string",
                            "description": "Preferred for one-off posts. Resolve exact calendar intent into YYYY-MM-DD. Examples: '2026-04-03', '2026-04-21'."
                        },
                        "post_time": {"type": "string", "description": "Execution time in HH:MM AM/PM format (e.g. '06:00 PM')"}
                    },
                    "required": ["client_id", "days", "post_time"]
                }
            }
        }
    def execute(self, client_id, days, post_time, topic=None, image=None, bundle_name=None, scheduled_date=None):
        client_id = resolve_client_id(client_id)
        
        # PRE-FLIGHT SAFETY CHECK
        token_err = verify_meta_token(client_id)
        if token_err:
            return {"error": f"❌ PRE-FLIGHT VERIFICATION FAILED: {token_err}\nTell the user they must update the client's Live Credentials in the dashboard securely before scheduling this."}
            
        if not topic:
            topic = f"Scheduled {bundle_name}" if bundle_name else "Scheduled Post"
            
        try:
            resolved_draft = resolve_saved_draft_reference(client_id, bundle_name=bundle_name, topic=topic)
            if resolved_draft:
                bundle_name = resolved_draft["bundle_name"]
                payload = resolved_draft["payload"]
                if not topic or str(topic).strip().lower() == bundle_name.strip().lower():
                    topic = str(payload.get("topic_hint") or f"{bundle_name} spotlight").strip()

            resolved_date, normalized_days = normalize_schedule_request(days, scheduled_date=scheduled_date)
            if schedule_request_is_in_past(post_time, scheduled_date=resolved_date or scheduled_date, raw_days=days):
                return {"error": past_time_error_message(post_time, scheduled_date=resolved_date or scheduled_date, days=normalized_days)}

            rule = {
                "client": client_id,
                "topic": topic,
                "days": normalized_days,
                "scheduled_date": resolved_date or "",
                "time": post_time,
                "status": "approved"
            }
            
            if bundle_name:
                queue_path = f"assets/{client_id}/queue.json"
                if resolved_draft:
                    payload = resolved_draft["payload"]
                    images = resolved_draft["images"]
                    videos = resolved_draft["videos"]
                    if images:
                        rule["images"] = images
                    if videos:
                        rule["videos"] = videos
                    rule["draft_name"] = bundle_name
                    rule["media_kind"] = payload["bundle_type"]
                elif os.path.exists(queue_path):
                    payload, images, videos = get_bundle_media_paths(client_id, queue_path, bundle_name)
                    if not payload:
                        return {"error": f"Creative draft '{bundle_name}' not found in the client's vault queue. Use read_vault_queue first to inspect the available draft names."}
                    if images:
                        rule["images"] = images
                    if videos:
                        rule["videos"] = videos
                    rule["draft_name"] = bundle_name
                    rule["media_kind"] = payload["bundle_type"]
                else:
                    return {"error": "No queue.json found for this client."}
            elif image:
                rule["images"] = [f"assets/{client_id}/{image}"]
                rule["media_kind"] = "image_single"

            added, duplicate, saved_job = add_scheduled_job(rule)
            if not added:
                dup_id = duplicate.get("job_id", "unknown") if duplicate else "unknown"
                return {
                    "error": (
                        f"An active scheduled job already exists for {client_id} at {format_schedule_label(post_time, scheduled_date=rule.get('scheduled_date'), days=normalized_days)}. "
                        f"Duplicate prevented. Existing job_id: {dup_id}."
                    )
                }
                
            daemon_status = ""
            try:
                if os.path.exists(".daemon_heartbeat"):
                    with open(".daemon_heartbeat", "r") as f:
                        last_beat = float(f.read().strip())
                    if time.time() - last_beat > 30:
                        daemon_status = " [CRITICAL WARNING: The execution daemon (scheduler.py) is OFFLINE. This post will NOT publish until you start the daemon.]"
                else:
                    daemon_status = " [CRITICAL WARNING: The execution daemon (scheduler.py) has never been started. This post will NOT publish until you run it.]"
            except Exception:
                pass

            schedule_label = format_schedule_label(post_time, scheduled_date=saved_job.get("scheduled_date"), days=saved_job.get("days"))
            return {"status": "success", "message": f"Successfully queued '{topic}' for {client_id} at {schedule_label} as job {saved_job['job_id']}.{daemon_status}", "job_id": saved_job["job_id"]}
        except Exception as e:
            import traceback
            return {"error": f"commit_autonomous_schedule crashed: {type(e).__name__}: {str(e)}", "traceback": traceback.format_exc()}

class RequestApprovalTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "request_client_approval",
                "description": "CRITICAL: ALWAYS USE THIS TOOL whenever you are told to schedule a post, UNLESS explicitly told to 'skip approval' or 'force schedule'. Drafts the post payload, queues it in pending_approvals.json, and pings the Agency Owner via WhatsApp with native Approve/Reject interactive buttons.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string", "description": "The EXACT client folder name"},
                        "topic": {"type": "string", "description": "Short topic or campaign angle for the draft"},
                        "days": {"type": "array", "items": {"type": "string"}, "description": "Legacy weekday list or relative phrase holder. Use scheduled_date for one-off calendar dates whenever possible."},
                        "scheduled_date": {"type": "string", "description": "Preferred one-off calendar date in YYYY-MM-DD after resolving phrases like next Friday or April 21."},
                        "time": {"type": "string", "description": "Time string e.g. '04:30 PM'"},
                        "bundle_name": {"type": "string", "description": "If scheduling a saved creative draft, the exact draft name from the queue (for example 'Reel 1' or 'Carousel 2')."},
                        "image": {"type": "string", "description": "If scheduling a single image, the filename"}
                    },
                    "required": ["client_id", "topic", "days", "time"]
                }
            }
        }
        
    def execute(self, client_id, topic, days, time, bundle_name=None, image=None, scheduled_date=None):
        try:
            import uuid
            from webhook_server import send_interactive_whatsapp_approval, get_agency_config

            client_id = resolve_client_id(client_id)
            caption_preview_line = ""
            resolved_draft = resolve_saved_draft_reference(client_id, bundle_name=bundle_name, topic=topic)
            if resolved_draft:
                bundle_name = resolved_draft["bundle_name"]
                payload = resolved_draft["payload"]
                if not topic or str(topic).strip().lower() == bundle_name.strip().lower():
                    topic = str(payload.get("topic_hint") or f"{bundle_name} spotlight").strip()
            raw_days = [str(day).strip() for day in days if str(day).strip()]
            if not raw_days and not scheduled_date:
                return {"error": "A scheduling target is required. Provide a day phrase like 'tomorrow' or an exact calendar date."}
            resolved_date, normalized_days = normalize_schedule_request(raw_days, scheduled_date=scheduled_date)
            if schedule_request_is_in_past(time, scheduled_date=resolved_date or scheduled_date, raw_days=raw_days):
                return {"error": past_time_error_message(time, scheduled_date=resolved_date or scheduled_date, days=normalized_days)}

            rule = {
                "job_id": uuid.uuid4().hex[:12],
                "client": client_id,
                "topic": topic,
                "days": normalized_days,
                "scheduled_date": resolved_date or "",
                "time": time,
                "status": "pending_approval"
            }

            if bundle_name:
                queue_path = f"assets/{client_id}/queue.json"
                if resolved_draft:
                    payload = resolved_draft["payload"]
                    images = resolved_draft["images"]
                    videos = resolved_draft["videos"]
                    if images:
                        rule["images"] = images
                    if videos:
                        rule["videos"] = videos
                    rule["draft_name"] = bundle_name
                    rule["media_kind"] = payload["bundle_type"]
                    if payload.get("caption_text"):
                        rule["caption_text"] = payload.get("caption_text", "")
                        rule["hashtags"] = payload.get("hashtags", [])
                        rule["seo_keyword_used"] = payload.get("seo_keyword_used", "")
                        rule["caption_mode"] = payload.get("caption_mode", "ai")
                        rule["caption_status"] = payload.get("caption_status", "ready")
                        preview_text = str(payload.get("caption_text", "")).strip()
                        if preview_text:
                            clipped = preview_text[:110].strip()
                            if len(preview_text) > 110:
                                clipped += "..."
                            caption_preview_line = f"Caption Preview: {clipped}\n"
                elif os.path.exists(queue_path):
                    payload, images, videos = get_bundle_media_paths(client_id, queue_path, bundle_name)
                    if not payload:
                        return {"error": f"Creative draft '{bundle_name}' not found."}
                    if images:
                        rule["images"] = images
                    if videos:
                        rule["videos"] = videos
                    rule["draft_name"] = bundle_name
                    rule["media_kind"] = payload["bundle_type"]
                    if payload.get("caption_text"):
                        rule["caption_text"] = payload.get("caption_text", "")
                        rule["hashtags"] = payload.get("hashtags", [])
                        rule["seo_keyword_used"] = payload.get("seo_keyword_used", "")
                        rule["caption_mode"] = payload.get("caption_mode", "ai")
                        rule["caption_status"] = payload.get("caption_status", "ready")
                        preview_text = str(payload.get("caption_text", "")).strip()
                        if preview_text:
                            clipped = preview_text[:110].strip()
                            if len(preview_text) > 110:
                                clipped += "..."
                            caption_preview_line = f"Caption Preview: {clipped}\n"
                else:
                    return {"error": "No queue.json found for this client."}
            elif image:
                rule["images"] = [f"assets/{client_id}/{image}"]
                rule["media_kind"] = "image_single"

            approval_id = uuid.uuid4().hex[:8].upper()
            rule["approval_id"] = approval_id

            pending = []
            if os.path.exists("pending_approvals.json"):
                with open("pending_approvals.json", "r", encoding="utf-8") as f:
                    try:
                        pending = json.load(f)
                    except Exception:
                        pending = []

            pending.append(rule)

            with open("pending_approvals.json", "w", encoding="utf-8") as f:
                json.dump(pending, f, indent=4)

            owner_phone = get_agency_config().get("owner_phone", "")
            if owner_phone:
                display_client = client_id.replace("_", " ").replace("-", " ").strip().title()
                image_count = len(rule.get("images", []))
                video_count = len(rule.get("videos", []))
                if video_count:
                    asset_label = "1-video post"
                elif image_count > 1:
                    asset_label = f"{image_count}-image carousel"
                elif image_count == 1:
                    asset_label = "1-image post"
                else:
                    asset_label = "Media ready"
                scheduling_label = format_schedule_label(time, scheduled_date=rule.get("scheduled_date"), days=rule.get("days"))
                creative_focus = f"{bundle_name or image or topic} spotlight"
                preview = (
                    f"{display_client}\n"
                    f"Your next creative is staged and ready for final approval.\n\n"
                    f"Go-live: {scheduling_label}\n"
                    f"Assets: {asset_label}\n"
                    f"Focus: {creative_focus}\n"
                    f"{caption_preview_line}"
                    f"Select the release path below."
                )
                send_result = send_interactive_whatsapp_approval(owner_phone, approval_id, preview)
                if send_result.get("success"):
                    return {
                        "status": "success",
                        "message": f"Draft prepared. Sent approval card {approval_id} to the agency owner for review.",
                        "approval_id": approval_id,
                        "job_id": rule["job_id"],
                    }
                return {
                    "error": f"Draft saved, but WhatsApp approval send failed: {send_result.get('error', 'Unknown Meta API failure.')}",
                    "approval_id": approval_id,
                    "job_id": rule["job_id"],
                }
            else:
                return {"error": "Draft saved, but could NOT send WhatsApp. OWNER_PHONE is missing from Agency Settings."}
        except Exception as e:
            return {"error": str(e)}

class ReadCronScheduleTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "read_cron_schedule",
                "description": "Read the entire live schedule.json file to see all currently active cron jobs across all clients.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
    def execute(self):
        try:
            data = load_schedule("schedule.json")
            if not data:
                return {"schedule": "The schedule is currently empty."}
            return data
        except Exception as e:
            return {"error": str(e)}

class ReadPipelineStreamTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "read_pipeline_stream",
                "description": "Tail the last 50 lines of pipeline_stream.log to see the LIVE status of the content generation nodes.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
    def execute(self):
        try:
            if not os.path.exists("pipeline_stream.log"):
                return {"log": "No pipeline logs exist yet."}
            with open("pipeline_stream.log", "r", encoding="utf-8") as f:
                lines = f.readlines()
            return {"log": "".join(lines[-50:])}
        except Exception as e:
            return {"error": str(e)}

class TriggerPipelineNowTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "trigger_pipeline_now",
                "description": "IMMEDIATELY execute the full content pipeline for a client: generates a caption via the Caption Agent, publishes to Meta (Facebook + Instagram), and sends a WhatsApp briefing. Use this for any 'post now' or same-day requests. This tool BLOCKS until the pipeline finishes and returns the real result.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string", "description": "The target CRM client ID"},
                        "topic": {"type": "string", "description": "The topic/prompt for the post"},
                        "image": {"type": "string", "description": "Optional exact image filename from the vault"},
                        "bundle_name": {"type": "string", "description": "Optional creative draft name from the queue (for example 'Reel 1', 'Carousel 2', or 'Image Post 3')."}
                    },
                    "required": ["client_id"]
                }
            }
        }
    def execute(self, client_id, topic=None, image=None, bundle_name=None, post_time=None, time=None, days=None, scheduled_date=None, **kwargs):
        import subprocess, sys
        client_id = resolve_client_id(client_id)
        
        # PRE-FLIGHT SAFETY CHECK
        token_err = verify_meta_token(client_id)
        if token_err:
            return {"error": f"❌ PRE-FLIGHT VERIFICATION FAILED: {token_err}\nTell the user they must update the client's Live Credentials in the dashboard securely before running this pipeline."}
            
        try:
            resolved_draft = resolve_saved_draft_reference(client_id, bundle_name=bundle_name, topic=topic)
            if resolved_draft:
                bundle_name = resolved_draft["bundle_name"]
                payload = resolved_draft["payload"]
                if not topic or str(topic).strip().lower() == bundle_name.strip().lower():
                    topic = str(payload.get("topic_hint") or f"{bundle_name} spotlight").strip()
            if not topic:
                topic = f"Auto-post for {bundle_name}" if bundle_name else "Immediate pipeline post"

            # Guard against the model selecting the immediate-post tool while also
            # attaching schedule-style arguments. In that case we fail clearly
            # instead of crashing or silently posting now.
            schedule_hint = post_time or time or scheduled_date or (days if days else None)
            if schedule_hint:
                return {
                    "error": (
                        "This request includes a future release window, so it should go through the scheduling/approval "
                        "workflow instead of immediate publishing. Use request_client_approval or commit_autonomous_schedule."
                    )
                }
                
            cmd = [sys.executable, "pipeline.py", "--client", client_id, "--topic", topic]
            
            if bundle_name:
                queue_path = f"assets/{client_id}/queue.json"
                if resolved_draft:
                    images = resolved_draft["images"]
                    videos = resolved_draft["videos"]
                    for img in images:
                        cmd += ["--image", img]
                    for video in videos:
                        cmd += ["--video", video]
                    cmd += ["--draft-name", bundle_name]
                elif os.path.exists(queue_path):
                    payload, images, videos = get_bundle_media_paths(client_id, queue_path, bundle_name)
                    if not payload:
                        return {"error": f"Creative draft '{bundle_name}' not found."}
                    for img in images:
                        cmd += ["--image", img]
                    for video in videos:
                        cmd += ["--video", video]
                    cmd += ["--draft-name", bundle_name]
                else:
                    return {"error": "No queue.json found for this client."}
            elif image:
                cmd += ["--image", f"assets/{client_id}/{image}"]
            
            logger.info(f"TriggerPipelineNow | Spawning pipeline for {client_id}...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            output = result.stdout + result.stderr
            
            # Detect publish failures from output regardless of exit code
            has_publish_error = any(err in output for err in [
                'Publishing failed', 'error', 'Error validating', 
                'FAILED', 'Error:', 'status": "error'
            ])
            
            if result.returncode != 0 or has_publish_error:
                reason = extract_pipeline_failure_reason(output)
                return {
                    "error": f"Immediate publish failed for {client_id}: {reason}",
                    "output": output[-1500:]
                }
            else:
                return {"status": "success", "message": f"Pipeline completed successfully for {client_id}.", "output": output[-1500:]}
        except subprocess.TimeoutExpired:
            return {"error": f"Immediate publish failed for {client_id}: Pipeline timed out after 120 seconds."}
        except Exception as e:
            import traceback
            return {"error": f"trigger_pipeline_now crashed: {type(e).__name__}: {str(e)}", "traceback": traceback.format_exc()}

class MetaInsightsScannerTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "meta_insights_scanner",
                "description": "Pull live Instagram and Facebook analytics for a client. Returns recent post performance including reach, likes, comments, shares, saves, and identifies the top-performing post.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string", "description": "The target CRM Client ID"},
                        "limit": {"type": "integer", "description": "Number of recent posts to analyze. CRITICAL: If the user asks for 'the recent post' or 'the last post' (singular), you MUST set limit to 1. (default 5, max 25)"}
                    },
                    "required": ["client_id"]
                }
            }
        }
    def execute(self, client_id, limit=10):
        import requests
        client_id = resolve_client_id(client_id)
        
        # Load client credentials
        client_file = f"clients/{client_id}.json"
        if not os.path.exists(client_file):
            return {"error": f"Client '{client_id}' not found. Register them in the dashboard first."}
        
        with open(client_file, "r", encoding="utf-8") as f:
            cdata = json.load(f)
        
        access_token = cdata.get("meta_access_token", os.getenv("META_ACCESS_TOKEN"))
        ig_user_id = cdata.get("instagram_account_id", os.getenv("META_IG_USER_ID"))
        fb_page_id = cdata.get("facebook_page_id", os.getenv("META_PAGE_ID"))
        
        if not access_token:
            return {"error": "No Meta Access Token configured for this client."}
        
        limit = min(limit, 25)
        results = {"client_id": client_id, "instagram": None, "facebook": None}
        
        # --- Instagram Insights ---
        if ig_user_id:
            try:
                media_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
                media_params = {
                    "fields": "id,caption,timestamp,like_count,comments_count,media_type",
                    "limit": limit,
                    "access_token": access_token
                }
                media_resp = requests.get(media_url, params=media_params, timeout=10).json()
                
                if "error" in media_resp:
                    results["instagram"] = {"error": media_resp["error"].get("message", "Unknown API error")}
                else:
                    posts = media_resp.get("data", [])
                    post_insights = []
                    total_likes = 0
                    total_comments = 0
                    top_post = None
                    top_engagement = 0
                    
                    for post in posts:
                        likes = post.get("like_count", 0)
                        comments = post.get("comments_count", 0)
                        engagement = likes + comments
                        total_likes += likes
                        total_comments += comments
                        
                        # Try to get per-post reach/saves
                        extra = {}
                        try:
                            insight_url = f"https://graph.facebook.com/v19.0/{post['id']}/insights"
                            insight_params = {"metric": "reach,saved", "access_token": access_token}
                            insight_resp = requests.get(insight_url, params=insight_params, timeout=5).json()
                            if "data" in insight_resp:
                                for metric in insight_resp["data"]:
                                    extra[metric["name"]] = metric["values"][0]["value"] if metric.get("values") else 0
                        except:
                            pass
                        
                        caption_preview = (post.get("caption") or "")[:80]
                        post_data = {
                            "id": post["id"],
                            "caption_preview": caption_preview + "..." if len(post.get("caption", "")) > 80 else caption_preview,
                            "timestamp": post.get("timestamp"),
                            "likes": likes,
                            "comments": comments,
                            "reach": extra.get("reach", "N/A"),
                            "saves": extra.get("saved", "N/A"),
                            "media_type": post.get("media_type", "IMAGE")
                        }
                        post_insights.append(post_data)
                        
                        if engagement > top_engagement:
                            top_engagement = engagement
                            top_post = post_data
                    
                    results["instagram"] = {
                        "total_posts_analyzed": len(posts),
                        "total_likes": total_likes,
                        "total_comments": total_comments,
                        "avg_likes_per_post": round(total_likes / len(posts), 1) if posts else 0,
                        "avg_comments_per_post": round(total_comments / len(posts), 1) if posts else 0,
                        "top_performing_post": top_post,
                        "recent_posts": post_insights[:5]
                    }
                    
                    # --- Enhanced Comparative Analytics ---
                    from collections import defaultdict
                    
                    # 1. Carousel vs Single Image performance
                    carousel_engagement = []
                    single_engagement = []
                    for p in post_insights:
                        eng = p["likes"] + p["comments"]
                        if p.get("media_type") == "CAROUSEL_ALBUM":
                            carousel_engagement.append(eng)
                        else:
                            single_engagement.append(eng)
                    
                    format_analysis = {}
                    if carousel_engagement:
                        format_analysis["carousel_avg_engagement"] = round(sum(carousel_engagement) / len(carousel_engagement), 1)
                        format_analysis["carousel_count"] = len(carousel_engagement)
                    if single_engagement:
                        format_analysis["single_avg_engagement"] = round(sum(single_engagement) / len(single_engagement), 1)
                        format_analysis["single_count"] = len(single_engagement)
                    if carousel_engagement and single_engagement:
                        carousel_avg = sum(carousel_engagement) / len(carousel_engagement)
                        single_avg = sum(single_engagement) / len(single_engagement)
                        if single_avg > 0:
                            format_analysis["carousel_vs_single_multiplier"] = f"{round(carousel_avg / single_avg, 1)}x"
                    
                    results["instagram"]["format_comparison"] = format_analysis
                    
                    # 2. Best posting day
                    day_engagement = defaultdict(list)
                    for p in post_insights:
                        ts = p.get("timestamp")
                        if ts:
                            try:
                                from datetime import datetime as dt
                                posted_dt = dt.fromisoformat(ts.replace("Z", "+00:00"))
                                day_name = posted_dt.strftime("%A")
                                day_engagement[day_name].append(p["likes"] + p["comments"])
                            except:
                                pass
                    
                    if day_engagement:
                        best_day = max(day_engagement, key=lambda d: sum(day_engagement[d]) / len(day_engagement[d]))
                        results["instagram"]["best_posting_day"] = best_day
                        results["instagram"]["day_breakdown"] = {
                            d: {"avg_engagement": round(sum(v)/len(v), 1), "posts": len(v)} 
                            for d, v in day_engagement.items()
                        }
                    
                    # 3. Total reach
                    total_reach = sum(p["reach"] for p in post_insights if isinstance(p.get("reach"), (int, float)))
                    if total_reach > 0:
                        results["instagram"]["total_reach"] = total_reach
            except Exception as e:
                results["instagram"] = {"error": f"Failed to fetch IG insights: {str(e)}"}
        
        # --- Facebook Page Insights ---
        if fb_page_id:
            try:
                fb_url = f"https://graph.facebook.com/v19.0/{fb_page_id}"
                fb_params = {
                    "fields": "fan_count,name",
                    "access_token": access_token
                }
                fb_resp = requests.get(fb_url, params=fb_params, timeout=10).json()
                
                if "error" in fb_resp:
                    results["facebook"] = {"error": fb_resp["error"].get("message", "Unknown")}
                else:
                    results["facebook"] = {
                        "page_name": fb_resp.get("name", "Unknown"),
                        "total_followers": fb_resp.get("fan_count", 0)
                    }
            except Exception as e:
                results["facebook"] = {"error": f"Failed to fetch FB insights: {str(e)}"}
        
        return results

class WebSearchTool:
    def get_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web using DuckDuckGo for real-time information. Use this for: industry trends, strategy research, competitor analysis, best practices, and any question that requires current knowledge. Returns top search results with titles, URLs, and snippets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query string"},
                        "max_results": {"type": "integer", "description": "Max results to return (default 5, max 8)"}
                    },
                    "required": ["query"]
                }
            }
        }
    def execute(self, query, max_results=5):
        max_results = min(max_results, 8)
        
        try:
            from ddgs import DDGS
            
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=max_results))
            
            if not raw_results:
                return {"query": query, "results": [], "note": "No results found. Try rephrasing the query."}
            
            results = []
            for r in raw_results:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
            
            return {"query": query, "results": results, "total": len(results)}
            
        except Exception as e:
            return {"error": f"Web search failed: {str(e)}"}

class OrchestratorAgent(Agent):
    def __init__(self):
        today_context = datetime.now().strftime("%A, %B %d, %Y")
        tools = [
            ListClientVaultTool(), ReadVaultQueueTool(), ReadClientBriefTool(), AutonomousScheduleTool(),
            ReadCronScheduleTool(), ReadPipelineStreamTool(), TriggerPipelineNowTool(), MetaInsightsScannerTool(),
            WebSearchTool(), RequestApprovalTool()
        ]
        super().__init__(tools)
        self.system_message = (
            "You are JARVIS, the highly intelligent Lead Orchestrator for Orionx Agency OS. "
            f"Today's date is {today_context}. Use this exact current date when resolving relative scheduling phrases. "
            "You have a dry, professional, and slightly sarcastic personality (similar to TARS from Interstellar). "
            "CRITICAL RULES FOR ASSETS AND CREATIVE DRAFTS: "
            "When asked to schedule media, ALWAYS prioritize using 'read_vault_queue' to inspect the user's explicitly created creative drafts (for example 'Reel 1', 'Carousel 2', or 'Image Post 3'). "
            "If the user asks you to schedule a saved creative draft, pass the EXACT `bundle_name`. NEVER try to pass raw filenames if a saved draft is requested. "
            "CRITICAL TOOL ROUTING RULES: "
            "2. Whenever you are asked to 'schedule' a post, YOU MUST use `request_client_approval` by default. This is the safe, production-grade workflow. "
            "3. ONLY use `commit_autonomous_schedule` if the user explicitly uses keywords like 'autonomous', 'force', 'skip approval', or 'bypass safety'. "
            "4. If requested to schedule multiple creative drafts, execute the chosen scheduling/approval tool MULTIPLE TIMES IN PARALLEL. DO NOT PROMPT THE USER BETWEEN CALLS. "
            "5. CALENDAR RULE: For one-off posts, ALWAYS resolve the user's date intent into `scheduled_date` using YYYY-MM-DD. Examples include today, tomorrow, this Friday, next Friday, April 21, 4/21, or Tuesday 21. "
            "6. Use `days` only for recurring weekly schedules or as a compatibility field. If the user wants a specific calendar release, prefer `scheduled_date`. "
            "7. If the user explicitly repeats the same creative draft name in their message, DO NOT SCHEDULE IT TWICE. Deduplicate their intent and only call the tool ONCE per unique draft. "
            "7b. If the user includes any future day/date/time phrase such as today at 6 PM, tomorrow, next Friday, or April 21, that is a scheduling request, not an immediate publish request. Route it to request_client_approval unless the user explicitly says post now or immediately. "
            "8. ANALYTICS: When asked about performance, insights, engagement, or analytics, use 'meta_insights_scanner'. Present the data conversationally — highlight the top post, compare carousel vs single-image performance, mention the best posting day, and make actionable recommendations. "
            "9. STRATEGY & RESEARCH: When asked about strategy, trends, competitor analysis, 'what should we do', or anything requiring current market knowledge, use 'web_search' to find real-time information. Combine search results with any available analytics data from 'meta_insights_scanner' to create data-backed strategy recommendations. Always cite your sources. "
            "10. ABSOLUTE HONESTY RULE: If ANY tool you call returns an error, failure, or exception, you MUST relay the EXACT error message to the user. NEVER claim success, NEVER soften the message, NEVER say 'posted successfully' or 'minor hiccup' when a tool failed. The user must know the truth. Violations of this rule are catastrophic. "
            "11. Be endlessly helpful and precise regarding anything related to the agency. "
            "12. Keep responses high-end, concise, and action-oriented."
        )

_global_agent = OrchestratorAgent()

def run_orchestrator(user_input: str) -> str:
    global _global_agent
    agent = _global_agent
    original_request = user_input
    max_turns = 10
    i = 0
    repeated_tool_rounds = 0
    last_tool_fingerprint = None
    last_error_message = None
    
    while i < max_turns:
        i += 1
        logger.info(f"Orchestrator Cycle {i} - Pinging OpenAI/OpenRouter via SDK...")
        
        response = agent.chat(user_input)
        if not response.choices:
            return "Error: No response generated from active LLM gateway."
            
        message = response.choices[0].message
        
        if message.tool_calls:
            agent.messages.append(message)
            current_fingerprint_parts = []
            round_errors = []
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_input = json.loads(tool_call.function.arguments)
                logger.info(f"Orchestrator invoking physical Python tool: {tool_name} | constraints: {tool_input}")
                current_fingerprint_parts.append(
                    json.dumps({"tool": tool_name, "input": tool_input}, sort_keys=True, ensure_ascii=False)
                )
                
                tool = agent.tool_map.get(tool_name)
                try:
                    if tool_name == "trigger_pipeline_now" and prompt_implies_scheduling(original_request):
                        tool_result = {
                            "error": (
                                "This request clearly includes a scheduled release window, so it must go through "
                                "the approval/scheduling workflow instead of immediate publishing."
                            )
                        }
                    elif tool:
                        tool_result = tool.execute(**tool_input)
                    else:
                        tool_result = {"error": f"Physical Tool {tool_name} not mounted."}
                except Exception as e:
                    import traceback
                    tool_result = {
                        "error": f"{tool_name} crashed: {type(e).__name__}: {str(e)}",
                        "traceback": traceback.format_exc(),
                    }

                if isinstance(tool_result, dict) and tool_result.get("error"):
                    round_errors.append(str(tool_result["error"]))
                    last_error_message = str(tool_result["error"])
                    
                agent.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result)
                })

            current_fingerprint = "|".join(current_fingerprint_parts)
            if current_fingerprint == last_tool_fingerprint:
                repeated_tool_rounds += 1
            else:
                repeated_tool_rounds = 0
                last_tool_fingerprint = current_fingerprint

            if repeated_tool_rounds >= 1 and round_errors:
                if "client" in " ".join(round_errors).lower():
                    return "Jarvis got stuck resolving the request because the target client context was unclear. Please retry with an explicit client mention like `@burger_grillz schedule Reel 1 for tomorrow at 12:10 PM`."
                return round_errors[-1]

            user_input = "" 
        else:
            return message.content
            
    if last_error_message:
        return last_error_message
    return "Jarvis reached its orchestration safety limit without resolving the request. Retry with a more explicit scheduling target, preferably including the client mention and exact date."
