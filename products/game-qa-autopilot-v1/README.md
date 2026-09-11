# Game QA Autopilot v1.0

**Jake AI Autonomous Workflow Skill — Gaming**

Game QA Autopilot turns raw playtest notes, bug reports, logs, or QA observations into a structured game-testing workflow.

## What it does

1. Normalizes incoming QA evidence without inventing missing facts.
2. Classifies defects by subsystem: gameplay, UI/UX, graphics, audio, input, save/load, networking, performance, compatibility, accessibility, localization, or build/release.
3. Assigns severity and confidence separately.
4. Produces concise reproduction steps from supplied evidence and explicitly flags unknown steps.
5. Identifies likely duplicate reports using symptoms, environment, and reproduction path.
6. Builds a prioritized regression checklist after fixes.
7. Produces a release-oriented QA summary with blockers, high-risk areas, unresolved unknowns, and recommended retests.

## Inputs

Accept any combination of:
- playtest notes
- bug reports
- crash/log excerpts
- screenshots described by the operator
- platform/build/version
- expected vs. observed behavior
- existing issue lists
- recent fixes or patch notes

## Required output

For each issue return:
- Issue ID
- Short title
- Subsystem
- Build/platform/environment (if supplied)
- Expected behavior
- Observed behavior
- Reproduction steps
- Reproduction confidence: Confirmed / Probable / Insufficient evidence
- Severity: Blocker / Critical / Major / Minor / Cosmetic
- Priority recommendation
- Evidence supplied
- Missing evidence
- Regression tests

Then return:
- duplicate candidates
- release blockers
- top regression risks
- recommended next QA pass

## Guardrails

- Never claim a bug was reproduced unless evidence says it was reproduced.
- Never fabricate logs, hardware, build numbers, reproduction steps, root causes, or test results.
- Distinguish observed facts from hypotheses.
- Treat suspected security vulnerabilities as a separate escalation item rather than supplying exploit instructions.
- Do not mark a build release-ready solely because no issues were supplied.

## Operator prompt

Use this skill with an AI assistant or agent by supplying the QA material and instructing it:

> Run Game QA Autopilot v1.0 on the material below. Preserve facts exactly, identify unknowns, structure every defect, prioritize the QA queue, and generate the regression plan. Do not invent reproduction evidence or claim tests were executed unless the supplied evidence proves they were.

Paste the game QA material below that instruction.

## Example use

Input: "Windows build 0.8.4. Player reports that after loading a save made inside the mine, the inventory sometimes appears empty until opening and closing the map. Happened twice in three loads."

Expected workflow result: classify as save/load or UI/state synchronization; preserve the 2-of-3 observation; create evidence-based reproduction steps; avoid claiming a root cause; assign severity based on impact; recommend inventory persistence and save/load regression tests.

## License

Commercial use by the purchaser is permitted for internal game-development and QA workflows. Redistribution, resale, sublicensing, or publication of this skill package itself is not permitted without written permission from Jake AI.

## Version

v1.0 — 2026-09-10
