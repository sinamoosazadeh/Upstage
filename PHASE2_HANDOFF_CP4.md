# PHASE2 HANDOFF — CP-4 → consumed by CP-5 (and CP-8 closeout)
Stage: CP-4 — Engines E07 RTM/ICT, E08 Wyckoff, E09 Trend — full §3/§5/§6/§8 fidelity
Rules (PROTOCOL P16): author = CP-4 executor (single session). ≤400 lines, nine headings below in order. Successors read ONLY this file + their own prompt/law/checkpoint sections; interfaces listed here are the public contract they may code against. First STATUS line: `LAW-ACK: G1..G20 + P1..P21 read <UTC>`.

## STATUS

LAW-ACK: G1..G20 + P1..P21 read 2026-09-12T15:40Z (all law files read in full before STEP 3 claim; blueprint ranges read per assignment list in PHASE2_CHECKPOINTS.md §CP-4).

COMPLETE. CP-4 fully closed: E07 RTM/ICT v4.0.0, E08 Wyckoff v4.0.0, E09 Trend v4.0.0 built from zero per the frozen blueprint (chapter order §3→§4→§5→§6→§7→§8 mirrored in each engine file), every §8 battery clause executed as a test, golden fixtures re-derived per ADR-P2-007.

- Suite: **593 passed / 0 failed** (`tests/unit` + `tests/integration`; baseline 481 CP-1/2/3 + 112 new CP-4 tests: E07 33, E08 44, E09 29, integration 6).
- Branch: `arena/01a09645-upstage` (pinned by environment; owner merges to main plain-merge per ENV NOTE). Commits (format `[CP-4] <module>: <what changed>`): 6893742 board IN-PROGRESS → 9c7e04d E07 → acaea9a E08 → 38ee786 E09 → 0f26234 integration.
- Environment: Python 3.11.2, Linux (sandbox); dev venv `/home/user/Upstage/.venv` (nine SBOM runtime pins + pytest 8.4.2 dev-only; ADR-P2-002 / ISSUE-CP1-013). Runtime deps unchanged — no new pins. NOTE: the sandbox checkout is SHALLOW (one visible commit at main), so predecessor commit ranges cannot be SHA-verified here; file contents and the green entry-gate suite (481/0 re-verified at session start) were used instead.

## DELIVERED

| file | purpose | blueprint section |
|---|---|---|
| apex/engines/e07_rtm/engine.py (+ __init__.py) | E07 RTM/ICT v4.0.0: order_map + sequence_integrity_v4 (0.5 penalty), Po3 range detection (ATR ratio + vol compression), MSS proximity, OTE 62–79%, Judas Swing, UTC activity windows (KZ.v2.1.1), bundle_confidence + Q0–Q5, conflict resolver, PO3/CHAIN/MSS bundle assembly, RTMEngineStreaming, EngineBase binding; E12-unavailable → `temporal_source=E07_UTC_FIXED_DEGRADED` (never fabricates E12) | APEX_GEN5.md L8293–9085 |
| apex/engines/e08_wyckoff/engine.py (+ __init__.py) | E08 Wyckoff v4.0.0: 8-phase softmax/entropy hypotheses, corrected EVR, Cause&Effect (P&F + continuous k=0.42/γ=0.71), Effort&Result ρ, 6-parameter event contract (SC/AR/ST/Spring/SOS/LPS/UTAD/LPSY), Dirichlet transition matrix, WyckoffEngineV4 streaming, EngineBase binding; encyclopedia ch.1 complete, ch.2–4 raise `WaveOutError("e08_encyclopedia_ch2_4", ...)` | APEX_GEN5.md L9086–9466 |
| apex/engines/e09_trend/engine.py (+ __init__.py) | E09 Trend v4.0.0: 4-scale (MICRO/SHORT/INTER/MACRO) state vector, seq_score, OLS + Newey-West (L=floor(4·(n/100)^(2/9))), Mann-Kendall + tie correction, Anis-Lloyd Hurst, full Wilder ADX, TrendStack fixed weights [0.1,0.2,0.3,0.4], Q_trend + Q0–Q5, divergence exhaustion, TrendEngine + EngineBase binding | APEX_GEN5.md L9467–10275 |
| tests/unit/test_e07_rtm.py | E07 §8.1 15 golden fixtures (re-derived), §8.2 replay, §8.3 no-leak, §8.4 ablation, §8.5 Wilson, §8.6 redundancy, §8.7 serialization, event catalog, params, E12-degraded branch, EngineBase binding, T-DR-001 | E07 §8 |
| tests/unit/test_e08_wyckoff.py | E08 event contract (re-derived from §9), three laws, phase/entropy/AMBIGUOUS, transition matrix, replay, no-leak, Brier calibration, redundancy, serialization, encyclopedia ch.1 + ch.2–4 Wave-Out, params, EngineBase binding, T-DR-001 | E08 §8 |
| tests/unit/test_e09_trend.py | E09 §8.1 FIX_01..11 (re-derived), seq_score §7 examples, replay, no-leak, ablation, Wilson, redundancy, serialization, Wilder ADX internals, Anis-Lloyd, params, EngineBase binding, T-DR-001 | E09 §8 |
| tests/integration/test_cp4_engines.py | E09 consumes E04 ATR + E01 swings; E07 assembles bundle from E04/E05/E06 evidence + E12-degraded branch; E08 phases over E04 ATR; emissions through store DDL; T-DR-001 ×3 | E07/E08/E09 §8.6 + CP-4 EXIT |
| tests/fixtures/e07_golden_fixtures.json | 13 re-derived E07 §8.1 fixtures (doc_inconsistency notes where doc diverges) | E07 §8.1 |
| tests/fixtures/e08_golden_fixtures.json | 8 E08 event fixtures re-derived from the §9 case study (source has no bar arrays — §8 note) | E08 §8 |
| tests/fixtures/e09_golden_fixtures.json | 11 re-derived E09 FIX_* fixtures (doc_inconsistency notes) | E09 §8.1 |
| PHASE2_DECISION_LOG.md §B/CP-4 | ISSUE-CP4-001..007 entries | G13 |
| PHASE2_TRACEABILITY_MATRIX.md, PHASE2_CHECKPOINT_STATUS.md | CP-4 rows / board boxes | G18 |

