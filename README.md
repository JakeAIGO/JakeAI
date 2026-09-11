# Jake AI — Autonomous Workflow Marketplace and Product Factory

Status: active development. This repository contains the Jake AI backend, public marketplace surfaces, machine-readable discovery interfaces, product-factory components, and supporting governance/validation assets.

This README describes repository behavior conservatively. A feature is not described as live, production-enforced, or autonomous unless that behavior is implemented and verified.

## Core application
- `main.py` — FastAPI backend, product catalog, product search, selected utility/robotics endpoints, machine-readable discovery routes, health routes, and checkout/delivery logic.
- `index.html` — public marketplace surface.
- `admin.html` — admin-facing static surface; presence of this file does not by itself imply authenticated/private admin functionality.
- `netlify.toml` / `_redirects` — website-to-backend proxy/routing configuration.
- `llms.txt` / `agent_card.json` — static compatibility surfaces; the intended authoritative machine-readable public surfaces are the backend-generated `/llms.txt` and `/.well-known/agent.json` after routing is verified.
- `governance/MASTER_BASELINE_ENGINE.md` — candidate specification for the canonical Jake AI Master Baseline Engine.
- `tests/test_master_baseline_invariants.py` — non-network regression checks for baseline invariants.

## Canonical public API convention
The intended website-facing API convention is:

`https://www.jakeaiofficial.com/api/v1/...`

The Railway backend serves direct `/v1/...` routes. Netlify proxies public website requests to those backend routes. Documentation and generated machine-readable surfaces should distinguish these contexts rather than presenting them as interchangeable.

## Commercial-state rules
Jake AI uses fail-closed commercial behavior:
- products requiring metering/entitlement are not chargeable until those controls exist;
- products without verified fulfillment/delivery are not chargeable;
- private delivery URLs must not appear in public catalog output;
- paid digital delivery must follow verified payment;
- free products must not require payment-processor credentials;
- demonstration/static data must not be represented as live data.

Product price, availability, fulfillment readiness, and checkout readiness are separate states. A listed product is not automatically purchasable.

## Autonomy and approval boundaries
Jake AI may automate discovery, analysis, generation, testing, and other workflow stages, but consequential actions retain explicit gates where required. Passing an earlier autonomous stage does not authorize publication, spending, checkout activation, legal/safety approval, or production deployment.

## Master Baseline promotion path
Candidate changes follow this sequence:

`MASTER BASELINE -> WORKING BRANCH -> AUTOMATED TESTS -> TRUTH/CLAIMS AUDIT -> SECURITY/LIABILITY AUDIT -> COUNCIL REVIEW -> HUMAN APPROVAL WHERE REQUIRED -> PRODUCTION`

A failed or unknown gate is a blocker, not a condition to bypass.

## Current remediation branch
`fix/website-truthfulness-audit-2026-09-11` is a non-production candidate branch used to reconcile website behavior, commerce logic, claims, routing, discovery surfaces, tests, and the first formal Master Baseline. Work on this branch does not authorize deployment or production modification.

## Current known verification requirements
Before this candidate can be considered a baseline, at minimum:
- free checkout must bypass Stripe before any Stripe-secret requirement;
- paid checkout/delivery must remain payment-verified and fail closed;
- homepage availability language must match per-product state;
- stale or unsupported live/authority/autonomy claims must be removed or proven;
- prices and commercial states must agree across the canonical registry and machine-readable/public surfaces;
- website links and API routes must be exercised and checked for expected status/behavior;
- static and dynamic machine-readable discovery surfaces must not drift;
- application import/startup, syntax, dependency, security, and regression checks must pass;
- unresolved legal/liability blockers must be surfaced to Council review before promotion.

## Production safety
Do not treat documentation, a passing unit test, or a branch commit as proof of production behavior. Production claims require runtime evidence. No file in this repository independently authorizes deployment, public posting, spending, checkout activation, or irreversible external action.