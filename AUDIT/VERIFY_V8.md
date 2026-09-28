| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---:|---:|---|---|---|
| P-001 | CONFIRMED | S1 | S1 | Yes—E03 | — | A: normalize timestamp units in a non-frozen E03 input adapter; retain raw source time |
| P-002 | CONFIRMED | S1 | S1 | Yes—E03 | — | A: detect continuity breaks before E03 admission and emit a named degraded/refusal status |
| P-003 | CONFIRMED | S1 | S2 | Yes—E03 | — | A: producer/store dedup before streaming admission; direct API remains defective |
| P-004 | PARTIAL | S1 | S2 | Yes—E03 | — | A: version calibration by source prefix and publish only after the calibration horizon |
| P-005 | CONFIRMED | S1 | S2 | Yes—E03 | — | A: map native evidence quality/status at a non-frozen fabric admission adapter |
| P-006 | CONFIRMED | S1 | S2 | Yes—E03 | — | A: bypass replay cache when dependency identity cannot be represented externally |
| P-007 | CONFIRMED | S2 | S2 | Yes—E03 | — | A: finite producer windows/reset policy; exact parity must be proved |
| P-008 | CONFIRMED | S1 | S1 | Yes—E04 | — | A: producer-side shock quarantine; do not consume suspect ATR for risk |
| P-009 | CONFIRMED | S1 | S1 | Yes—E04 | — | A: independent producer gap veto/alert before native E04 output admission |
| P-010 | PARTIAL | S2 | S3 | Yes—E04 | — | A: owner resolves RV unit/annualization contract before changing formula |

This is a read-only verification on baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`. The report source is `/tmp/AUDIT.md` fetched from audit commit `015d19bd6ec1956b853fd566157a929f9f95f260`; the compact index was only a locator. No `.env`, secrets, `data/`, database, device, exchange or Telegram endpoint was read or contacted. No source, config, tests, or existing documents were changed. The only working-tree additions are this report and new files in `AUDIT/probes_V8/`.

All four engines are frozen by the user’s stated boundary. Any in-engine change below is therefore not authorized by this verification. Contract prose is treated as binding except where the later owner decision log explicitly resolves a conflict; owner decisions take precedence. Synthetic results establish behavior for these inputs only, not frequency or impact on market/device data.

### P-001

#### Auditor claim (short quote)

“OI timestamp is milliseconds but `5*timeframe_sec` is seconds; increasing hourly OI is falsely STALE.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e03_volume/engine.py:285–325` (`TF_SECONDS`, `detect_oi_stale`), `:531–603` (`VolumeEngineV4.ingest_bar`), `:929–959` (`observation_to_bar`), and `:972–1024` (`E03VolumeEngine.compute`); `apex/data_catalog/contracts.py:95–240` (`MarketObservation` and `validate_market_observation`); E03 test helper and relevant OI tests in `tests/unit/test_e03_volume.py:55–95,150–176`; grep of consumers found native call at `engine.py:588`, batch path `:853–858`, `E03VolumeEngine.compute :998–1007`, and producer conversions/consumption in `apex/ops/engine_context.py:1469–1497,1483–1491,2459–2500`. Those callers provide epoch-ms OI timestamps. The producer passes OI timestamps via `MarketObservation.oi_timestamp` and the E03 adapter without unit conversion.

#### Reproduction (command, probe file, actual result)

Command: `PYTHONPATH=. python3 AUDIT/probes_V8/P-001.py` (output in `AUDIT/probes_V8/P-001.out`). Five increasing OI observations passed `validate_market_observation`; consecutive timestamp delta was `3,600,000` ms. The real `detect_oi_stale(..., timeframe_sec=3600)` returned `(True, 'STALE_GAP_3600000')`. This directly reproduces the false-stale predicate; no real market series was consulted.

#### Verdict and reasoning

**CONFIRMED.** The function subtracts integer source timestamps then compares directly to `5 * timeframe_sec`, with no unit conversion. Hourly milliseconds exceed the 18,000-second bound numerically. The probe used the repository function, not a reimplementation.

#### Root cause

Mixed epoch-millisecond and duration-second units in one comparison. The adjacent `len(set(...)) == 1` flat-OI branch is a separate stale rule and is not implicated.

#### Direct impact

Increasing OI can be classified STALE and its `oi_z` omitted. The engine appends `EV_VOL_011 OI_Unavailable`; stale OI therefore ceases to contribute its intended evidence.

#### Secondary effects and interactions (upstream/downstream)

Upstream, `MarketObservation.oi_timestamp` is an ISO timestamp converted to epoch milliseconds. Downstream, E03’s participation evidence can influence later context and E11 participation inputs; fabric is a read-only projection and does not repair the erroneous classification. A producer unit normalization can make the current PAPER conversion consistent, but it cannot change direct E03 API semantics. No position or order was exercised.

#### Contract and decisions

E03 §3.10 at `APEX_GEN5.md:3899`/the OI freshness discussion requires OI freshness in timeframe terms and the E03 schema requires explicit timestamp provenance. Global `MarketObservation` time is ISO/UTC and adapter code converts it to milliseconds. No later owner decision authorizes mixed units or overrides the formula. Contract semantics govern; implementation diverges.

