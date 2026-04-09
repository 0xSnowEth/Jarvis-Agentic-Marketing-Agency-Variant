# Jarvis

Jarvis is a premium agency operating system for content teams.

The current product is built around one core idea:
- Jarvis chat is the front door
- WhatsApp is the mobile control lane
- Schedule is the oversight surface
- Vaults and Client Config support the work underneath

This repo is no longer a generic "AI demo". It is a working multi-client content operations system with real publishing, scheduling, approvals, media validation, and client-isolated brand memory.

## Current Product Shape

### Core workflow
1. Add or synthesize a client
2. Save brand profile + live Meta credentials
3. Upload assets into the client vault
4. Create or reuse a creative draft
5. Ask Jarvis to schedule or post it
6. Approve inline in Jarvis chat or route it to WhatsApp
7. Jarvis schedules or publishes and reports per-platform results honestly

### Current positioning
- Desktop-first agency operating system
- Premium lock screen and dashboard
- Multi-client brand isolation
- Real Facebook + Instagram publishing
- WhatsApp used as a mobile control lane, not as a cloned dashboard

### What Jarvis is strongest at right now
- Client onboarding and brand synthesis
- Asset vaults and creative drafts
- Caption generation
- Inline approvals in chat
- Scheduling and immediate publishing
- WhatsApp routing for owner approvals
- Honest publish reporting and media preflight

## Architecture

### Main runtime
- `webhook_server.py`
  - FastAPI hub
  - dashboard APIs
  - auth flow
  - client synthesis
  - vault APIs
  - inline approval actions
  - WhatsApp webhook handling
- `orchestrator_agent.py`
  - Jarvis chat orchestration
  - intent parsing
  - schedule vs immediate-post routing
  - inline approval metadata
- `caption_agent.py`
  - brand-aware caption generation
  - currently Arabic-first
  - bilingual extension is the next major capability
- `publish_agent.py`
  - media preflight
  - platform-specific publishing
  - honest per-platform result reporting
- `scheduler.py`
  - daemon for future jobs
  - reads live schedule store
  - marks failures and history states correctly

### Storage
- Supabase is the active backend
- JSON fallback remains for local recovery / migration tooling
- assets are stored per client
- videos are normalized to Meta-safe MP4 on upload

### Frontend
- `jarvis-dashboard.html`
  - premium lock screen
  - Jarvis chat
  - dashboard
  - vaults
  - client config
  - schedule
  - live agent status

## Startup

### API
```bash
cd /home/snowaflic/agents
./venv/bin/python3 -m uvicorn webhook_server:app --host 0.0.0.0 --port 8000
```

### Scheduler
```bash
cd /home/snowaflic/agents
./venv/bin/python3 scheduler.py
```

### Cloudflared
```bash
cd /home/snowaflic/agents
cloudflared tunnel --url http://127.0.0.1:8000
```

Important:
- `WEBHOOK_PROXY_URL` must always point to the current live public tunnel/domain
- if that URL is stale, Meta will fail to fetch assets
- temporary `trycloudflare` URLs are acceptable for quick tests but are not considered production-safe for Instagram media delivery
- a stable HTTPS domain or stable tunnel should be treated as the final publishing requirement

## Current Product Decisions

### What was intentionally simplified
- Approval Center is no longer a primary visible workflow surface
- Jarvis chat now handles approval actions inline
- WhatsApp is retained for mobile control, not for duplicating the whole dashboard

### What is intentionally not "production-complete" yet
- bilingual English/Arabic caption workflow
- stable hosted domain instead of rotating temporary tunnel
- deeper WhatsApp client-facing inbox / lead handling
- final deployment and operational hardening

## Immediate Priorities

1. Finish bilingual brief/caption support
2. Run final demo QA with two real client accounts
3. Record the demo
4. Move to stable hosting / deployment
5. Continue production hardening

## Important Files

- [jarvis-dashboard.html](/home/snowaflic/agents/jarvis-dashboard.html)
- [webhook_server.py](/home/snowaflic/agents/webhook_server.py)
- [orchestrator_agent.py](/home/snowaflic/agents/orchestrator_agent.py)
- [caption_agent.py](/home/snowaflic/agents/caption_agent.py)
- [publish_agent.py](/home/snowaflic/agents/publish_agent.py)
- [scheduler.py](/home/snowaflic/agents/scheduler.py)
- [asset_store.py](/home/snowaflic/agents/asset_store.py)
- [schedule_store.py](/home/snowaflic/agents/schedule_store.py)
- [CURRENT_STATE.md](/home/snowaflic/agents/CURRENT_STATE.md)
