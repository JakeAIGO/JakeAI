# JakeAI Model Continuity Router

## Principle

**The model is not the memory. The model is not the project. JakeAI owns the project state; models are interchangeable compute.**

This package is the first implementation skeleton for surviving model/session limits without reconstructing JakeAI from scratch.

## Goals

- Preserve project state outside any individual AI chat.
- Produce a compact, model-agnostic handoff package.
- Track what is verified, staged, pending, blocked, or merely proposed.
- Prevent a new model from turning a concept or partial test into a claim that something is live.
- Keep proprietary implementation details and secrets out of portable handoffs unless explicitly approved.
- Allow ChatGPT, Gemini, Grok, Claude, Perplexity, Codex, or a human collaborator to resume from the same checkpoint.
- Use no paid dependency and no provider-specific SDK.

## Files

- `state.schema.json` — portable state contract.
- `current_state.json` — current sanitized JakeAI checkpoint.
- `handoff_template.md` — deterministic prompt/template for the next worker.
- `router.py` — standard-library CLI that validates state and emits a portable handoff bundle.

## Operating flow

1. Work occurs in any model/tool.
2. Meaningful progress updates `current_state.json`.
3. Before a session/model limit, run `python continuity/router.py handoff`.
4. The command writes a timestamped Markdown handoff to `continuity/out/`.
5. Give that handoff plus relevant files/links to the next model.
6. The next model resumes from `next_action`, verifies external state before consequential writes, and updates the state again.

## Non-negotiable status meanings

- `verified_live`: independently confirmed in the real destination.
- `verified_staged`: built/tested but not confirmed live.
- `pending`: action initiated but final outcome not verified.
- `blocked`: cannot proceed without a dependency, permission, or user/security step.
- `proposed`: idea only; not built or verified.

## Security / confidentiality

Portable handoffs must not contain passwords, API keys, tokens, private delivery URLs, payment credentials, proprietary prompts, internal orchestration logic, or trade-secret implementation details. The handoff may describe outcomes, interfaces, dependencies, status, and next actions.

## What this does not do

This does not bypass or defeat any provider's usage limits. It removes JakeAI's dependence on a single provider/session by making project state portable and resumable.
