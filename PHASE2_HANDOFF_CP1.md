# PHASE2 HANDOFF — CP-1 → consumed by CP-2 (and CP-8 closeout)
Stage: CP-1 — Foundation (packaging/config/errors/bus/identity/data_catalog/quality/params/base) + Feature Fabric §3.12/3.13
Rules (PROTOCOL P16): author = CP-1 executor (or its continuation session — state which, first line of STATUS). ≤400 lines, nine headings below in order. Successors read ONLY this file + their own prompt/law/checkpoint sections; interfaces listed here are the public contract they may code against. First STATUS line: `LAW-ACK: G1..G20 + P1..P21 read <UTC>`.

## STATUS
LAW-ACK: G1..G20 + P1..P21 read 2026-09-12T00:00:00Z (all law files read in full before STEP 3 claim; blueprint ranges read per assignment list in PHASE2_CHECKPOINTS.md §CP-1).
Author: CP-1 executor (single session, no continuation; board claim + all code + all tests + this handoff written in one session, 2026-09-12).
complete — commits pushed; suite totals: 158 passed / 0 failed (pytest 8.4.2, `PYTHON=<venv> ./scripts/run_all_tests.sh`).
Environment note: sandbox = Linux x86_64, CPython 3.11.2, venv at /home/user/apex-venv (outside repo; PEP 668 blocks system pip). Target runtime = Termux/aarch64 (owner device); the frozen Ch.1 SBOM pins govern there. No pip-install-without-lock ever (G16).
Branch note: this session's commits are on `arena/01a09373-upstage` (Arena-tied session branch of main@bc91ed4); on the owner's repo the same commit chain is what would land on `main` per ADR-P2-012. Recorded in DECISION_LOG §B/CP-1 (ISSUE-CP1-014).

## DELIVERED
| file | purpose | blueprint | MATRIX Part III row |
|---|---|---|---|
| pyproject.toml, requirements.lock | packaging: nine SBOM pins exact; pytest dev-only `[tests]` extra; no dotenv | Ch.1 + ADR-P2-002 | P1·P2·P3 |
| .gitignore | ADR-P2-013 hygiene list | ADR-P2-013 | P1 |
| README.md | skeleton: install/test/run-procedure placeholder (CP-7 finalizes run blocks) | §9.5 tree | P1 |
| scripts/run_all_tests.sh | full-suite runner (venv-aware) | §9.5 tree | P1 |
| apex/__init__.py, apex/config.py | nine env names EXACT + stdlib .env parser (no shadowing, no dotenv) + params loader | §2.5 + §9.5-12 + G16 | CFG1·CFG2 |
| apex/errors.py | all 23 Ch.7 rows verbatim + WaveOutError + frozen Wave-Out list | Ch.7 L14643–14671 | ERR1 |
| apex/bus.py | in-process asyncio bus; P0 synchronous; P0/P1 never dropped; P2/P3 shared lane drop-oldest+log; raw-candle queue 1000 drop-oldest | §9.5-10 + AI.12 + AI.8/AI.9 + Ch.23 | BUS1·BUS2 |
| apex/identity/canonical_json.py, uuid_v7.py, snapshot.py, hashes.py | canonical serializer; ONE uuid_v7 (RFC 9562); snapshot envelope + governed as_of; content_id/replay_key | GLOBAL IDENTITY L4104–4158 + AI.3 + §9.5-5 | ID1..ID5 |
| apex/data_catalog/contracts.py | MarketObservation + fail-fast validation order; §3.12 FeatureID/FeatureContract; 24-field EvidenceEvent; catalog.get result shape | AI.4 + §3.12 + Ch.5 + L18185 | DC1·DC2 |
| apex/data_catalog/{atomic,molecular,organismic,math,performance}/ + catalog.py | 74-feature registry as tier packages (ADR-P2-006); §3.13 enforcement (74==74, F49 REMOVED-slot, F56 always-UNAVAILABLE); tier caches (ATOM never / MOLE 5 / ORGN LRU-100); ATOM failure halts pipeline; catalog.get only public read | §3.12 L13529–14371 + §3.13 L14371–14382 + Ch.5 | FB1..FB4 |
| apex/data_catalog/store/sqlite_store.py | SQLite WAL store: Ch.4 DDL + Ch.5 DDL + AI.5 raw_revision/raw_manifest + migrations + immutability triggers + governed retention purge + evidence insert with 24-field validation | Ch.4 L14383–14544 + Ch.5 L14545–14642 + AI.5 + §2.6 + P12 | ST1..ST4 |
| apex/data_catalog/ingest/toobit_public.py | public Toobit client (six endpoints), wire maps, 3-attempt 1s/2s/4s backoff, OI failure → MISSING never 0, funding alert |0.001| | Ch.16 L16750–16936 | IN1 |
| apex/quality/vector.py, numerical.py, pit.py | §2.1 13 gates + 7 components + 4 vetoes + Q_min + Q_window; §2.2 two-tier eps + quantize + division guards + core formulas; §2.3 PIT windows + MTF states + snapshot determinism | §2.1/§2.2/§2.3 (Ch.2) | Q1..Q4 |
| apex/engines/__init__.py, base.py | FROZEN engine base: v4.0.0 interfaces; lifecycle CANDIDATE→CONFIRMED→ACTIVE→terminal (forward-only); replay_key idempotency + TTL cache discarded on code_revision change; emission→24-field validation; Wave-Out plumbing; catalog-only data access; frozen per-engine EPS | AI.2/AI.3/AI.4/AI.11/AI.12 + §2.2 + Ch.5 | EB1·EB2 |
| params/{universe_v1,risk_defaults_v1,setup_weights_v1,quality_weights_v1,toobit_wire_v1,e11_params_v4}.yaml | six frozen YAMLs; values literal from §9.5/Ch.10/§2.1/Ch.16; code loads never hardcodes | §9.5 L20228–20243 + Ch.10 + §2.1 + Ch.16 | PR1..PR6 |
| tests/unit/ + tests/integration/ | 158 tests incl. T-DC/T-PIT/T-ID/T-CL/T-OM/T-RS/T-MON-001 + every §2.x rule + DDL verbatim-equivalence + import-chain | AI.10 + AI.12 + §8 id list | TS1 |

