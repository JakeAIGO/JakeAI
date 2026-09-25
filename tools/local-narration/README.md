# JakeAI Local Narrator

This is the no-per-character narration path for JakeAI Editions.

## Why it exists

Hosted voice APIs charge by character or generated audio. That conflicts with low-priced JakeAI Editions. This runner uses **Chatterbox Nano** locally instead.

- Open-source Chatterbox family by Resemble AI
- MIT licensed for commercial use
- Zero-shot voice cloning from a short private reference recording
- Chatterbox Nano is designed for CPU/on-device use
- Generated audio includes Chatterbox's PerTh AI watermark
- No voice sample is committed to this repository
- No per-character API call is made by this runner

Official project: https://github.com/resemble-ai/chatterbox

## Privacy

Never commit the founder voice sample. Keep it outside the repo or in the ignored `private/` directory.

The runner does not upload the reference recording. It passes the local WAV file directly to the locally running Chatterbox model.

## Exact-text rule

The input EPUB must contain:

- `META-INF/jakeai-fidelity.json`
- `OEBPS/source/canonical.txt`

The runner verifies the canonical SHA-256 before generation.

Every TTS chunk is a contiguous, exact UTF-8 slice of the immutable canonical source. The runner does not modernize spelling, correct punctuation, expand abbreviations, rewrite dialogue, or normalize the literary text.

Whitespace-only source slices are represented as silence rather than synthesized speech.

The resulting audiobook remains **PRIVATE_AUDIO_QA_REQUIRED** until audio QA and final human release approval are completed.

## Windows

1. Run `setup_windows.bat` once.
2. Keep the private voice reference WAV somewhere local.
3. Download a verified private JakeAI EPUB release candidate.
4. Run `run_narrator.bat`.
5. Select the EPUB, reference WAV and an output folder.

The first run downloads the open-source model weights. Later runs reuse them locally.

## Economics

Model generation is local compute. There is no per-character royalty, usage cap, or revenue share from the MIT-licensed Chatterbox model. Hardware/electricity and any optional hosting remain ordinary infrastructure costs.

This is intentionally separate from paid hosted TTS adapters, which may still be used for controlled quality comparisons but are not the default production path.
