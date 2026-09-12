# JakeAI Boss Builder Proof Case 02 — The Abyssal Bellkeeper

## Why this test exists
The first reference encounter, Cosmic Vending Machine, could still be a one-off. This test uses a materially different genre, tone, arena, player kit, victory model, phase count, and interaction pattern to test whether the underlying Boss Builder architecture generalizes.

## Identity and hook
The Abyssal Bellkeeper is a four-phase underwater horror boss occupying a flooded cathedral chamber. The creature is mostly hidden in darkness and cannot be damaged directly until sonar exposes resonant anatomy. The arena's cathedral bells are not decoration: the player manipulates them to interrupt attacks, redirect currents, and create damage windows.

## Core deterministic state loop
Each combat phase follows a shared contract:

`INTRO/TRANSITION -> TELEGRAPH -> ACTIVE_ATTACK -> COUNTERPLAY_WINDOW -> RECOVERY -> NEXT_ATTACK`

Phase transitions are monotonic: 1 -> 2 -> 3 -> 4 -> DEFEATED. A transition lock prevents duplicate advancement.

## Phase 1 — The Drowned Nave
**Purpose:** teach sonar + weak-point interaction.

- Telegraph: boss silhouette crosses darkness pockets; floor ripples and chain tension visibly point toward the next strike lane.
- Attack: sweeping anchor-arm strike followed by a current pulse.
- Counterplay: sonar reveals one resonant weak point for a short window.
- Opening: successful sonar reveal opens a harpoon damage window during recovery.
- Arena behavior: two slow current lanes rotate clockwise.
- Transition: after the first health threshold is reached, the Bellkeeper retreats upward and tears loose the first bell chain.

## Phase 2 — Bells Below
**Purpose:** introduce environmental interruption.

- Telegraph: one suspended bell shakes while a matching visual waveform appears on the arena floor.
- Attack: pressure-wave scream that tracks the player.
- Counterplay: harpoon the highlighted chain before the scream peaks; the falling bell interrupts the attack and exposes the boss.
- Opening: interrupted scream creates a larger recovery window than normal sonar exposure.
- Arena behavior: three current lanes rotate at alternating speeds.
- Failure safety: if the player misses every bell-chain interrupt, the normal sonar route still creates smaller damage opportunities; the encounter never becomes unwinnable.
- Transition: health threshold plus at least one successful bell interaction.

## Phase 3 — Blackwater Choir
**Purpose:** combine learned mechanics under reduced visibility.

- Telegraph: visible sonar rings identify the next safe lane; attack direction is also represented by chain movement so the cue is not color-dependent.
- Attack set: alternating current crush, phantom lunge, and delayed pressure burst.
- Counterplay: use sonar to distinguish the real Bellkeeper from decoys, then strike the correct bell chain to interrupt the real attack.
- Opening: correct identification creates a weak-point exposure; incorrect chain choice changes arena current but does not hard-lock progress.
- Arena behavior: darkness pockets expand and migrate.
- Transition: health threshold triggers collapse of the central bell tower and changes the arena topology.

## Phase 4 — Last Toll
**Purpose:** hybrid objective finale rather than a simple HP race.

- Boss HP stops being the sole victory condition.
- Three resonant seals appear around the chamber.
- Loop: sonar reveals which seal is active -> player survives attack -> harpoons corresponding chain -> bell strike breaks seal.
- Each broken seal removes one attack from the boss's final pattern and increases recovery duration slightly.
- After all three seals break, the Bellkeeper enters `FINAL_EXPOSURE` and one normal damage window becomes available.
- Victory occurs only when all three seals are broken and the final exposure is successfully damaged.
- Safety rule: seals cannot become permanently inaccessible; failed attempts recycle after a bounded recovery period.

## Central tuning surface
The generated GameMaker scaffold should expose, at minimum:

- max HP and per-phase HP thresholds
- telegraph frames per attack
- active attack frames
- recovery frames
- sonar reveal duration
- bell interrupt timing tolerance
- current-lane speed by phase
- darkness-pocket coverage by phase
- seal recycle delay
- final exposure duration
- difficulty multipliers

## Difficulty scaling
Easy/Normal/Hard/Expert variants alter timing and simultaneous hazards, not hidden rules. Readability is preserved at every level. Higher difficulty shortens recovery windows, increases current speed, and combines attack patterns; it does not remove telegraphs.

## Accessibility contract
- No essential telegraph depends on color alone.
- Audio attack cues have visible waveform/chain-motion equivalents.
- No unavoidable full-screen flashes.
- Critical timing windows are exposed as centralized values so alternate difficulty/accessibility presets can widen them.

## QA gates
1. No phase can transition backward.
2. Duplicate phase transitions are ignored.
3. Damage is rejected outside explicit recovery/final-exposure states.
4. Missing a bell interrupt cannot make the encounter unwinnable.
5. Wrong Phase 3 chain selection cannot permanently block the correct solution.
6. Phase 4 seals always recycle until completed.
7. Final victory cannot trigger before three seals are broken.
8. Encounter completion fires once.
9. Reset restores HP, phase, seals, currents, darkness state, and transition locks.
10. All attack telegraphs have both gameplay-readable and accessibility-readable cues.

## Generalization result
This encounter differs from Cosmic Vending Machine in theme, phase count, player verbs, arena mechanics, damage model, victory model, attack vocabulary, and accessibility demands while still fitting the same Boss Builder input/output contract. That is evidence that the architecture is reusable rather than tied to a single boss concept.