## INTERFACES
(module | class/function | signature | semantics | version) — exhaustive for everything CP-2 consumes; nothing invented, everything cited.

apex.config
- ENV_NAMES: List[str] — the nine frozen env names (§9.5-12), exactly.
- parse_dotenv(path) -> Dict[str,str] — stdlib .env parser; unknown name/malformed → ValueError (fail-closed).
- Config(env_path=None): props apex_env, allow_signed, economic_gate_signed, toobit_api_key, toobit_api_secret, telegram_bot_token, telegram_owner_chat_id, telegram_watchdog_chat_id, sqlite_path; validate_environment() (PAPER/LIVE/RESEARCH/BACKTEST only; SHADOW → ValueError). Real env never shadowed by .env. repr masks secrets. | v4.0.0
- load_params() -> Params — Params[name] / .universe() / .risk_defaults() / .setup_weights() / .quality_weights() / .toobit_wire() / .e11_params() -> Dict. Values ONLY from params/*.yaml (§9.5-10). | v4.0.0
- PARAMS_FILES: Dict[str,str] — name → YAML filename.

apex.errors
- ERROR_REGISTRY: Dict[str,ErrorCode] — all 23 Ch.7 rows (codes exact incl. QX_INVALID, TOO_MAUTC_W2_REQUESTS, RSK-ERR-506, UNAUTHORIZED, VETO_*).
- get_error_code(code) -> ErrorCode — unknown code → KeyError.
- WaveOutError(feature, reason) — the ONLY lawful handling of Wave-Out items; wave_out(feature, reason="OUT_OF_CONTRACT"); WAVE_OUT_FEATURES frozen set. | v4.0.0

apex.bus
- P0/P1/P2/P3 ints; Priority IntEnum; BusEvent(priority:int, topic:str, payload:Any, event_id:str, created_at:float); make_event(priority, topic, payload) -> BusEvent.
- EventBus(lane_maxsize=1000): subscribe(topic, consumer:async fn) / unsubscribe / await publish(BusEvent) — P0 delivered inline (synchronous) in subscription order; P1 dedicated lane (never dropped/blocked; evicts oldest shared item at bound); P2/P3 shared lane (drop-oldest + QUEUE_OVERFLOW_DROP log); start()/await stop(); eviction_log; counts. In-process ONLY (networked bus = Wave-Out). | v4.0.0
- RawCandleQueue(maxsize=1000): await put(item, event_id, topic) — drop-oldest+log on overflow (no backpressure); await get(); qsize(); drop_log. | v4.0.0

apex.identity.canonical_json
- canonical_json(obj) -> str — sorted keys, no whitespace, Decimal→fixed-point string (no exponent; -0→"0"), datetime→`YYYY-MM-DDTHH:MM:SS.fffZ`, NaN/Inf/unsupported → CanonicalJsonError. Byte-stable (hash identity depends on it). canonical_json_bytes(obj) -> bytes. | v4.0.0

apex.identity.uuid_v7
- uuid_v7() -> str — RFC 9562 (48-bit ms | ver 7 | 12-bit rand_a | variant | 62-bit rand_b). THE ONLY implementation (grep-enforced test). Operational-only; never inside snapshot payloads. uuid_v7_timestamp_ms(uuid) -> int. | v4.0.0

apex.identity.snapshot
- canonical_snapshot_id(engine, contract_version, payload:dict) -> str — frozen envelope SHA256; empty context → ValueError("INVALID_SNAPSHOT_CONTEXT_QX").
- governed_as_of_ms(required_artifacts) -> int — as_of = max(availability_time_ms); errors MISSING_REQUIRED_ARTIFACTS_QX / MISSING_AVAILABILITY_TIME_QX.
- SnapshotBarrier(as_of, symbol_scope, timeframe_scope, source_state, manifest_hash, parameter_package_id, code_version, quality_state, observation_windows, mtf_states, overall_mtf, created_at=None) — immutable; .snapshot_id (64-hex, created_at excluded); symbol_scope>10 / timeframe_scope>14 / missing package|code → ValueError; .to_dict(). | v4.0.0
- snapshot_id_from_payload(payload) -> str; manifest_hash(manifest) -> str. | v4.0.0

apex.identity.hashes
- sha256_hex(bytes|str) -> str; content_id(payload) -> str; replay_key(engine_version, contract_version, symbol, timeframe, as_of_timestamp, input_hash, parameter_package_id, code_revision, canonical_payload) -> str (AI.3 field order). | v4.0.0

apex.data_catalog.contracts
- CORE10_SYMBOLS, TIMEFRAMES_14; OIState (AVAILABLE/STALE/MISSING/INVALID/DEGRADED); CandleStatus; CatalogStatus (OK/MISSING/STALE/UNAVAILABLE/INVALID); LifecycleState (+is_terminal); parse_utc_ms(str) -> datetime (strict, else ValueError).
- MarketObservation (frozen dataclass): symbol, timeframe, open/high/low/close/volume (Decimal), oi (Decimal|None — None means MISSING, never 0), timestamp (ISO-8601-ms-Z), sequence, status, source, availability_time, oi_timestamp, oi_lag_seconds, source_health, gap_count, expected_count, completeness_pct, delay_seconds; .is_closed; .content_hash() (duplicate detection hash); .to_dict().
- validate_market_observation(obs, prev_sequence=None) — AI.4 10-step fail-fast order; ValidationError(code, detail) carries the Ch.7 code (E-Q-001/E-NUM-001/E-NUM-002/QX_INVALID).
- oi_state_for(oi, lag_seconds, threshold_seconds) -> (OIState, float) — AVAILABLE 1.0, STALE 0.5, DEGRADED 0.2, MISSING/INVALID 0.0; missing OI never coerced.
- FeatureID/ValidityPolicy/FeatureContract (§3.12 dataclasses, v5.0.0).
- EVIDENCE_EVENT_FIELDS_24 (tuple); EvidenceEvent (24 fields) with validate_24_fields() (engine_id ∈ E01..E12; direction ∈ {-1,0,1}; finite strength/confidence/quality; resolution_class Q0..QX) and to_ddl_row() (L18185 mapping).
- CatalogResult(feature_id, symbol, timeframe, as_of, value, q_component, availability_time, snapshot_id, status, reason). | v4.0.0

apex.data_catalog.catalog
- WindowProvider protocol: async get_window(symbol, timeframe, as_of, bars) -> List[MarketObservation] (CLOSED, ascending, PIT-bounded); async max_availability_time(symbol, timeframe, as_of) -> Optional[str]. (Sync fakes tolerated.)
- FeatureRegistry: register(contract)/lookup(alias|full_id)/all()/count()/tier_counts(). build_registry() -> (FeatureRegistry, computers). 74 slots: ATOM 44 / ORGN 29 (F49 slot registered REMOVED; F56 registered, always UNAVAILABLE) / MOLE 1.
- AtomTierFailure(alias, status, reason) — ATOM INVALID/DEGRADED halts the whole pipeline (§3.12); warmup UNAVAILABLE and CANDIDATE return results (AI.6 gates-stay-open).
- Catalog(params=None, provider=None, code_revision="0"*40): .registry; set_provider(p); set_code_revision(rev) (cache invalidated); verify_completeness() -> {count, tiers} (raises on §3.13 violation); await get(feature_id, symbol, timeframe, as_of, lookback=1, context=None) -> CatalogResult — Ch.5 contract: unknown id → INVALID; future as_of → INVALID (PIT_FUTURE_AS_OF); tier caches (ATOM never cached; MOLE 5 candles; ORGN 50+ LRU-100). Module-level `catalog` instance. | v4.0.0

apex.data_catalog.atomic/organismic/molecular.features
- ATOM_ENTRIES/ORGN_ENTRIES/MOLE_ENTRIES: (num, alias, full_id[, note]) — exact §3.12 identifiers.
- COMPUTERS: Dict[alias, fn(window, params, context) -> (value|None, q_formula_valid:float, status, reason)]. status ∈ {OK, INVALID, DEGRADED, CANDIDATE, UNAVAILABLE, MISSING}. §2.2-defined ATOM formulas implemented exactly (body_ratio/upper_wick/lower_wick 6dp, close_position 4dp, volume_ratio 8dp SMA_20 on t−1, return_k 10dp k∈{1,5,20}, normalized_range 4dp, ATR_14, TR, SMA/EMA/RMA/Wilder, VWAP, OBV, RSI_14, z-scores, Slope, Hurst, Parkinson, Garman-Klass, Rogers-Satchell, theta_maxAge=100, is_bullish/bearish, range, body_size, OI_z, RangeZ, VolRatio). Formula-not-in-CP-1-text features return UNAVAILABLE with deterministic reason (k_*/theta_* F22–30, GARCH, theta_body/vol/invalid — engine chapters own them; see ISSUE-CP1-004/011). ORGN CTXT features needing regime/temporal/HTF context return UNAVAILABLE (ISSUE-CP1-005); OI-dependent return MISSING on absent OI (T-OM). F74 compute_sweep(window, params, context) per §3.12 text (5-candle block, rolling 20-bar extreme, close-back-inside, VolumeZ≥2, 3-block cooldown, theta_sweep gate when context provides it). | v4.0.0

