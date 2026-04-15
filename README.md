# Jarvis

Jarvis is now a WhatsApp-first agency operating system for multi-client content teams.

Phase 1 is explicitly backend-first:
- WhatsApp is the primary operator workspace
- `webhook_server.py` is the ingress hub
- `orchestrator_agent.py`, `caption_agent.py`, `strategy_agent.py`, `publish_agent.py`, and `scheduler.py` remain the core spokes
- `jarvis-dashboard.html` is a frozen fallback UI, not the product center of gravity

This repo is production-oriented infrastructure for real client onboarding, content prep, approvals, scheduling, and Facebook/Instagram delivery. The dashboard still exists, but the operator lane is now WhatsApp.

## Current Product Shape

### Core operator workflow
1. Operator messages Jarvis on WhatsApp
2. Jarvis routes owner/operator requests into the operator lane
3. Jarvis collects onboarding answers, media documents, or strategy intent
4. Existing synthesis, draft, caption, approval, schedule, and publish flows execute through the backend hub-and-spoke architecture
5. Jarvis reports status, previews, approvals, and Meta connection steps back over WhatsApp

### Current positioning
- WhatsApp-first operator interface
- FastAPI backend as the single orchestration ingress
- Multi-client brand isolation
- Real Facebook + Instagram publishing
- Strategy planning layered on top of execution
- Dashboard retained only as fallback support UI in phase 1

### What Jarvis is strongest at right now
- Client onboarding and brand synthesis
- Per-client trend dossier building
- Asset vaults and creative drafts
- Premium caption generation with language control and quality gating
- Strategy planning and saved plans
- Scheduling and immediate publishing
- WhatsApp approvals and operator control
- Honest publish reporting and media preflight

## Architecture

### Main runtime
- `webhook_server.py`
  - FastAPI hub
  - WhatsApp webhook ingress
  - operator routing
  - client synthesis and save flows
  - vault, draft, strategy, approval, and publish APIs
  - Meta OAuth connect handoff
- `whatsapp_operator.py`
  - owner/operator lane
  - onboarding state machine
  - slash commands
  - media intake
  - preview loop
  - schedule/post actions
- `orchestrator_agent.py`
  - Jarvis orchestration brain
  - scheduling and publish tools
  - strategy delegation
- `caption_agent.py`
  - language-controlled caption generation
  - saved trend dossier reuse
  - deduplication and quality gate loop
- `strategy_agent.py`
  - saved strategy planning
  - research-backed content planning
- `publish_agent.py`
  - media preflight
  - platform-specific publish delivery
  - honest per-platform results
- `scheduler.py`
  - future job execution
  - reads live schedule state
  - transitions delivered/failed history correctly

### Storage
- Supabase is the production source of truth
- JSON fallback remains inside store files and must not be broken casually
- runtime state now includes operator sessions
- assets, drafts, approvals, schedules, publish runs, trend dossiers, and operator state are persisted through the existing store pattern

### WhatsApp phase-1 rules
- `agency_config.json.owner_phone` is the only operator
- non-owner numbers keep the existing client auto-reply path
- operator publishable media must arrive as WhatsApp `document`
- gallery `image` and `video` messages are rejected with resend guidance to preserve quality

## Startup

### API
```bash
cd /home/snowaflic/agents
uvicorn webhook_server:app --host 0.0.0.0 --port 8000
```

### Scheduler
```bash
cd /home/snowaflic/agents
python scheduler.py
```

### Tests
```bash
cd /home/snowaflic/agents
python -m pytest tests -v
```

### Syntax check
```bash
cd /home/snowaflic/agents
python -m py_compile webhook_server.py whatsapp_operator.py caption_agent.py
```

Important:
- `JARVIS_DATA_BACKEND` should be `supabase` in production
- `WEBHOOK_PROXY_URL` or a stable public HTTPS domain must point at the live API
- `WHATSAPP_TOKEN`, `WHATSAPP_TEST_PHONE_NUMBER_ID`, and `WEBHOOK_VERIFY_TOKEN` must be valid before using the WhatsApp lane
- `META_APP_ID`, `META_APP_SECRET`, and `META_OAUTH_REDIRECT_URI` or `META_OAUTH_PUBLIC_BASE_URL` must be configured before using `/connect`

## Current Product Decisions

### Phase-1 commitments
- WhatsApp is the primary operator workspace
- Dashboard work is frozen unless explicitly requested
- Existing approval, schedule, and publish flows are reused rather than replaced
- Supabase is treated as the production source of truth even while JSON fallback remains implemented internally

### Not production-complete yet
- full multi-operator access control
- richer client-facing WhatsApp concierge flows
- final deployment hardening on stable infrastructure

## Important Files

- [AGENTS.md](/home/snowaflic/agents/AGENTS.md)
- [ARCHITECTURE.md](/home/snowaflic/agents/ARCHITECTURE.md)
- [WHATSAPP_OPERATOR_SPEC.md](/home/snowaflic/agents/WHATSAPP_OPERATOR_SPEC.md)
- [webhook_server.py](/home/snowaflic/agents/webhook_server.py)
- [whatsapp_operator.py](/home/snowaflic/agents/whatsapp_operator.py)
- [whatsapp_transport.py](/home/snowaflic/agents/whatsapp_transport.py)
- [orchestrator_agent.py](/home/snowaflic/agents/orchestrator_agent.py)
- [caption_agent.py](/home/snowaflic/agents/caption_agent.py)
- [strategy_agent.py](/home/snowaflic/agents/strategy_agent.py)
- [publish_agent.py](/home/snowaflic/agents/publish_agent.py)
- [scheduler.py](/home/snowaflic/agents/scheduler.py)
- [runtime_state_store.py](/home/snowaflic/agents/runtime_state_store.py)
- [infra/supabase/schema.sql](/home/snowaflic/agents/infra/supabase/schema.sql)
- [CURRENT_STATE.md](/home/snowaflic/agents/CURRENT_STATE.md)