#### Frozen status and non-frozen alternative

`apex/engines/e03_volume/engine.py` is frozen. A non-frozen adapter may convert both values to the same unit before engine admission, with the original raw timestamp retained in lineage and validation rejecting ambiguous units. It cannot correct calls that bypass that adapter. In-engine correction changes E03 evidence state, hashes, fixture expectations and replay outputs; dependent training/backtest artifacts would need revalidation or retraining if E03-derived features are inputs.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Adapter normalization (preferred short-term):** convert `oi_timestamp`/gaps to seconds or convert the threshold to ms, with explicit unit contract. Side effects: adapter tests and stored lineage expectations change; direct native calls remain exposed; no frozen file changes.

B. **Owner-authorized E03 correction:** normalize units in `detect_oi_stale`. Side effects: frozen-file exception required; rederive/update E03 golden cases, snapshot/replay hashes and downstream feature baselines; rerun relevant training/backtests.

#### My recommendation

A as a containment measure, plus an owner decision before any frozen E03 correction. Do not treat adapter-only protection as proving the frozen API correct.

#### Acceptance and regression tests

Assert increasing OI every 1h with millisecond stamps is AVAILABLE; a true gap greater than 5 TF is STALE; five equal OI observations are STALE independent of timestamp units; test exact threshold equality and adjacent milliseconds/seconds. Validate the observation before adapting it and test the same series through both direct engine and producer adapter.

### P-002

#### Auditor claim (short quote)

“E03 contract requires reset after a gap greater than 1.5 TF; the engine appends history without resetting volume baselines.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e03_volume/engine.py:495–563` (initialization, `_warm_append`, `ingest_bar` admission), `:610–755` (feature calculation and append after emission), and `:851–858` (`run_engine`); E03’s §3.1 contract range `APEX_GEN5.md:3970–3987`; caller locations listed under P-001. `grep -rn` found the native PAPER projection at `apex/ops/engine_context.py:1483–1497` creates per-window `run_engine` data; no gap-reset call exists between timestamp comparison and history append in the reviewed E03 path.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=. python3 AUDIT/probes_V8/P-002.py`; 51 individually valid synthetic OHLC inputs were run twice, with monotonically varying volume and either no gap or a 12-hour timestamp jump on the final 1h bar. Both runs retained 51 observations / 51 unique timestamps and emitted `volume_sma=139.5`, with prior-history length 50. The raw output is `AUDIT/probes_V8/P-002.out`. This demonstrates no gap-triggered reset in this direct streaming path; a constant-price synthetic window cannot establish real-data impact.

#### Verdict and reasoning

**CONFIRMED.** The reviewed method validates candle shape and duplicate-last-key behavior but does not compare successive candle times against 1.5 TF or reset the rolling arrays. The pre-gap 50 observations still form the baseline after the timestamp discontinuity.

#### Root cause

No continuity state/branch is implemented in E03 ingestion. A timestamp jump is accepted as another adjacent member of the same history.

#### Direct impact

VolumeRatio, VolumeZ and related E03 features can continue using pre-gap samples, while warm-up does not restart.

#### Secondary effects and interactions (upstream/downstream)

Upstream, store/closed-window validation determines which observations reach E03; it orders/deduplicates but does not establish that a gap-free statistical baseline exists. Downstream, E03 volume context is projected to other engine/fabric consumers. The producer’s finite rolling window bounds history length, not continuity within the window. No actual trade, Q score or real gap incidence was measured.

#### Contract and decisions

E03 §3.1 at `APEX_GEN5.md:3970–3987` calls for gap-aware reset/re-warm behavior; no later owner decision found that supersedes it. Contract governs over the current append-only code behavior.

#### Frozen status and non-frozen alternative

E03 is frozen. The producer can detect discontinuity from adjacent validated timestamps, tag/withhold that cell’s E03 projection, and wait for a contiguous window before admitting it. An exact in-engine reset changes warm-up boundaries, snapshots, fixtures and replay outputs; training/backtest parity must be re-established.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Producer continuity gate:** mark discontinuous E03 evidence unavailable until a contiguous baseline is available. Side effects: delayed/absent evidence, additional status lineage, downstream fixture updates; no frozen-file change.

B. **Owner-authorized native reset:** clear baseline on the contract threshold. Side effects: frozen E03 mutation; golden fixtures, identities and all dependent historical/research results need revalidation.

#### My recommendation

A now because the defect is frozen and the producer controls the input boundary; do not silently replace the model’s window semantics without an owner ruling.

#### Acceptance and regression tests

Use nonconstant volume and valid candles; gap 1.5 TF minus/at/plus one time unit; prove no pre-gap sample contributes to any emitted baseline until required contiguous samples accrue; prove no-gap prefix output remains identical. Add producer-level test to establish gate behavior.

### P-003

#### Auditor claim (short quote)