apex.data_catalog.math (tier module)
- sma/ema/rma/true_range/atr_simple/atr_wilder/vwap/obv_series/rsi_wilder/zscore/slope_ols/hurst_rs/parkinson/garman_klass/rogers_satchell/quantize(value, digits) — pure Decimal math, division-guarded (max(|d|, 1e-12)), None on insufficient data (never NaN). | v4.0.0

apex.data_catalog.performance (tier module)
- LRUCache(capacity=100): get/put/__len__; TierCache(): set_code_revision(rev), lookup(super_layer, key, bar_index), store(...) — tier cache discipline. | v4.0.0

apex.data_catalog.store.sqlite_store
- MIGRATIONS (M001_ch4/M002_ch5/M003_ai5/M004_triggers); CH4_DDL/CH5_DDL/AI5_DDL/IMMUTABILITY_TRIGGERS constants; RAW_RETENTION_MONTHS=12; SNAPSHOT_RETENTION_MONTHS=6.
- SQLiteStore(path=None): await open() (WAL/FULL/FK/busy_timeout=5000 + migrations) / await close(); .db (aiosqlite conn); applied_migrations(); await ingest_raw(obs, oi_state) -> event_id (E-VAL-021/022 rejection; duplicate content_hash dedup); await correct_raw(original_event_id, corrected, oi_state, reason, actor) -> new_event_id (SUPERSEDED+CORRECTED+raw_revision+retention_event); await get_window/max_availability_time (WindowProvider); await insert_snapshot(snapshot:dict); await insert_evidence(EvidenceEvent) (24-field validation); await write_manifest(period_start, period_end, content_hashes, parent_manifest_hash) -> manifest_hash; await retention_purge(actor) -> purged ids (governed flag; retention_event rows; ledger/outcome never purged); await table_names(). UPDATE/DELETE on raw_observation + ledger → ABORT (triggers). | v4.0.0

