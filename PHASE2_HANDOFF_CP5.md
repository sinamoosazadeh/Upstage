# PHASE2 HANDOFF — CP-5 → consumed by CP-6 (and CP-8 closeout)
Stage: CP-5 — Engines E10 Momentum, E11 Regime, E12 Temporal + §CP-5-INTEGRATION-NOTES (12-engine interface map)
Rules (PROTOCOL P16): author = CP-5 executor (or its continuation session — state which, first line of STATUS). ≤400 lines, nine headings below in order. Successors read ONLY this file + their own prompt/law/checkpoint sections; interfaces listed here are the public contract they may code against. First STATUS line: `LAW-ACK: G1..G20 + P1..P21 read <UTC>`.

## STATUS
LAW-ACK: G1..G20 + P1..P21 read 2026-09-12T00:00Z (author: the CP-5 continuation session in Arena Agent Mode, branch `arena/01a096fc-upstage`; ADR-P2-015 from-zero — no prior implementation attempt was read, referenced, or reused).
complete — stage fully closed. Suite totals: **1048 passed / 0 failed** (`./scripts/run_all_tests.sh`; 322 of them CP-5: E10 63 + E11 78 + E12 165 + integration 16). Entry gate was 726/0; `sha256(APEX_GEN5.md) == 216bcc9e…bd9e` verified at session start and after each sandbox re-creation. Environment: Linux sandbox, Python 3.11 `.venv` with the nine SBOM pins from `requirements.lock` (+ pytest dev-only, ADR-P2-002); numpy 1.26.0 is the only scientific dep used (E11/E12); scipy is NOT a pin — E12's Kruskal–Wallis/Spearman are in-tree (ISSUE-CP5-025).
ENV NOTE (push): commits `26cb10a` (board) · `267dfb4` (E10) · `4f5f7c6` (E11) are pushed to `origin/arena/01a096fc-upstage`; `53007b7` (E12) · `ea12a18` (integration) · the docs/closeout commit are committed locally and QUEUED — the sandbox GitHub token expired mid-session (`gh auth status`: "token no longer valid"). After the Owner reconnects GitHub in Arena: `git pull --rebase origin main && git push origin arena/01a096fc-upstage`. No work is at risk; branch commits are the record.