“E03 idempotency is applied only after warm-up and only against the latest `(ts,c,v)`; 50 redeliveries fake warm-up.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e03_volume/engine.py:501–563` (`_warm_append`, warm-up path, late duplicate test), `:731–755` (append/emission), `:851–858` (`run_engine`), `tests/unit/test_e03_volume.py:360–430` (streaming/idempotency-related tests), and direct call sites from `grep -rn`: `E03VolumeEngine.compute` builds a new `VolumeEngineV4` at `:998`; `engine_context.py:1494` invokes the producer’s batch E03 path. Producer reads a closed, store-backed ordered window; this narrows but does not eliminate direct streaming API behavior.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=. python3 AUDIT/probes_V8/P-003.py`; 50 copies of one validated closed candle created `history=50`, `unique ts=1`, and no emission. One different valid timestamp then caused an emission with reported prior history 50, despite only two unique timestamps. Output: `AUDIT/probes_V8/P-003.out`.

#### Verdict and reasoning

**CONFIRMED.** Warm-up calls `_warm_append` before reaching the later duplicate check. The later check compares only to the last candle and only matching close/volume, so it cannot repair the already-inflated warm-up count. This is a direct streaming API defect; the probe does not show that normal PAPER storage delivers duplicates.

#### Root cause

Idempotency occurs after `len(history_bars) < 50` handling, with no identity set keyed by timestamp/content/version. The direct API treats replayed closed bars as new during warm-up.

#### Direct impact

A false 50-bar warm-up can lead to calculated evidence using repeated observations and insufficient unique-time support.

#### Secondary effects and interactions (upstream/downstream)

The store and current producer window are expected to provide ordered, deduplicated observations, limiting normal-path exposure. A retry/replay caller or future adapter that feeds the same candle repeatedly can still poison E03 state; downstream evidence identity and E06/feature inputs then reflect fabricated sample count. No live producer retry sequence was run.

#### Contract and decisions

E03 §3.1 PIT/rolling history and §4 idempotent streaming provisions (`APEX_GEN5.md:3917–3923,4673–4689`) require deterministic ingestion and distinct candle history. No later owner decision supersedes this. Contract governs.

#### Frozen status and non-frozen alternative

E03 is frozen. The non-frozen producer can deduplicate by full candle identity before each call and reject same-timestamp corrections for explicit version handling. This only protects that ingress. Native repair changes E03 state progression and all golden/replay snapshots; any trained feature artifact using E03 output needs parity or retraining.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Producer dedup (preferred containment):** one accepted identity per timestamp/version, correction gets an explicit supersession path. Side effects: lineage/version bookkeeping and producer tests; direct API remains defective.

B. **Owner-authorized native dedup:** validate/deduplicate before warm-up. Side effects: frozen-file change; update fixtures, identities, replay outputs, and dependent research baselines.

#### My recommendation

A for existing producer path; also add a release gate documenting direct API exposure until the owner approves a frozen correction.

#### Acceptance and regression tests

50 identical redeliveries yield one accepted candle and do not satisfy warm-up; 50 unique consecutive candles do; same timestamp with changed OHLC/volume follows explicit correction/refusal semantics; exact replay of a valid unique stream remains byte-identical.

### P-004

#### Auditor claim (short quote)

“E03 calibration uses later bars to revise confidence for earlier events, while evidence availability remains at the source candle.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e03_volume/engine.py:1031–1057` (`_climax_calibration`), `:972–1021` (`compute` source-index association and calibration call), `:1080–1122` (`_to_evidence` timestamps); `tests/unit/test_e03_volume.py:599–617` (calibration/source-index regressions); producer projection at `apex/ops/engine_context.py:1483–1497` and post-bundle event availability projection around `:2323–2329`. The latter raises event availability to the maximum of the complete raw window; this is material mitigation. Caller search showed no independent live use of `_climax_calibration` outside `compute` and its tests.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=. python3 AUDIT/probes_V8/P-004.py`; all 52 synthetic OHLC candles were valid. The climax at index 49 had confidence `0.0` without a successful continuation at index 50 and `0.20654329147389294` when index 50 closed beyond it. The event’s reported source availability stayed at its index-49 timestamp in this direct calibration probe. See `AUDIT/probes_V8/P-004.out`.

#### Verdict and reasoning

**PARTIAL.** The future-dependent calibration and mutable earlier confidence are confirmed. However, the native PAPER producer projects the complete frame’s maximum availability onto produced events, so this does not establish that a decision at index 49 consumes the future-conditioned confidence in that path. The claim overstates operational early availability; historical prefix/replay stability remains a defect. The synthetic result does not quantify how often such a climax occurs.

#### Root cause

One Wilson estimate is computed across the full window and applied to all emitted event rows, instead of using a prefix/as-of calibration or versioned later publication. The native producer’s frame-level availability projection mitigates consumer leakage but not the underlying prefix dependence.

#### Direct impact

A given historical event’s confidence changes as the window is extended. In the direct engine evidence projection, its time fields may still reflect source availability.

#### Secondary effects and interactions (upstream/downstream)

Upstream, the calibration consumes future continuation outcomes within five candles. Downstream, PAPER’s outer projection delays all frame output to the end of the window; this prevents the specific old-decision bypass in this probe. Backtest/replay consumers outside that projection may still see non-prefix-stable confidence. No market/device training pipeline was run.

