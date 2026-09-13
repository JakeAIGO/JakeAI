# Customer Evidence Intake v1 — Real-Host Activation Checklist

Status: **UNRELEASED / OFF-MAIN / PUBLIC LAUNCH NOT APPROVED**

This checklist is the final host-specific gate before any Customer Evidence Intake route may be exposed. Completing it does not itself authorize merge, deployment, checkout activation, or public launch.

## 1. Railway topology freeze
- [ ] Production source remains `JakeAIGO/JakeAI` on `main`.
- [ ] Production service remains `agent-commerce-network`.
- [ ] Production entrypoint remains `commerce_guard:app` unless a separately reviewed release changes it.
- [ ] Public domain and TLS termination are verified on the real Railway service.
- [ ] Intake remains `JAKEAI_INTAKE_ENABLED=false` during all preparation work.

## 2. Isolated evidence storage
- [ ] Provision a **dedicated PostgreSQL database** for Customer Evidence Intake rather than reusing the commerce SQLite store.
- [ ] Confirm least-privilege credentials are scoped to the intake service only.
- [ ] Confirm provider-side encryption at rest and encrypted transport.
- [ ] Apply only the reviewed intake schema.
- [ ] Confirm backup/restore behavior and document whether raw evidence can appear in backups.
- [ ] Confirm deletion semantics after backup restore.
- [ ] Record the database resource ID privately; never commit connection credentials.

## 3. Encryption/key lifecycle
- [ ] Select a reviewed authenticated-encryption provider; do not ship a home-grown cipher.
- [ ] Generate a production encryption key outside the repository.
- [ ] Record only a non-secret key identifier in application metadata.
- [ ] Define rotation, revocation, restore, and old-key read behavior.
- [ ] Prove missing/unavailable key causes fail-closed startup or request rejection.
- [ ] Verify no plaintext customer evidence is written to database, audit tables, logs, traces, crash dumps, or temporary files.

## 4. Deletion authority
- [ ] Generate deletion-token pepper outside the repository; minimum 32 bytes of strong random material.
- [ ] Assign a non-secret pepper version ID for rotation bookkeeping.
- [ ] Store only HMAC digests of deletion tokens; never store plaintext tokens.
- [ ] Persist deletion credential state in the isolated evidence store.
- [ ] Verify one-time token consumption survives process restart.
- [ ] Verify wrong token, consumed token, missing record, and wrong pepper version fail closed.
- [ ] Define pepper rotation so outstanding credentials remain intentionally usable or are deliberately invalidated with a documented customer path.

## 5. Authentication and abuse controls
- [ ] Generate a production-only intake API secret outside source control.
- [ ] Confirm no secret value is present in GitHub, build output, public frontend source, or logs.
- [ ] Configure rate limiting in a shared/durable backend suitable for the actual replica count.
- [ ] Verify forwarded client identity only from the real trusted Railway proxy chain.
- [ ] Run spoof tests for `X-Forwarded-For` and equivalent headers.
- [ ] Document immediate kill-switch procedure (`JAKEAI_INTAKE_ENABLED=false`).

## 6. Privacy-safe observability
- [ ] Disable request-body logging for the intake route.
- [ ] Redact authorization headers globally.
- [ ] Confirm contact fields and submitted evidence never enter platform logs or error traces.
- [ ] Audit events contain only timestamp, event class, actor fingerprint, and outcome.
- [ ] Configure alerts on error rate, abuse/rate-limit spikes, storage failure, encryption-provider failure, and deletion failure without payload capture.

## 7. Retention and deletion policy
- [ ] Human owner explicitly approves the public raw-evidence retention period.
- [ ] Retention job is tested against real production storage in a non-customer rehearsal dataset.
- [ ] Expired raw evidence is removed while permitted non-sensitive aggregate recurrence data follows the approved policy.
- [ ] Explicit deletion removes raw evidence and that submission's recurrence contribution.
- [ ] Define contact-data retention separately from evidence retention.
- [ ] Define what happens to deleted data in backups and after disaster recovery.

## 8. Privacy / consent / customer-facing copy
- [ ] Publish only after the companion `PRIVACY_CONSENT_DRAFT.md` is legally/privacy reviewed and converted into approved public copy.
- [ ] Clearly state what data is requested, what must not be submitted, why it is processed, retention, deletion, and access scope.
- [ ] Explicit consent and no-secrets acknowledgement are required before submission.
- [ ] Do not describe submissions as anonymous unless the actual design and legal review support that claim.
- [ ] No customer material is used publicly, in marketing, or as training/example data without separate permission.

## 9. Safety and scope
- [ ] Text-only intake remains enforced; no upload or URL fetching unless separately reviewed.
- [ ] Credentials, tokens, private keys, payment-card data, financial-account credentials, medical records, government IDs, and unnecessary sensitive data fail closed.
- [ ] Medical, legal, employment, financial-transfer, safety-critical, destructive, or irreversible actions remain outside autonomous v1 scope.
- [ ] Unknown or ambiguous safety state routes to rejection or human review.

## 10. Real-host rehearsal
- [ ] Create a non-customer synthetic test submission containing no secrets or personal information.
- [ ] Verify encryption before persistence.
- [ ] Verify recurrence contribution creation.
- [ ] Verify deletion credential issue/verify/consume path.
- [ ] Verify explicit deletion removes raw evidence and recurrence contribution.
- [ ] Restart the service and verify durable controls persist.
- [ ] Exercise rate-limit and proxy-spoof cases.
- [ ] Disable intake and prove the public route no longer accepts submissions.
- [ ] Confirm rollback does not prevent already-issued deletion requests from being honored.

## 11. Release evidence package
Before requesting launch approval, capture evidence for each item above plus:
- exact Git commit SHA,
- exact CI workflow results,
- exact Railway service/environment/resource identifiers,
- encryption provider/key ID (never key material),
- evidence-store resource ID (never credentials),
- approved retention value,
- approved privacy/consent copy,
- incident owner and kill-switch procedure,
- rollback rehearsal result,
- final GO/NO-GO recommendation.

## Human release gate
**Do not merge PR #45, create or modify production resources, set production intake variables, expose a route, activate checkout, or publish launch messaging without explicit approval for that specific release after the evidence package is reviewed.**
