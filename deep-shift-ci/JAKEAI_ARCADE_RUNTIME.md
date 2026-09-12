# JakeAI Arcade Runtime v0.1

Status: development branch implementation
Game module #001: MANTLEBREAK
Studio: Blazed Trail Studios
Parent universe/platform: JakeAI Arcade

## Purpose
The arcade runtime owns cabinet behavior. Individual games own gameplay. MANTLEBREAK must not contain hard-coded assumptions about coin hardware, operator menus, high-score persistence, or future cabinet vendors.

## Runtime state machine
BOOT → ATTRACT → CREDIT → READY → PLAY → BOSS → GAME_OVER → INITIALS → ATTRACT

## Game/runtime contract
The runtime provides:
- credit accounting and Free Play
- start authorization
- operator lockout
- persistent operator settings
- persistent top-10 scores
- attract/game state transitions
- hooks for cabinet input abstraction
- hooks for crash/watchdog recovery in later passes

A game module must provide:
- a clean new-run reset
- a start-of-play transition
- score reporting
- boss-state notification when applicable
- end-of-run score + metadata
- deterministic reset back to attract-ready state

## MANTLEBREAK cabinet controls
Single player target:
- joystick: movement / drill-rig direction
- DRILL: primary interaction/attack
- SHOCK: crowd-control ability
- SHIELD: emergency defense
- BOOST: high-risk mobility/scoring action
- START: begin authorized run
- CREDIT: generic input event, independent of coin/card hardware
- OPERATOR: protected service input

## Operator settings target
- Free Play
- Credits per Game
- Difficulty
- Master Volume
- Attract Audio
- Input Test
- High-Score Reset
- Runtime Version
- Restart Game
- Exit to System

## Cabinet resilience target
Production cabinets must boot directly into JakeAI Arcade, never require a keyboard for normal recovery, and automatically relaunch the game/runtime after recoverable failures. Hardware-specific payment systems remain replaceable adapters that emit generic CREDIT events.

## Current implementation
`res://scripts/ArcadeRuntime.gd` implements the initial state machine, credits, Free Play, start authorization, operator lockout, persistent settings, and persistent top-10 scores.

## Next engineering pass
1. Wire START/CREDIT/OPERATOR actions into Godot InputMap.
2. Add attract-mode controller and cabinet UI scene.
3. Connect GameState score/death/win events to ArcadeRuntime.
4. Add initials-entry UI.
5. Add operator/settings scene and input diagnostics.
6. Run headless compile + state-machine tests.
7. Add watchdog/relaunch layer for cabinet deployment.
