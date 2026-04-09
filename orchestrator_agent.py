import os
import json
import logging
import time
import re
from datetime import datetime, timedelta
from agent import Agent
from asset_store import list_client_assets
from client_store import get_client_store
from schedule_store import add_scheduled_job, load_schedule
from approval_store import save_pending_approval
from draft_store import get_draft_media_paths, list_client_drafts, resolve_draft_payload
from schedule_utils import (
    format_schedule_label,
    normalize_schedule_request,
    normalize_prompt_date_typos,
    past_time_error_message,
    parse_time_string,
    resolve_date_phrase,
    schedule_request_is_in_past,
)

logger = logging.getLogger("Orchestrator")


SCHEDULE_WORDS = (
    "schedule",
    "today",
    "tonight",
    "this evening",
    "this afternoon",
    "this morning",
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
IMMEDIATE_WORDS = ("post now", "post this now", "right now", "immediately", "asap", "instantly", "now")
TIME_WINDOW_RE = re.compile(r"\b\d{1,2}(?::\d{2})?\s*(am|pm)\b", re.IGNORECASE)
SMART_DRAFT_REF_RE = re.compile(
    r'@\[(?P<client>[^\]]+)\]\s+draft_id:"(?P<draft_id>[^"]+)"(?:\s+draft:"(?P<draft>[^"]+)")?',
    re.IGNORECASE,
)
VISIBLE_SMART_DRAFT_RE = re.compile(
    r'@\[(?P<client>[^\]]+)\]\s+draft\s+[·Â·]\s+(?P<draft>.+?)(?=(?:\s+(?:please|post|publish|schedule|delete|move|refine|approve|for|now|today|tomorrow|next)\b)|$)',
    re.IGNORECASE,
)




ROBUST_CLIENT_MENTION_RE = re.compile(r'@\[(?P<client>[^\]]+)\]', re.IGNORECASE)
RAW_CLIENT_MENTION_RE = re.compile(r'(?<!\[)@(?P<client>[A-Za-z0-9_-]+)', re.IGNORECASE)
ROBUST_DRAFT_MARKER_RE = re.compile(r'\bdraft\b\s*(?:[·•:\-\u2013\u2014]|Â·|Ã‚Â·)\s*', re.IGNORECASE)
BATCH_POST_WORDS = ("post", "publish", "launch", "release")
CLAUSE_SPLIT_RE = re.compile(r"(?:,\s*|\band also\b|\band then\b|;\s*|\n+)", re.IGNORECASE)
DATE_TOKEN_RE = re.compile(
    r"\b(today|tonight|this evening|this afternoon|this morning|tomorrow|(this|next)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(?:date\s+)?\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{4})?|"
    r"(january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{4})?|"
    r"\d{1,2}/\d{1,2}(?:/\d{2,4})?|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)
ACTION_PREVIEW_WORDS = ("preview", "check", "validate", "review", "plan", "ready")


def _clean_draft_reference_text(value: str) -> str:
    text = str(value or "")
    for token in ("Ã‚Â·", "Â·", "\u00b7", "\u2022", "\u2013", "\u2014"):
        text = text.replace(token, " ")
    return re.sub(r"\s+", " ", text).strip()


def _normalize_draft_match_text(value: str) -> str:
    cleaned = _clean_draft_reference_text(value).lower()
    cleaned = re.sub(r"[\"'`]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" ,.;:!?-")


def _normalize_client_match_text(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    cleaned = re.sub(r"[_\-]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _candidate_matches_draft_name(candidate: str, draft_name: str) -> bool:
    normalized_candidate = _normalize_draft_match_text(candidate)
    normalized_draft = _normalize_draft_match_text(draft_name)
    if not normalized_candidate or not normalized_draft:
        return False
    if normalized_candidate == normalized_draft:
        return True
    if not normalized_candidate.startswith(normalized_draft):
        return False
    remainder = normalized_candidate[len(normalized_draft):].strip(" ,.;:!?-")
    if not remainder:
        return True
    return remainder.startswith(
        (
            "and post",
            "and publish",
            "and schedule",
            "and send",
            "post",
            "publish",
            "schedule",
            "send",
            "now",
            "tonight",
            "for approval",
            "today",
            "tomorrow",
            "this evening",
            "this afternoon",
            "this morning",
            "by ",
            "next ",
            "at ",
            "on ",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )
    )


def _lookup_client_draft_refs(client_id: str) -> list[dict]:
    bundles = list_client_drafts(client_id).get("bundles", {})
    refs = []
    if not isinstance(bundles, dict):
        return refs
    for draft_name, payload in bundles.items():
        name = str(draft_name or "").strip()
        if not name:
            continue
        refs.append(
            {
                "client_id": client_id,
                "draft_name": name,
                "draft_id": str((payload or {}).get("draft_id") or "").strip(),
            }
        )
    refs.sort(key=lambda item: len(item["draft_name"]), reverse=True)
    return refs


def _resolve_visible_draft_reference(client_id: str, candidate: str, provided_refs: list[dict]) -> dict | None:
    for ref in provided_refs:
        draft_name = str(ref.get("draft_name") or "").strip()
        if _candidate_matches_draft_name(candidate, draft_name):
            return {
                "client_id": client_id,
                "draft_name": draft_name,
                "draft_id": str(ref.get("draft_id") or "").strip(),
            }

    for ref in _lookup_client_draft_refs(client_id):
        draft_name = str(ref.get("draft_name") or "").strip()
        if _candidate_matches_draft_name(candidate, draft_name):
            return ref
    return None


def _default_single_draft_reference(client_id: str, provided_refs: list[dict]) -> dict | None:
    candidates = [ref for ref in provided_refs if str(ref.get("draft_name") or "").strip()]
    if not candidates:
        candidates = _lookup_client_draft_refs(client_id)
    if len(candidates) != 1:
        return None
    chosen = candidates[0]
    return {
        "client_id": client_id,
        "draft_name": str(chosen.get("draft_name") or "").strip(),
        "draft_id": str(chosen.get("draft_id") or "").strip(),
    }


def collect_explicit_draft_targets(prompt: str, provided_refs: list[dict] | None = None) -> list[dict]:
    raw = str(prompt or "")
    if not raw:
        return []

    provided_refs = [ref for ref in (provided_refs or []) if isinstance(ref, dict)]
    provided_by_client: dict[str, list[dict]] = {}
    for ref in provided_refs:
        client_id = resolve_client_id(str(ref.get("client_id") or "").strip())
        if not client_id:
            continue
        prepared = {
            "client_id": client_id,
            "draft_name": str(ref.get("draft_name") or "").strip(),
            "draft_id": str(ref.get("draft_id") or "").strip(),
        }
        provided_by_client.setdefault(client_id, []).append(prepared)

    targets: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for match in SMART_DRAFT_REF_RE.finditer(raw):
        client_id = resolve_client_id(str(match.group("client") or "").strip())
        draft_name = str(match.group("draft") or "").strip()
        draft_id = str(match.group("draft_id") or "").strip()
        if not client_id or not draft_name:
            continue
        key = (client_id.lower(), (draft_id or draft_name).lower())
        if key in seen:
            continue
        seen.add(key)
        targets.append({"client_id": client_id, "draft_name": draft_name, "draft_id": draft_id})

    mentions = list(ROBUST_CLIENT_MENTION_RE.finditer(raw))
    for index, match in enumerate(mentions):
        client_id = resolve_client_id(str(match.group("client") or "").strip())
        if not client_id:
            continue
        segment_end = mentions[index + 1].start() if index + 1 < len(mentions) else len(raw)
        segment = raw[match.end():segment_end]
        marker = ROBUST_DRAFT_MARKER_RE.search(segment)
        candidate = segment[marker.end():].strip() if marker else ""
        resolved = None
        if candidate:
            resolved = _resolve_visible_draft_reference(client_id, candidate, provided_by_client.get(client_id, []))
        if not resolved:
            resolved = _default_single_draft_reference(client_id, provided_by_client.get(client_id, []))
        if not resolved:
            continue
        key = (client_id.lower(), (resolved.get("draft_id") or resolved.get("draft_name") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        targets.append(resolved)

    raw_mentions = list(RAW_CLIENT_MENTION_RE.finditer(raw))
    for index, match in enumerate(raw_mentions):
        client_id = resolve_client_id(str(match.group("client") or "").strip())
        if not client_id:
            continue
        segment_end = raw_mentions[index + 1].start() if index + 1 < len(raw_mentions) else len(raw)
        segment = raw[match.end():segment_end]
        raw_candidate_match = re.search(
            r'^\s*\.\s*(?:draft\b\s*(?:[Â·â€¢:\-\u2013\u2014]|Ã‚Â·|Ãƒâ€šÃ‚Â·)?\s*)?(?P<draft>.+)$',
            segment,
            re.IGNORECASE,
        )
        candidate = str(raw_candidate_match.group("draft") or "").strip() if raw_candidate_match else ""
        resolved = None
        if candidate:
            resolved = _resolve_visible_draft_reference(client_id, candidate, provided_by_client.get(client_id, []))
        if not resolved:
            resolved = _default_single_draft_reference(client_id, provided_by_client.get(client_id, []))
        if not resolved:
            continue
        key = (client_id.lower(), (resolved.get("draft_id") or resolved.get("draft_name") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        targets.append(resolved)

    return targets


def _normalize_clause_text(raw_clause: str) -> str:
    text = normalize_prompt_date_typos(raw_clause)
    text = re.sub(r"\s+", " ", text).strip(" ,;\n\t")
    text = re.sub(r"^(?:and\s+(?:also\s+|then\s+)?)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdate\s+(\d{1,2})(st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\bat\s+exactly\b", "at", text, flags=re.IGNORECASE)
    return text.strip()


def _split_release_clauses(prompt: str) -> list[str]:
    raw = str(prompt or "").strip()
    if not raw:
        return []
    parts = [segment.strip() for segment in CLAUSE_SPLIT_RE.split(raw) if str(segment or "").strip()]
    merged: list[str] = []
    for part in parts:
        if merged and not re.search(r'@\[[^\]]+\]|@\w+', part):
            merged[-1] = f"{merged[-1]} {part}".strip()
            continue
        merged.append(part)
    return merged


def _format_clause_time(text: str) -> str | None:
    match = TIME_WINDOW_RE.search(str(text or ""))
    if not match:
        return None
    hour = match.group(0)
    try:
        parsed = parse_time_string(hour)
    except Exception:
        return None
    return datetime.combine(datetime.now().date(), parsed).strftime("%I:%M %p")


def _resolve_loose_weekday(token: str) -> str | None:
    lowered = str(token or "").strip().lower()
    weekdays = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    if lowered not in weekdays:
        return None
    today = datetime.now().date()
    target = weekdays.index(lowered)
    delta = (target - today.weekday()) % 7
    resolved = today + timedelta(days=delta)
    return resolved.isoformat()


def _extract_clause_schedule(raw_clause: str) -> tuple[dict | None, str | None]:
    clause = _normalize_clause_text(raw_clause)
    lower = clause.lower()
    has_schedule_language = bool(
        TIME_WINDOW_RE.search(lower)
        or DATE_TOKEN_RE.search(lower)
        or any(token in lower for token in SCHEDULE_WORDS)
    )
    if not has_schedule_language:
        return None, None

    formatted_time = _format_clause_time(clause)
    date_value = None
    date_match = DATE_TOKEN_RE.search(clause)
    if date_match:
        token = str(date_match.group(0) or "").strip()
        resolved = resolve_date_phrase(token)
        if not resolved and token.lower() in {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}:
            loose = _resolve_loose_weekday(token)
            date_value = loose
        elif resolved:
            date_value = resolved.isoformat()

    if formatted_time and date_value:
        return {"scheduled_date": date_value, "time": formatted_time}, None

    if "schedule" in lower or has_schedule_language:
        if not date_value and not formatted_time:
            return None, f"Jarvis needs an exact release date and time for this clause: {clause}"
        if not date_value:
            return None, f"Jarvis needs a release date for this clause: {clause}"
        if not formatted_time:
            return None, f"Jarvis needs an exact release time for this clause: {clause}"

    return None, None


def _resolve_clause_action(raw_clause: str, schedule_payload: dict | None) -> tuple[str | None, str | None]:
    clause = _normalize_clause_text(raw_clause)
    lower = clause.lower()
    immediate = contains_immediate_intent(lower)
    publish_language = any(keyword in lower for keyword in BATCH_POST_WORDS)
    schedule_language = "schedule" in lower or bool(schedule_payload)

    if immediate and not schedule_payload:
        return "post_now", None
    if schedule_payload:
        return "schedule", None
    if schedule_language:
        return None, f"Jarvis needs both a date and time before it can schedule this clause: {clause}"
    if publish_language:
        return None, f"Jarvis needs either 'now' or an exact release window for this clause: {clause}"
    if any(keyword in lower for keyword in ACTION_PREVIEW_WORDS):
        return None, f"Preview-only clause detected without an executable release action: {clause}"
    return None, f"Jarvis could not infer whether this clause should post now or schedule later: {clause}"


def parse_multi_clause_release_request(prompt: str, draft_refs: list[dict] | None = None) -> dict | None:
    raw_prompt = str(prompt or "").strip()
    if not raw_prompt:
        return None

    clauses = _split_release_clauses(raw_prompt)
    if not clauses:
        return None

    tasks: list[dict] = []
    warnings: list[str] = []

    for clause in clauses:
        normalized_clause = _normalize_clause_text(clause)
        if not normalized_clause:
            continue
        if not re.search(r'@\[[^\]]+\]|@\w+', normalized_clause):
            continue

        explicit_refs = collect_explicit_draft_targets(normalized_clause, draft_refs)
        if len(explicit_refs) != 1:
            warning = (
                f"Jarvis could not isolate one draft in this clause: {normalized_clause}"
                if not explicit_refs
                else f"Jarvis found multiple draft targets in one clause and needs them separated: {normalized_clause}"
            )
            warnings.append(warning)
            tasks.append(
                {
                    "client_id": "",
                    "client_label": "",
                    "draft_id": "",
                    "draft_label": "",
                    "action": "",
                    "scheduled_date": "",
                    "time": "",
                    "source_text": normalized_clause,
                    "status": "ambiguous",
                    "warning": warning,
                }
            )
            continue

        ref = explicit_refs[0]
        schedule_payload, schedule_warning = _extract_clause_schedule(normalized_clause)
        action, action_warning = _resolve_clause_action(normalized_clause, schedule_payload)
        warning = schedule_warning or action_warning
        status = "ready" if not warning and action else "ambiguous"
        if warning:
            warnings.append(warning)

        tasks.append(
            {
                "client_id": str(ref.get("client_id") or "").strip(),
                "client_label": str(ref.get("client_id") or "").strip(),
                "draft_id": str(ref.get("draft_id") or "").strip(),
                "draft_label": str(ref.get("draft_name") or "").strip(),
                "action": str(action or "").strip(),
                "scheduled_date": str((schedule_payload or {}).get("scheduled_date") or "").strip(),
                "time": str((schedule_payload or {}).get("time") or "").strip(),
                "source_text": normalized_clause,
                "status": status,
                "warning": str(warning or "").strip(),
            }
        )

    actionable = [task for task in tasks if task.get("client_id") or task.get("status") == "ambiguous"]
    if not actionable:
        return None

    requires_confirmation = len([task for task in tasks if task.get("status") == "ready"]) > 1 or any(
        str(task.get("action") or "").strip().lower() == "schedule" for task in tasks
    )
    return {
        "tasks": tasks,
        "warnings": warnings,
        "requires_confirmation": requires_confirmation,
    }


def maybe_execute_explicit_batch_publish(agent: Agent, prompt: str, draft_refs: list[dict] | None = None) -> dict | None:
    raw_prompt = str(prompt or "").strip()
    if not raw_prompt:
        return None

    explicit_refs = collect_explicit_draft_targets(raw_prompt, draft_refs)
    has_explicit_draft_syntax = bool(ROBUST_CLIENT_MENTION_RE.search(raw_prompt) and re.search(r"\bdraft\b", raw_prompt, re.IGNORECASE))
    if has_explicit_draft_syntax and not explicit_refs:
        return {
            "reply": (
                "Jarvis couldn't resolve those draft references. Use the exact client and draft labels shown in the dashboard, "
                "for example `@[Veloura Studio] Draft · Fashion now`."
            )
        }

    lower_prompt = raw_prompt.lower()
    if not explicit_refs:
        return None
    if prompt_implies_scheduling(raw_prompt):
        return None
    if any(keyword in lower_prompt for keyword in ("approval", "approve", "whatsapp", "review")):
        return None
    if not contains_immediate_intent(raw_prompt) and not any(keyword in lower_prompt for keyword in BATCH_POST_WORDS):
        return None

    tool = getattr(agent, "tool_map", {}).get("trigger_pipeline_now")
    if not tool:
        return {"reply": "Jarvis could not access the immediate publish tool."}

    messages: list[str] = []
    for ref in explicit_refs:
        tool_result = tool.execute(
            client_id=ref["client_id"],
            bundle_name=ref.get("draft_name"),
            draft_id=ref.get("draft_id") or None,
            topic=ref.get("draft_name") or None,
        )
        if isinstance(tool_result, dict):
            messages.append(
                str(
                    tool_result.get("message")
                    or tool_result.get("error")
                    or f"Processed {ref['client_id']} · {ref.get('draft_name') or 'draft'}."
                ).strip()
            )
        else:
            messages.append(str(tool_result).strip())

    return {"reply": summarize_multi_publish_results(messages)}


def _within_one_edit(token: str, target: str) -> bool:
    token = str(token or '').strip().lower()
    target = str(target or '').strip().lower()
    if token == target:
        return True
    if abs(len(token) - len(target)) > 1:
        return False
    if len(token) == len(target):
        return sum(1 for a, b in zip(token, target) if a != b) <= 1
    if len(token) + 1 == len(target):
        token, target = target, token
    i = j = edits = 0
    while i < len(token) and j < len(target):
        if token[i] == target[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        i += 1
    return True


def contains_immediate_intent(prompt: str) -> bool:
    text = f' {str(prompt or '').strip().lower()} '
    if not text.strip():
        return False
    if any(keyword in text for keyword in IMMEDIATE_WORDS):
        return True
    tokens = re.findall(r'[a-z]+', text)
    if not any(token in {'post', 'publish'} for token in tokens):
        return False
    return any(_within_one_edit(token, 'now') for token in tokens)

def prompt_implies_scheduling(prompt: str) -> bool:
    text = f" {str(prompt or '').strip().lower()} "
    if not text.strip():
        return False
    if contains_immediate_intent(text):
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
    if not raw_id:
        return raw_id
    try:
        client_ids = get_client_store().list_client_ids()
    except Exception:
        client_ids = []
    for client_id in client_ids:
        if client_id.lower() == raw_id.lower():
            return client_id
    normalized_raw = _normalize_client_match_text(raw_id)
    for client_id in client_ids:
        if _normalize_client_match_text(client_id) == normalized_raw:
            return client_id
    return raw_id

def verify_meta_token(client_id: str):
    import requests
    access_token = os.getenv("META_ACCESS_TOKEN")
    try:
        cdata = get_client_store().get_client(client_id) or {}
        access_token = cdata.get("meta_access_token", access_token)
    except Exception:
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


def extract_pipeline_status(output: str) -> tuple[str, str]:
    raw = str(output or "")
    status = "unknown"
    message = ""
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("PIPELINE_STATUS:"):
            status = stripped.split(":", 1)[1].strip().lower() or "unknown"
        elif stripped.startswith("PIPELINE_MESSAGE:"):
            message = stripped.split(":", 1)[1].strip()
    return status, message


def extract_pipeline_platform_breakdown(output: str) -> dict[str, dict[str, str]]:
    platforms: dict[str, dict[str, str]] = {}
    current_platform = ""
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if line.startswith("Facebook:"):
            current_platform = "facebook"
            status_text = line.split(":", 1)[1].strip()
            platforms[current_platform] = {
                "status": status_text.split()[0].lower() if status_text else "unknown",
                "detail": status_text,
            }
            continue
        if line.startswith("Instagram:"):
            current_platform = "instagram"
            status_text = line.split(":", 1)[1].strip()
            platforms[current_platform] = {
                "status": status_text.split()[0].lower() if status_text else "unknown",
                "detail": status_text,
            }
            continue
        if current_platform and line.startswith("Error:"):
            platforms[current_platform]["error"] = line.replace("Error:", "").strip()
            continue
        if current_platform and line.startswith("Step:"):
            platforms[current_platform]["step"] = line.replace("Step:", "").strip()
            continue
    return platforms


def classify_pipeline_outcome(output: str, pipeline_status: str) -> tuple[str, str]:
    status = str(pipeline_status or "unknown").strip().lower() or "unknown"
    breakdown = extract_pipeline_platform_breakdown(output)
    statuses = [str(item.get("status") or "").strip().lower() for item in breakdown.values() if item]
    if status in {"error", "partial_success", "success"}:
        return status, status
    if statuses and all(item == "error" for item in statuses):
        return "error", "derived"
    if statuses and any(item == "published" for item in statuses) and any(item == "error" for item in statuses):
        return "partial_success", "derived"
    if statuses and all(item == "published" for item in statuses):
        return "success", "derived"
    return status, "raw"


def summarize_pipeline_publish_success(output: str, client_id: str, pipeline_message: str) -> str:
    breakdown = extract_pipeline_platform_breakdown(output)
    parts = []
    fb = breakdown.get("facebook", {})
    ig = breakdown.get("instagram", {})
    if fb.get("status") == "published":
        parts.append(f"Facebook {fb.get('detail') or 'published'}")
    if ig.get("status") == "published":
        parts.append(f"Instagram {ig.get('detail') or 'published'}")
    if parts:
        return f"Pipeline completed successfully for {client_id}. " + " ".join(parts)
    if pipeline_message:
        return f"Pipeline completed successfully for {client_id}. {pipeline_message}"
    return f"Pipeline completed successfully for {client_id}."


def summarize_multi_publish_results(messages: list[str]) -> str:
    cleaned = [str(item).strip() for item in (messages or []) if str(item).strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    return "Batch publish results:\n- " + "\n- ".join(cleaned)


def resolve_saved_draft_reference(client_id: str, bundle_name: str | None = None, topic: str | None = None, draft_id: str | None = None) -> dict | None:
    for candidate, source in ((bundle_name, "bundle_name"), (topic, "topic")):
        payload = resolve_draft_payload(client_id, draft_name=candidate, draft_id=draft_id)
        if not payload:
            continue
        resolved_name = str(payload.get("bundle_name") or payload.get("draft_name") or candidate or "").strip()
        payload, images, videos = get_draft_media_paths(
            client_id,
            draft_name=resolved_name,
            draft_id=str(payload.get("draft_id") or draft_id or "").strip() or None,
        )
        if not payload:
            continue
        return {
            "bundle_name": resolved_name,
            "payload": payload,
            "images": images,
            "videos": videos,
            "matched_from": "draft_id" if draft_id else source,
        }

    if draft_id:
        payload = resolve_draft_payload(client_id, draft_id=draft_id)
        if payload:
            resolved_name = str(payload.get("bundle_name") or payload.get("draft_name") or bundle_name or topic or "").strip()
            payload, images, videos = get_draft_media_paths(
                client_id,
                draft_name=resolved_name,
                draft_id=str(payload.get("draft_id") or draft_id or "").strip() or None,
            )
            if payload:
                return {
                    "bundle_name": resolved_name,
                    "payload": payload,
                    "images": images,
                    "videos": videos,
                    "matched_from": "draft_id",
                }

    return None


def extract_forced_draft_refs(prompt: str) -> list[dict]:
    refs = []
    raw = str(prompt or "")
    for match in SMART_DRAFT_REF_RE.finditer(raw):
        refs.append(
            {
                "client_id": resolve_client_id(str(match.group("client") or "").strip()),
                "draft_id": str(match.group("draft_id") or "").strip(),
                "draft_name": str(match.group("draft") or "").strip(),
            }
        )
    return [ref for ref in refs if ref["client_id"] and ref["draft_id"]]


def inject_forced_draft_reference(tool_input: dict, draft_refs: list[dict]) -> dict:
    if not isinstance(tool_input, dict) or not draft_refs:
        return tool_input
    client_id = resolve_client_id(str(tool_input.get("client_id") or "").strip())
    if not client_id:
        return tool_input

    refs_for_client = [ref for ref in draft_refs if ref.get("client_id") == client_id]
    if not refs_for_client:
        return tool_input

    if str(tool_input.get("draft_id") or "").strip():
        return tool_input

    bundle_name = str(tool_input.get("bundle_name") or "").strip()
    topic = str(tool_input.get("topic") or "").strip()

    matched = None
    if bundle_name:
        matched = next((ref for ref in refs_for_client if ref.get("draft_name", "").lower() == bundle_name.lower()), None)
    if matched is None and topic:
        matched = next((ref for ref in refs_for_client if ref.get("draft_name", "").lower() == topic.lower()), None)
    if matched is None and len(refs_for_client) == 1:
        matched = refs_for_client[0]

    if not matched:
        return tool_input

    enriched = dict(tool_input)
    enriched["draft_id"] = matched["draft_id"]
    if not bundle_name and matched.get("draft_name"):
        enriched["bundle_name"] = matched["draft_name"]
    return enriched

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
        files = [asset.get("filename") for asset in list_client_assets(client_id) if asset.get("filename")]
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
        try:
            data = list_client_drafts(client_id).get("bundles", {})
            return {"client_id": client_id, "bundles": data}
        except Exception:
            return {"error": "Failed to load saved creative drafts."}

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
        payload = get_client_store().get_client(client_id)
        if not payload:
            return {"error": f"Profile '{client_id}' not found."}
        return payload

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
                        "draft_id": {"type": "string", "description": "Stable draft identifier when a saved creative draft was selected from the dashboard draft picker."},
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
    def execute(self, client_id, days, post_time, topic=None, image=None, bundle_name=None, scheduled_date=None, draft_id=None):
        client_id = resolve_client_id(client_id)
        
        # PRE-FLIGHT SAFETY CHECK
        token_err = verify_meta_token(client_id)
        if token_err:
            return {"error": f"❌ PRE-FLIGHT VERIFICATION FAILED: {token_err}\nTell the user they must update the client's Live Credentials in the dashboard securely before scheduling this."}
            
        if not topic:
            topic = f"Scheduled {bundle_name}" if bundle_name else "Scheduled Post"
            
        try:
            resolved_draft = resolve_saved_draft_reference(client_id, bundle_name=bundle_name, topic=topic, draft_id=draft_id)
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
                if resolved_draft:
                    payload = resolved_draft["payload"]
                    images = resolved_draft["images"]
                    videos = resolved_draft["videos"]
                    if images:
                        rule["images"] = images
                    if videos:
                        rule["videos"] = videos
                    rule["draft_name"] = bundle_name
                    if payload.get("draft_id"):
                        rule["draft_id"] = payload.get("draft_id")
                    rule["media_kind"] = payload["bundle_type"]
                else:
                    payload, images, videos = get_draft_media_paths(client_id, bundle_name, draft_id=draft_id)
                    if not payload:
                        return {"error": f"Creative draft '{bundle_name}' not found in the client's vault queue. Use read_vault_queue first to inspect the available draft names."}
                    if images:
                        rule["images"] = images
                    if videos:
                        rule["videos"] = videos
                    rule["draft_name"] = str(payload.get("bundle_name") or bundle_name).strip()
                    if payload.get("draft_id"):
                        rule["draft_id"] = payload.get("draft_id")
                    rule["media_kind"] = payload["bundle_type"]
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
                "description": "CRITICAL: ALWAYS USE THIS TOOL whenever you are told to schedule a post, UNLESS explicitly told to 'skip approval' or 'force schedule'. Drafts the post payload, stores it in the approval queue, and pings the Agency Owner via WhatsApp with native Approve/Reject interactive buttons.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string", "description": "The EXACT client folder name"},
                        "topic": {"type": "string", "description": "Short topic or campaign angle for the draft"},
                        "days": {"type": "array", "items": {"type": "string"}, "description": "Legacy weekday list or relative phrase holder. Use scheduled_date for one-off calendar dates whenever possible."},
                        "scheduled_date": {"type": "string", "description": "Preferred one-off calendar date in YYYY-MM-DD after resolving phrases like next Friday or April 21."},
                        "time": {"type": "string", "description": "Time string e.g. '04:30 PM'"},
                        "bundle_name": {"type": "string", "description": "If scheduling a saved creative draft, the exact draft name from the queue (for example 'Reel 1' or 'Carousel 2')."},
                        "draft_id": {"type": "string", "description": "Stable draft identifier when a saved creative draft was selected from the dashboard draft picker."},
                        "image": {"type": "string", "description": "If scheduling a single image, the filename"}
                    },
                    "required": ["client_id", "topic", "days", "time"]
                }
            }
        }
        
    def execute(self, client_id, topic, days, time, bundle_name=None, image=None, scheduled_date=None, draft_id=None, approval_routing_override=None):
        try:
            import uuid
            from webhook_server import build_approval_preview, get_agency_config, get_approval_routing_mode, normalize_approval_routing_mode, send_pending_approval_to_whatsapp

            client_id = resolve_client_id(client_id)
            caption_preview_line = ""
            resolved_draft = resolve_saved_draft_reference(client_id, bundle_name=bundle_name, topic=topic, draft_id=draft_id)
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
                if resolved_draft:
                    payload = resolved_draft["payload"]
                    images = resolved_draft["images"]
                    videos = resolved_draft["videos"]
                    if images:
                        rule["images"] = images
                    if videos:
                        rule["videos"] = videos
                    rule["draft_name"] = bundle_name
                    if payload.get("draft_id"):
                        rule["draft_id"] = payload.get("draft_id")
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
                    payload, images, videos = get_draft_media_paths(client_id, bundle_name, draft_id=draft_id)
                    if not payload:
                        return {"error": f"Creative draft '{bundle_name}' not found."}
                    if images:
                        rule["images"] = images
                    if videos:
                        rule["videos"] = videos
                    rule["draft_name"] = str(payload.get("bundle_name") or bundle_name).strip()
                    if payload.get("draft_id"):
                        rule["draft_id"] = payload.get("draft_id")
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
            elif image:
                rule["images"] = [f"assets/{client_id}/{image}"]
                rule["media_kind"] = "image_single"

            approval_id = uuid.uuid4().hex[:8].upper()
            rule["approval_id"] = approval_id
            override_mode = normalize_approval_routing_mode(approval_routing_override) if approval_routing_override else ""
            rule["approval_routing"] = override_mode or get_approval_routing_mode()
            rule["whatsapp_sent"] = False

            save_pending_approval(rule)

            owner_phone = get_agency_config().get("owner_phone", "")
            routing_mode = rule["approval_routing"]
            if routing_mode == "desktop_first":
                return {
                    "status": "success",
                    "message": f"Draft prepared. Approval {approval_id} is ready in Jarvis for desktop review.",
                    "approval_id": approval_id,
                    "job_id": rule["job_id"],
                    "whatsapp_sent": False,
                }

            if owner_phone:
                send_result = send_pending_approval_to_whatsapp(approval_id, phone=owner_phone)
                if send_result.get("success"):
                    return {
                        "status": "success",
                        "message": f"Draft prepared. Sent approval card {approval_id} to the agency owner's WhatsApp mobile control lane.",
                        "approval_id": approval_id,
                        "job_id": rule["job_id"],
                        "whatsapp_sent": True,
                    }
                return {
                    "status": "partial_success",
                    "message": f"Approval {approval_id} is ready in Jarvis, but WhatsApp send failed: {send_result.get('error', 'Unknown Meta API failure.')}",
                    "approval_id": approval_id,
                    "job_id": rule["job_id"],
                    "whatsapp_sent": False,
                }
            return {
                "status": "partial_success",
                "message": f"Approval {approval_id} is ready in Jarvis, but OWNER_PHONE is missing from Agency Settings.",
                "approval_id": approval_id,
                "job_id": rule["job_id"],
                "whatsapp_sent": False,
            }
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
                        "bundle_name": {"type": "string", "description": "Optional creative draft name from the queue (for example 'Reel 1', 'Carousel 2', or 'Image Post 3')."},
                        "draft_id": {"type": "string", "description": "Stable draft identifier when a saved creative draft was selected from the dashboard draft picker."}
                    },
                    "required": ["client_id"]
                }
            }
        }
    def execute(self, client_id, topic=None, image=None, bundle_name=None, post_time=None, time=None, days=None, scheduled_date=None, draft_id=None, **kwargs):
        import subprocess, sys
        client_id = resolve_client_id(client_id)
        
        # PRE-FLIGHT SAFETY CHECK
        token_err = verify_meta_token(client_id)
        if token_err:
            return {"error": f"❌ PRE-FLIGHT VERIFICATION FAILED: {token_err}\nTell the user they must update the client's Live Credentials in the dashboard securely before running this pipeline."}
            
        try:
            resolved_draft = resolve_saved_draft_reference(client_id, bundle_name=bundle_name, topic=topic, draft_id=draft_id)
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
                if resolved_draft:
                    images = resolved_draft["images"]
                    videos = resolved_draft["videos"]
                    for img in images:
                        cmd += ["--image", img]
                    for video in videos:
                        cmd += ["--video", video]
                    cmd += ["--draft-name", bundle_name]
                else:
                    payload, images, videos = get_draft_media_paths(client_id, bundle_name, draft_id=draft_id)
                    if not payload:
                        return {"error": f"Creative draft '{bundle_name}' not found."}
                    for img in images:
                        cmd += ["--image", img]
                    for video in videos:
                        cmd += ["--video", video]
                    cmd += ["--draft-name", bundle_name]
            elif image:
                cmd += ["--image", f"assets/{client_id}/{image}"]
            
            logger.info(f"TriggerPipelineNow | Spawning pipeline for {client_id}...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            output = result.stdout + result.stderr
            
            pipeline_status, pipeline_message = extract_pipeline_status(output)
            normalized_status, _ = classify_pipeline_outcome(output, pipeline_status)

            if result.returncode != 0 or normalized_status == "error":
                reason = extract_pipeline_failure_reason(output)
                return {
                    "error": f"Immediate publish failed for {client_id}: {reason}",
                    "output": output[-1500:]
                }
            if normalized_status == "partial_success":
                breakdown = extract_pipeline_platform_breakdown(output)
                fb = breakdown.get("facebook", {})
                ig = breakdown.get("instagram", {})
                parts = []
                if fb.get("status") == "published":
                    parts.append("Facebook posted successfully")
                elif fb.get("status") == "error":
                    parts.append(f"Facebook failed: {fb.get('error') or fb.get('detail')}")
                if ig.get("status") == "published":
                    parts.append("Instagram posted successfully")
                elif ig.get("status") == "error":
                    ig_detail = ig.get("error") or ig.get("detail") or "Instagram failed during publish."
                    if ig.get("step"):
                        ig_detail = f"{ig_detail} (step: {ig.get('step')})"
                    parts.append(f"Instagram failed: {ig_detail}")
                return {
                    "status": "partial_success",
                    "message": "Immediate publish partially succeeded for "
                    f"{client_id}. " + (" ".join(parts) if parts else (pipeline_message or "At least one platform published successfully while another failed.")),
                    "output": output[-1500:],
                }
            else:
                return {
                    "status": "success",
                    "message": summarize_pipeline_publish_success(output, client_id, pipeline_message),
                    "output": output[-1500:],
                }
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
        cdata = get_client_store().get_client(client_id)
        if not cdata:
            return {"error": f"Client '{client_id}' not found. Register them in the dashboard first."}
        
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
        jarvis_model = os.getenv("JARVIS_MODEL", "").strip()
        if not jarvis_model:
            jarvis_model = "openai/gpt-4o-mini" if os.getenv("OPENROUTER_API_KEY") else "gpt-4o-mini"
        super().__init__(tools, model=jarvis_model)
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
            "4b. If requested to immediately publish multiple drafts or multiple clients now, execute `trigger_pipeline_now` MULTIPLE TIMES IN THE SAME TURN, once per requested draft/client, then summarize all outcomes together. "
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

def run_orchestrator(user_input: str, draft_refs: list[dict] | None = None, original_request: str | None = None):
    global _global_agent
    agent = _global_agent
    # Reset message history per request to prevent unbounded memory growth (C-06)
    agent.messages = []
    original_request = original_request or user_input
    forced_draft_refs = collect_explicit_draft_targets(original_request, draft_refs) or draft_refs or extract_forced_draft_refs(original_request)
    explicit_batch_result = maybe_execute_explicit_batch_publish(agent, original_request, forced_draft_refs)
    if explicit_batch_result is not None:
        return explicit_batch_result
    max_turns = 10
    i = 0
    repeated_tool_rounds = 0
    last_tool_fingerprint = None
    last_error_message = None
    last_structured_action = None
    
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
            immediate_replies = []
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_input = json.loads(tool_call.function.arguments)
                except (json.JSONDecodeError, TypeError) as parse_err:
                    logger.error(f"Orchestrator | Failed to parse tool arguments for {tool_name}: {parse_err}")
                    agent.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"error": f"Invalid tool arguments from LLM for {tool_name}. Retry the request."})
                    })
                    continue
                tool_input = inject_forced_draft_reference(tool_input, forced_draft_refs)
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
                    logger.error(f"Tool {tool_name} crashed: {type(e).__name__}: {str(e)}", exc_info=True)
                    tool_result = {
                        "error": f"{tool_name} encountered an internal error: {type(e).__name__}: {str(e)}",
                    }

                if isinstance(tool_result, dict) and tool_result.get("error"):
                    round_errors.append(str(tool_result["error"]))
                    last_error_message = str(tool_result["error"])
                elif (
                    tool_name == "request_client_approval"
                    and isinstance(tool_result, dict)
                    and tool_result.get("status") == "success"
                    and tool_result.get("approval_id")
                ):
                    last_structured_action = {
                        "type": "approval_request",
                        "approval_id": str(tool_result.get("approval_id") or "").strip(),
                        "job_id": str(tool_result.get("job_id") or "").strip(),
                        "message": str(tool_result.get("message") or "").strip(),
                    }
                elif (
                    tool_name == "trigger_pipeline_now"
                    and isinstance(tool_result, dict)
                    and tool_result.get("status") == "partial_success"
                ):
                    immediate_replies.append(str(tool_result.get("message") or "").strip())
                elif (
                    tool_name == "trigger_pipeline_now"
                    and isinstance(tool_result, dict)
                    and tool_result.get("status") == "success"
                ):
                    immediate_replies.append(str(tool_result.get("message") or "").strip())
                elif (
                    tool_name == "trigger_pipeline_now"
                    and isinstance(tool_result, dict)
                    and tool_result.get("error")
                ):
                    immediate_replies.append(str(tool_result.get("error") or "").strip())
                    
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
                    return {
                        "reply": "Jarvis got stuck resolving the request because the target client context was unclear. Please retry with an explicit client mention like `@burger_grillz schedule Reel 1 for tomorrow at 12:10 PM`."
                    }
                return {"reply": round_errors[-1]}

            if immediate_replies:
                return {"reply": summarize_multi_publish_results(immediate_replies)}

            user_input = "" 
        else:
            final_reply = str(message.content or "").strip()
            if not final_reply and last_structured_action:
                final_reply = str(last_structured_action.get("message") or "").strip()
            payload = {"reply": final_reply}
            if last_structured_action:
                payload["action"] = last_structured_action
            return payload
            
    if last_error_message:
        return {"reply": last_error_message}
    return {
        "reply": "Jarvis reached its orchestration safety limit without resolving the request. Retry with a more explicit scheduling target, preferably including the client mention and exact date."
    }
