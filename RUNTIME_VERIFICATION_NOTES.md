# JakeAI Runtime Verification Notes

Status: remediation-branch verification record only. No production deployment or commercial activation is authorized by this file.

## Audit provider wiring
Repository inspection confirms `main.py` includes direct upstream integrations for Anthropic and Perplexity in the multi-model audit endpoint.

- Anthropic endpoint: `https://api.anthropic.com/v1/messages`
- Configured model: `claude-3-5-sonnet-20241022`
- Environment key: `ANTHROPIC_API_KEY`

- Perplexity endpoint: `https://api.perplexity.ai/chat/completions`
- Configured model: `sonar-pro`
- Environment key: `PERPLEXITY_API_KEY`

Provider credentials are server-side only; caller-supplied provider-key headers are not accepted. If either server key is absent, the corresponding provider returns `simulation_mode` and `NOT_RUN`, and consensus does not return a successful dual-model GO.

Runtime configuration is not proven solely by source inspection. A later authorized deployment/runtime check must verify that each provider is configured and returns a successful live response before JakeAI describes every audit as executed by both external providers.

## Public API routing
The Netlify front end proxies `/api/*` to the Railway backend with the `/api/` prefix removed. Therefore the canonical website-facing form is `/api/v1/...`, while direct Railway/backend routes use `/v1/...` where implemented.

Documentation and machine-readable surfaces must distinguish website proxy paths from direct backend paths.

## Machine-readable discovery
`main.py` generates `/llms.txt` and `/.well-known/agent.json` dynamically from the runtime catalog. Netlify routing force-proxies both public machine-readable paths to Railway.

Static repository `llms.txt` and `agent_card.json` are non-authoritative pointer/compatibility artifacts. Claim-consistency tests prevent them from silently asserting live commercial state.

## External network-fetch posture
Outbound fetch-based tools are disabled by default behind server-side configuration pending hardened egress validation. This includes the web-to-markdown extractor and remote agent-card audit path.

Current SSRF controls reject direct private/loopback/link-local/reserved targets and fail if hostname resolution includes a private target. These controls are useful but are not being treated as sufficient proof against redirect or DNS-rebinding classes of attack; the features therefore remain fail-closed by default.

## Health semantics
`/health` is a process-liveness signal only. A response of `status: alive` does not assert checkout readiness, provider readiness, fulfillment readiness, metering readiness, or full dependency health.

## Current verification boundary

Verified in repository code/tests:
- provider integration code exists;
- missing provider configuration fails closed to `NOT_RUN` / review required;
- caller-supplied provider secrets are not accepted;
- dynamic machine-readable routes exist;
- canonical public-vs-backend API routing convention is defined;
- external fetch tools fail closed by default;
- payment verification binds paid session to product, amount, and currency;
- public catalog/machine discovery excludes private delivery URLs;
- Master Baseline CI runs the full regression suite.

Verified by read-only production smoke at selected checkpoints:
- site root reachability;
- `/health`;
- `/llms.txt`;
- `/.well-known/agent.json`;
- `/docs`;
- `/openapi.json`;
- terms/privacy/refunds pages.

Not yet verified:
- remediation candidate deployed to production;
- both provider keys are present in live deployment;
- live calls to both providers succeed;
- provider responses match marketing descriptions;
- paid Stripe purchase/fulfillment works in production;
- Game QA private fulfillment is live;
- API-credit metering/entitlement is operational;
- outbound-network tools are safe to enable;
- the audit is enforced as a required production deployment gate.

Until those runtime checks pass, public claims must distinguish implemented/configurable capability from verified live execution.
