# JakeAI Codex Operating Instructions

## Mission
JakeAI is an autonomous AI-product marketplace and product-factory platform. Coding agents should improve reliability, safety, product discovery, validation, packaging, publishing, and machine-to-machine commerce while preserving human control over consequential actions.

## Repository orientation
- `main.py` is the primary FastAPI backend and product catalog/API surface.
- `index.html` and related HTML files are the public/admin web surfaces.
- `jakeai_mcp_server.py` exposes JakeAI capabilities to MCP-compatible agents.
- `jakeai_audit.py` provides audit functionality.
- `.github/workflows/` contains the autonomous discovery/validation pipeline.
- `product-discovery/` contains opportunity-radar, enrichment, clustering, discovery, and validation logic.
- `agent_card.json` and `llms.txt` are machine-readable agent-discovery surfaces.

## Non-negotiable safety rules
1. Never modify `main` directly for substantive changes. Work on a feature branch and use a pull request.
2. Never enable autonomous spending, publication, checkout, production deployment, or irreversible external actions unless the repository's explicit approval gates authorize them.
3. Preserve fail-closed behavior for products that require metering, entitlement, delivery URLs, or legal/safety review.
4. Safety-critical, regulated, or consequential products (including aviation, transportation, medical, financial, legal, industrial safety, robotics, infrastructure, and similar domains) require a documented review gate before publication or activation.
5. Never expose secrets, API keys, private delivery URLs, tokens, credentials, or hidden configuration in source, logs, artifacts, public APIs, or front-end code.
6. Do not weaken SSRF, CORS, authentication, payment, entitlement, validation, or audit controls without a clearly documented reason and replacement control.
7. Do not make claims of market validation, legal compliance, safety, live-data status, or external-model participation unless the underlying evidence and implementation support the claim.
8. Preserve human approval where existing workflows mark `human_approval_required: true` or equivalent.

## Change protocol
Before editing:
- Inspect the affected files and nearby tests/workflows.
- Identify deployment, payment, data, security, and compliance implications.
- Prefer the smallest coherent change.

While editing:
- Keep public APIs backward-compatible unless the task explicitly requires a versioned breaking change.
- Keep checkout/delivery logic fail-closed.
- Use environment variables for secrets and deploy-specific configuration.
- Add or update tests/validation for behavior changes.

Before proposing merge:
- Run relevant Python tests and validation scripts.
- Validate YAML/JSON syntax for workflow and machine-readable files.
- Verify the app still imports/starts successfully when feasible.
- Review the diff for secrets, unsafe URLs, accidental product activation, pricing changes, and public exposure of delivery links.
- Summarize risks, tests run, and rollback path in the PR.

## Autonomous Product Factory stages
Treat these as distinct gates rather than one continuous permission:
1. Signal discovery
2. Evidence enrichment
3. Opportunity scoring
4. Opportunity clustering
5. Product discovery
6. Independent validation
7. Build authorization
8. Product construction
9. Technical QA
10. Security review
11. Legal/liability review where applicable
12. Pricing and packaging
13. Publication authorization
14. Deployment/listing
15. Post-launch monitoring and rollback

Passing one stage does not imply authorization for later stages.

## Product and commercial rules
- Do not enable checkout unless fulfillment/delivery is configured and verified.
- Do not represent demonstration or synthetic data as live data.
- Pricing changes must be explicit and reviewable.
- Products dependent on third-party models, APIs, licenses, or data sources must accurately describe those dependencies.
- Third-party code/content must be license-compatible and attributed where required; prefer original implementations over copying.

## GitHub / CI rules
- Use feature branches for substantive work.
- Do not delete working workflows merely to make CI pass.
- A failing safety/validation test is a blocker, not something to bypass.
- Prefer PR-based review with a concise change summary, risk assessment, tests, and rollback instructions.

## Current conservative default
When requirements are ambiguous, choose the option that preserves existing production behavior and keeps publication, spending, checkout, and irreversible actions disabled until explicitly authorized.

## Codex task completion format
For every substantive task, report:
- What changed
- Files changed
- Tests/checks run and results
- Remaining risks or unknowns
- Whether any deployment/publication/payment behavior changed
- Recommended next action
