# Model Options

This file is a practical model note for Jarvis, not a generic model dump.

## Current Recommendation

### Main orchestrator
- target: `GPT-5.1` or `GPT-4o`
- role: Jarvis chat, tool routing, approval/schedule decisions

### Client synthesizer
- target: small fast instruction-following model
- role: intake -> profile structure

### Caption agent
- target: cheaper generation model with strong multilingual output
- role: caption drafting

### Classifiers / triage
- target: smallest cheap model possible
- role: routing, safety, classification

## Product Rule

Do not burn premium model cost on every low-value step.

The product should use:
- strong model for orchestration
- cheaper model for repetitive generation
- smallest model for classification

## Current Engineering Reality

The repo has been built to stay model-flexible.

That means:
- current development models may change
- prompt/control quality matters as much as model choice
- media and workflow reliability are currently more important than squeezing the absolute smartest model into every step

## Immediate Model Priority

The next product priority is not a model swap.

The next product priority is:
- bilingual English/Arabic support
- stable demo flow
- stable media delivery

Only after those are stable should model optimization become a major focus.
