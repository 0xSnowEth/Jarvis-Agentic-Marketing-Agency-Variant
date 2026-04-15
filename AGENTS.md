# Jarvis Agent Notes

## Runtime
- API: `uvicorn webhook_server:app --host 0.0.0.0 --port 8000`
- Scheduler: `python scheduler.py`
- Tests: `python -m pytest tests -v`
- Python syntax check: `python -m py_compile <file>.py`

## Primary Product Direction
- WhatsApp is the primary operator interface.
- `webhook_server.py` is the ingress hub.
- `orchestrator_agent.py`, `caption_agent.py`, `strategy_agent.py`, `publish_agent.py`, and `scheduler.py` are the existing spokes.
- `jarvis-dashboard.html` is frozen fallback UI in phase 1. Do not expand it unless explicitly asked.

## Storage Rules
- Production source of truth is Supabase.
- Internal JSON fallback still exists in store files and must not be broken casually.
- If you add persisted state, implement both JSON and Supabase paths.
- Current runtime state lives in `runtime_state_store.py`.

## High-Risk Files
- `webhook_server.py`: large FastAPI monolith, high blast radius.
- `jarvis-dashboard.html`: frozen unless directly requested.
- `scheduler.py`: keep subprocess pipeline path intact.

## WhatsApp Rules
- Owner phone in `agency_config.json.owner_phone` is the phase-1 operator.
- Non-owner WhatsApp numbers keep the existing client auto-reply path.
- Operator media must be sent as WhatsApp `document` for publish quality.
- Gallery `image` and `video` messages should be rejected with resend guidance.

## Environment
- `JARVIS_DATA_BACKEND`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `WHATSAPP_TOKEN`
- `WHATSAPP_TEST_PHONE_NUMBER_ID`
- `WEBHOOK_VERIFY_TOKEN`
- `WEBHOOK_PROXY_URL`
- `META_APP_ID`
- `META_APP_SECRET`
- `META_OAUTH_REDIRECT_URI` or `META_OAUTH_PUBLIC_BASE_URL`

## Current Backend Boundaries
- Reuse existing client synthesis and save routes for onboarding.
- Reuse existing draft, asset, schedule, approval, and publish flows.
- Do not invent a parallel publish pipeline for WhatsApp.
