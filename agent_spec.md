# Jarvis System Spec

This is the current high-level system spec, not the original early brainstorm.

## Goal

Jarvis is a multi-client agency operating system that helps a marketing agency:
- onboard clients
- store brand memory
- upload and organize creative assets
- create and manage drafts
- generate captions
- schedule or immediately publish to Facebook and Instagram
- route approvals through desktop chat or WhatsApp

The main product is not “many disconnected tools”. The main product is one operator lane centered on Jarvis chat.

## Core Product Rules

1. Jarvis chat is the front door.
2. WhatsApp is the mobile control lane, not a second dashboard.
3. Schedule is an oversight surface, not a mandatory workflow detour.
4. Approvals must be validated before they become executable jobs.
5. Jarvis must report real platform outcomes, not AI filler.

## Main Agents / Roles

### Lead Orchestrator
- interprets user intent
- distinguishes schedule vs immediate publish
- mounts client and draft context
- creates approval requests
- returns structured action metadata to the frontend

### Client Synthesizer
- turns raw intake text into client profile structure
- extracts brand voice, services, audience, SEO cues, and operating defaults
- currently strongest for Arabic-first content brands

### Caption Agent
- generates brand-aware captions from client context and draft/topic context
- currently Arabic-first
- should become bilingual next

### Publish Agent
- validates media and account readiness
- performs per-platform delivery
- returns honest platform breakdown

### Scheduler
- runs future jobs
- tracks active and history states
- marks failed jobs cleanly

### WhatsApp Lane
- sends owner approvals and controlled mobile actions
- respects the 24-hour reply window

## Current Workflow

1. Client is created or synthesized.
2. Profile + credentials are saved.
3. Assets are uploaded into that client’s vault.
4. Draft is created from the selected asset(s).
5. User asks Jarvis to schedule or post.
6. If approval is needed, Jarvis returns an inline approval card.
7. User approves in chat or routes to WhatsApp.
8. Approval is preflight-validated.
9. Job is scheduled or published.
10. Jarvis reports exact outcome.

## Storage Model

### Active backend
- Supabase

### Fallback
- JSON remains available for recovery / migration use

### Important data areas
- client profiles
- brand profiles
- schedule jobs
- approval records
- publish runs
- asset vault storage

## What Has Been Simplified

### Removed as primary workflow
- visible Approval Center as a required step

### Kept
- underlying approval model
- schedule oversight
- WhatsApp control path

This is intentional. The premium version of the product should reduce operator hopping, not increase it.

## Current Risks

1. Rotating public tunnel URL can break Meta media fetches.
2. Bilingual brief/caption support is still incomplete.
3. The frontend is a large single-file dashboard and requires disciplined sectioning when edited.

## Next Major Capability

### Bilingual support
Needed behavior:
- synthesize English briefs correctly
- still allow Arabic captions when the agency wants Arabic output
- support English-only, Arabic-only, or bilingual caption output per client / per draft

This is the next meaningful product upgrade before broader deployment.
