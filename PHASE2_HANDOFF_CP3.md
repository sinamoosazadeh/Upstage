# PHASE2 HANDOFF — CP-3 → consumed by CP-4 (and CP-8 closeout)
Stage: CP-3 — Engines E04 Volatility, E05 FVG, E06 OrderBlock
Rules (PROTOCOL P16): author = CP-3 executor (or its continuation session — state which, first line of STATUS). ≤400 lines, nine headings below in order. Successors read ONLY this file + their own prompt/law/checkpoint sections; interfaces listed here are the public contract they may code against. First STATUS line: `LAW-ACK: G1..G20 + P1..P21 read <UTC>`.

## STATUS

LAW-ACK: G1..G20 + P1..P21 read 2026-09-12T08:40Z (single-executor session; continuation of the same session that executed CP-3 from the entry gate).

COMPLETE. CP-3 fully closed: E04 Volatility v4.0.0, E05 FVG v4.0.0, E06 OrderBlock v4.0.0 built from zero per the frozen blueprint (chapter order §3→§4→§5→§6→§7→§8 mirrored in each engine file), every §8 battery clause executed as a test, golden fixtures re-derived per ADR-P2-007.

- Suite: **481 passed / 0 failed** (`tests/unit` + `tests/integration`; baseline 305 CP-1/CP-2 + 176 new CP-3 tests: E04 66, E05 49, E06 53, integration 8).
- Branch: `arena/01a094c8-upstage` (pinned by environment; owner merges to main plain-merge per ENV NOTE). Commits (format `[CP-3] <module>: <what changed>`): 8024232 board IN-PROGRESS → a27b362 E04 → a58cdc9 E05 → (E06 + integration + control files: subsequent commits on this branch; see `git log --oneline main..arena/01a094c8-upstage`).
- Environment: Python 3.11.2, Linux (sandbox); dev venv /home/user/apex-venv (nine SBOM runtime pins + pytest 8.4.2 dev-only; ADR-P2-002 / ISSUE-CP1-013). Runtime deps unchanged — no new pins. NOTE: the sandbox checkout is SHALLOW (one visible commit at main 2d503e2), so predecessor commit ranges (CP-1/CP-2) cannot be SHA-verified here; file contents and the green entry-gate suite were verified instead.

## DELIVERED

