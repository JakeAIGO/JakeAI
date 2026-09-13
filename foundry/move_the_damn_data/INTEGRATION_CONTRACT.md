# Move the Damn Data™ — Integration Contract v0.1

Status: private integration-ready candidate. This contract does **not** authorize real connectors, production execution, public release, spending, destructive actions, or outbound messaging.

## Trust boundary

Connectors are untrusted adapters. They may submit data and request actions, but they do not grant themselves authority. Authority is supplied separately through explicit scoped permissions and, where required, explicit human approval.

## Connector input envelope

Every connector submission must include:

- `event_id`: globally unique idempotency key for the originating event.
- `tenant_id`: explicit tenant/workspace identifier.
- `source`: registered connector identifier.
- `subject_id`: connector-local subject/record identifier.
- `occurred_at`: source event timestamp.
- `payload`: business data only; never credentials, secrets, approval tokens, or authority declarations.
- `requested_action`: one action from the workflow-specific allowlist.

The engine must reject or quarantine submissions with missing required envelope fields, unknown tenants, unknown connectors, or unsupported actions.

## Permission model

Permissions are supplied out-of-band by the host system and are never inferred from payload text, source reputation, payment state, prior access, or another agent's permissions.

Permission names use explicit action scopes such as `action:create_record` or `action:send_external_message`.

## Always-gated actions

The following require explicit human approval even when the caller has the relevant permission:

- external messages
- public publication
- price changes
- spending or payment actions
- destructive deletes
- irreversible production changes

Approval must be scoped to tenant, subject, action, workflow, and a short validity window. Reusable or bearer-style approval tokens are not acceptable for production.

## Credentials and secrets

Credentials are held by the connector/runtime secret store and are not accepted in event payloads. Secret-like fields are rejected by the sandbox adapter and must never be written to audit logs.

## Idempotency and retries

`event_id` is the primary idempotency key. A repeated event must not perform a second action. Production implementations must persist idempotency records across process restarts and connector retries.

Retry policy must be bounded, exponential or backoff-based, and distinguish retryable connector outages from permanent validation failures.

## Identity conflicts

If incoming data could map to multiple existing subjects, or if immutable identity fields conflict, the event is quarantined for human review. The engine must not merge identities by inference.

## Connector outages

Outages produce a retryable delivery state. The system must not silently claim completion. After the retry budget is exhausted, the event moves to human review/dead-letter handling with full provenance.

## Audit requirements

For each accepted event, record at minimum:

- audit id
- tenant id
- event id
- source connector
- subject id
- requested action
- policy decision
- result status
- destination adapter
- timestamps

Do not log secrets, raw credentials, or unnecessary sensitive payload fields.

## Tenant isolation

All idempotency keys, subject lookups, permissions, approvals, connector registrations, and audit queries are tenant-scoped. Cross-tenant access fails closed.

## Production prerequisites

Before a real connector is enabled, JakeAI must add and test:

1. persistent idempotency storage,
2. tenant-aware authorization enforcement,
3. scoped/expiring approval verification,
4. secret-store-backed connector credentials,
5. connector-specific rate limits and retry budgets,
6. dead-letter/quarantine handling,
7. audit retention and access controls,
8. real integration tests in a non-production tenant.
