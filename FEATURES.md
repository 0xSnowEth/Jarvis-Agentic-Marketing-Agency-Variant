# Jarvis Feature Registry

This file is the current capability map for Jarvis as of the latest working state of the repo.

## 1. Product Flow

### Primary flow
- Jarvis chat is the main command surface
- inline approval cards handle approve / move time / discard / WhatsApp routing
- schedule page is for oversight and history
- vaults and client config support the content workflow

### Secondary flow
- WhatsApp acts as a mobile control lane for:
  - owner approvals
  - urgent review
  - failure alerts
  - executive summaries

## 2. Client Onboarding

- AI client synthesis from pasted brief or uploaded text file
- client profile persistence
- separated brand profile and live credential storage
- client config editing from dashboard
- no auto-popup operating brief after save

## 3. Brand Memory

- stored tone / audience / services / SEO keywords / hashtag bank
- brand voice examples
- client-isolated profile loading
- Jarvis context mounting through `@client`

## 4. Asset Vaults

- per-client asset isolation
- upload multiple files
- images, carousels, and videos
- old vault videos can be repaired for Meta
- new uploaded videos are normalized automatically for Meta-safe publishing
- scheduled drafts are hidden from the visible draft queue but retained for execution
- immediate successful posts clear the draft queue entry

## 5. Creative Drafts

- draft creation from vault assets
- draft rename
- Copy Studio editing
- caption regeneration
- manual caption editing
- draft references can be mounted into Jarvis chat reliably

## 6. Jarvis Chat

- natural language scheduling
- natural language immediate publish
- inline approval cards
- retry support for failed immediate publish attempts
- deterministic tool-first replies for publish outcomes
- less filler, more exact platform result reporting

## 7. Approvals

- pending approvals can be created by Jarvis
- approvals can be handled:
  - inline in chat
  - via WhatsApp
- approval preflight now validates:
  - media compatibility
  - live Meta credentials
  - schedule timing
- invalid approvals are blocked before they reach live schedule

## 8. WhatsApp

- owner approval routing
- 24-hour reply window enforcement
- inbound message window tracking
- approval card delivery guardrails
- WhatsApp remains part of the system, but is no longer the main UX surface

## 9. Scheduling

- one-off scheduling
- relative scheduling phrases
- active vs history separation
- failed jobs marked `failed`
- purge history removes retained history states
- stale approvals pruned when they already became scheduled or expired

## 10. Publishing

- Facebook image posting
- Facebook video posting
- Instagram image posting
- Instagram reel/video posting
- platform-specific result reporting
- partial success reporting
- dead public asset URL detection before publish
- Instagram image/video compatibility preflight

## 11. Media Safety / Compatibility

- Instagram-incompatible images are flagged
- non-safe video audio/video profiles are detected
- transport preflight checks public media fetchability
- Meta-safe video normalization on upload
- one-click repair for older stored videos

## 12. Dashboard

- premium lock screen
- simplified production-like dashboard
- operations snapshot
- live agent status
- section notification pings
- no visible “demo” framing in the main flow

## 13. Live Agent Status

The dashboard now surfaces active roles conceptually:
- Orchestrator
- Client Synthesizer
- Caption Agent
- Publish Agent
- Scheduler
- WhatsApp Lane

These cards are used to make the system easier to read for non-technical viewers.

## 14. Known Gaps

- bilingual English/Arabic brief and caption workflow is not fully implemented yet
- stable production domain still needed; rotating tunnel URLs are fragile
- no full client-facing WhatsApp inbox product yet
- no deep autonomous troubleshooting engine yet

## 15. Product Principle

Jarvis should report what actually happened.

That means:
- no fake “everything worked” language
- no vague troubleshooting promises unless there is a real recovery path
- per-platform outcomes must be surfaced honestly