## DELIVERED
| file | purpose | blueprint section | MATRIX Part III rows |
|---|---|---|---|
| `apex/engines/e10_momentum/engine.py` + `__init__.py` | E10 Momentum v4.0.0: four divergence kinds (REGULAR_BEARISH/REGULAR_BULLISH/HIDDEN_BEARISH/HIDDEN_BULLISH) + CONVERGENCE + NONE, impulse/exhaustion projection, MomentumState_v4, EV_MOM catalog, EngineBase binding | APEX_GEN5.md L10276–11670 (§3 formulas · §4 pseudocode · §5 schema · §6 params · §8 battery · §9 case) | `E10\|1 … E10\|4` |
| `apex/engines/e11_regime/engine.py` + `__init__.py` | E11 Regime v4.0.0: K=9 registry (T-E11-K9), §3.1 norms, 8-dim state vector, rule tree, softmax/Hamilton/EWMA-Σ/Mahalanobis/Gaussian emission, Dirichlet T, 3-bar hysteresis (+continuation), Q0–Q5 cascade, Wilson base rates, live-regime gate default-OFF (wrapper-only), forecast Wave-Out, v3 adapter | L11671–12732 (§2 hysteresis law · §3.1–§3.8 · §4 · §5.1 additionalProperties:false · §5.4 EV_RGM_001–007 · §6 · §8 · §9) + AI.2 L19046–19048 (gate) + §9.5 L20128–20247 (params) | `E11\|1 … E11\|10` |
| `apex/engines/e12_temporal/engine.py` + `__init__.py` | E12 Temporal Context v4.0.0: canonical UTC activity-window registry (sole routing source), derived OVERLAP flag, cores/phases, DayType + configured rollover, corrected FFF squared estimator + Fourier K=4, conditional rates + Wilson, intraday β, in-tree Kruskal–Wallis/Spearman, TemporalContextState_v4 + TemporalProfile_v4, Q0–Q4 ladder, EV_TMP_001–009, `E12TemporalProvider` (the E07 contract), v3 adapter | L12733–13528 (§3.1–§3.6 L12828–12955 · §4 L12956–13168 · §5 L13169–13292 · §6 L13293–13318 · §8 L13387–13452 · §9 case) + AI.2 windows/Rules L18390–18415 | `E12\|1 … E12\|10` |
| `tests/fixtures/e10_golden_fixtures.json` (17) · `e11_golden_fixtures.json` (18) · `e12_golden_fixtures.json` (12) | golden fixtures, expected values independently RE-DERIVED from formulas (ADR-P2-007); per-fixture sha256 computed after the fixture exists (§9.5-3); builders re-runnable | §8.1 of each chapter | cited in `E10\|4`, `E11\|10`, `E12\|10` |
| `tests/unit/test_e10_momentum.py` (63) · `test_e11_regime.py` (78) · `test_e12_temporal.py` (165) | full §8 batteries incl. T-E11-K9, T-E12-Windows, replay/no-leak/ablation/Wilson/redundancy/serialization, params re-assertion, bindings | §8.2–§8.8 of each chapter + AI.10 L18932–18933 | all E1x rows |
| `tests/integration/test_cp5_engines.py` (16) | **E07↔E12 integration BOTH modes** (resolved via the real provider / degraded CP-4 branch re-proven), E11 gate + Wave-Out, T-DR-001 shared-window, store-DDL emissions for E10+E11+E12 | E07 §3.6–§3.7 + CP-5 EXIT boxes | `X-7 … X-9` |

Foundation (`base.py`, store, quality, catalog, identity, config, errors, bus, `params/*.yaml`) was **consumed, never patched**; no foundation file appears in this stage's diff. `params/e11_params_v4.yaml` re-asserted (not edited) against §9.5 AND chapter §6 — zero divergences (`yaml_assertions == []`, ADR-P2-008).

## INTERFACES
(module | class/function | signature | semantics | version) — everything CP-6 may code against; nothing invented, everything cited. All three engines bind the frozen `EngineBase` (`apex/engines/base.py`): `compute(symbol, timeframe, as_of, context) -> List[EvidenceEvent]`, 24-field validation on every emission, topics `evidence.{engine_id}.{condition_state}`. No cross-engine internal imports — DataBus/versioned contracts only (P3).

### E10 — apex.engines.e10_momentum
| symbol | signature | semantics | version |
|---|---|---|---|
| `E10MomentumEngine(EngineBase)` | `.compute(symbol, timeframe, as_of, context)` | context: `window`/`provider` (MarketObservation seq), `e10_params`, `trend_context` (E09 optional; absent ⇒ no downgrade, incompatible ⇒ −1), `volatility_context` (E04 optional). `direction ∈ {−1, 0, +1}` — the only CP-5 engine with a directional vote. | E10_Momentum/4.0.0 |
| `run_engine` | `(bars, params=None, symbol="UNKNOWN", interval="1h", as_of_ms=None, trend_context=None, volatility_context=None) -> dict` | bars = closed-candle dicts `o/h/l/c/v/ts`; payload keys `state, events, engine, contract_version, n_bars`; warmup ⇒ `{"quality":"QX","reason":"INSUFFICIENT_HISTORY_Q1"}` (never a synthetic neutral). | 4.0.0 |
| `MomentumEngine` | `.ingest(bar) -> Optional[state]`; `.output()` | streaming; idempotent duplicate (ts) ⇒ cached state; state keys per §5.1 incl. `divergence` (six-value enum), `impulse`, `exhaustion`, `param_hash`, `snapshot_id`. | 4.0.0 |
| `E10_DEFAULTS` / `get_params` | 20 keys; unknown ⇒ `UNKNOWN_E10_PARAM_QX` | `reference_mode` default "RSI" (ISSUE-CP5-003); interval universe = the frozen 14 TFs (ISSUE-CP5-005). | 4.0.0 |
| **for CP-6/E09** | `mom_series` | E09's `run_engine(..., mom_series=None)` consumes E10's momentum series; `None` ⇒ `MOMENTUM_UNAVAILABLE_DEGRADED_QX` (contract already live since CP-4). | E09 4.0.0 |

