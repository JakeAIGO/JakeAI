# JakeAI Truth & Claims Audit

Status: draft audit for Codex setup branch only. This document does not authorize production deployment, publication, spending, checkout, or product activation.

## Purpose
JakeAI exposes machine-readable claims through README.md, llms.txt, agent_card.json, MCP tooling, public catalog metadata, and deployment configuration. Those claims should describe only behavior that is actually implemented, deployed, tested, and authorized.

## Findings

### 1. Pricing mismatch in llms.txt
`llms.txt` describes the Multi-Model Pre-Deployment Audit as `Price: .00 USD (Single) / 8.00 USD (10-Audit Developer Pack)`.

The product catalog in `main.py` currently declares:
- `prod_multi_model_audit_08`: $2.00
- `prod_audit_pack_10`: $18.00

Disposition: BLOCK public-price synchronization until the intended commercial pricing is explicitly confirmed. No automatic price change should be made from either source.

### 2. External-model participation claims require runtime verification
`llms.txt`, `jakeai_mcp_server.py`, and `jakeai_audit.py` state that the audit service uses Claude 3.5 Sonnet and Perplexity Sonar-Pro and returns a combined Go/No-Go result.

The repository surfaces inspected during this audit show clients that call the live audit endpoint, but they do not by themselves prove which upstream models are actually invoked at runtime.

Disposition: Treat named-model participation as UNVERIFIED until the live endpoint implementation/configuration and successful runtime evidence are inspected. Do not strengthen marketing claims until verified.

### 3. "Protects production deployments" is not yet enforced by repository CI
`jakeai_audit.py` describes itself as a CI/CD runner that exits non-zero on NO-GO to protect production deployments.

At the time of this audit, the existing repository workflows are opportunity-radar, product-discovery, product-validation, and a disabled Drive sync. None of those workflows invokes `jakeai_audit.py` as a required production gate.

Disposition: Rephrase documentation as a capability unless/until the audit becomes a required branch/deployment check. Do not claim enforcement that is not configured.

### 4. Public API path conventions are inconsistent
`README.md` documents backend paths such as `/v1/products/search` and `/v1/transactions/settle`.

`llms.txt` documents public proxied paths such as `/api/v1/products/search` and `/api/v1/transactions/settle`.

Netlify `_redirects` proxies `/api/*` to the Railway backend with the `/api/` prefix removed, so both forms may be meaningful in different deployment contexts, but the public contract is not clearly explained.

Disposition: Define one canonical public API surface and separately document direct-backend/internal paths. Avoid presenting both as interchangeable without explanation.

### 5. agent_card.json is materially narrower than llms.txt and README.md
`agent_card.json` currently advertises only product search and the robotics grasp solver, while `llms.txt` and README.md describe registration, settlement, audits, checkout-related behavior, and additional capabilities.

Disposition: Decide whether the agent card is intentionally minimal. If it is intended as the authoritative machine-discovery surface, synchronize it only with verified, production-authorized capabilities.

### 6. "Without human intervention" conflicts with current Product Factory approval gates
`README.md` describes commercial publishing, discovery, and settlement as operating "without human intervention."

Current validation logic explicitly sets publication, spending, and build authorization to false and requires human approval. The new Codex operating instructions also preserve those fail-closed gates.

Disposition: Replace broad autonomy language with scoped language that distinguishes autonomous execution from human authorization for consequential or commercial actions.

### 7. Machine-readable commercial claims need one source of truth
Prices, product availability, endpoint descriptions, creator economics, protocol fees, checkout state, and named external dependencies are currently represented across multiple files.

Disposition: Long-term target should be a generated machine-readable manifest sourced from one canonical product registry, with README/llms.txt/agent-card content derived from verified registry fields rather than maintained independently.

## Required truth gates before autonomous publication
A coding or product agent must not publish or strengthen a claim unless all applicable checks pass:

1. Implementation exists in the repository or approved external dependency.
2. Deployment/runtime behavior has been verified.
3. Pricing and commercial terms match the approved source of truth.
4. Required metering, entitlement, fulfillment, and checkout controls are operational.
5. Named third-party models/services are actually configured and successfully invoked.
6. Data labeled live or real-time is genuinely live; otherwise it must be labeled demonstration, simulated, cached, or historical as appropriate.
7. Safety-critical or regulated products have completed the applicable technical, security, legal/liability, and human-approval gates.
8. Public machine-readable files agree on canonical endpoint paths and capability status.

## Recommended remediation order
1. Verify the live audit endpoint implementation and its upstream providers.
2. Confirm intended audit-product prices before changing any public prices.
3. Define canonical public API paths.
4. Reconcile README.md autonomy wording with current human-approval policy.
5. Decide whether agent_card.json is minimal by design or should become authoritative.
6. Add automated claim-consistency tests for price, endpoint, and capability metadata.
7. Only after verification, update public claims in a separate reviewable commit.

## Safety note
This audit intentionally does not auto-correct prices, activate checkout, change settlement logic, enable autonomous publication, or alter production deployment behavior. Ambiguities remain fail-closed until explicitly resolved.