apex.data_catalog.ingest.toobit_public
- ToobitPublicError(endpoint, detail); to_wire_symbol(s) ("BTCUSDT"→"BTC-SWAP-USDT"; unknown → ValueError); to_wire_interval(i) ("1mo"→"1M").
- parse_kline_to_observation(symbol, interval, row, seq) -> MarketObservation (CLOSED; oi=None).
- ToobitPublicClient(session=None): await get_server_time/get_exchange_info/get_depth(symbol, limit=100)/get_klines(symbol, interval, start_ms, end_ms, limit=None) -> List[MarketObservation] (limit ≤ 1000)/get_open_interest(symbol, interval) -> Optional[Decimal] (failure → None = MISSING, never 0)/get_funding_rate(symbol) -> (rate|None, alert:bool) (|rate|≥0.001). 3 attempts, 1s/2s/4s backoff; final error carries RETRY_EXHAUSTED + last code. PUBLIC ONLY — never signed. | v4.0.0

apex.quality.numerical
- EPS_TIER1=1e-12, EPS_TIER2=1e-8, ATR_FLOOR=1e-8; ENGINE_EPS (E01 SCALED, E02/03/05/06/07/08/10/11 1e-8, E04/09/12 1e-12); PRECISION (price10/volume8/quality4/strength4/confidence4/fee10/atr10/return10/body_ratio6); eps_for_engine(id, tick_size=None, closes_20=None); quantize(v, digits) ROUND_HALF_UP; quantize_field(field, v); guarded_div(n, d, eps) (sign-preserving floor; NaN/Inf → ValueError); sanitize_decimal(v) -> (Decimal|None, q); calc_numerical_contract(C,O,H,L,V,ATR_n,tick_size,quantity_step,timeframe,eps) -> (dict|None, status, class); formula_body_ratio/upper_wick/lower_wick/close_position/normalized_range/volume_ratio/return_k. | v4.0.0

