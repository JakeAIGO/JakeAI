# JakeAI Customer Evidence Intake — Privacy & Consent Draft

Status: **DRAFT FOR REVIEW / NOT PUBLIC COPY / NOT LEGAL APPROVAL**

This draft is intended to become the plain-language intake notice and consent text after privacy/legal review and host-specific retention/storage decisions are finalized.

## Short notice for the intake form

**What this is**

JakeAI uses this form to understand one recurring task, exception, or workaround that your existing software or AI still makes a person fix, check, copy, chase, or redo. The goal is to determine whether that human intervention is recurring, economically meaningful, and potentially safe to reduce or automate.

**What to submit**

Please provide only the minimum non-sensitive information needed to describe the workflow, including the software involved, what normally happens, what a person still has to do, how often it happens, roughly how long it takes, what happens if it is not done, and the non-sensitive evidence the person uses to decide what to do.

**Do not submit**

Do not submit passwords, API keys, access tokens, private keys, authentication codes, payment-card data, financial-account credentials, medical records, government identification numbers, confidential customer records, trade secrets you are not authorized to share, or other unnecessary sensitive or regulated information. Do not submit material that you do not have permission to provide.

**What JakeAI does with it**

JakeAI may screen the submission for prohibited or sensitive content, convert accepted information into a structured workflow-evidence packet, estimate human time involved, compare the problem against existing/free alternatives, and determine whether a bounded JakeAI Rescue may be worth proposing. Submission does not guarantee that JakeAI will build, automate, or solve the workflow.

**What JakeAI does not do through this form**

This intake does not give JakeAI access to your systems, credentials, files, accounts, or production environment. It does not authorize JakeAI to make financial, medical, legal, employment, safety-critical, destructive, or irreversible decisions or changes on your behalf.

**Retention and deletion**

Accepted raw submissions will be retained only for the approved period stated at launch. The exact public retention period is not yet finalized in this draft. A deletion mechanism will be provided for accepted submissions. Depending on the final approved policy, non-sensitive aggregate recurrence information may be retained separately from raw text unless you exercise a deletion right that also removes your submission's contribution.

**Contact information**

Providing contact information is optional unless JakeAI needs a way to return a requested result. If collected, contact information will be used only for the stated follow-up purpose and will follow a separately approved retention/deletion rule.

**No public reuse without permission**

JakeAI will not publish your raw submission, use it as a public product example, or use it in marketing without separate permission. This intake notice does not grant permission to make your material public.

## Required consent checkboxes

Before submission, the public form should require affirmative confirmation of all of the following:

- [ ] **I am authorized to submit this information.**
- [ ] **I have removed passwords, API keys, tokens, private keys, financial-account credentials, medical records, government IDs, payment-card data, and other unnecessary sensitive information.**
- [ ] **I understand this submission is for workflow analysis/qualification and does not guarantee automation, savings, error reduction, compliance, or a paid product.**
- [ ] **I consent to JakeAI processing this information for the purposes described in the intake notice.**
- [ ] **I understand that I should not use this form for emergencies or for consequential medical, legal, employment, financial-transfer, safety-critical, destructive, or irreversible decisions.**

The submit action must remain disabled until every required checkbox is affirmative.

## Suggested confirmation after submission

**Received.** JakeAI will first screen the submission for scope and safety. If it contains material that should not be processed, it may be rejected without being stored in the evidence system. If accepted, it may be converted into a structured workflow-evidence packet for Product Factory evaluation. A submission is evidence, not a promise that a product will be built.

If a deletion credential is issued for your accepted submission, keep it secure. JakeAI cannot safely substitute a different person for possession of that credential unless a separately approved account-authenticated recovery process exists.

## Internal privacy rules tied to this notice

1. Collect the minimum information necessary for workflow qualification.
2. Do not silently broaden the purpose after collection.
3. Separate optional contact data from workflow evidence where practical.
4. Never write raw submissions, contact text, authorization headers, or suspected secrets to ordinary application logs.
5. Block or fail closed on likely secrets and prohibited high-risk categories before downstream processing/persistence where technically possible.
6. Do not call a hash, fingerprint, or recurrence signature "anonymous" merely because plaintext was transformed.
7. Restrict access to authorized operators/services with a business need.
8. Keep raw retention bounded and documented.
9. Honor approved deletion semantics, including recurrence-contribution removal where promised.
10. Do not use submissions for public training, promotion, testimonials, or examples without separate explicit permission.
11. Do not sell customer-submitted raw evidence as a data product.
12. Material changes to purpose, retention, access, or reuse require a new review and, where appropriate, updated notice/consent.

## Claims that must not appear in public copy

Do not claim that the intake is anonymous, perfectly secure, legally compliant in every jurisdiction, guaranteed to find savings, guaranteed to automate a process, guaranteed to eliminate human review, guaranteed to prevent errors, or a substitute for legal/compliance/security advice.

## Items that must be frozen before publication

- Public raw-evidence retention period.
- Contact-data retention period and purpose.
- Final deletion UX and authentication/recovery model.
- Final storage/encryption/backup treatment.
- Operator/access roles.
- Incident/contact channel.
- Geographic/customer scope at launch.
- Applicable privacy/consumer/data-security requirements after legal/privacy review.
- Final Terms/Privacy Policy cross-links and version/effective date.

## Release gate

This file is drafting material only. It does not constitute legal advice or legal approval. Do not publish it as final privacy/consent language and do not collect real customer evidence through the production intake until the host-specific data lifecycle is finalized, the applicable legal/privacy review is completed, and the user explicitly approves the specific public release.
