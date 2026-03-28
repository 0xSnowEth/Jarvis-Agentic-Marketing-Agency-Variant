# Caption Generation Agent — Spec

## 1. Goal

Generate Gulf Arabic (خليجي), SEO-friendly social media captions in a client's brand voice for Facebook and Instagram.

This is agent #1 of a larger system. It does NOT schedule posts, manage WhatsApp, or run ads. Only caption generation.

## 2. Tools

**Tool 1: `load_brand_profile`**
- Reads a client's brand voice JSON file from `brands/{client_name}.json`
- Returns: tone, dialect, banned words, SEO keywords, hashtag bank, services offered
- Read-only

**Tool 2: `generate_caption`**
- Takes the brand profile + a content topic + target platform (instagram/facebook)
- Uses the LLM to produce the caption
- Returns: Arabic caption (150–300 chars), 3–5 Arabic hashtags, embedded SEO keyword
- The LLM IS the tool here — no external caption API

That's it. 2 tools.

## 3. Starting Information (required per run)

| Input | Example | Required? |
|---|---|---|
| Client name | `"client_a"` | Yes — maps to brand profile JSON |
| Content topic | `"summer real estate deals in Dubai"` | Yes |
| Platform | `"instagram"` or `"facebook"` | Yes — affects caption length/style |
| Image/video description | `"luxury villa pool shot"` | Optional — helps caption relevance |

If client name doesn't match any brand profile file → agent halts, logs error. No guessing.

## 4. What Success Looks Like

A successful run produces:

- Caption in **Gulf Arabic** (not MSA, not Egyptian)
- **150–300 characters** (adjustable per client later)
- **3–5 Arabic hashtags** relevant to the topic and industry
- At least **1 SEO keyword** from the brand profile embedded naturally in the caption
- Tone matches the brand voice profile (formal, casual, warm — whatever the profile says)
- Output is **structured** (JSON with `caption`, `hashtags`, `seo_keyword_used` fields) — not just raw text

## 5. What Failure Looks Like

| Failure | What Happens | Agent Response |
|---|---|---|
| Brand profile JSON not found | `brands/client_x.json` doesn't exist | Halt. Return error: "No brand profile for client_x. Create one before running." |
| LLM returns English or MSA instead of Khaleeji | Model ignores dialect instruction | Retry once with stronger dialect prompt. If still wrong, flag for human review. |
| Caption exceeds 300 chars | LLM over-generates | Truncate at nearest sentence boundary. Log a warning. |
| LLM returns empty or garbage | API error or model failure | Return structured error with the raw response saved for debugging. |
| Missing required input | No topic or no platform provided | Halt immediately. Don't guess the topic. |

## 6. When to Ask a Human

- Brand profile is missing → **hard stop**, don't invent a brand voice
- Caption is about a sensitive topic (politics, religion, competitors) → **hold for review**
- LLM fails dialect check twice → **send draft to human for manual edit**
- Any content that could damage the client's brand reputation → **never auto-publish** (this agent doesn't publish anyway, but the rule carries forward)

## 7. What We're Using (for now)

- **LLM**: `gpt-4o-mini` via OpenRouter (free tier for development)
- **SDK**: OpenAI Agents SDK (`from agents import Agent, Runner, function_tool`)
- **Brand storage**: JSON files in `brands/` directory
- **Production upgrade path**: swap model to GPT-5 / Claude Opus, swap JSON to PostgreSQL

## 8. Out of Scope (for this agent)

- ❌ Posting to Meta (that's agent #2)
- ❌ Scheduling (that's the scheduler layer)
- ❌ WhatsApp follow-ups (that's agent #3)
- ❌ Ad targeting (future feature)
- ❌ Owner briefings via WhatsApp (system-level feature, not this agent's job)
