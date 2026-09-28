# SESSION V3 — Independent Verification

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---:|---:|---|---|---|
| K-001 | CONFIRMED | S1 | S1 | Yes — frozen data contract/store | — | A — fail closed on hash-colliding revisions; owner-approved versioned hash migration before acceptance |
| K-002 | CONFIRMED | S1 | S1 | Yes — frozen parser/store | ISSUE-CP1-012 (correction lifecycle only) | A — bind each revision to its recorded correction time; refuse historical reconstruction until version-aware reads exist |
| K-003 | CONFIRMED | S1 | S1 | No — producer is non-frozen; store DDL remains frozen | ISSUE-079 (cache correctness, distinct from latency) | A — fingerprint the selected PIT revision/status set and force cold rebuild on mismatch |
| K-004 | CONFIRMED | S2 | S2 | Yes — SQLiteStore is frozen; route via non-frozen guarded service pending owner approval for store guard | — | A now, B with owner approval — guard all three identity fields before correction |
| K-005 | CONFIRMED | S1 | S1 | Yes — SQLiteStore is frozen; non-frozen atomic writer is a fallback | ISSUE-076 (commit boundary) | B with owner approval; until then gate writes or route through tested atomic writer |
| K-006 | PARTIAL | S1 | S1 | Yes — core catalog/store frozen; non-frozen checked projection exists in producer | — | A — route every consumer through one lineage-checked final-observation projection |
| K-007 | CONFIRMED | S2 | S2 | Yes — purge and raw_revision DDL are in frozen SQLiteStore | — | Single safe path: preflight/hold referenced rows with explicit owner-approved archival/retention policy; never disable FK |
| K-008 | CONFIRMED | S2 | S2 | Yes — store frozen; non-frozen readers/training discovery can contain orphans | — | Single safe path: lineage-filter all non-frozen readers/discovery and refuse orphans consistently |
| K-009 | CONFIRMED | S1 | S1 | No — EngineContextProducer timeline cache is non-frozen; frozen engines unchanged | — | A — include all per-prefix MTF input identities and replay from earliest affected prefix |
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

### K-002

#### Auditor claim (short quote)
> “parser، availability کندل اصلاحی را close تاریخی می‌گذارد؛ `correct_raw` نسخهٔ فعال را جایگزین می‌کند، بی‌آنکه زمان دریافت اصلاح مبنای انتخاب باشد.” — “The parser stamps a corrected candle with its historical close time; the active version is replaced without version-time selection.”

