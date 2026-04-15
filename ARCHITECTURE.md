# Jarvis Architecture

## Product Positioning
- Jarvis is now a WhatsApp-first operator system.
- The backend is the product.
- The dashboard is frozen fallback UI in phase 1.

## Hub And Spoke

### Hub
- [webhook_server.py](/home/snowaflic/agents/webhook_server.py)
  - FastAPI ingress
  - WhatsApp webhook
  - client synthesis and profile save routes
  - Meta OAuth start and callback
  - approval routing and diagnostics

### Lead Brain
- [orchestrator_agent.py](/home/snowaflic/agents/orchestrator_agent.py)
  - scheduling
  - approval requests
  - immediate publish routing
  - client resolution

### Spokes
- [caption_agent.py](/home/snowaflic/agents/caption_agent.py)
  - caption generation
  - saved trend dossier reuse
  - quality gate loop
- [strategy_agent.py](/home/snowaflic/agents/strategy_agent.py)
  - strategy planning
  - research-backed plan generation
- [publish_agent.py](/home/snowaflic/agents/publish_agent.py)
  - Meta publish execution
  - media preflight
- [scheduler.py](/home/snowaflic/agents/scheduler.py)
  - future job execution

## WhatsApp Runtime

### Transport
- [whatsapp_transport.py](/home/snowaflic/agents/whatsapp_transport.py)
  - outbound text
  - outbound buttons and lists
  - inbound normalization
  - Meta media fetch

### Operator Lane
- [whatsapp_operator.py](/home/snowaflic/agents/whatsapp_operator.py)
  - single-operator routing via `agency_config.json.owner_phone`
  - onboarding state machine
  - client picker
  - media batch collection
  - caption preview loop
  - strategy replies
  - Meta connect handoff

### Client Lane
- [whatsapp_agent.py](/home/snowaflic/agents/whatsapp_agent.py)
  - existing inbound client triage and auto-reply path
  - preserved for non-operator phone numbers

## Persistence

### Production Source Of Truth
- Supabase

### Internal Fallback
- JSON store files remain available and must not be broken casually

### Runtime State
- [runtime_state_store.py](/home/snowaflic/agents/runtime_state_store.py)
  - auth sessions
  - orchestrator runs
  - reschedule sessions
  - operator sessions
  - operator audit events

### Business Data
- [client_store.py](/home/snowaflic/agents/client_store.py)
- [draft_store.py](/home/snowaflic/agents/draft_store.py)
- [asset_store.py](/home/snowaflic/agents/asset_store.py)
- [schedule_store.py](/home/snowaflic/agents/schedule_store.py)
- [approval_store.py](/home/snowaflic/agents/approval_store.py)

## Operator Workflow

### 1. Client Onboarding
- operator sends `/addclient`
- Jarvis asks the intake questions one by one
- Jarvis calls the existing synthesis and save routes
- background trend dossier build runs after save

### 2. Meta Connection
- operator sends `/connect @client`
- Jarvis sends browser handoff link
- callback stores page token, page id, and instagram account id
- Jarvis confirms back in WhatsApp

### 3. Media Intake
- operator sends image or video as WhatsApp `document`
- Jarvis collects documents for 10 seconds
- one image becomes image post
- multiple images become carousel
- one video becomes reel/video
- gallery image/video messages are rejected with resend guidance

### 4. Preview Loop
- Jarvis stores the media as assets
- Jarvis creates a normal draft bundle
- Jarvis generates caption and runs the quality gate
- Jarvis replies with preview
- operator replies with:
  - `yes`
  - `change ...`
  - `schedule ...`
  - `cancel`

### 5. Execution
- immediate publish uses the existing trigger-pipeline-now path
- future release uses the existing approval/schedule path

## Intentional Phase-1 Limits
- single operator only
- documents only for publishable operator media
- dashboard frozen, not deleted
- existing approval buttons preserved
- existing client auto-reply behavior preserved