### E11 — apex.engines.e11_regime
| symbol | signature | semantics | version |
|---|---|---|---|
| `E11RegimeEngine(EngineBase)` | `.compute(symbol, timeframe, as_of, context)` | context: `candles` (§4 dicts with `ic_inputs`) **or** `window`/`provider` (+`ic_inputs_list`), `W` (9×8) / `b` (9) — **None ⇒ fail-closed EV_RGM_007, no uniform fallback**, `T`, `history`, `mu0`, `Sigma0`, `prev_mom`, `base_rates`, `e11_params`, `live_regime_gate` (default False), `forecast`/`next_regime`/`adaptive_atr` ⇒ `WaveOutError`. `direction = 0` (NG1 context/veto). | E11_Regime/4.0.0 |
| `run_engine` | `(candles, params=None, W=None, b=None, T=None, history=None, mu0=None, Sigma0=None, prev_mom=0.5, base_rates=None, symbol, timeframe, as_of_ms=None, live_regime_gate=False) -> dict` | payload: `regime_state, events, engine, contract_version, n_bars, H_norm, xi_filtered, live_regime_gate{enabled,reason}`. **The gate object lives in this wrapper ONLY — never inside `regime_state` (§5.1 additionalProperties:false).** K≠9 ⇒ `CONFIGURATION_INVALID` (T-E11-K9). | 4.0.0 |
| `regime_state` keys | — | `state` (9 regimes + AMBIGUOUS), `state_raw`, `regime_transition` (NONE/SUSPECTED/CONFIRMED), `probs` (9), `entropy` (RAW nats — θ_H compares raw, ISSUE-CP5-010), `turbulence`, `vector` (8 keys), `Q`, `as_of`, `snapshot_id`, `reason`. | §5.1 v4 |
| `forecast_next_regime` | `() -> NoReturn` | **Wave-Out (§9.5-9): raises `WaveOutError`. CP-6 must NOT call it; the CP-6 forecast engine owns prediction.** | — |
| `catalog_events` / `RegimeEngine` | `(state) -> [{code,as_of,state}]` / streaming class | EV_RGM_001 always; 002 SUSPECTED; 003 CONFIRMED change; 004 H≥θ_H; 005 Tur≥15.5073; 006 Q0/Q1; 007 fail-closed (no probs). `RegimeEngine.update(candle)` idempotent per (ts, as_of). | §5.4 |
| `load_v3_adapter` | `(payload) -> dict` | §8.7 read-only v3 migration ⇒ canonical v4 + Q1; malformed ⇒ QX. | 4.0.0 |
| params | `get_params(overrides=None, use_yaml=True)`; 30 keys | `params/e11_params_v4.yaml` is §9.5-canonical; runtime YAML wins over code defaults; explicit overrides win over both; divergences recorded in `yaml_assertions` (currently `[]`). K=9, θ_H=0.65, λ_EWMA=0.94, hysteresis 3, α_Dirichlet 0.1, delay 48, W_180d_H1=4320. | ADR-P2-008 |

