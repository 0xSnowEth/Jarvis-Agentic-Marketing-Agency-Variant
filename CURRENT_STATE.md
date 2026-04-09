# Current State

This is the fastest file for a future session to read before continuing work.

## Product State

Jarvis is currently a working multi-client content operations system with:
- premium lock screen
- premium dashboard
- Jarvis chat as the main workflow
- WhatsApp as a mobile control lane
- schedule as an oversight/history surface

Approval Center has been removed as a visible primary workflow.

## What Works

- client synthesis
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
- video normalization on upload
- one-click repair for older stored videos
- schedule history / failed state handling

## What Was Fixed Recently

- approvals are now validated before entering the live schedule
- stale pending approvals are pruned
- dead public media host detection happens before publish
- Facebook is no longer blocked just because Instagram preflight fails
- partial-success replies are more deterministic
- retry for immediate publish exists
- draft mounting preserves names like `Image Post 1`
- purge history clears retained history states correctly

## Current UX Direction

### Keep
- Jarvis chat
- Schedule
- Vaults
- Client Config
- WhatsApp mobile lane

### Do not reintroduce as primary workflow
- Approval Center as a required page

## Current Biggest Remaining Product Task

Bilingual support.

Needed behavior:
- English brief synthesis
- Arabic brief synthesis
- English captions
- Arabic captions
- English brief with Arabic caption output
- per-client output language control

## Current Biggest Operational Risk

`WEBHOOK_PROXY_URL` must point to a live public media host.

If that URL is stale, Meta cannot fetch assets and publishing breaks.

For Instagram video reliability:
- Jarvis now expects a stable HTTPS public media host
- temporary `trycloudflare` URLs may work for testing but are not the production-safe delivery path

## Before Demo

1. Use two real clients
2. Use two separate Meta destinations
3. Verify:
   - lock / unlock
   - vault upload
   - draft generation
   - caption generation
   - inline approval
   - scheduled publish
   - immediate publish
   - restart persistence

## Next Build Order

1. bilingual support
2. final demo recording
3. stable public hosting / deployment
4. production QA pass
5. broader outreach
