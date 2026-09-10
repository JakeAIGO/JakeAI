# Deep Shift — Pass 11 External Playtest Promotion

Goal: move Pass 10 from mechanically hardened candidate to a human-facing external playtest build.

## Promotion gates

1. First-run onboarding
   - Show movement, dig, abilities, extraction objective, and pause/controller hints in-game.
   - Dismissible and non-blocking after first sector start.

2. HUD clarity
   - Clearly separate ORE (current extraction requirement) from CREDITS (persistent/run economy).
   - Show sector number/name and extraction lock reason.
   - Boss sector must visibly state that extraction is locked until Core Warden defeat.

3. Feedback
   - Damage feedback must be visible and throttled by Pass 10 invulnerability.
   - Zero-energy emergency recovery must be explained instead of looking broken.
   - Upgrade selection must communicate that gameplay is paused.

4. Input readiness
   - Keyboard mappings remain functional.
   - Controller pause mapping remains present.
   - Controller-facing hint text included where appropriate.

5. Regression
   - Pass 10 hardening gate remains green.
   - Full game-flow gate remains green.
   - Interaction gate remains green.
   - Windows export succeeds.
   - Exact exported EXE receives downstream artifact startup QA.

6. External playtest package
   - Include DeepShift.exe, BUILD_IDENTITY.txt, SHA256.txt, and PLAYTEST_README.txt.
   - README asks tester to report: launch failure, confusing controls, unfair deaths, soft-locks, boss problems, and overall fun score 1–10.

## Commercial status

Pass 11 is an external playtest candidate, not a commercial release. Formal IP/trademark and release/legal gates remain required before sale.
