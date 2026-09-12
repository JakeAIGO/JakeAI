# Deep Shift — Godot Production Pass 5

This pass builds the first commercial-support layer around the core game.

## New
- Seven original, procedurally generated WAV sound effects.
- Pooled Godot audio manager.
- Keyboard + gamepad input mappings.
- Persistent accessibility/settings data.
- Run telemetry recorder.
- Autonomous deterministic playtest simulator.
- Batch playtest runner designed for headless Godot.
- Windows Desktop export preset.
- Autonomous playtester specification and acceptance gates.

## Autonomous playtest command
When Godot 4 is available:

`godot --headless --path . --scene res://scenes/PlaytestRunner.tscn`

The current abstract simulator runs 250 deterministic expeditions and reports:
- win rate
- average score
- death causes
- ability usage
- reproducible failure seeds

This is deliberately separated from the future real-input gameplay bot. It lets the Product Factory begin testing the balance-analysis pipeline before full runtime automation exists.

## Runtime limitation
Godot is still not installed in this execution environment. Static/resource QA passes, but runtime validation and Windows export must occur on a machine/CI runner with Godot 4 and export templates.

## Next major gate
Before adding Steamworks, the project should execute:
1. SmokeTest.tscn
2. PlaytestRunner.tscn
3. A real interactive Godot playthrough
4. Windows export
5. Human fun/fairness validation

Only after those pass should the Steam integration/release pipeline be promoted.


## Production Pass 6
A GitHub Actions pipeline now automates the next proof point. On a repository runner it installs Godot, imports the project, executes smoke tests and the autonomous playtest simulation, then attempts a Windows export and uploads the resulting build artifact.

Also added:
- ReleaseGate.tscn
- RELEASE_CANDIDATE_GATE.md
- CI_RUNTIME_GATE.md
- asset provenance/IP manifest
- SHA-256 project manifest

No runtime-pass or executable claim is being made until that CI pipeline actually succeeds.


## Production Pass 8 — Live Godot validation

The GitHub `deep-shift-ci` branch has now executed a strict Godot 4.3 pipeline successfully.

Verified in a real Godot runner:
- clean import with log scanning for hidden script errors
- production gameplay script compile gate
- deterministic smoke tests
- 500 generated sector layouts checked for placement overlap
- 250-expedition autonomous balance gate

Latest balance baseline: 54 wins / 250 runs (21.6%), average score 2596.4. Energy depletion accounted for only 4 deaths; enemy/hazard pressure remains the dominant loss source.

Important scope boundary: this proves the tested gameplay code and procedural systems compile/run under Godot. It is not yet proof that the complete visual/audio game exports and launches as a Windows executable.
