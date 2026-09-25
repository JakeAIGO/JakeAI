# KJAI 404 Local Station v1

This layer turns the existing dynamic DJ brain into an actual private station audio pipeline.

## Parallel architecture

### Voice
Uses the same `jakeai_local_voice.py` adapter as JakeAI Editions.

That means books and radio share:
- the same founder voice;
- the same local Chatterbox runtime;
- the same CPU compatibility fixes;
- the same watermark/release behavior;
- no per-character TTS bill.

### Music
The current original-music candidate is **ACE-Step 1.5**.

Verified current licensing:
- official `ace-step/ACE-Step-1.5` repository: **MIT**
- official `ACE-Step/Ace-Step1.5` model metadata: **MIT**

Do not rely on a code license alone as proof that a generated song is non-infringing. Every generated track remains:

`PRIVATE_ORIGINALITY_REVIEW_REQUIRED`

until reviewed.

The prompt pack deliberately:
- uses no named artists;
- requests original compositions;
- uses no external samples;
- starts with instrumentals.

## Build original station music

Start the official ACE-Step 1.5 local REST API:

`uv run acestep-api`

Then:

`python radio/music_factory_kjai404.py --out C:\KJAI\music`

The music factory writes:
- WAV files;
- prompt;
- deterministic seed;
- model;
- SHA-256;
- license evidence;
- commercial status = false;
- originality review required.

## Assemble a private show

After there are music files and a catalog:

`python radio/local_station_runner.py --catalog C:\KJAI\music\kjai404-generated-catalog.json --voice C:\PRIVATE\founder_reference.wav --out C:\KJAI\show --context radio/demo_context.json --private-unwatermarked --allow-unreviewed-music`

The two explicit flags mean **private QA only**.

Production removes both flags after:
- working audio watermark;
- track originality review;
- rights evidence;
- final station QA.

## Station behavior

For each song transition:
1. snapshot game/session context;
2. create fresh KJAI break;
3. apply repetition and founder-voice gates;
4. synthesize the new break locally;
5. mix DJ audio into the next track;
6. save memory so future breaks do not repeat;
7. write a show manifest.

No public release is performed by this runner.