## INTERFACES

All three engines bind the frozen EngineBase contract (`apex/engines/base.py`, consumed never patched): `compute(symbol, timeframe, as_of, context) -> List[EvidenceEvent]` with `context['window']: List[MarketObservation]` (or sync `context['provider']`); every emission validates the 24-field EvidenceEvent frame; topics `evidence.{engine_id}.{condition_state}`. Shared helper: `observation_to_bar(obs[, timeframe])`.

### E07 (`apex.engines.e07_rtm`, ENGINE="E07_RTM_ICT", CONTRACT_VERSION="4.0.0", ε=1e-8)

| symbol | signature / semantics |
|---|---|
| `run_engine(bars, params=None, symbol="", timeframe="1h", structure_events=None, sweep_events=None, volume_events=None, fvg_events=None, ob_events=None, atr_series=None, temporal_windows=None, econ_events=None, mtf_align=0.0, as_of_ms=None) -> {"engine","bundles","kz_info","temporal_source","as_of_ms"}` | batch driver; `bundles` are `RTMBundle` objects (framework_id, integrity, confidence, direction, resolution_class Q0–Q5, components_present/missing, fate, snapshot_id). `temporal_source ∈ {"E12","E07_UTC_FIXED_DEGRADED"}`. |
| `E07RTMEngine(EngineBase)` | `compute(...)`; context keys: `window`/`provider`, `e07_params`, `structure_events` (E01 `{kind:"BOS"/"CHoCH", direction, valid_at_idx, ts}`), `sweep_events` (E02), `volume_events` (E03), `fvg_events` (E05 `{present, direction, lower, upper}`), `ob_events` (E06), `atr_series` (E04), `temporal_windows` (E12 — OPTIONAL), `econ_events`, `mtf_align`. |
| Formulas (§3/§4) | `sequence_integrity_v4(expected, present, order_map) -> (integrity, weight_coverage, missing)`; `evaluate_order_ok(...)`; `atr_ratio_detect(bars, params)`; `mss_proximity_check(p_sweep, p_choch, atr20, thresh)`; `ote_zone_calc(a, b)`; `judas_swing_detect(bars, expected_dir, atr20, ...)`; `utc_activity_window_check(ts_ms, econ_events, ...)`; `bundle_confidence(...)`; `resolution_class_of(...)`; `resolve_conflicting_bundles(...)`; `build_bundle_pipeline(...)`; `wilson_ci(...)`; `make_snapshot_id(payload)`. |
| Frameworks | `RTM.PO3.v1` weights {sweep 1.5, CHoCH 1.0, BOS 1.0, FVG 0.8, volume 0.7}; `RTM.CHAIN.v1` (Liquidity Grab) {sweep 1.5, structure 1.0, FVG 0.8, retest 0.8, volume 0.7}; `RTM.MSS.v1`; `RTM.OTE.v1`; `RTM.JUDAS.v1`; `RTM.UTC_ACTIVITY_WINDOW.v1` (enum-only; OTE/JUDAS/UTC emitted via the formula functions above). |
| Params | `E07_DEFAULTS` + `get_params(overrides)` (unknown keys rejected; §6 literals: th_int 0.7, th_weight 0.6, th_mss 0.65, ote 0.62/0.79/0.705, judas 0.25/1.0/3, conf 0.4/0.25/0.2/0.15, expiry 20). |

