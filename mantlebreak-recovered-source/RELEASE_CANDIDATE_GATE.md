# Deep Shift Release-Candidate Gate

A build cannot be labeled release candidate until every mandatory item below passes.

- [ ] Godot imports the project without script/resource errors.
- [ ] `SmokeTest.tscn` exits with code 0.
- [ ] `PlaytestRunner.tscn` completes its deterministic batch.
- [ ] `ReleaseGate.tscn` exits with code 0.
- [ ] Windows export completes and produces a non-empty executable.
- [ ] Keyboard playthrough completed.
- [ ] Gamepad playthrough completed.
- [ ] Five-sector expedition can be completed.
- [ ] Failure/death flow returns cleanly to menu.
- [ ] Save data persists across restart.
- [ ] Accessibility settings persist.
- [ ] At least three reproduced failure seeds have been regression-tested.
- [ ] Core Warden telegraphs are readable before damage.
- [ ] No impossible ore/extraction state found.
- [ ] Original production art replaces primitive placeholders.
- [ ] Audio levels reviewed.
- [ ] Store copy and visual identity pass IP/legal review.
- [ ] Current Steamworks requirements rechecked immediately before submission.
