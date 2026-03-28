# 🧠 Jarvis Agency OS — Feature Registry

> Last updated: March 26, 2026  
> This file is the single source of truth for every implemented capability.

---

## Lead Orchestrator (Chat Interface)

| Feature | Description |
|---------|-------------|
| Natural Language Commands | Chat with Jarvis in plain English to schedule, post, analyze, and manage |
| @Client Mentions | Type `@` to mount a client's CRM vault into context |
| Smart Loading States | Context-aware loading text (posting, analyzing, searching, scanning) |
| Triple-Dot Pulse Animation | Premium breathing dots during AI processing |
| Markdown Renderer | Full support: bold, italic, headers, bullet/numbered lists, code, HR |
| Dual Response Modes | Conversational replies = clean bubble · Structured data = formatted card |
| RGB Breathing Input | Conic-gradient animation on input bar while processing |
| Success Flash | Green border flash on completion |
| Error Cards | Red-bordered error display with exact failure message |

---

## Content Pipeline

| Feature | Description |
|---------|-------------|
| AI Caption Generation | LLM-powered captions using brand voice profiles (tone, dialect, hashtags) |
| Gulf Arabic (خليجي) Support | Natural Arabic dialect, not robotic MSA |
| Single Image Publishing | One image → Facebook + Instagram |
| Carousel Publishing | Multi-image bundles → Instagram carousel (swipeable) + Facebook album |
| Platform-Specific Formatting | IG: hook in first 125 chars · FB: short-form |
| Safety Guardrails | Won't generate off-brand or sensitive content |

---

## Scheduling & Automation

| Feature | Description |
|---------|-------------|
| Cron Scheduler | Time-based scheduling with exact day/hour/minute control |
| Bundle Queuing | Create named bundles (Bundle 1, 2…) in the image vault |
| Live Delivery Status | Dashboard shows pending → delivered ✅ for each scheduled job |
| Hot Reload | Add new schedules without restarting the daemon |
| Background Daemon | `scheduler.py` runs independently, executes jobs automatically |
| Duplicate Prevention | Jarvis deduplicates repeated bundle names in a single message |
| Absolute Date Scheduling | Supports `today`, `tomorrow`, `this Friday`, `next Friday`, and calendar-style one-off scheduling |
| Active / History Separation | Delivered jobs no longer clutter the active schedule view; they move into retained history |
| Delivered Retention Window | Delivered jobs are auto-pruned after the retention window instead of growing forever |

---

## Client Management (CRM)

| Feature | Description |
|---------|-------------|
| AI Profile Synthesizer | Paste raw client info → LLM auto-fills brand profile JSON |
| Brand Voice Profiles | Stored in `brands/` — identity, tone, audience, dos/don'ts |
| Client Credentials | Stored in `clients/` — Meta tokens, page IDs, IG account IDs |
| Pre-Flight Token Validator | Validates Meta credentials BEFORE committing any schedule |

---

## Media & Asset Management

| Feature | Description |
|---------|-------------|
| Drag-and-Drop Upload | Drop images directly onto client vault in dashboard |
| Click-to-Upload | File picker button for browsing local files |
| Client-Isolated Vaults | Each client's assets stored in `assets/{client_id}/` |
| Bundle Creator | Select images → name a bundle → ready for scheduling |
| Asset Queue (queue.json) | Tracks which bundles exist and what images they contain |

---

## Analytics & Intelligence

| Feature | Description |
|---------|-------------|
| MetaInsightsScanner | Live IG/FB data via Graph API: likes, comments, reach, saves |
| Top Post Detection | Identifies highest-engagement post automatically |
| Carousel vs Single Comparison | Compares avg engagement between post formats with multiplier |
| Best Posting Day Analysis | Identifies which weekday gets highest avg engagement |
| Day-by-Day Breakdown | Per-day engagement averages and post counts |
| Total Reach Aggregation | Summed reach across all analyzed posts |
| DuckDuckGo Web Search | Search-grounded strategy — real web results, not LLM guessing |

---

## Notifications

| Feature | Description |
|---------|-------------|
| WhatsApp Executive Briefing | Auto-notification after every publish with post details |
| Carousel Detection | Briefing notes whether the post was single or carousel |
| Post ID Links | Direct links to live posts in briefing messages |
| Interactive Approval Cards | Owner receives branded WhatsApp approval cards with Approve / Refine / Move Time actions |
| Reschedule Flow | Move Time opens a WhatsApp reschedule loop and re-issues the approval card with the new release window |

---

## Architecture