#### Contract and decisions

E03 §8.5 Wilson calibration and the global PIT requirements (`APEX_GEN5.md:3895,3929`) govern. Later test decisions on calibration source-index binding ensure event-to-source mapping but do not authorize future-conditioned confidence to be presented as prefix-stable. Owner decisions supersede conflicting prose; no conflicting decision was found for this behavior.

#### Frozen status and non-frozen alternative

E03 is frozen. A producer can retain calibration publication time, version it, and withhold the calibrated confidence until the five-bar horizon is observed; alternatively emit uncalibrated confidence in immediate contexts. A frozen fix changes confidence and snapshot/event outputs, fixtures and replay hashes; training/research must be rerun for dependent outputs.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Prefix-safe producer projection:** mark event confidence provisional until its calibration horizon closes, then emit a superseding version. Side effects: additional lineage/identity and delayed calibrated values; no engine mutation.

B. **Native prefix calibration:** calculate confidence per event as-of. Side effects: frozen change and changed historical outputs/hashes; regression/retraining required wherever calibration is a learned feature.

#### My recommendation

A, because it preserves frozen native results and makes the publication boundary truthful. Keep severity S2: a PIT concern remains, but native PAPER delays the complete frame.

#### Acceptance and regression tests

For each prefix `t` and `t+1`, earlier published rows are invariant or explicitly superseded with availability no earlier than `t+1`; run the same check through direct engine and producer projection. Include mature and immature events and verify no earlier risk/fabric consumer can access a future-conditioned version.

### P-005

#### Auditor claim (short quote)

“When OI is missing/stale, E03’s Q1 state becomes a VALID/ACTIVE Q3 event and event codes are collapsed.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e03_volume/engine.py:730–755` (state and event append), `:1080–1150` (`_to_evidence`, `_quality_tag`), `apex/fabric/evidence.py:307–404,430–472` (event-to-fabric projection/admission), and `apex/ops/engine_context.py:1661–1681,2323–2329` (producer event/admission projections). Test references in `tests/unit/test_e03_volume.py` cover event mapping and missing OI generally, but do not assert that every simultaneous native event has its own EvidenceEvent condition. Producer crosswalk receives the emitted EvidenceEvent; the explanation retains the underlying list, while `condition_state` carries only `events[0]`.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=. python3 AUDIT/probes_V8/P-005.py`; a real `ParticipationEvidence` instance with `oi_state=MISSING`, `quality=Q1`, and two event names was passed to native `_to_evidence`. Result: `resolution_class=Q3`, `validity=VALID`, `fate=ACTIVE`, `confidence=0.0`, `condition_state=EV_VOL_001...`; the second event is absent from `condition_state` but remains in explanation. Output: `AUDIT/probes_V8/P-005.out`. The synthetic object tests projection, not market occurrence.

#### Verdict and reasoning

**CONFIRMED.** The two code mappings are explicit. “Quality upgrade” is not a proven downstream trading effect: Q3 is a resolution label rather than a numeric evidence-quality score, and confidence is zero in this projection. Nevertheless, the resolution label is misaligned with the underlying `ParticipationEvidence.quality=Q1` and missing-OI condition, and simultaneous machine-readable event identity is lossy.

#### Root cause

`_quality_tag` maps OI non-availability to Q3 before considering ordinary Q1 event class. `_to_evidence` serializes only the first entry in `ev.events` to `condition_state`; remaining names are human-readable only in explanation.

#### Direct impact

Consumers may interpret a Q3 resolution class as a proxy classification even for a simple volume spike; independent event code `EV_VOL_011` is not a distinct machine-readable `condition_state`.

#### Secondary effects and interactions (upstream/downstream)

E03 sets its state DEGRADED for missing/stale OI, but emits the EvidenceEvent with `validity=VALID` unless the resolution is QX. Fabric projects event lifecycle and resolution without recalculating the engine status, so it will not neutralize the mismatch. D23 is specifically about E11 participation/sample quality and Q5, not a license to rewrite E03’s own output mapping; it does show missing OI must not be imputed or silently treated as healthy. No setup, risk, or order was run.

#### Contract and decisions

E03 §1.2/§3.6 (`APEX_GEN5.md:3893–3895`) distinguishes Q1 normalized features, Q3 model-driven proxies and QX invalid/missing data; the contract also requires explicit proxy labeling. The later D23 decision (`PHASE2_DECISION_LOG.md:343`) governs E11: missing OI removes its weight, marks participation PARTIAL, and prevents Q5; it does not supersede E03’s evidence semantics. Contract applies to E03; D23 takes precedence only for E11 participation.

#### Frozen status and non-frozen alternative

E03 is frozen. Fabric/producer can gate resolution/validity based on an explicit engine-state marker and carry all event codes as structured children/lineage; this avoids mutating the engine but requires compatible event schema and golden producer tests. Native correction changes event ids/identity and fixtures; dependent feature snapshots and any E03-derived training must be rebuilt or proven parity.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Producer/fabric admission adapter (preferred):** preserve the raw event, derive explicit status from `oi_state`, and do not relabel a simple event as a model proxy; split simultaneous event codes into separately identified child refs. Side effects: additional adapter schema/identity and changed fabric membership; frozen engine remains unchanged.

