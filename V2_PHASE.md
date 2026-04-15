# Next Phases

This file now tracks the real next phases of the product, not the old speculative split.

## Phase 1: Demo Readiness

This is the current immediate phase.

### Goal
Make the system stable, readable, and persuasive enough for real agency demos.

### Must-have checks
- two real client accounts
- isolated Meta credentials per client
- lock / unlock flow stable
- vault uploads stable
- draft creation stable
- caption generation stable
- inline approvals stable
- schedule page stable
- immediate publish stable
- one scheduled publish stable
- restart persistence verified

### Current blocker
- bilingual workflow is not fully implemented yet

## Phase 2: Strategy + Calendar Proof

This is the next major monetizable implementation target.

### Needed behavior
- saved strategy plans per client
- planned-but-not-scheduled items shown in Calendar
- materialized strategy suggestions for operator review
- early proof layer showing what was planned vs what shipped
- real strategy prompts from Jarvis assistant

### Files most likely to change
- `strategy_agent.py`
- `strategy_plan_store.py`
- `webhook_server.py`
- `jarvis-dashboard.html`

## Phase 3: Bilingual Support

### Needed behavior
- English brief synthesis
- Arabic brief synthesis
- English caption generation
- Arabic caption generation
- English brief -> Arabic caption support
- per-client language settings
- optional per-draft caption language override

### Files most likely to change
- `webhook_server.py`
- `caption_agent.py`
- `client_store.py`
- `jarvis-dashboard.html`

## Phase 4: Stable Public Delivery

### Goal
Remove dependence on fragile rotating quick tunnels.

### Needed
- stable public domain or stable tunnel
- production-like hosting path
- verified Meta media fetchability

## Phase 5: Deployment Hardening

### Goal
Run Jarvis as a serious hosted service instead of a local prototype stack.

### Needed
- VPS / Hetzner deployment
- process supervision
- clean restart scripts
- stable environment config
- operational runbook

## Phase 6: V2 Agency WhatsApp

Only after the above are stable.

### Goal
Expand WhatsApp from owner-control lane to deeper client/lead workflow where it genuinely adds value.

### Important
This should not bloat the current product before the core desktop + publish path is stable.