apex.quality.vector
- QualityFlags(schema_valid, ordering_valid, duplicate_hash_exists, sequence_hash_valid, replay_hash_valid); QUALITY_CLASSES Q0..QX; calc_quality_vector(obs, flags) -> (Q_raw|None, state, class) — 13 hard gates + 7 components + 4 vetoes + Q_min; calc_window_quality(qualities: [(q, age)], lam=None, q_thr=None) -> (Q_window|None, state, class) — min-veto (any Q_i < Q_thr → whole window INVALID) + exp-decay weighted mean; q_feature(q_formula_valid, q_lookback_complete, q_epsilon); q_evidence(q_conf, q_strength, q_fresh, q_regime, timeframe) — ValueError for undocumented TFs (no interpolation); q_param/q_forecast(rolling_calibration_error, brier, log_loss) -> (value, degraded|blocked); q_fresh(age_bars, lam=None). All tables from params/quality_weights_v1.yaml. | v4.0.0

apex.quality.pit
- TF_DURATION_SECONDS (1mo=2592000, 30-day interval — ISSUE-CP1-007); MTF_STATES; calc_snapshot_pit_window(observations, required_timeframes, minimum_bars, closed_only=True, freshness_threshold=None, eps=1e-12) -> (snapshot|None, state, class) — as_of=max(availability_time), PIT_VIOLATION/INSUFFICIENT_BARS, per-TF observation windows, MTF ALIGNED/PARTIALLY_ALIGNED/CONFLICTING/INSUFFICIENT/ABSENT, deterministic 64-hex snapshot_id (created_at excluded), missing availability_time → ValueError(MISSING_AVAILABILITY_TIME_QX); build_snapshot_barrier(...) -> SnapshotBarrier. | v4.0.0

