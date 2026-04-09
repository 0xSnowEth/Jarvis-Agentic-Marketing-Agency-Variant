# Caption Agent Spec

This file documents the current caption agent and the next required extension.

## Current Goal

Generate brand-aware social captions for saved client drafts and content topics.

Today the agent is strongest when the target output is Arabic. It uses:
- client brand profile
- services
- target audience
- SEO keywords
- hashtag bank
- brand voice examples

## Current Inputs

- `client_id`
- draft/topic context
- media type
- stored brand profile

## Current Outputs

- caption text
- hashtags
- structured payload used by the dashboard / pipeline

## Current Reality

The current implementation is Arabic-first.

That was correct for the earliest customer brief, but it is now a limitation because the system needs to support:
- English-language clients
- Arabic-language clients
- English briefs that still require Arabic captions

## Required Upgrade

The next version of the caption agent must support separated language concerns:

### 1. Brief language
What language the agency used when writing the intake / client brief.

### 2. Brand primary language
What language the client primarily communicates in.

### 3. Caption output language
What language Jarvis should generate for publishing.

These are not always the same.

Example:
- brief language: English
- brand primary language: Arabic
- caption output language: Arabic

## Proposed Minimal Data Shape

Add a language profile to the stored client profile:

```json
{
  "language_profile": {
    "brief_language": "english",
    "primary_language": "arabic",
    "caption_output_language": "arabic",
    "arabic_mode": "gulf"
  }
}
```

## Required Behavior

### Arabic output
- natural Gulf Arabic when configured
- not robotic MSA unless explicitly requested

### English output
- clean premium agency English
- not literal Arabic-to-English translation

### Bilingual output
- optional mode for mixed campaigns
- must be explicit, not accidental

## Required UI Support

The dashboard should expose:
- primary language
- caption output language
- optional per-draft override

## What Not To Do

- do not guess Arabic output just because the system was originally Arabic-first
- do not assume the brief language is the publish language
- do not hide the chosen output language from the operator

## Current Priority

This bilingual extension is one of the highest-value remaining product upgrades before broader demos and deployment.