B. **Owner-authorized E03 correction:** revise `_quality_tag`/emission. Side effects: frozen file, golden fixtures, snapshot/feature hashes, replay/backtest parity and dependent training affected.

#### My recommendation

A. Treat missing OI as an orthogonal status, not as a reason to call a volume spike a model-derived Q3 proxy. Keep the numeric impact limited pending a complete risk-path probe.

#### Acceptance and regression tests

For OI absent, stale, invalid and healthy: assert engine state, native EvidenceEvent validity/resolution and fabric admission agree with contract. Multiple simultaneous event codes must survive as separate structured identifiers or an explicit lossless list; test confidence independently. Healthy OI must not be disabled by the gate.

### P-006

#### Auditor claim (short quote)

“E03 replay key omits OI, OI time/availability and most parameters, so the same instance can return a stale snapshot.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e03_volume/engine.py:919–928` (canonical hashing), `:972–1021` (`compute`, input hash/key/cache lookup), `apex/engines/base.py:157–203` (cache key creation, lookup, TTL/store), `apex/ops/engine_context.py:1483–1497` (E03 producer caller creates a computation per frame) and its engine collection wiring; tests reference replay behavior at `tests/unit/test_e03_volume.py:200–245,360–430`. Caller search found no persistent E03VolumeEngine singleton in the normal per-frame native projection; the direct EngineBase API remains callable repeatedly.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=. python3 AUDIT/probes_V8/P-006.py`; two validated 55-observation windows with same OHLCV/time but different OI inputs were computed on one `E03VolumeEngine` at the same `as_of`. The second call returned the same object/evidence IDs as the first (`same_result_object=True`, `same_ids=True`); a fresh engine on the changed window produced a different final snapshot ID. Probe and raw output: `AUDIT/probes_V8/P-006.py`, `.out`. Because P-001 also makes the increasing hourly OI stale, this probe proves omitted OI dependency/hash and stale cache, not that the fresh OI state should specifically be AVAILABLE.

#### Verdict and reasoning

**CONFIRMED.** Input hash includes only `(ts,o,h,l,c,v,atr_prev)` and the parameter payload includes only `vol_sma_n/profile_window`; the lookup occurs after full recomputation and returns the older result when that incomplete key collides. The normal producer generally creates a fresh engine per frame, so scope of exposure is narrower than the API-level defect.

#### Root cause

The replay identity is not canonical over all effective input/provenance and parameters. It excludes OI and availability as well as other E03 parameters; key construction does not bind the complete payload.

#### Direct impact

Repeated same-instance compute calls can return cached `EvidenceEvent` objects from a distinct OI/parameter input, including the old snapshot identity.

#### Secondary effects and interactions (upstream/downstream)

The producer’s ordinary frame-level instantiation limits repeated cache hits across frames, but API users and future shared-engine paths are exposed. A cache hit can propagate old E03 evidence to E06/E11/fabric and invalidate replay determinism with respect to actual inputs. P-001 independently affects OI state. No training artifact or producer singleton was tested.

#### Contract and decisions

`apex/engines/base.py:169–203` binds replay behavior to input hash, parameter package and canonical payload; E03 §5 identity/replay text (`APEX_GEN5.md:3917–3923,4673–4689`) requires deterministic replay over the actual data. No owner decision permits omitted effective dependencies. Engine contract is binding.

#### Frozen status and non-frozen alternative

E03 is frozen. A non-frozen caller can disable reuse by creating a fresh computation per request or include a caller-computed full dependency digest in the identity where the interface permits. No non-frozen wrapper can safely reconstruct hidden native dependencies without the complete canonical schema. A native repair changes cache/replay key, snapshot identity and existing fixture expectations; any cached/researched/trained outputs keyed by old identities need invalidation or retraining.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Fresh-instance containment:** prohibit cross-input instance reuse at producer boundaries. Side effects: more compute; loses cache benefit; no frozen change.

B. **Owner-authorized canonical replay key:** bind all source values, provenance/availability, parameters and code/contract version. Side effects: frozen change; all cache keys and snapshot/replay baselines invalidated, golden tests updated, dependent training/backtests revalidated.

#### My recommendation

A for current production composition; file an owner-approved frozen correction before sharing an E03 instance between distinct contexts. This is a valid containment, not a proof the API contract is repaired.

#### Acceptance and regression tests

Same OHLCV with changed OI value, OI timestamp, availability, `atr_prev`, each effective parameter and code revision must not alias; exact identical inputs remain deterministic and idempotent. Compare each same-instance result with a fresh-instance oracle and assert identity as well as payload equality.

### P-007

#### Auditor claim (short quote)

