# JakeAI Zero-Cost Dependency Gate

Applies to JakeAI: The Factory and is designed for reuse by the broader JakeAI Autonomous Product Factory.

## Hard rule
No third-party component enters the production dependency graph until it passes every required gate below.

## Required gates
1. Acquisition cost: $0 required.
2. Commercial use: explicitly permitted.
3. License: identified and reviewed before integration.
4. Attribution: copyright/license/notice obligations captured in the dependency manifest.
5. Runtime cost: no mandatory paid API, cloud service, seat, subscription, royalty, per-render, per-request, per-user or usage fee.
6. Trial trap: a time-limited free trial does NOT qualify as zero-cost infrastructure.
7. Compatibility: pinned version must work with the project's actual engine/runtime version.
8. Web/mobile: browser and mobile behavior must be tested when those are target platforms.
9. Replaceability: dependency should be replaceable without surrendering JakeAI-owned game/product logic.
10. Security/maintenance: source and maintenance status reviewed before adoption.
11. Build verification: deterministic test proves the dependency works in our actual build/export pipeline.
12. Cost regression: future upgrades must re-pass the gate; a formerly free dependency cannot silently become paid infrastructure.

## Decision states
- CANDIDATE: discovered but not trusted.
- REVIEWING: cost/license/compatibility investigation underway.
- APPROVED-PINNED: exact version passed all gates.
- REJECTED: failed one or more hard gates.
- QUARANTINED: previously approved dependency changed terms, ownership, behavior or cost and must be re-reviewed.

## Current policy
Prefer permissive open-source dependencies, especially MIT/Apache-2.0/BSD/CC0 where appropriate, but never infer commercial rights from the word "free." Each component's actual license controls.

Godot Engine is acceptable in principle under its MIT license, subject to required license/third-party notices in distribution. Individual addons/assets must be evaluated independently; inclusion in an asset marketplace/library does not replace our review.

## Dependency manifest fields
Every approved dependency must record:
- name
- purpose
- source repository/site
- exact version or commit
- acquisition_cost
- mandatory_runtime_cost
- license SPDX/name
- commercial_use_allowed
- attribution_required
- attribution_text/location
- engine compatibility
- web compatibility
- mobile compatibility
- source available
- maintenance status
- approval date
- evidence links
- replacement strategy
- approval state

## Automated release gate
A production build fails if:
- an imported dependency is absent from the manifest;
- acquisition_cost is not $0;
- mandatory_runtime_cost is not $0;
- license/commercial-use status is unknown;
- required attribution is missing;
- the dependency version differs from the approved pin;
- compatibility tests fail.

## Cost-control principle
Free means sustainably zero mandatory cost for the way JakeAI actually uses the component. Optional donations/support tiers do not disqualify a component. Required payment now or later does.

## Productization candidate
**JakeAI Autonomous Open-Source Dependency Scout**

Discover needed capabilities -> find candidate components -> verify current cost -> inspect license -> evaluate commercial-use obligations -> check compatibility/security/maintenance -> test in target runtime -> generate attribution manifest -> approve/reject/quarantine -> monitor approved dependencies for material changes.

This workflow is intentionally generic enough to become a JakeAI marketplace product after internal validation.