# JARVIS OX: Agency OS Master Spec

**Project:** JARVIS (Orionx Agency OS)
**Purpose:** A completely autonomous, zero-code AI agent framework that handles client onboarding, asset parsing, and scheduled social media operations directly via natural language routing.

---

## 1. System Architecture
The platform is built on a distributed micro-agent architecture running alongside a centralized FastAPI hub and a physical cron daemon.

1.  **Lead Orchestrator (TARS)**
    *   **Role:** The conversational nexus and global supervisor.
    *   **Capabilities:** Conversational memory, sarcastic work-ethic enforcement (TARS persona), physical disk inspection, client brief reading, live cron scheduling, and pipeline telemetry monitoring.
    *   **Interaction:** Driven through the `#orch-chat` UI using Mistral/GPT via OpenRouter SDK.

2.  **The Subagents Framework**
    *   **Caption Agent:** Specializes in localized Khaleeji/English marketing copy, constrained by individual client JSON profiles (identity, tone, target audience, dos/donts). Continually scans external URLs and brand context.
    *   **Publish Agent:** Handles the final physical payload execution. Hooks into the Instagram/Facebook Graph APIs to post scheduled content using client-specific tokens.
    *   **WhatsApp Agent (Approvals):** Broadcasts proposed drafts to clients via the WhatsApp Cloud API. Parses human replies (Approve/Reject) and forces revision loops backwards into the DAG.

3.  **FastAPI Central Hub (`webhook_server.py`)**
    *   Serves the frontend dashboard.
    *   Manages Client Profile generation (Intake → Mistral-Nemo → JSON).
    *   Manages Asset Vault bulk uploads via drag-and-drop.
    *   Maintains the persistent `OrchestratorAgent` session state.
    *   Receives asynchronous webhooks from Meta (WhatsApp inbound messages).

4.  **The Cron Daemon (`scheduler.py`)**
    *   A detached Python subprocess that persistently reads `schedule.json`.
    *   Spawns `pipeline.py` subprocess threads asynchronously based on time-triggers without blocking the main event loop.

---

## 2. Global Data Structures

### Assets Vault
*   **Path:** `assets/{client_id}/`
*   **Concept:** Physical multi-tenant isolation. No agent can cross-contaminate images.
*   **Ingestion:** Drag-and-drop UI automatically syncs files into subdirectories matching the exact `client_id`.

### CRM Definitions
*   **Path:** `clients/{client_id}.json`
*   **Contents:** Phone numbers, Instagram/Facebook tokens, and the AI-generated "Brand Profile".
*   **Lifecycle:** Orchestrator reads this exactly when needed to inject the client's strict constraints into the active pipeline context.

### The Global Schedule
*   **Path:** `schedule.json`
*   **Format:** A flat array of execution rules `[{"client": "burger_grillz", "topic": "xyz", "time": "18:00", ...}]`.
*   **Integrity:** Both the `scheduler.py` daemon and the Orchestrator's `commit_cron_schedule` tool use standard dictionary structures to sync gracefully.

---

## 4. End-to-End Execution Flow (Verification Protocol)
To completely prevent silent failures ("bullshit assurances"), the system uses a multi-step verification pipeline:

1. **Intent & Verification (`orchestrator_agent.py`):** 
   - Jarvis reads the natural language prompt and maps the constraints.
   - **Heartbeat Check:** Jarvis physically reads `.daemon_heartbeat`. If the daemon (`scheduler.py`) has not updated this file in the last 30 seconds, Jarvis forcibly appends a `[CRITICAL WARNING]` into the chat advising the user that the pipeline is offline.
   - **Commit:** The task is written to `schedule.json`.
2. **Hot-Reloading Daemon (`scheduler.py`):**
   - The detached subprocess runs continuously (`python scheduler.py`).
   - Every 10 seconds, it writes the current timestamp to `.daemon_heartbeat`.
   - It watches `schedule.json` for modification time (`os.path.getmtime`). If Jarvis alters the schedule, it drops its internal memory and hot-reloads the triggers instantly.
   - Triggers `pipeline.py` when the clock strikes.
3. **The Localized Brain (`pipeline.py`):**
   - Loads `caption_agent.py` to draft the SEO and copy using the strict brand voice defined in `clients/<id>.json`.
   - Uses `send_owner_briefing()` to blast the personal Meta Graph API, sending the human owner a WhatsApp draft preview.
