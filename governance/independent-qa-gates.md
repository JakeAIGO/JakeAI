# JakeAI Independent QA Gates

Status: CANONICAL GOVERNANCE RULE
Date: 2026-09-10

## Core rule

JakeAI must not be the sole grader of JakeAI.

The agent or workflow that creates an output may not independently certify that same output for publication, sale, deployment, or promotion. Creation and approval are separate duties.

## Required separation of duties

1. **Producer** — creates the candidate output from approved inputs and canonical references.
2. **Independent evaluator** — evaluates the candidate against locked requirements, source evidence, and canonical assets. Prefer a different model/process from the producer where practical and deterministic checks wherever possible.
3. **QA gate** — checks technical correctness, continuity, factual claims, legal/platform constraints, packaging, and release requirements appropriate to the artifact.
4. **Release authority** — only an output that passes required gates may advance. High-impact or new canonical assets retain human approval where required.

The producer cannot override a failed independent gate.

## Brand Asset Continuity rule

No visual containing the JakeAI character may be promoted as canonical, published, or used to generate downstream media unless the locked canonical JakeAI master asset was actually available to the generation/evaluation workflow.

A textual description, memory of the avatar, or an unapproved derivative is not a substitute for the canonical master.

If the canonical master is unavailable, the workflow must STOP rather than invent or approximate JakeAI.

## Regression Test: UNKNOWN GUY TEST

Purpose: detect character-identity drift.

Test:
- Supply the locked JakeAI canonical master asset.
- Request JakeAI in a materially new scene, pose, or environment.
- Independently compare the candidate with the master and continuity manifest.

Automatic FAIL conditions include:
- recognizable identity drift;
- replacement by a generic or newly invented person;
- unapproved changes to defining canonical features;
- evaluator lacks access to the canonical master;
- producer attempts to self-certify identity without independent evaluation.

On FAIL:
- do not publish;
- do not add to the canonical asset library;
- do not use as a reference for later images, GIFs, video, thumbnails, or social assets;
- record the failure and corrective action for regression testing.

## Factory-wide application

This separation applies beyond graphics:
- Discovery does not solely validate its own product idea.
- Builders do not solely certify their own code.
- Marketing does not solely substantiate its own claims.
- Media generation does not solely fact-check its own documentary history.
- Commerce readiness is not declared by the component implementing checkout.

## QA Report #001 — historical regression fixture

Subject: JakeAI visual identity

Result: **NOT JAKEAI — FAIL**

Observed failure: A newly generated JakeAI Universe concept visual contained an invented person instead of the locked canonical JakeAI avatar.

Root cause: The generation step proceeded without the canonical master asset actually attached as its identity reference, then relied on the same workflow's interpretation of JakeAI continuity.

Corrective action: enforce canonical-master availability plus independent evaluation before publication or downstream reuse.

Internal shorthand: **"JakeAI asked JakeAI whether JakeAI looked like JakeAI."**

This incident is retained as a permanent regression fixture and may be used as truthful behind-the-scenes material for the JakeAI Universe series.
