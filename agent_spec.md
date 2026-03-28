# AGENT SPECS.
## 6 Questions to answer before we build.

Q1: What is the agent's specific goal?

Answer: 
Automatically generate Arabic, SEO-friendly captions, schedule and publish posts to Facebook and Instagram, and manage WhatsApp-based client follow-ups — across 3 client accounts — without human intervention. 


Q2 2. TOOLS REQUIRED:

Tool 1: LLM (Claude Opus 4.6 or GPT-5)
Function: Arabic caption generation, SEO optimization, content ideation
Access: Read-Write
External System: Anthropic / OpenAI API
Status: Confirmed
While we build: we use a free openrouter model like gpt-4o-mini for now, later we can upgrade to opus 4.6 or gpt-5.3 after client has paid for it.

Tool 2: Meta Graph API
Function: Schedule + publish posts to Facebook & Instagram
Access: Read-Write
External System: Meta Business Suite
Status: Confirmed

Tool 3: WhatsApp Business API (or Baileys/WA-Web)
Function: Read group messages, send follow-up responses
Access: Read-Write
External System: WhatsApp
Status: Confirmed

Tool 4: Cron / Heartbeat Scheduler
Function: Trigger agent on defined posting schedule
Access: Read-Write
Internal System: Internal scheduler
Status: Confirmed

Tool 5: Brand Voice Store
Function: Stores per-client tone, keywords, SEO tags
Access: Read-Write
External System: Local DB / JSON / Notion
Status: Confirmed execept that we'll use a made up brand voice for now in which we create and test with since we dont have any client data yet

Tool 6: Logging Layer
Function: Records every action taken per client per run
Access: Read-Write
External System: Internal (DB or Sheet)
Status: Confirmed in principle

Tool 7: Briefing/Notification Channel
Function: Sends owner a summary after each run
Access: Read-Write
External System: NOT SPECIFIED⚠ 



3. STARTING INFORMATION:

Answer: The following must be provided before the agent could run, if any of these are missing the agent halts and logs a missing-input error:

1. Per Client: Facebook PAGE id + Instagram business account id + meta api access token
2. Per Client: WhatsApp Group ID's designated for follow ups.
3. Per Client: Brand voice profile (tone descriptors, Arabic dialect preference, banned words, key services)
4. Per Client: SEO keyword list (arabic) for caption ingestion
5. Per run: Raw content assets (images/videos) + campaign brief — provided by the agency
6. Global: Posting schedule (days, times per client)
7. Global: LLM API key (we'll use a free openrouter model like gpt-4o-mini for now, later we can upgrade to opus 4.6 or gpt-5.3 after client has paid for it)



4. WHAT SUCCESS LOOKS LIKE
Caption Generation:
Arabic caption, 150–300 characters [DEFAULT — not confirmed by client], 3–5 Arabic hashtags, minimum 1 target SEO keyword embedded naturally, matched to provided brand voice profile.
[Source: "captions needs to be arabic and SEO friendly"]
Post Scheduling & Publishing:
Post (image/video + caption) published to Facebook Page AND Instagram Business account at the scheduled time. Meta API confirmation ID logged per post.
[Source: "schedule post… in meta" + "Facebook, Instagram" — Q1 answer]
WhatsApp Follow-Up:
Inbound message in client group detected → response sent within [DEFAULT: 5 minutes — not confirmed by client], in Arabic, in the client's brand voice. Message thread logged with timestamp, content, and client name.
[Source: "groups with the clients for follow up and thats the most headache"]
Run Briefing:
After each completed run, owner receives a structured summary including: posts published (per client), captions generated, follow-ups handled, and any errors.
Channel: NOT SPECIFIED — needs clarification.








5. WHAT FAILURE LOOKS LIKE
Failure ModeTriggerAgent ActionLogged?Missing content assetsAgency didn't upload image/video before runHalt that client's posting task, continue othersYes — client name + timestampMeta API auth failureToken expired or revokedHalt posting, escalate to human immediatelyYes — error code + clientWhatsApp session dropWA connection lost mid-sessionRetry × 3 (5-min intervals), then escalateYes — retry count + timestampsLLM returns non-Arabic outputModel produces English or mixed contentRetry with explicit Arabic-only prompt × 2, then flag for human reviewYes — raw LLM output savedCaption exceeds character limitLLM over-generatesAuto-truncate at nearest sentence boundary, flag in logYesNo brand voice profile foundNew client onboarded without profile setupHalt all tasks for that clientYes — hard stop, no guessing






6. WHEN TO ASK A HUMAN
TriggerEscalation ActionMeta API token expired for any clientImmediate alert — human must re-auth before next runWhatsApp session fails after 3 retriesAlert sent — human must restart sessionInbound WA message classified as complaint or legal threat (sentiment threshold)Do NOT auto-respond — flag for human review immediatelyBrand voice profile missing for a clientBlock that client's entire run until profile is submittedLLM produces off-brand or inappropriate Arabic content (2nd retry fail)Hold caption, send draft to human for approvalNotification channel:NOT SPECIFIED — needs clarification. Could be WhatsApp message to owner, email summary, or Google Sheet dashboard
[Source: "gives you briefings once finished" — channel undefined]

WHAT YOU CAN BUILD NOW vs WHAT NEEDS CLARIFICATION
✅ BUILD NOW — Unblocked

Caption generation module (Arabic, SEO-injected, brand-voice-matched)
Meta Graph API integration for Facebook + Instagram posting
Cron-based scheduling engine (per client, per platform)
WhatsApp listener + auto-responder (brand voice, Arabic)
Per-client brand voice profile schema + storage
Logging layer (all actions, errors, timestamps)
Failure handling logic (retry, halt, escalate triggers)

 — Needs Clarification Before Building
Blocked ItemWhat's MissingOwner briefing / notification systemQ5 was not answered — WhatsApp? Email? Sheet?Brand voice profile storage formatNotion? JSON file? Google Sheet? Needs decisionWhatsApp API methodPersonal number (Baileys/unofficial) vs WhatsApp Business API (Meta-approved) — legal and cost implications differ significantlyPost frequency / scheduleDays and times per client not definedArabic dialect preferenceGulf? Levantine? Modern Standard Arabic? Affects caption quality

Spec produced under Principle 1: no invented details. All claims sourced. All gaps named. Sonnet 4.6Extended






⚠ BLOCKED — Needs Clarification Before Building
Blocked ItemWhat's MissingOwner briefing / notification systemQ5 was not answered — WhatsApp? Email? Sheet?Brand voice profile storage formatNotion? JSON file? Google Sheet? Needs decisionWhatsApp API methodPersonal number (Baileys/unofficial) vs WhatsApp Business API (Meta-approved) — legal and cost implications differ significantlyPost frequency / scheduleDays and times per client not definedArabic dialect preferenceGulf? Levantine? Modern Standard Arabic? Affects caption quality