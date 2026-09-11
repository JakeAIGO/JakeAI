# JakeAI Master Baseline Security Checkpoint — 2026-09-11

Status: remediation branch only. Not production authorization.

This checkpoint exists to force CI to evaluate the repaired branch head after automated branch-only repairs.

## Security controls now under regression test

- Free products must not depend on Stripe credentials.
- Metered/unfulfilled products fail closed.
- Paid delivery requires a paid Stripe session.
- A paid Stripe session is bound to the exact product ID.
- Paid-session amount must match the catalog price.
- Paid-session currency must be USD for the current checkout implementation.
- A paid session for one SKU cannot unlock another SKU.
- Public catalog, llms.txt, and agent-card output must not expose private delivery URLs.
- SSRF checks reject loopback, private, link-local, reserved, and non-http(s) targets.
- CORS only permits configured JakeAI origins.
- Validation rejects nonpositive or otherwise invalid financial/energy inputs.
- Repair automation rebases onto newer branch-only work and fails closed on conflicts rather than force-pushing.

## Promotion status

No merge, deployment, checkout activation, or production modification is authorized by this checkpoint.
