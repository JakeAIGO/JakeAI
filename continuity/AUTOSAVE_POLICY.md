# JakeAI Continuity Autosave Policy

## Objective
Keep the shared handoff state current enough that an unexpected model/session limit causes minimal context loss.

## Write triggers
Every worker should write a continuity event immediately after any meaningful completed work unit, including:

- code or configuration changed;
- branch, commit, pull request, deploy, or release state changed;
- external destination verified;
- product status, pricing, legal/safety gate, or commercial decision changed;
- social post or campaign status changed;
- new blocker discovered;
- user gives a durable instruction that changes project operation;
- next action materially changes.

## Rolling checkpoint rule
Update `current_state.json` whenever a new event changes any verified fact, active work item, blocker, constraint, or next action. Do not wait until the end of a session.

## Session-age safeguard
During sustained work, if no state-changing event has occurred for about 15 minutes, no forced checkpoint is necessary because there is no new state to preserve. If meaningful work has occurred but has not yet been recorded, record it before continuing to another major task.

## Failover rule
If a provider/session becomes unavailable unexpectedly, the next worker should read, in order:

1. `current_state.json`
2. the tail of `events.jsonl`
3. a generated portable handoff if available
4. relevant evidence links/files referenced by those records

The next worker must not ask the user to reconstruct information already present there.

## Truth and safety
- Preserve status labels exactly.
- Never promote staged/pending work to live without evidence.
- Do not record secrets, credentials, private paid-delivery URLs, proprietary prompts, internal orchestration logic, or trade-secret implementation details.
- Consequential actions still require their normal approval/security gates.

## Design principle
The handoff is no longer a periodic document created from memory. It is a view generated from JakeAI-owned rolling state plus its recent event journal.
