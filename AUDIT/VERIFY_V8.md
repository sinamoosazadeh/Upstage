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
| P-011 | CONFIRMED | S1 | S2 | Yes—E04 | — | A: producer versions/corrects candle identity before E04 stream |
| P-012 | PARTIAL | S2 | S2 | Yes—E04 | — | A: adapter rejects invalid observation; index-join outputs by timestamp |
| P-013 | CONFIRMED | S1 | S2 | Yes—E04 | — | A: per-call fresh E04 instance; do not reuse across changed params |
| P-015 | CONFIRMED | S2 | S2 | Yes—E04 | — | A: producer counts UTC days, or owner approves per-bar periods |
| P-016 | PARTIAL | S2 | S2 | Yes—E04 | — | A: producer carries `garch_status`/estimator provenance into evidence |
| P-018 | PARTIAL | S2 | S2 | Yes—E05 | — | A: non-frozen E05 adapter supplies StructuralRole from E01 |
| P-019 | PARTIAL | S2 | S2 | Yes—E05 | ISSUE-CP3-004 | A: owner specifies terminal priority; do not silently rewrite history |
| P-020 | CONFIRMED | S1 | S2 | Yes—E05 | D31 (not its scope) | A: producer preserves both canonical terminal payload and identity |
| P-021 | PARTIAL | S2 | S2 | Yes—E05 | D31 | A: preserve native forensic event; admit terminal only as terminal |
| P-022 | PARTIAL | S2 | S2 | Yes—E05 | — | A: producer treats corrections as new versions; native API remains exposed |

This is a read-only verification on baseline `85b2c155d7b054a468379ddfd802eb239d0801f9`. The report source is `/tmp/AUDIT.md` fetched from audit commit `015d19bd6ec1956b853fd566157a929f9f95f260`; the compact index was only a locator. No `.env`, secrets, `data/`, database, device, exchange or Telegram endpoint was read or contacted. No source, config, tests, or existing documents were changed. The only working-tree additions are this report and new files in `AUDIT/probes_V8/`.

All four engines are frozen by the user’s stated boundary. Any in-engine change below is therefore not authorized by this verification. Contract prose is treated as binding except where the later owner decision log explicitly resolves a conflict; owner decisions take precedence. Synthetic results establish behavior for these inputs only, not frequency or impact on market/device data. Relevant suite command: `python3 -m pytest -q -p no:cacheprovider tests/unit/test_e03_volume.py tests/unit/test_e04_volatility.py tests/unit/test_e05_fvg.py tests/unit/test_e06_orderblock.py tests/integration/test_cp3_engines.py` → `227 passed in 28.72s`. This is suite status, not evidence that every audit claim has a dedicated regression test.

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

### P-011

#### Auditor claim (short quote)

“E04 records `(ts,c,v)` before validation; invalid→corrected or changed-wick bars at the same key are silently skipped.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e04_volatility/engine.py:852–873` (key registration precedes OHLC validation), `:1193–1240` (E04 EngineBase compute), `apex/ops/engine_context.py:2459–2500` (native stream), plus the E04 observation converter and store-ingress contract in `apex/data_catalog/contracts.py:185–239`. Direct callers from `grep -rn`: `run_engine`, E04 stream `ingest_bar`, `E04VolatilityEngine.compute`, producer `volatility_stream`, and unit tests. The producer performs a chronological stream over store observations; no correction/version route was demonstrated.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=.:AUDIT/probes_V8 python3 AUDIT/probes_V8/P-011.py`. After 55 valid bars, a second, independently contract-validated candle with same timestamp/close/volume but a different valid high returned `None`; E04 retained 55 bars and 55 keys. Raw output: `AUDIT/probes_V8/P-011.out`. The invalid H<L variant was intentionally not injected because it fails the required repository validator; valid-wick correction reproduces the other half.

#### Verdict and reasoning

**CONFIRMED.** Valid changed OHLC can be silently discarded because the key omits high/low and is inserted before later checks. Invalid→corrected behavior is also directly implied by add-before-H<L-check, but not separately executed under the valid-input probe rule.

#### Root cause

Idempotency key `(ts,c,v)` is incomplete and reserved before validation; it does not include wick values or correction version.

#### Direct impact

A valid wick correction with unchanged close/volume/time does not update ATR or volatility state.

#### Secondary effects and interactions (upstream/downstream)

E04 publishes ATR consumed by E03, E05 and E06. Producer chronological store stream minimizes ordinary duplicates but cannot represent corrected bars unless the input reader produces a new version; the direct API remains wrong for correction. No store mutation or market correction was tested.

#### Contract and decisions

E04 §3.1 requires OHLC TR from the current valid bar and §4 duplicate timestamp handling (`APEX_GEN5.md:5015–5017,5039–5045,5410–5415`). `MarketObservation.content_hash` includes open/close/volume, while the public validation and store handle duplicate policy upstream; no owner decision authorizes dropping different wick content. Contract governs.

