# Jarvis WhatsApp Intended Behaviour

This file is the source-of-truth reference for the intended end-to-end operator workflow in the WhatsApp-first Jarvis build.

## Core Product Direction

- WhatsApp is the primary operator interface.
- The operator is the number configured in `agency_config.json.owner_phone`.
- The dashboard is frozen fallback only.
- Operator media for posts must be sent as WhatsApp `Document`.
- Normal gallery `image` and `video` messages must be rejected with resend guidance.

## Root Entry

The following messages must all re-anchor the operator to the same root experience:

- `hey jarvis`
- `hi jarvis`
- `hello jarvis`
- `/help`
- `/menu`
- `/start`

### Root Menu

Jarvis should send a premium greeting and 3 buttons:

1. `New Post`
2. `Add Client`
3. `More`

If interactive buttons fail, Jarvis must fall back to clean structured text that lists the same 3 actions.

## Root Button Behaviour

### `New Post`

Expected result:

- Jarvis opens a client picker.
- If only one client exists, Jarvis may go directly into that client’s media flow.
- After client selection, Jarvis asks the operator to send media as WhatsApp `Document`.

### `Add Client`

Expected result:

- Jarvis opens a second-level Add Client mode picker with exactly 3 buttons:
  - `Quick Brief`
  - `Import Brief`
  - `Scan Website`

### `More`

Expected result:

- Jarvis opens a list menu with:
  - `Strategy`
  - `Connect Meta`
  - `Clients`
  - `Schedules`
  - `Status`
  - `Help`

## Add Client Modes

### 1. `Quick Brief`

Expected result:

- Jarvis sends a one-message structured intake template.
- The operator pastes the full client brief in one go.
- Jarvis synthesizes the profile.
- The operator-provided onboarding facts remain authoritative for:
  - main language
  - business type
  - audience
  - brand tone
  - city/market
- Jarvis saves the client.
- Jarvis sends a success card with:
  - `Connect Meta`
  - `New Post`
  - `Open Menu`

If the intake is incomplete:

- Jarvis must not restart the whole flow.
- Jarvis must ask only for missing critical fields using a small numbered mini-template.

### 2. `Import Brief`

Expected result:

- Jarvis asks for a client brief as WhatsApp `Document`.
- Supported types:
  - PDF
  - DOCX
  - TXT
  - MD
- Jarvis downloads the file.
- Jarvis parses the file contents.
- Jarvis synthesizes the client profile from the parsed text.
- Jarvis saves the client or asks only for missing critical fields.

Important routing rule:

- While waiting for a client brief document, inbound documents must not be treated as post media.

### 3. `Scan Website`

Expected result:

- Jarvis asks for a single public website URL.
- Jarvis validates the URL.
- Jarvis runs the existing website enrichment and synthesis path.
- Jarvis saves the client or asks only for missing critical fields.

If the message is not a valid public URL:

- Jarvis must reply with a precise correction message.

## Add Client Success State

After a successful client save:

- Jarvis sends a “Client Added” card.
- The card must show the actual saved client ID.
- The card must provide buttons for:
  - `Connect Meta`
  - `New Post`
  - `Open Menu`

### `Connect Meta`

Expected result:

- Jarvis uses the actual saved client ID.
- Jarvis builds the Meta OAuth connect link.
- Jarvis sends the link to the operator.
- After the callback completes, Jarvis confirms the connection in WhatsApp.

## New Post Flow

### Step 1: Choose Client

Expected result:

- Jarvis opens a client picker.
- After selection, Jarvis anchors the session to that client.

### Step 2: Wait for Media

Expected result:

- Jarvis asks for media as WhatsApp `Document`.
- Jarvis explains that it will collect multiple documents for up to 10 seconds.

### Gallery Rejection

If the operator sends normal gallery `image` or `video`:

- Jarvis must reject it.
- Jarvis must ask the operator to resend as WhatsApp `Document`.

### Document Intake

If the operator sends one valid image or video document:

- Jarvis stores it in the active post collection.
- Jarvis sends a bundle-specific progress message:
  - first image -> `Image received`
  - second-or-later image -> `Carousel bundle updated`
  - one video -> `Video received`
- Jarvis waits up to 10 seconds in case more documents arrive.
- Every newly accepted document resets that 10-second bundle window.

If the operator sends 2 or more image documents inside the collection window:

- Jarvis should build a carousel draft.

If the operator sends 1 video document:

- Jarvis should build a video/reel draft.

If the operator sends mixed media into the same bundle:

- Jarvis must reject it cleanly before preview generation.
- One bundle may contain either:
  - one-or-more image documents
  - exactly one video document

