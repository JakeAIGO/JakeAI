# KJAI Broadcast Engine v1

Broadcast 001 Producer Mix v2 is the reference production standard.

## What passed QA

The reviewed private master established the following baseline:
- continuous radio-style DJ/music overlap instead of waiting through dead tails;
- independent loudness targets for songs and DJ;
- sustained-dead-tail trimming only (musical endings are preserved);
- founder voice used only as DJ/narrator, never as a song vocalist;
- original synthetic KJAI station stings;
- cue sheet + cryptographic provenance manifest;
- private/release-gated by default.

Reference private master measurements:
- duration: 19:55.83;
- sample rate: 48 kHz stereo;
- final peak: approximately -0.8 dBFS;
- no clipping observed.

## Default mix profile

- Music RMS target: -18 dBFS
- DJ RMS target: -17 dBFS
- Final RMS target: -17.4 dBFS
- Final peak ceiling: -0.8 dBFS
- DJ -> music overlap: 1.00 s
- Song -> DJ overlap: 0.95 s
- Closing overlap: 0.55 s
- Song tail threshold: -38 dBFS
- Preserve 0.35 s after final active song frame
- DJ edge threshold: -44 dBFS

These are engineering defaults, not creative rules. A specific program can
override them when the material requires it.

## Hard separation rules

1. Founder voice: DJ/narration only.
2. Song singers: fictional synthetic performers or cleared human recordings.
3. No Creative Claw dependency.
4. No automatic paid media fallback.
5. Generated music remains review-gated until originality/rights QA is complete.
6. Broadcast assembly remains private until explicit public release approval.
7. The engine never changes song lyrics, song audio content, or DJ wording during mixdown.

## Broadcast workflow

Artist roster -> program rotation -> song masters -> contextual DJ breaks ->
founder-voice render -> Broadcast Engine -> cue/provenance QA -> human release gate.

The intended result is a station, not a playlist.
