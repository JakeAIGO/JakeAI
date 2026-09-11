# JakeAI Truth & Claims Audit

Status: remediation-branch audit only. This document does not authorize production deployment, publication, spending, checkout activation, or product activation.

## Purpose
JakeAI exposes machine-readable claims through README.md, runtime `/llms.txt`, runtime `/.well-known/agent.json`, repository compatibility files, catalog metadata, and deployment configuration. Those claims should describe only behavior that is actually implemented, tested, runtime-verified where applicable, and explicitly authorized.

## Current findings and dispositions

### 1. Audit-product pricing is locked pending explicit commercial approval
The runtime catalog currently declares:
- `prod_multi_model_audit_08`: $2.00
- `prod_audit_pack_10`: $18.00

Repository tests lock those values against silent change. The static repository `llms.txt` no longer publishes stale commercial pricing and is explicitly non-authoritative.

Disposition: BLOCK any public price change until intended commercial pricing is explicitly approved. Do not infer commercial approval from implemented catalog values.

### 2. External-model implementation exists; successful live runtime participation remains unverified
Inspection of `main.py` confirms direct provider implementations for:
- Anthropic Messages API at `https://api.anthropic.com/v1/messages`, model `claude-3-5-sonnet-20241022`, configured by `ANTHROPIC_API_KEY`.
- Perplexity Chat Completions API at `https://api.perplexity.ai/chat/completions`, model `sonar-pro`, configured by `PERPLEXITY_API_KEY`.

Caller-supplied Anthropic/Perplexity secret-header overrides have been removed. Provider credentials are server-side configuration only.

If either key is absent, that provider returns `simulation_mode` / `NOT_RUN`; consensus does not falsely report a successful dual-model GO.

Disposition: Provider wiring is VERIFIED IN CODE and fail-closed behavior is VERIFIED IN TESTS. Successful live runtime participation is still UNVERIFIED until deployment evidence confirms both providers are configured and returning successful responses.

### 3. Production-enforcement claims remain constrained
`jakeai_audit.py` may be capable of returning a non-zero result on a NO-GO, but the Master Baseline must not claim that every production deployment is protected by that mechanism unless repository/deployment rules actually require it.

Disposition: Treat the audit as a capability, not an enforced production control, until required checks/rules are explicitly configured and verified.

### 4. Public API path convention is now explicit
Canonical website-facing convention: `/api/v1/...`.
Direct Railway/backend convention: `/v1/...`.

Netlify proxy rules translate website `/api/...` requests to backend routes. Documentation must distinguish public proxy paths from direct backend paths.

Disposition: VERIFIED IN REPOSITORY CONFIGURATION. Do not present deployment-context paths as interchangeable without explanation.

### 5. Dynamic machine-readable discovery is the intended authority
`main.py` dynamically serves `/llms.txt` and `/.well-known/agent.json` from the runtime catalog. Netlify routing force-proxies these public paths to the backend.

Static repository `llms.txt` and `agent_card.json` are now non-authoritative compatibility/pointer artifacts and are guarded by claim-consistency tests so they cannot silently assert live commercial state.

Disposition: Dynamic runtime discovery is the intended source of public capability truth. Repository copies must remain non-authoritative.

### 6. Broad no-human-intervention claims are not allowed
Current product-validation and Master Baseline governance preserve human approval for consequential commercial, publication, spending, and release actions.

Disposition: Describe autonomy only for scoped execution. Do not claim unrestricted commercial operation without human intervention.

### 7. Commercial/economic claims still require explicit approval
The repository and website have historically referenced protocol fees, creator economics, prices, checkout availability, and agent-to-agent settlement language.

The Master Baseline manifest now sets `production_authorized`, `publication_authorized`, and default commercial approval to false. Individual products also remain `commercial_approved: false`.

Disposition: Commercial claims are not authorized merely because code or copy exists. Protocol fee, creator split, settlement language, and individual price decisions require explicit approval before being promoted as active commercial truth.

### 8. Safety and regulated-domain claims are constrained
- PJM/tariff outputs are demonstration/static data, not live grid pricing.
- Robotics grasp outputs are classified `UNVALIDATED_PHYSICAL_CONTROL_MODEL` and advisory only.
- Tax/financial outputs remain informational/advisory and require independent validation before production reliance.
- External network-fetch tools fail closed by default pending hardened egress validation.

Disposition: Keep these constraints in catalog, machine discovery, docs, and tests. Do not strengthen claims without independent validation and applicable legal/safety review.

## Required truth gates before autonomous publication
A coding or product agent must not publish or strengthen a claim unless all applicable checks pass:

1. Implementation exists in the repository or approved external dependency.
2. Deployment/runtime behavior has been verified for claims that depend on live runtime state.
3. Pricing and commercial terms match the approved source of truth.
4. Required metering, entitlement, fulfillment, and checkout controls are operational.
5. Named third-party models/services are configured and successfully invoked before being described as live.
6. Data labeled live or real-time is genuinely live; otherwise label it demonstration, simulated, cached, or historical.
7. Safety-critical or regulated products complete applicable technical, security, legal/liability, and human-approval gates.
8. Public machine-readable surfaces agree on canonical endpoint paths and capability status.
9. The exact candidate SHA passes the full Master Baseline gate.
10. Council review and required human approvals are recorded before promotion.

## Remaining blockers before production/commercial promotion

- Verify live provider configuration/results if external-model execution is to be marketed as live.
- Confirm intended commercial pricing, creator economics, protocol fee, and settlement language.
- Verify metering/entitlement for API-credit products.
- Verify paid checkout and private fulfillment in an explicitly authorized test environment before production activation.
- Complete applicable legal/liability review for tax/financial, robotics, settlement, refunds, and privacy claims.
- Decide whether the temporary write-capable remediation workflow is removed/disabled before final baseline freeze.
- Freeze and fingerprint the exact Council-approved candidate.

## Safety note
This audit intentionally does not auto-correct commercial prices, activate checkout, enable autonomous publication, spend money, or deploy to production. Ambiguities remain fail-closed until explicitly resolved.