**E07↔E12 DEFERRED-INTEGRATION NOTE (ledger — do not forget):** E07 codes the "E12 unavailable → degraded" branch at CP-4: when `context['temporal_windows']` is absent, `temporal_source = "E07_UTC_FIXED_DEGRADED"` and the bundle uses the internal UTC-fixed `KZ.v2.1.1` window (aligned with canonical E12 §3.5); E12 evidence is NEVER fabricated. The E07↔E12 integration test that asserts the degraded branch RESOLVES when real E12 evidence is present is scheduled at CP-5 (PHASE2_CHECKPOINTS.md §CP-5: "ADD E07↔E12 both-mode integration test (degraded branch must now assert it resolves when E12 present)"). CP-5 must consume `temporal_windows` from E12 and assert `temporal_source == "E12"` for the same window that produced `E07_UTC_FIXED_DEGRADED` without it.

### E08 (`apex.engines.e08_wyckoff`, ENGINE="E08_Wyckoff", CONTRACT_VERSION="4.0.0" = APEX-CONTRACT-WYCKOFF-V4.0.0, ε=1e-8)

| symbol | signature / semantics |
|---|---|
| `run_engine(bars, params=None, atr_series=None, vol_ratios=None, structure_events=None, symbol="", timeframe="6h") -> {"engine","results","cycle_state","events","phases_history"}` | batch driver; `cycle_state` = `{phase_hypotheses (8 phases), entropy, fate, range{lo,hi,age_bars,atr}, confirmed_events, snapshot_id, quality}`. |
| `WyckoffEngineV4(params=None)` | `process_bar(bar, atr, vol_ratio, close_pos, evr, bos_event, structure="BULL") -> dict` (idempotent per bar). |
| `E08WyckoffEngine(EngineBase)` | `compute(...)`; context keys: `window`/`provider`, `e08_params`, `atr_series` (E04), `vol_ratios` (E03), `structure_events` (E01), `regime` (E11 — optional; absent → degraded, MARKUP/MARKDOWN validity not asserted). |
| Formulas (§3/§4) | `rma(series, n)`; `softmax(z)`; `entropy(p)`; `phase_probabilities(scores, w, phases) -> (probs, H)`; `detect_sc/ar/st/spring/sos/lps/ut` (6-parameter contract); `cause_effect_target(range_cause, duration, k, gamma)`; `pf_target(breakout, columns, box_size, reversal_rows)`; `evr_correlation(vols, abs_returns)`; `detect_range(bars, atr, min_bars)`; `transition_matrix(n_obs=None, alpha=0.1)` (uniform Dirichlet prior when no counts); `brier_score(...)`; `wilson_ci(...)`; `score_position/evr/volume/structure/age`. |
| Encyclopedia | `encyclopedia_chapter(n)` — ch.1 returns the complete Historical Foundation; ch.2–4 raise `WaveOutError("e08_encyclopedia_ch2_4", ...)` (§9.5-9/G6/D-E08-M5). |
| Params | `E08_DEFAULTS` + `get_params(overrides)`: sc_vol_ratio 2.5, sc_range_z 2.0, ar_min_ratio 0.5, st_vol_ratio 0.7, spring_pen_max 0.3, spring_vol_min 1.3, sos_vol_min 1.2, entropy_threshold 0.85, cause_effect k 0.42/γ 0.71, evr_rho_threshold 0.2, max_age_bars 96. |

### E09 (`apex.engines.e09_trend`, ENGINE="E09_Trend", CONTRACT_VERSION="4.0.0", ε=1e-12)