apex.engines.base (FROZEN — engine stages CONSUME, never edit; changes are G13 issues)
- CONTRACT_VERSION = INTERFACE_VERSION = "v4.0.0"; ENGINE_IDS = E01..E12; ReplayEntry; EngineStateError.
- EngineBase(catalog_=None, bus=None, params=None): engine_id/analyst_version/code_revision (subclass sets; analyst_version = SemVer+git40); contract_version; state (LifecycleState); eps (frozen §2.2 table; E01 scaled variant needs set_eps_inputs(tick_size, closes_20) else ValueError); set_eps_inputs(...); advance_state(new_state) — only forward/terminal (T-MON-002); confirm()/activate(); await feature(feature_id, symbol, timeframe, as_of, lookback=1, context=None) -> CatalogResult (catalog-only data access; never SQL, never get_ohlcv); build_replay_key(symbol, timeframe, as_of, input_hash, parameter_package_id, canonical_payload) -> str; replay_lookup(key) -> cached|None (TTL 60–300s; discarded on code_revision change); replay_store(key, result, ttl_seconds=300); await emit(event: EvidenceEvent, bus=None, priority=2) — validate_24_fields() + producer-engine check + bus publish; wave_out(feature, reason="OUT_OF_CONTRACT") -> WaveOutError; compute(symbol, timeframe, as_of, context=None) -> List[EvidenceEvent] (abstract — CP-2+ implements). | v4.0.0

## DATA-CHANGES
Created (all in `apex/data_catalog/store/sqlite_store.py`, schema_migrations-versioned, WAL, synchronous=FULL, foreign_keys=ON, busy_timeout=5000):
- M001: Ch.4 tables verbatim — market_observation, quality_vector, snapshot_pit, evidence_event, pattern_evidence, setup_candidate, ledger, outcome (column names + CHECK enums exact).
- M002: Ch.5 tables verbatim — raw_observation (+ idx_raw_sym_tf_asof), bootstrap_progress.
- M003: AI.5 — raw_revision (+ idx_raw_revision_original), raw_manifest (+ idx_raw_manifest_period), view raw_store_current, retention_event (audit trail for corrections/purges).
- M004: immutability triggers — raw_observation UPDATE/DELETE ABORT, ledger UPDATE/DELETE ABORT; purge_allow flag table (governed retention deletion path only).
Migrations are append-only; never edit existing entries. No table altered.

## TESTS
| test file | ids covered | result |
|---|---|---|
| tests/unit/test_cp1_foundations.py | nine pins exact; pytest dev-only; no dotenv; .gitignore ADR-P2-013; tree presence; import-chain; no-TODO/FIXME/stub sweep; params frozen literals (§9.5/Ch.10/§2.1/Ch.16 copy-exact) | 17 passed |
| tests/unit/test_config.py | env names exact; stdlib .env; no-shadow; SHADOW rejected; frozen defaults; secrets masked; params loader | 14 passed |
| tests/unit/test_errors.py | every Ch.7 row (23) exact codes/meanings/handling; Wave-Out list frozen; WaveOutError plumbing | 7 passed |
| tests/unit/test_bus.py | P0 synchronous+ordered; P0 never dropped (200 P0 + 100 P2); P1 dedicated lane FIFO; P1 never dropped (evicts shared); P2/P3 drop-oldest+QUEUE_OVERFLOW_DROP; raw queue 1000 | 8 passed |
| tests/unit/test_identity.py | T-PIT-001 (byte-identical ×50); T-PIT-002 (n=500); T-PIT-003 (stable key+dedup); T-PIT-004 (×100); T-ID-001 (1000 events, monotonic, no dupes); T-ID-002 lineage refs; canonical_json Decimal/datetime/NaN/Inf/-0; uuid_v7 RFC 9562 shape + single-implementation grep; snapshot envelope + scope BLOCKs + governed_as_of fail-closed | 21 passed |
| tests/unit/test_catalog.py | §3.13 74==74 + tier counts + F74 template + F73 complete + F49 REMOVED slot + F56 always-UNAVAILABLE; exact full_ids; unregistered → INVALID; future as_of → INVALID; result shape; tier caches (ATOM never cached; MOLE 5-candle; ORGN LRU-100); T-DC-001..004 (incl. 1000 random OHLC, OI never 0); T-OM-001..003; T-DR-001 feature replay; T-MON-001; ATOM-failure halts pipeline | 23 passed |
| tests/unit/test_quality.py | §2.1 gates×13 + vetoes×4 + Q_min + Q_oi STALE=0.5 canonical + Q_window min-veto/weighted + derived measures (Q_feature/Q_evidence/Q_param/Q_forecast/Q_fresh); §2.2 two-tier eps + ENGINE_EPS + quantize ROUND_HALF_UP + division guards + contract example + doji guard + core formulas; §2.3 as_of=max(availability) + fail-closed missing availability + MTF states + closed-only + deterministic snapshot_id + tf_duration | 27 passed |
| tests/unit/test_toobit_public.py | wire maps; kline parsing (list/dict/bad); retry 3× with 1s/2s/4s backoff; RETRY_EXHAUSTED; 429 → TOO_MAUTC_W2_REQUESTS; OI endpoint failure → None (never 0); funding alert threshold 0.001; klines limit cap | 13 passed |
| tests/unit/test_base_contract.py | versioned interfaces v4.0.0; engine_id validation; lifecycle forward-only/terminal-never-reverts; replay key + cache + code_revision invalidation; emission 24-field validation (bad engine/direction/NaN/resolution); Wave-Out plumbing; catalog-only data access; frozen EPS (E05 1e-8; E01 scaled fail-closed + 0.05 case) | 15 passed |
| tests/integration/test_store_integration.py | Ch.4 table/column verbatim-equivalence; Ch.5/AI.5 tables + indexes; WAL pragmas; migrations recorded; T-RS-001 UPDATE/DELETE blocked at DB level; T-RS-002 manifest hash chain; T-RS-003 retention purge + audit rows; T-CL-001/002 SUPERSEDED+CORRECTED+raw_revision; T-CL-003 cascade lineage; ingest dedup; E-VAL-021/022 rejection; evidence insert 24-field validation; catalog-over-store (real body_ratio 0.416667; future as_of INVALID) | 13 passed |
| TOTAL | suite = 158 passed / 0 failed | |

