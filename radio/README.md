# KJAI 404 — Signal Found

KJAI 404 is JakeAI's dynamic in-world radio engine.

It is inspired by the *idea* of interactive game radio, but it uses original station identity, original music, original dialogue, and JakeAI's own local voice stack. It is not a GTA asset, clone, or derivative radio station.

## What makes it different

The host does not rely on a fixed library of prerecorded DJ clips.

For every transition the engine receives:

- the track that just ended;
- the track coming next;
- location/time/weather when available;
- recent game events;
- player state;
- recent DJ memory.

It creates a short break, checks recent memory for repetition, then hands that approved text to the local **JakeAI Original AI Narration** voice.

The goal is that the station sounds like an actual DJ who has been sitting there all night, not a shuffled set of canned clips.

## JakeAI humor canon

The station's comedy should feel like JakeAI:

> Treat chaos as a mildly inconvenient administrative problem.

Preferred:
- dry understatement;
- conversational observations;
- slightly absurd practicality;
- occasional self-awareness;
- humor that sounds discovered in the moment.

Avoid:
- jokes that announce themselves as jokes;
- repeated catchphrases;
- loud wackiness;
- cruelty;
- sales copy.

Example tone:

> "That track has now completed its duties with minimal paperwork."

That line is a tone example, not a mandatory recurring catchphrase.

## Founder voice hard rules

The JakeAI founder voice may host normal entertainment radio, but it must not be used for:

- advertising or sponsored reads;
- political material;
- sexual material;
- impersonating another person.

If a future game needs fictional commercials, campaign satire, adult stations, or character impersonations, those require a different authorized voice.

## Music

Production music should be either:

1. original JakeAI-generated work with commercial rights evidence; or
2. separately licensed music with documented rights.

ACE-Step 1.5 is the current local-generation candidate. The current official ACE-Step 1.5 repository and ACE-Step/Ace-Step1.5 model metadata identify the license as MIT, but generated tracks still require originality review before commercial release. Do not prompt the model to imitate a named artist.

The sample song catalog in this folder contains placeholders only. They are not release-cleared tracks.

## Runtime path

```
song out
  -> context snapshot
  -> radio break generator
  -> repetition/safety gate
  -> JakeAI Original AI Narration
  -> loudness normalization
  -> duck/fade music bed
  -> next song
  -> write memory
```

## Release state

This is an internal prototype.

- No station audio has been publicly released.
- No sample song is commercial-ready.
- No founder-voice ad copy is permitted.
- Public integration remains human approval-gated.
