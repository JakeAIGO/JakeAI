# JakeAI Canonical Avatar Recovery Audit

Status: IN PROGRESS — PRODUCTION CHARACTER RENDERING REMAINS BLOCKED

## Evidence recovered

1. **Jake AI Neon Avatar Concept Board**
   - Library file: `file_000000007bf881f582761e3096b8141c`
   - The board explicitly labels a neon `J` mark as **CORE AVATAR** and says it is based on the original design.
   - This is useful identity evidence for the brand mark, but it does not by itself prove which approved protagonist master should drive character scenes.

2. **JakeAI Discord Neon Asset Pack**
   - Library file: `file_000000006c9881f5be7e0b894e204e70`
   - Contains a recurring JakeAI human character treatment across profile, emote, sticker and banner variants.
   - This is derivative-reference evidence only. It is NOT promoted to master status.

3. **JakeAI neon emblem reference**
   - Library file: `file_00000000dda881f5a98a23e848a05ca5`
   - Clean brand-mark reference suitable for UI and environmental branding.

## Decision

Do **not** guess between the emblem identity and the human-character identity.
Do **not** generate a new substitute protagonist.
Do **not** promote a derivative sheet to canonical master merely because it is visually consistent.

Until the originally approved master image is recovered, `BrandAssetGate.character_render_allowed()` must remain false.

## Safe work that may continue while blocked

- factory environment scenes
- cinematic camera choreography
- dialogue/timeline systems
- UI, lighting, VFX and world-building
- emblem-based signage and non-character branding
- placeholder character anchor nodes with no rendered substitute identity

## Promotion requirements

The master may be promoted to `APPROVED_LOCKED` only after:

1. exact approved image is recovered;
2. provenance is recorded;
3. visual comparison against approved derivative references passes;
4. a stable asset path/hash is recorded;
5. the user-approved identity is preserved without redesign.

This audit is intentionally conservative because identity continuity is a release gate, not a cosmetic preference.
