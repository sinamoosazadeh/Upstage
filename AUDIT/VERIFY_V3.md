# SESSION V3 — Independent Verification

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---:|---:|---|---|---|
| K-001 | CONFIRMED | S1 | S1 | Yes — frozen data contract/store | — | A — fail closed on hash-colliding revisions; owner-approved versioned hash migration before acceptance |
| K-002 | PENDING | S1 | — | — | — | — |
| K-003 | PENDING | S1 | — | — | — | — |
| K-004 | PENDING | S2 | — | — | — | — |
| K-005 | PENDING | S1 | — | — | — | — |
| K-006 | PENDING | S1 | — | — | — | — |
| K-007 | PENDING | S2 | — | — | — | — |
| K-008 | PENDING | S2 | — | — | — | — |
| K-009 | PENDING | S1 | — | — | — | — |
| K-010 | PENDING | S2 | — | — | — | — |
| K-011 | PENDING | S1 | — | — | — | — |
| K-012 | PENDING | S1 | — | — | — | — |
| K-013 | PENDING | S2 | — | — | — | — |
| K-014 | PENDING | S2 | — | — | — | — |
| K-015 | PENDING | S1 | — | — | — | — |
| K-016 | PENDING | S1 | — | — | — | — |
| K-017 | PENDING | S2 | — | — | — | — |
| K-018 | PENDING | S2 | — | — | — | — |
| K-019 | PENDING | S1 | — | — | — | — |
| K-020 | PENDING | S1 | — | — | — | — |
| K-021 | PENDING | S2 | — | — | — | — |
| K-022 | PENDING | S2 | — | — | — | — |
| K-023 | PENDING | S2 | — | — | — | — |
| K-024 | PENDING | S1 | — | — | — | — |
| K-025 | PENDING | S1 | — | — | — | — |
| K-026 | PENDING | S1 | — | — | — | — |
| K-027 | PENDING | S2 | — | — | — | — |
| K-028 | PENDING | S2 | — | — | — | — |
| K-029 | PENDING | S2 | — | — | — | — |
| K-030 | PENDING | S2 | — | — | — | — |
| K-031 | PENDING | S2 | — | — | — | — |
| K-032 | PENDING | S1 | — | — | — | — |
| K-033 | PENDING | S2 | — | — | — | — |
| K-034 | PENDING | S2 | — | — | — | — |
| L-001 | PENDING | S2 | — | — | — | — |
| L-002 | PENDING | S2 | — | — | — | — |
| L-003 | PENDING | S1 | — | — | — | — |
| L-004 | PENDING | S1 | — | — | — | — |
| L-005 | PENDING | S2 | — | — | — | — |
| L-006 | PENDING | S2 | — | — | — | — |
| L-007 | PENDING | S2 | — | — | — | — |
| L-008 | PENDING | S2 | — | — | — | — |
| L-009 | PENDING | S2 | — | — | — | — |
| L-010 | PENDING | S2 | — | — | — | — |
| L-011 | PENDING | S2 | — | — | — | — |
| L-012 | PENDING | S1 | — | — | — | — |
| L-013 | PENDING | S2 | — | — | — | — |
| L-014 | PENDING | S2 | — | — | — | — |
| L-015 | PENDING | S2 | — | — | — | — |
| X-V3-001 | PENDING | New | — | — | ISSUE-079 | — |

**Baseline:** `85b2c155d7b054a468379ddfd802eb239d0801f9`; source code line references are against this commit. No device database, `.env`, secrets, exchange/Telegram endpoint, order, or external service was accessed. Probes use synthetic in-memory or temporary SQLite stores only; synthetic results are not device evidence.

### K-001

#### Auditor claim (short quote)
> “`content_hash`، high/low/OI را پوشش نمی‌دهد؛ `correct_raw` آن را duplicate ingest می‌کند.” — “The hash omits high/low/OI; `correct_raw` deduplicates that correction.”