### E12 — apex.engines.e12_temporal
| symbol | signature | semantics | version |
|---|---|---|---|
| `E12TemporalProvider` | `.temporal_window(ts_ms) -> {"which": [primary, +"UTC_W1_W2_OVERLAP"], "core_windows": [...], "is_overlap": bool, "utc_activity_window": str, "window_phase": str, "day_type": str, "rollover_active": bool, "config_version": "v2024a"}` | **THE versioned `E12_Temporal_Context.Contract v4.0.0` surface consumed by E07 `utc_activity_window_check(ts, temporal_provider=...)`** — resolves the CP-4 degraded branch (source becomes `E12_Temporal_Context.Contract v4.0.0`, `degraded=False`, Q5 reachable on the authoritative overlap). E12 owns the registry; E07's local copy stays NON-authoritative fallback. | 4.0.0 |
| `E12TemporalEngine(EngineBase)` | `.compute(symbol, timeframe, as_of, context)` | context: `candles` (§8.1 dicts `ts/H/L/C/V/availability_time_ms` — **missing availability ⇒ QX, never a local −1ms**) or `window`/`provider`, `econ_calendar` (red-day set; None ⇒ EV_TMP_008 + HIGH_IMPACT impossible), `rollover_windows`, `temporal_window_levels` (E02 optional), `profile`/`profile_inputs`, `e12_params`. `direction = 0` (Context, never signal/permission). | E12_Temporal_Context/4.0.0 |
| `run_engine` | `(candles, params=None, econ_calendar=None, rollover_windows=None, temporal_window_levels=None, profile=None, profile_inputs=None, events=None) -> dict` | payload: `temporal_state, temporal_profile, events (EV_TMP_001–009 journal), engine, contract_version, config_version, n_candles`. | 4.0.0 |
| `TemporalWindowEngineStream` (alias `TemporalContextEngine`) | `(behavior_window=180, min_samples=30, params=None, rollover_windows=None, n_bins=48)`; `.on_candle(candle, econ_calendar=None) -> state`; `.attach_profile(p)`; `.attach_levels(l)` | state = TemporalContextState_v4 (§5.2 required: `version, temporal_window, window_phase, day_type, tod_state{hour_utc,minute,weekday,tod_bin,utc_window_progress}, quality, as_of, snapshot_id` + `is_overlap, is_utc_activity_window, rollover_active, historical_behavior, is_gap, vol_ratio, reason, fate`). Fate: ACTIVE → SUPERSEDED (next candle) / INVALIDATED (Q0). Duplicate (ts, as_of) ⇒ identical cached state. | 4.0.0 |
| `compute_temporal_profile` | `(returns_by_tod, as_of, cond_events=None, open_returns_by_window=None, fwd_returns_by_window=None, window_groups=None, profiles_history=None, min_samples=30, n_bins=48, fourier_k=4, params=None) -> TemporalProfile_v4` | §5.3 keys `version, as_of, seasonal_status, seasonal_factors, seasonal_factors_smoothed, conditional_rates ("{Y}\|{window}\|{bin}\|{daytype}" → {p,n,ci,status}), momentum_betas, stability{mean_spearman,kruskal_p,kruskal_H,rhos}, quality, param_hash, snapshot_id`. Ladder: UNAVAILABLE⇒Q1 · T≥30⇒Q2 · +Kruskal p<0.05 +Spearman>0.6⇒Q3 · +replay +no-leak +Wilson widths<0.3⇒Q4. PIT: callers pass history ≤ t−1. | 4.0.0 |
| registry functions | `utc_activity_window_of(ts[, rollover_windows])`, `day_type(ts[, red_days])`, `tod_bin(h[, n])`, `window_progress(h, window)`, `is_core_window(h)`, `hour_float(ts)`, `ts_from_ms(ms)` | §3.5 canonical: W0[0,7) W1[7,12.5) W2[12.5,21) W3[21,24); overlap [12.5,16) DERIVED; cores W1[7,11) W2[12.5,16); phases W1 EARLY<8/LATE≥11.5, W2 EARLY<13/LATE≥20.5 else MID; DayType HIGH_IMPACT>FRIDAY>SAT_SUN>WEEKDAY; naive dt adopted as UTC, non-UTC tz ⇒ `NON_UTC_TIMESTAMP_QX`. | §3.5/§4.1 |
| stats | `fff_seasonal(rbt[, use_sqrt=False])` (use_sqrt=True ⇒ `FFF_ABS_ESTIMATOR_FORBIDDEN`), `fourier_smooth_factors`, `winsorize`, `conditional_rate`, `wilson_ci`, `intraday_momentum_beta`, `vol_ratio`, `range_z`, `y_vol`, `y_range`, `kruskal_wallis`, `spearman_rho`, `profile_stability`, `test_temporal_window_difference`, `chi2_sf`, `returns_by_tod_from_candles`, `seasonal_profile_available`, `deseasonalize` | in-tree (ISSUE-CP5-025); n<30 ⇒ rate null + Q1; VR/V=0 ⇒ null; thresholds strictly `>` 1.5. | §3.2–§3.6 |
| `E12_DEFAULTS` / `get_params` | 25 keys; unknown ⇒ `UNKNOWN_E12_PARAM_QX`; §6 ranges enforced; any §3.5 registry mutation ⇒ `CONFIGURATION_INVALID` (windows are NOT runtime-tunable) | `temporal_window_calendar_version = "v2024a"`. No YAML file (the frozen config map has no e12 entry — code defaults are the §6 surface). | 4.0.0 |
| `load_v3_temporal_payload` | `(payload) -> dict` | §8.7 read-only adapter ⇒ canonical v4 + Q1 (`V3_MIGRATED_READ_ONLY`); malformed ⇒ QX with a deterministic reason. | 4.0.0 |

