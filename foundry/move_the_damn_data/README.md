# Move the Damn Data™ — Reference Prototype

A fail-closed, synthetic-data reference implementation for a reusable JakeAI administrative relay.

## Contract

`event -> validate -> permission check -> approval gate -> transform -> prepare/complete -> audit`

The prototype deliberately does **not** connect to real customer systems, send messages, spend money, change pricing, delete records, or publish anything. Those capabilities belong behind explicit connector permissions and human approval gates in later integration work.

## Safety properties demonstrated

- Idempotency: a repeated event ID does not perform a second action.
- Required data is never invented; incomplete records route to human review.
- Every action requires explicit permission.
- Gated actions require explicit approval and are only marked `prepared` here.
- Unsupported actions fail closed.
- Minimal provenance/audit metadata is recorded without credentials.

## Test

From this directory:

```bash
python -m unittest -v test_engine.py
```

The test harness uses only synthetic data and the Python standard library.