If the operator sends notes during `media_collect`:

- Jarvis must keep the bundle alive.
- Jarvis must save the notes and extend the collection window by 10 seconds.

If the operator sends a new document after preview is already open:

- Jarvis must not overwrite the preview session.
- Jarvis must ask the operator to finish or cancel the preview first.

## Preview Flow

After the collection window closes:

- Jarvis materializes the draft.
- Jarvis shows a concise premium progress sequence while the caption is being prepared:
  - `Drafting caption`
  - `Ranking the variants`
  - `Tightening the draft` only if the first pass misses threshold
  - further model rewrite passes before any deterministic fallback is considered
- Jarvis generates the caption.
- Jarvis runs the internal multimodal ranking and review layer.
- Jarvis keeps one winning caption for WhatsApp and stores hidden alternates internally for revision flows.
- Jarvis sends a preview card that includes:
  - client
  - format
  - optional clean direction when the operator brief is human-readable
  - caption
  - hashtags
  - quality verdict
  - compact quality snapshot across voice, specificity, humanizer, length, and engagement

The preview must not expose:

- raw bundle names
- timestamps
- internal labels such as `WhatsApp Carousel`
- internal phrases such as `carousel concept` or `reel concept`

The preview must include 3 buttons:

1. `Post Now`
2. `Schedule`
3. `Revise`

### `Revise`

Expected result:

- Jarvis asks for revision notes or accepts a free-text change request.
- If hidden alternates already exist, Jarvis may promote the next strongest alternate before regenerating from scratch.
- Revision requests are not limited to a single tone tweak. The operator can ask for combinations such as:
  - sharper
  - more premium
  - more local to Kuwait
  - shorter
  - warmer
  - more direct
- Jarvis regenerates the caption.
- The new caption must differ in hook and hashtag selection where possible.
- The revision examples shown in WhatsApp are examples only, not hard limits.

### `Schedule`

Expected result:

- Jarvis asks for a schedule instruction such as:
  - `today 2pm`
  - `tomorrow 7pm`
  - `monday 6am`
  - `friday 17 at 6am`
- Jarvis routes into the existing safe scheduling path.
- If the first reply is missing a usable time, Jarvis stays in schedule mode and waits for the corrected follow-up instead of dropping the preview context.
- Jarvis confirms the scheduled result.

### `Post Now`

Expected result:

- Jarvis routes into the existing publish path.
- Jarvis returns the publish result in WhatsApp.

## More Menu Behaviour

### `Strategy`

Expected result:

- Jarvis opens a client picker if needed.
- Jarvis then asks what strategy to build.
- Jarvis routes into the existing strategy flow.
- Jarvis returns a summarized strategy response in WhatsApp.

### `Clients`

Expected result:

- Jarvis returns a clean client summary list.

### `Schedules`

Expected result:

- Jarvis returns upcoming scheduled releases.

### `Status`

Expected result:

- Jarvis returns operator/backend status.

### `Help`

Expected result:

- Jarvis re-anchors to the root menu.

## Recovery Behaviour

### `/cancel`

Expected result:

- Jarvis clears the active operator session.

## Language Behaviour

- If onboarding sets `main_language = arabic`, caption output must be Arabic only.
- If onboarding sets `main_language = english`, caption output must be English only.
- The operator's chosen main language must override any contrary guess coming back from synthesis.
- Jarvis confirms the flow was cancelled.

### Delayed Replies

If the operator replies late:

- Jarvis should continue from the active session if the state is still valid.
- If the state is no longer clear, Jarvis should re-anchor with a clean next-step prompt.

### Build In Progress

If the operator sends other messages while a client build is still running:

- Jarvis must not corrupt the intake.
- Jarvis must reply that the build is still running and that it will confirm automatically when complete.

## Language Behaviour

The selected client language governs later caption generation:

- `arabic` -> captions and hashtags should be Arabic
- `english` -> captions and hashtags should be English

This remains true even if the original intake or source brief was written in another language.

## Expected Response Times

Target expectations:

- Root menu or button response: usually 1 to 3 seconds
- Quick Brief save: usually 5 to 20 seconds
- Import Brief parse + save: usually 10 to 30 seconds
- Scan Website: usually 15 to 45 seconds
- Caption preview after media: usually 10 to 30 seconds

If Jarvis exceeds these windows without sending a progress or result message, treat that as a bug.

## Production Safety Rules

- Never expose raw Python objects or stack traces in WhatsApp.
- Never accept gallery media as production post media.
- Never restart a full client intake if only a few fields are missing.
- Always provide a next step after a major state transition.
- Always let `/cancel` and `hey jarvis` recover the operator from a confused state.
