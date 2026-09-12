# QA — Cosmic Vending Machine v0.1

## State safety
- Phase 1 cannot skip directly to Phase 3.
- Each phase transition fires once even if HP crosses multiple thresholds in one frame.
- No normal attack starts while phase_transition is active.
- defeated is terminal.

## Telegraph cycle
For every attack family verify the sequence is deterministic:
1. telegraph
2. active
3. recovery
4. idle
5. next attack

## Damage rules
- Phase 1 accepts normal damage.
- Phase 2 accepts normal damage plus reflected-receipt damage.
- Reflected receipts do nothing outside Phase 2.
- Phase 3 rejects normal HP damage.

## Objective rules
- Product returns count only in Phase 3.
- Counter caps at required_returns.
- Third valid return completes the objective.
- Encounter cannot report victory before required_returns is reached.

## Reset / lifecycle
- New encounter starts at full HP, Phase 1, idle state, zero products returned.
- Restart does not retain prior phase/objective state.
- Encounter completion should trigger reward logic exactly once after production integration.

## Integration checks before sale
- Replace comment placeholders with actual GameMaker object/spawner references.
- Validate syntax in current GameMaker IDE/runtime.
- Run with low/high room speed assumptions and convert timing to seconds if project requires frame-rate independence.
- Confirm spawned hazards and projectiles are destroyed on room restart/death.
- Confirm conveyor mechanics cannot trap the player irrecoverably.
- Verify readable telegraphs for color-vision and reaction-time accessibility.
