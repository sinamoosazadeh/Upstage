# PHASE2 HANDOFF — CP-2 → consumed by CP-3 (and CP-8 closeout)
Stage: CP-2 — Engines E01 Structure, E02 Liquidity, E03 Volume — full §3/§5/§6/§8 fidelity
Rules (PROTOCOL P16): author = CP-2 executor (or its continuation session — state which, first line of STATUS). ≤400 lines, nine headings below in order. Successors read ONLY this file + their own prompt/law/checkpoint sections; interfaces listed here are the public contract they may code against. First STATUS line: `LAW-ACK: G1..G20 + P1..P21 read <UTC>`.

## STATUS
LAW-ACK: G1..G20 + P1..P21 read 2026-09-12T06:20:00Z
COMPLETE — author: CP-2 executor session (Arena agent on branch arena/01a0944e-upstage, the session-pinned branch per ISSUE-CP1-014 discipline).
Commits pushed: 3cd94e3 (board claim) → 89e60e2 (E01) → 36d0cb6 (E02) → cfd3fe0 (E03) → 28893bc (integration) → docs commit (this handoff + matrix + board).
Suite totals: 305 passed / 0 failed via `PYTHON=/home/user/apex-venv/bin/python ./scripts/run_all_tests.sh` (158 CP-1 + 44 E01 + 46 E02 + 49 E03 + 8 integration).
Environment: Python 3.11.2, Linux (sandbox); dev venv /home/user/apex-venv with the nine SBOM runtime pins + pytest 8.4.2 (dev-only, ADR-P2-002/ISSUE-CP1-013). Runtime deps unchanged — no new pins.

## DELIVERED
- apex/engines/e01_structure/__init__.py + engine.py | E01 Structure v4.0.0 full engine (§3 formulas→§8 battery, chapter order) | E01 chapter §1–§10 | MATRIX Part III rows 1–8
- apex/engines/e02_liquidity/__init__.py + engine.py | E02 Liquidity v4 full engine (Merton jump-diffusion, 1D DBSCAN pools, salience with proximity_HTF, level/pool/sweep/raid/void lifecycle, OFI/VPIN/Kyle/GM, LVN voids) | E02 chapter §1–§10 | MATRIX Part III rows 9–16
- apex/engines/e03_volume/__init__.py + engine.py | E03 Volume v4 full engine (PIT-safe VR/VZ, TP-VWAP, Wilder OBV, 0.25·ATR sorted-VA profile, EVR, A/D tanh proxy, wash/OI-stale, six-phase state machine; Phase 67/79/80/88 correction records quoted above the code they govern) | E03 chapter §0–§10 + Part R.7 | MATRIX Part III rows 17–24
- tests/fixtures/e01_golden_fixtures.json | FIX_001–010 inputs, expected values re-derived | E01 §8.1 | —
- tests/fixtures/e02_golden_fixtures.json | GF_LIQ_001–012 inputs, expected values re-derived | E02 §8.1 | —
- tests/fixtures/e03_golden_fixtures.json | 12 E03 cases, expected values re-derived | E03 §8.1 | —
- tests/unit/test_e01_structure.py | full E01 §8 battery + T-E01-001 + T-DR-001(E01) | E01 §8 | —
- tests/unit/test_e02_liquidity.py | full E02 §8 battery + T-DR-001(E02) | E02 §8 | —
- tests/unit/test_e03_volume.py | full E03 §8 battery + T-DR-001(E03) + six-phase + correction-block greps | E03 §8 | —
- tests/integration/test_cp2_engines.py | §8.6 cross-engine redundancy gates + T-DR-001 shared window + store-DDL emission validation | E01/E02/E03 §8.6, CP-2 EXIT | —

## INTERFACES
(module | class/function | signature | semantics | version) — what CP-3 may code against. All engine packages are import-stable; nothing else in them is public.

