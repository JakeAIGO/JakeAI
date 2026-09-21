# JakeAI Insurance Growth Desk — Jim Pilot

Status: PRIVATE RELEASE CANDIDATE. Not released to production.

## Architecture

This pilot reuses JakeAI Direct and its existing Campaign Builder/runtime. It does not create a second marketing platform.

Primary doors:
1. IUL + Annuity Lead Foundry
2. First Term Marketing

Supporting surfaces:
- Jim Direct command console
- Private Lead Inbox
- consent evidence + lead status ledger
- funnel metrics
- approval gate

## Fail-closed rules

- No public lead-capture endpoint in this release.
- No email, text, call, social post, ad spend, deployment, or other outbound action is executed by the Insurance Growth Desk.
- Outbound copy is draft material until an authorized human approves it.
- A lead cannot reach `contact_approved` unless its consent status is `opt_in_verified` and consent evidence is recorded.
- The workspace does not make individualized insurance recommendations or annuity suitability/best-interest determinations.
- Sensitive traits are not valid lead-scoring inputs.
- IUL/annuity claims must not promise market returns or guaranteed tax results.
- First Term's legal identity, carrier relationships, product portfolio, licensing, approved disclosures, and approved marketing language remain unverified until supplied and reviewed.

## Production configuration required before pilot access

- `INSURANCE_PILOT_ACCESS_CODE`
- `INSURANCE_PILOT_OWNER=Jim`
- `INSURANCE_BRAND_DISPLAY_NAME=<verified legal/display name>`
- `INSURANCE_BRAND_VERIFIED=false` until verification is complete
- optional `INSURANCE_PILOT_DAILY_RUN_LIMIT` (default 50)

## Activation sequence

1. Review this branch and automated guardrail tests.
2. Verify First Term identity and approved public-facing brand language.
3. Configure a strong pilot access code server-side.
4. Deploy the backend + static portal together.
5. Smoke-test login, Direct run, manual lead creation, consent blocking, logout, mobile and desktop.
6. Give Jim the private portal URL/access code.
7. Keep public lead capture and outbound automation disabled during the validation period.
8. Collect pilot evidence: lead source, verified opt-in, appointment, application, issued result, and campaign attribution.
9. Only after evidence + compliance review consider adding permission-based public intake or approved outbound adapters.

## Pilot success evidence

The pilot is successful when it demonstrates that Jim can use JakeAI directly to prepare campaigns and lead workflows, manage permissioned leads, and connect marketing activity to measurable insurance-business outcomes without bypassing human approval.