| symbol | signature / semantics |
|---|---|
| `run_engine(bars, params=None, swings=None, atr=0.0, mom_series=None, symbol="", timeframe="1h") -> {"scales","bias","snapshot_id","as_of_bar","alignment","divergence","events"}` | batch driver; `scales` keyed MICRO/SHORT/INTER/MACRO with `{direction, strength, quality, quality_label, seq_score, slope_z, pos, r2, adx, di_plus, di_minus, hurst, mk_z, evidence_count}`. |
| `TrendEngine(params=None)` | `process_bar(bars, swings, atr, mom_series) -> dict` (cached by bar close). |
| `E09TrendEngine(EngineBase)` | `compute(...)`; context keys: `window`/`provider`, `e09_params`, `swings` (E01 `{type HH/HL/LH/LL/EQ, idx, confirmed_at_idx}`), `atr` (E04), `mom_series` (E10 — optional). Emits one EvidenceEvent per scale. |
| Formulas (§3/§4) | `validate_bar(bar)`; `compute_seq_score(swings, window, current_idx)`; `ols_slope_newey_west(ts, ys)`; `mann_kendall_with_tie_correction(x)`; `anis_lloyd_expected_rs(n)`; `hurst_rs_anis_lloyd_corrected(x, min_len, max_len)`; `wilder_rma(prev, curr, n)`; `compute_adx_wilder(bars, n)`; `compute_pos_scale(bars, window, atr)`; `trend_direction_and_strength(...)`; `compute_trend_quality(r2, adx, hurst)` (§3.8 H_clip); `quality_label(q, r2, adx, hurst)`; `divergence_exhaustion_check(...)`; `alignment_of(bias)`; `wilson_ci(...)`. |
| Params | `E09_DEFAULTS` + `get_params(overrides)`: windows 5/20/60/240, w_a_b_c 0.4/0.35/0.25, slope_z_threshold 1.5, pos_threshold 0.3, strength_th 0.5, adx_n 14, mk_crit_z 1.96, hurst_window 128, hurst_min_len 8, stack_weights 0.1/0.2/0.3/0.4, divergence_delta 0.1, r2_min_for_Q 0.2, adx_min_for_trend 15. |

### Cross-engine consumption contract (CP-5 builds on this)

- E04 `run_engine(...)["atr_series"]` → E07 `atr_series`, E08 `atr_series`, E09 `atr` (left-pad first bar with `ATR_FLOOR=1e-8`).
- E01 swing points → E09 `swings` (`{type, idx, confirmed_at_idx}`); E01 BOS/CHoCH → E07 `structure_events` and E08 `structure_events`.
- E05 FVG zones → E07 `fvg_events` (`{present, direction, lower, upper}`); E02 sweeps → E07 `sweep_events`; E03 volume → E07 `volume_events` / E08 `vol_ratios`.
- E12 temporal windows → E07 `temporal_windows` (OPTIONAL at CP-4; see deferred-integration note above). E11 regime → E08 `regime` (optional).
- E10 momentum → E09 `mom_series` (optional; divergence path).

## DATA-CHANGES

none. No new tables/columns/migrations; emissions insert through the frozen CP-1 `evidence_event` DDL via `SQLiteStore.insert_evidence` (round-trip asserted in tests/integration/test_cp4_engines.py). No params YAML added (six-YAML law, ISSUE-CP2-006 pattern: §6 tables live as frozen in-package defaults).

## TESTS

Run: `PYTHON=/home/user/Upstage/.venv/bin/python bash scripts/run_all_tests.sh` → **593 passed, 0 failed**.

| test file | ids covered | result |
|---|---|---|
| tests/unit/test_e07_rtm.py | E07 §8.1 15 golden fixtures (re-derived), §8.2 replay, §8.3 no-leak + governed_as_of_ms, §8.4 ablation, §8.5 Wilson, §8.6 redundancy, §8.7 serialization, event catalog, params, E12-unavailable degraded branch, EngineBase binding (24-field), T-DR-001 | 33 passed |
| tests/unit/test_e08_wyckoff.py | E08 event contract (re-derived from §9), three laws (EVR/CE/ER), phase+entropy+AMBIGUOUS, Dirichlet transition matrix, replay, no-leak, Brier, redundancy, serialization, encyclopedia ch.1 + ch.2–4 Wave-Out, params, EngineBase binding, T-DR-001 | 44 passed |
| tests/unit/test_e09_trend.py | E09 §8.1 FIX_01..11 (re-derived), §7 seq_score examples, replay, no-leak, ablation, Wilson, redundancy, serialization, Wilder ADX internals, Anis-Lloyd, params, EngineBase binding, T-DR-001 | 29 passed |
| tests/integration/test_cp4_engines.py | E09←E04/E01 chain, E07 bundle + E12-degraded branch, E08←E04 ATR, store-DDL emissions, T-DR-001 ×3 | 6 passed |