“E03’s streaming histories grow without bound and OBV/divergence recompute on full history; 3,000 bars are a required memory probe.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e03_volume/engine.py:495–529` (unbounded lists and warm append), `:619–628` (full-history OBV construction), `:684–695` (full close-history pivot scan), `:731–749` (append), `:972–1021` (fresh batch instance), `apex/ops/engine_context.py:1483–1497,2472–2500` (frame window and native chronological context); source caller grep includes `run_engine`, compute and PAPER context. The E03 engine itself has no retention/pruning branch. Producer’s per-frame batch call receives a bounded window (current engine context says 300 bars); this is not evidence that all streaming APIs or memory remain bounded.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=. python3 AUDIT/probes_V8/P-007.py`; all 3,000 synthetic OHLC inputs were first built from repository-validated `MarketObservation` values. Real `VolumeEngineV4` processed all 3,000 in 18.461 seconds under `tracemalloc`; `history_bars`, closes, volumes and OBV each retained 3,000 elements; current traced allocation 6,369,751 bytes, peak 6,583,666 bytes. Raw output is `AUDIT/probes_V8/P-007.out`. This is one sandbox run, not a device benchmark or a 50,000-bar asymptotic performance conclusion.

#### Verdict and reasoning

**CONFIRMED.** The streaming object has no pruning and retains every accepted bar. It reconstructs OBV from all history during warm-up and builds a full-history OBV series for each mature bar; pivot detection scans close history. The 3,000-bar measurement confirms linear retained element growth at that point and material repeated work, not device latency.

#### Root cause

Long-lived `VolumeEngineV4` stores all history and recomputes derived state from the full prefix, rather than incremental state or a governed retention policy.

#### Direct impact

Memory grows with bars processed; mature-bar work grows with history and is not bounded by the engine API. Actual device resource budget remains unmeasured.

#### Secondary effects and interactions (upstream/downstream)

The native PAPER context uses finite per-frame windows and fresh batch calculation, which bounds that particular call at roughly 300 bars; this does not cure standalone streaming or a future persistent instance. D30’s 20 base training cells are distinct from the wider 140-cell data scope. No 140-cell workload or device latency is inferred from this single engine probe.

#### Contract and decisions

E03 §3.3 requires Wilder OBV semantics and replayability; the global performance contract requires bounded resource use, while the exact retention/replay law needs the full engine chapter and is not inferred from the synthetic measurement. D30 (`PHASE2_DECISION_LOG.md:523–532`) establishes only 20 E11 training cells, not E03 runtime scope. No decision authorizes unbounded process memory. (This row remains incomplete against the mandatory full-contract/caller read.)

#### Frozen status and non-frozen alternative

E03 is frozen. The producer can keep its bounded frame window and avoid one streaming instance spanning all bars; periodic reset changes warm-up/continuity and must be treated as a new prefix with explicit state provenance. There is no general fabric-side remedy for memory already allocated inside a long-lived engine. An exact incremental native fix can change floating-point ordering, OBV pivot results, identities and replay/golden fixtures; full parity and dependent training/backtest revalidation would be required.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Maintain bounded producer windows:** keep current finite context windows and instrument any persistent stream. Side effects: reset/warm-up semantics, compute repetition and cache identity must be controlled; no native fix.

B. **Owner-authorized incremental state/pruning:** preserve exact OBV/pivot state and define replay checkpoint/retention. Side effects: frozen E03 change, parity/identity and golden fixture updates; retrain/replay if any derived artifact changes.

#### My recommendation

A is containment in the existing PAPER window. Do not claim a device performance pass. Plan B only with owner approval and a byte/prefix parity harness.

#### Acceptance and regression tests

Required 3,000-bar probe is present. Extend isolated timing/memory measurements to n=500, 3,000, 5,000, 50,000 with warm/cold runs and exact final evidence parity; measure replay after restart/checkpoint; separately confirm producer keeps its documented fixed window. Target-device evidence is required before a device capacity claim.

### P-008

#### Auditor claim (short quote)

“E04 includes the outlier in the 99th-percentile reference; 20 unit TRs plus TR=100 return the uncapped 100 and ATR consumes it.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e04_volatility/engine.py:840–850` (`_winsorize_tr`), `:852–890` (`ingest_bar`, TR/ATR update), `:1070–1086` (extreme event decision), `:1157–1178` (`run_engine`), downstream adapter at `apex/ops/engine_context.py:1469–1483,1490–1497` and E04→E05/E06 integration at `tests/integration/test_cp3_engines.py:31–50`. Grep of callers found `run_engine`, E04 stream, producer `volatility_stream`, and unit tests; no second native winsorizer.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=. python3 AUDIT/probes_V8/P-008.py`; 20 valid synthetic observations with unit range were validated; the outlier OHLC was also validated. Real `_winsorize_tr(100.0)` with `trs=[1.0]*20` returned `(100.0, True)`. Output: `AUDIT/probes_V8/P-008.out`.

#### Verdict and reasoning

**CONFIRMED.** Sorted sample contains 20 unit values plus the current 100; `ceil(0.99*21)-1` selects index 20, the outlier itself. `ingest_bar` uses the returned value as `tr` before calling Wilder ATR. This proves failure to cap under the stated probe, not that every Q0 rule or downstream guard is absent.

#### Root cause

The outlier is part of its own winsorization reference set, and the selected 99th-percentile order statistic can equal the current outlier for small sample sizes.