| file | purpose | blueprint section |
|---|---|---|
| apex/engines/e04_volatility/engine.py (+ __init__.py) | E04 Volatility v4.0.0: HV/RV family, EWMA/GARCH/HAR-RV, squeeze/expansion/regime state machine, PIT quantile regime banding, Ljung–Box + non-directional fallback, vol targeting; ε=1e-12 tier; adaptive ATR E04↔E11 raises WaveOutError (never built) | APEX_GEN5.md L4955–5601 (§3–§8 order mirrored) |
| apex/engines/e05_fvg/engine.py (+ __init__.py) | E05 FVG v4.0.0: Gates A–D detection, ICT zone [H_{t−2}, L_t] with negative-width safety net, classification tree (CONVENTIONAL/BISI/SIBI/DOJI/REJECTION/SEQUENTIAL/INVERSE), salience + premium/discount, full lifecycle (FRESH→TOUCHED→MITIGATED→FILLED / EXPIRED), IoU/containment merge, v3→v4 adapter | APEX_GEN5.md L5602–6859 |
| apex/engines/e06_orderblock/engine.py (+ __init__.py) | E06 OrderBlock v4.0.0: origin + multi-candle displacement + corrected Context, asymmetric zones, Q0–Q4 ladder, lifecycle (CANDIDATE→ACTIVE→RETESTED→MITIGATED→INVALIDATED/EXPIRED), BREAKER reclaim, MITIGATION_BLOCK (Q2 research cap), merge/confluence; evidence-only consumption (§1.4) with fail-closed intake | APEX_GEN5.md L6860–8292 |
| tests/unit/test_e04_volatility.py | E04 §8.1–8.8 battery + EngineBase binding + Wave-Out + T-DR-001 re-run | E04 §8 |
| tests/unit/test_e05_fvg.py | E05 §8 battery + lifecycle + serialization + T-DR-001 re-run | E05 §8 |
| tests/unit/test_e06_orderblock.py | E06 §8 battery incl. mandated consumption-lint test (zero internal SMA/ATR/Wilder recomputation; no e01–e05 imports) + bar-driven lifecycle + T-DR-001 re-run | E06 §8 + CP-3 stage prompt |
| tests/integration/test_cp3_engines.py | Cross-engine chains: E04→E05/E06 ATR evidence, E05→E06 FVG Context term, §8.6 redundancy gate, store-DDL emission inserts, T-DR-001 across all three engines | E04/E05/E06 §8.6 + CP-3 EXIT box |
| tests/fixtures/e04_golden_fixtures.json | 12 re-derived E04 golden fixtures (doc_inconsistency notes where the doc's own values diverge) | E04 §8.1 |
| tests/fixtures/e05_golden_fixtures.json | 10 re-derived E05 golden fixtures | E05 §8.1 |
| tests/fixtures/e06_golden_fixtures.json | 12 verbatim-from-doc E06 fixtures with re-derived semantics notes | E06 §8.1 |
| PHASE2_DECISION_LOG.md §B/CP-3 | ISSUE-CP3-001..013 entries | G13 |
| PHASE2_TRACEABILITY_MATRIX.md, PHASE2_CHECKPOINT_STATUS.md | CP-3 rows / board boxes | G18 |

## INTERFACES

All three engines bind the frozen EngineBase contract (`apex/engines/base.py`, consumed never patched): `compute(symbol, timeframe, as_of, context) -> List[EvidenceEvent]` with `context['window']: List[MarketObservation]` (or sync `context['provider']`); every emission validates the 24-field EvidenceEvent frame; topics `evidence.{engine_id}.{condition_state}`. Shared helpers: `observation_to_bar(obs[, timeframe])`.

### E04 (`apex.engines.e04_volatility`, ENGINE="E04_Volatility", CONTRACT_VERSION="4.0.0", ε=1e-12)

| symbol | signature / semantics |
|---|---|
| `VolatilityEngineV4(params=None, timeframe="1h", risk_budget=0.0)` | §4 streaming engine. `ingest_bar(bar: dict) -> Optional[VolatilityEvidence]` (bar keys o/h/l/c/v/ts; one CLOSED candle; returns evidence carrying `state: VolatilityState`, `atr_scalar: float`, `events: list`); `output() -> dict` (engine/version/bars/regime/in_squeeze/garch_status/nondir_fallback/last_error); `request_adaptive_atr(regime_source="E11")` ALWAYS raises `WaveOutError("adaptive_atr_e04_e11", ...)` (§9.5-9/G6); `atr_series_for(symbol, timeframe, as_of, context) -> List[float]` (left-pads with `ATR_FLOOR=1e-8` for the evidence-free first bars). |
| `run_engine(bars, params=None, timeframe="1h", risk_budget=0.0) -> {"engine", "states", "events", "atr_series"}` | batch driver; `atr_series` is the governed ATR evidence other engines consume (length = bars that produced evidence). |
| `E04VolatilityEngine(EngineBase)` | `compute(symbol, timeframe, as_of, context)`; context keys: `window` / `provider`, `e04_params`, `risk_budget`, `adaptive_atr`/`adaptive_period` (raise WaveOutError). Emits regime/squeeze/expansion evidence on `evidence.E04.*`. |
| `VolatilityState` | 21 required fields (`VOLATILITY_STATE_REQUIRED`), `to_canonical()` (excludes snapshot_id), `update_snapshot()`; `load_state(payload)` round-trips fail-closed. |
| Formulas (§3, all PIT-safe) | `annualized_hv(returns, bars_per_year)`, `realized_var(...)`, `ewma_vol_step(prev, r, lam)`, `garman_klass`, `parkinson_raw`, `parkinson_adjusted`, `rogers_satchell`, `overnight_var`, `oc_var`, `bollinger_width`, `range_z`, `rolling_quantiles(series, window, qs)` (linear interpolation; NaN if len ≤ window), `regime_from_hv(hv, qs, rz)` → `REGIMES` (CRUSHED/LOW/NORMAL/ELEVATED/EXTREME), `cluster_persistence`, `chi2_sf(x, df)`, `t_sf_two_sided(t, df)`, `ljung_box(returns, m) -> (Q, p_exact)`, `nondirectional_test(returns)`, `garch_mle_fit(returns)` (deterministic restart grid + coordinate search, stdlib-only; EWMA fallback w/ degraded flag), `har_rv_fit(rv_series)`, `wilson_ci(p_hat, n, z=1.96)`, `vol_targeting(risk_budget, atr, regime, k=K_TARGETING)`, `snapshot_id(content_dict)` (canonical §9.5-5 form). |
| Params | `E04_DEFAULTS` + `get_params(overrides)` (unknown keys rejected; §6 literals). |
| Events | `EVENT_CATALOG` EV_VLT_001..008 (regime up/down, squeeze start/end, expansion, extreme, …); EV_VLT_005 carries `bos_required=True` note. |

### E05 (`apex.engines.e05_fvg`, ENGINE="E05_FVG", CONTRACT_VERSION="4.0.0", ε=1e-8)

| symbol | signature / semantics |
|---|---|
| `FVGEngine(params=None, tick_size=0.01, symbol="")` | §4 streaming lifecycle manager. `process_bar(bars, i, htf_fvgs=None, trend_htf=None, bos_events=None, struct_role=0.5, atr_override=None) -> List[event dict]` — one CLOSED candle; idempotent per (idx, ts); events `EV_FVG_001..009`. Active zones in `active_fvgs: Dict[fid, FVGObject]`, terminal in `history`. |
| `run_engine(bars, params=None, tick_size=0.01, symbol="", htf_fvgs_by_idx=None, trend_htf_by_idx=None, bos_by_idx=None, atr_by_idx=None) -> {"engine","events","active","history"}` | batch driver; `atr_by_idx` is the E04 evidence pathway (else §4 PIT fallback `atr_calc`). |
| `E05FVGEngine(EngineBase)` | `compute(...)`; context keys: `window`/`provider`, `e05_params`, `tick_size`, `atr_series` (E04_ATR governed input — consumed, never recomputed for normative decisions), `htf_fvgs_by_idx` (MTF_FVG_HTF@^4.0.0), `trend_htf_by_idx`, `bos_by_idx` (E01_STRUCTURE_BOS@^3.2.0). Emits FVG_ZONE@^4.0.0 evidence. |
| `FVGObject` (dataclass) | 21 required contract fields (`FVG_ZONE_REQUIRED`) + extras; `validate_schema()` (enums: FTYPES, QTAGS incl. Q3_Experimental, FATES); `update_snapshot()` canonical. |
| Detection / classification (§3) | `detect_fvg_at(bars, i, theta_min_w, min_abs_ticks, tick_size, atr_override=None)` — Gates A–D; ICT zone bull `[H_{t−2}, L_t]`, bear `[H_t, L_{t−2}]`; Gate_D = `width ≥ θ_minW·ATR ∧ width ≥ min_abs_ticks·tick` with θ_minW = 0.2 FROZEN (CP-E05-001's 0.25 NOT applied); returns `{direction, lower, upper, width, atr, at_idx, at_ts, b2, b1, b0}` or `{"invalid_reason": ...}`. `classify_fvg(det, bars, i, params, htf_fvgs=None, trend_htf=None, bos_events=None) -> (ftype, penalty)`. |
| Salience / mitigation | `compute_salience_and_premium(det, ftype, penalty, bars, i, params, struct_role=0.5, vr_override=None) -> (sal0, sal, freshness, z_mid)` — `vr_override=0.0` is the documented Q1-warmup conservative path (ISSUE-CP3-007); direct contract calls raise `INSUFFICIENT_HISTORY_Q1`. `mitigation_of(fvg, bar, prev_close) -> (touch, depth, dir)`; `freshness_decay(age, half_life)`; `iou_of(a_lo,a_hi,b_lo,b_hi)`; `body_ratio(bar)`; `vol_ratio(bars, idx, lookback=20)` (None ⇒ warmup); `range_20(bars, idx, lookback=20)`; `wilson_ci(p_hat, n, z=1.96)`; `load_v3_adapter(payload)` (v3→v4 read-only; ambiguity fail-closed). |
| Params | `E05_DEFAULTS` + `get_params(overrides)`; frozen literals per §6 (min_width_atr=0.2, half_life_bars=48, fresh_thr=0.15, iou_merge_thr=0.7, salience_weights=(0.35,0.25,0.25,0.15), inverse_enabled=False, …). |
| Lifecycle semantics | Quality: Q2 at classification (CONVENTIONAL/BISI/SIBI), Q3 other/unproven, Q4 TOUCHED, Q5 FILLED, QX_EXPIRED terminal; expiry `age ≥ max_age_bars OR freshness < fresh_thr` (boundary-inclusive, ISSUE-CP3-004); merge IoU > 0.7 OR containment → bounds union, S = max×1.1, `extra["merged_from"]`. |

### E06 (`apex.engines.e06_orderblock`, ENGINE="E06_OrderBlock", CONTRACT_VERSION="4.0.0", ε=1e-8)

| symbol | signature / semantics |
|---|---|
| `OrderBlockEngine(params: EngineParams = None)` | §4 streaming engine, EVIDENCE-ONLY. `ingest_bars(bars_closed, volume_evidence, volatility_evidence)` — lengths must align (`UPSTREAM_EVIDENCE_ALIGNMENT_QX`); missing/misaligned entries raise `MISSING_VOLUME_EVIDENCE_QX` / `MISSING_VOLATILITY_EVIDENCE_QX` / `INVALID_VOLATILITY_EVIDENCE_QX`; volume PIT violation raises `VOLUME_EVIDENCE_PIT_QX`. `detect_at(origin_idx, structure_events, fvg_events) -> Optional[OB]` (Gates: BodyRatio ≥ θ_body, opposite-direction displacement, Disp_multi ≥ θ_disp, corrected Context `VR ≥ θ_vol ∧ (FVG ∨ Disp_multi ≥ θ_disp_high)`, structural event for Q3; asymmetric zone ±θ_tol·ATR; width floor; delayed confirmation t+K; lifecycle never touches bars ≤ confirmed_at). `update_with_bar(bar_idx)` — invalidation ±θ_inv_tol·ATR, directional mitigation (§2.8 wrong-side never counts), expiry θ_age=144, BREAKER reclaim, MITIGATION_BLOCK reactivation (Q2 cap), IoU merge, confluence. `run_full(bars, struct_events_by_idx, fvg_by_idx, volume_evidence, volatility_evidence) -> List[OB]` (struct events gathered from idx i..i+2 per origin i). |
| `run_engine(bars, struct_events_by_idx=None, fvg_by_idx=None, volume_evidence=None, volatility_evidence=None, params=None) -> {"engine","obs","events"}` | batch driver; **raises `MISSING_EVIDENCE_QX` when either evidence stream is omitted** (§1.4 fail-closed; SMA/ATR are NEVER recomputed). |
| `E06OrderBlockEngine(EngineBase)` | `compute(...)`; context keys: `window`/`provider`, `e06_params`, `struct_events_by_idx` (I_Structure_v4: `{kind, direction, level, ts, valid_at_idx}`), `fvg_by_idx` (I_FVG_v4: `{present, direction, lower, upper, type}`), `volume_evidence` (I_Volume_v4: `{volume_sma, volume_ratio, snapshot_id, as_of_ts[, availability_time_ms]}`), `volatility_evidence` (I_Volatility_v4: `{atr_n, tr_method, snapshot_id, as_of}`). |
| `OB` (dataclass) | `OB_REQUIRED` fields + lifecycle extras; `to_canonical()` (excludes snapshot_id/lineage), `validate_schema()`; `e06_snapshot_id(ob)` canonical. |
| Evidence shape | `struct_events`: `{kind: "BOS"|"CHoCH", direction: "UP"|"DOWN", valid_at_idx: int}`; `fvg_zones`: `{present, direction, lower, upper}` consumed only when `present=True` ∧ direction == displacement direction ∧ |mid−origin_close| ≤ 2·ATR. |
| Helpers | `body_ratio_pit(bar)` (H<L → 0), `iou_zones`, `asymmetric_zone(direction, bar, atr, zone_tol)`, `directional_mitigation(ob, bar, prev_close, first_touch_strict) -> (touch, side_ok, depth)`, `promote_quality(ob, checks, ts=0)` (Q0→Q4 ratchet + lineage), `promote_q4(touches, n)` (Wilson lower > 0.5 ∧ exact binomial p < 0.05), `wilson_ci`, `binomial_test_gt_half(k, n)` (exact, lgamma), `load_v3_adapter(payload)` (v3 zone derivation from zone_lo/hi or origin_high/low; ambiguity/version fail-closed), `canonical_hash(obj)`. |
| Params | `E06_DEFAULTS` + `get_params(overrides)`: body_min=0.55, disp_min=1.5, disp_high=1.8, zone_tol=0.15, vol_min=1.3, max_age_bars=144, mit_activate=0.5, min_width_atr=0.15, inv_tol=0.2, iou_thresh=0.7, merge_bars=20, disp_max_k=5, salience_weights=(0.35,0.25,0.25,0.15). |
| Events | `EVENT_CATALOG` EV_OBK_001..009 (Formed, Displacement_Confirmed, Retested, Mitigated, Invalidated, Expired, Breaker_Converted, Confluence, Reversal_OB_Confirmed). |

### Cross-engine consumption contract (CP-4/CP-6 build on this)

- E04 `run_engine(...)["atr_series"]` (or `E04VolatilityEngine.atr_series_for`) → E05 `atr_by_idx` and E06 `volatility_evidence[].atr_n` (left-pad first bar with `ATR_FLOOR=1e-8`).
- E05 active zones → E06 `fvg_by_idx` as `{present: True, direction, lower, upper, type}`.
- E01 structure events → E06 `struct_events_by_idx` (`{kind, direction, valid_at_idx}`), gathered per origin over idx i..i+2.
- Volume evidence for E06 is I_Volume_v4 shape (`volume_sma`, `volume_ratio`, `snapshot_id`, `as_of_ts`), produced by E03.
- Redundancy guard (§8.6): zones with IoU > 0.6 ∧ midpoint distance < 0.2·ATR are redundant; keep higher Salience (asserted in integration).

## DATA-CHANGES

none. No new tables/columns/migrations; emissions insert through the frozen CP-1 `evidence_event` DDL via `SQLiteStore.insert_evidence` (round-trip asserted in tests/integration/test_cp3_engines.py). No params YAML added (six-YAML law, ISSUE-CP2-006 pattern: §6 tables live as frozen in-package defaults).

## TESTS

Run: `PYTHON=/home/user/apex-venv/bin/python bash scripts/run_all_tests.sh` → **481 passed, 0 failed**.

| test file | ids covered | result |
|---|---|---|
| tests/unit/test_e04_volatility.py | E04 §8.1 golden F01–F12 (re-derived), §8.2 500-bar deterministic replay byte-identical, §8.3 no-future-leak (shock-last-bar regime stability, prefix ATR identity), §8.4 ablation (YZ-RMSE vs C2C; Wilder-var < SMA-var), §8.5 Wilson wide-CI, §8.6 redundancy gates, §8.7 v3-payload rejection + v4 roundtrip, §8.8 non-directional fallback, event machine (squeeze/expansion/regime), §6 frozen params, Wave-Out ×2, EngineBase binding (24-field emissions), T-DR-001 | 66 passed |
| tests/unit/test_e05_fvg.py | E05 §8.1 ten golden fixtures (re-derived), §8.2 replay, §8.3 PIT/no-leak, §8.4 ablation (per-component zeroing), §8.5 Wilson calibration, §8.6 redundancy threshold, §8.7 v3→v4 adapter, §6 params (incl. CP-E05-001 key rejection), lifecycle FRESH→TOUCHED→MITIGATED→FILLED/EXPIRED, events EV_FVG_001..009, EngineBase binding, T-DR-001 | 49 passed |
| tests/unit/test_e06_orderblock.py | E06 §8.1 twelve fixtures (semantics re-derived), CONSUMPTION LINT (no Wilder/SMA/ATR recomputation internals, no e01–e05 imports), §1.4 fail-closed evidence intake (6 negative paths), §8.2 replay (canonical hash), §8.3 no-future-leak (guarded list), §8.4 ablation ladder, §8.5 calibration (Wilson + exact binomial), §8.6 merge/confluence, §8.7 v3 adapter, bar-driven lifecycle incl. BREAKER + wrong-side immunity, EngineBase binding, T-DR-001 | 53 passed |
| tests/integration/test_cp3_engines.py | E04→E05/E06 ATR chain, E05→E06 FVG Context term (Q3 lift), §8.6 cross-engine redundancy gate, emissions insert through store DDL (E04+E05+E06), T-DR-001 all three engines, MISSING_EVIDENCE_QX fail-closed | 8 passed |

## DEVIATIONS

- ADR-P2-002 applied: dev-only pytest via venv; runtime deps unchanged.
- ADR-P2-007 applied: every §8.1 fixture value re-derived by recomputation; doc-divergent values recorded as `doc_inconsistency` notes (never copied).
- ADR-P2-014 applied: where the doc text and its own fixtures disagree, the fixture is canonical (ISSUE-CP3-004/005/007/011).
- ADR-P2-015 applied: no earlier implementation attempt referenced; built from the frozen blueprint only.
- G6/§9.5-9 applied: adaptive ATR (E04↔E11) raises `WaveOutError("adaptive_atr_e04_e11", ...)`; not implemented.
- ISSUE-CP2-006 pattern applied: §6 parameter tables as frozen in-package defaults with `get_params` unknown-key rejection.

## OPEN-ISSUES

All logged in DECISION_LOG §B/CP-3 (verbatim): [ISSUE-CP3-001] exact χ²/t CDFs vs §4 coarse p-steps (CLOSED); [ISSUE-CP3-002] abandoned max/min zone formula (CLOSED); [ISSUE-CP3-003] Ljung–Box criticals vs exact p (CLOSED); [ISSUE-CP3-004] freshness expiry boundary-inclusive (CLOSED); [ISSUE-CP3-005] INVERSE VR gate during warmup (CLOSED); [ISSUE-CP3-006] MITIGATION_BLOCK Q2 cap (CLOSED); [ISSUE-CP3-007] VolRatio warmup conservative-0 in streaming path (CLOSED); [ISSUE-CP3-008] E04 regime fixture missing RZ + §7 YZ approximate intermediates (CLOSED); [ISSUE-CP3-009] doc fixture bars failing own gates (CLOSED); [ISSUE-CP3-010] IoU 0.6 vs doc 0.75 (CLOSED); [ISSUE-CP3-011] E06 fixture 10 effective-touch semantics (CLOSED); [ISSUE-CP3-012] E06 fixture 2 Q2 label vs §1.6 ladder (CLOSED); [ISSUE-CP3-013] resolution_class Q0..QX comment vs Q0..Q5 validator (CLOSED; CP-8 may reconcile). Carried-over context: [ISSUE-CP2-006]/[ISSUE-CP2-016] remain OPEN per CP-2 (CP-8 dispositions); CP-3 consumed the pattern, changed nothing.

## HOW-TO-RUN

```bash
cd /home/user/Upstage
# one-time (sandbox already provisioned):
python3 -m venv /home/user/apex-venv
/home/user/apex-venv/bin/pip install -r requirements.lock pytest   # pytest dev-only (ADR-P2-002)

# full suite (481 tests):
PYTHON=/home/user/apex-venv/bin/python bash scripts/run_all_tests.sh

# per-engine batteries:
/home/user/apex-venv/bin/python -m pytest tests/unit/test_e04_volatility.py tests/unit/test_e05_fvg.py tests/unit/test_e06_orderblock.py tests/integration/test_cp3_engines.py -q

# demo (E04 → E05/E06 chain, deterministic):
/home/user/apex-venv/bin/python - <<'EOF'
from tests.integration.test_cp3_engines import lcg_window, e04_atr_series
from apex.engines.e05_fvg import run_engine as run_e05
bars = lcg_window(90)
_, atr = e04_atr_series(bars)
r = run_e05(bars, tick_size=0.01, symbol="BTCUSDT",
            atr_by_idx={i: atr[i] for i in range(len(bars))})
print("FVG zones:", len(r["active"]), "history:", len(r["history"]))
EOF
```

No servers, no data files, no migrations. Engines are pure over closed-candle windows; the only runtime surface is `compute(symbol, timeframe, as_of, context)` per engine.

## REMAINING WORK LEDGER

none — stage fully closed. Notes for successors (not gaps): (1) CP-4 consumes E04–E06 strictly via the INTERFACES tables above; E06 requires both evidence streams or raises `MISSING_EVIDENCE_QX`. (2) Real-data verification of the §8.4/§8.5 research numbers (ablation precision deltas, OOS touch rates) remains with the research stage's ADR-P2-005 harness (ISSUE-CP2-015 discipline). (3) ISSUE-CP3-013 leaves a cosmetic comment/validator mismatch in the frozen contracts file for CP-8 triage. (4) The sandbox checkout is shallow — CP-4 should re-verify predecessor ranges once full history is available.
