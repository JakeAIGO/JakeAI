# JakeAI Founder Narrator v1

This replaces the experimental Windows hotfix chain with one shared production path.

## Proven

The first local founder-voice audition successfully generated on Windows using:
- the private founder voice reference;
- Chatterbox Turbo;
- CPU generation;
- exact Wells source-word verification.

## Production differences

The production runner is resumable and works from a verified JakeAI EPUB.

It:
1. verifies the canonical source SHA-256;
2. reconstructs the entire book from EPUB section XHTML and requires an exact byte match;
3. splits sections into contiguous exact source slices;
4. verifies Chatterbox does not add/remove/substitute lexical words;
5. generates chunks deterministically;
6. saves every chunk so an interrupted run can resume;
7. builds section/chapter WAVs;
8. normalizes levels;
9. records hashes, source offsets, audio QA metadata and watermark state.

## Watermark rule

Production defaults to **fail closed** if the real Perth implicit watermarker is unavailable.

For private testing only, the Python runner supports:

`--private-unwatermarked`

Anything generated that way is marked:

`PRIVATE_UNWATERMARKED_QA_ONLY`

and is not release-eligible.

## Founder voice use

The private reference recording remains local and must never be committed.

The same voice-use restrictions apply across JakeAI:
- no advertising/sponsored reads;
- no political material;
- no sexual material;
- no impersonation of another person.

## Public release

Completing this script does not publish anything.

Audiobook release still requires:
- successful watermarking;
- complete audio QA;
- Edition Passport update;
- final human release approval.
