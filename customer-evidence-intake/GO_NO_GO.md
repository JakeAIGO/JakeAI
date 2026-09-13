# Customer Evidence Intake v1 — GO / NO-GO Launch Sheet

Status: **PRIVATE RELEASE CANDIDATE / DRAFT PR #45 / NOT APPROVED FOR PUBLIC LAUNCH**

Decision rule: engineering readiness is necessary but not sufficient. Public launch remains NO-GO until every required production and governance item below is evidenced and the human release gate is explicitly approved for this release.

## Verified engineering gates — GO

- Text-only intake; no file upload and no URL fetching.
- Bounded request size and strict JSON shape.
- Explicit HTTPS origin allowlist; wildcard origin rejected.
- Bearer authentication boundary with strong deploy-time secret requirement.
- Secret/sensitive-data screening fails closed for tested credential patterns.
- High-consequence categories route away from autonomous processing.
- Rejected secret/sensitive submissions are not persisted by the intake service.
- Durable rate-limit prototype survives process reopen and stores hashed actor identifiers.
- Trusted proxy logic ignores forwarded client identity from untrusted peers.
- Audit prototype stores metadata only, not request payload or authorization values.
- Explicit deletion removes raw evidence and the submission's recurrence contribution.
- Deletion credentials are random, one-time, and stored only as digests by the current authority prototype.
- Raw-evidence retention purge is bounded and tested.
- Production evidence protection fails closed without an injected encryption provider; JakeAI does not ship homemade cryptography.
- Final offline attack/rollback rehearsal passes on the exact candidate head after fixing defects discovered by CI.
- No production endpoint, customer database, checkout activation, or public intake was created by this release-candidate work.

## Production gates — NO-GO until evidenced

1. **Encryption provider selected and integrated.** Use a reviewed authenticated-encryption/key-management implementation appropriate to the actual host. Record key ID strategy, rotation, revocation, backup/restore behavior, and failure mode.
2. **Production data store selected and access-isolated.** Confirm encryption at rest, least-privilege service access, backup handling, restore behavior, tenant/access boundaries, and deletion propagation.
3. **Deletion authority made durable and recoverable without weakening token secrecy.** The current in-memory authority proves the interface, not production durability.
4. **Rate limiting made horizontally safe.** SQLite prototype is acceptable for rehearsal, not proof for multiple replicas/workers.
5. **Hosting proxy chain verified.** Freeze trusted proxy CIDRs/identity behavior for the actual deployment and test spoofing against that configuration.
6. **Secret lifecycle configured.** Generate a production-only intake secret outside the repository; define rotation/revocation and never log it.
7. **Observability configured without payload logging.** Confirm platform/app logs cannot capture request bodies, authorization headers, contact text, or rejected sensitive material.
8. **Incident/abuse procedure written and owned.** Include secret-submission response, abuse/rate-limit escalation, data-deletion failure, suspected exposure, and kill-switch procedure.
9. **Rollback rehearsal against the real host.** Prove disable/rollback without preserving unintended public access or losing required deletion capability.
10. **Backup/deletion semantics verified.** Decide whether backups contain raw evidence, retention period, and how deletion requests affect backup restoration.

## Privacy / legal / claims gates — NO-GO until reviewed

- Finalize plain-language intake notice describing purpose, accepted data, prohibited data, retention, deletion, contact handling, and who can access submissions.
- Do not claim submissions are anonymous. Hashes/digests used for deduplication or identifiers are not automatically anonymous.
- Separate optional contact information from evidence storage and define its purpose/retention/deletion rules before launch.
- Define the public retention promise. The current 30-day value is a prototype default, not yet an approved public policy.
- Confirm the applicable privacy/consumer/data-security obligations for the actual launch geography and customer types before collecting real submissions.
- Confirm terms/consent language, limitation-of-service claims, and treatment of customer-provided material before launch.
- No customer material becomes public training data, a public product example, or marketing content without separate explicit permission.
- Do not make guarantees that JakeAI can automate a submitted process, save a particular amount, eliminate errors, or provide legal/compliance assurance.

## Commercial gate

- Customer Evidence Intake is a **free qualification/diagnostic entry point**, not itself the paid product.
- A paid Rescue is offered only after the submitted residual survives Product Factory evidence, dollarized-pain, competitor/free-alternative, safety/legal/liability, and objective completion-test gates.
- Do not activate checkout for a Rescue before the bounded deliverable and acceptance test are defined.
- First independent paying customer remains unverified; friendly/self/test payments do not count as outside validation.

## Release decision

**Current recommendation: NO-GO for public deployment. GO for continued private release preparation only.**

The engineering candidate has passed its current offline security/rehearsal tests, but real-host encryption/storage, durable deletion authority, horizontally safe abuse controls, privacy/consent language, legal/privacy review, and host-specific rollback remain unresolved.

### Human release gate

Even after all NO-GO items become evidenced, do not merge PR #45, deploy the intake, expose a public endpoint, activate checkout, or publish launch messaging until the user gives explicit approval for that specific release after reviewing the final evidence package.
