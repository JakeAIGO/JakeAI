# JKI Agent Runaway & Budget Guard v1.0 — Publication Candidate

**Status:** VALIDATED PROTOTYPE / PUBLICATION CANDIDATE  
**Publication mode:** Human approval required  
**Checkout:** Disabled until fulfillment is securely configured and verified  
**Product class:** Autonomous Workflow Skill / Agent Runtime Safety Utility

## Problem
Autonomous agents can enter repetitive tool-call loops, continue after repeated failures, exceed intended token/runtime budgets, or silently consume API spend. Developers need hard execution limits that do not depend on the model deciding to stop itself.

## Target buyer
- Individual agent developers
- Small AI product teams
- MCP/tool-using agent builders
- Teams testing autonomous workflows before production deployment

## Evidence
The opportunity was identified through enterprise-agent research plus bottom-up developer evidence. A May 2026 Haystack feature request explicitly asked for cost, token, time, tool-call and loop guardrails for agents. Enterprise AI research also indicates poor real-time visibility and control over agent/AI operating costs remains common.

## Proposed product
**JKI Agent Runaway & Budget Guard v1.0**

Outcome: put deterministic limits around an AI-agent run so a runaway loop cannot silently consume unlimited tokens, API calls, wall-clock time, retries or estimated spend.

### v1 controls
- Maximum estimated dollar cost
- Maximum token consumption
- Maximum wall-clock runtime
- Maximum tool calls
- Maximum consecutive failures
- Repeated identical tool-call detection
- Observe-only mode
- Explicit stop reason
- Compact usage report

## Implementation status
A working Python package has been built and locally validated.

Validation performed:
- 6 automated unit tests: PASS
- Deliberately looping demo agent: PASS
- Demo stops on repeated identical tool call and emits an explicit exit reason and run report
- No third-party runtime dependency required for the core package

## Secure package identity
The paid delivery package is intentionally **not committed to this public repository**.

- Package filename: `JKI_Agent_Runaway_Budget_Guard_v1.0.zip`
- Size: 14,903 bytes
- SHA-256: `78831e2fad97e9a4ada8db82dfdc8625105486dbb8bbb39b5954c382583eae29`

Any fulfillment copy must match this checksum unless a new version is deliberately built and reviewed.

## Safety principle
**Capability != Authority.**

The guard configuration must be owned by trusted operator policy, not by model-generated text. The agent must not be able to raise or disable its own execution limits.

## Known limitations
- v1 detects exact repeated tool calls, not semantic-equivalent loops.
- Estimated cost is supplied by the integration; v1 does not maintain a universal provider pricing table.
- v1 is not an identity provider, enterprise compliance suite, or complete agent-security platform.
- v1 does not automatically roll back external actions.
- v1 limits specified execution dimensions; it does not guarantee globally safe agent behavior.

## Pricing experiment
Recommended launch experiment: **$9-$19 one-time developer purchase**. Initial objective is paid-market validation, not maximum revenue.

## Proposed listing language
**Don't let a broken AI agent run away with your API budget.**

JKI Agent Runaway & Budget Guard adds deterministic limits for cost, tokens, runtime, tool calls, retries and repeated identical tool calls. It includes observe-only mode, explicit stop reasons, a usage report, tests and a deliberately broken demo so buyers can verify the guard before integrating it.

## Publication gates
Before publication/checkout, verify all of the following:
1. Secure entitlement-controlled delivery location exists for the exact reviewed ZIP.
2. Delivery URL is not exposed in public source or unauthenticated frontend code.
3. Checkout delivers only after successful payment/entitlement verification.
4. Product page clearly states limitations and does not claim guaranteed savings or complete security.
5. Test the live purchase -> entitlement -> download flow end to end.
6. Confirm rollback path for disabling the listing or checkout.
7. Human explicitly authorizes publication and price.

## Recommended next action
Feed this candidate through the existing PR guardrails and product publication pipeline. Keep checkout and public fulfillment disabled until the secure delivery path is verified.
