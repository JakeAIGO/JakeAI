# JakeAI Media Gateway

## Decision

Creative Claw is **not a JakeAI core dependency**.

It is an optional paid adapter that may be useful for comparisons or one-off renders, but a JakeAI product must not require Creative Claw credits to function.

## Canonical architecture

**JakeAI workflow → Media Gateway → local/free engine first → QA/provenance → optional approved paid fallback**

JakeAI owns:

- prompts and generation specifications
- workflow state
- rights/license evidence
- source/reference provenance
- output hashes
- QA
- release gates
- storage/catalog metadata
- cost policy

Models and providers are replaceable adapters.

## Primary local routes

| Media | Primary route | Marginal vendor charge |
|---|---|---:|
| Book narration / DJ host | Chatterbox local | $0 |
| Original songs / synthetic singers | ACE-Step 1.5 local | $0 |
| Audio mixing / radio assembly | FFmpeg local | $0 |
| Book covers / deterministic graphics | SVG/HTML/code renderer | $0 |
| Video post / assembly | FFmpeg local | $0 |

Local compute, electricity, disk, and optional hosting still have ordinary infrastructure costs.

## Founder voice

The JakeAI founder reference is a private narration/DJ asset.

Allowed:
- book narration
- ordinary JakeAI radio DJ hosting
- JakeAI station identification

Forbidden:
- song vocals
- sexual material
- political content
- advertisements/sponsor reads
- impersonation

Songs receive independent synthetic performers appropriate to the track.

## Paid fallback rule

A paid adapter is ineligible unless all of these are true:

1. the adapter is explicitly enabled by environment/config;
2. the requesting workflow explicitly allows paid fallback;
3. a non-zero approved spend ceiling is supplied;
4. the result still passes JakeAI rights/provenance/QA gates.

This prevents a new product from silently acquiring a per-character, per-song, per-render, or per-play vendor bill.

## Existing Creative Claw CDN assets

Some already-published JakeAI pages reference Creative Claw-hosted static images. Those pages remain functional while the assets are migrated to JakeAI-controlled storage.

That is **legacy hosting debt**, not a generation/runtime dependency.

Migration is hash-and-visual-fidelity checked and URL replacement happens one asset at a time so public pages do not break.

## Commercial release

Local/open-source does not mean automatically releasable.

Every public media asset still needs:
- exact model/checkpoint license evidence
- input/reference rights
- originality/IP review appropriate to the medium
- provenance manifest
- QA
- human release approval when required

The gateway solves dependency and unit economics; it does not bypass rights or release controls.
