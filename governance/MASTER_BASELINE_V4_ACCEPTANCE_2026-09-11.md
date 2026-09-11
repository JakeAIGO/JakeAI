# JakeAI Master Baseline v4 — Commercial Rules Registry Acceptance

Date: 2026-09-11

Candidate branch: `feature/commercial-rules-registry-2026-09-11`

Purpose: add the JakeAI Commercial Rules Registry to the protected baseline so commercial configuration has one canonical, fail-closed source of truth.

## Accepted baseline capability

The candidate adds `governance/commercial_rules_registry.json`, deterministic validation in `tools/commercial_rules.py`, regression tests, change-control classification for commercial/legal surfaces, and CI enforcement alongside Change Control and Module Sandbox gates.

The registry records current product prices while keeping all product commercial and checkout authorization false. The 50/50 creator split and 1% protocol fee are stored only as proposed, unapproved terms with public claims unauthorized. Refunds remain pending product-specific policy and legal review.

## Governance disposition

Internal Council result: GO for canonical baseline inclusion; NO-GO for commercial activation. This acceptance does not authorize a merge to `main`, production deployment, publication, checkout activation, spending, or commercial release.

The earlier baseline anchors remain recovery points and are not to be overwritten.

## Promotion condition

This record becomes the v4 anchor only after the exact commit containing this acceptance record passes the combined Change Control, Module Sandbox, Commercial Rules Registry, compile, Master Baseline repository audit, and full regression suite. The resulting exact SHA is the only SHA eligible to be named `baseline/master-v4-2026-09-11`.
