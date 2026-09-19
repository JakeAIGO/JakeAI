# Pilot Concierge — Release Readiness

Status: **READY FOR DEPLOY REVIEW — NOT YET MERGED TO PRODUCTION**

## Purpose
Pilot Concierge is JakeAI's internal autonomous intake operator for the Autonomous Employee Foundry. It converts each founding-pilot submission into a bounded review case before any human has to manually triage it.

## End-to-end flow
1. Customer submits the existing Autonomous Employee Foundry form.
2. The browser sends the intake to `/pilot-concierge-api`.
3. The server rejects obvious spam, rate-limits abusive sources, and refuses likely passwords/API keys/private keys.
4. The deterministic qualification core scores fit, risk, complexity, missing information and a preliminary internal commercial band.
5. The full case, draft proposal, authority flags and audit events are stored in Netlify Blobs.
6. The customer receives only a receipt and case ID. Internal pricing/risk details are not exposed.
7. The private operator page reads the queue only with `PILOT_CONCIERGE_ADMIN_TOKEN`.
8. Human operator may mark a case approved for scoping, proposal ready, hold, or declined.
9. Those buttons update internal state only. They do **not** email the customer, spend money, deploy code, access external accounts or make commitments.

## Fail-closed / fallback behavior
- If Pilot Concierge is unavailable, the existing Netlify Form submission path remains the fallback capture mechanism.
- Checkout remains gated.
- Customer contact is not automated.
- Production deployment is not authorized by a case status.
- The operator UI is noindex/nofollow and is not linked from public navigation.
- Sensitive case data is returned only after bearer-token authorization.

## Required environment configuration
Set one Netlify secret:
- `PILOT_CONCIERGE_ADMIN_TOKEN` — secret, function/runtime scope.

No secret value belongs in the repository.

## Routes
- Public intake: `/autonomous-employee.html`
- Concierge endpoint: `/pilot-concierge-api`
- Internal operator surface: `/pilot-concierge-operator.html`

The endpoint intentionally does **not** use `/api/*` because current Netlify routing proxies that namespace to the Railway backend.

## Data
Production cases use the global Netlify Blob store:
- Store: `jakeai-pilot-concierge`
- Case keys: `case/<case-id>`
- Rate-limit keys: `rate/<hour>/<hashed-ip>`

Non-production deploys use deploy-scoped blobs so preview/test cases do not contaminate production.

## Qualification output
Every case includes:
- fit score
- fit class: strong-fit / review / needs-clarification
- risk: low / medium / high
- complexity
- tool count
- preliminary internal setup and managed-operation price floors
- open questions
- required approval gates
- recommended build path
- draft proposal
- explicit authority flags, all false by default
- append-only case audit events

The commercial band is an internal estimate only. It is never a customer quote until a human approves scope and price.

## Verification checklist before merge
- [ ] `node tests/pilot_concierge_core.test.mjs` passes.
- [ ] Netlify preview build succeeds.
- [ ] Dry self-test returns strong-fit / low-risk and writes no case.
- [ ] Invalid email is rejected.
- [ ] Secret-like input is rejected and not stored.
- [ ] Six rapid submissions from one source cause rate limit on the sixth.
- [ ] Operator GET without bearer token returns 401.
- [ ] Operator GET with configured token returns the queue.
- [ ] Status update changes internal queue state and adds an audit event.
- [ ] Operator buttons do not send external communication.
- [ ] Public form fallback still exists.
- [ ] Production homepage remains unchanged.
- [ ] Existing commerce fail-closed tests remain green.

## First controlled production test
Submit a clearly labeled case:
`JAKEAI INTERNAL TEST — PILOT CONCIERGE`

Expected:
- case created
- qualification generated
- appears in operator queue
- no email is sent to a customer
- no payment is requested
- no tool connection occurs
- no external action occurs

After verification, mark the case declined or hold. Do not delete audit history merely to make the queue look clean.

## Next evolution after first real pilot
Only after evidence from a real customer case:
- optional model-adapter review for richer scoping
- approved notification channel
- approved proposal-send action
- connector-specific deployment recipes
- outcome monitoring
- reusable skill extraction into the Foundry

Do not add those before the first evidence-bearing pilot proves the base loop.
