# V8 independent-verification probe index

These are read-only, synthetic-only probes for `AUDIT/VERIFY_V8.md`. Run from the repository root with:

```sh
PYTHONPATH=.:AUDIT/probes_V8 python3 AUDIT/probes_V8/P-033.py
```

Each `P-0xx.py` uses repository engine code; matching `P-0xx.out` preserves the raw stdout from the recorded run. Where a probe ingests OHLC, `AUDIT/probes_V8/common.py` constructs a `MarketObservation` and calls `validate_market_observation` before adaptation. Object/event-only probes are identified as such in the verification report. Synthetic results are code-path evidence only, not validation against exchange/device/market data.

## Probe inventory

| IDs | Probe focus |
|---|---|
| P-001–P-010 | E03/E04 first tranche: units/continuity, dedup/replay, producer/fabric projections, memory, statistical/volatility edge cases |
| P-011–P-016 | E04 identity, correction, invalid-data boundary, parameter cache, drift and GARCH status |
| P-018–P-022 | E05 role, terminal transitions/identity/fate, correction behavior |
| P-023–P-032 | E05/E06 MTF and closed inputs; lifecycle cutoff, PIT context, confluence, breaker, identity and fabric admission |
| P-033–P-039 | E06 no-BOS timing/scan, structure join, origin-size threshold, mitigation transition; E05 inverse/merge; E03 availability fallback |

P-014 and P-017 are excluded from V8 scope. Every in-scope raw output is kept beside its probe script; the report records any probe limitations and rows still incomplete.