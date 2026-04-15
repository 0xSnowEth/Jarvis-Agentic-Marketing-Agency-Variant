# WhatsApp Operator Spec

## Scope
- phase 1 operator interface
- one owner phone only
- backend-first execution
- dashboard frozen fallback only

## Operator Identity
- operator phone is `agency_config.json.owner_phone`
- all other phone numbers stay on the client WhatsApp path unless explicitly changed later

## Commands

### `/help`
- returns the operator command list

### `/clients`
- returns saved clients
- each row should show client label, client id, and Meta connection status

### `/schedules`
- returns active scheduled jobs only
- each row should show client, topic or draft name, date, and time

### `/status`
- returns a compact operational summary:
  - total clients
  - connected Meta accounts
  - active scheduled jobs
  - operator phone

### `/addclient`
- starts the onboarding state machine

### `/connect @client`
- sends browser OAuth handoff link

### `/strategy @client ...`
- runs the strategy agent
- returns a compact WhatsApp-formatted summary

## Onboarding Questions
Ask exactly in this order:
1. business name
2. business type
3. main language
4. what they sell
5. target audience
6. brand tone
7. product or service examples
8. city or market
9. words to avoid
10. competitor or inspiration references

Rules:
- `skip` is allowed for words to avoid and inspirations
- client id is auto-generated from the business name
- onboarding uses the existing synthesis and save routes
- trend dossier build remains background-only

## Media Rules
- publishable operator media must come in as WhatsApp `document`
- gallery `image` and `video` messages are rejected with resend guidance
- accepted shapes:
  - 1 image document
  - 2 or more image documents within 10 seconds
  - 1 video document
- rejected shapes:
  - mixed image + video bundle
  - more than one video in one bundle

## Media Collection Window
- first document starts a 10-second collection window
- more documents inside that window join the same bundle
- free-text sent during the window updates the pending notes and can contain the client mention or scheduling hint

## Client Resolution
- explicit `@[client_id]` wins
- plain `@client_id` is accepted
- if only one client exists, Jarvis auto-scopes to it
- otherwise Jarvis sends a client picker list
- text fallback is allowed if interactive list does not load

## Draft Creation
- operator media becomes a normal creative draft
- stored through existing asset and draft stores
- no separate WhatsApp-only media pipeline

## Caption And Preview
- captions are generated through `caption_agent.py`
- the saved trend dossier should be reused
- the quality gate must run before preview
- preview response contains:
  - client
  - draft name
  - media shape
  - quality score
  - caption
  - hashtags
  - reply instructions

## Preview Replies

### `yes`
- if the original instruction clearly meant `now`, publish now
- if the original instruction clearly included a future window, schedule via approval flow
- otherwise ask for explicit release mode

### `change ...`
- regenerate caption with revision context
- keep the same draft bundle

### `schedule tomorrow 7pm`
- schedule through the existing approval path
- do not bypass approval unless intentionally changed later

### `cancel`
- clear the current operator session

## Meta OAuth
- `/connect @client` is the only first-class connection path in phase 1
- callback stores:
  - `meta_access_token`
  - `facebook_page_id`
  - `instagram_account_id`
- callback also updates profile metadata for connection visibility

## Observability
- operator flow events should be written through the existing operator audit event path
- operator sessions persist through `runtime_state_store.py`

## Production Assumptions
- Supabase is the production source of truth
- JSON fallback still exists internally
- this phase optimizes for shipping the operator workflow fast without deleting the rest of the system
