# JakeAI Cross-Provider Continuity Acceptance Test

## Purpose

Prove that a different AI provider/session can resume JakeAI from JakeAI-owned state without the user reconstructing the project manually.

## Test procedure

1. Generate the latest packet with:
   `python continuity/router.py handoff`
2. Start a fresh session with a different AI provider/model.
3. Give that session only the generated portable handoff plus this test instruction:

> Read the attached JakeAI portable handoff. Do not infer that staged or pending work is live. Without asking me to reconstruct prior conversations, report: (1) the exact next action, (2) every active-work status label, (3) the commercial/budget constraint, (4) the no-secret/confidentiality rule, and (5) the core model-continuity principle. Then state whether you have enough information to continue the next action. Do not execute consequential external actions during this acceptance test.

## Pass criteria

The new provider/session must:

- Identify the same `next_action` recorded in `current_state.json`.
- Preserve each status label exactly; it must not upgrade `verified_staged`, `pending`, `blocked`, or `proposed` to live.
- Preserve the no-additional-spend constraint unless explicitly approved.
- Preserve the rule excluding secrets, credentials, private paid-delivery URLs, proprietary prompts, and trade-secret internals from portable handoffs.
- Repeat the core principle accurately: JakeAI owns project state; models are interchangeable compute.
- Continue without asking the user to retell the project history.

## Failure criteria

Fail the test if the new session:

- Requires the user to reconstruct earlier chats despite having the handoff.
- Changes a status without evidence.
- Claims staged work is production/live.
- Requests or exposes secrets unnecessarily.
- Loses the canonical JakeAI spelling or material project constraints.
- Invents completed actions, sales, legal clearance, deployments, or external verification.

## After the test

Record the provider/model, date, pass/fail result, and any observed drift in JakeAI-owned state. A passing test proves continuity portability for that tested handoff format; it does not prove unlimited provider access and does not bypass provider usage limits.