| Feature | Description |
|---------|-------------|
| FastAPI Backend | `webhook_server.py` — REST API for all dashboard operations |
| Static Asset Server | `/assets/` route serves images for Meta to download |
| Cloudflare Tunnel | Public URL for Meta's servers to reach local assets |
| OpenRouter Integration | Multi-model LLM access (GPT-4o-mini, Mistral-Nemo, etc.) |
| Modular Agent Design | Separate agents: Orchestrator, Caption, Publish, WhatsApp |
| Pipeline Subprocess | Each post runs as isolated subprocess for fault tolerance |
| Honesty Rule | System prompt forces Jarvis to relay exact errors, never fake success |

---

## Dashboard Pages

| Page | What It Does |
|------|-------------|
| Lead Orchestrator | Chat with Jarvis — the main command center |
| Dashboard | System overview and status |
| Architecture | Visual system topology |
| Asset Vaults | Upload/manage images per client |
| Client Config | View/edit client profiles and credentials |
| + New Client | AI-synthesized client onboarding |
| Cron Schedule | View scheduled jobs and delivery status |
| Audit Logs | System event history |

---

## 📱 WhatsApp Integration Architecture

The Agency OS features a bifurcated WhatsApp routing system to ensure client satisfaction while keeping the agency owner completely in the loop.

### 🏢 WhatsApp Agency Features (Your Number / OWNER_PHONE)
Your phone number is securely stored in the `.env` root file under the `OWNER_PHONE` variable. The system will ONLY send the following system-level alerts to this number:
- **Executive Post Briefings:** Every time the automated pipeline successfully publishes a scheduled bundle, it fires a WhatsApp message to you containing the post's caption preview, the platforms it was published on, the media format, timestamp, and live URLs to the posts.
- **Escalation Alerts (Triage Firewall):** If a client texts the bot and is detected as angry or complaining by the Triage AI, the bot will immediately pause auto-replying and ping you with an emergency escalation alert containing the client's name and raw message, allowing you or your human account managers to step in.

### 🤝 WhatsApp Client Features (Client Config Number)
The client's phone number is saved during onboarding and stored in their `Config` profile. 
- **AI Account Manager:** If the client explicitly texts the bot's WhatsApp number, the LLM will securely load their unique Brand Profile, read their tone/rules, and naturally reply to their questions in Khaleeji Gulf Arabic.
- **Support Autonomy:** The AI can assure them that their posts are scheduled and handle basic CRM communication, essentially acting as an employee of your agency.

---

## 🛑 TESTS BEFORE PRODUCTION (The Chaos Matrix)

| Test Name | Description | Status |
|-----------|-------------|--------|
| **1. The Bad Token Trap** | Schedule with invalid Meta Token to test preemptive failure | ✅ **Completed** |
| **2. The Ghost Bundle** | Ask to schedule a bundle that doesn't exist to test LLM refusal | ✅ **Completed** |
| **3. The Collision Test** | Schedule multiple bundles for the exact same minute to test parallel pipeline isolation | ✅ **Completed** |
| **4. The Sabotaged Vault** | Delete an image out of an active scheduled bundle to test runtime missing asset handling | ✅ **Completed** |
| **5. The WhatsApp Outage** | Process a post while WhatsApp API keys are broken to test graceful platform degradation | ⏳ Pending Fix |
| **6. Approval Happy Path** | Approve a WhatsApp draft, confirm it enters the schedule, receives a job ID, posts, and sends the executive briefing | ✅ **PASS** |
| **7. Past-Time Rejection** | Ask Jarvis to schedule `today` at a time that has already passed | ✅ **PASS** |
| **8. Duplicate Active Schedule Prevention** | Attempt the same active schedule twice and confirm the second is blocked cleanly | ✅ **PASS** |
| **9. Immediate Publish Path** | Trigger `post now` and confirm immediate publishing still succeeds without the scheduler | ✅ **PASS** |
| **10. Delivery Integrity** | Confirm a scheduled job is marked delivered after publish and does not remain executable | ✅ **PASS** |
| **11. Move Time Owner UX** | Tap `Move Time`, reply with a new weekday/time naturally, and confirm the approval card is refreshed cleanly | 🔄 **Retest After Session Binding Patch** |
| **12. Absolute Date Scheduling** | Schedule with phrases like `tomorrow`, `this Friday`, and `next Friday` and confirm Jarvis resolves a real release date | ✅ **PASS** |
| **13. Schedule Hygiene** | Confirm active jobs remain clean while delivered jobs are separated into retained history | ✅ **PASS** |
