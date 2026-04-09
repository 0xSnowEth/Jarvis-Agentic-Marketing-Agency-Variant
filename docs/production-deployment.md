# Jarvis Production Deployment

This document covers the production baseline for a single-agency VPS deployment.

## 1. Apply the runtime-state schema

Jarvis now expects these runtime tables in Supabase:

- `auth_sessions`
- `orchestrator_runs`
- `reschedule_sessions`
- `operator_audit_events`

Apply the SQL from:

- `/home/snowaflic/agents/infra/supabase/schema.sql`

If these tables are missing, `/api/health` will report `runtime_state` as unhealthy and restart-safe auth/run recovery will fall back to local JSON only.

## 2. Required environment

At minimum, production should set:

- `JARVIS_DATA_BACKEND=supabase`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `JARVIS_ADMIN_PASSWORD`
- `PUBLISH_MEDIA_BASE_URL` or `PUBLIC_ASSET_BASE_URL`
- `WEBHOOK_PROXY_URL` only if media is still being exposed through a tunnel

Recommended:

- `JARVIS_STRICT_STARTUP=1`
- `JARVIS_RUNTIME_STATE_DIR=/home/ubuntu/jarvis-runtime`

## 3. Install the services

Copy the systemd units:

- `/home/snowaflic/agents/infra/systemd/jarvis-api.service`
- `/home/snowaflic/agents/infra/systemd/jarvis-scheduler.service`

Then run on the VPS:

```bash
sudo cp /home/snowaflic/agents/infra/systemd/jarvis-api.service /etc/systemd/system/
sudo cp /home/snowaflic/agents/infra/systemd/jarvis-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable jarvis-api
sudo systemctl enable jarvis-scheduler
sudo systemctl start jarvis-api
sudo systemctl start jarvis-scheduler
```

## 4. Release gate

Do not treat a deployment as production-ready unless all of the following are true:

```bash
cd /home/snowaflic/agents
./venv/bin/python3 -m unittest discover -s tests -v
curl http://127.0.0.1:8000/api/health
```

Required health conditions:

- `health.api = online`
- `readiness.ok = true`
- `readiness.checks.runtime_state.ok = true`
- `readiness.checks.scheduler.ok = true`
- `readiness.checks.public_media_host.ok = true`

## 5. Operational notes

- Auth sessions are now durable and survive FastAPI restarts until expiry.
- Orchestrator run timelines are now durable and can be reopened after restart.
- Reschedule sessions are now durable and no longer depend on raw file-only state.
- Approval actions, auth events, and orchestrator run activity now emit operator audit events.
- Current rate limiting is process-local and intended as a first production baseline, not a final distributed limiter.
