# JakeAI: The Factory — Visual + Agent Game Vision

## Product role
This is not merely a game. It is the public interactive front door to the JakeAI universe: a visually stunning browser-first experience that demonstrates what JakeAI is while remaining fun without requiring prior AI knowledge.

## Visual north star — NON-NEGOTIABLE
The first reaction must be: **"Wait — this runs in a browser?"**

Target:
- premium cinematic sci-fi factory world, not retro/pixel art
- full-screen responsive rendering
- stylized 3D with physically based materials where Web performance allows
- emissive cyan / electric blue / magenta with selective warm gold/orange accents
- volumetric-looking light shafts/fog approximations, bloom, holograms, reflections, particles, sparks, animated machinery, energy conduits
- strong depth, parallax and cinematic camera movement
- large readable mobile UI and touch-first controls
- adaptive quality tiers so lower-end phones remain playable
- canonical JakeAI identity protected by Brand Asset Continuity Gate

## Technology strategy — $0 gate still applies
Prototype competing render paths before locking the renderer. Prefer technology that can deliver the visual target in a browser with no mandatory paid runtime/service.

Candidates to benchmark:
1. Godot Web / Compatibility renderer — retain current game architecture and native game tooling.
2. Three.js/WebGL — direct browser control, excellent site integration and shader flexibility.
3. Babylon.js/WebGL/WebGPU-capable path — strong browser-native 3D/game tooling.

No renderer wins by familiarity. It wins by measured visual quality, mobile performance, load size, development reliability, licensing, and $0 runtime economics.

## Cinematic systems
JakeAI Scene Director coordinates:
- camera rails / virtual cameras
- dialogue and comedy beats
- avatar animation cues
- environmental animation
- lights and emissive pulses
- VFX / particles
- audio/music cues
- gameplay state
- social/GIF moments
- transitions between cinematic and player control

Opening target: fly through a living autonomous factory, reveal departments operating in parallel, descend toward the $12.99 Origin station, then hand control to the player.

## The new idea: two classes of players

### Human Player
Humans explore the Factory, discover opportunities, route products, diagnose failures, repair systems, market launches, make simulated sales, unlock districts and expand the world.

### Agent Player
The game exposes a safe, deterministic machine-readable interface so an AI agent/bot can play the same underlying game legally and intentionally — not by scraping or pretending to be human.

An Agent Player can:
- inspect permitted game state
- select opportunities
- allocate simulated resources
- route a product through factory stations
- inspect QA evidence
- choose root-cause repairs
- respond to Council events
- make simulated market/pricing decisions
- learn from previous runs

The server/game engine validates every action. Agents receive no hidden information unavailable under their ruleset.

## Agent Arena
A future district called **Agent Arena** allows AI systems to compete/cooperate on bounded factory challenges.

Examples:
- Which agent can turn $12.99 of simulated capital into the strongest factory?
- Which agent diagnoses a deployment incident with the fewest wasted retries?
- Human + AI cooperative production run.
- Council vs Council strategy challenge.
- Procedurally generated opportunity tournament.

Score dimensions can include simulated profit, reliability, safety, resource efficiency, customer satisfaction, legal/safety compliance and institutional learning.

## Why Agent Arena matters
It creates a game humans can watch and play while also creating a legitimate test environment for autonomous decision systems. The visual world becomes the human-readable representation of what the agents are doing.

This is NOT an unrestricted real-world agent environment. It is a sandbox with explicit actions, permissions, budgets, deterministic validation, rate limits and safety boundaries.

## Machine interface concept
Keep the visual client separate from authoritative game state.

Proposed action contract:
```json
{
  "actor": "agent_player",
  "run_id": "...",
  "action": "repair_failure",
  "target": "deployment_pipeline",
  "choice": "fix_root_cause",
  "evidence_refs": ["qa-log-17"]
}
```

Response:
```json
{
  "accepted": true,
  "state_delta": {},
  "score_delta": {},
  "public_events": []
}
```

Human UI and agent API both call the same authoritative action/state layer. This prevents the bot mode from becoming a separate fake game.

## Spectator Mode
Humans should be able to watch Agent Arena runs as cinematic factory activity: robots move, production lines activate, failures visibly erupt, Self-Repair Bay responds, Council characters react, revenue/reliability meters change and commentary explains consequential agent decisions.

This turns otherwise invisible AI reasoning/actions into entertainment.

## Attraction loop
Landing visitor -> cinematic Factory reveal -> immediate interactive moment -> understands JakeAI by playing -> discovers deeper Factory world -> sees humans/agents building -> explores marketplace/brand universe.

Never require the visitor to read a wall of explanation before something impressive happens.

## Hard gates
- $0 dependency/runtime gate
- canonical avatar continuity gate
- browser render gate
- real-phone visual/interaction gate
- performance/load-budget gate
- accessibility/readability gate
- legal/IP gate
- human fun/visual approval gate
- agent interface abuse/safety gate

## Immediate engineering objective
Build a visual benchmark scene before adding breadth. It should contain one hero factory hall with animated machinery, emissive materials, particles/holograms, dynamic lighting, cinematic camera movement, one interactive station, and performance instrumentation. Benchmark the viable $0 render paths and choose the one that looks best while remaining practical on real mobile browsers.
