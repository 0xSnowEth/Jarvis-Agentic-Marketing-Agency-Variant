# Internal Trial Lockdown

Run one more fake-client validation pass before sending Jarvis to the real client.

## What this does

The harness in [scripts/internal_trial_lockdown.py](/home/snowaflic/agents/scripts/internal_trial_lockdown.py) will:

- seed 2 fake clients
- synthesize and save their brand profiles
- upload assets and create working drafts
- run caption fidelity scenarios
- run strategy-agent scenarios
- run approval / move / reject workflow checks
- verify restart recovery if you provide a restart command
- write JSON + Markdown reports into `/home/snowaflic/agents/tmp`

## Default fake clients

- `Northline Dental`
- `Cedar Atelier`

The fixture pack lives in [scripts/internal_trial_fixtures.json](/home/snowaflic/agents/scripts/internal_trial_fixtures.json).

## Before you run it

1. Start FastAPI.
2. Start the scheduler.
3. Make sure `JARVIS_ADMIN_PASSWORD` is available in your shell.
4. If you want one fake client to validate the full live publish lane, export these too:
   - `DEMO_META_ACCESS_TOKEN`
   - `DEMO_FACEBOOK_PAGE_ID`
   - `DEMO_INSTAGRAM_ACCOUNT_ID`

Without those demo Meta variables, the harness will still validate synthesis, captions, strategy, and approval creation, but it will mark approve-to-schedule and live publish as not fully green.

## Recommended run

```bash
cd /home/snowaflic/agents
./venv/bin/python3 scripts/internal_trial_lockdown.py
```

## Recommended run with restart recovery

Use a restart command so the script can kill and relaunch FastAPI, then verify the same auth session still works.

Example:

```bash
cd /home/snowaflic/agents
./venv/bin/python3 scripts/internal_trial_lockdown.py \
  --restart-command "bash -lc 'cd /home/snowaflic/agents && fuser -k 8000/tcp 2>/dev/null || true && nohup ./venv/bin/python3 -m uvicorn webhook_server:app --host 0.0.0.0 --port 8000 > tmp/internal_trial_uvicorn.log 2>&1 &'"
```

## Reports

The harness writes:

- `tmp/internal-trial-lockdown-<timestamp>.json`
- `tmp/internal-trial-lockdown-<timestamp>.md`

Read the Markdown report first. Use the JSON report if you want the raw outputs.

## Green means

Do not go back to the client until the report is green or at least green enough for the lane you want to trial.

Target checks:

- both fake clients pass caption fidelity
- both fake clients pass strategy usefulness
- at least one workflow succeeds without backend rescue
- restart recovery passes
- `/api/health` is green enough for the trial lane

## How he accesses Jarvis on his device

Jarvis stays hosted on your side.

Trial-day flow:

1. Run FastAPI.
2. Run the scheduler.
3. Expose Jarvis over HTTPS.
   - best: VPS + domain
   - acceptable for guided trial: Cloudflare tunnel
4. Confirm [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health).
5. Send him the hosted `/app` URL and the Jarvis login password.
6. He opens it from his own browser. Nothing is installed on his laptop.

Operationally:

- you control infra, tokens, scheduler, runtime state, and logs
- he controls actual product usage from his device
