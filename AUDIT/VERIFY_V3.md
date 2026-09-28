# SESSION V3 — Independent Verification

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---:|---:|---|---|---|
| K-001 | CONFIRMED | S1 | S1 | Yes — frozen data contract/store | — | A — fail closed on hash-colliding revisions; owner-approved versioned hash migration before acceptance |
| K-002 | CONFIRMED | S1 | S1 | Yes — frozen parser/store | ISSUE-CP1-012 (correction lifecycle only) | A — bind each revision to its recorded correction time; refuse historical reconstruction until version-aware reads exist |
| K-003 | CONFIRMED | S1 | S1 | No — producer is non-frozen; store DDL remains frozen | ISSUE-079 (cache correctness, distinct from latency) | A — fingerprint the selected PIT revision/status set and force cold rebuild on mismatch |
| K-004 | CONFIRMED | S2 | S2 | Yes — SQLiteStore is frozen; route via non-frozen guarded service pending owner approval for store guard | — | A now, B with owner approval — guard all three identity fields before correction |
| K-005 | CONFIRMED | S1 | S1 | Yes — SQLiteStore is frozen; non-frozen atomic writer is a fallback | ISSUE-076 (commit boundary) | B with owner approval; until then gate writes or route through tested atomic writer |
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

