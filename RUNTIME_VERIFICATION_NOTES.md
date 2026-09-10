# JakeAI Runtime Verification Notes

Status: Codex setup branch only. No production deployment or commercial activation is authorized by this file.

## Audit provider wiring
Repository inspection confirms `main.py` includes direct upstream integrations for Anthropic and Perplexity in the multi-model audit endpoint.

- Anthropic endpoint: `https://api.anthropic.com/v1/messages`
- Configured model: `claude-3-5-sonnet-20241022`
- Environment key: `ANTHROPIC_API_KEY`

- Perplexity endpoint: `https://api.perplexity.ai/chat/completions`
- Configured model: `sonar-pro`
- Environment key: `PERPLEXITY_API_KEY`

If either key is absent, the corresponding provider returns `simulation_mode` and `NOT_RUN`, and the consensus does not return a successful dual-model GO. This is a useful fail-closed behavior.

Runtime configuration is not proven solely by source inspection. A later deployment check must verify that each provider is configured and returns a successful live response before JakeAI describes the dual-model audit as live.

## Public API routing
The Netlify front end proxies `/api/*` to the Railway backend with the `/api/` prefix removed. Therefore the canonical website-facing form should be `/api/v1/...`, while Railway itself serves backend `/v1/...` routes.

`main.py` currently registers both `/v1/products/search` and `/api/v1/products/search` for the search route, but most other backend routes are `/v1/...` only. Documentation should distinguish website proxy paths from direct backend paths.

## Machine-readable discovery
`main.py` generates `/llms.txt` and `/.well-known/agent.json` dynamically from the live catalog. This is more reliable than separately maintained static files because price and checkout status can be generated from the same catalog logic.

The `codex-setup` branch now force-proxies both public machine-readable paths to Railway so Netlify does not serve stale static claims. The Codex PR guardrail also checks that these routing rules remain present.

## Security follow-up
The multi-model audit accepts optional `X-Anthropic-Key` and `X-Perplexity-Key` request headers in addition to environment keys. Before public BYOK support is claimed or encouraged, document and review:

- whether caller-supplied keys are intentionally supported;
- authentication/authorization expectations;
- whether headers can appear in application, proxy, platform, or error logs;
- rate limiting and abuse controls;
- retention and privacy behavior;
- whether server-owned keys should take precedence over caller keys or vice versa.

## Current decision boundary
Verified in repository code:
- provider integration code exists;
- missing provider configuration fails closed to `NOT_RUN` / review required;
- dynamic machine-readable routes exist;
- Netlify proxy architecture is understood.

Not yet verified:
- both provider keys are present in live deployment;
- live calls to both providers succeed;
- provider responses match the marketing descriptions;
- the audit is enforced as a required production CI gate.

Until those runtime checks pass, public claims should say the integration is implemented/configurable rather than asserting every audit is executed by both external providers.
