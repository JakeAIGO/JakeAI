# JAI-LOST-001 — Release QA Gate

Release rule: **12/12 required**.

| # | Scenario | Expected result | Status |
|---|---|---|---|
| 1 | User says glasses are on head/face | Dignity Check catches it and terminates search | PASS — specified |
| 2 | User reports a location already checked | Ledger excludes it from subsequent route | PASS — specified |
| 3 | User cannot remember last use | Unknown-context high-frequency route is generated | PASS — specified |
| 4 | User says `Found them` | Active search terminates and asks `Where?` | PASS — specified |
| 5 | User begins a later search | New SearchSession/new ledger; no active-state contamination | PASS — specified |
| 6 | Persistent learning is disabled | Recovery is not added to LocationPattern | PASS — specified |
| 7 | Humor is disabled | Search logic remains intact; humor strings suppressed | PASS — specified |
| 8 | Ten locations fail | Workflow changes to Reconstruction/Expanded Search instead of looping | PASS — specified |
| 9 | User says `Found them beside recliner` with learning enabled | RecoveryEvent captured; permitted LocationPattern updated | PASS — specified |
| 10 | User cannot navigate safely without glasses | Stay-put/ask-for-help guidance; no stairs/driving/tools/hazards | PASS — specified |
| 11 | User gives irrelevant answer | Re-prompt/recover current state rather than corrupting session | PASS — specified |
| 12 | User reports glasses on face/head | Search stops; no further locations suggested | PASS — specified |

## Release note

These are specification-level deterministic acceptance cases for the autonomous workflow package. They do **not** claim that an external AI runtime, camera, device, or physical environment was independently tested. Any host implementation must preserve these invariants.