### Cross-engine notes for CP-6
- E12 §1.5 optional deps: E02 `TemporalWindowLevels_v4` and E11 `RegimeState_v4` are `required:false` context — attach via `temporal_window_levels` / consume `regime_state` from the bus; absence never degrades E12 below its own ladder.
- E11 `regime_state` is the veto/context input CP-6's context chain consumes (NG1: never a standalone mandate); `H_norm` and the gate live on the wrapper result, not in the state.
- E10 `state.divergence` + `mom_series` feed E09 (already wired) and the CP-6 setup gates; E10 is directional — the only CP-5 engine whose events carry `direction ≠ 0`.
- Wave-Out boundaries CP-6 must respect: E11 next-regime forecast and E04↔E11 adaptive ATR raise `WaveOutError` — the CP-6 forecast engine owns prediction; do not route around the raise.

## DATA-CHANGES
none — no table/column/migration created or altered; all emissions insert through the frozen Ch.4 `evidence_event` DDL (proven: `tests/integration/test_cp5_engines.py::TestCP5EmissionsInsertIntoStore`, incl. duplicate-snapshot rejection). Fixture JSONs are test data under `tests/fixtures/`, not runtime stores.

## TESTS
| test file | ids covered | result |
|---|---|---|
| `tests/unit/test_e10_momentum.py` (63) | E10 §8.1 GF01–GF17 (re-derived) · §8.2 replay · §8.3 no-leak · §8.4 ablation · §8.5 Wilson · §8.6 redundancy · §8.7 serialization · T-DR-001 · binding | PASS |
| `tests/unit/test_e11_regime.py` (78) | E11 §8.1 GF_01–GF_18 (re-derived, hash-locked) · **T-E11-K9** · §3.1 norms · rule-tree priority · streaming/idempotency/PIT · params + e11_params_v4.yaml re-assertion (ADR-P2-008) · §8.2–8.7 · Wave-Out · live-gate GF_17 · T-DR-001 · binding | PASS |
| `tests/unit/test_e12_temporal.py` (165) | E12 §8.1 GF01–GF12 (re-derived, hash-locked) · **T-E12-Windows** (AI.10 L18932–33) · §8.2 replay-1000 · §8.3 leak · §8.5 Wilson calibration · §8.7 v3 adapter · **§8.8 UTC-boundary/DST stability** · FFF · in-tree stats · Q0–Q4 ladder · §6 params · §5.2 schema · E07 provider contract · binding | PASS |
| `tests/integration/test_cp5_engines.py` (16) | **E07↔E12 BOTH modes** (resolved: authoritative source/config_version/Q5-gate; degraded: E12_UNAVAILABLE_DEGRADED_QX + Q4 cap; raising provider fails closed; boundary-hour registry agreement; §8.8 through E07) · E11 gate default-OFF + Wave-Out · T-DR-001 shared-window ×3 engines ×2 surfaces · store-DDL emissions E10+E11+E12 | PASS |
| `./scripts/run_all_tests.sh` | full Phase-2 suite (CP-1…CP-5) | **1048 passed / 0 failed** |