#### Direct impact

The outlier can enter ATR despite the suspect flag; shock ATR can alter stop/range normalization. The code does record `TR_WINSORIZED_Q0_SUSPECT`, so the claim that it is wholly unflagged would be false.

#### Secondary effects and interactions (upstream/downstream)

Native E04 ATR feeds E03 as prior ATR, E05 Gate D and E06 supplied volatility evidence; the CP3 integration tests establish this wiring. The producer does not automatically replace ATR merely because the event is flagged. Risk/order impact on real data is not proven. A future gate can neutralize consumption without editing E04.

#### Contract and decisions

E04 §3.1 (`APEX_GEN5.md:5015–5017,5039–5045`) says winsorize TR above 10×median(TR20); §3.4.1 allows analytical fallback only with degraded provenance. No owner ruling was found that says flagged raw outliers must feed ATR. Contract governs.

#### Frozen status and non-frozen alternative

E04 is frozen. Non-frozen producer can withhold suspect ATR from risk/setup consumers or gate E04 evidence as degraded, while preserving raw diagnostics. An in-engine quantile fix changes ATR history and therefore E03/E05/E06 outputs, replay/snapshot hashes, fixtures and possibly model calibration; dependent training/backtests need revalidation.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Producer shock quarantine:** preserve raw E04 evidence but prevent suspect ATR from decision-facing contexts until a governed replacement/confirmation exists. Side effects: more refusals/degraded periods and cross-engine fixture changes; no frozen edit.

B. **Owner-authorized native correction:** define an historical-only quantile/reference sample and consistent capped/raw fields. Side effects: frozen change; new golden fixture semantics, hashes and downstream calibration/retraining.

#### My recommendation

A as an immediate risk containment, with owner ruling required for B. Do not pass the flagged scalar into sizing as if clamped.

#### Acceptance and regression tests

20 prior unit TRs plus 100 must produce the contract-defined cap; assert raw and capped TR separately, flag behavior, ATR recurrence, snapshot identity, and E03/E05/E06 consumer refusal/quality. Also test no-outlier parity and short-history boundaries.

### P-009

#### Auditor claim (short quote)

“E04 compares a gap with ATR after updating ATR, so a 20-point gap over prior ATR 2 fails the 8× threshold.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e04_volatility/engine.py:840–889` (winsorization, `ingest_bar`, Wilder ATR update, gap predicate), `:1070–1086` (Extreme_Move event), `:1157–1178` (`run_engine`), `tests/unit/test_e04_volatility.py` gap/suspect cases, and E04 native chronological stream at `apex/ops/engine_context.py:1469–1483,2459–2500`.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=. python3 AUDIT/probes_V8/P-009.py`; 55 valid, constant-range synthetic bars established prior ATR `2.0`; the next valid bar opened 20 above previous close. Real E04 produced current ATR `3.357142857142857`, only `EV_VLT_007`, and `TR_WINSORIZED_Q0_SUSPECT`; no `EV_VLT_008` Extreme_Move. Since 20 is not greater than `8×3.357142857=26.857...`, this reproduces the threshold suppression. Raw output: `AUDIT/probes_V8/P-009.out`.

#### Verdict and reasoning

**CONFIRMED.** `ingest_bar` updates the short Wilder ATR using current TR before computing `gap_extreme`; the post-update ATR is the comparator. This synthetic result matches the claim. No real gap/position or actual risk response was tested.

#### Root cause

Ordering: current-bar TR is included in ATR before an event whose threshold is intended to detect a shock relative to the prior baseline.

#### Direct impact

A shock that exceeded the previous ATR threshold may not produce `EV_VLT_008`; an outlier-quality event is still emitted separately.

#### Secondary effects and interactions (upstream/downstream)

E04 feeds ATR/regime context to E03/E05/E06 and risk-facing context, so a missing shock event may affect downstream gating if consumers depend on that event. Existing separate `TR_WINSORIZED_Q0_SUSPECT` provides a diagnostic but is not the same event. Device behavior is unknown.

#### Contract and decisions

E04 §7 failure-mode contract (`APEX_GEN5.md:5410–5415`) says gap greater than 8×ATR is flagged as Extreme_Move; §3.1 defines the ATR recurrence. The unambiguous PIT comparator for a shock is the previously available ATR, while formula prose does not explicitly define update ordering. No owner decision supersedes the prior-baseline interpretation; this is a confirmed implementation inconsistency, subject to owner confirmation of the edge semantics.

#### Frozen status and non-frozen alternative

E04 is frozen. Producer can independently compare the current opening gap with the last published E04 ATR and raise a separate non-engine risk/diagnostic gate. This adds a second event path and must avoid double counting. Native fix changes gap event history, snapshots and downstream context/fixtures; rerun E04 and consumers’ replay/backtests, and retrain dependent model features if applicable.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Producer gap guard:** use last published prior ATR for a producer-side hard warning/withhold decision; leave native event as-is. Side effects: new duplicate-control/lineage and producer integration tests.

B. **Owner-authorized E04 ordering correction:** evaluate shock before current ATR update. Side effects: frozen mutation, changed event order/identity and E04/E05/E06 fixtures/calibration.

