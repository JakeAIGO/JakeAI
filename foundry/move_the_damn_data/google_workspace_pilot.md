# Move the Damn Data™ — Google Workspace Private Pilot

Status: **PRIVATE / CONTROLLED / NOT PRODUCTION / NOT PUBLIC**

## Selected connector pair

**Google Sheets intake → Gmail draft**

This is the first real connected-system boundary selected for the Move the Damn Data™ private pilot because it proves a useful cross-system relay while keeping the consequential outbound action behind human approval.

## Pilot behavior

1. Read an authorized intake record from the private pilot Sheet.
2. Validate that the record is synthetic/authorized for testing.
3. Prepare the next permitted action.
4. Create a Gmail draft only.
5. Record the Gmail draft/message identifier back into the Sheet.
6. Stop with `awaiting_explicit_send_approval`.
7. Do not send unless the user explicitly authorizes that specific send.

## Latest controlled pilot evidence

Event: `pilot-002`

Source: `authorized_intake_private_pilot`

Requested action: `prepare_followup_draft`

Result: `draft_created_waiting_human_approval`

Audit state: `real_connector_draft_created`

Next action: `do_not_send_without_explicit_approval`

The recipient for this pilot step is the authenticated JakeAI account itself. No customer or outside recipient is involved.

## Important implementation truth

This pilot uses ChatGPT's connected Google Sheets and Gmail actions as the live connector boundary. It does **not** mean the repository's reference Python code is independently deployed with Google credentials or autonomously polling Google Workspace.

The repository engine remains the safety/reference architecture for idempotency, approval scope, durable state, recovery, tenant isolation, and fail-closed execution. Production connector deployment remains a separate approval-gated step.

## Release gate

No merge, production deployment, public listing, public publication, spending, customer communication, or autonomous external send is authorized by this pilot.