E01 — apex.engines.e01_structure
- E01StructureEngine(EngineBase) | compute(symbol, timeframe, as_of, context) -> List[EvidenceEvent] | context keys: window (List[MarketObservation], preferred — the streaming data-plane path, ISSUE-CP2-007), provider (sync WindowProvider), bars (int, default 300), tick_size (float, else universe_v1.yaml lookup), htf_swings (E01 merge input), states_by_tf (dict tf→BULL/BEAR/RANGE → emits EV_STR_020), e01_params (override dict, keys ⊆ E01_DEFAULTS). Fail-closed: ValueError MISSING_WINDOW_CONTEXT_QX. | v4.0.0
- run_pipeline(candles, params=None) -> {"events", "swings", "pruned", "state", "bias"} | pure batch over closed-candle dicts {O,H,L,C,V,open_time,close_time}; min_candles 50. | 4.0.0
- StructureEngineStreaming(config=None) | on_new_candle(candle) -> List[event dicts] | §4.10 streaming, idempotent per close_time; config key "dynamic_k" → WaveOutError. | 4.0.0
- Public formula/flow functions (CP-3 may reuse, no signature change): scaled_epsilon, atr_sma, atr_wilder, sma_until, break_mag, s_struct, wilson_ci, detect_swings_williams, detect_swings_gann, is_outside_bar, is_inside_bar, merge_and_prune_swings, detect_gaps, detect_bos, detect_choch, detect_retest_and_invalidation, detect_wick_rejection, compute_mtf_bias, candle_features, stop_context, validate_swingpoint, validate_structure_event. Detectors accept atr_override (test/fixture pathway; production path computes ATR per-bar).
- Topics published via base.emit: evidence.E01.<EV_STR_### condition_state> (EV_STR_000–020 catalog in EVENT_CATALOG). Schema pointers: SwingPoint/BOS-Event required-field tuples SWINGPOINT_REQUIRED/STRUCTURE_EVENT_REQUIRED; validate_* raise ValueError. Contract version: v4.0.0 (base CONTRACT_VERSION). Params keys: E01_DEFAULTS (k_williams, atr_n, zigzag_threshold, break_policy, break_min_mag, disp_min, eq_tol, retest_tol_kappa, expiry_bars, accept_wicks, theta_depth, theta_maxAge, theta_ext, gamma_gap, T_HTF, strength_weights, tf_weights, bias_threshold, max_levels, redundancy_thr, tick_size, min_candles). Degradation branches: <50 candles → warmup, no events (EV_STR_000 for H<L bars); dynamic-k request → WaveOutError; unknown context tick + unknown symbol → ValueError (fail-closed).
E02 — apex.engines.e02_liquidity
- E02LiquidityEngine(EngineBase) | compute(symbol, timeframe, as_of, context) -> List[EvidenceEvent] | context keys: window, provider, bars, htf ({levels: [{price}], atr_htf} → proximity_HTF; absent → proximity 0), l2_snapshots (Cont-OFI input; absent → QX, never fabricated), e02_params. All emissions direction=0 (NG1/NG3 — context only). | v4.0.0
- LiquidityEngineV4(theta_eq, sweep_min_pen, sweep_min_rej, lambda_decay, kappa, raid_window, level_expiry_bars, invalid_break_atr, void_gap, lvn_percentile, salience_weights, type_scores, sweep_weights, volume_profile_bars, vp_bins) | on_new_closed_candle(candle, htfs=None, l2_snapshots=None) -> List[event dicts]; feed_touches([{price, bar_index, type, confirmed}]) = SwingInput.v1; output() -> E02.Output.v4 dict; set_htf(levels, atr_htf). Idempotent per bar_index. | 4.0.0
- Public functions: group_equal_levels_hierarchical (§3.3 chain-preventing), dbscan_1d_optimal + adaptive_min_pts (pool radius 2·θ_eq·ATR·κ, ISSUE-CP2-010), compute_salience, proximity_htf, freshness, compute_pool_weight, detect_sweep (P1–P5 + SweepScore; STRENGTHENED counts as the ACTIVE family), detect_raid, compute_OFI_from_L2_snapshots (§3.8 signs; ISSUE-CP2-013), compute_VPIN + vpin_from_buckets (BVC), kyle_lambda, glosten_milgrom_half_spread, identify_liquidity_voids_LVN (§2 aggregated-share rule, ISSUE-CP2-011), merton_hit_probability + brownian_hit_probability + estimate_merton_parameters (log-distance conversion, ISSUE-CP2-012), poisson_significance, jaccard_index, wilson_ci, load_output (v3→v4 Q3 warning), validate_level_row/validate_pool_row/validate_event_row, run_engine, sweep_outcomes, no_future_leak_check, ablation_sweep_score.
- Topics: evidence.E02.<EV_LIQ_###> (EV_LIQ_000–013). Schema pointers: Level/Pool/SweepEvent dataclasses; E02.Output.v4 field sets in the validators. Contract version 4.0.0. Params keys: E02_DEFAULTS (theta_eq, kappa, sweep_min_pen, sweep_min_rejection, sweep_weights, lambda_decay, lambda_fast, lambda_slow, salience_weights, void_gap, lvn_percentile, raid_window, level_expiry_bars, invalid_break_atr, sweep_cooldown_bars, utc_activity_windows, type_score, merton{lambda_j,mu_j,sigma_j}, T_hit, volume_profile_bars, vp_bins, min_candles). Degradation branches: H<L bar → EV_LIQ_000 Q0; no L2 → OFI/VPIN QX (no fabricated values); no HTF → proximity 0; <14-candle ATR sample → Q3; V=0 → VolumeRatio component 0 (Q3 path).
E03 — apex.engines.e03_volume
- E03VolumeEngine(EngineBase) | compute(symbol, timeframe, as_of, context) -> List[EvidenceEvent] | context keys: window, provider, bars, atr_prev (scalar or per-bar list — the ATRBundle v2.0.0 / E04 I_Volatility_v4 scalar; MISSING → every bar fails closed ATR_UNAVAILABLE_QX, engine emits nothing), oi_availability_time_ms, atr_availability_time_ms, e03_params. | v4.0.0
- VolumeEngineV4(params) | ingest_bar(bar) -> Optional[ParticipationEvidence]; bar keys: ts(ms), o,h,l,c,v, is_closed, tf, symbol, oi, oi_timestamp, atr_prev, availability_time_ms, oi_availability_time_ms, atr_availability_time_ms, temporal_window. Six phases: state ∈ INIT/WARMUP/READY/EMITTING/DEGRADED/FAILED (non-emitting before history ≥ 50; DEGRADED on OI STALE/MISSING; FAILED after 3 consecutive H<L); last_error = {code, quality, as_of_ts}. Idempotent on (ts, v, c). | 4.0.0
- ParticipationEvidence dataclass — fields per §5.1 incl. the Phase-80 governed volume_sma (E06's I_Volume_v4 contract consumes {volume_sma, vol_ratio, snapshot_id, as_of}); required_fields_present() validates the schema. Events EV_VOL_001–012 (strings "EV_VOL_### name" as in the chapter); EV_VOL_010 emitted via the §3.8 pivot-slope divergence.
- Public functions: sma_pit, mean_std_pit, zscore_pit, volume_ratio_pit, typical_price (H<L → ValueError INVALID_OHLC_H_LT_L), vwap_pit, obv_series_wilder, volume_profile_sorted (+ _select_value_area), evr_corrected, tanh_mapping, ad_proxy_tanh, detect_wash_trading, detect_oi_stale, detect_participation_divergence, ols_slope, wilson_ci, normalize/quarantine non-finite, governed_as_of_ms/e03_governed_as_of_ms, snapshot_id, TF_SECONDS (14 TFs, 8h ✓, no 3d), mtf_vr_ratio, bos_confirmation_filter, run_engine, deterministic_replay_check, no_future_leak_check, ablation_ad, round8.
- Topics: evidence.E03.<EV_VOL_###>. Schema pointer: ParticipationEvidence v4.0.0 (required: engine, version, snapshot_id, as_of_ts, volume_ratio, volume_sma, quality). Contract version 4.0.0. Params keys: E03_DEFAULTS (vol_sma_n, vol_z_window, oi_window, climax_ratio, climax_range_z, dryup_ratio, vwap_temporal_window, vwap_lookback, profile_window, value_area_pct, ad_weights, ad_tau, oi_missing_policy, wash_vr_threshold, oi_stale_candles, atr_period, min_candles). Degradation branches: ATR absent/invalid → ATR_UNAVAILABLE_QX (None return, last_error); OI missing/stale → DEGRADED + EV_VOL_011; open bar → ignored; non-finite intermediates → explicit None (Phase 79/88); H<L → rejected, 3 consecutive → FAILED.

Cross-engine notes for CP-3: E04 must publish its ATR scalar in the form E03's context expects (atr_prev per bar) — the I_Volatility_v4 mirror of Phase 80's I_Volume_v4; E05/E06 consume evidence via the topics above; nobody may import another engine's internals — DataBus/versioned contracts only.

## DATA-CHANGES
none (no migrations; emissions validated against the frozen CP-1 evidence_event DDL via SQLiteStore.insert_evidence in tests/integration/test_cp2_engines.py).

## TESTS
- tests/unit/test_e01_structure.py | §8.1 FIX_001–010, §8.2 T-DR-001(E01), §8.3 no-future-leak, §8.4 ablation, §8.5 Wilson+CI+z, §8.7 serialization, T-E01-001, state machines, Wave-Out dynamic-k, §6 params, §7 metrics, streaming idempotency, EngineBase emission | 44 passed
- tests/unit/test_e02_liquidity.py | §8.1 GF_LIQ_001–012, §8.2 T-DR-001(E02), §8.3 first_seen≤at_bar−1, §8.4 ablation+ground truth, §8.5 Wilson (§9 figures), §8.7 v3→v4 loader, schema/state, §9 case study, raid, emission | 46 passed
- tests/unit/test_e03_volume.py | §8.1 twelve fixtures, §8.2 T-DR-001(E03), §8.3 V-replacement+open-bar, §8.4 ablation, §8.5 Wilson calibration, §8.7 serialization, six phases, Phase 67/79/80/88 quotes, §9 re-derivations, emission | 49 passed
- tests/integration/test_cp2_engines.py | E01§8.6 r≤0.15, E02§8.6 density≤0.85 + salience band, E03§8.6 EVR/AD<0.85 + VWAP_dev/OBVZ<0.3, T-DR-001 shared window, store-DDL emission inserts | 8 passed
- Full suite: 305 passed / 0 failed (includes the CP-1 158 unchanged).

## DEVIATIONS
none — no ADR-P2-0NN deviation was needed beyond the pre-adjudicated applications already recorded as issues: ADR-P2-007 applied (all §8 expected values re-derived from formulas; document hashes/case values never copied), ADR-P2-014 applied (fixtures canonical in the five reconciliations ISSUE-CP2-002/003/010/011/012), ADR-P2-017 applied (E03's ATR dependency on later-stage E04 consumed as a specified context contract with its specified fail-closed degradation path). No simplifications, no formula changes, no TODO/FIXME/pass/NotImplementedError in any Wave-In engine file.

## OPEN-ISSUES
Mirrored in PHASE2_DECISION_LOG.md §B/CP-2 (16 issues; format P13):
[ISSUE-CP2-001] CLOSED — E01 §5.3 garbled state token AUTC_W2 read as TRANSITION.
[ISSUE-CP2-002] CLOSED — E01 BOS level_index in price-adjacency order (§3.6/FIX_004 over §4.6 recency).
[ISSUE-CP2-003] CLOSED — E01 Gann detection/dedup reconciled to FIX_002+§9+§3.4 (fixture/case/formula over §4 pseudo-code).
[ISSUE-CP2-004] CLOSED — E01 retest is close-based (§3.11 over §4.8 wick-touch; FIX_007).
[ISSUE-CP2-005] CLOSED — E01 gap BREAKAWAY per §4.5 (§3.2 VR variant recorded as metadata).
[ISSUE-CP2-006] OPEN (informational) — engine §6 tables live as frozen in-package defaults (six-YAML law; §9.5 tree).
[ISSUE-CP2-007] CLOSED — compute() window intake via context window / sync WindowProvider; async-without-context fail-closed.
[ISSUE-CP2-008] CLOSED — FIX_010 bias scalar inconsistent with §3.10 formula (1.0 asserted).
[ISSUE-CP2-009] CLOSED — theta_maxAge 100 (§2.1/F31) vs 120 (E01 §6): scope separation.
[ISSUE-CP2-010] CLOSED — E02 pool radius 2·θ_eq·ATR·κ (GF_LIQ_003/Ch.2 examples).
[ISSUE-CP2-011] CLOSED — E02 LVN void via §2 aggregated-share threshold (GF_LIQ_007).
[ISSUE-CP2-012] CLOSED — E02 Merton log-distance conversion (§9 Step 10 / GF_LIQ_012).
[ISSUE-CP2-013] CLOSED — E02 OFI sign per §3.8 formula (GF_LIQ_008; §7 example erroneous).
[ISSUE-CP2-014] CLOSED — E03 VWAP fixture scalar inconsistent with §3.2 (96.778 asserted; §7 example 97.29 reproduced).
[ISSUE-CP2-015] CLOSED — §8.5 z and §8.6 thresholds: reproducible parts asserted; data-dependent gates verified on documented deterministic synthetic windows (no fabricated statistics).
[ISSUE-CP2-016] OPEN — ISSUE-CP1-004 partially resolved: engine chapters define θ_eq/θ_depth/θ_maxAge as parameters (supplied in-package); the formula_k_* catalog slots remain undefined placeholders and stay fail-closed UNAVAILABLE (catalog consumed-never-patched).

## HOW-TO-RUN
# tests (full suite; venv per ISSUE-CP1-013):
PYTHON=/home/user/apex-venv/bin/python ./scripts/run_all_tests.sh
# single engine battery:
PYTHON=/home/user/apex-venv/bin/python ./scripts/run_all_tests.sh tests/unit/test_e01_structure.py
PYTHON=/home/user/apex-venv/bin/python ./scripts/run_all_tests.sh tests/unit/test_e02_liquidity.py
PYTHON=/home/user/apex-venv/bin/python ./scripts/run_all_tests.sh tests/unit/test_e03_volume.py
PYTHON=/home/user/apex-venv/bin/python ./scripts/run_all_tests.sh tests/integration/test_cp2_engines.py
# quick engine demo (no repo state needed):
/home/user/apex-venv/bin/python -c "
from apex.engines.e01_structure import run_pipeline
from apex.engines.e02_liquidity import run_engine, Candle
from apex.engines.e03_volume import run_engine as run_e03
from tests.integration.test_cp2_engines import lcg_window, to_e02_candles, to_e03_bars
w = lcg_window(120)
print('E01 events:', len(run_pipeline([{'O':o,'H':h,'L':l,'C':c,'V':v,'open_time':str(i),'close_time':str(i)} for i,(o,h,l,c,v) in enumerate(w)])['events']))
print('E02 events:', len(run_engine(to_e02_candles(w)).events))
print('E03 emissions:', len(run_e03(to_e03_bars(w))))"
# fresh-clone verification (owner): git clone → python3 -m venv .venv → .venv/bin/pip install -r requirements.lock ".[tests]" 2>/dev/null || .venv/bin/pip install -r requirements.lock "pytest>=7,<9" → PYTHON=.venv/bin/python ./scripts/run_all_tests.sh

## REMAINING WORK LEDGER
none — stage fully closed. Notes for successors (not gaps): (1) E01 §8.2's 20,000-candle BTCUSDT 2020–2024 replay and the §8.5/§8.6 real-data calibrations require a real OHLCV dataset that does not exist in the sandbox and may not be fabricated — the equivalent properties (byte-identical double-run, no-future-leak, formula checks, correlation gates) are executed on deterministic synthetic windows (ISSUE-CP2-015); the research stage's ADR-P2-005 harness owns real-data verification. (2) E03's ATR input becomes live when CP-3 ships E04 (see INTERFACES cross-engine note). (3) ISSUE-CP2-006/016 are informational-open; CP-8 dispositions.
