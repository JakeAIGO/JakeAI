# JakeAI Media Gateway

Status: LOCAL-FIRST / PROVIDER-INDEPENDENT

JakeAI owns routing, policy, provenance, QA and release gates. Models and hosted services are replaceable adapters.

## Hard rules

1. Local/self-hosted first.
2. No automatic paid fallback.
3. Hosted providers may be used only when they materially improve an output and any required spend/action has explicit approval.
4. The JakeAI Founder voice remains private local input and is never uploaded by the Media Gateway.
5. Public release requires provenance, licensing/rights evidence, QA and the applicable human release gate.
6. A provider outage, pricing change, credit balance or account closure must not stop the JakeAI core product from functioning.

## Primary stack

- Book narration: local Chatterbox.
- Radio DJ: local Chatterbox.
- Original songs: local ACE-Step 1.5.
- Audio assembly: local FFmpeg / TorchAudio.
- Deterministic covers and graphics: JakeAI SVG/code renderer.
- Generative images: replaceable model adapter when needed.
- Video: replaceable renderer when quality justifies it.

## Creative Claw

Creative Claw is optional_adapter_only.

It is not the source of truth, a required runtime, the default voice engine, the default music engine, an automatic fallback, or allowed to spend credits automatically.

Legacy public assets historically hosted on Creative Claw's CDN are copied into JakeAI-owned persistent media storage. Frontends are migrated to JakeAI media URLs only after cache verification.

## Release philosophy

Generation -> provenance -> QA -> rights/license gate -> human release approval.

A successful render is never equivalent to permission to publish.
