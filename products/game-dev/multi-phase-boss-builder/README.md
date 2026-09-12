# JakeAI Multi-Phase Boss Builder Autopilot v0.1

Status: executable prototype branch

## Purpose
Convert a boss concept into an original, implementation-ready GameMaker boss package.

## Inputs
- boss identity/concept
- phase count
- player abilities
- target difficulty
- arena rules
- attacks and hazards
- reward/ending condition

## Outputs
- boss state machine
- phase transition thresholds
- attack-selection logic
- telegraph -> attack -> recovery timing
- damage and invulnerability windows
- cooldown and tuning variables
- arena phase changes
- GameMaker object/event scaffolding
- GML implementation skeleton
- QA checklist and edge cases

## First validation boss: Cosmic Vending Machine
Phase 1: Snack Storm
- falling product hazards
- visible telegraphs
- movement-pressure test

Phase 2: Refund Denied
- arena conveyor belts activate
- energy receipts can be reflected
- reflected receipts create boss damage windows

Phase 3: Return to Sender
- victory condition shifts from raw damage to objective play
- return three misplaced products to matching slots while surviving the malfunction

## Product-chain test
Boss Fight Lab -> Multi-Phase Boss Builder -> Game QA Autopilot

The prototype is considered useful only if it shortens implementation work, keeps phase logic understandable, and exposes balancing variables cleanly enough for a developer to tune without rewriting the state machine.

## Originality / legal rule
Public projects may be used as evidence that a problem exists. JakeAI does not copy third-party source code, assets, level layouts, or proprietary implementation details. Generated implementations must be independently designed from the requested gameplay behavior and public GameMaker platform capabilities.

## v0.1 acceptance gates
1. A developer can map the generated files into a GameMaker project without inventing the state architecture from scratch.
2. Every attack follows a readable telegraph -> active -> recovery cycle.
3. Phase transitions are deterministic and cannot double-trigger.
4. Damage windows and invulnerability are explicit.
5. Core tuning values are centralized.
6. QA includes stuck-state, transition, cooldown, objective, and death/reset checks.
