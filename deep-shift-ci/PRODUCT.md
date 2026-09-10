# Deep Shift — Product Milestone

## Product target
Ship a small, original, playable Windows game prototype under the working studio label Shiftforge Games.

## Core player loop
1. Enter a procedurally assembled underground sector.
2. Move, survive hazards, and fight enemies.
3. Use the existing ability system to create tactical choices.
4. Reach the sector objective / boss encounter.
5. Complete the run or die and restart.

## Prototype acceptance criteria
A build is a PRODUCT CANDIDATE only when all of these pass:
- Godot project compiles without script/parser errors.
- Automated smoke test passes.
- Automated playtest runner completes its required assertions.
- Player can move and use the implemented core abilities.
- Enemy and hazard interactions can damage/kill the player.
- A boss encounter can be reached and resolved.
- Game state supports a complete run outcome and restart path.
- Windows export succeeds and produces a downloadable artifact.
- No third-party copyrighted game assets, names, characters, or music are required to run the prototype.

## Current build evidence
The repository contains a Godot project, gameplay scripts, smoke/compile/playtest scenes, an automated Deep Shift Runtime QA workflow, and a Windows export preset. The CI workflow is the source of truth for technical pass/fail.

## Next production gate
Do not add broad strategy documents until the playable artifact gate is satisfied. Prioritize, in order:
1. executable Windows artifact,
2. complete start-to-finish run,
3. visible original game presentation,
4. player-facing menu/instructions,
5. packaging for external playtest.

## Commercial gate
Steam/store publication is not authorized by this milestone. Before sale/publication, complete original-asset/IP review, naming review, store packaging, pricing, and release authorization.
