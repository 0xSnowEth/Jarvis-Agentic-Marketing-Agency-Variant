# Jarvis Model Roadmap

This file is the source of truth for the current free-first model stack and the exact paid replacements to use later.

## Current Rule

- While closing clients, Jarvis should prefer free or near-free models first.
- Paid models are optional upgrades, not default requirements.
- The caption system should work without `ANTHROPIC_API_KEY`.

## Current Free-First Stack

### Caption Generation

- Primary:
  - `CAPTION_MODEL=llama-3.1-8b-instant`
  - Provider: Groq
  - Use for: main caption draft generation, rewrite passes, hidden alternate generation

- Free fallback:
  - `CAPTION_FALLBACK_MODEL=qwen/qwen3.6-plus-preview:free`
  - Provider: OpenRouter
  - Use for: backup text generation only if the primary Groq route fails

### Media Understanding

- Current default:
  - `VISION_ANALYSIS_MODE=heuristic`
  - Provider: local code only
  - Use for: image/carousel/video bundle analysis without any paid vision API

### WhatsApp / Operator Reasoning

- Current:
  - `WHATSAPP_MODEL=openai/gpt-4o-mini`
  - `TRIAGE_MODEL=openai/gpt-4o-mini`
  - Use for: operator chat, menu recovery, client-facing routing logic

### Client Synthesis

- Current:
  - `SYNTHESIZER_MODEL=qwen/qwen3.6-plus-preview:free`
  - Use for: onboarding profile synthesis and source-driven client building

### Trend Dossier

- Current:
  - `TREND_DOSSIER_MODEL=openai/gpt-4o-mini`
  - Use for: trend distillation and strategy support

## Paid Upgrade Targets

These are the exact paid replacements to switch to after client revenue starts covering API usage.

### Premium Caption Generation

- Recommended paid target:
  - `ANTHROPIC_CAPTION_MODEL=claude-3-7-sonnet-latest`
  - Use for: multimodal caption generation, richer rewrites, stronger hidden alternates

### Premium Media Understanding

- Recommended paid target:
  - `ANTHROPIC_VISION_MODEL=claude-3-7-sonnet-latest`
  - Use for: real image/video-aware media analysis instead of heuristic-only visual grounding

### Premium Operator / Orchestration

- Recommended paid target:
  - `WHATSAPP_MODEL=gpt-5.4-mini`
  - `TRIAGE_MODEL=gpt-5.4-mini`
  - Use for: stronger operator conversation quality, instruction following, and recovery behavior

### Premium Client Synthesis

- Recommended paid target:
  - `SYNTHESIZER_MODEL=gpt-5.4-mini`
  - Use for: higher-trust onboarding synthesis from briefs, documents, and websites

### Premium Trend Distillation

- Recommended paid target:
  - `TREND_DOSSIER_MODEL=gpt-5.4-mini`
  - Use for: better trend compression, cleaner hooks, better strategy summaries

## How To Switch Later

### Upgrade caption generation to paid Anthropic

1. Add `ANTHROPIC_API_KEY` to `.env`
2. Set:
   - `ANTHROPIC_CAPTION_MODEL=claude-3-7-sonnet-latest`
   - `ANTHROPIC_VISION_MODEL=claude-3-7-sonnet-latest`
   - `VISION_ANALYSIS_MODE=anthropic`
3. Keep Groq or OpenRouter as fallback if desired

### Upgrade operator and synthesis quality

Replace these env vars when ready:

- `WHATSAPP_MODEL=gpt-5.4-mini`
- `TRIAGE_MODEL=gpt-5.4-mini`
- `SYNTHESIZER_MODEL=gpt-5.4-mini`
- `TREND_DOSSIER_MODEL=gpt-5.4-mini`

## Practical Intent

- Right now: free-first, good enough to replicate the premium workflow shape.
- Later: swap env vars to the paid targets above without redesigning the system again.
