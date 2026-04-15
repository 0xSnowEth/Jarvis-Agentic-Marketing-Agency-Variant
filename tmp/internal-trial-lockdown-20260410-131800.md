# Internal Trial Lockdown Report

- Generated at: `2026-04-10T13:18:05.028992+00:00`
- Base URL: `http://127.0.0.1:8000`
- Overall status: `red`
- Go / No-Go: `no_go`

## Readiness

- Health before: `False`
- Health after: `False`

## Restart Recovery

- Passed: `False`
- Details: Restart command not provided. Recovery verification was skipped.

## Northline Dental

- Synthesis passed: `True`
- Caption suite passed: `True`
- Strategy suite passed: `True`
- Workflow hard pass: `True`

### Notes

- Live publish was not validated for this fake client. Add demo Meta credentials if you need a full green publish lane.

## Cedar Atelier

- Synthesis passed: `True`
- Caption suite passed: `False`
- Strategy suite passed: `True`
- Workflow hard pass: `True`

### Notes

- Caption fidelity suite is not green yet.
- Live publish was not validated for this fake client. Add demo Meta credentials if you need a full green publish lane.

## Device Access Model

- Keep Jarvis hosted on your side.
- Run FastAPI and the scheduler.
- Expose `/app` over HTTPS through your VPS/domain or Cloudflare tunnel.
- Confirm `/api/health` before sending the URL.
- Send him the hosted `/app` URL plus the trial login password.
- He uses Jarvis from his browser on his own device; nothing is installed locally.