4. **Approval & Publishing (`webhook_server.py` & `publish_agent.py`):**
   - The central FastAPI hub catches the inbound "Yes" via Webhooks.
   - `publish_agent.py` leverages the specific client's Instagram/Facebook access tokens to construct the physical multipart payload and publish.

---

## 5. Direct Pipeline Execution (`TriggerPipelineNowTool`)
For same-day or "post now" requests, the Orchestrator bypasses the cron daemon entirely and uses `trigger_pipeline_now`, which:
1. Directly spawns `pipeline.py` as a subprocess.
2. Blocks until the pipeline finishes (up to 120s timeout).
3. Returns the actual stdout/stderr result — Jarvis only confirms success if exit code = 0.

**Routing Logic:**
- "Post now" / "schedule for today" → `trigger_pipeline_now` (real execution)
- "Every Monday at 9 AM" → `commit_cron_schedule` (recurring daemon job)

---

## 6. Dual-Directory Brand Architecture
The Caption Agent reads brand profiles from `brands/{client_id}.json`, while the Publish Agent reads credentials from `clients/{client_id}.json`.

**Both directories are auto-synced** when a profile is saved or updated via the dashboard:
- `clients/` → Full profile (credentials + brand profile JSON)
- `brands/` → Brand-only fields (voice, services, SEO keywords, hashtag bank, banned words, caption defaults)

### Required Brand Profile Schema (`brands/*.json`)
```json
{
  "client_name": "...",
  "business_name": "...",
  "industry": "...",
  "brand_voice": { "tone": "...", "style": "...", "dialect": "gulf_arabic_khaleeji", "dialect_notes": "..." },
  "services": [],
  "seo_keywords": [],
  "hashtag_bank": [],
  "banned_words": [],
  "caption_defaults": { "min_length": 150, "max_length": 300, "hashtag_count_min": 3, "hashtag_count_max": 5 }
}
```

---

## 7. Client Config Dashboard
Each client card in the Config page has two expandable sections:
- **Client Details** (purple tab): Editable brand profile (identity, tone, audience, services, dos/donts). Saves to both `clients/` and `brands/`.
- **Live Credentials** (blue tab): Editable tokens/IDs (WhatsApp, Meta token, FB Page ID, IG Account ID).

### +New Client Intake
- Accepts raw text paste OR file upload (TXT, MD) via drag-and-drop.
- Synthesis via Mistral-Nemo extracts the full brand profile schema.
- JSON preview for human review before "Confirm & Write to Disk".

*Document dynamically maintained by Orionx engineering.*

---

## 8. Execution Trace Logs (Phase 11: Intelligent Bundling & Delivery)
```text
2026-03-26 04:24:03,379 - SchedulerDaemon - INFO - ⚡ [TRIGGERED] Spawning pipeline.py for 'Burger_grillz'...
2026-03-26 04:24:33,738 - SchedulerDaemon - INFO - ✅ [SUCCESS] Pipeline completed successfully for 'Burger_grillz'.
2026-03-26 04:24:33,739 - SchedulerDaemon - INFO - --- PIPELINE OUTPUT ---
============================================================
📊 PIPELINE FINAL REPORT
============================================================
Client:       Burger_grillz
Topic:        Scheduled Bundle 1
SEO Keyword:  برجر
------------------------------------------------------------
📋 GENERATED TEXT:
فزتوا بجاااانب مره حلو! 🥳 صحيح انكم تنتظرون، لكن الحين نعلن عن باقة الجداول الزمنية 1. 🌟 فيها برجر يدوب في الفم، فرايز مشبعه وجددّوا حماسكم مع حليب شاك فريد خيال! يالله، شوفوا هذا وخلّوا أجواءكم وايد مميزة مع أصدقائكم!  

#سماش_برجر #فرايز #ميلك_شيك #أكل_شوارع #الكويت
------------------------------------------------------------
📈 PUBLISHING RESULTS (Carousel Enabled):
Facebook:  published (ID: 1339992028331984)
Instagram: published (ID: 18104109815495499)
============================================================

INFO - ✅ Marked 'Scheduled Bundle 1' as Delivered in the schedule via IPv4 loopback (127.0.0.1:8000).
```
