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

### 2. External-model implementation exists; runtime configuration remains unverified
Inspection of `main.py` confirms that the audit endpoint has direct provider implementations for:
- Anthropic Messages API at `https://api.anthropic.com/v1/messages`, using model `claude-3-5-sonnet-20241022`.
- Perplexity Chat Completions API at `https://api.perplexity.ai/chat/completions`, using model `sonar-pro`.

The endpoint reads `ANTHROPIC_API_KEY` and `PERPLEXITY_API_KEY` from the environment, with optional request-header overrides. If either key is missing, that provider returns `simulation_mode` / `NOT_RUN`; consensus then returns `REVIEW REQUIRED — one or more models not configured` rather than falsely reporting a successful dual-model audit.

Disposition: Provider wiring is VERIFIED IN CODE. Successful live runtime participation is still UNVERIFIED until deployment configuration/runtime evidence confirms both providers are configured and returning successful responses. Marketing should distinguish implemented integration from verified live execution.

Security note: request-header API-key overrides (`X-Anthropic-Key`, `X-Perplexity-Key`) should be reviewed before broad public use. They may be intentional for bring-your-own-key clients, but their authorization, logging, retention, abuse, and disclosure model should be explicit.

### 3. "Protects production deployments" is not yet enforced by repository CI
`jakeai_audit.py` describes itself as a CI/CD runner that exits non-zero on NO-GO to protect production deployments.

At the time of this audit, the existing repository workflows are opportunity-radar, product-discovery, product-validation, and a disabled Drive sync. None of those workflows invokes `jakeai_audit.py` as a required production gate.

Disposition: Rephrase documentation as a capability unless/until the audit becomes a required branch/deployment check. Do not claim enforcement that is not configured.

### 4. Public API path conventions are inconsistent but the proxy behavior is now understood
`README.md` documents backend paths such as `/v1/products/search` and `/v1/transactions/settle`.

`llms.txt` documents public proxied paths such as `/api/v1/products/search` and `/api/v1/transactions/settle`.

Netlify `_redirects` proxies `/api/*` to the Railway backend with the `/api/` prefix removed. `main.py` also explicitly registers both `/v1/products/search` and `/api/v1/products/search` for product search.

Disposition: Define `/api/v1/...` as the canonical website-facing API path and document `/v1/...` as the direct Railway/backend path where applicable. Do not present deployment-context paths as interchangeable without explanation.

### 5. Machine-readable discovery surfaces were split between static Netlify files and dynamic Railway routes
`main.py` dynamically serves `/llms.txt` and `/.well-known/agent.json` from the live catalog, including current product price and checkout status. The repository also contains a static root `llms.txt`, while the static `agent_card.json` is not located at the standard `/.well-known/agent.json` path.

This creates drift risk: the website could serve stale static claims while the backend generates newer truth from `GENESIS_CATALOG`.

Remediation staged on `codex-setup`: Netlify `_redirects` now force-proxies `/llms.txt` and `/.well-known/agent.json` to the Railway backend so the public machine-readable surfaces use the backend-generated source of truth. This is branch-preview only until the PR is approved and merged.

### 6. agent_card.json is materially narrower than the backend-generated agent surface
The static `agent_card.json` advertises only product search and the robotics grasp solver. The dynamic `/.well-known/agent.json` in `main.py` publishes the active catalog from `GENESIS_CATALOG`.

Disposition: Treat the dynamic well-known endpoint as the intended authoritative discovery surface after proxy verification. Keep or deprecate the static `agent_card.json` only after compatibility needs are understood.

### 7. "Without human intervention" conflicts with current Product Factory approval gates
`README.md` describes commercial publishing, discovery, and settlement as operating "without human intervention."

Current validation logic explicitly sets publication, spending, and build authorization to false and requires human approval. The new Codex operating instructions also preserve those fail-closed gates.

Disposition: Replace broad autonomy language with scoped language that distinguishes autonomous execution from human authorization for consequential or commercial actions.

### 8. Machine-readable commercial claims need one source of truth
Prices, product availability, endpoint descriptions, creator economics, protocol fees, checkout state, and named external dependencies are currently represented across multiple files.

Disposition: Long-term target should be a generated machine-readable manifest sourced from one canonical product registry, with README/llms.txt/agent-card content derived from verified registry fields rather than maintained independently.

## Required truth gates before autonomous publication
A coding or product agent must not publish or strengthen a claim unless all applicable checks pass:

1. Implementation exists in the repository or approved external dependency.
2. Deployment/runtime behavior has been verified.
3. Pricing and commercial terms match the approved source of truth.
4. Required metering, entitlement, fulfillment, and checkout controls are operational.
5. Named third-party models/services are actually configured and successfully invoked before being described as live.
6. Data labeled live or real-time is genuinely live; otherwise it must be labeled demonstration, simulated, cached, or historical as appropriate.
7. Safety-critical or regulated products have completed the applicable technical, security, legal/liability, and human-approval gates.
8. Public machine-readable files agree on canonical endpoint paths and capability status.

## Recommended remediation order
1. Verify live runtime configuration/results for both audit providers.
2. Confirm intended audit-product prices before changing any public prices.
3. Verify the new Netlify proxy behavior in the deploy preview.
4. Define canonical public API paths in documentation.
5. Reconcile README.md autonomy wording with current human-approval policy.
6. Decide whether static `agent_card.json` remains for compatibility or is deprecated.
7. Add automated claim-consistency tests for price, endpoint, and capability metadata.
8. Only after verification, update public claims in a separate reviewable commit.

## Safety note
This audit intentionally does not auto-correct prices, activate checkout, change settlement logic, enable autonomous publication, or alter production deployment behavior. Ambiguities remain fail-closed until explicitly resolved.
