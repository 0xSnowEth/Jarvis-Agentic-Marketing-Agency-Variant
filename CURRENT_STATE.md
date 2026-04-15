# Current State

This is the fastest file for a future session to read before continuing work.

## Product State

Jarvis is currently a working multi-client marketing-agency workflow system with:
- WhatsApp as the primary operator interface
- `webhook_server.py` as the backend ingress hub
- `whatsapp_operator.py` as the owner/operator control lane
- quick client setup as the primary onboarding path
- optional PDF / website / social-page enrichment during synthesis
- asset vaults, drafts, caption generation, approvals, scheduling, and publishing
- a saved strategy-planning layer
- dashboard surfaces frozen as fallback support UI in phase 1

The product is no longer strictly brief-first. New brands can now start from a few simple answers and still get a usable synthesized profile.

## What Works

- quick client setup onboarding
- optional brief import (TXT / MD / PDF / DOCX)
- optional website and social-page enrichment during synthesis
- client synthesis into structured brand profile
- client config editing
- asset vault upload
- draft creation
- draft rename
- caption generation
- inline approval cards in Jarvis chat
- WhatsApp approval routing
- scheduling
- immediate publish
- per-platform result reporting
- strategy plan generation and persistence
- strategy suggestion materialization
- video normalization on upload
- one-click repair for older stored videos
- schedule history / failed state handling
- durable auth sessions
- durable orchestrator runs
- durable operator sessions
- restart-safe live run hydration
- structured `/api/health` readiness checks
- basic runtime rate limiting
- operator audit trail
- WhatsApp operator slash commands
- WhatsApp client onboarding state machine
- WhatsApp document-based media intake
- WhatsApp preview / change / schedule / confirm loop
- Meta OAuth connect handoff route

## What Was Fixed Recently

- caption generation now enforces per-client language mode
- caption generation now reuses saved trend dossiers before live research
- caption generation now carries recent-caption dedup context
- caption generation now runs through a native quality gate with regeneration attempts
- client creation now triggers background trend dossier builds
- trend dossiers now persist in both runtime storage paths, with Supabase as production target
- operator sessions now persist in runtime state
- owner WhatsApp messages now route into a dedicated operator lane
- operator media collection now batches inbound documents into a single draft bundle
- operator client selection now supports interactive picker plus text fallback
- Meta OAuth connect handoff routes were added for WhatsApp-driven client connection
- Supabase schema was extended for `client_trend_dossiers` and `operator_sessions`

## Current UX Direction

### Primary
- WhatsApp operator inbox
- onboarding over chat
- document-based content intake
- preview / change / schedule / confirm loop
- backend-managed scheduling, approval, and publish execution

### Secondary
- dashboard as frozen fallback support UI
- client config editing as secondary support surface

### Removed from primary flow
- dashboard-first operator workflow
- client-side orchestration as the center of gravity

## Current Production Baseline

The production-hardening baseline is implemented in code:
- durable runtime state store exists
- systemd service files exist
- structured readiness checks exist
- persisted strategy plan store exists
- regression tests exist for:
  - runtime state persistence
  - schedule phrase normalization
  - draft resolution
  - strategy routing
  - strategy plan persistence

Current production target is still:
- single-agency VPS first

The repo is materially stronger than demo-only state, but production is only fully green when these live runtime conditions are also green:
- scheduler heartbeat
- stable public HTTPS media host / tunnel
- valid WhatsApp runtime token if WhatsApp lane is being used
- Supabase connectivity and schema match the live backend code path

## Current Biggest Remaining Product Task

Finish end-to-end WhatsApp operator hardening.

Needed behavior:
- complete `/addclient` via WhatsApp against the live backend
- validate `/connect @client` Meta OAuth round-trip against real credentials
- validate operator media batching from WhatsApp documents into drafts
- validate preview replies (`yes`, `change ...`, `schedule ...`, `cancel`) against real publish and approval flows
- confirm all operator actions write durable runtime state and audit events correctly

## Current Biggest Operational Risks

1. `WEBHOOK_PROXY_URL` / public media hosting must point to a live HTTPS host.
   - If the public media host is stale, Meta cannot fetch assets and publishing breaks.

2. `scheduler.py` must be running for scheduled delivery state to remain live.

3. WhatsApp runtime must have a valid live token if approval routing is part of the workflow.

4. Cloudflared / public tunnel must actually be running if the configured public host depends on it.

5. Supabase schema must include new runtime tables used by the backend:
   - `client_trend_dossiers`
   - `operator_sessions`

## Before Trial / Smoke Test

1. Check `/api/health`
2. Confirm:
   - `readiness.checks.runtime_state.ok = true`
   - `readiness.checks.scheduler.ok = true`
   - `readiness.checks.public_media_host.ok = true`
3. If using WhatsApp, also confirm:
   - `readiness.checks.whatsapp_runtime.ok = true`
4. Run one smoke path:
   - `/addclient` over WhatsApp
   - confirm background trend dossier build fires
   - send one media document and produce a preview
   - use `change ...` once
   - use `schedule ...` once
   - use `yes` once on an immediate-post path
   - use `/strategy @client ...` once
   - confirm state survives restart and refresh

## Next Build Order

1. live WhatsApp operator smoke testing
2. Meta OAuth production validation
3. publish/schedule loop hardening from WhatsApp
4. stable public hosting / VPS deployment
5. richer reporting / performance layer
6. client-facing WhatsApp concierge
7. multi-operator roles and permissions