## DEVIATIONS
- ADR-P2-002 applied: pytest dev-only extra `[tests] = pytest>=7,<9`; never in requirements.lock, never imported by apex/**.
- ADR-P2-003 applied: additive files all logged in DELIVERED + DECISION_LOG §B/CP-1 (tier packages, math/performance tiers, tests/, scripts/, __init__.py files, universe_v1.yaml additive keys from the Ch.5 table).
- ADR-P2-006 applied: tier packages under apex/data_catalog/ exactly as §3.12 names them; single catalog.py registration path.
- ADR-P2-008 applied: e11_params_v4.yaml carries the §9.5-canonical values.
- ADR-P2-013 applied: .gitignore exactly the ADR list; no extra entries.
- ADR-P2-015 applied: everything built fresh; no prior-attempt code, no copied illustrative hashes/values (no-hash rule honored: all test expectations re-derived from formulas, e.g. body_ratio=5/12=0.416667).
- ADR-P2-016 applied: single-session budget respected (no overflow); CP-1 completed under the window.
- Otherwise: none — no silent deviations (G4).

## OPEN-ISSUES
- [ISSUE-CP1-002] veto_OI_lag fires at lag > 5×threshold (DEGRADED band); STALE (≤5×thr) is scored 0.5, not vetoed — §2.1 Q_oi table vs Ch.7 wording. CLOSED with interim (vector.py); owner needs nothing.
- [ISSUE-CP1-003] §3.12 uniform template metadata vs §2.2 per-feature math (range/body_size are price diffs; is_bullish 0/1; return_k → {k1,k5,k20}). §2.2 is formula authority; template metadata retained verbatim. CLOSED.
- [ISSUE-CP1-004] k_*/theta_* (F22–30), GARCH (F40), theta_body/vol/invalid (F42–44): §3.12 names formulas without math in CP-1's assigned text (E02/E03 chapters own them). Registered with full contracts; compute returns UNAVAILABLE (deterministic reason) — never a guessed formula. OPEN until CP-2/CP-3 supply implementations from their chapters.
- [ISSUE-CP1-005] ORGN CTXT features requiring regime/temporal-window/HTF evidence return UNAVAILABLE until CP-5/CP-6 build those producers (AI.6 missing-data model; gates stay open, nothing fires). OPEN — CP-6 wires them.
- [ISSUE-CP1-006] F20 VolRatio vs F41 volume_ratio: F41 = exact §2.2 8-digit formula (SMA_20 on t−1); F20 = plain ratio with the same PIT discipline. CLOSED (mapping disclosed).
- [ISSUE-CP1-007] tf_duration table: blueprint names it without values; 1mo = 2592000 s (30-day exchange interval, Toobit 1mo→1M). CLOSED with deterministic interim.
- [ISSUE-CP1-008] params YAML parsing: runtime SBOM has no YAML library → strict stdlib parser for the frozen "APEX params subset" (the six YAMLs use only it); anything outside → ValueError (fail-closed). CLOSED.
- [ISSUE-CP1-009] universe_v1.yaml additive keys (tick_size/quantity_step/min_notional/exchange_max_leverage) from the Ch.5 table — permitted by ADR-P2-003, logged. CLOSED.
- [ISSUE-CP1-010] F74 sweep rejection-ratio = recovery/penetration (close-back-inside depth); theta_sweep consumed from context when provided (E02 parameter, not yet built). CLOSED with interim; CP-2 (E02 owner) re-asserts.
- [ISSUE-CP1-011] Indicator definitions (SMA/EMA/RMA/Wilder/ATR/TR/VWAP/OBV/RSI/z/OLS/Hurst/Parkinson/GK/RS) implemented per the standard definitions the frozen text uses; Ch.6 Feature Catalogue per-feature code is not assigned to any stage — §3.12 registry + §2.2 formulas are CP-1's authority. CLOSED; engine stages re-assert against their chapters.
- [ISSUE-CP1-012] Correction statuses: original market_observation → SUPERSEDED, corrected row → CORRECTED (both in the Ch.4 enum); raw_observation rows remain append-only with lineage in raw_revision. CLOSED.
- [ISSUE-CP1-013] Sandbox toolchain: PEP 668 → venv outside the repo for pytest; target device uses the frozen Termux SBOM. Environment note only. CLOSED.
- [ISSUE-CP1-014] Session branch arena/01a09373-upstage vs plan's main (Arena-session constraint): commit chain pushed to the session branch; ADR-P2-012 main-branch discipline applies on the owner repo. CLOSED (recorded, not silently merged).