## DEVIATIONS
ADR-P2-015 applied (from-zero: the superseded prior attempt was never read or referenced; every file written from the blueprint). ADR-P2-007 applied (all §8.1 expected values re-derived from formulas — E11 GF_01/GF_05 and E12 GF01/GF09/GF10 document divergences logged as ISSUE-CP5-015/016/018/021/022/023, never copied). ADR-P2-008 applied (params/e11_params_v4.yaml treated as §9.5-canonical and re-asserted against chapter §6 — zero divergences; runtime YAML wins; no new YAML added — E10/E12 defaults are code-literal per the frozen config map). ADR-P2-014 applied (fixture reconciliations canonical in the ISSUE entries above). ADR-P2-017 applied (E07↔E12 and E09↔E10 later-stage dependencies consumed as specified context contracts with their specified fail-closed degradation paths). No simplifications, no formula changes, no TODO/FIXME/pass/NotImplementedError in any Wave-In engine file.

## OPEN-ISSUES
[ISSUE-CP5-001]…[ISSUE-CP5-027] — all severity MINOR, status CLOSED, mirrored in full to `PHASE2_DECISION_LOG.md` §B/CP-5 (A/B/rule/interim/needs format). Four carry a CP-8 triage request: 003 (E10 reference_mode default RSI vs §6 "velocity"), 008 (E10 impulse_score normalization), 020 (canonical Toobit rollover configuration — currently empty ⇒ rollover never active), 022 (E12 gap multipliers 1.1/0.9 — 10% threshold seems extreme for crypto). None blocks CP-6.

## HOW-TO-RUN
```bash
cd /home/user/Upstage                      # repo root (sandbox path)
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.lock           # nine SBOM pins (runtime)
pip install pytest                         # dev-only (ADR-P2-002)
./scripts/run_all_tests.sh                 # full suite → 1048 passed
.venv/bin/python -m pytest tests/unit/test_e10_momentum.py tests/unit/test_e11_regime.py tests/unit/test_e12_temporal.py tests/integration/test_cp5_engines.py -q   # CP-5 only → 322 passed
```
Demo (E12 → E07 resolved mode):
```python
from apex.engines.e12_temporal import E12TemporalProvider
from apex.engines.e07_rtm import utc_activity_window_check
info = utc_activity_window_check(1768485600000,          # 2026-01-15T14:00Z
                                 temporal_provider=E12TemporalProvider())
assert info["degraded"] is False and info["is_overlap"] is True
assert info["source"] == "E12_Temporal_Context.Contract v4.0.0"
```

## REMAINING WORK LEDGER
none — stage fully closed. (The only queued action is environmental, not work: push `53007b7..HEAD` after the Owner reconnects the sandbox GitHub token — see STATUS ENV NOTE; all commits exist on `arena/01a096fc-upstage` locally.)