#### My recommendation

A until the owner confirms exact comparison semantics, then B only through a frozen-file ruling if native semantics must change.

#### Acceptance and regression tests

With prior ATR 2 and current raw gap 20, ensure the prior-based event fires exactly once at correct timestamp; a gap below/equal/above `8×priorATR` tests strictness; verify post-update ATR remains mathematically correct and no duplicate producer alert.

### P-010

#### Auditor claim (short quote)

“E04 hourly `hv30` annualizes a sum of 30 hourly returns with 8,760 bars/year, while the contract’s `sqrt(RV×365)` gives a different horizon; unit/meaning needs owner decision.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e04_volatility/engine.py:363–374` (`realized_var`, `annualized_hv`), `:852–903` (caller builds RV over `hv_window` and passes timeframe), test `tests/unit/test_e04_volatility.py:223–227`, contract E04 §3.2 at `APEX_GEN5.md:5047–5049`, and E04 producer projection at `apex/ops/engine_context.py:1469–1483`. The function computes bars/year as `days*86400/tf_seconds`; the exact intended unit of an `M`-bar RV is the unresolved contract question.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=. python3 AUDIT/probes_V8/P-010.py`; real `realized_var([.01]*30)=.003`; `annualized_hv(.003,3600,365)=5.1264022471905175`; literal daily expression `sqrt(.003*365)=1.0464224768228172`. Output: `AUDIT/probes_V8/P-010.out`. This is arithmetic on an artificial series, not evidence of trading impact.

#### Verdict and reasoning

**PARTIAL.** The numerical divergence is reproducible, but it does not establish that the code is wrong: for 30 hourly return observations, annualizing by 8,760 hourly bars/year is internally dimensionally coherent; the contract’s 365 multiplier applies when RV is daily. The specification does not clearly bind the intraday `hv30` window to daily RV units. This is primarily an owner/specification resolution, not a proven trading defect.

#### Root cause

The contract combines daily crypto annualization language with an implementation parameterized by timeframe and an intraday window. The unit of RV and the intended horizon label (“30” bars versus “30-day”) are underspecified.

#### Direct impact

HV differs by a constant horizon factor under different interpretations. No position-size, regime threshold or signal impact was independently run; relative ordering may remain unchanged under a fixed scalar, but absolute thresholds can change.

#### Secondary effects and interactions (upstream/downstream)

E04 exposes HV in volatility state; downstream regime/classifier thresholds or calibration could depend on its absolute scale. Producer does not normalize or relabel the horizon. D30 concerns E11 training scope (20 base cells), not the number of data cells or the RV unit; no training-scope conflation is made here.

#### Contract and decisions

E04 §3.2 (`APEX_GEN5.md:5047–5049`) says `RV=sum r²` and gives annualization `sqrt(RV×365)` for crypto; implementation `annualized_hv` uses timeframe bars/year. ADR-P2-007 says worked examples are illustrative and values must be re-derived; it does not resolve units. No owner decision found specifying the hourly annualization convention. Until clarified, formula text is the reference but not enough to declare the time unit.

#### Frozen status and non-frozen alternative

E04 is frozen. A non-frozen producer can label/route `hv30` with explicit timeframe and horizon, and avoid mixing hourly and daily measures in downstream thresholds; this does not reconcile engine formula semantics. In-engine change affects volatility-state snapshots, replay fixtures and downstream E03/E05/E06 inputs; calibration and any dependent training must be repeated.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Owner decision first (recommended):** specify RV input interval, horizon, and annualization for each timeframe, then either preserve or change code. Side effects: no code change before decision; documentation and tests must lock the selected meaning.

B. **Producer relabeling:** expose explicit `hv_horizon` and scale metadata. Side effects: downstream schema/identity changes and consumer/test updates; formula remains frozen and ambiguous direct calls remain.

C. **Owner-authorized native change:** implement the decided formula. Side effects: frozen engine change, hash/fixture changes and recalibration/retraining of downstream features.

#### My recommendation

A. Record a binding owner decision defining units and threshold calibration before classifying this as a formula defect.

#### Acceptance and regression tests

Use constant returns on 1h and 1d windows of multiple lengths; assert annualized outputs match the owner-selected units/horizon, including time conversion and dimensional labels. Verify E04 state, E11/regime consumers and E05/E06 consumers use the same documented scale.

## New findings not in the audit

None identified in this ten-row tranche. This is not a claim that the full E03–E06 scope has no additional findings.

## Rows not verified or incomplete

The exact third-party row text was read for P-001–P-010 and each has a real-code probe or direct arithmetic check. However, the mandatory depth requirement to read every complete engine/test/context file and all transitive callers/callees was not completed for this tranche; the findings above are limited to the specifically cited code paths, and no device/real-data validation was performed. Rows P-011–P-039 have not yet been independently assessed and are not covered by this tranche.

## Final counts

This progress tranche: CONFIRMED 7; PARTIAL 3; REJECTED 0; DEVICE-EVIDENCE-NEEDED 0. The full 37-row V8 scope is not yet verified; do not interpret these counts as project-wide totals.