## HOW-TO-RUN
```bash
cd Upstage
# toolchain (sandbox): venv with pytest
python3 -m venv /home/user/apex-venv
/home/user/apex-venv/bin/pip install -r requirements.lock "pytest>=7,<9"
# (on-device: the frozen Termux SBOM provides the nine pins + pytest dev-extra)

# full suite (unit + integration), 158 tests:
PYTHON=/home/user/apex-venv/bin/python ./scripts/run_all_tests.sh

# import smoke:
/home/user/apex-venv/bin/python -c "from apex.data_catalog.catalog import catalog; print(catalog.verify_completeness())"
# → {'count': 74, 'tiers': {'ATOM': 44, 'MOLE': 1, 'ORGN': 29}}

# demo entry (store + catalog end-to-end):
/home/user/apex-venv/bin/python - <<'EOF'
import asyncio
from decimal import Decimal
from apex.data_catalog.store.sqlite_store import SQLiteStore
from apex.data_catalog.catalog import Catalog
from apex.data_catalog.contracts import MarketObservation

async def main():
    s = await SQLiteStore("/tmp/demo_apex.sqlite3").open()
    obs = MarketObservation(symbol="BTCUSDT", timeframe="15m",
        open=Decimal(100), high=Decimal(110), low=Decimal(98),
        close=Decimal(105), volume=Decimal(10), oi=Decimal(500),
        timestamp="2024-01-01T00:15:00.000Z", sequence=0, status="CLOSED",
        source="TOOBIT", availability_time="2024-01-01T00:15:00.000Z")
    await s.ingest_raw(obs, "AVAILABLE")
    c = Catalog(); c.set_provider(s)
    r = await c.get("body_ratio", "BTCUSDT", "15m", "2024-01-01T00:15:00.000Z")
    print(r.status.value, r.value)   # OK 0.416667
    await s.close()

asyncio.run(main())
EOF
```

## REMAINING WORK LEDGER
none — stage fully closed (complete; all CP-1 exit boxes checked with test-name evidence; suite green; handoff written; matrix filled; board updated; commits pushed).
For CP-2: the k_*/theta_*/GARCH/theta_body/vol/invalid formulas (ISSUE-CP1-004) and the ORGN CTXT context-gated features (ISSUE-CP1-005) are the only CP-1 surfaces waiting on later stages' chapters — they return UNAVAILABLE until then (fail-closed), and their contracts are already registered and test-covered.