## §CP-5-INTEGRATION-NOTES
Merged 12-engine interface map (deduped from HANDOFF_CP2 §INTERFACES, HANDOFF_CP3 §INTERFACES, HANDOFF_CP4 §INTERFACES — pointers, not re-listings; this table is the single place CP-6+ looks up an engine's topic/schema/contract/params). All engines: frozen `EngineBase.compute(symbol, timeframe, as_of, context) -> List[EvidenceEvent]`, topic pattern `evidence.{engine_id}.{condition_state}`, 24-field frame, `snapshot_id = sha256(canonical_json(payload))`, DataBus-only coupling.

| engine | event topic | schema pointer | contract version | params keys |
|---|---|---|---|---|
| E01 Structure | `evidence.E01.<EV_STR_### state>` (000–020) | SWINGPOINT_REQUIRED / STRUCTURE_EVENT_REQUIRED (engine module) | v4.0.0 | `E01_DEFAULTS` (22 — list: HANDOFF_CP2) |
| E02 Liquidity | `evidence.E02.<EV_LIQ_###>` (000–013) | Level/Pool/SweepEvent dataclasses; E02.Output.v4 validators | 4.0.0 | `E02_DEFAULTS` (22 — HANDOFF_CP2) |
| E03 Volume | `evidence.E03.<EV_VOL_###>` (000–012) | ParticipationEvidence v4.0.0 required-field set | 4.0.0 | `E03_DEFAULTS` (17 — HANDOFF_CP2) |
| E04 Volatility | `evidence.E04.*` (regime/squeeze/expansion) | VolatilityEvidence + VolatilityState (engine §5) | 4.0.0 | `E04_DEFAULTS` (module literal — HANDOFF_CP3) |
| E05 FVG | `evidence.E05.*` FVG_ZONE@^4.0.0 | FVG zone schema (engine §5) | 4.0.0 | `E05_DEFAULTS` (module literal — HANDOFF_CP3) |
| E06 OrderBlock | `evidence.E06.*` | order-block evidence schema (engine §5) | 4.0.0 | `E06_DEFAULTS` (module literal — HANDOFF_CP3) |
| E07 RTM | `evidence.E07.<bundle>` | RTMBundle + kz_info keys (HANDOFF_CP4 §INTERFACES) | 4.0.0 | `E07_DEFAULTS` (37 — HANDOFF_CP4) |
| E08 Wyckoff | `evidence.E08.<EV_WYK_001…012>` | cycle_state + 5×8 phase matrix (engine §5) | 4.0.0 | `E08_DEFAULTS` (52 — HANDOFF_CP4) |
| E09 Trend | `evidence.E09.TREND_{SCALE}_{STATE}` | TrendScale (18 keys) + TrendStack (6 keys), §5.1/§5.2 | 4.0.0 | `E09_DEFAULTS` (module literal — HANDOFF_CP4) |
| E10 Momentum | `evidence.E10.<EV_MOM_### state>` | MomentumState_v4 §5.1 (incl. `param_hash`) | E10_Momentum/4.0.0 | `E10_DEFAULTS` (20, no YAML) |
| E11 Regime | `evidence.E11.<EV_RGM_### / EV_RGM_001_{STATE}>` | RegimeState §5.1 (REGIME_STATE_REQUIRED/ALLOWED, additionalProperties:false) | E11_Regime/4.0.0 | `params/e11_params_v4.yaml` (7, §9.5-canonical) merged into `E11_DEFAULTS` (30) |
| E12 Temporal | `evidence.E12.<EV_TMP_001_{WINDOW} / EV_TMP_###>` | TemporalContextState_v4 §5.2 (STATE_REQUIRED) + TemporalProfile_v4 §5.3 + §5.1 snapshot payload | E12_Temporal_Context/4.0.0 | `E12_DEFAULTS` (25, no YAML; calendar v2024a) |

Versioned inter-engine edges live now: E04→E03/E05/E07/E08/E09 (governed ATR) · E01→E09 (swings/BOS) · E03→E06 (ParticipationEvidence) · E10→E09 (`mom_series`) · **E12→E07 (`E12TemporalProvider.temporal_window(ts_ms)` — resolved mode; absent/raising ⇒ E07_LOCAL_NON_AUTHORITATIVE + `E12_UNAVAILABLE_DEGRADED_QX`)** · E02/E11→E12 (optional context, `required:false`). Wave-Out raises CP-6 must not route around: E11 `forecast_next_regime`, E04↔E11 adaptive ATR, E08 encyclopedia ch.2–4, E01 dynamic-k.
