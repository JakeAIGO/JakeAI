# MiMo V2.6 Evaluation Gate

Date: 2026-09-23

## Purpose

Add Xiaomi MiMo V2.6 to the JakeAI model-adapter layer without changing the
current production default or weakening JakeAI approval gates.

## Current state

- Existing JakeAI Direct default remains OpenAI.
- MiMo is opt-in with `DIRECT_MODEL_PROVIDER=mimo`.
- MiMo credentials remain server-side in `MIMO_API_KEY`.
- Default MiMo candidate is `mimo-v2.6-flash`; `DIRECT_MIMO_MODEL` can select
  `mimo-v2.6-pro` for controlled tests.
- Default pay-as-you-go base URL is `https://api.xiaomimimo.com/v1`; a Token
  Plan or other Xiaomi-supported endpoint can be supplied through
  `MIMO_BASE_URL`.
- The adapter uses the OpenAI-compatible Responses API.
- MiMo tool execution is deliberately disabled in this integration.

## Why tool execution is gated

Fresh public bug reports for MiMo V2.6 describe malformed structured calls,
large rotating tool-call batches, and repeat loops. Those reports are not
treated as proof of universal failure, but they are sufficient to keep MiMo
outside JakeAI's autonomous tool-execution path until our own bounded tests
pass.

## Bake-off

Run configuration-only inspection:

```bash
python model_bakeoff.py
```

Authorize bounded live API tests only after server-side credentials are set:

```bash
MIMO_API_KEY=... DIRECT_MIMO_MODEL=mimo-v2.6-flash \
python model_bakeoff.py --providers mimo --live --out mimo-flash-results.json
```

Then repeat with `mimo-v2.6-pro` and the current OpenAI Direct model. Compare:

1. task completion checks,
2. latency,
3. input/output tokens,
4. provider cost from the provider's actual bill or current published rates,
5. structured-output reliability,
6. any repeated/empty responses.

## Promotion gate

MiMo may become eligible for automatic routing only after:

- bounded text-only bake-off passes,
- provider billing is verified,
- regression tests pass,
- repeated-output and empty-output behavior are acceptable,
- a separate tool-calling harness passes with hard call-count and time limits,
- human approval is given for the production routing change.

No production provider switch is made by this change.