#### What I read (files, line ranges, functions, callers)
Read `MarketObservation.content_hash()` in `apex/data_catalog/contracts.py:138–150`; `SQLiteStore.ingest_raw`, `correct_raw`, and `_find_by_event` in `apex/data_catalog/store/sqlite_store.py:383–486`; and the repair comparison/apply path `_ohlcv_equal` → `repair_one` in `apex/ops/partial_bar_repair.py:355–361,365–449`. `grep -RIn --include='*.py' 'correct_raw(' apex scripts tests` found the only production caller in `partial_bar_repair.py:447` and two store-integration test callers (`tests/integration/test_store_integration.py:201,226`). The callee `ingest_raw` hashes before inserting, uses `INSERT OR IGNORE`, finds a prior row by `content_hash`, commits, and returns the old event ID on a duplicate; `correct_raw` then changes status by the same derived hash and records the returned ID as `new_event_id`.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONDONTWRITEBYTECODE=1 python3 -B AUDIT/probes_V3/store_probes.py K-001`. Probe: `AUDIT/probes_V3/store_probes.py::k001`; raw result: `AUDIT/probes_V3/K-001.json`. Using the repository `SQLiteStore.open()` migrations and `ingest_raw`/`correct_raw` on a temporary SQLite file, a high-only change 105→107 had equal content hashes. `correct_raw` returned the original event ID; the raw table remained one row with high 105; the sole market row remained high 105 but became `CORRECTED`; `raw_revision` pointed from that event ID to itself; the repository window still returned high 105. This reproduces the reported false correction in repository code. OI-only is also unrepresented: `content_hash` omits `oi`, and `_ohlcv_equal` checks OHLCV only, so the repair caller treats an OI-only change as identical rather than repairing it.

#### Verdict and reasoning
**CONFIRMED — independent severity S1** (auditor S1 retained). The source-level omission is exact, and the isolated real-store probe shows the wrong value survives while status/lineage imply a correction. S1 reflects incorrect immutable market history feeding downstream calculations, not evidence that a device record or trade was affected. The OI-only caller behavior is a distinct adjacent consequence; the concrete reproduced mutation was high-only.

#### Root cause
The frozen duplicate key is `(symbol, timeframe, timestamp, open, close, volume)`. It excludes high, low, and OI. `repair_one` detects a changed wick, but passes it to a store method whose dedupe key aliases it to the original row. `correct_raw` does not verify that the returned `new_event_id` differs from `original_event_id` before relabeling the market row and inserting revision lineage.

#### Direct impact
A high/low correction can be reported as `CORRECTED` without storing its changed value; the active market record is the old value and the revision is self-referential. OI-only differences are instead reported as verified by `_ohlcv_equal`. Neither path produces a faithful corrected observation.

#### Secondary effects and interactions (upstream/downstream)
Upstream, a provider/evidence replacement enters through `partial_bar_repair.repair_one`; downstream, the unchanged wick/OI can feed ATR, stops, FVG/structure, catalog features, producer fingerprints, replay, and training. These are code-path consequences, not measured device outcomes. No duplicate D/ISSUE owner item was found for this exact identity collision.

#### Contract and decisions
`APEX_GEN5.md:18678` defines the duplicate hash over “(symbol, timeframe, timestamp, open, close, volume)”; however, `:18692–18699` says a CLOSED object is immutable and, “If data differs,” a new corrected record/event with lineage must be appended. The exact duplicate-key clause cannot be silently broadened in frozen code, but the correction clause does not support treating a changed high/low as byte-identical. `PHASE2_DECISION_LOG.md:51` (ISSUE-CP1-012) governs status/lineage: original `SUPERSEDED`, new row `CORRECTED`, raw append-only, revision and retention audit rows. That ruling does not authorize a hash collision or self-revision; the frozen contract and decision together require refusal until representable.

#### Frozen status and non-frozen alternative
**Frozen:** `contracts.py` and `sqlite_store.py` are under frozen `apex/data_catalog/**`; do not patch them in this audit. `partial_bar_repair.py` is non-frozen. A safe non-frozen alternative is to compare every correction-bearing field, including OI, and refuse with an explicit identity-collision verdict whenever the full payload differs but `content_hash()` is unchanged. This prevents false success but deliberately does not install the correction. There is no safe non-frozen way to make the existing frozen window reader expose a new wick/OI revision.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — immediate containment:** make the repair caller reject unrepresentable high/low/OI changes and preserve a visible pending/refused report. Side effects: no identity or cache changes, but the old bar remains and repair readiness is not achieved. **B — owner-approved v2 correction identity:** revise the frozen hash/store contract only after explicit approval, with a migration/versioned identity rather than silently changing the existing key. Side effects: re-keyed raw payload hashes/manifests and dependent snapshots, input fingerprints, feature/cache identities, replay/training query hashes, and likely retraining/replay; existing event IDs can remain lineage anchors. No schema/hash change was made here.

#### My recommendation
Use A now and fail closed; require an owner decision and migration plan before B. Never return `CORRECTED` or write a self-edge when the corrected payload cannot be represented by the frozen dedupe identity.

#### Acceptance and regression tests
Add high-only, low-only, and OI-only repair cases; each must either store a distinct, fully valued revision with original `SUPERSEDED`, new `CORRECTED`, non-self `raw_revision`, and correct active window, or return the named refusal under the current frozen hash. Assert byte-identical duplicates remain no-ops and that no false `VERIFIED_CLOSED`, `CORRECTED`, or self-revision is emitted. Run fault-injection/atomicity tests separately (K-005).
