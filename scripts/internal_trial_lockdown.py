#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import difflib
import json
import mimetypes
import os
import re
import subprocess
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DEFAULT_FIXTURES_PATH = ROOT / "scripts" / "internal_trial_fixtures.json"
DEFAULT_REPORT_DIR = ROOT / "tmp"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = (10, 180)
AI_SMELL_PHRASES = {
    "unleash",
    "elevate your",
    "transform your",
    "game changer",
    "must-have",
    "whether you're",
    "step into",
    "discover the perfect",
    "experience the ultimate",
    "designed to",
}
TERMINAL_RUN_STATUSES = {"completed", "failed", "partial_success"}
SUCCESSFUL_ITEM_STATUSES = {"published", "scheduled", "approval_ready", "approval_sent_whatsapp", "completed", "partial_success"}
ARABIC_CHAR_RE = re.compile(r"[\u0600-\u06FF]")
WORD_RE = re.compile(r"[A-Za-z\u0600-\u06FF0-9#']+")


class HarnessError(RuntimeError):
    pass


@dataclass
class CheckOutcome:
    name: str
    passed: bool
    details: str
    severity: str = "error"
    payload: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        data = {
            "name": self.name,
            "passed": self.passed,
            "details": self.details,
            "severity": self.severity,
        }
        if self.payload is not None:
            data["payload"] = self.payload
        return data


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_fixture_value(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("env:"):
        return os.getenv(value.split(":", 1)[1], "").strip()
    if isinstance(value, dict):
        return {key: resolve_fixture_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_fixture_value(item) for item in value]
    return value


def normalize_words(text: str) -> list[str]:
    return [match.group(0).strip().lower() for match in WORD_RE.finditer(str(text or ""))]


def arabic_character_count(text: str) -> int:
    return len(ARABIC_CHAR_RE.findall(str(text or "")))


def language_match(expected: str, text: str) -> tuple[bool, str]:
    expected_key = str(expected or "").strip().lower()
    arabic_chars = arabic_character_count(text)
    latin_chars = len(re.findall(r"[A-Za-z]", str(text or "")))
    if expected_key == "arabic":
        passed = arabic_chars >= max(10, latin_chars)
        return passed, f"Arabic chars={arabic_chars}, Latin chars={latin_chars}"
    if expected_key == "english":
        passed = arabic_chars <= 4 and latin_chars >= 25
        return passed, f"Arabic chars={arabic_chars}, Latin chars={latin_chars}"
    if expected_key == "bilingual":
        passed = arabic_chars >= 6 and latin_chars >= 15
        return passed, f"Arabic chars={arabic_chars}, Latin chars={latin_chars}"
    return True, f"Language expectation '{expected_key}' not enforced."


def text_contains_any(text: str, phrases: list[str]) -> bool:
    haystack = str(text or "").lower()
    return any(str(phrase or "").strip().lower() in haystack for phrase in phrases if str(phrase or "").strip())


def collect_service_tokens(services: list[str]) -> set[str]:
    tokens: set[str] = set()
    for service in services:
        for token in normalize_words(service):
            if len(token) >= 4 and token not in {"with", "from", "your", "that", "this", "for", "into"}:
                tokens.add(token)
    return tokens


def caption_quality_checks(
    caption_text: str,
    expected_language: str,
    banned_words: list[str],
    services: list[str],
    seo_keyword_used: str,
) -> list[CheckOutcome]:
    caption_lower = str(caption_text or "").lower()
    service_tokens = collect_service_tokens(services)
    seo_keyword = str(seo_keyword_used or "").strip()
    seo_match = bool(seo_keyword) and seo_keyword.lower() in caption_lower
    service_match = any(token in caption_lower for token in service_tokens) if service_tokens else False
    smell_hit = next((phrase for phrase in AI_SMELL_PHRASES if phrase in caption_lower), "")
    language_ok, language_details = language_match(expected_language, caption_text)
    checks = [
        CheckOutcome("language_match", language_ok, language_details, payload={"expected": expected_language}),
        CheckOutcome(
            "banned_words_absent",
            not text_contains_any(caption_text, banned_words),
            "No banned words detected." if not text_contains_any(caption_text, banned_words) else "Caption contains one or more banned words.",
            payload={"banned_words": banned_words},
        ),
        CheckOutcome(
            "seo_keyword_used",
            seo_match,
            f"SEO keyword '{seo_keyword}' present in caption." if seo_match else f"SEO keyword '{seo_keyword}' was not surfaced in caption text.",
            payload={"seo_keyword_used": seo_keyword},
        ),
        CheckOutcome(
            "service_specificity",
            service_match,
            "Caption references a real service/product context." if service_match else "Caption stayed too generic and missed the service/product context.",
            payload={"services": services},
        ),
        CheckOutcome(
            "ai_smell_absent",
            not smell_hit,
            "No stale AI phrasing detected." if not smell_hit else f"Detected stale AI phrase: '{smell_hit}'.",
        ),
        CheckOutcome(
            "publishable_without_rewrite",
            bool(str(caption_text or "").strip()) and len(str(caption_text or "").strip()) >= 80,
            "Caption length and structure look usable." if len(str(caption_text or "").strip()) >= 80 else "Caption is too thin to feel publishable.",
        ),
    ]
    return checks


def evaluate_strategy_plan(plan: dict[str, Any], require_uncertainty: bool = False) -> list[CheckOutcome]:
    items = list(plan.get("items") or [])
    item_payload = []
    for item in items:
        item_payload.append(
            {
                "item_id": item.get("item_id"),
                "topic": item.get("topic"),
                "format": item.get("format"),
                "platforms": item.get("platforms"),
                "recommended_time": item.get("recommended_time"),
                "needs_review": item.get("needs_review"),
                "confidence": item.get("confidence"),
            }
        )
    structure_ok = all(
        str(item.get("topic") or "").strip()
        and str(item.get("format") or "").strip()
        and list(item.get("platforms") or [])
        and str(item.get("recommended_time") or "").strip()
        and str(item.get("rationale") or "").strip()
        for item in items
    )
    non_generic = all(len(str(item.get("topic") or "").strip()) >= 8 and len(str(item.get("rationale") or "").strip()) >= 20 for item in items)
    uncertainty_signaled = any(bool(item.get("needs_review")) or float(item.get("confidence") or 0) < 0.7 for item in items)
    checks = [
        CheckOutcome(
            "plan_has_items",
            bool(items),
            f"Plan returned {len(items)} items." if items else "Strategy plan returned no items.",
            payload={"items": item_payload},
        ),
        CheckOutcome(
            "plan_structure_complete",
            structure_ok,
            "Each item has topic, format, platforms, time, and rationale." if structure_ok else "One or more strategy items are structurally incomplete.",
            payload={"items": item_payload},
        ),
        CheckOutcome(
            "plan_non_generic",
            non_generic,
            "Topics and rationales feel specific enough." if non_generic else "Strategy items look too generic or underexplained.",
            payload={"items": item_payload},
        ),
    ]
    if require_uncertainty:
        checks.append(
            CheckOutcome(
                "low_context_uncertainty_signaled",
                uncertainty_signaled,
                "Plan surfaced needs-review / lower-confidence signals." if uncertainty_signaled else "Low-context plan looked overconfident and did not mark uncertainty.",
                payload={"items": item_payload},
            )
        )
    return checks


def build_raw_context(fixture: dict[str, Any], voice_examples_key: str = "voice_examples") -> str:
    context = dict(fixture.get("context") or {})
    quick = dict(fixture.get("quick_intake") or {})
    voice_examples = list(context.get(voice_examples_key) or [])
    do_rules = list(context.get("do_rules") or [])
    dont_rules = list(context.get("dont_rules") or [])
    seo_keywords = list(context.get("seo_keywords") or [])
    hashtags = list(context.get("hashtags") or [])
    lines = [
        f"Brand identity: {context.get('identity', '').strip()}",
        f"Positioning: {context.get('positioning', '').strip()}",
        f"Audience reality: {quick.get('target_audience', '').strip()}",
        f"Main offer lane: {quick.get('what_they_sell', '').strip()}",
        f"Primary market: {quick.get('city_market', '').strip()}",
        f"Language guidance: {context.get('dialect_notes', '').strip()}",
        "Brand voice examples:",
    ]
    lines.extend(f"- {example}" for example in voice_examples)
    if do_rules:
        lines.append("Do rules:")
        lines.extend(f"- {rule}" for rule in do_rules)
    if dont_rules:
        lines.append("Avoid rules:")
        lines.extend(f"- {rule}" for rule in dont_rules)
    if seo_keywords:
        lines.append("SEO keywords:")
        lines.append(", ".join(seo_keywords))
    if hashtags:
        lines.append("Hashtag bank:")
        lines.append(", ".join(hashtags))
    return "\n".join(part for part in lines if str(part or "").strip())


class JarvisInternalTrialHarness:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.base_url = str(args.base_url).rstrip("/")
        self.fixtures_path = Path(args.fixtures).resolve()
        self.report_dir = Path(args.report_dir).resolve()
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.password = args.password or os.getenv("JARVIS_ADMIN_PASSWORD", "").strip()
        self.run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.report_json_path = self.report_dir / f"internal-trial-lockdown-{self.run_timestamp}.json"
        self.report_md_path = self.report_dir / f"internal-trial-lockdown-{self.run_timestamp}.md"
        self.initial_agency_config: dict[str, Any] | None = None

    def api(self, method: str, path: str, *, expected: tuple[int, ...] = (200,), **kwargs: Any) -> Any:
        response = self.session.request(method, f"{self.base_url}{path}", timeout=DEFAULT_TIMEOUT, **kwargs)
        if response.status_code not in expected:
            text = response.text.strip()
            raise HarnessError(f"{method} {path} failed with {response.status_code}: {text}")
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise HarnessError(f"{method} {path} returned non-JSON content.") from exc

    def login(self) -> None:
        if not self.password:
            raise HarnessError("JARVIS_ADMIN_PASSWORD is missing. Export it or pass --password.")
        payload = self.api("POST", "/api/auth/login", json={"password": self.password})
        token = str(payload.get("token") or "").strip()
        if not token:
            raise HarnessError("Login succeeded without a session token.")
        self.session.headers.update({"x-jarvis-auth": token})

    def health(self) -> dict[str, Any]:
        return self.api("GET", "/api/health")

    def get_agency_config(self) -> dict[str, Any]:
        return self.api("GET", "/api/agency/config")

    def set_desktop_first_approval_routing(self) -> dict[str, Any]:
        current = self.get_agency_config()
        self.initial_agency_config = copy.deepcopy(current)
        payload = {
            "owner_phone": str(current.get("owner_phone") or "").strip(),
            "whatsapp_access_token": str(current.get("whatsapp_access_token") or "").strip(),
            "approval_routing": "desktop_first",
        }
        return self.api("POST", "/api/agency/config", json=payload)

    def restore_agency_config(self) -> dict[str, Any] | None:
        if self.initial_agency_config is None:
            return None
        payload = {
            "owner_phone": str(self.initial_agency_config.get("owner_phone") or "").strip(),
            "whatsapp_access_token": str(self.initial_agency_config.get("whatsapp_access_token") or "").strip(),
            "approval_routing": str(self.initial_agency_config.get("approval_routing") or "desktop_first").strip() or "desktop_first",
        }
        return self.api("POST", "/api/agency/config", json=payload)

    def delete_client_if_present(self, client_id: str) -> dict[str, Any]:
        return self.api("DELETE", f"/api/client/{requests.utils.quote(client_id, safe='')}", expected=(200, 404))

    def synthesize_client(self, fixture: dict[str, Any], *, raw_context: str) -> dict[str, Any]:
        payload = {
            "client_name": fixture["client_id"],
            "quick_intake": fixture["quick_intake"],
            "raw_context": raw_context,
            "website_url": str((fixture.get("optional_sources") or {}).get("website_url") or "").strip() or None,
            "social_url": str((fixture.get("optional_sources") or {}).get("social_url") or "").strip() or None,
        }
        return self.api("POST", "/api/synthesize-client", json=payload)

    def save_client_profile(self, fixture: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
        overrides = resolve_fixture_value(dict(fixture.get("save_overrides") or {}))
        payload = {
            "client_id": fixture["client_id"],
            "phone_number": str(overrides.get("phone_number") or "").strip() or None,
            "meta_access_token": str(overrides.get("meta_access_token") or "").strip(),
            "whatsapp_token": str(overrides.get("whatsapp_token") or "").strip() or None,
            "facebook_page_id": str(overrides.get("facebook_page_id") or "").strip(),
            "instagram_account_id": str(overrides.get("instagram_account_id") or "").strip(),
            "profile_json": profile,
        }
        return self.api("POST", "/api/save-client-profile", json=payload)

    def get_client(self, client_id: str) -> dict[str, Any]:
        return self.api("GET", f"/api/client/{requests.utils.quote(client_id, safe='')}")

    def update_client(self, client_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        return self.api("PUT", f"/api/client/{requests.utils.quote(client_id, safe='')}", json={"profile_json": profile})

    def upload_assets(self, fixture: dict[str, Any]) -> dict[str, Any]:
        assets = list(fixture.get("assets") or [])
        data = {"client_id": fixture["client_id"]}
        with ExitStack() as stack:
            file_payload = []
            for asset in assets:
                local_path = ROOT / str(asset.get("path") or "").strip()
                if not local_path.exists():
                    raise HarnessError(f"Fixture asset does not exist: {local_path}")
                handle = stack.enter_context(open(local_path, "rb"))
                mime_type = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"
                remote_name = str(asset.get("filename") or local_path.name).strip()
                file_payload.append(("files", (remote_name, handle, mime_type)))
            return self.api("POST", "/api/upload-bulk", data=data, files=file_payload)

    def create_bundle(self, client_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "bundle_name": bundle["bundle_name"],
            "files": bundle["files"],
            "bundle_type": bundle.get("bundle_type"),
        }
        return self.api("POST", f"/api/vault/{requests.utils.quote(client_id, safe='')}/bundles", json=payload)

    def generate_caption(self, client_id: str, bundle_name: str, topic: str, caption_mode: str = "ai") -> dict[str, Any]:
        payload = {"topic": topic, "caption_mode": caption_mode}
        return self.api(
            "POST",
            f"/api/vault/{requests.utils.quote(client_id, safe='')}/bundles/{requests.utils.quote(bundle_name, safe='')}/generate-caption",
            json=payload,
        )

    def save_manual_caption(self, client_id: str, bundle_name: str, caption_text: str, hashtags: list[str], seo_keyword_used: str) -> dict[str, Any]:
        payload = {
            "caption_text": caption_text,
            "hashtags": hashtags,
            "seo_keyword_used": seo_keyword_used,
            "caption_mode": "manual",
        }
        return self.api(
            "PUT",
            f"/api/vault/{requests.utils.quote(client_id, safe='')}/bundles/{requests.utils.quote(bundle_name, safe='')}/caption",
            json=payload,
        )

    def create_strategy_plan(self, client_id: str, window: str, goal: str = "", campaign_context: str = "") -> dict[str, Any]:
        payload = {
            "client_id": client_id,
            "window": window,
            "goal": goal or None,
            "campaign_context": campaign_context or None,
        }
        return self.api("POST", "/api/strategy/plans", json=payload)

    def materialize_strategy_plan(self, plan_id: str, item_ids: list[str] | None = None) -> dict[str, Any]:
        return self.api("POST", f"/api/strategy/plans/{requests.utils.quote(plan_id, safe='')}/materialize", json={"item_ids": item_ids or []})

    def create_orchestrator_plan(self, action: str, client_id: str, draft_name: str, scheduled_date: str | None = None, time_label: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": action,
            "items": [{"client_id": client_id, "draft_name": draft_name}],
        }
        if scheduled_date and time_label:
            payload["schedule"] = {"scheduled_date": scheduled_date, "time": time_label}
        return self.api("POST", "/api/orchestrator/plan", json=payload)

    def run_orchestrator_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        return self.api("POST", "/api/orchestrator/run", json={"plan": plan})

    def get_run(self, run_id: str) -> dict[str, Any]:
        payload = self.api("GET", f"/api/orchestrator/runs/{requests.utils.quote(run_id, safe='')}")
        return payload.get("run") or {}

    def wait_for_run(self, run_id: str, timeout_seconds: int = 90) -> dict[str, Any]:
        start = time.time()
        last = {}
        while (time.time() - start) < timeout_seconds:
            run = self.get_run(run_id)
            last = run
            if str(run.get("status") or "").strip().lower() in TERMINAL_RUN_STATUSES:
                return run
            time.sleep(1.5)
        raise HarnessError(f"Orchestrator run {run_id} did not finish within {timeout_seconds} seconds. Last state: {json.dumps(last)}")

    def list_pending_approvals(self) -> list[dict[str, Any]]:
        payload = self.api("GET", "/api/approvals/pending")
        return list(payload.get("approvals") or [])

    def approve_pending_approval(self, approval_id: str) -> dict[str, Any]:
        return self.api("POST", f"/api/approvals/{requests.utils.quote(approval_id, safe='')}/approve", json={})

    def reject_pending_approval(self, approval_id: str) -> dict[str, Any]:
        return self.api("POST", f"/api/approvals/{requests.utils.quote(approval_id, safe='')}/reject", json={})

    def move_pending_approval(self, approval_id: str, release_window: str) -> dict[str, Any]:
        return self.api("POST", f"/api/approvals/{requests.utils.quote(approval_id, safe='')}/move", json={"release_window": release_window})

    def schedule_snapshot(self) -> dict[str, Any]:
        return self.api("GET", "/api/schedule")

    def list_clients(self) -> list[str]:
        payload = self.api("GET", "/api/clients")
        return list(payload.get("clients") or [])

    def restart_server(self) -> CheckOutcome:
        command = str(self.args.restart_command or "").strip()
        if not command:
            return CheckOutcome("restart_recovery", False, "Restart command not provided. Recovery verification was skipped.", severity="warning")
        try:
            subprocess.run(command, shell=True, check=True, cwd=str(ROOT))
            time.sleep(float(self.args.restart_wait_seconds))
            health = self.health()
            clients = self.list_clients()
            if not health.get("readiness", {}).get("checks", {}).get("api", {}).get("ok"):
                return CheckOutcome("restart_recovery", False, "Server restarted but API readiness is still false.", payload={"health": health, "clients": clients})
            return CheckOutcome("restart_recovery", True, "FastAPI restart completed and the session token still worked.", payload={"health": health, "clients": clients})
        except Exception as exc:
            return CheckOutcome("restart_recovery", False, f"Restart verification failed: {exc}")

    def _tomorrow(self) -> str:
        return (date.today() + timedelta(days=1)).isoformat()

    def run_caption_suite(self, fixture: dict[str, Any], saved_profile: dict[str, Any]) -> dict[str, Any]:
        client_id = fixture["client_id"]
        bundles = list(fixture.get("drafts") or [])
        caption_topics = [{"bundle_name": bundle["bundle_name"], "topic": bundle["topic"]} for bundle in bundles[:3]]
        expected_language = str(((saved_profile.get("language_profile") or {}).get("caption_output_language") or fixture["quick_intake"].get("main_language") or "")).strip().lower()
        base_results = []
        for item in caption_topics:
            generated = self.generate_caption(client_id, item["bundle_name"], item["topic"])
            generated_payload = generated.get("generated") or {}
            caption_text = str(generated_payload.get("caption") or generated.get("draft", {}).get("caption_text") or "").strip()
            checks = caption_quality_checks(
                caption_text,
                expected_language,
                list(saved_profile.get("banned_words") or []),
                list(saved_profile.get("services") or []),
                str(generated_payload.get("seo_keyword_used") or generated.get("draft", {}).get("seo_keyword_used") or "").strip(),
            )
            fail_count = sum(1 for check in checks if not check.passed)
            base_results.append(
                {
                    "bundle_name": item["bundle_name"],
                    "topic": item["topic"],
                    "caption_text": caption_text,
                    "hashtags": generated_payload.get("hashtags") or generated.get("draft", {}).get("hashtags") or [],
                    "checks": [check.as_dict() for check in checks],
                    "fail_count": fail_count,
                    "passed": fail_count < 2,
                }
            )

        original_profile = copy.deepcopy(saved_profile)
        variant_profile = copy.deepcopy(saved_profile)
        variant_examples = list((fixture.get("context") or {}).get("voice_examples_variant") or [])
        if variant_examples:
            variant_profile["brand_voice_examples"] = variant_examples
        self.update_client(client_id, variant_profile)
        variant_generated = self.generate_caption(client_id, bundles[0]["bundle_name"], bundles[0]["topic"])
        variant_caption = str((variant_generated.get("generated") or {}).get("caption") or variant_generated.get("draft", {}).get("caption_text") or "").strip()
        baseline_caption = str(base_results[0]["caption_text"] or "")
        similarity = difflib.SequenceMatcher(a=baseline_caption, b=variant_caption).ratio() if baseline_caption and variant_caption else 1.0
        voice_shift = CheckOutcome(
            "voice_example_influence",
            similarity <= 0.88 and baseline_caption != variant_caption,
            "Swapping the voice examples changed the caption meaningfully." if similarity <= 0.88 and baseline_caption != variant_caption else "Swapping the voice examples did not move the caption enough.",
            payload={"baseline_caption": baseline_caption, "variant_caption": variant_caption, "similarity_ratio": round(similarity, 3)},
        )

        rules_profile = copy.deepcopy(saved_profile)
        banned_words = list((fixture.get("context") or {}).get("rules_pressure_banned_words") or [])
        if banned_words:
            rules_profile["banned_words"] = banned_words
        self.update_client(client_id, rules_profile)
        rules_topic = str((fixture.get("context") or {}).get("rules_pressure_topic") or bundles[1]["topic"]).strip()
        rules_generated = self.generate_caption(client_id, bundles[1]["bundle_name"], rules_topic)
        rules_caption = str((rules_generated.get("generated") or {}).get("caption") or rules_generated.get("draft", {}).get("caption_text") or "").strip()
        rules_check = CheckOutcome(
            "rules_pressure",
            not text_contains_any(rules_caption, banned_words),
            "Caption respected the banned-word rules." if not text_contains_any(rules_caption, banned_words) else "Caption still used one or more banned words after rule pressure.",
            payload={"caption_text": rules_caption, "banned_words": banned_words},
        )

        specificity_profile = copy.deepcopy(saved_profile)
        specificity_services = list((fixture.get("context") or {}).get("specificity_services") or saved_profile.get("services") or [])
        specificity_profile["services"] = specificity_services
        self.update_client(client_id, specificity_profile)
        specificity_topic = str((fixture.get("context") or {}).get("specificity_topic") or bundles[2]["topic"]).strip()
        specificity_generated = self.generate_caption(client_id, bundles[2]["bundle_name"], specificity_topic)
        specificity_caption = str((specificity_generated.get("generated") or {}).get("caption") or specificity_generated.get("draft", {}).get("caption_text") or "").strip()
        specificity_tokens = collect_service_tokens(specificity_services)
        specificity_ok = any(token in specificity_caption.lower() for token in specificity_tokens)
        specificity_check = CheckOutcome(
            "specificity_pressure",
            specificity_ok,
            "Caption surfaced the concrete service/product lane." if specificity_ok else "Caption stayed generic even after concrete services were injected.",
            payload={"caption_text": specificity_caption, "services": specificity_services},
        )

        self.update_client(client_id, original_profile)
        caption_suite_pass = all(item["passed"] for item in base_results) and voice_shift.passed and rules_check.passed and specificity_check.passed
        return {
            "suite_pass": caption_suite_pass,
            "base_brand_fit": base_results,
            "voice_example_influence": voice_shift.as_dict(),
            "rules_pressure": rules_check.as_dict(),
            "specificity_pressure": specificity_check.as_dict(),
        }

    def run_strategy_suite(self, fixture: dict[str, Any], saved_profile: dict[str, Any]) -> dict[str, Any]:
        client_id = fixture["client_id"]
        strategy_fixture = dict(fixture.get("strategy") or {})
        runs = []
        scenario_specs = [
            ("next_7_days", "next_7_days", str(strategy_fixture.get("weekly_goal") or strategy_fixture.get("campaign_goal") or "").strip(), ""),
            ("next_30_days", "next_30_days", str(strategy_fixture.get("monthly_goal") or strategy_fixture.get("campaign_goal") or "").strip(), ""),
            ("campaign_week", "next_7_days", str(strategy_fixture.get("campaign_goal") or "").strip(), str(strategy_fixture.get("campaign_context") or "").strip()),
        ]
        for name, window, goal, campaign_context in scenario_specs:
            created = self.create_strategy_plan(client_id, window, goal=goal, campaign_context=campaign_context)
            plan = created.get("plan") or {}
            checks = evaluate_strategy_plan(plan, require_uncertainty=False)
            runs.append(
                {
                    "scenario": name,
                    "plan_id": plan.get("plan_id"),
                    "window": window,
                    "goal": goal,
                    "campaign_context": campaign_context,
                    "checks": [check.as_dict() for check in checks],
                    "passed": all(check.passed for check in checks),
                    "plan": {"summary": plan.get("summary"), "objective": plan.get("objective"), "timeframe": plan.get("timeframe"), "items": plan.get("items")},
                }
            )

        original_profile = copy.deepcopy(saved_profile)
        low_context_profile = copy.deepcopy(saved_profile)
        low_context_profile["brand_voice_examples"] = []
        low_context_profile["seo_keywords"] = low_context_profile.get("seo_keywords", [])[:1]
        low_context_profile["hashtag_bank"] = []
        low_context_profile["dos_and_donts"] = []
        low_context_profile["banned_words"] = []
        self.update_client(client_id, low_context_profile)
        low_context_created = self.create_strategy_plan(
            client_id,
            "next_7_days",
            goal=str(strategy_fixture.get("low_context_goal") or "Keep the client active without inventing fake offers.").strip(),
            campaign_context="",
        )
        low_context_plan = low_context_created.get("plan") or {}
        low_context_checks = evaluate_strategy_plan(low_context_plan, require_uncertainty=True)
        runs.append(
            {
                "scenario": "low_context",
                "plan_id": low_context_plan.get("plan_id"),
                "window": "next_7_days",
                "goal": str(strategy_fixture.get("low_context_goal") or "").strip(),
                "campaign_context": "",
                "checks": [check.as_dict() for check in low_context_checks],
                "passed": all(check.passed for check in low_context_checks),
                "plan": {"summary": low_context_plan.get("summary"), "objective": low_context_plan.get("objective"), "timeframe": low_context_plan.get("timeframe"), "items": low_context_plan.get("items")},
            }
        )
        self.update_client(client_id, original_profile)

        first_plan_id = next((run["plan_id"] for run in runs if run["plan_id"]), "")
        materialized = {}
        if first_plan_id:
            materialized_payload = self.materialize_strategy_plan(first_plan_id)
            plan = materialized_payload.get("plan") or {}
            materialized = {
                "plan_id": first_plan_id,
                "status": plan.get("status"),
                "suggested_item_count": sum(1 for item in plan.get("items", []) if str(item.get("status") or "") == "suggested"),
                "items": plan.get("items"),
                "passed": any(str(item.get("status") or "") == "suggested" for item in plan.get("items", [])),
            }

        return {"suite_pass": all(run["passed"] for run in runs) and bool(materialized.get("passed")), "runs": runs, "materialized": materialized}

    def run_workflow_suite(self, fixture: dict[str, Any], saved_profile: dict[str, Any]) -> dict[str, Any]:
        client_id = fixture["client_id"]
        bundles = list(fixture.get("drafts") or [])
        workflow_report: dict[str, Any] = {"steps": [], "live_meta_ready": False}
        overrides = resolve_fixture_value(dict(fixture.get("save_overrides") or {}))
        live_meta_ready = all(str(overrides.get(key) or "").strip() for key in ("meta_access_token", "facebook_page_id", "instagram_account_id"))
        workflow_report["live_meta_ready"] = live_meta_ready

        materialized_plan = self.create_strategy_plan(
            client_id,
            "next_7_days",
            goal=str((fixture.get("strategy") or {}).get("campaign_goal") or "").strip(),
            campaign_context=str((fixture.get("strategy") or {}).get("campaign_context") or "").strip(),
        )
        strategy_plan = materialized_plan.get("plan") or {}
        materialized = self.materialize_strategy_plan(str(strategy_plan.get("plan_id") or "").strip())
        materialized_items = list((materialized.get("plan") or {}).get("items") or [])
        suggestion = next((item for item in materialized_items if str(item.get("status") or "").strip().lower() == "suggested"), None)
        if suggestion:
            suggestion_bundle = {
                "bundle_name": f"Strategy Suggestion - {str(suggestion.get('item_id') or 'item').strip()}",
                "files": list(bundles[0]["files"]),
            }
            self.create_bundle(client_id, suggestion_bundle)
            generated = self.generate_caption(client_id, suggestion_bundle["bundle_name"], str(suggestion.get("topic") or "Turn the strategy idea into a clean working draft.").strip())
            generated_payload = generated.get("generated") or {}
            caption_text = str(generated_payload.get("caption") or generated.get("draft", {}).get("caption_text") or "").strip()
            manual_caption = f"{caption_text}\n\nBook a consult or message the team for the next available slot.".strip()
            self.save_manual_caption(
                client_id,
                suggestion_bundle["bundle_name"],
                manual_caption,
                list(generated_payload.get("hashtags") or generated.get("draft", {}).get("hashtags") or []),
                str(generated_payload.get("seo_keyword_used") or generated.get("draft", {}).get("seo_keyword_used") or "").strip(),
            )
            workflow_report["steps"].append(
                {
                    "name": "strategy_materialized_to_draft",
                    "passed": True,
                    "details": "Materialized strategy suggestion was converted into a working draft and manually refined once.",
                    "payload": {"bundle_name": suggestion_bundle["bundle_name"], "item_id": suggestion.get("item_id")},
                }
            )

        approval_date = self._tomorrow()
        approval_a = self.create_orchestrator_plan("send_for_approval", client_id, bundles[0]["bundle_name"], approval_date, "06:00 PM")
        run_a = self.wait_for_run(self.run_orchestrator_plan(approval_a.get("plan") or {}).get("run_id"))
        approvals_after_a = self.list_pending_approvals()
        approval_item_a = next((item for item in approvals_after_a if str(item.get("client") or item.get("client_id") or "").strip() == client_id and str(item.get("draft_name") or "").strip() == bundles[0]["bundle_name"]), None)
        workflow_report["steps"].append(
            {
                "name": "approval_request_created",
                "passed": str(run_a.get("status") or "").strip().lower() in {"completed", "partial_success"} and approval_item_a is not None,
                "details": "Jarvis created a pending approval from the first draft." if approval_item_a else "The orchestrator finished but no pending approval was found for the first draft.",
                "payload": {"run": run_a, "approval": approval_item_a},
            }
        )

        approval_b = self.create_orchestrator_plan("send_for_approval", client_id, bundles[1]["bundle_name"], approval_date, "07:00 PM")
        run_b = self.wait_for_run(self.run_orchestrator_plan(approval_b.get("plan") or {}).get("run_id"))
        approvals_after_b = self.list_pending_approvals()
        approval_item_b = next((item for item in approvals_after_b if str(item.get("client") or item.get("client_id") or "").strip() == client_id and str(item.get("draft_name") or "").strip() == bundles[1]["bundle_name"]), None)
        workflow_report["steps"].append(
            {
                "name": "second_approval_request_created",
                "passed": str(run_b.get("status") or "").strip().lower() in {"completed", "partial_success"} and approval_item_b is not None,
                "details": "Jarvis created a second pending approval for move/reject testing." if approval_item_b else "Could not find the second approval item.",
                "payload": {"run": run_b, "approval": approval_item_b},
            }
        )

        if approval_item_a:
            moved = self.move_pending_approval(str(approval_item_a.get("approval_id") or ""), "Tomorrow 8:15 PM")
            workflow_report["steps"].append(
                {
                    "name": "approval_move",
                    "passed": str(moved.get("status") or "").strip().lower() == "success",
                    "details": "Pending approval moved to a new release window." if str(moved.get("status") or "").strip().lower() == "success" else str(moved.get("reason") or "").strip(),
                    "payload": moved,
                }
            )
        if approval_item_b:
            rejected = self.reject_pending_approval(str(approval_item_b.get("approval_id") or ""))
            workflow_report["steps"].append(
                {
                    "name": "approval_reject",
                    "passed": str(rejected.get("status") or "").strip().lower() == "success",
                    "details": "Pending approval was rejected cleanly." if str(rejected.get("status") or "").strip().lower() == "success" else str(rejected.get("reason") or "").strip(),
                    "payload": rejected,
                }
            )

        if live_meta_ready and approval_item_a:
            approved = self.approve_pending_approval(str(approval_item_a.get("approval_id") or ""))
            schedule_snapshot = self.schedule_snapshot()
            workflow_report["steps"].append(
                {
                    "name": "approval_approve_and_schedule",
                    "passed": str(approved.get("status") or "").strip().lower() == "success",
                    "details": "Approval moved into the live schedule." if str(approved.get("status") or "").strip().lower() == "success" else str(approved.get("reason") or "").strip(),
                    "payload": {"approve_result": approved, "schedule": schedule_snapshot},
                }
            )
            publish_plan = self.create_orchestrator_plan("post_now", client_id, bundles[2]["bundle_name"])
            publish_run = self.wait_for_run(self.run_orchestrator_plan(publish_plan.get("plan") or {}).get("run_id"))
            workflow_report["steps"].append(
                {
                    "name": "live_publish",
                    "passed": any(str(item.get("status") or "").strip().lower() == "published" for item in publish_run.get("items") or []),
                    "details": "At least one draft published successfully." if any(str(item.get("status") or "").strip().lower() == "published" for item in publish_run.get("items") or []) else "Live publish did not reach a published state.",
                    "payload": publish_run,
                }
            )
        else:
            workflow_report["steps"].append(
                {
                    "name": "approval_approve_and_schedule",
                    "passed": False,
                    "details": "Skipped full approve/schedule/publish because demo Meta credentials were not provided for this fake client.",
                    "severity": "warning",
                    "payload": {"live_meta_ready": live_meta_ready},
                }
            )

        refresh_checks = []
        clients_after = self.list_clients()
        refresh_checks.append(CheckOutcome("client_persisted_after_refresh", client_id in clients_after, "Client still exists after multiple API reads.", payload={"clients": clients_after}))
        approvals_snapshot = self.list_pending_approvals()
        refresh_checks.append(CheckOutcome("approvals_accessible_after_refresh", isinstance(approvals_snapshot, list), "Pending approvals endpoint still responds after workflow actions.", payload={"approval_count": len(approvals_snapshot)}))
        workflow_report["steps"].append(
            {
                "name": "refresh_recovery",
                "passed": all(check.passed for check in refresh_checks),
                "details": "State survived follow-up API reads." if all(check.passed for check in refresh_checks) else "State access degraded after workflow actions.",
                "payload": {"checks": [check.as_dict() for check in refresh_checks]},
            }
        )

        workflow_report["suite_pass"] = all(bool(step.get("passed")) or str(step.get("severity") or "") == "warning" for step in workflow_report["steps"])
        workflow_report["hard_pass"] = all(bool(step.get("passed")) for step in workflow_report["steps"] if str(step.get("severity") or "") != "warning")
        workflow_report["full_live_success"] = any(step.get("name") == "live_publish" and step.get("passed") for step in workflow_report["steps"])
        return workflow_report

    def write_reports(self, payload: dict[str, Any]) -> None:
        self.report_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        lines = [
            "# Internal Trial Lockdown Report",
            "",
            f"- Generated at: `{payload.get('generated_at')}`",
            f"- Base URL: `{payload.get('base_url')}`",
            f"- Overall status: `{payload.get('overall_status')}`",
            f"- Go / No-Go: `{payload.get('go_no_go')}`",
            "",
            "## Readiness",
            "",
            f"- Health before: `{payload.get('health_before', {}).get('readiness', {}).get('ok')}`",
            f"- Health after: `{payload.get('health_after', {}).get('readiness', {}).get('ok')}`",
            "",
        ]
        restart_check = payload.get("restart_recovery") or {}
        if restart_check:
            lines.extend(["## Restart Recovery", "", f"- Passed: `{restart_check.get('passed')}`", f"- Details: {restart_check.get('details')}", ""])
        for client in payload.get("clients", []):
            lines.extend(
                [
                    f"## {client.get('client_id')}",
                    "",
                    f"- Synthesis passed: `{client.get('synthesis', {}).get('passed')}`",
                    f"- Caption suite passed: `{client.get('caption_suite', {}).get('suite_pass')}`",
                    f"- Strategy suite passed: `{client.get('strategy_suite', {}).get('suite_pass')}`",
                    f"- Workflow hard pass: `{client.get('workflow_suite', {}).get('hard_pass')}`",
                    "",
                    "### Notes",
                    "",
                ]
            )
            for note in client.get("notes", []):
                lines.append(f"- {note}")
            lines.append("")
        lines.extend(
            [
                "## Device Access Model",
                "",
                "- Keep Jarvis hosted on your side.",
                "- Run FastAPI and the scheduler.",
                "- Expose `/app` over HTTPS through your VPS/domain or Cloudflare tunnel.",
                "- Confirm `/api/health` before sending the URL.",
                "- Send him the hosted `/app` URL plus the trial login password.",
                "- He uses Jarvis from his browser on his own device; nothing is installed locally.",
                "",
            ]
        )
        self.report_md_path.write_text("\n".join(lines), encoding="utf-8")

    def run(self) -> dict[str, Any]:
        fixtures_payload = json.loads(self.fixtures_path.read_text(encoding="utf-8"))
        fixtures = [resolve_fixture_value(item) for item in fixtures_payload.get("clients", [])]
        if len(fixtures) < 2:
            raise HarnessError("The fixture pack must contain at least two fake clients.")

        self.login()
        health_before = self.health()
        self.set_desktop_first_approval_routing()
        report: dict[str, Any] = {"generated_at": now_utc_iso(), "base_url": self.base_url, "fixtures": str(self.fixtures_path), "health_before": health_before, "clients": []}

        try:
            for fixture in fixtures:
                client_notes: list[str] = []
                client_id = fixture["client_id"]
                self.delete_client_if_present(client_id)
                raw_context = build_raw_context(fixture)
                synth = self.synthesize_client(fixture, raw_context=raw_context)
                synthesis_passed = str(synth.get("status") or "").strip().lower() == "success"
                profile_data = copy.deepcopy(synth.get("data") or {})
                if not synthesis_passed:
                    client_notes.append(f"Synthesis returned `{synth.get('status')}` instead of `success`.")
                if synth.get("missing_fields"):
                    client_notes.append(f"Synthesis reported missing fields: {', '.join(synth.get('missing_fields') or [])}")
                if not profile_data:
                    raise HarnessError(f"Synthesis did not return a usable profile for {client_id}.")

                save_result = self.save_client_profile(fixture, profile_data)
                uploaded = self.upload_assets(fixture)
                uploaded_filenames = [str(asset.get("filename") or "").strip() for asset in (uploaded.get("assets") or []) if str(asset.get("filename") or "").strip()]
                for bundle in fixture.get("drafts") or []:
                    missing_files = [name for name in bundle.get("files", []) if name not in uploaded_filenames]
                    if missing_files:
                        raise HarnessError(f"Bundle '{bundle['bundle_name']}' for {client_id} references missing uploaded files: {missing_files}")
                    self.create_bundle(client_id, bundle)

                saved_client = self.get_client(client_id)
                saved_profile = copy.deepcopy(saved_client.get("profile_json") or profile_data)
                caption_suite = self.run_caption_suite(fixture, saved_profile)
                if not caption_suite.get("suite_pass"):
                    client_notes.append("Caption fidelity suite is not green yet.")
                strategy_suite = self.run_strategy_suite(fixture, saved_profile)
                if not strategy_suite.get("suite_pass"):
                    client_notes.append("Strategy suite is not green yet.")
                workflow_suite = self.run_workflow_suite(fixture, saved_profile)
                if not workflow_suite.get("hard_pass"):
                    client_notes.append("Workflow suite still has hard failures.")
                if not workflow_suite.get("full_live_success"):
                    client_notes.append("Live publish was not validated for this fake client. Add demo Meta credentials if you need a full green publish lane.")

                report["clients"].append(
                    {
                        "client_id": client_id,
                        "synthesis": {"passed": synthesis_passed, "status": synth.get("status"), "missing_fields": synth.get("missing_fields") or [], "source_warnings": synth.get("source_warnings") or [], "save_result": save_result, "profile": profile_data},
                        "uploaded_assets": uploaded.get("assets") or [],
                        "caption_suite": caption_suite,
                        "strategy_suite": strategy_suite,
                        "workflow_suite": workflow_suite,
                        "notes": client_notes,
                    }
                )

            restart_recovery = self.restart_server()
            report["restart_recovery"] = restart_recovery.as_dict()
            health_after = self.health()
            report["health_after"] = health_after
        finally:
            try:
                self.restore_agency_config()
            except Exception as exc:
                report.setdefault("cleanup_warnings", []).append(f"Failed to restore agency config: {exc}")

        caption_green = all(client.get("caption_suite", {}).get("suite_pass") for client in report["clients"])
        strategy_green = all(client.get("strategy_suite", {}).get("suite_pass") for client in report["clients"])
        workflow_green = any(client.get("workflow_suite", {}).get("full_live_success") for client in report["clients"])
        recovery_green = bool(report.get("restart_recovery", {}).get("passed"))
        readiness_green = bool(report.get("health_after", {}).get("readiness", {}).get("ok"))

        if caption_green and strategy_green and workflow_green and recovery_green and readiness_green:
            report["overall_status"] = "green"
            report["go_no_go"] = "go"
        elif caption_green and strategy_green and readiness_green:
            report["overall_status"] = "attention"
            report["go_no_go"] = "hold_for_live_publish_or_restart"
        else:
            report["overall_status"] = "red"
            report["go_no_go"] = "no_go"

        self.write_reports(report)
        return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Jarvis's internal fake-client trial lockdown suite.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL for the live Jarvis API.")
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES_PATH), help="Path to the fake-client fixture pack.")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="Directory where JSON/Markdown reports will be written.")
    parser.add_argument("--password", default="", help="Jarvis admin password. Falls back to JARVIS_ADMIN_PASSWORD.")
    parser.add_argument(
        "--restart-command",
        default="",
        help="Optional shell command that restarts FastAPI so recovery can be verified with the same session token.",
    )
    parser.add_argument("--restart-wait-seconds", type=float, default=8.0, help="How long to wait after the restart command before re-checking health.")
    parser.add_argument("--strict-exit", action="store_true", help="Exit with status 1 when the final go/no-go is not GO.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    harness = JarvisInternalTrialHarness(args)
    try:
        report = harness.run()
    except Exception as exc:
        print(f"[internal-trial-lockdown] failed: {exc}", file=sys.stderr)
        return 1

    print(f"[internal-trial-lockdown] overall_status={report.get('overall_status')} go_no_go={report.get('go_no_go')}")
    print(f"[internal-trial-lockdown] json_report={harness.report_json_path}")
    print(f"[internal-trial-lockdown] markdown_report={harness.report_md_path}")
    if args.strict_exit and report.get("go_no_go") != "go":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