#### Frozen status and non-frozen alternative

E04 is frozen. A producer can accept only immutable candle versions and identify corrections explicitly; if upstream exposes a same timestamp with changed wick, it should create a new version or refuse and rebuild a fresh E04 prefix. Native correction changes ATR paths, state hashes, E03/E05/E06 inputs and fixtures; historical replay and dependent training require revalidation.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Producer version gate:** refuse ambiguous same-time correction or start a new versioned stream from that timestamp. Side effects: extra lineage and replay cost; no frozen mutation.

B. **Owner-authorized native key correction:** include full OHLC/version and validate before storing seen identity. Side effects: frozen edit; cache/replay identities and golden outputs change; rerun all downstream tests and revalidate models.

#### My recommendation

A until correction/version semantics are owner-governed. Never silently ignore a valid correction.

#### Acceptance and regression tests

Identical same-key retransmission is idempotent; changed high/low with same close/volume/time must produce corrected output or a named refusal; invalid first then valid correction must not be lost; input contract validation must precede native admission.

### P-012

#### Auditor claim (short quote)

“E04 pads skipped ATR outputs only on the left, shifting ATR values against later timestamps after an invalid middle candle.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e04_volatility/engine.py:852–895` (invalid H<L returns without state output), `:1157–1178` (`run_engine` collects only non-None states), `:1241–1258` (`atr_series_for` prepends floor until lengths match), `apex/data_catalog/contracts.py:185–239` (bounds validation rejects OHLC violations), `tests/unit/test_e04_volatility.py:756–763`, and `tests/integration/test_cp3_engines.py:28–36` (consumer assumes 1:1 sequence). Producer entry is the validated public observation window before the E04 converter; no direct caller provides timestamp-keyed ATR join here.

#### Reproduction (command, probe file, actual result)

No malformed bar was passed to E04: repository `validate_market_observation` rejected the crafted H<max(O,C) observation as `QX_INVALID` before any engine call. Raw output: `AUDIT/probes_V8/P-012.out`. The existing suite test `test_atr_series_for_e03_alignment_and_floor` is included in the 227-pass run, but asserts length/finite padding, not invalid-middle timestamp alignment. No raw reproduction of the audit's direct malformed-engine example is claimed.

#### Verdict and reasoning

**PARTIAL.** Source flow shows a skipped E04 state shortens `atr_series` and the adapter only prepends `ATR_FLOOR`; if invalid bars reach this public dictionary API, middle alignment can be wrong. But such input violates the frozen observation contract and is rejected upstream. I did not independently execute the invalid path, so I do not treat it as a confirmed PAPER-path defect.

#### Root cause

Batch API represents state output as a compact list without timestamp-to-input index mapping, then pads only at the left. The producer contract is the upstream defense.

#### Direct impact

If an invalid item bypasses validation, an ATR value may be paired with a different original index. No compliant input sequence reproduced that condition.

#### Secondary effects and interactions (upstream/downstream)

E03 prior ATR and E05/E06 ATR inputs are index consumers, so alignment errors would matter. Upstream validated `MarketObservation` bounds mitigate the scenario in the standard path. This finding does not show future leakage or a problem with valid all-closed sequences.

#### Contract and decisions

Global MarketObservation rules (`apex/data_catalog/contracts.py:185–239`) reject `H<max(O,C)` / `L>min(O,C)` and `H<L`; E04 §3.1 tags invalid input Q0 and freezes ATR (`APEX_GEN5.md:5039–5045`). No later decision authorizes treating rejected observations as valid. Contract/validator take precedence over a direct malformed dictionary call.

#### Frozen status and non-frozen alternative

E04 is frozen; `contracts.py` is also frozen. A non-frozen adapter should accept only validated observations and join state results by `state.as_of` to source close time, with explicit missing slots. In-engine list alignment changes output shapes and identities; an owner ruling and downstream replay/fixture updates would be required.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Non-frozen validation + timestamp join (preferred):** reject malformed inputs before E04, maintain an index/time map, and refuse a missing slot. Side effects: named refusals and adapter/schema tests; no frozen edit.

B. **Owner-authorized output alignment:** emit indexed optional values or timestamp-keyed ATR. Side effects: E04 API change, frozen approval, all E03/E05/E06 consumer fixtures and replay identities must be updated.

#### My recommendation

A. Run a future adversarial malformed-input test only in an explicitly non-production validation harness; do not use it as evidence for valid PAPER flow.

#### Acceptance and regression tests

Validated all-valid observations preserve exact time/value alignment. Adapter rejects invalid bars before E04. If native malformed-input behavior is separately tested after owner approval, assert missing index yields sentinel/refusal rather than a shifted neighboring ATR.

### P-013

#### Auditor claim (short quote)

“E04 replay key omits `boll_k`; same-instance compute returns old snapshots after a parameter change.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e04_volatility/engine.py:116–130` (parameter schema), `:524–537` (`bollinger_width` uses k), `:1193–1239` (compute builds partial replay payload), `apex/engines/base.py:169–203` (cache semantics), and producer chronology at `apex/ops/engine_context.py:2459–2500`. Caller grep found E04 batch compute, the `volatility_stream`, and unit tests. `compute`’s cache signature lists only `atr_short`, `atr_long`, `hv_window`, `ewma_lambda`, and `ljung_m`.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=.:AUDIT/probes_V8 python3 AUDIT/probes_V8/P-013.py`; 55 validated observations, same instance, same `as_of`, `boll_k=2` then `3`: second call returned same object/snapshot IDs; a fresh E04 instance at `boll_k=3` returned a different snapshot. Raw output: `AUDIT/probes_V8/P-013.out`.

#### Verdict and reasoning

**CONFIRMED.** `boll_k` affects Bollinger width but is absent from the replay payload. The native compute path recomputes then returns cached events under the collided key. As in P-006, the current producer typically owns a single stream per cell and does not demonstrate parameter mutation on that live stream; API correctness is proven, incident frequency is not.

#### Root cause

Incomplete parameter identity in E04’s replay key; only five selected values are serialized.

#### Direct impact

Same-instance use with changed `boll_k` returns stale feature/snapshot payload despite different fresh-instance output.

#### Secondary effects and interactions (upstream/downstream)

Bollinger width/squeeze can affect E04 context, and E04 evidence/ATR flows to E03/E05/E06. Current producer’s stream is initialized once per cell, reducing ordinary exposure; mutable governance/runtime parameter reload would expose it. No runtime parameter reload/device was tested.

#### Contract and decisions

`EngineBase.build_replay_key` requires the parameter package and canonical payload (`apex/engines/base.py:169–182`); E04 §6/§8 parameter and replay contract (`APEX_GEN5.md:5047–5049`) requires governed parameters. No decision permits dropping effective parameters from identity. Contract governs.

#### Frozen status and non-frozen alternative

E04 is frozen. Producer can create a fresh per-version E04 stream when the effective parameter package changes and never reuse cached results across package versions. Native full-parameter key correction invalidates cache keys and snapshots; golden outputs, E03/E05/E06 integration and dependent calibrations/training require revalidation.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Producer versioned stream:** parameter package change ends the old stream and starts a fresh state. Side effects: warm-up restart and more compute; explicit lineage required.

B. **Owner-authorized native complete digest:** hash every effective parameter and package/code identity. Side effects: frozen change and complete replay/cache invalidation, fixture and downstream revalidation.

#### My recommendation

A for current runtime. Resolve a frozen correction before a long-lived E04 instance accepts parameter changes.

#### Acceptance and regression tests

Change each effective parameter one at a time on a same instance and compare against fresh-instance oracle; changed parameters must not alias; identical repeated input must remain deterministic. Include `boll_k`, which is explicitly shown to change snapshot output.

### P-015

#### Auditor claim (short quote)

“Three failures are counted per candle despite contract text requiring three consecutive days.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e04_volatility/engine.py:627–656` (`nondirectional_test`), `:1087–1101` (`drift_streak` increment/reset and threshold), E04 parameter defaults/validation at `:116–130`, `APEX_GEN5.md:5546–5547` and §8.8, plus producer chronological hourly/daily stream in `apex/ops/engine_context.py:1469–1483,2459–2500`. The code comment itself calls this “per-bar evaluation”; it increments one streak for each emitted candle and has no UTC-day grouping.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=.:AUDIT/probes_V8 python3 AUDIT/probes_V8/P-015.py`. Sixty-five valid synthetic hourly bars were used; in-memory governed test overrides forced the statistical failure condition (`nondir_corr_thr=-1`, `nondir_p_thr=1`) to isolate the counter. `EV_VLT_002` began at bar 34 with `drift_streak=3`; subsequent bars continued to emit. Output: `AUDIT/probes_V8/P-015.out`. The parameter-forced probe does not show that the defaults trigger on a real market series.

#### Verdict and reasoning

**CONFIRMED.** When its per-bar statistical condition is met, the counter advances on each hourly observation and the threshold name/default says days, so three qualifying bars can represent hours. The code-versus-contract mismatch is proven; default-condition prevalence is not.

#### Root cause

No daily bucketing or UTC boundary exists around the per-bar counter. `drift_consec_days` is applied directly to bar observations.

#### Direct impact

At intraday timeframes, the RS fallback/warning can occur after three bars rather than three daily observations.

#### Secondary effects and interactions (upstream/downstream)

E04’s YZ/RS estimator and warning flows into volatility state consumed downstream by E03/E05/E06. Producer can observe timeframe but currently feeds every CLOSED bar. No three-day real market sequence was available; no trading effect is claimed.

#### Contract and decisions

E04 §8.8 at `APEX_GEN5.md:5546–5547` says three consecutive days; formula-level daily PIT language also uses close timestamps. No later owner decision changes “days” to “bars.” Contract governs over code comment and parameter name.

#### Frozen status and non-frozen alternative

E04 is frozen. Producer can aggregate the failure predicate to UTC-day observations before allowing a daily fallback gate; however, native E04 may still emit its warning. Native correction changes event timing, state snapshots and risk context; fixtures/replay and any dependent model calibration require revalidation.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Producer daily gate:** suppress/qualify the E04 warning for consumers until three UTC days; side effects: alternate producer-side status and duplicate-event prevention.

B. **Owner-authorized E04 correction:** track day-level streaks. Side effects: frozen-file change, output hashes/timing, golden fixtures and downstream backtests/training revalidation.

C. **Owner redefinition:** formally define the parameter as consecutive bars. Side effects: contract/owner policy change; all timeframe behavior must be retested.

#### My recommendation

A short-term; ask the owner to choose between daily and per-bar semantics before native change.

#### Acceptance and regression tests

Force consecutive failures on 1h, 4h, 1d; three qualifying hourly bars must not mean three days under current prose; three UTC days must cross threshold exactly once. Verify resets, missing bars and timezone boundaries.

### P-016

#### Auditor claim (short quote)

“Before 100 returns, E04 uses EWMA in the GARCH field but its state and EvidenceEvent omit degraded fallback provenance.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e04_volatility/engine.py:380–445` (`garch_mle_fit`), `:699–752` (`VolatilityState` payload), `:852–1030` (GARCH status and EWMA fallback state), `:1111–1143` (state/event output), `:1298–1332` (`_to_evidence`); `APEX_GEN5.md:5065–5074` and §3.4.1 at `:5056–5080`; E04 output status at `:1136–1155`. Direct caller grep found `run_engine`, `E04VolatilityEngine.compute`, producer stream and tests. `engine.output()` exposes `garch_status`, but `VolatilityState`/EvidenceEvent has no such field.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=.:AUDIT/probes_V8 python3 AUDIT/probes_V8/P-016.py`; 55 valid bars: `garch_status=insufficient`, `state.garch_vol==state.ewma_vol`, `VolatilityState` has no `garch_status`; emitted event is `validity=VALID`, `resolution=Q2`, explanation only lists regime/ATR/VolRatio/Q tag. Raw result: `AUDIT/probes_V8/P-016.out`.

#### Verdict and reasoning

**PARTIAL.** The status/provenance gap is confirmed. But “insufficient” warm-up before the estimator minimum is not necessarily the same failure as a diverged fitted GARCH fallback; it is expected startup behavior. Contract §3.4.1 expressly requires degraded fallback provenance where fallback is used, yet the exact quality tag for normal insufficient warm-up is not fully specified. The row should not equate every early warm-up with model divergence.

#### Root cause

GARCH status lives only on the mutable engine object; the emitted state carries a numeric `garch_vol` but not estimator identity/status. The EvidenceEvent serializer further omits it.

#### Direct impact

An external reader cannot distinguish fitted GARCH from an EWMA substitute using the public state/event alone.

#### Secondary effects and interactions (upstream/downstream)

Calibration/replay may conflate estimator sources. Hard risk bypass or an unsafe order was not shown; fallback is explicitly allowed for diagnostics/context if degraded provenance is carried. Producer has access to engine status but its regular EvidenceEvent path does not map it.

#### Contract and decisions

E04 §3.4.1 (`APEX_GEN5.md:5056–5060`) permits deterministic analytical fallback only with degraded quality/provenance and forbids decision usability upgrade; §3.4 discusses GARCH→EWMA. No later decision removes that status obligation. Contract governs, with warm-up-versus-divergence distinction preserved.

#### Frozen status and non-frozen alternative

E04 is frozen. Non-frozen E04 producer can add `garch_status`, selected estimator and `decision_usable` to a sidecar/lineage field, or withhold fallback values from decision-facing gates. Sidecar changes fabric identity/consumer tests. Native state change alters serialized snapshots and fixtures; retrain/revalidate consumers if estimator choice is a learned feature.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Producer provenance sidecar (preferred):** carry exact engine status beside native EvidenceEvent and gate it as degraded where required. Side effects: adapter schema and fabric/hash changes, tests for both insufficient and divergence.

B. **Owner-authorized native state extension:** include status and estimator. Side effects: frozen file, state snapshot schema/hashes and E04/E05/E06 fixtures; dependent training/backtests revalidated.

#### My recommendation

A; distinguish `insufficient` warm-up from actual failed-fit fallback, but never publish an EWMA substitute as fitted GARCH.

#### Acceptance and regression tests

At 55 and 100+ returns, assert status and estimator on state, event, store roundtrip and consumer. Force optimizer failure separately from insufficient sample; only status-defined fallback receives the prescribed degraded treatment, and no risk veto is bypassed.

### P-018

#### Auditor claim (short quote)

“CONVENTIONAL FVG `StructuralRole` is 0.5 regardless of BOS input; structure is not reflected in salience.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e05_fvg/engine.py:332–400` (`classify_fvg`), `:406–438` (`compute_salience_and_premium`), `:481–535` (`process_bar` input and object construction), `:676–701` (`run_engine`), `:762–803` (`E05FVGEngine.compute`), contract §2/§3.4 at `APEX_GEN5.md:5750–5751,5849–5860`, and producer `apex/ops/engine_context.py` E05 wiring via `grep -rn`. The API accepts `struct_role` as a separate scalar; `bos_events` affects only inverse classification. E05’s wrapper does not pass a `struct_role` argument to `run_engine`, so it defaults to 0.5.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=.:AUDIT/probes_V8 python3 AUDIT/probes_V8/P-018.py`; a three-bar FVG shape was adjusted to satisfy all MarketObservation OHLC bounds, then passed repository validation. Native FVG processing with no BOS, BOS_UP, BOS_DOWN and identical default `struct_role=0.5` returned CONVENTIONAL with role 0.5 and salience 0.4096153846 in each case. Output: `AUDIT/probes_V8/P-018.out`.

#### Verdict and reasoning

**PARTIAL.** The observed equality is real for the test because the caller holds `struct_role` constant; it does not prove BOS input should mutate that explicit independent argument. However, the normative contract defines role from same/opposite BOS within three bars, while the public EngineBase wrapper has no `struct_role` input and calls `run_engine` without deriving one. Thus the substantive native producer wiring omission is confirmed, but the auditor’s BOS-events-only comparison overstates the causal test.

#### Root cause

StructuralRole is a separate scalar in the low-level API, but not computed from the supplied `bos_events`; the high-level E05 `compute` path does not supply the scalar, leaving the default 0.5.

#### Direct impact

Normal EngineBase E05 outputs may give all FVGs neutral structural role rather than contract-defined 1/0 based on E01 BOS, changing the structural contribution to salience.

#### Secondary effects and interactions (upstream/downstream)

E05→E06/FVG context and evidence strength may differ. The producer does provide E01 structure elsewhere, but no explicit E01-to-E05 `struct_role` binding was found in the wrapper. No decision or order was run. `inverse_enabled` is default false and unrelated to normal StructuralRole enrichment.

#### Contract and decisions

E05 §2 defines StructuralRole from E01 (same-direction BOS 1.0, inside range 0.5, opposite BOS 0.0) and §3.4 weights it in salience (`APEX_GEN5.md:5750–5751,5849–5860`). No later CP3 decision overrides that rule. Contract governs; the default argument does not redefine the high-level contract.

#### Frozen status and non-frozen alternative

E05 engine is frozen. A non-frozen adapter can derive the per-index role from E01 BOS history and pass it through a producer-side API that supports it, or add a wrapper path that calls the low-level FVG engine with role values. Side effects: changed salience/object identity and producer tests. Native parameter/compute signature fix changes snapshots, fixture hashes, FVG/E06 replay outputs and requires retraining/recalibration if salience-derived features are used.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Non-frozen producer role binding (preferred):** compute same/opposite/no BOS role from already available E01 events and inject per index. Side effects: producer code and event identity changes; no frozen mutation.

B. **Owner-authorized E05 native API extension:** consume aligned BOS history and derive StructuralRole internally. Side effects: frozen change; golden fixtures, snapshot/replay identities, E06 consumers and training baselines need revalidation.

#### My recommendation

A. Do not claim the low-level `bos_events` list is itself supposed to populate `struct_role`; do fix/verify the high-level contract input path.

#### Acceptance and regression tests

Same valid FVG with role 0.5/1.0/0.0 must change salience by exactly the governed `w_s` contribution. High-level E05 compute with E01 no-BOS/same-BOS/opposite-BOS histories must generate role 0.5/1/0 with PIT-aligned timestamps; test producer and direct low-level API separately.

### P-019

#### Auditor claim (short quote)

“At `max_age_bars=1`, a fully filled FVG in the same bar is then expired; history logs both and terminal fate is EXPIRED.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e05_fvg/engine.py:481–624` (`process_bar` lifecycle ordering), `:223–250` (`update_snapshot`), contract §3.3/expiry and §3.7 at `APEX_GEN5.md:5865–5890,6060–6079`, `PHASE2_DECISION_LOG.md:76` (ISSUE-CP3-004), and producer crosswalk `apex/ops/engine_context.py:1862–1882,1922–1926`. Caller search found `process_bar`, batch `run_engine`, EngineBase compute and tests. Owner decision CP3-004 resolves the age boundary inclusive (`age >= max_age`), not fill-versus-expire precedence.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=.:AUDIT/probes_V8 python3 AUDIT/probes_V8/P-019.py`; FVG lifecycle used a closed valid generated bar that fully crossed the zone. Native events were TOUCH, MITIGATED, FILLED, EXPIRED; final history fate was EXPIRED at age 1. Raw output `AUDIT/probes_V8/P-019.out`.

#### Verdict and reasoning

**PARTIAL.** Both transitions are produced in one update and the last fate is EXPIRED, as claimed. But CP3-004 explicitly makes age expiry boundary-inclusive; the unresolved portion is only terminal precedence and whether a fully filled object should remain FILLED or be expired in the same bar. No owner rule was found that makes the audit’s preferred priority normative.

#### Root cause

Lifecycle updates run fill before expiry and do not stop after the first terminal transition; expiry assignment overwrites FILLED and appends a second terminal event.

#### Direct impact

At the boundary, consumers may see both fill and expiry events while the object’s final state says EXPIRED.

#### Secondary effects and interactions (upstream/downstream)

Producer bridge maps both FILLED and EXPIRED into a filled boolean in one downstream context; that mitigates immediate zone selection but loses terminal distinction. Persistence keeps full event/state identity; replay forensic state can remain ambiguous. No trading action observed.

#### Contract and decisions

E05 §3.3 specifies full crossing as fill and expiry at age threshold; `ISSUE-CP3-004` (`PHASE2_DECISION_LOG.md:76`) explicitly resolves only `age >= max_age` and freshness threshold. There is no later decision establishing fill precedence. Apply owner decision to the boundary; do not infer an unrecorded terminal priority. Contract remains ambiguous for simultaneous conditions.

#### Frozen status and non-frozen alternative

E05 is frozen. Producer can preserve ordered terminal events and attach a boundary ambiguity/refusal rather than selecting one silently; this may still not repair E05 object state. Native priority correction alters lifecycle snapshots, evidence identity and fixture expectations; all FVG/E06 bridge/replay tests and dependent training need revalidation.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Owner decision before semantic change:** record precedence and exact boundary; then producer can enforce it for decision-facing view. Side effects: no implementation change until owner responds; avoids invented rule.

B. **Owner-authorized native first-terminal-wins:** on full fill, skip expiry in same bar or vice versa according to ruling. Side effects: frozen code, different terminal history/hash, fixture and replay updates.

#### My recommendation

A. Preserve both raw facts for forensic trace, but do not collapse one into the other until the owner resolves priority.

#### Acceptance and regression tests

Exact-age full fill and non-fill must yield one governed terminal fate/event, stable snapshot, deterministic order independent of call order, and idempotent replay. Test age `max-1`, `max`, `max+1`; keep CP3-004’s inclusive expiry rule unless owner supersedes it.

### P-020

#### Auditor claim (short quote)

“E05 expiry returns before `update_snapshot`, so the terminal payload is paired with the old snapshot ID.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e05_fvg/engine.py:223–250` (canonical fields/update), `:550–624` (lifecycle mutation and expiry `continue`), `:625–666` (merge mutation), `:833–868` (`_to_evidence`), `apex/ops/engine_context.py:1862–1882` (snapshot-based E05 admission crosswalk), plus public event persistence path and D31 record at `PHASE2_DECISION_LOG.md:564–571`. Consumer grep found merge, `run_engine`, EngineBase compute, producer `fvg_objects` lookup and downstream zone bridge.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=.:AUDIT/probes_V8 python3 AUDIT/probes_V8/P-020.py`; a valid closed synthetic bar filled and expired an injected valid FVG on the same lifecycle update. Stored terminal fate was EXPIRED with old ID `acb919c2…`; recomputing the real object’s canonical snapshot produced `c9b15817…`, unequal. Output: `AUDIT/probes_V8/P-020.out`. The related P-019 output confirms the terminal path.

#### Verdict and reasoning

**CONFIRMED.** Expiry branch sets fate/quality and exits before snapshot update. This defect is specific to the expired mutation; non-expired and some fill paths update snapshots. Do not generalize to every terminal FVG.

#### Root cause

Mutable terminal fields change after the last canonical hash, and expiry bypasses `update_snapshot()`.

#### Direct impact

The persisted/emitted snapshot ID does not identify the terminal payload it accompanies.

#### Secondary effects and interactions (upstream/downstream)

Producer joins native FVG object to event by snapshot ID; stale ID may still match both event and same in-memory object, so it can pass the crosswalk while undermining forensic content-address verification. D31 requires preservation of full terminal QX evidence, not stale identity. No acceptance by actual SQLite or decision was attempted in this probe.

#### Contract and decisions

E05 §5.4 requires SHA-256 over canonical full state (`APEX_GEN5.md:5901–5913`); D31 (`PHASE2_DECISION_LOG.md:564–571`) authorizes preserving the full QX terminal event and forbids dropping/relabelling it. D31 does not authorize inconsistent identity. Owner decision governs terminal retention; contract governs hash consistency.

#### Frozen status and non-frozen alternative

E05 is frozen. Producer may verify `snapshot_id == canonical_hash(current_terminal_payload)` before persistence and refuse or assign a versioned wrapper identity when inconsistent; it must not rewrite/remove D31-required evidence. Native fix changes IDs for expiry terminal objects, invalidates caches/crosswalk and all golden/replay snapshots; revalidate downstream and retrain if identity enters features.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Non-frozen identity assertion/sidecar (preferred containment):** preserve original event verbatim, attach validation mismatch and keep it out of decision use until owner-approved terminal version is available. Side effects: extra diagnostic lineage and potential refusal.

B. **Owner-authorized native snapshot update:** recalculate after every terminal mutation. Side effects: frozen E05 change, updated golden/hash baselines, event-store and producer regression tests; no schema change implied.

#### My recommendation

A in the producer now, then B only if owner explicitly authorizes a frozen correction. Never alter D31’s retention requirement.

#### Acceptance and regression tests

For fill-only, expiry-only and same-bar fill+expiry, stored snapshot equals canonical payload for final object; event/store readback preserves full QX; producer crosswalk maps terminal view as terminal, and replay is byte-stable.

### P-021

#### Auditor claim (short quote)

“Native E05 terminal evidence is emitted ACTIVE at creation availability, but PAPER keeps QX and maps final zone fate out of active fabric.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e05_fvg/engine.py:833–868` (`_to_evidence` maps every object to `fate_state=ACTIVE` and created-at timestamps), `apex/ops/engine_context.py:1862–1882` (E05 object fate crosswalk before fabric assembly), `:1922–1926` (bridge filled/fate context), `apex/fabric/evidence.py:335–404` (assembly/admission); owner D31 at `PHASE2_DECISION_LOG.md:564–571`. `grep -rn` found `_to_evidence` called for active+history objects in `E05FVGEngine.compute` (`engine.py:779–803`), then producer persistence and bridge projection.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=.:AUDIT/probes_V8 python3 AUDIT/probes_V8/P-021.py`; a native EXPIRED FVG produced `validity=DEGRADED`, `resolution=QX`, but `fate_state=ACTIVE`; both event and availability time were the creation timestamp. Raw output: `AUDIT/probes_V8/P-021.out`. The producer correction is directly evidenced in source, not reproduced end-to-end against a database.

#### Verdict and reasoning

**PARTIAL.** The native emitter is wrong for a current terminal state. However, the audit itself identifies the PAPER guard, and producer crosswalk uses matching object fate to transition EXPIRED/INVALIDATED/MITIGATED and FILLED away from active before assembling fabric. D31 binds full QX terminal persistence and explicitly rejects deletion/relabelling. Remaining issue is native/API consumers outside this producer and terminal event-time/availability semantics; the audit’s implication that PAPER admits terminal events is false for the inspected crosswalk.

#### Root cause

`_to_evidence` reports object’s current terminal fate only in `condition_state`/resolution but hardcodes lifecycle ACTIVE and uses creation time; producer later repairs lifecycle in a separate decision view.

#### Direct impact

Direct consumers can see an EXPIRED condition carried as ACTIVE with old availability; PAPER fabric view applies a more conservative fate transition.

#### Secondary effects and interactions (upstream/downstream)

Producer maps FILLED to MITIGATED and terminal non-filled states to their corresponding terminal lifecycle; fabric admission sees corrected refs. The raw event is retained/persisted as required by D31, so this native inconsistency remains visible to forensic readers/other integrations. No device data was checked.

#### Contract and decisions

E05 lifecycle and event-time rules (`APEX_GEN5.md:5865–5890,5901–5913`) require lifecycle and PIT facts; D31 (`PHASE2_DECISION_LOG.md:564–571`) is the later binding decision: terminal QX events are retained unchanged, not dropped, relabelled or upgraded. Thus audit claim about terminal loss is superseded/false for current PAPER producer; emitter inconsistency beyond D31 remains.

#### Frozen status and non-frozen alternative

E05 is frozen. Producer can maintain separate immutable forensic event and decision-view projection, with event availability at the actual terminal transition and admission inactive. Side effects: new projection identity and tests; preserves raw D31 event. Native correction needs owner exception, snapshot/version and fixture updates.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Keep D31 persistence; correct non-frozen decision view (preferred):** retain native full QX event exactly, apply current final fate/time only to separate fabric reference. Side effects: producer view hash and persistence tests; no deletion/relabeling.

B. **Owner-authorized native lifecycle/time correction:** terminal object emits a terminal version and transition availability. Side effects: frozen change plus changed snapshots/event hashes and downstream regression/retraining.

#### My recommendation

A. Existing producer crosswalk is the right boundary; strengthen it with tests for actual transition time and public SQLite round-trip, preserving D31’s byte-level terminal evidence.

#### Acceptance and regression tests

Direct emitter assertion distinguishes initial active from terminal state. PAPER DB roundtrip retains original QX event; producer fabric excludes terminal from active members and keeps transition record/availability at decision time. Verify D31 tests and no terminal-to-Q5 promotion.

### P-022

#### Auditor claim (short quote)

“E05’s `_processed` key is `(index,ts)`; a valid same-time wick correction is silently ignored.”

#### What I read (files, line ranges, functions, callers)

`apex/engines/e05_fvg/engine.py:463–490` (`FVGEngine` state and process key), `:481–624` (lifecycle), `:676–701` (fresh batch driver), `:762–803` (EngineBase wrapper constructs fresh `run_engine`), and producer E05 compute/bundle path; grep callers include direct `process_bar`, `run_engine`, EngineBase compute and unit tests. The standard wrapper creates a new `FVGEngine` for each batch call.

#### Reproduction (command, probe file, actual result)

`PYTHONPATH=.:AUDIT/probes_V8 python3 AUDIT/probes_V8/P-022.py`; an FVG was created from three valid contract-checked bars. A changed but still valid wick at same index/time was submitted; second call returned `[]`, and active zone bounds stayed `(101,102.5)` despite corrected bar. Raw output: `AUDIT/probes_V8/P-022.out`.

#### Verdict and reasoning

**PARTIAL.** Direct streaming `FVGEngine` correction is ignored by the key. But `run_engine`/`E05FVGEngine.compute` constructs a new FVGEngine per window, so this probe does not establish that normal PAPER reuses the same instance across a correction. The direct API issue is confirmed; producer incidence remains unproven.

#### Root cause

`_processed` treats index and timestamp as complete identity and has no content hash/revision or replay-from-correction semantics.

#### Direct impact

A correction in a long-lived streaming instance does not re-evaluate the affected FVG or lifecycle.

#### Secondary effects and interactions (upstream/downstream)

A revised wick can alter zone detection, fill/mitigation and E06 context, but fresh-window batch recomputation may reflect corrected bars. Producer store correction semantics and actual replay were not inspected end-to-end. No order/ledger effect was tested.

#### Contract and decisions

E05 §5 lifecycle/identity and global PIT correction semantics (`APEX_GEN5.md:5901–5913,6051–6075`) require deterministic identity and historical versioning; ADR-P2-007 warns example values are illustrative. No owner decision authorizes content-insensitive correction handling. Contract governs.

#### Frozen status and non-frozen alternative

E05 is frozen. Producer must construct a new versioned window/engine when source content hash changes and invalidate downstream derived snapshots from that time. This costs recomputation and changes FVG/E06 identities. Native idempotency correction changes processed keys, history and replay/golden outputs; owner exception and full downstream revalidation/retraining are needed.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)

A. **Producer correction replay (preferred):** detect changed observation content hash, restart a bounded FVG window from correction point, supersede old evidence. Side effects: replay latency, lineage and identity changes; no frozen edit.

B. **Owner-authorized native revision API:** content/version-aware processed key with deterministic correction replay. Side effects: frozen change, changed lifecycle identities and golden fixtures; downstream retraining/backtests revalidated.

#### My recommendation

A for the current batch-oriented producer; prove producer correction invalidation before making an operational incident claim.

#### Acceptance and regression tests

Same bit-identical candle remains idempotent; valid same-time wick correction causes recomputation or explicit refusal; corrected and fresh full-window oracle outputs match, including lifecycle, snapshot identity, and E06 downstream context.

## New findings not in the audit

None identified in this second tranche. This is not a claim that the full E03–E06 scope has no additional findings.

## Rows not verified or incomplete

The exact report text was read for P-001–P-013, P-015, P-016, P-018–P-022. For these, only the cited functions/ranges and direct callers identified by targeted `grep -rn` were examined; the mandatory complete-file read of every engine, full test file, complete context sections, all transitive callers/callees and all requested fixtures has not been completed. P-012's invalid-middle probe was deliberately not run because that input fails the mandatory data contract; only the malformed-path source logic and upstream guard were inspected. No real database/device/data validation was performed.

P-023–P-039 have not yet been independently assessed. P-014 and P-017 do not exist in the audit and are excluded, as requested.

## Final counts

Progress tranche (20 report IDs): CONFIRMED 12; PARTIAL 8; REJECTED 0; DEVICE-EVIDENCE-NEEDED 0. P-023–P-039 remain unverified; these are not full-scope V8 counts.
