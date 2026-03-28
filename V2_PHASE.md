# Jarvis OS Marketing Variant — V2 Phase Spec

## Why this is V2, not the current demo

The current product is strongest when it stays focused on:
- client onboarding
- brand synthesis
- creative drafts
- caption generation
- approvals
- Meta scheduling and publishing

Per-client WhatsApp automation is intentionally **not** part of the current demo flow anymore, because it introduces:
- extra credentials per client
- another live operational surface
- more failure modes
- more explanation overhead during the sales demo

For the current phase, the agency-level WhatsApp layer is enough:
- owner approvals
- executive publish briefings
- escalation alerts

That keeps the prototype sharper and easier to demo.

---

## V2 Objective

Turn Jarvis into a true **agency-side follow-up employee** for multi-client operations.

This directly matches the pain point from [Client Brief.md](/home/snowaflic/agents/Client%20Brief.md):
- agencies dealing with Arab clients
- follow-up groups becoming a headache
- need for client follow-ups, lead handling, captions, scheduling, and SEO-friendly Arabic copy

V2 should solve:
- inbound lead follow-up
- client communication continuity
- brand-safe Arabic replies
- owner escalation when a conversation becomes risky

---

## The Use Case

Agency example:
- Orynx manages 3-5 client accounts
- Jarvis already handles content planning, captions, approvals, scheduling, and publishing
- V2 adds client-facing WhatsApp operations so Jarvis also handles lead and follow-up conversations

Real workflow:
1. A lead messages Client A's WhatsApp number.
2. Jarvis identifies the client account tied to that WhatsApp business line.
3. Jarvis loads Client A's brand profile, tone, services, offer rules, and banned phrasing.
4. Jarvis replies in Arabic/Khaleeji style that matches that client.
5. Jarvis answers basic questions, qualifies the lead, and keeps the conversation moving.
6. If the lead looks high-intent, Jarvis escalates or books the next step.
7. If the conversation turns sensitive, angry, or commercially risky, Jarvis alerts the agency owner.

This is where the "AI employee" story becomes much stronger.

---

## Features to Implement in V2

### 1. Per-Client WhatsApp Business Identity

Each client would optionally get:
- `whatsapp_access_token`
- `whatsapp_phone_number_id`
- `whatsapp_business_account_id`
- optional approved message template names

This is different from the current agency-level WhatsApp config.

Current:
- one agency WhatsApp identity for owner approvals and briefings

V2:
- one WhatsApp identity per client for real client-facing messaging

### 2. Client Conversation Routing

Jarvis should map incoming WhatsApp messages to the correct client by:
- phone number ID
- business account ID
- or the recipient WhatsApp line

That is the missing reason the per-client WhatsApp token field was confusing in the current demo:
- without conversation routing, the field had no real value

### 3. AI Account Manager

This is already hinted in [FEATURES.md](/home/snowaflic/agents/FEATURES.md) under `WhatsApp Client Features`.

V2 should make it real:
- brand-aware replies
- Arabic-first support
- service-specific answers
- answer common FAQs
- reassure clients about scheduled posts and campaign status

### 4. Lead Qualification Layer

Jarvis should classify incoming messages into:
- lead
- existing customer
- client asking for updates
- complaint / escalation
- spam / irrelevant

For leads, Jarvis should extract:
- service interest
- urgency
- budget signals
- booking intent
- contact details if shared

### 5. Escalation and Summary Engine

When a chat becomes sensitive, Jarvis should:
- stop autonomous replies
- ping the agency owner
- send a compact summary

Example summary:
- client
- lead/customer status
- current sentiment
- what was asked
- what Jarvis already replied with
- recommended next action

### 6. Internal Lead Inbox

V2 should add a dashboard inbox with:
- open conversations
- lead status
- last reply time
- escalation markers
- assigned client

That keeps the agency from living inside WhatsApp threads blindly.

---

## Why this is commercially strong

From the client brief, the pain is not only posting.
It is:
- keeping up with follow-ups
- handling Arab clients properly
- managing multiple clients at once

The premium V2 sell becomes:

"Jarvis does not only post content. It also keeps the conversation moving, qualifies leads, and keeps your agency responsive without adding headcount."

That is much closer to a real monthly-retainer product.

---

## Suggested Technical Implementation

When the product moves beyond demo stage, implement V2 on top of the production migration:

### Database
- `whatsapp_client_channels`
- `whatsapp_threads`
- `whatsapp_messages`
- `lead_records`
- `lead_events`
- `escalation_events`

### Storage
- conversation summaries
- message attachments if needed later

### Runtime
- inbound webhook receiver
- routing layer by recipient line
- brand-aware reply agent
- triage/escalation agent
- lead extraction worker

### Agency Controls
- per-client enable/disable switch
- office hours / response rules
- escalation keywords
- do-not-reply scenarios
- human handoff mode

---

## Demo Boundary

For the current demo version:
- keep per-client WhatsApp auth hidden
- keep agency WhatsApp visible
- focus the story on content operations and owner approval polish

For V2:
- reintroduce per-client WhatsApp credentials only when inbound client conversation routing is actually implemented

That keeps the product coherent instead of prematurely exposing a half-used field.
