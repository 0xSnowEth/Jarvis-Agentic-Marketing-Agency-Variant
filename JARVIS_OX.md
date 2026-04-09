# Jarvis Master Spec

## Purpose

Jarvis is a premium agency operating system for content operations.

It is designed to let an agency operator manage multiple clients from one controlled lane, with:
- brand memory
- vault assets
- creative drafts
- caption generation
- approvals
- scheduling
- publishing

## Current UX Philosophy

The product should feel like one system.

That means:
- Jarvis chat is primary
- Schedule is secondary oversight
- WhatsApp is mobile control
- supporting pages should not compete with the main workflow

## Core Runtime

### `webhook_server.py`
- FastAPI API layer
- auth
- client synthesis
- dashboard summary
- vault endpoints
- approval actions
- WhatsApp webhooks

### `orchestrator_agent.py`
- natural language routing
- draft/client mounting
- schedule vs immediate publish logic
- structured action return

### `caption_agent.py`
- caption generation from brand profile
- currently strongest in Arabic mode

### `publish_agent.py`
- media validation
- platform-specific publish
- per-platform result reporting

### `scheduler.py`
- future execution daemon
- hot loads schedule store

## Data Model

### Backend
- Supabase is the intended active backend

### Fallback
- JSON exists for recovery / migration use

### Major stores
- client store
- draft store
- approval store
- schedule store
- publish run store
- asset store

## Current Product Boundary

### In
- content operations
- approvals
- scheduling
- direct publishing
- mobile control lane

### Not fully in yet
- bilingual full workflow
- deep client-facing WhatsApp inbox
- stable hosted public delivery

## Product Quality Rules

1. Do not silently accept work that will fail later.
2. Validate media and credentials before approval enters the live schedule.
3. Report real platform outcomes, not generic AI softening.
4. Keep workflow surfaces minimal and coherent.

## Strategic Direction

Jarvis should become a reusable vertical system:
- Jarvis Marketing
- Jarvis Leads
- Jarvis Real Estate

The lock screen, dashboard shell, and operating pattern can stay structurally similar across verticals, while:
- palette
- copy
- agent emphasis
- workflow details
change per domain.