#### What I read (files, line ranges, functions, callers)
Read `parse_kline_to_observation` (`apex/data_catalog/ingest/toobit_public.py:122–170`), its `ToobitPublicClient.get_klines` caller (`:294`) and the `ToobitKlineSource`/repair callers (`apex/ops/bootstrap_service.py`, `apex/ops/partial_bar_repair.py:389–449`); then `SQLiteStore.correct_raw` and `get_window` (`apex/data_catalog/store/sqlite_store.py:448–522`) and the full metadata/PIT path in `EngineContextProducer.window` (`apex/ops/engine_context.py:2367–2405`). `grep` found no additional production callers of the parser beyond public `get_klines` and partial-bar repair. `correct_raw` records `raw_revision.correction_timestamp`, but the historical window path does not use that timestamp to select a version.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONDONTWRITEBYTECODE=1 python3 -B AUDIT/probes_V3/store_probes.py K-002`. Probe: `store_probes.py::k002`; raw result: `AUDIT/probes_V3/K-002.json`. On a temporary DB, the real Toobit parser made both the original Jan-10 bar and a later corrected close (101→102) available at `2026-01-10T01:00:00Z`. Before correction, producer `window()` at `2026-01-10T01:05:00Z` returned 101. `correct_raw` recorded the new revision at `2026-09-28T19:14:33.044Z`; after the correction, the same historical `as_of` returned 102. No venue or device was contacted.

#### Verdict and reasoning
**CONFIRMED — independent severity S1** (auditor S1 retained). The parser maps the venue’s candle-close field to `availability_time`, and the actual correction is admitted at a point in time months before `raw_revision.correction_timestamp`. The reproduction demonstrates a historical query changing after a later correction. It proves this code path, not that a live/device correction occurred.

#### Root cause
The parser uses `close_time` as availability for each received row. `correct_raw` globally marks the prior market row `SUPERSEDED`, adds a new current row, and records a later correction timestamp; both `SQLiteStore.get_window` and `EngineContextProducer.window` read the current status rather than reconstructing the revision that was available at the queried `as_of`. The producer then trusts the corrected raw row’s historical `availability_time`.

#### Direct impact
A correction fetched/stored in September can replace a January row for a January `as_of`; the corrected close is visible before the recorded revision time. If the corrected row instead receives a later availability timestamp without a version-aware reader, the superseded original is absent from the ordinary active window and the past query may lose the bar rather than correctly recover the old version.

#### Secondary effects and interactions (upstream/downstream)
Upstream, parsed klines flow through `ToobitPublicClient.get_klines`/`ToobitKlineSource` and the repair adapter. Downstream, window consumers include the producer feature timeline, quality/MTF, replay/training, and context inputs; the direct PAPER mark/price path also needs its own version-aware reader. No executed plan/order follows from this probe. Cross-reference `ISSUE-CP1-012` only for the correction lifecycle rule (old `SUPERSEDED`, new row appended); that closure does not settle version-specific PIT availability.

#### Contract and decisions
`APEX_GEN5.md:903–930` defines `as_of` from artifact availability and says this PIT rule prevents “future corrections” from leaking into calculations; `:18692–18699` requires corrections to be appended with a new event ID and lineage rather than rewriting history. `PHASE2_DECISION_LOG.md:51` (ISSUE-CP1-012) specifies the old/new status and append-only `raw_revision`/`retention_event` trace. Precedence: the AI.4 correction event and Ch.2.3 PIT rule must both hold; the status decision is not authority to backdate the new version’s availability.

#### Frozen status and non-frozen alternative
**Frozen:** the parser/store are in `apex/data_catalog/**`. `partial_bar_repair.py`, `EngineContextProducer`, and the PAPER price adapter are non-frozen. A non-frozen service can bind a corrected version to its actual receipt/correction time and add a version-aware as-of read over `raw_observation` plus `raw_revision`; until every relevant consumer uses that reader, refuse historical queries whose required version cannot be selected. Merely stamping a late time in the parser is insufficient because the frozen `get_window` exposes only the latest non-SUPERSEDED row.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — non-frozen, fail-closed bridge:** use the recorded correction receipt time and reconstruct the version valid at the requested `as_of` in the producer/price adapters; return a named refusal if the lineage cannot identify one unambiguously. Side effects: past queries may now return the original row or a refusal rather than the latest correction; context/snapshot/cache/replay identities and training labels must be regenerated for changed version selections. **B — owner-approved store/API migration:** add an explicit version-valid-time model and migrate historical rows/readers, then retire latest-status-only reads. Side effects: frozen schema/API change requires approval; migration must preserve existing raw event IDs, revision parents, retention manifests, and recalculate dependent hashes/caches/training artifacts. No such migration was performed.

#### My recommendation
Adopt A as containment: capture the actual correction receipt, serve only the version visible at `as_of`, and refuse when the frozen latest-only store cannot provide it. Seek owner approval for B if the version-aware read must be shared by all store consumers. Do not infer receipt time from candle close.

#### Acceptance and regression tests
With original value at `t0` and correction received at `t2`, query before `t2` must return the original version and query at/after `t2` the correction; both must carry matching raw lineage and availability. Verify unchanged time/version before and after restart, future version exclusion, correction chains, and an explicit refusal for ambiguous or missing revision timestamps. Add a direct test for `SQLiteStore.get_window`/`last_closed_price`, not only the producer path.

### K-003

#### Auditor claim (short quote)
> “fingerprint ردیف‌های raw با `availability<=as_of` را می‌گیرد، نه status فعال market.” — “The fingerprint hashes raw rows available by `as_of`, not the active market status.”

#### What I read (files, line ranges, functions, callers)
Read all of `_input_fingerprint`, `prepare`, `get_bridge_context`, and `EngineContextProducer.window` (`apex/ops/engine_context.py:1775–1840,2367–2405`). `_input_fingerprint` selects `m.observation_id`, `m.raw_payload_hash`, and raw availability/OI metadata, filters only `m.symbol` and `r.availability_time<=as_of`, and omits `candle_status`; `prepare` uses fingerprint equality to reuse an exact `BRIDGE_CONTEXT` fact at `:1810–1819`. Caller trace: `scripts/run_apex.py:748–753` binds `producer.prepare` and `get_bridge_context` to `PaperPlanBridge`; `PaperPlanBridge.prepare` (`apex/ops/plan_bridge.py:530–539`) invokes the preparer; `PaperRuntime.run_cycle` (`apex/ops/paper_loop.py:1008–1029`) calls it before cells; the bridge then calls the context source. `get_bridge_context` returns the resulting `_ready` context at `engine_context.py:1829–1840`.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONDONTWRITEBYTECODE=1 python3 -B AUDIT/probes_V3/store_probes.py K-003`. Probe: `store_probes.py::k003`; raw result: `AUDIT/probes_V3/K-003.json`. On repository DDL/store code, the fingerprint before/after a correction was byte-for-byte equal. `SQLiteStore.get_window` changed to close 102; `EngineContextProducer.window` returned no bars because the active correction’s raw availability was after the historical `as_of`. I inserted a schema-valid synthetic prior evidence/context fact (not a native composed context), called the real `prepare` cache-hit path, and `get_bridge_context` reused the prior close 101. Because the model artifact is absent from this checkout, the probe supplies an in-memory synthetic artifact that passes the repository’s real `validate_classifier`; it does not call `_compose_bridge_context`, build a native plan, or establish device behavior. These bounds are recorded in the raw JSON.

#### Verdict and reasoning
**CONFIRMED — independent severity S1** (auditor S1 retained). The raw join fingerprint excludes active status/revision selection; the active store window changes while the fingerprint remains equal. The real `prepare` cache-hit branch accepted a valid exact prior context at that equal fingerprint. The context contents in the probe are synthetic, so the evidence confirms the cache mechanism and stale-reuse condition, not an end-to-end trading outcome.

#### Root cause
The fingerprint treats stored raw rows with `availability_time<=as_of` as a complete identity of the market input, but a correction mutates the market projection’s status and inserts a new version. For a late-available correction, the old raw row still satisfies the fingerprint query and the new row is excluded, while `get_window` selects the current `CORRECTED` projection and the producer then rejects it for the historical `as_of`. Therefore identical fingerprint does not imply identical selected window.

#### Direct impact
An exact `BRIDGE_CONTEXT` fact can be reused after the current market view has changed or become unavailable for that `as_of`; the probe returned the prior synthetic context while the current producer window was empty. This can make warm preparation differ from recomputation/cold replay.

#### Secondary effects and interactions (upstream/downstream)
Upstream, `correct_raw`/retention/status transitions can change the active observation. Downstream, `PaperPlanBridge` consumes `get_bridge_context`; native feature, fabric, setup, forecast, and risk projection may then rely on the cached evidence. `ISSUE-079` overlaps because it concerns this fingerprint join’s performance, but this row is the independent correctness/invalidation defect, not a latency claim. K-009 is a separate in-memory HTF feature-timeline cache. No device cache hit or plan/order was observed.

#### Contract and decisions
`APEX_GEN5.md:903–930` forbids future-correction leakage, and `:1125–1130` states that later availability invalidates evidence tied to the old snapshot and requires a new snapshot/refusal when a required timeframe becomes insufficient. `PHASE2_DECISION_LOG.md`’s ISSUE-CP14-013 (`:389–390`) says the producer must retain raw availability rather than rewrite it; that decision does not equate a stable raw-row subset with an unchanged active market selection. Precedence: PIT/revision selection and deterministic cache identity outrank reuse convenience; no decision authorizes a hit after the selected input changed.

#### Frozen status and non-frozen alternative
**Not frozen at the defect site:** `EngineContextProducer` and its fingerprint are non-frozen; the underlying store/DDL is frozen. A non-frozen fix can hash the active, as-of-selected version set (including candle status/revision identity and every field used downstream), and bypass reuse if that identity cannot be proven. No frozen schema change is necessary for this guard; the existing `raw_revision`/status metadata can be read. It should also invalidate `_timelines` when their own multi-timeframe input identity changes (separately verified by K-009).

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — producer-only identity correction:** fingerprint the exact PIT-selected market/raw versions and relevant revision/status fields, then append a new immutable context fact on mismatch. Side effects: existing exact facts remain stored but stop matching; first post-deploy preparation recomputes and may refuse if historical revisions cannot be reconstructed; context/evidence identities and replay/training outputs may change. **B — shared version-aware reader:** add a canonical as-of revision view and use its selected IDs in both fingerprint and all readers. Side effects: wider adapter/query migration, cache namespace change, and required replay/retraining for affected snapshots. B is not required to contain the current producer bug.

#### My recommendation
Implement A first: the cache key must describe the same selected input set that `window()` actually serves. Treat uncertain revision lineage as a miss followed by a named refusal, never as a hit. Track query-performance tuning under ISSUE-079 separately so an index optimization cannot mask the correctness gap.

#### Acceptance and regression tests
Persist a valid context at `as_of`, then add a later correction with availability after that `as_of`: the fingerprint must change or the selected historical input must be reconstructed identically; `prepare` must not reuse the stale fact. Assert warm and cold calls agree on both value and named refusal, status/revision changes invalidate the key, and unchanged inputs reuse the exact context. Include correction, purge, restart, and content-hash collision cases; do not use an invalid or synthetic context as proof of native plan acceptance.

### K-004

#### Auditor claim (short quote)
> “`correct_raw` تنها event_id اصل را می‌سنجد، نه برابری symbol/TF/open_time جایگزین.” — “`correct_raw` checks only the original event ID, not the replacement’s symbol/timeframe/open-time identity.”

#### What I read (files, line ranges, functions, callers)
Read `SQLiteStore.correct_raw` and `_find_by_event` (`apex/data_catalog/store/sqlite_store.py:448–494`) and `repair_one`’s caller-side identity preparation (`apex/ops/partial_bar_repair.py:389–449`). `grep -RIn --include='*.py' 'correct_raw(' apex scripts tests` found `repair_one` as the only production caller plus two integration-test calls. The repair path parses the replacement using the candidate’s symbol/timeframe and refuses a timestamp mismatch before `correct_raw`; the store method itself fetches the original by event ID, marks it superseded, and ingests the supplied observation without comparing symbol, timeframe, or open time.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONDONTWRITEBYTECODE=1 python3 -B AUDIT/probes_V3/store_probes.py K-004`. Probe: `store_probes.py::k004`; raw result: `AUDIT/probes_V3/K-004.json`. On a temporary SQLite database opened/migrated by `SQLiteStore`, I passed a BTCUSDT original and an ETHUSDT replacement with the same open time to the actual `correct_raw`. It returned a distinct new event; the BTC row became `SUPERSEDED`, the ETH row became `CORRECTED`, and `raw_revision` linked the BTC event ID to the ETH event ID. This proves the direct API behavior. It does not establish that the currently inspected `repair_one` production caller can generate that cross-symbol payload.

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). The store-level API accepts and persists a cross-cell revision. Severity is limited because the current repair caller supplies symbol/timeframe from the candidate and checks the open-time value before calling; no real caller-induced cross-cell event or device data was observed.

#### Root cause
`correct_raw` treats `original_event_id` as sufficient identity. `_find_by_event` returns the original observation ID but `correct_raw` does not compare the corrected record’s `(symbol, timeframe, timestamp)` with that original before the status update and append.

#### Direct impact
A direct or future caller can mark BTC superseded while adding an ETH row as its “correction”; the lineage then says ETH replaces BTC, and no BTC replacement remains active. The caller’s current safeguards reduce the known production exposure but do not make the store API safe.

#### Secondary effects and interactions (upstream/downstream)
Upstream, the current `repair_one` constructs replacement identity from the candidate and venue request, so the reproduced cross-cell path is an API misuse/future-caller risk. Downstream, a cross-cell revision can corrupt per-symbol/timeframe windows, lineage, quality, features, training, and any correction consumer. Cross-reference `ISSUE-CP1-012` only for lifecycle/status behavior; it does not specify or enforce cross-cell identity. No D/ISSUE owner item was found that closes this boundary validation.

#### Contract and decisions
`APEX_GEN5.md:18692–18699` says a correction marks “the original record” superseded and creates the new record “with the corrected values” and parent lineage to that original; it does not expressly spell out the equality predicate, so I do not claim a separate written symbol/time equality clause. `PHASE2_DECISION_LOG.md:51` (ISSUE-CP1-012) governs append-only correction status and lineage. Precedence: the row establishes an unsafe API seam; the current guarded repair caller narrows occurrence, but neither text authorizes using a different market cell as the correction.

#### Frozen status and non-frozen alternative
**Frozen:** `SQLiteStore` is in frozen `apex/data_catalog/**`. `partial_bar_repair.py` and `bootstrap_service.py` are non-frozen. A safe non-frozen alternative is one audited correction service that loads the original identity, validates all three identity fields before write, and is the only allowed production entry point; call-site checks can prevent new direct writes. This cannot change or fully harden the frozen public store method, so direct API callers must remain explicitly unsupported/refused by policy until owner approval.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — route and guard non-frozen callers:** require exact symbol/timeframe/open-time equality before calling the frozen method and add a repository call-site/lint test. Side effects: no content hashes or caches change; invalid cross-cell candidates remain unapplied and must be ingested/reconciled as separate observations. **B — owner-approved frozen API invariant:** validate replacement identity inside `correct_raw` before any write. Side effects: API callers that relied on cross-cell misuse will now fail; no schema/hash migration is needed, but any already-written cross-cell revisions require a separate audit/recovery rather than silent rewriting.

#### My recommendation
Use A immediately and seek approval for B so the invariant sits at the store boundary. A correction must never be a migration between symbols, timeframes, or candle opens; ingest such data as its own observation.

#### Acceptance and regression tests
For each identity field, mutate only symbol, timeframe, then timestamp in separate direct `correct_raw` tests; each must refuse before changing either market row or inserting raw/revision data. The current repair caller with exact candidate identity must still succeed. Add a persisted-state assertion that the old row is unchanged on refusal, and a call-site test ensuring production code uses the guarded service.

### K-005

#### Auditor claim (short quote)
> “`correct_raw` قبل از درج `raw_revision` داخل `ingest_raw` commit می‌کند؛ … اصل SUPERSEDED و جایگزین CLOSED ماندند، اما revision و audit ساخته نشدند.” — “`correct_raw` commits inside `ingest_raw` before inserting `raw_revision`; … the original remained SUPERSEDED and the replacement CLOSED, with no revision or audit row.”

#### What I read (files, line ranges, functions, callers)
Read the full `correct_raw`, `ingest_raw`, `_find_by_event`, and relevant transaction/commit paths (`apex/data_catalog/store/sqlite_store.py:392–494`). `correct_raw` marks the original superseded, calls `ingest_raw` (`:461`), then marks the new market row corrected, inserts `raw_revision`, inserts `retention_event`, and calls `commit` (`:463–479`). `ingest_raw` commits its raw/market insert before returning. `grep -RIn --include='*.py' 'correct_raw(' apex scripts tests` confirms `partial_bar_repair.repair_one` is the only production caller; the other calls are integration tests. That repair awaits the public method directly and does not wrap its internal commits.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONDONTWRITEBYTECODE=1 python3 -B AUDIT/probes_V3/store_probes.py K-005`. Probe: `store_probes.py::k005`; raw result: `AUDIT/probes_V3/K-005.json`. On temporary repository DDL, I installed a test-only SQLite trigger that aborts insertion into `raw_revision`, called the real `correct_raw`, caught the injected `IntegrityError`, and rolled back the remaining transaction. The original market row persisted as `SUPERSEDED`; a second raw row and market row persisted as `CLOSED`; `raw_revision` count and correction `retention_event` count were both zero. The trigger was isolated to the temporary probe database; this is not a device fault or device-data result.

#### Verdict and reasoning
**CONFIRMED — independent severity S1** (auditor S1 retained). A failure after `ingest_raw`’s inner commit leaves a durable partial correction even when the caller rolls back. The exact injected failure point demonstrates the code’s transaction boundary; one probe does not estimate hardware/power-loss probability.

#### Root cause
The method spans several logically coupled rows but delegates to `ingest_raw`, which commits the shared SQLite connection before the revision and retention records are inserted. A later rollback cannot undo that commit, and the old supersede update was included in it.

#### Direct impact
A failed correction can leave no active original, an unclassified `CLOSED` replacement, and no lineage/audit record. Retry, recovery, and the active market projection can then disagree about whether correction completed.

#### Secondary effects and interactions (upstream/downstream)
Upstream, partial-bar repair can trigger this path; failures propagate through the caller but cannot reverse the nested commit. Downstream, PIT reconstruction, revision lookup, cache keys, quality/feature consumers, and retention/audit reconciliation see incomplete history. `ISSUE-076` overlaps only on inner/per-row commit boundaries; this finding concerns atomicity of one correction across raw, market, revision, and retention state, not replay throughput. `ISSUE-CP1-012` owns the expected status/lineage semantics but does not make these writes atomic. No concurrent-device or filesystem failure was run.

#### Contract and decisions
`APEX_GEN5.md:18692–18699` requires append correction, original `SUPERSEDED`, new event, parent lineage, and retained history; `:18725–18730` makes the raw store append-only and revision-bearing. `PHASE2_DECISION_LOG.md:51` (ISSUE-CP1-012) records the chosen status/lineage mapping. The text does not explicitly prescribe a SQLite `BEGIN/COMMIT` boundary; the independent finding is that a mid-operation error leaves a state inconsistent with that correction model, not a claim that a specific SQL primitive is named as normative.

#### Frozen status and non-frozen alternative
**Frozen:** `SQLiteStore` is in frozen `apex/data_catalog/**`; `partial_bar_repair.py` is non-frozen. Without changing frozen code, route production corrections through a new non-frozen atomic writer that uses a single explicit transaction and avoids calling the commit-owning `ingest_raw`/`correct_raw` methods. This duplicates or factors frozen serialization/DDL assumptions and must be guarded by schema-compatibility and parity tests. Caller-level rollback alone is not an alternative because the inner commit is already durable.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — non-frozen transaction-owning correction service:** validate and prepare the canonical event, then write raw observation, market projection, revision, and retention audit under one `BEGIN IMMEDIATE`/commit, rolling all back on any error; route all production writes through it. Side effects: duplicates store internals, holds the writer lock longer, requires idempotent retry rules, and must exactly preserve event/hash/lineage semantics (including K-001/K-004 constraints). **B — owner-approved store correction transaction:** refactor the frozen method so nested ingestion does not commit and the entire correction owns one transaction. Side effects: frozen implementation change and explicit migration/parity approval; existing partial corrections need a reconciliation report, not automatic rewrite.

#### My recommendation
Do not retry/continue from a failed correction as though it were atomic. Seek owner approval for B; until then, block the production correction path or route it only through a fully tested atomic writer A, with startup reconciliation for existing split states.

#### Acceptance and regression tests
Inject failure after each write boundary (original status, raw insert, market insert, new status, revision, retention event, final commit). After each failure, assert the durable database contains either the exact pre-state or the complete corrected state—never a partial mix. Verify rollback under WAL, restart/reopen, concurrent reader behavior, idempotent retry, and retention/revision consistency; keep a test that proves `ingest_raw` remains atomic for its own single-observation contract.

### K-006

#### Auditor claim (short quote)
> “`get_window` بار CORRECTED نهایی را برمی‌گرداند و `closed_engine_window` آن را می‌پذیرد؛ اما کیفیت PAPER و plan bridge فقط CLOSED را قبول می‌کنند… guard فیچر وضعیت CORRECTED را CANDIDATE می‌نامد، ولی `CatalogStatus` آن را ندارد.” — “`get_window` returns a final CORRECTED bar and `closed_engine_window` accepts it; but PAPER quality and the plan bridge accept only CLOSED… the feature guard calls CORRECTED CANDIDATE, but `CatalogStatus` has no such value.”

#### What I read (files, line ranges, functions, callers)
Read the store’s final-row selection (`apex/data_catalog/store/sqlite_store.py:497–522`), `closed_engine_window` and its native callers (`apex/ops/engine_context.py:1270–1283,1408–1425`), `PaperRuntime._stage_ingest/_stage_quality` (`apex/ops/paper_loop.py:479–498`), `PaperPlanBridge._window` (`apex/ops/plan_bridge.py:592–612`), `adv_base_volume` and its `EngineContextProducer.adv_input` caller (`engine_context.py:168–196,2142–2161`), the `_guard` and ATOM feature (`apex/data_catalog/atomic/features.py:41–57,68–75`), `Catalog.get` (`apex/data_catalog/catalog.py:291–381`), and `CatalogStatus` (`apex/data_catalog/contracts.py:57–64`). `grep -RIn` found the native producer intentionally normalizes final CORRECTED rows to CLOSED before engine computation; the raw store itself retains CORRECTED. The direct bridge-store fallback does not use that projection.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONDONTWRITEBYTECODE=1 python3 -B AUDIT/probes_V3/store_probes.py K-006`. Probe: `store_probes.py::k006`; raw result: `AUDIT/probes_V3/K-006.json`. Using 720 synthetic 1h rows and a real `correct_raw` correction in an isolated SQLiteStore, the actual `PaperRuntime._stage_ingest` returned a 300-row window and `_stage_quality` refused with `DATA_QUALITY_QX`; direct `PaperPlanBridge._window` over the store refused with the same reason. The real `closed_engine_window` projected the stored CORRECTED row to in-memory CLOSED, and the bridge accepted that producer-style window—so the bridge claim is conditional, not universal. A real `Catalog(provider=store).get("body_ratio", …)` raised `ValueError: 'CANDIDATE' is not a valid CatalogStatus`. With identity-bound synthetic public venue facts and 720 1h rows, real `EngineContextProducer.adv_input` refused `ADV_UNAVAILABLE: duplicate/nonclosed/non-PIT 1h volume`; the actual `adv_base_volume` all-CLOSED control returned 24.0. No network, owner device data, native engine bundle, order, or real venue fact was used.

#### Verdict and reasoning
**PARTIAL — independent severity S1** (auditor S1 retained). The core cross-consumer status mismatch and the PaperRuntime refusal, Catalog exception, ADV refusal, and direct-store bridge refusal reproduce. However, the auditor’s blanket implication that the plan bridge always rejects a corrected bar is overstated: the normal EngineContextProducer path explicitly maps a verified current CORRECTED row to an in-memory CLOSED engine row, which the bridge accepts. The main PAPER scheduler still encounters the raw corrected status at its quality stage before that path can proceed.

#### Root cause
The persisted market projection uses `CORRECTED` as an accepted final revision status, but multiple consumers define finality as exactly `CLOSED`. The ATOM feature guard maps every non-CLOSED row—including final CORRECTED—to `CANDIDATE`; `Catalog.get` then tries to construct a `CatalogStatus` from that string, although `CatalogStatus` only defines OK/MISSING/STALE/UNAVAILABLE/INVALID. Other paths inconsistently normalize: `closed_engine_window` accepts CORRECTED, while PaperRuntime, direct PlanBridge window retrieval, `adv_base_volume`, and `paper_close_marks` require CLOSED.

#### Direct impact
A normal current correction can stop the PAPER cell at `_stage_quality`; a direct catalog feature request can raise instead of returning a typed result; and one CORRECTED 1h observation in the complete 30-day ADV range produces `ADV_UNAVAILABLE` until it leaves that range (assuming the remaining data/provenance stays valid). The producer→bridge path itself can accept it after explicit in-memory normalization.

#### Secondary effects and interactions (upstream/downstream)
Upstream, `correct_raw` retains the CORRECTED market status and revision lineage; that is intentional. Downstream, paper marks also enforce CLOSED in `paper_close_marks`; MTF/engine code using `closed_engine_window` accepts after projection; Catalog and consumers bypassing that projection diverge. `K-001`/`K-002` are separate content-hash/PIT defects and do not reconcile the status vocabulary. The implementation is fail-closed at some call sites and raises an untyped `ValueError` at Catalog; no live trade or order effect was observed. No listed D/ISSUE owner item overlaps this status-boundary defect.

#### Contract and decisions
`APEX_GEN5.md:18669` enumerates canonical candle statuses OPEN/PARTIAL/CLOSED; `:18692–18699` requires corrections to append a new version and retain lineage, and `:18302` states CLOSED-candle PIT consumption with append-only corrections. `PHASE2_DECISION_LOG.md:51` (ISSUE-CP1-012) explicitly records the implementation decision: original market row SUPERSEDED, corrected row CORRECTED, raw append-only, lineage in `raw_revision` and `retention_event`. `EngineContextProducer.closed_engine_window` documents CORRECTED as a final observation at its reader boundary. Precedence: preserve the persisted CORRECTED identity and lineage; each consumer must either validate and project that final version to a closed input or return a typed refusal. Do not relabel the stored row or accept PARTIAL/OPEN as final.

#### Frozen status and non-frozen alternative
**Frozen:** `apex/data_catalog/**` (store, feature guard, catalog, and enums) is frozen. The producer, PaperRuntime, and plan bridge adapters are non-frozen. A non-frozen `FinalObservationProvider` can validate active status, raw/revision binding, PIT availability, and lineage; return a copied CLOSED projection for consumers while retaining original status and IDs in provenance. Route `PaperRuntime` quality/mark checks, producer ADV reads, direct bridge fallback, and the frozen Catalog’s provider through that same adapter. This avoids changing DDL and frozen enums; catalog consumers must keep the correction lineage outside the temporary CLOSED view.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — non-frozen finality adapter and consistent routing:** reuse one checked projection at every non-frozen boundary and wrap the Catalog provider so feature guards see CLOSED only after the correction is proven final. Side effects: changes which corrected rows reach PAPER/ADV/features, requires new producer/catalog code version and replay/training/evidence regeneration for affected snapshots; hashes/cache identities may change, and stored correction lineage must remain in sidecar provenance. **B — owner-approved frozen contract update:** extend the frozen candle/feature/catalog status handling to represent final CORRECTED without the invalid CANDIDATE→CatalogStatus conversion. Side effects: changes frozen API/contract semantics and compatibility expectations for callers; requires a coordinated release and full regression of all status transitions. Do not globally add `CANDIDATE` to `CatalogStatus` as a substitute for defining final correction semantics.

#### My recommendation
Implement A first as a fail-closed, lineage-checked reader adapter, and normalize only the in-memory consumer view. Retain raw `CORRECTED` and `SUPERSEDED` states, correction hashes, and parent IDs in audit/provenance. Seek owner approval before changing any frozen status enum or store contract.

#### Acceptance and regression tests
With a valid same-cell correction, assert the store retains CORRECTED and its revision/retention lineage; PaperRuntime quality, paper marks, producer ADV, producer-backed and direct bridge paths, and `Catalog.get("body_ratio")` all return a consistent typed acceptance/result after the checked projection. The 720-hour ADV window must accept the final correction when otherwise complete, and cease to depend on it after the rolling window expires. PARTIAL/OPEN, SUPERSEDED originals, future availability, missing lineage, and invalid correction identity must remain refused; Catalog must never leak a `ValueError` for a producer-controlled status.

### K-007

#### Auditor claim (short quote)
> “`raw_revision` به هر دو raw event FK دارد؛ correction قدیمی‌تر از ۱۲ ماه باعث `FOREIGN KEY constraint failed` در `retention_purge` شد و دو raw+revision ماندند.” — “`raw_revision` has foreign keys to both raw events; a correction older than 12 months caused `FOREIGN KEY constraint failed` in `retention_purge`, leaving both raw rows and the revision.”

#### What I read (files, line ranges, functions, callers)
Read the full `raw_revision` DDL (`apex/data_catalog/store/sqlite_store.py:246–256`), connection PRAGMAs at `:342–350`, `correct_raw` at `:448–479`, and `retention_purge` at `:627–660`. Both `original_event_id` and `new_event_id` are immediate SQLite foreign keys to `raw_observation(event_id)` with no `ON DELETE` action. Purge selects all raw rows whose `as_of` is older than `datetime('now','-12 months')`, then deletes one by one. `grep -RIn 'retention_purge('` found the store method and the store integration test; no separate production caller is present in this checkout. `apex/ops/partial_bar_repair.py:52–55` says both old rows share `as_of` and are purged together, but it does not account for the revision foreign keys.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONDONTWRITEBYTECODE=1 python3 -B AUDIT/probes_V3/store_probes.py K-007`. Probe: `store_probes.py::k007`; raw result: `AUDIT/probes_V3/K-007.json`. In a temporary repository SQLiteStore with `PRAGMA foreign_keys=1`, I wrote an old BTCUSDT observation and a same-cell correction with `as_of=2024-01-15T00:00:00.000Z`, verified `raw_revision` linked both IDs, then called the real `retention_purge`. It raised `IntegrityError: FOREIGN KEY constraint failed`; both raw rows and the revision remained, no PURGE_RAW event was added, the pre-existing CORRECTION audit remained, and the purge gate row was cleaned up. This is synthetic old data on repository DDL, not a device purge run.

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). The documented retention operation cannot delete a referenced correction pair with the installed foreign keys. The method repeatedly selects the same old events and raises; the pair’s age, not a test trigger, caused the failure.

#### Root cause
The physical foreign key graph forbids deleting either raw event while the immutable `raw_revision` row points to it, while purge attempts to delete raw events without archiving, detaching, or otherwise resolving revision references. Deleting both endpoints in sequence does not help under immediate FK checks; the first delete is rejected.

#### Direct impact
The corrected raw pair and its revision cannot be purged after the 12-month cutoff. Repeated calls fail, leaving the pair and its linked correction audit in place. The probe did not include unrelated old rows, so it does not assess whether a mixed batch might have additional partial-purge effects.

#### Secondary effects and interactions (upstream/downstream)
Upstream, `correct_raw` creates exactly the two references that block this delete. Downstream, repeated retention failure can grow the raw database beyond the target and makes retention status/reporting unreliable; preserving the pair does retain useful lineage, but the current method returns an exception rather than a typed legal hold. K-008 is a distinct orphan defect for unreferenced raw rows that do purge. No owner D/ISSUE item in the scoped overlap list resolves this retention/lineage policy.

#### Contract and decisions
`APEX_GEN5.md:18725–18735` says the AI.5 store is append-only, stores revisions/manifests, and sets raw retention to 12 rolling months; `:18692–18699` requires correction history and parent lineage. `PHASE2_DECISION_LOG.md:51` (ISSUE-CP1-012) specifies the append-only correction status/lineage but not purge ordering or archived-reference behavior. There is a real contract collision: both the retention limit and preserved revision lineage are binding, but no stated exception or archival mechanism reconciles them. Do not interpret FK failure as permission to disable constraints or delete lineage.

#### Frozen status and non-frozen alternative
**Frozen:** `SQLiteStore`, `raw_revision` DDL, and the purge method are in frozen `apex/data_catalog/**`. A non-frozen retention runner can preflight aged rows with references and fail/hold them explicitly, report IDs and storage growth, and avoid presenting the run as successful. This is safe containment only, not a way to meet the 12-month purge target. No non-frozen SQL ordering can delete referenced raw rows while preserving the current FK and revision row; an owner-approved archival/schema policy is needed.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**Single safe path:** obtain an owner decision on how the revision record remains auditable after its raw endpoints reach retention age, then implement that policy in the frozen store/DDL under explicit approval. Candidate designs include an immutable external archive/manifest with verifiable retrieval and an approved reference transition, or an explicit retention hold for linked raw rows; neither is currently authorized by the reviewed text. Side effects differ materially: archive/reference migration changes replay availability and FK/schema semantics, while a hold exceeds the 12-month raw-retention target and increases storage. Until the owner decides, keep foreign keys enabled and report/refuse the blocked purge.

#### My recommendation
Treat referenced corrections as an explicit legal hold and stop the retention job with a named, actionable report; ask the owner to reconcile AI.5 retention against correction-history preservation. Do not silently delete `raw_revision`, disable foreign keys, or claim the pair was purged.

#### Acceptance and regression tests
With FK enabled, test single corrections and multi-step correction chains across and inside the cutoff. The approved behavior must atomically either (1) archive and verify every endpoint/revision/audit before purging under a documented reference policy, or (2) refuse with exact held event IDs and a durable audit. Re-running must be deterministic; no partial deletion, dangling reference, hidden hold, or false-success count is allowed.

### K-008

#### Auditor claim (short quote)
> “raw قدیمیِ بدون revision در purge حذف می‌شود ولی `market_observation` فعال می‌ماند؛ `get_window` هنوز بار را برمی‌گرداند اما join هویت raw در producer صفر ردیف داشت و به `RAW_LINEAGE_INVALID` می‌رسد. cell discovery آموزش market orphan را می‌شمارد.” — “An old raw row without a revision is purged while `market_observation` remains active; `get_window` still returns the bar but the producer’s raw-identity join returns no row and raises `RAW_LINEAGE_INVALID`. Training cell discovery counts the market orphan.”

#### What I read (files, line ranges, functions, callers)
Read `retention_purge` and `get_window` (`apex/data_catalog/store/sqlite_store.py:497–522,627–660`), `EngineContextProducer.window`’s raw identity join and checks (`apex/ops/engine_context.py:2367–2406`), `CELL_QUERY` (`:1713–1727`), and `train_classifier` (`:3111–3160`). The market query includes `CLOSED`/`CORRECTED` rows but does not require a raw row. The training loop obtains its cell count from this market-only query and calls the producer with that count; the producer raises on missing lineage before feature generation. `PaperRuntime._stage_ingest` also calls the legacy store window directly (`apex/ops/paper_loop.py:479–486`), so that path initially sees the orphan rather than a lineage-checked refusal.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONDONTWRITEBYTECODE=1 python3 -B AUDIT/probes_V3/store_probes.py K-008`. Probe: `store_probes.py::k008`; raw result: `AUDIT/probes_V3/K-008.json`. In a temporary store I ingested one old, uncorrected BTCUSDT row and ran the actual `retention_purge`; it deleted the raw row and wrote `PURGE_RAW`. Afterward `raw_observation` count was 0, `market_observation` count was 1, and `SQLiteStore.get_window` returned one CLOSED row. The actual producer join refused with `RAW_LINEAGE_INVALID: observation/raw content binding missing`. Executing the repository’s actual `CELL_QUERY` returned the market-only cell with count 1. This is synthetic SQLite evidence; the training loop itself was not run.

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). The physical delete leaves an active market projection with no immutable raw support. The legacy window and training discovery see it, while the lineage-aware producer rejects it. No trained artifact or device store was used.

#### Root cause
The purge deletes from `raw_observation` only and has no corresponding market-projection cleanup/tombstone. `market_observation` has no FK to raw `observation_id`; `get_window` reads it independently. Conversely, the producer requires an `observation_id`/raw content binding and detects the missing raw row. Training discovery is also driven from `market_observation` alone.

#### Direct impact
After the retention cutoff, different readers disagree: the store window exposes a CLOSED bar, but the producer refuses it. A training run counts the cell as nonempty and then fails at `producer.window` (that exception is not caught in the loop shown); it does not silently train on the orphan in this path. Any consumer that bypasses the lineage-aware producer can still use the stale market row.

#### Secondary effects and interactions (upstream/downstream)
Upstream, retention is the trigger for unreferenced raw observations; unlike K-007 there is no revision FK blocking deletion. Downstream, paper ingestion and catalog/legacy readers may see a row whose authoritative raw evidence is gone; producer, cache, or trainer can refuse or terminate on the same cell. `CELL_QUERY` changes would change the training protocol identity (`TRAINING_QUERY` contains the query), invalidating cell cache/artifact assumptions. No replay/training completion or device data was observed.

#### Contract and decisions
`APEX_GEN5.md:18725–18735` governs the raw store and 12-month rolling raw retention; `:18302` defines PIT consumption and append-only corrections, and Ch.5 requires catalog-mediated reading. The reviewed contract does not specify retention behavior for the denormalized `market_observation` projection or a tombstone/archive rule. No PHASE2 ruling found in the relevant passages authorizes serving an active projection after its raw identity has been purged. Precedence: a consumer requiring raw lineage must refuse an orphan; a legacy reader must not present one as a verified authoritative candle.

#### Frozen status and non-frozen alternative
**Frozen:** `SQLiteStore.retention_purge/get_window` and their DDL are in frozen `apex/data_catalog/**`. Non-frozen consumers can use a shared lineage-checked provider; make `PaperRuntime`, Catalog provider wiring, and training discovery consult raw existence/content binding before admitting a market row. Training discovery can use an `EXISTS` join and preserve the matching input in `TRAINING_QUERY`. This prevents an orphan from being consumed or counted but does not remove the orphan from the frozen store; the physical projection-retention mismatch still needs owner approval.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — non-frozen containment:** filter rawless rows from all consumers and training discovery, and return a named lineage-retention refusal to direct readers. Side effects: the training SQL/query hash changes, invalidating existing per-cell cache and model artifacts; orphan cells disappear from effective coverage and must be reported. **B — owner-approved physical retention fix:** atomically delete/archive both the raw source and market projection (plus any dependent quality/feature rows) or retain a tombstone that makes the projection explicitly unavailable. Side effects: frozen schema/retention behavior changes, dependent foreign keys and audit semantics need migration, and any old snapshots/artifacts relying on the rows may become unreconstructable. No safe deletion workaround is established in this probe.

#### My recommendation
Apply A as a fail-closed consumer guard and request an owner decision for B. Do not silently repair an orphan by reconstructing raw fields from `market_observation`; the store’s own lineage contract says that projection is not a replacement for the immutable raw event.

#### Acceptance and regression tests
Purge one unreferenced old raw row and assert every read path either returns a lineage-valid row or the same named refusal; no PaperRuntime/catalog path may expose it as verified. Training discovery must not count it, and `CELL_QUERY`/protocol hash/cache invalidation must be explicit. Also test a retained/revision-linked row (K-007), cutoff boundary, restart, and old market rows with missing/wrong raw hashes; preserve a durable report of coverage excluded by retention.

### K-009

#### Auditor claim (short quote)
> “با تغییر HTF و پایهٔ ثابت، context دوباره ساخته می‌شود اما timeline همان `last_item` و state قبلی را می‌دهد؛ H4 از ۰٫۲۵ به −۰٫۸۵ عوض شد و خروجی گرم ۰٫۲۵ ماند.” — “With an HTF change and fixed base timeframe, context is rebuilt but the timeline returns the same `last_item` and prior state; H4 changed from 0.25 to −0.85 while the warm result remained 0.25.”

#### What I read (files, line ranges, functions, callers)
Read `EngineContextProducer.__init__` and `_timelines` (`apex/ops/engine_context.py:1773–1775`), `_frame_at` (`:2421–2442`), all of `feature_timeline` (`:2444–2549`), its runtime caller `prepare_engine_bundle` (`:2283–2318`), and `_compose_bridge_context` (`:1843–1856`). Runtime invokes `feature_timeline(..., incremental=True)`; the training call at `:3212` defaults to `incremental=False`, so I do not claim this exact cache hit was a completed training run. The cache is keyed only by `(symbol,timeframe)` and stores the base-window signatures plus history/μ/Σ/ATR/volatility state and `last_item`; equality tests only the supplied base-window signature prefix at `:2461–2470`, not the `_frame_at` dependencies or `dep_rows`. The H4/H1/M15 biases are read later at `:2507–2515`.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONDONTWRITEBYTECODE=1 python3 -B AUDIT/probes_V3/store_probes.py K-009`. Probe: `store_probes.py::k009`; raw result: `AUDIT/probes_V3/K-009.json`. The probe created 51 base 1h rows, 80 H4 rows, and 60 M15 rows in a temporary repository SQLiteStore. It ran the real async `feature_timeline` and real store/raw-lineage/window/correction methods. To isolate invalidation from native model correctness, it replaced `upstream_frame`, structure/confirmation, and E11 state-vector helpers in-process with deterministic synthetic functions; the H4 bias was derived from the actual last H4 close. Initial bias/trendiness were `0.25`/`1.0`. I then appended an available-by-`as_of` H4 correction, leaving all 51 base signatures unchanged. Warm incremental output reused the identical `last_item` and still reported H4 `0.25`, trendiness `1.0`; a fresh producer running the same real timeline function returned H4 `-0.85`, trendiness `0.0`. No native engine result, training artifact, or device evidence is claimed.

#### Verdict and reasoning
**CONFIRMED — independent severity S1** (auditor S1 retained). The same base prefix, `as_of`, and code path produced warm and cold outputs that differ solely because an HTF revision changed. The test exercises the cache logic and real SQLite dependency reader; its synthetic engine functions limit conclusions to invalidation, not native indicator arithmetic or plan impact.

#### Root cause
The incremental timeline cache treats equality of base `MarketObservation` signatures as equality of the complete feature input. It stores no per-prefix H4/H1/M15 selected observation IDs, raw hashes, availability frontier, or dependency state. When all base signatures still match, `start == len(window)` returns the old `last_item` without re-reading dependencies, even though `_frame_at` would produce a different H4 state on a cold call.

#### Direct impact
A corrected HTF candle can leave a warm runtime timeline with stale bias, trendiness, and E11 normalization state while a cold recomputation sees the new revision. The probe showed `H4 bias=0.25` and `trendiness_raw=1.0` warm versus `−0.85` and `0.0` cold. This violates deterministic warm/cold parity for identical current store state.

#### Secondary effects and interactions (upstream/downstream)
Upstream, any required HTF version, availability, quality, or dependency row can change while the base prefix is unchanged. Downstream, `prepare_engine_bundle` uses the cached feature timeline for native evidence; stale bias affects E11 inputs/state and can flow into MTF/context, evidence, setup, forecast, and bridge projections. Runtime `prepare_engine_bundle` is incremental; training’s current call uses the cold default, so warm/cold training corruption was not observed. K-003 is a separate persisted BRIDGE_CONTEXT fingerprint defect; neither fix substitutes for the other. No real native plan or order was built.

#### Contract and decisions
`APEX_GEN5.md:943–960` requires all decision-relevant timeframe states to come from one `SnapshotBarrier` and one `as_of`; each TF tracks its own source snapshot, lookback, regime scope, and expiry/freshness, and a missing/insufficient required TF must downgrade or refuse. `:1110–1116` requires parent lineage back to raw to remain reconstructible. `PHASE2_DECISION_LOG.md:1046,1055,1060` records binding D35: a cell whose inputs changed is recomputed; the consumed-row hash includes cell bars plus prefetched HTF rows; any input mismatch means recompute, never partial reuse, and speedups require exact-parity tests. That D35 cache rule is specifically for training artifacts; I apply its input-identity/parity principle to this shared feature stream without claiming the probe exercised D35 cell-cache serialization. Precedence: a base-only warm hit cannot override a changed required timeframe under the shared PIT/MTF contract.

#### Frozen status and non-frozen alternative
**Not frozen at the defect site:** the incremental cache and producer are in non-frozen `apex/ops/engine_context.py`; no engine formula or frozen `apex/engines/**` code needs to change. The producer can key each prefix by the full consumed dependency signature or bypass the warm path whenever dependency identity is unavailable.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — dependency-aware incremental replay:** record, for every emitted base prefix, the exact PIT-selected input identity of each required timeframe (raw event/observation ID, content hash, availability, quality snapshot, timeframe, and relevant package/model versions). On mismatch, find the earliest affected prefix and replay all subsequent state; if exact invalidation boundaries are unavailable, clear the cell timeline and cold-recompute. Side effects: more signatures and storage in memory, more HTF reads/hash work, and reprocessing latency; downstream E11/evidence identities and snapshot/context outputs may change, so affected training/replay/cache artifacts must be regenerated and checked for identity collisions. **B — disable incremental reuse for multi-timeframe contexts:** cold-recompute every affected cell until a proven dependency signature is available. Side effects: increased runtime latency/CPU but simplest correctness fallback; no store migration.

#### My recommendation
Implement A with B as the fail-closed fallback. Invalidation must include selected raw revision and availability, not just OHLC values or the outer context fingerprint; replay state from the first changed dependency rather than replacing only the final bias.

#### Acceptance and regression tests
With an unchanged base window, correct each required HTF separately (H4, H1, M15) and assert warm incremental output equals a fresh cold producer at the same `as_of` for bias, trendiness, E11 vector, and downstream evidence. Also test newly available/deleted/missing HTF rows, availability-only changes, quality revision, a correction before and after the current prefix, and a changed base candle. Prove no stale cached `last_item`, history, μ/Σ, previous momentum, ATR history, or E04 stream survives an affected dependency; assert exact parity when all dependency identities are unchanged.