## DEVIATIONS

- ADR-P2-002 applied: dev-only pytest via venv; runtime deps unchanged (nine SBOM pins).
- ADR-P2-007 applied: every §8.1 fixture value re-derived by recomputation; doc-divergent values recorded as `doc_inconsistency` notes (ISSUE-CP4-005/006/007), never copied.
- ADR-P2-014 applied: where the doc fixture and the §4 executable formula disagree, the formula wins; the divergence is recorded (ISSUE-CP4-004/005/006/007).
- ADR-P2-015 applied: no earlier implementation attempt referenced; built from the frozen blueprint only.
- G6/§9.5-9 applied: E08 encyclopedia ch.2–4 raise `WaveOutError("e08_encyclopedia_ch2_4", ...)` — never stubbed. E07 E12-unavailable degrades deterministically (never fabricated).
- ISSUE-CP2-006 pattern applied: §6 parameter tables as frozen in-package defaults with `get_params` unknown-key rejection.

## OPEN-ISSUES

All logged in DECISION_LOG §B/CP-4 (verbatim, all CLOSED): [ISSUE-CP4-001] E09 Hurst-clip phrasing (§3.8 applied); [ISSUE-CP4-002] E08 transition-matrix "K=9" vs 8 phases (K=8 applied); [ISSUE-CP4-003] CP-4 "E09 AD-line" has no normative anchor (ADX + multi-scale implemented, no invention); [ISSUE-CP4-004] E07 UTC `which` single-vs-multi-entry (doc_inconsistency); [ISSUE-CP4-005] FIX_01 Q_min not reproducible (5 bars < 2n); [ISSUE-CP4-006] FIX_03 MICRO_dir 0 not reproducible (raw slope_z); [ISSUE-CP4-007] FIX_04 15 bars insufficient for ADX14. Carried-over (still open upstream): [ISSUE-CP2-006]/[ISSUE-CP2-016] (CP-8 dispositions); [ISSUE-CP3-013] (CP-8). CP-5 MUST pick up the E07↔E12 deferred-integration note (§INTERFACES above).

## HOW-TO-RUN

```bash
cd /home/user/Upstage
# one-time (sandbox already provisioned):
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock pytest==8.4.2   # pytest dev-only (ADR-P2-002)

# full suite (593 tests):
PYTHON=/home/user/Upstage/.venv/bin/python bash scripts/run_all_tests.sh

# per-engine batteries:
/home/user/Upstage/.venv/bin/python -m pytest tests/unit/test_e07_rtm.py tests/unit/test_e08_wyckoff.py tests/unit/test_e09_trend.py tests/integration/test_cp4_engines.py -q

# demo (E07 chain over a deterministic window, E12 absent → degraded):
/home/user/Upstage/.venv/bin/python - <<'EOF'
from tests.integration.test_cp4_engines import lcg_window
from apex.engines.e07_rtm import run_engine as run_e07
bars = lcg_window(120)
r = run_e07(bars, sweep_events=[{"valid_at_idx":1,"ts":3600000,"p_confirm":0.9}],
            structure_events=[{"kind":"BOS","valid_at_idx":3,"ts":10800000}],
            fvg_events=[{"present":True,"valid_at_idx":4,"ts":14400000,"touch_count":1}],
            volume_events=[{"valid_at_idx":5,"ts":18000000,"p_confirm":0.9}],
            mtf_align=1.0, as_of_ms=18000000)
print("temporal_source:", r["temporal_source"])
print("bundles:", [(b.framework_id, b.resolution_class) for b in r["bundles"]])
EOF
```

No servers, no data files, no migrations. Engines are pure over closed-candle windows; the only runtime surface is `compute(symbol, timeframe, as_of, context)` per engine.

## REMAINING WORK LEDGER

none — stage fully closed. Notes for successors (not gaps): (1) CP-5 MUST implement the E07↔E12 both-mode integration test — the degraded branch is already coded and tested here; CP-5 asserts it resolves to `temporal_source == "E12"` when E12 evidence is supplied (PHASE2_CHECKPOINTS.md §CP-5). (2) CP-5 appends §CP-5-INTEGRATION-NOTES (merged 12-engine topic/version map) to PHASE2_HANDOFF_CP5.md. (3) The sandbox checkout is shallow — CP-5 should re-verify predecessor ranges once full history is available.
