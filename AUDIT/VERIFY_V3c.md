# SESSION V3c — Independent Verification (L-001…L-015: quality, math and numerical layer)

**Baseline:** `85b2c155d7b054a468379ddfd802eb239d0801f9` (verified with `git rev-parse HEAD`;
`git log -1 --oneline` = `85b2c15 Merge pull request #25 from sinamoosazadeh/arena/01a0d98b-upstage`).
All source line numbers are against this commit.

**Inputs:** full audit report `AUDIT/APEX_GEN5_AUDIT.md` @ `690e2d8899319a7c7a96456f92c3008878e59346`
(fetched to `/tmp/AUDIT.md`), index `AUDIT/APEX_GEN5_AUDIT_INDEX.md` @ same commit (`/tmp/INDEX.md`).
Session V3 (`AUDIT/VERIFY_V3.md` @ `arena/01a0e8ac-upstage`) verified K-001…K-012 and session V3b
(`AUDIT/VERIFY_V3b.md` @ `arena/01a0e9b1-upstage`) verified X-V3b-001 (= ISSUE-079, measured) plus
K-013…K-026; both were read first for method (real repository code, temporary/in-memory SQLite
with the repository's own DDL, explicit synthetic-vs-device boundary) and are cited, not redone.

**Read-only discipline:** no repository source, config, test or document file was modified;
no pull request, no `main`, no order, no exchange/Telegram endpoint, no secret, no `.env`,
no `data/`. The only files added are under `AUDIT/`. Probe databases are written to `/tmp`.

**Environment:** `python3 -m pip install --break-system-packages -q -r requirements.lock pytest`
(numpy 1.26.0, pytest 9.1.1), tests run as `python3 -m pytest -q -p no:cacheprovider <path>`.

**Synthetic boundary (applies to every row):** every reproduction below uses synthetic data
and, where a store is needed, a synthetic SQLite database built with the repository's own DDL
and its own write methods. Synthetic success is never proof about the owner's device database,
and synthetic failure proves the code path, not that it has already damaged a device record.

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---:|---:|---|---|---|
| L-001 | CONFIRMED | S2 | S2 | Yes — `apex/data_catalog/**` + frozen `engines/base.py` | — | B now (explicit lookback / non-frozen depth adapter); A by owner ruling (validity-vs-depth split) |
| L-002 | CONFIRMED | S2 | S2 | Yes — `apex/data_catalog/math` + `atomic/features.py` | L-001 (default depth hides crash as OK/0) | B now (refuse/reroute to E03); A by owner ruling (Wilder convention verbatim) |
| L-003 | CONFIRMED | S1 | S1 | Yes — `apex/data_catalog/math` + `atomic/molecular/features.py` | E03 `zscore_pit` is the conformant reference | B now (conformant adapter, never consume catalog z-features); A by owner ruling (baseline + σ-guard together) |
| L-004 | CONFIRMED | S1 | S1 | Yes — `apex/data_catalog/atomic/features.py` | L-003 (same window-as-baseline confusion) | B now (adapter currency check); A by owner ruling jointly with L-003-A |
| L-005 | CONFIRMED | S2 | S2 | Yes — `apex/data_catalog/math` + `atomic/features.py` | E10 `rsi_series`/streaming is the conformant reference | B now (E10 RSI via adapter); A by owner ruling (§3.3 edge verbatim) |
| L-006 | CONFIRMED | S2 | S2 | No — `apex/quality/vector.py` + `apex/setup/gates.py` are non-frozen | D-026 (same NaN-through-comparison theme at risk layer) | A — single path: API-boundary finite/range validation |
| L-007 | CONFIRMED | S2 | S2 | No — `apex/fabric/context.py` is non-frozen | — | A — single path: time-aware pairing (backward compatible) |
| L-008 | CONFIRMED | S2 | S2 | No for this helper; consistent triad fix touches frozen `_f41` | `_f41_volume_ratio` (frozen) + E03 `volume_ratio_pit` share the degraded reading | Owner ruling for the triad: A-with-cap or B (contract amendment); do not flip this branch alone |
| L-009 | CONFIRMED (worse than claimed: 4 silent-VALID positions) | S2 | S2 | No — `apex/quality/numerical.py` is non-frozen | `guarded_div` in the same file is the correct pattern | A — single path: pre-validate all inputs |
| L-010 | CONFIRMED | S2 | S2 | No — `apex/pattern/fibonacci.py` is non-frozen | N-010 (same single-linkage-vs-diameter theme in runtime E02) | Owner ruling quantifying independence + diameter, then A; rewrite the pinning test |
| L-011 | CONFIRMED | S2 | S2 | No — `apex/pattern/fibonacci.py` is non-frozen | L-010 (diameter fix must include non-finite refusal); L-006 (NaN-comparison theme) | A — single path: uniform isfinite gates on inputs + outputs, jointly with L-010 |
| L-012 | CONFIRMED | S1 | S1 | No — `quality/vector.py` + `setup/gates.py` + `risk/kernel.py` non-frozen | H-014 (label side); D-026 (adjacent risk-NaN theme); D59 (formula preserved, validation added) | A — single path: finite+domain pre-validation, D59 formula untouched |
| L-013 | PENDING | S2 | — | — | — | — |
| L-014 | CONFIRMED | S2 | S2 | No — `apex/research/proxies.py` is non-frozen | B08 registry row "feeding context/regime" is aspirational (no caller); EC-register discipline | A if owner approves formula (last-vs-window PIT composite); else B (demote to REGISTERED_OPEN) |
| L-015 | PENDING | S2 | — | — | — | — |

---
## L-001 — ATOM default window depth (lookback=1 for all 44 contracts)

#### Auditor claim (short quote)
> "All 44 ATOM contracts carry `lookback=1,warmup=0` while TR needs 2, ATR/RSI 15, SMA/VolumeZ 20 and return_k 21 bars; `get(...,lookback=1)` and `EngineBase.feature` fetch one bar despite available history." (Index: "ATOM does not declare the real warmup/lookback depth of the indicators.")

#### What I read (files, line ranges, functions, callers)
- `apex/data_catalog/catalog.py` (complete, 395 lines): `_make_atom_contract` (116–136) hardcodes `lookback=1, warmup=0` for every ATOM entry; `build_registry` (207–231) registers all 44 ATOM aliases through that single template; `Catalog.get` (291–361) resolves physical depth as `bars = max(lookback, contract.lookback + contract.warmup)` (~line 336), so a default call always fetches exactly 1 bar.
- `apex/data_catalog/atomic/features.py` (complete, 496 lines): `_f09_tr` needs 2 bars via `_guard(need_prev_close=True)` (52–66, 138–143); `_f10_atr_t`/`_f11_atr` need n+1=15 (146–185); `_f12_sma`/`_f13_ema`/`_f19_volume_z`/`_f34_range_z`/`_f35_slope` need n=20 (188–241, 321–327); `_f18_rsi` needs n+1=15 (228–233); `_f20_vol_ratio`/`_f41_volume_ratio` need n+1=21 (244–256, 389–417); `_f32_return_k` needs 21 (289–304); `_f36_hurst` needs 24 via math (330–335). All return `UNAVAILABLE/INSUFFICIENT_BARS_QX` below their minimum. `_f17_obv` needs only ≥1 bar (221–225) and therefore returns `OK/0` on a single bar (see L-002).
- `apex/engines/base.py` (complete, 236 lines): `EngineBase.feature(..., lookback=1)` (156–167) — the frozen engine read path defaults to depth 1.
- Callers (mandatory `grep -rn "\.feature(\|catalog\.get(" apex/ scripts/`): NO concrete engine and NO runtime/serve caller invokes `self.feature()` or `catalog.get()`; the only hit is `EngineBase.feature`'s own delegation. The catalog read path is currently unwired from the PAPER serve path (which uses `EngineContextProducer` windows plus native engine streams). Direct tests call `catalog.get`, some with explicit `lookback=15` (`tests/unit/test_catalog.py:336–338`).
- `tests/unit/test_catalog.py:107–120`: the only default-depth `UNAVAILABLE` assertions are F56 `market_profile` (ORGN tier, Wave-Out) and the F49 slot — unaffected by any ATOM depth change.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONPATH=/home/user/Upstage python3 AUDIT/probes_V3c/L-001.py`. Probe: `AUDIT/probes_V3c/L-001.py` (real `Catalog`, real registry, real ATOM computers, 40 synthetic CLOSED bars, in-memory provider). Raw output: `AUDIT/probes_V3c/L-001.out`. Result: all 44 ATOM contracts report `(lookback, warmup) = (1, 0)`; `EngineBase.feature` default `lookback=1`; default-depth reads of `TR_t`/`ATR`/`SMA`/`RSI`/`VolumeZ`/`return_k` all return `UNAVAILABLE/INSUFFICIENT_BARS_QX`, while the same `as_of` with `lookback=22` returns `OK` with values; `OBV` at default depth returns `OK/0E-8` (false zero — L-002).

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). Every factual element — uniform (1,0) contracts, per-formula minima, one-bar default fetch, `UNAVAILABLE`-at-default/`OK`-at-depth behavior — is reproduced in real repository code. S2 because the failure mode is fail-closed `UNAVAILABLE` (not a wrong value), the path has no runtime consumer today, and explicit-depth reads work; it is latent dead-on-arrival for any future default-depth consumer.

#### Root cause
The registry template conflates two different quantities: ATOM *validity/refresh semantics* ("computed per closed candle, validity 1 candle") and each formula's *physical input depth*. `Catalog.get` then uses the validity fields as the physical fetch depth (`bars = max(lookback, lookback+warmup)`), so the default call can never satisfy a multi-bar formula.

#### Direct impact
Any default-depth read of a multi-bar ATOM feature is permanently `UNAVAILABLE`, regardless of available history. No trading/accounting impact today (no runtime consumer); a future serve consumer using defaults would see every indicator feature as missing.

#### Secondary effects and interactions (upstream/downstream)
Upstream, the single `_make_atom_contract` template mirrors contract cadence language (`APEX_GEN5.md:13699`) into a physical depth with no per-formula override. Downstream: (a) direct-call tests that always pass an explicit lookback mask the defect; (b) the one non-fail-closed default read is `OBV → OK/0` (L-002); (c) no cache poisoning is possible — ATOM is never cached (`catalog.py` tier discipline); (d) no identity/hash impact — `CatalogResult` carries no hash and feeds no fingerprint today; (e) `AtomTierFailure` is not triggered (`UNAVAILABLE` is the AI.6 missing-data model, gates stay open).

#### Contract and decisions
`APEX_GEN5.md:13699` says "ATOM tier (features 01-44): computed per closed candle, 1-candle lookback, validity of 1 candle, no decay" — but the same contract's §2.2 formulas require multi-bar inputs (`SMA_20`, `ATR_14`, `return_k` k=1/5/20, L835–843) and §3.1 requires 20-bar reference windows (L3970–3978). The "1-candle lookback" line describes tier cadence/validity; read literally as physical input depth it contradicts the formulas. No `PHASE2_DECISION_LOG.md` ruling separates validity from depth (grep for "lookback" shows only unrelated items). Precedence: the formulas govern computation; the cadence line cannot shrink physical inputs — an owner ruling is needed to split "validity lookback" from "input depth".

#### Frozen status and non-frozen alternative
**Frozen:** `apex/data_catalog/catalog.py` and `apex/data_catalog/atomic/features.py` are under frozen `apex/data_catalog/**`; `apex/engines/base.py` is the frozen base contract. A non-frozen alternative EXISTS and needs no frozen change: (a) callers pass an explicit `lookback=N` (already supported by `Catalog.get`); (b) a non-frozen depth adapter (alias→required-bars table plus a wrapper over `catalog.get`) living outside the frozen tree resolves correct depths for any consumer.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — owner-ruled registry fix (frozen):** give each ATOM contract the true `lookback`/`warmup` of its formula; `get()` already takes the max, so default reads become correct. Side effects: default `get()` results change `UNAVAILABLE→OK` on deep history (intended); no existing test breaks (the only default-depth `UNAVAILABLE` assertions are F56/F49, ORGN/Wave-Out); no hashes/identities/caches invalidated (ATOM uncached, results unhashed); no DB migration or retraining (catalog unconsumed at runtime). Touches frozen files → owner ruling required.
**B — non-frozen depth adapter (no frozen change):** wrapper resolves per-alias depth and passes explicit `lookback`. Side effects: a second source of truth that must be manually synced if frozen computers ever change depth; otherwise zero blast radius.

#### My recommendation
B now for any consumer that needs correct reads (zero frozen risk); request an owner ruling for A — the validity-vs-depth split — before wiring catalog reads into the serve path, so the registry itself declares true depths.

#### Acceptance and regression tests
- Registry test: every ATOM alias whose computer requires N bars exposes declared depth ≥ N (probe table: TR 2, ATR/RSI 15, SMA/EMA/VolumeZ/RangeZ/Slope/VolRatio 20–21, return_k 21, Hurst 24).
- Catalog test on ≥40 synthetic bars: default-depth `get()` for the multi-bar features returns `OK` with values bit-equal to explicit-depth reads at the same `as_of`; on <N bars it returns exactly `UNAVAILABLE` (never a silent short-window value).
- Regression: `tests/unit/test_catalog.py` and `tests/unit/test_cp1_foundations.py` pass unchanged.

## L-002 — catalog-math OBV reads `.close` off a Decimal

#### Auditor claim (short quote)
> "`obv_series` puts `prev=obs.close` (Decimal) after the first candle but reads `prev.close` on the next pass: for ≥2 bars `AttributeError` escapes from `Catalog.get("OBV",lookback=2)`. With the one-bar default from L-001 the same API returns `OK/0` for any market instead of crashing; that is no sign of OBV health. E03 runtime has a separate computation; no direct PAPER effect is attributed."

#### What I read (files, line ranges, functions, callers)
- `apex/data_catalog/math/__init__.py` (complete, 305 lines): `obv_series` (128–141) — `prev = obs.close` stores a `Decimal` (line 140), then `prev.close` (line 136) dereferences it on every bar after the first. One-bar windows return `Decimal(0)` unconditionally (the loop body never executes the comparison).
- `apex/data_catalog/atomic/features.py:221–225` (`_f17_obv`): passes the window straight to `m.obv_series` with no depth guard beyond ≥1 bar, then quantizes — so 1 bar yields `OK/0E-8`.
- `apex/data_catalog/catalog.py:336–361`: `Catalog.get` invokes computers with NO `try/except` — the `AttributeError` propagates out of the public `catalog.get` API instead of becoming a status.
- `apex/engines/e03_volume/engine.py:160–177` (`obv_series_wilder`, Wilder rule with flat handling, seeded `obv=vols[0]`) with call sites at 521 and 619–623 — the independent E03 implementation; covered by `tests/unit/test_e03_volume.py:124–129` (`OBV_Wilder_Flat`, asserts the flat-rule 700, not the naive 3000).
- Callers (mandatory grep): catalog `obv_series` is called ONLY by `_f17_obv`; nothing else in `apex/`, `scripts/` or `tests/` imports it. No runtime path reaches `_f17_obv` (L-001: no `catalog.get` callers). No test covers catalog OBV (`grep OBV tests/unit/test_catalog.py tests/unit/test_cp1_foundations.py` → empty), so the bug is unguarded AND no test enshrines it.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONPATH=/home/user/Upstage python3 AUDIT/probes_V3c/L-002.py`. Probe: `AUDIT/probes_V3c/L-002.py` (real `obv_series`, real `Catalog.get("OBV")`, real E03 `obv_series_wilder`; synthetic bars). Raw output: `AUDIT/probes_V3c/L-002.out`. Result: 1-bar rising/falling/flat windows all return `0`; every 2-bar window raises `AttributeError: 'decimal.Decimal' object has no attribute 'close'`; `Catalog.get("OBV")` at default depth returns `OK/0E-8`; `Catalog.get("OBV", lookback=2)` raises the same `AttributeError` out of `catalog.get`; E03's function on identical closes returns `[10.0, 20.0]` / `[10.0, 0.0]` / `[10.0, 10.0]` (correct Wilder behavior).

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). The crash and the false `OK/0` are both reproduced in real code with the exact claimed mechanics. S2 (not S1) because the catalog OBV has no runtime consumer — E03 computes its own OBV — and the failure is loud (exception) at depth ≥2; the quiet `OK/0` at depth 1 is the more insidious half, but still latent. A fix that only repairs the loop without fixing the seed convention would still leave catalog OBV inconsistent with E03.

#### Root cause
Type confusion in the loop accumulator: `prev` is assigned the `Decimal` close but consumed as a `MarketObservation`. One-bar windows never touch `prev`, so the bug hides exactly at the L-001 default depth, where the function additionally returns a direction-blind zero seed as `OK`.

#### Direct impact
Catalog OBV is unusable: `OK`-with-false-zero at depth 1, uncaught exception at every depth ≥2. Any registry-based volume analysis, quality check, or acceptance test built on catalog `OBV` gets either a lie or a crash. No PAPER impact today (E03 path is independent).

#### Secondary effects and interactions (upstream/downstream)
Upstream, L-001's one-bar default is what converts this crash bug into a silent false `OK/0` on the default path. Downstream, the exception escapes `catalog.get` — a fail-OPEN crash from the "ONLY public read" API, violating the Ch.5 status contract (`OK/MISSING/STALE/UNAVAILABLE/INVALID`; exceptions are not in the vocabulary). Two OBV conventions now exist (catalog seed-0-if-it-worked vs E03 seed-`vols[0]` + Wilder flat rule), so even a repaired loop must pick the governed seed/edge convention or registry and engine OBV permanently disagree.

#### Contract and decisions
No `APEX_GEN5.md` clause gives catalog-math OBV a seed/edge formula distinct from E03's; E03's Wilder rule (flat contributes nothing, §3.3 per the engine docstring) and its fixture tests are the only governed OBV behavior in the checkout. No `PHASE2_DECISION_LOG.md` ruling covers catalog OBV. Precedence: E03's tested Wilder behavior is the reference; catalog OBV must be reconciled to it by owner ruling (it lives in a frozen file).

#### Frozen status and non-frozen alternative
**Frozen:** `apex/data_catalog/math/__init__.py` and `apex/data_catalog/atomic/features.py` are under frozen `apex/data_catalog/**`. A non-frozen alternative EXISTS for consumers: use E03's `obv_series_wilder` (non-frozen engine code, tested) via a non-frozen adapter instead of catalog `OBV`; and/or a non-frozen guard wrapper that refuses catalog `OBV` reads (`UNAVAILABLE/OBV_KNOWN_BROKEN`) until the frozen fix lands. There is NO non-frozen way to repair `Catalog.get("OBV")` itself.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — frozen loop + convention fix (owner ruling):** store a numeric `prev_close` (or keep `prev_obs` object) consistently; adopt the E03 seed (`vols[0]`) and Wilder flat rule so registry and engine agree; add a ≥2-bar minimum returning `UNAVAILABLE` below it (a 1-bar OBV is seed, not signal). Side effects: `Catalog.get("OBV")` changes from `OK/0`/crash to real values (intended); NO existing test breaks (nothing covers catalog OBV); no hashes/caches/DB/retraining impact (catalog unconsumed, ATOM uncached). Touches frozen files → owner ruling required.
**B — non-frozen containment (no frozen change):** adapter refuses or reroutes catalog `OBV` reads to E03's function. Side effects: catalog `OBV` stays broken for direct callers; E03's float path vs catalog's Decimal path differ in precision/quantization (8 digits) — document the seam.

#### My recommendation
B immediately (refuse-or-reroute adapter) so no future consumer silently eats `OK/0`; pursue A by owner ruling as the durable fix, with the E03 Wilder convention adopted verbatim to end the two-OBV split.

#### Acceptance and regression tests
- Rising/falling/flat 2-bar windows return the governed signed/zero increments (no exception); 1-bar returns `UNAVAILABLE` (seed is not a value); 20-bar series equals E03 `obv_series_wilder` on the same closes/volumes to the 8-digit quantization.
- `Catalog.get("OBV", lookback=2)` returns a status, never raises.
- Regression: `tests/unit/test_e03_volume.py` (OBV fixtures) unchanged; new test pins catalog OBV to the E03 convention.
## L-003 — z-score self-normalization (current bar in its own baseline) + F74 sweep gate

#### Auditor claim (short quote)
> "`zscore` takes mean/σ from 20 values INCLUDING the current candle; the E03 VolumeZ/RangeZ contract uses the 20 values BEFORE the candle. F74 repeats the same self-normalization in `_volume_z(prior+obs,20)`. In the sample (prior vols 1..20, sweep-bar vol 23) contract Z≈2.1678 but computed Z≈1.9177; with low=89 under extreme=90 and close=95, F74 returned `OK/NO_SWEEP_IN_BLOCK` instead of a valid sweep."

#### What I read (files, line ranges, functions, callers)
- `apex/data_catalog/math/__init__.py:167–178` (`zscore`): `recent = values[-n:]`, `last = values[-1]` — the scored value is a member of its own baseline by construction.
- `apex/data_catalog/atomic/features.py:236–241` (`_f19_volume_z`), `:321–327` (`_f34_range_z`): pass the full window including the current bar; `:257–263` (`_f21_oi_z`) passes the None-filtered list likewise. Mandatory grep shows these plus `molecular/features.py:113` are the ONLY `m.zscore` callers in `apex/`.
- `apex/data_catalog/molecular/features.py` (complete, 123 lines): `_volume_z(prior, obs)` (108–115) builds `vols = prior + [obs]` (21 items) then `m.zscore(vols, 20)` — the last 20 = 19 prior + current; `compute_sweep` (64–84) requires `vol_z >= VOLUMEZ_GATE = 2` at the penetration candle before testing penetration geometry.
- `apex/engines/e03_volume/engine.py:119–124` (`zscore_pit(current, history, n)` — current scored against a SEPARATE history) with call sites `vz` (572), `rz` (574), `oi_z` (598), `obv_z` (623); the current bar is appended to `history_vols/ranges/closes/obv` only AFTER computation (732–735; the warmup path returns early without scoring). E03 baselines are therefore strictly prior-only — the contract-conformant shape.
- Tests: no test pins F74 sweep values (`tests/unit/test_catalog.py:194–201` only counts `sweep` computer invocations for cache behavior); nothing asserts `_f19/_f34` values against a prior-only oracle.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONPATH=/home/user/Upstage python3 AUDIT/probes_V3c/L-003.py`. Probe: `AUDIT/probes_V3c/L-003.py` (real `cmath.zscore`, real `compute_sweep`/`_volume_z`, real E03 `zscore_pit`; synthetic bars). Raw output: `AUDIT/probes_V3c/L-003.out`. Result: catalog `zscore = 1.91765986…` vs prior-only contract value `2.16777492…` (auditor's 1.9177/2.1678 to 4dp); E03 `zscore_pit = 2.1677749238103` (matches contract); F74 `_volume_z = 1.9177 < 2` so `compute_sweep → OK/NO_SWEEP_IN_BLOCK` on geometry that the contract Z (2.1678 ≥ 2) would admit as a sweep.

#### Verdict and reasoning
**CONFIRMED — independent severity S1** (auditor S1 retained). The self-normalization, the exact numbers, the missed sweep, and the E03/catalog split are all reproduced in real code. S1 because a threshold gate (`VolumeZ ≥ 2`) is systematically biased downward near the boundary — outliers are shrunk toward the baseline that contains them — and the same wrong primitive feeds `VolumeZ`, `RangeZ`, `OI_z` and F74. Severity stays S1 rather than S0 only because the catalog path has no runtime consumer today (E03 computes its own conformant scores); the day catalog features feed serve, this corrupts sweep/outlier detection silently.

#### Root cause
`zscore(values, n)` conflates "the window the caller hands over" with "the baseline": it scores `values[-1]` against statistics that include `values[-1]`. Every caller passes a window whose last element is the bar being scored, and F74 additionally concatenates `prior + [obs]` before calling it — so the current bar dilutes its own deviation in all four consumers.

#### Direct impact
Near-threshold sweeps and outliers are missed or under-scored: any `VolumeZ/RangeZ/OI_z` within the dilution band below its gate reads low, and F74 drops valid penetration candles (`NO_SWEEP_IN_BLOCK` with `q=1.0`, i.e. confidently wrong).

#### Secondary effects and interactions (upstream/downstream)
Upstream, the defect is in the shared primitive, so one fix covers all four consumers. Downstream, catalog `VolumeZ/RangeZ` disagree with E03's `vz/rz` on identical inputs (proven: 1.9177 vs 2.1678), so any future calibration, backtest statistics, or setup/playbook logic built on catalog features would silently diverge from E03-native behavior. Beyond-audit note (same function, same clause, same fix vehicle — folded here, not a separate X-ID): §3.1 also specifies `σ<ε → clamp σ=ε (1e-8)`, but `zscore` returns `Decimal(0)` when `σ<ε` — a second, unclaimed deviation in the same formula that the owner ruling should settle together with the baseline question.

#### Contract and decisions
`APEX_GEN5.md:3970–3978` (§3.1) is explicit: "the reference SMA and standard deviation are computed only over the window preceding the current bar, never including it", with `VZ_t^PIT = (V_t − μ_{t−1,n})/max(σ_{t−1,n}, ε)` over `i=t−n..t−1`; `L9152–9158` repeats `VolumeZ = (V_t − SMA_{t−1}(V,20))/max(SD_{t−1}(V,20), ε)`. The code violates the "never including it" sentence directly. No `PHASE2_DECISION_LOG.md` ruling overrides §3.1 (later decisions override contract prose; none touches z-score baselines). Precedence: §3.1 governs; E03's implementation is the conformant reference.

#### Frozen status and non-frozen alternative
**Frozen:** `apex/data_catalog/math/__init__.py`, `atomic/features.py`, `molecular/features.py` are all under frozen `apex/data_catalog/**`. A non-frozen alternative EXISTS for consumers: compute z-scores outside the frozen tree with the §3.1 formula (prior-only baseline, σ-clamp) in a producer/adapter layer — E03's `zscore_pit` (non-frozen engine code) is exactly such a reference and can be reused or mirrored. There is NO non-frozen way to repair `Catalog.get("VolumeZ"/"RangeZ"/"OI_z"/"sweep")` themselves.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — frozen primitive + caller fix (owner ruling):** change `zscore` to score `values[-1]` against `values[-n-1:-1]` (or take an explicit `(current, history)` pair like `zscore_pit`), fix `_volume_z` to pass prior-only history, and settle the σ-guard (clamp vs 0) in the same ruling. Side effects: `VolumeZ/RangeZ/OI_z/sweep` VALUES CHANGE on every bar (intended — they were wrong); NO existing test breaks (no value-pinning tests for these features); no hashes/caches/DB/retraining impact (catalog unconsumed, ATOM/MOLE values unhashed at rest... MOLE is cached 5 candles — the cache is in-memory per-process `TierCache`, invalidated by `code_revision`, so no durable invalidation needed). Touches frozen files → owner ruling required.
**B — non-frozen adapter (no frozen change):** §3.1-conformant z-score/sweep in the producer layer; refuse or relabel catalog z-features until A lands. Side effects: catalog reads stay wrong for direct callers; adapter must mirror the σ-guard ruling once made.

#### My recommendation
B now (conformant adapter; never consume catalog z-features/sweep directly); pursue A by owner ruling, deciding baseline AND σ-guard together, before any serve wiring.

#### Acceptance and regression tests
- `prior=1..20/current=23 → Z>2` and the auditor's sweep geometry yields a valid sweep with the governed θ; boundary tests at exactly Z=2, trend windows, σ≈0 windows, and a no-future-leak test (shifting the current bar must not change any earlier bar's score).
- Parity test: catalog `VolumeZ/RangeZ` equal E03 `vz/rz` on identical synthetic windows to quantization.
- Regression: `tests/unit/test_catalog.py` (incl. the sweep cache-count test) and `tests/unit/test_e03_volume.py` pass.

## L-004 — OI_z with missing current OI returns history as OK

#### Auditor claim (short quote)
> "`_f21_oi_z` drops every `None` OI from the window and checks only the survivor count; with 20 valid-OI bars and a current bar lacking OI, `lookback=20` gives MISSING but `lookback=21` returns history as `OK/1.6475` for the SAME as_of. The existing test covers only a single OI-less bar."

#### What I read (files, line ranges, functions, callers)
- `apex/data_catalog/atomic/features.py:257–263` (`_f21_oi_z`): `ois = [o.oi for o in window if o.oi is not None]`; `len(ois) < n → MISSING/OI_MISSING_QX`, else `m.zscore(ois, n)` → `OK` with `q=1.0`. The current bar's OI is never inspected — a `None` simply vanishes from the list.
- `apex/data_catalog/catalog.py:336–361`: `bars = max(lookback, 1)` supplies the window; the same `as_of` with different `lookback` yields different windows, hence different verdicts for one missing input.
- `apex/data_catalog/contracts.py:243–257` (`oi_state_for`): `oi=None → (MISSING, 0.0)`; "Missing OI is NEVER 0 (T-DC-004)". The catalog returns `OK/q=1.0` — full quality — for a feature whose current input is exactly this MISSING state.
- `tests/unit/test_catalog.py:286–294` (T-OM-002): single bar with `oi=None → MISSING` — the only OI_z test; it cannot catch survivor-count logic because one bar never reaches n=20.
- Boundary contrast: `apex/engines/e03_volume/engine.py:577–600` — `oi=None → oi_state="MISSING"`, `oi_z=None` (no value fabricated); the native path treats missing current OI as unavailable.
- Callers: `_f21_oi_z` is reachable only via `Catalog.get("OI_z")`, which has no runtime caller (L-001).

#### Reproduction (command, probe file, actual result)
Command: `PYTHONPATH=/home/user/Upstage python3 AUDIT/probes_V3c/L-004.py`. Probe: `AUDIT/probes_V3c/L-004.py` (real `Catalog.get("OI_z")`; 21 synthetic bars, bars 0–19 OI-valid, bar 20 OI-None). Raw output: `AUDIT/probes_V3c/L-004.out`. Result: same `as_of`, `lookback=20 → MISSING/OI_MISSING_QX/q=0.0`, `lookback=21 → OK/1.6475/q=1.0`; the control (current OI valid) returns the IDENTICAL `OK/1.6475/q=1.0` — the missing current OI is completely invisible in the output.

#### Verdict and reasoning
**CONFIRMED — independent severity S1** (auditor S1 retained). The depth-dependent verdict flip and the auditor's `OK/1.6475` are reproduced exactly, and the control proves indistinguishability from a genuinely-OK read. S1 because a missing current input produces a full-quality `OK` value — the worst failure mode (confident fabrication from stale history) — even though the path is latent today. The "never coerce OI to 0" comment in the code shows the author cared about OI-missing semantics but enforced it only on the count, not on currency.

#### Root cause
Currency is never validated: the function filters `None` over the whole window and counts survivors, so "20 valid OIs somewhere in the window" passes — including the case where the 20 are all history and the bar being scored has no OI. Depth then decides the verdict instead of the input state.

#### Direct impact
A consumer reading `OI_z` at sufficient depth cannot distinguish "current OI missing" from "current OI present" — same status, same value shape, same `q=1.0`. Any OI-gated logic (regime, risk, quality) built on this read would act on a stale-history value as if it were current.

#### Secondary effects and interactions (upstream/downstream)
Upstream, this is the same "window-as-baseline" confusion as L-003 plus a missing currency check. Downstream, the verdict flip by `lookback` (MISSING at 20, OK at 21) makes the read non-deterministic across callers with different depths — two consumers of the same `as_of` legitimately disagree. No cache/identity impact (ATOM uncached, results unhashed). E03's native `oi_z=None`-on-missing is the correct reference behavior and disagrees with the catalog read on identical inputs.

#### Contract and decisions
T-DC-004 (`contracts.py` + §AI.6): "Missing OI is NEVER 0" with `Q_oi=0/MISSING` as a label. Returning `OK/q=1.0` for a missing-current-OI feature contradicts the missing-OI-must-be-visible principle; the code's own `OI_MISSING_QX` reason shows the intended vocabulary. No `PHASE2_DECISION_LOG.md` ruling covers `OI_z` currency. Precedence: T-DC-004 + E03's `oi_z=None` behavior govern; the survivor-count logic has no contract support.

#### Frozen status and non-frozen alternative
**Frozen:** `apex/data_catalog/atomic/features.py` is under frozen `apex/data_catalog/**`. A non-frozen alternative EXISTS for consumers: validate `window[-1].oi is not None` (and window contiguity) in a non-frozen adapter BEFORE consuming `OI_z`, refusing currency-violating reads regardless of the catalog verdict. There is NO non-frozen way to repair `Catalog.get("OI_z")` itself.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — frozen currency fix (owner ruling):** require `window[-1].oi is not None` (MISSING otherwise) and compute the z-score over the governed contiguous window (prior-only per L-003-A). Side effects: `OI_z` flips `OK→MISSING` exactly on missing-current reads (intended); NO existing test breaks (T-OM-002's single-bar case stays MISSING); no hashes/caches/DB/retraining impact. Touches frozen files → owner ruling required.
**B — non-frozen adapter guard (no frozen change):** currency-check wrapper; refuse stale reads. Side effects: direct catalog reads stay wrong; one more seam to keep aligned with the frozen reason vocabulary.

#### My recommendation
B now (adapter currency check on every `OI_z` consumption); pursue A by owner ruling together with L-003-A (the z-score baseline fix), since both touch `_f21_oi_z`.

#### Acceptance and regression tests
- The probe's 21-bar case (current OI None) returns `MISSING/Q0` at EVERY lookback; current-valid + history-valid returns `OK`; current-valid + short history returns `MISSING` (not a short-window value).
- Contiguity: a `None` OI strictly inside history is either refused or explicitly degraded per the owner ruling — never silently dropped.
- Regression: T-OM-002 (`tests/unit/test_catalog.py:286–294`) still passes; add the two-depth test to `test_catalog.py`.
## L-005 — catalog RSI returns 100 on a flat market (contract/E10 say 50)

#### Auditor claim (short quote)
> "In L00 RSI the `avg_loss==0` branch returns 100 indiscriminately, even when `avg_gain==0`; for 15 flat closes catalog-math=100 but E10/explicit §3.3 contract=50. Changing depth past L-001 reveals the difference."

#### What I read (files, line ranges, functions, callers)
- `apex/data_catalog/math/__init__.py:144–164` (`rsi_wilder`): Wilder SMA-seed + RMA recursion, then `if avg_loss == 0: return Decimal(100)` — no flat check, exact-`==0` (not `<ε`). The docstring itself documents the deviation: "flat series → 100".
- `apex/data_catalog/atomic/features.py:228–233` (`_f18_rsi`): needs n+1=15 bars, passes closes straight through — so the edge is reachable only past the L-001 default depth (verified: default `UNAVAILABLE`, depth-15 `OK/100.0000`).
- `apex/engines/e10_momentum/engine.py:424–458` (`rsi_series`, RMA method): `AL<ε∧AG<ε → 50.0; AL<ε → 100.0`; the streaming path `:831–845` implements the identical edge. `tests/unit/test_e10_momentum.py:275–283` (GF16) pins constant-series RSI to 50.0 ("constant series ⇒ RSI edge AG=AL=0 ⇒ 50 (§3.3)").
- Callers: catalog `rsi_wilder` is called ONLY by `_f18_rsi`; `_f18_rsi` only via `Catalog.get("RSI")`, which has no runtime caller (L-001). E10 never touches catalog math.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONPATH=/home/user/Upstage python3 AUDIT/probes_V3c/L-005.py`. Probe: `AUDIT/probes_V3c/L-005.py` (real `rsi_wilder`, real E10 `rsi_series`, real `Catalog.get("RSI")`; synthetic closes). Raw output: `AUDIT/probes_V3c/L-005.out`. Result: 15 flat closes → catalog `100`, E10 `50.0`; pure-up → `100`/`100.0` (agree); pure-down → `0`/`0.0` (agree); flat-market `Catalog.get("RSI")` default → `UNAVAILABLE`, `lookback=15 → OK/100.0000`.

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). The divergence is isolated to exactly the flat edge (up/down agree), reproduced with both real functions plus the catalog path. S2 because catalog RSI is latent (E10 computes its own conformant RSI) and the failure is a wrong-but-bounded value (100 vs 50), not a crash or leak; it would become S1 the day catalog RSI feeds momentum/calibration logic, since flat-neutral would read as overbought.

#### Root cause
Missing distinguished flat branch: `avg_loss == 0` conflates "pure gains" (→100) with "no movement at all" (→50), and uses exact equality instead of the contract's `<ε` comparison.

#### Direct impact
Any flat/near-flat market reads RSI=100 (maximum overbought) instead of 50 (neutral) on the catalog path. Calibration, display, or signal logic built on catalog RSI would misclassify dead markets as extreme momentum.

#### Secondary effects and interactions (upstream/downstream)
Upstream, L-001 hides the bug at default depth (the probe shows `UNAVAILABLE` there) — it surfaces only when a caller passes sufficient depth, i.e. exactly when the feature starts being used. Downstream, catalog RSI and E10 RSI permanently disagree on flat windows (100 vs 50), so cross-checks between registry features and engine indicators would flag false mismatches. No identity/cache/ledger impact (ATOM uncached, results unhashed, path unconsumed).

#### Contract and decisions
`APEX_GEN5.md:10459–10467` (§3.3): "**Edge:** if `AL_t < ε` and `AG_t < ε`: RSI=50 (flat). If `AL_t < ε` and `AG_t>0`: RSI=100." The code implements only the second half and with `==0`. E10 (both batch and streaming paths) plus the GF16 fixture test implement the full edge — the conformant reference. No `PHASE2_DECISION_LOG.md` ruling touches RSI edges. Precedence: §3.3 governs; the frozen docstring "flat series → 100" contradicts the contract and cannot stand as an interpretation.

#### Frozen status and non-frozen alternative
**Frozen:** `apex/data_catalog/math/__init__.py` and `atomic/features.py` are under frozen `apex/data_catalog/**`. A non-frozen alternative EXISTS for consumers: use E10's `rsi_series`/streaming RSI (non-frozen, tested, §3.3-conformant) via a non-frozen adapter instead of catalog `RSI`. There is NO non-frozen way to repair `Catalog.get("RSI")` itself.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — frozen edge fix (owner ruling):** `avg_gain<ε ∧ avg_loss<ε → 50; avg_loss<ε (gain positive) → 100`, matching §3.3/E10 verbatim. Side effects: flat-window catalog RSI changes 100→50 (intended); NO existing test breaks (nothing pins catalog RSI values; E10's GF16 already expects 50); no hashes/caches/DB/retraining impact. Touches frozen files → owner ruling required.
**B — non-frozen adapter (no frozen change):** route RSI consumption through E10's function. Side effects: catalog `RSI` stays wrong for direct callers; float-vs-Decimal precision seam (4-digit quantization) to document.

#### My recommendation
B now (never consume catalog RSI directly); pursue A by owner ruling — a two-line edge fix adopting the §3.3 text verbatim.

#### Acceptance and regression tests
- 15+ flat bars → 50; pure-up → 100; pure-down → 0; near-ε windows (gains/losses straddling ε) compared against E10 `rsi_series` bar-for-bar.
- Parity test: catalog RSI equals E10 RSI on identical synthetic windows to the 4-digit quantization.
- Regression: `tests/unit/test_e10_momentum.py` (GF01/GF16) unchanged.

## L-006 — NaN window quality stays VALID/Q1; non-finite gate measured values pass

#### Auditor claim (short quote)
> "`calc_window_quality([(0.9,0.0),(NaN,1.0)])` returned `(nan,'VALID','Q1')`: the `min_q < q_thr` comparison is not fail-closed for NaN and gate 2 passes on `state=='VALID'` alone. §15 extension: `run_all` with `final_score/q_forecast=+inf` and `conflict_penalty/redundancy_penalty/h_norm=-inf` gave `all_pass=True` with gates 1/3/4/7/12 passing; gate 11 hashed a separate finite payload and never sees the outside measured values. The PAPER producer has separate finite guards; bypass of that producer is not proven."

#### What I read (files, line ranges, functions, callers)
- `apex/quality/vector.py:163–187` (`calc_window_quality`): `min_q = min(q…)` then `if min_q < q_thr` — for NaN the `<` is False, so the minimum-veto never fires; the weighted sum is NaN, returned as `(nan, 'VALID', 'Q1')`.
- `apex/setup/gates.py:185–207` (`gate2_window_quality`): `passed = state == "VALID"` — consumes the verdict without inspecting finiteness of `value`.
- `apex/setup/gates.py` score gates: `gate1` (178–182, `final_score >= thr` — +inf passes), `gate3` (210–216, `penalty <= 0.5` — −inf passes), `gate4` (218–222, `<= 0.3` — −inf passes), `gate7` (250–256, `h_norm <= thr` — −inf passes), `gate12` (350–359, `>= thr` with only a NaN/None check — +inf passes); `run_all` (447–476) threads `context[…]` measured values straight into each gate.
- `gate11_snapshot_lineage` (303–341): hashes ONLY its own `payload` argument; non-finite payload → `GATE11_SNAPSHOT_UNHASHABLE`, but measured values of sibling gates are outside its input — it cannot see them by construction.
- Native-producer guards (boundary): `apex/ops/engine_context.py:317–340` (`measured_number` finite+range guard; `window_quality_projection` applies it to every `(q, age)` pair before `calc_window_quality`); `validate_produced_context` (3901–3960) finite-guards `data_trust/q_raw/h_norm/s_i/q_i/x/risk` keys and re-runs `window_quality_projection` on `window_qualities` (3942–3944); `canonical_json` forbids NaN/Inf (`apex/identity/canonical_json.py`, `test_nan_inf_forbidden`).
- Callers: `calc_window_quality` ← `window_quality_projection` (guarded) + `gate2` (unguarded); `gate2` ← `run_all` ← family `evaluate` (`family_sf_fvg_sweep_rev.py:549`, `window_qualities or [(1.0,0.0)]*len(bars)`) ← `plan_bridge.py:803` (`_required(context, "window_qualities")`) ← producer `q["window_qualities"]` (finite pairs, `engine_context.py:340,2017`). The native chain is finite at every hop; the hole needs a non-producer caller.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONPATH=/home/user/Upstage python3 AUDIT/probes_V3c/L-006.py`. Probe: `AUDIT/probes_V3c/L-006.py` (real `calc_window_quality`, `gate2`, `run_all`, `window_quality_projection`, `canonical_json`; synthetic inputs). Raw output: `AUDIT/probes_V3c/L-006.out`. Result: `calc_window_quality([(0.9,0),(nan,1)]) → (nan,'VALID','Q1')`; `gate2 → passed=True, measured=nan`; `run_all` with the auditor's inf pattern → `all_pass=True, action=ELIGIBLE`, gates 1/3/4/7/12 passed with inf measured, gate 11 passed on the separate finite payload; `window_quality_projection` refused NaN and +inf with `BridgeError QUALITY_PROVENANCE_UNAVAILABLE`; `canonical_json(+inf)` raised `CanonicalJsonError`.

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). Both halves (§7 NaN-window, §15 non-finite measured) reproduce exactly, including gate 11's blindness-by-construction and both boundary guards. S2 because exploitation requires a non-producer caller: the entire native producer→family→gate→risk chain is finite-guarded twice over (`measured_number` at projection + `validate_produced_context`), and no such caller exists in the checkout — so this is a fail-open API surface, not an active bypass. It would escalate to S1 if any new caller (backfill, replay, tooling, future serve path) feeds unguarded numbers into gates.

#### Root cause
Two missing validations at the API boundary: (a) `calc_window_quality` never checks finiteness of `Q_i`/`age_i` before the minimum-veto comparison, and NaN poisons comparisons silently (`nan < thr` is False); (b) the score gates compare raw measured floats against thresholds with no finite/range pre-check, so ±inf lands on the passing side of one-sided comparisons.

#### Direct impact
Any direct API caller can obtain `VALID/Q1` window quality from NaN-contaminated inputs and `ALL_GATES_PASS/ELIGIBLE` from impossible measured values (`final_score=+inf`, negative-infinite penalties). The outputs are verdict-shaped lies: `measured=nan/inf` sitting next to `passed=True`.

#### Secondary effects and interactions (upstream/downstream)
Upstream, `min()` itself is NaN-fragile (`min(0.9, nan)` returns 0.9 or nan depending on order — CPython returns the first-seen on `<` chains... in fact `min` uses `<` pairwise, so NaN position changes the result), adding order-dependence on top of the fail-open. Downstream, a contaminated gate verdict would flow into setup eligibility and (via `failed_setup_gate`) risk veto 1 — the exact path the producer guards exist to protect. Cross-ref D-026 (risk-kernel NaN handling): same NaN-through-comparison theme one layer down; the producer guards mitigate both for the native path only. No DW impact on device data (read-only probe, synthetic inputs).

#### Contract and decisions
§2.1 (via `vector.py` module contract + `APEX_GEN5.md` quality chapter): "NaN/Inf never return silently — callers set Q_formula_valid=0"; Ch.10 §10.1 gate table lists blocking conditions that presuppose real measurements. No clause permits `VALID` on NaN or passing on ±inf. No `PHASE2_DECISION_LOG.md` ruling authorizes non-finite measured values. Precedence: the fail-closed quality contract governs; the guards belong at the API boundary, not only in the producer.

#### Frozen status and non-frozen alternative
**NOT frozen:** `apex/quality/vector.py` and `apex/setup/gates.py` are outside the frozen set (`engines/**`, `data_catalog/**`, `research/bootstrap.py`, `research/backtest.py`, six YAMLs, `requirements.lock`). No frozen change is needed; the producer guards in non-frozen `engine_context.py` already demonstrate the pattern.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — API-boundary finite/range validation (single path, non-frozen):** in `calc_window_quality`, reject non-finite `Q_i`/`age_i` (and non-finite `weighted_sum`/`exp_sum`) with a named `INVALID_NONFINITE_QX` before the veto comparison; in gates 1/3/4/7/12, finite-check (and, where the domain is bounded, range-check) `measured` before comparing, failing closed with named reasons. Side effects: direct callers passing NaN/Inf now get refusals instead of passes (intended); EXISTING TESTS — `tests/unit/test_quality.py` window tests use finite inputs (unaffected); `tests/unit/test_setup_gates.py` uses finite ±1-unit boundary values plus two NaN-fail-closed pins (`gate12(NaN)→fail` at :170, `gate11(NaN payload)→fail` at :228) that A preserves — no test asserts an inf-pass, so none should break (re-run to confirm); the native producer path is behavior-identical (its inputs are already finite). No hashes/identities/caches/DB/retraining impact. No frozen file touched.
No alternative path is needed — A is small, non-frozen, and matches the existing producer-guard precedent.

#### My recommendation
Implement A (both the `calc_window_quality` finite check and the five gate measured-checks) with named reasons; keep the producer guards as defense-in-depth.

#### Acceptance and regression tests
- NaN/±Inf in any `(Q_i, age_i)` position → named invalid + gate 2 fail; finite valid inputs keep the exact previous weighted values (bit-equality test against current outputs).
- NaN/±Inf in `final_score/conflict_penalty/redundancy_penalty/h_norm/q_forecast` → each gate fails with a named reason independent of the payload; finite boundary values (±1 unit) keep previous verdicts.
- Regression: `tests/unit/test_quality.py`, `tests/unit/test_setup_gates.py`, `tests/unit/test_cp146.py`, `tests/unit/test_engine_context_store_sources.py` all pass.
## L-007 — redundancy_rho pairs series by position after independent NaN-drops (wrong time join)

#### Auditor claim (short quote)
> "`redundancy_rho` drops each series' NaNs INDEPENDENTLY and zips the tails. On 50 truly anti-correlated points with NaN at two different times it gave `rho=+1.0,points=47`; on the time-aligned valid pairs `rho=−1.0`. In the current producer history all components are numeric and complete; this NaN occurrence in PAPER is not established."

#### What I read (files, line ranges, functions, callers)
- `apex/fabric/context.py:511–532` (`redundancy_rho`): `a = [v for v in list(s_a)[-n:] if v == v]`, same for `b`, then `k = min(len)`, tail-truncate, positional `zip`. No timestamps are accepted, so re-alignment after the drops is impossible by construction. Defaults: `n=48` (`redundancy_window_n`), `min_points=20`.
- `apex/ops/engine_context.py:1888–1899`: producer builds `series[name] = [h["s_i"][name] …]` from stored `COMPONENTS` facts and calls `redundancy_rho` pairwise; the stored rows are written at :2009–2012 as `{k: components["s_i"].get(k, 0.) for k in COMPONENT_ENGINE}` — complete 12-key dicts of `float(any(…))` ∈ {0.0, 1.0} (`component_projection`, :358–379), persisted via `append_context_fact` → `canonical_json`, which REJECTS NaN/Inf. Additionally `validate_produced_context` (:3931–3935) requires native `s_i ∈ {0., 1.}` finite. NaN therefore cannot enter producer history through the native write path.
- `apex/setup/family_sf_fvg_sweep_rev.py:508–545`: the family path calls the same function over caller-supplied `component_series` (or skips when absent); `rho` feeds `apply_redundancy` (victim halving) and the redundancy penalty.
- `redundancy_rho` callers (mandatory grep): only the two above. No test feeds NaN-bearing series to `redundancy_rho` (checked `tests/unit/test_fabric_context.py` redundancy cases — finite inputs).

#### Reproduction (command, probe file, actual result)
Command: `PYTHONPATH=/home/user/Upstage python3 AUDIT/probes_V3c/L-007.py`. Probe: `AUDIT/probes_V3c/L-007.py` (real `redundancy_rho` with default n=48; `a=t%2`, `b=1−t%2`, t=0..49, NaN in `a` at t=2, NaN in `b` at t=49). Raw output: `AUDIT/probes_V3c/L-007.out`. Result: `rho=+1.0, points=47, skipped=False` — the auditor's numbers exactly; the pairwise-complete time-aligned reference gives `rho=−1.0` on the common valid times; the no-NaN control gives `rho=−1.0, points=48`; `canonical_json` on a NaN `s_i` raises `CanonicalJsonError` (boundary).

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). The sign flip (+1.0 vs −1.0) and the point count (47) reproduce exactly with the real function, and the mechanism is precisely the claimed independent-drop-plus-zip. S2 because the trigger (NaN inside a stored/input `s_i` series) is unreachable through today's native producer path — complete 0/1 histories sealed by `canonical_json` — so this is a latent API-level time-join defect, not an active mis-penalty. It would matter the day any caller supplies gappy series (backfill gaps, partial histories, family-level direct calls).

#### Root cause
The function signature carries values without times, then filters each side independently: two drops at different positions shift the middle segment by one slot, and the positional zip pairs values from different instants. With phase-sensitive series (e.g. alternating 0/1), a one-slot shift converts perfect anti-correlation into perfect correlation.

#### Direct impact
On gappy inputs, ρ's sign, magnitude, and sample count can all be wrong (`+1.0/47` for data that is `−1.0` on every commonly-valid instant), and the `skipped=False/OK` reason asserts a healthy measurement.

#### Secondary effects and interactions (upstream/downstream)
Upstream, `n=48` windowing happens BEFORE filtering, so `points` conflates window truncation with NaN drops — the count is uninterpretable on gappy data. Downstream, a flipped ρ crosses the `|ρ|>0.85` threshold and triggers `apply_redundancy` victim-halving plus the redundancy penalty on a relationship that does not exist (or misses one that does). This is independent of L-006's NaN handling (there the values reach a comparison; here they are dropped asymmetrically). Note `min_points=20` counts zipped positions, not commonly-valid instants — a second-order overstatement of evidence on gappy data.

#### Contract and decisions
Ch.10 §10.1 (via the `setup_score` docstring + family code): "Pearson ρ on the last n=48 OK points of the two s_i series (same symbol+TF)". "OK points" implies commonly-OK instants; nothing authorizes independent per-side filtering with positional re-zip. No `PHASE2_DECISION_LOG.md` ruling covers redundancy pairing. Precedence: the "same symbol+TF … OK points" law governs — pairing must be over commonly-valid instants.

#### Frozen status and non-frozen alternative
**NOT frozen:** `apex/fabric/context.py` is outside the frozen set. The fix belongs in the function itself; no frozen change, no alternative layer needed.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — time-aware pairing (single path, non-frozen):** accept optional per-point times/keys (defaulting to positional index when absent for backward compatibility); drop only pairwise-incomplete instants; count `points` as commonly-valid pairs; keep the `min_points=20` skip with a traceable reason when keys are absent or insufficient. Side effects: complete-series behavior is BIT-IDENTICAL (no drops → same zip) — existing tests and the native producer path are unaffected; gappy inputs change from wrong-ρ to aligned-ρ-or-skip (intended). No hashes/identities/caches/DB/retraining impact (pure function, unhashed outputs consumed as floats).

#### My recommendation
Implement A with the optional-times signature (backward compatible, native path untouched), and add the probe's alternating-series case as a regression test.

#### Acceptance and regression tests
- The probe case (NaN at two different times) yields ρ computed over time-intersection (−1.0 here) with true pair counts; insufficient common pairs → named skip, never a re-aligned ρ.
- Complete-history behavior bit-identical (existing `test_fabric_context.py` redundancy tests pass unchanged).
- Family-level test: gappy `component_series` either halves the correct victim or skips with reason.

## L-008 — formula_volume_ratio SMA=0 branch contradicts the §2.2 epsilon formula

#### Auditor claim (short quote)
> "Contract and docstring explicitly require `V/max(SMA_prev,ε)` with a large-but-finite value for SMA=0; the code returns `(None,0.0)` for `formula_volume_ratio(20,0)` before dividing, and the existing test pins exactly that. For the default epsilon the formula gives `2E+13`; null volume is a separate state."

#### What I read (files, line ranges, functions, callers)
- `apex/quality/numerical.py:246–257` (`formula_volume_ratio`): `if sma_prev == 0: return None, 0.0` precedes the `guarded_div(V, max(sma_prev, eps_volume))` line — the epsilon floor is unreachable for exactly the input it exists for. The docstring (246–248) promises the opposite: "SMA=0 → large-but-finite via the epsilon floor (never NaN)" — the code contradicts its own contract sentence.
- `APEX_GEN5.md:835–839` (§2.2): "`volume_ratio = V / max(SMA_n(V), ε_volume)`, n=20, computed on bar t−1 … if `SMA_n(V)=0`, volume_ratio still resolves to a large-but-finite value via the epsilon floor; if V is null, Q_volume=0 …" — the SMA=0 and V-null states are explicitly distinguished; the code collapses SMA=0 into the missing/degraded bucket.
- `tests/unit/test_quality.py:247–251` (`test_core_formulas`): asserts `formula_volume_ratio(20, 0) → (None, 0.0)` — the deviation is pinned by a passing test (re-ran: 1 passed).
- Callers (mandatory grep): NONE in `apex/` or `scripts/` — the helper is currently test-only. Adjacent consistency notes: `_f41_volume_ratio` (`atomic/features.py:389–417`, frozen) and E03 `volume_ratio_pit` (`e03_volume/engine.py:127–133`) also return degraded/None on SMA≈0 rather than large-but-finite — so the "large-but-finite" reading has NO implementation anywhere in the checkout, while the degraded reading has three (one pinned by test). The contract sentence is unambiguous, but its operationalization (a 2E+13 ratio flowing into downstream consumers) has never existed.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONPATH=/home/user/Upstage python3 AUDIT/probes_V3c/L-008.py` + `python3 -m pytest -q -p no:cacheprovider tests/unit/test_quality.py::TestNumerical22::test_core_formulas`. Probe: `AUDIT/probes_V3c/L-008.py` (real helper; contract formula evaluated inline). Raw output: `AUDIT/probes_V3c/L-008.out`. Result: helper `(None, 0.0)`; contract formula `2.0E+13`; existing test passes (pins the deviation).

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). Code-vs-contract-vs-docstring triple contradiction is exact, and the test pin is verified by re-running. S2 because the helper has no runtime caller (latent), and because the "correct" behavior (emitting 2E+13) is itself operationally questionable — a giant finite ratio could do more downstream damage than a clean degraded flag. This row is therefore as much a contract-clarification item as a code defect: the fix direction needs an owner decision (run the epsilon formula, possibly with a governed cap, or amend the contract to the degraded reading that three implementations already share).

#### Root cause
The SMA=0 early-return was written as a degraded path (probably mirroring E03/`_f41`) while the docstring/contract sentence describes the epsilon-floor path; the guard order makes the floor dead code for SMA=0.

#### Direct impact
Today: none at runtime (no callers) — the impact is a pinned deviation: the test suite certifies behavior the contract forbids, so any future caller inherits a contract-violating helper with a green test suite.

#### Secondary effects and interactions (upstream/downstream)
Upstream, the same degraded-on-zero reading in `_f41` (frozen) and E03 (non-frozen) means "fixing" only this helper would create a THREE-way inconsistency (helper large-finite vs `_f41`/E03 degraded) unless the ruling covers all three. Downstream, if the epsilon reading is adopted, consumers must be audited for giant-ratio handling (2E+13 exceeds any sane feature range; quantization to 8 digits is fine, but thresholds/comparisons are not). If the degraded reading is adopted instead, the contract sentence + this docstring must be amended by owner ruling.

#### Contract and decisions
`APEX_GEN5.md:835–839` governs and is explicit (large-but-finite via floor; V-null separate). No `PHASE2_DECISION_LOG.md` ruling overrides it. Precedence: contract text governs over the three degraded implementations and the pinning test — BUT the operational risk of 2E+13 ratios means the owner should rule on the full triad (helper + `_f41` + E03) and on capping, not just flip this branch. Note `_f41` is frozen, so the triad ruling necessarily touches the frozen process.

#### Frozen status and non-frozen alternative
**NOT frozen:** `apex/quality/numerical.py` is outside the frozen set — this helper can be fixed without a frozen ruling. However, the CONSISTENT fix (helper + `_f41` frozen + E03) does touch one frozen file, and the contract-amendment alternative needs an owner ruling either way. Non-frozen alternative for the helper alone: fix the branch + docstring + test directly (no alternative layer needed).

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — epsilon-formula reading (non-frozen for this helper):** remove the early return so `guarded_div(V, max(sma_prev, eps))` runs; add a GOVERNED cap (owner-decided, e.g. ratio ceiling with a named reason) so "large-but-finite" does not mean "unbounded". Side effects: `test_core_formulas` MUST be updated (it pins the old branch); `_f41` (frozen — owner ruling) and E03 should follow for consistency; downstream consumers audited for giant ratios. No hash/cache/DB/retraining impact (pure helper, no callers).
**B — degraded-reading ruling (contract amendment):** owner rules SMA=0 → degraded `(None, 0.0)`; amend §2.2 sentence + this docstring. Side effects: test stays green; `_f41`/E03 already conform; the "large-but-finite" sentence is retired explicitly rather than violated silently. No code change at all.

#### My recommendation
Ask the owner to choose A-with-cap or B for the whole triad; do not flip this branch alone. If forced to act without a ruling, B (document current behavior as intended via a decision log entry) is safer than emitting 2E+13 into unprepared consumers — but B without an owner ruling would itself be a contract amendment, so the honest interim is: leave code+test as-is, record the deviation.

#### Acceptance and regression tests
- Under A: `V>0,SMA_prev=0 → finite value == V/eps (or governed cap with named reason)`; `V` genuinely missing → independent missing/degraded state per contract; `_f41`/E03 parity test across the triad.
- Under B: contract sentence amended; docstring/test descriptions updated to cite the ruling; a test pins the distinguished V-null vs SMA-zero states.
- Regression: `tests/unit/test_quality.py` (updated only as the ruling directs).
## L-009 — calc_numerical_contract guards non-finite AFTER arithmetic (raises; some positions silently VALID)

#### Auditor claim (short quote)
> "The docstring promises `(None,'QUARANTINED_NAN_INF','QX')` for NaN/Inf, but `Decimal('NaN')` raises `decimal.InvalidOperation` at comparison/`max` instead; the non-finite guard sits AFTER the arithmetic. Valid ingest pre-checks finite upstream, but this API does not honor its own contract."

#### What I read (files, line ranges, functions, callers)
- `apex/quality/numerical.py:128–166` (`calc_numerical_contract`, full file read): epsilon pre-computation (136–139), `Decimal(str(x))` coercion (141–142), `H_d < L_d` comparison (144), `max(range_d, eps_range)` (147), five ratio computations + `quantize` (149–156) — and only THEN the non-finite check (158–160) over the five results. `Decimal('NaN')` `<`/`max`/`quantize` raise `InvalidOperation` (IEEE comparison semantics), so NaN in any compared/coerced position explodes before line 158 is reached.
- `apex/data_catalog/contracts.py:204–212` (`validate_market_observation` step 2): the raw ingest path raises `E-NUM-001/002` on non-finite OHLCV/OI — the upstream finite pre-condition the auditor cites (verified by reading; ingest callers in `sqlite_store`/`bootstrap_service` enforce it before any quality math).
- `tests/unit/test_quality.py:219–239`: pins the finite example + `H<L` quarantine; NO NaN/Inf test exists for this function — the fix breaks nothing.
- Callers (mandatory grep): NONE in `apex/` or `scripts/` — the function is currently test-only; all native quality math flows through `calc_quality_vector`/`formula_*`/producer guards instead.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONPATH=/home/user/Upstage python3 AUDIT/probes_V3c/L-009.py`. Probe: `AUDIT/probes_V3c/L-009.py` (real function; each Decimal input set to NaN/+Inf in turn). Raw output: `AUDIT/probes_V3c/L-009.out`. Result: baseline `VALID/Q1`; `C/O/H/L/ATR_n=NaN` and `C/H=+Inf` → `RAISED InvalidOperation` (claim confirmed); `H<L` finite → `QUARANTINED_H_LT_L/QX` (intact). BEYOND the claim, four positions return `VALID/Q1` with non-finite inputs: `V=NaN`, `tick_size=NaN`, `quantity_step=NaN` (V/tick/step never enter the five ratios, so the post-guard cannot see them) and `ATR_n=+Inf` (`range/max(Inf,eps) = 0`, finite — silently accepted).

#### Verdict and reasoning
**CONFIRMED (worse than claimed) — independent severity S2** (auditor S2 retained). The claimed exception path reproduces on 6 positions, and 4 further positions fail WORSE than claimed (silent `VALID` on NaN/Inf, not even an exception). S2 because the function has no caller in the checkout (latent API) and the ingest path it would sit behind already refuses non-finite — but the silent-`VALID` positions mean a future direct caller would get corrupted quality output with no signal at all, which is strictly worse than the loud `InvalidOperation`.

#### Root cause
Guard-after-compute plus guard-over-outputs-only: finiteness is checked on the five derived ratios after all comparisons/divisions/quantizations, so (a) NaN in compared positions raises before the guard runs, and (b) NaN/Inf in positions that do not affect the ratios (V, tick, step) or that collapse to finite (ATR=+Inf) passes as `VALID`.

#### Direct impact
Direct callers get one of three wrong outcomes for non-finite inputs: an unclassified `InvalidOperation` traceback (6 positions), or a confident `VALID/Q1` (4 positions) — never the documented `QUARANTINED_NAN_INF/QX`. The documented refusal contract is dead in all 10 non-finite positions tested.

#### Secondary effects and interactions (upstream/downstream)
Upstream, `validate_market_observation` step 2 protects the ingest path only — this function's whole purpose as a standalone §2.2 oracle is defeated for direct callers. Downstream, an uncaught `InvalidOperation` would abort quality reporting/lineage chains with an unrelated traceback (no Ch.7 code, no QX label), while the silent-`VALID` cases would feed NaN-derived eps outputs (`eps_price/volume/range` can be NaN when tick/step/ATR are NaN — they are returned inside the `VALID` dict) into any consumer. Note `guarded_div` (same file, :91–107) demonstrates the correct pattern: explicit pre-check raising `ValueError("NAN_INF_QX")`.

#### Contract and decisions
Module contract (`numerical.py` docstring + §2.2): "NaN/Inf always set Q_formula_valid=0 (degraded) — never silently skipped"; the function docstring promises `QUARANTINED_NAN_INF/QX`. Both are violated (loudly on 6 positions, silently on 4). No `PHASE2_DECISION_LOG.md` ruling touches this function. Precedence: the fail-closed §2.2 contract governs; the guard must move before all arithmetic and cover all inputs.

#### Frozen status and non-frozen alternative
**NOT frozen:** `apex/quality/numerical.py` is outside the frozen set. Fix directly; no alternative layer needed.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — pre-validate all inputs (single path, non-frozen):** check `is_finite()` on every Decimal input (C/O/H/L/V/ATR_n/tick/step) BEFORE any comparison or arithmetic; any non-finite → `(None, "QUARANTINED_NAN_INF", "QX")`. Keep the post-check as defense-in-depth. Side effects: the 6 raising positions become named refusals and the 4 silent-`VALID` positions become refusals (all intended); NO existing test breaks (finite example + `H<L` pins are preserved — verify by re-running `test_quality.py`); no callers exist, so no downstream behavior changes; no hashes/caches/DB/retraining impact.

#### My recommendation
Implement A (ten-line pre-validation); add the probe's 10-position matrix as a regression test.

#### Acceptance and regression tests
- NaN/±Inf in EVERY field (C/O/H/L/V/ATR_n/tick/step) → `QUARANTINED_NAN_INF/QX` with no traceback; `H<L` still quarantines with its own code; ordinary numbers keep the exact pinned outputs (`test_numerical_contract_example` bit-identical).
- Regression: full `tests/unit/test_quality.py` passes.

## L-010 — fibonacci.confluence clusters by neighbor gaps, ignores source independence and diameter

#### Auditor claim (short quote)
> "`confluence` claims independent levels with in-tolerance diameter, but clusters by neighbor distances and never checks source. One source with levels 100/100.1/100.2 at ATR=1 returned a 3-member cluster with spread=0.2 over tolerance=0.15; the existing test even pins spread=0.2 for ATR=1."

#### What I read (files, line ranges, functions, callers)
- `apex/pattern/fibonacci.py:160–196` (`confluence`, full file read): flattens `(level, source)` pairs, sorts by price, and cuts a new cluster ONLY when `v − cur[-1][0] > tol` (neighbor gap, :184–187) — single-linkage chaining with no diameter cap and no source-diversity check; clusters of size ≥2 are reported with `spread = max−min` (:190–196), which can therefore exceed `tol` by construction.
- `APEX_GEN5.md:15005–15021` (Ch.9 §9.0 Pattern contract): lists "Fibonacci … confluence" among deterministic detection families without pinning a single-source/diameter rule — the "independent constructions" requirement comes from the function's own docstring ("Cluster levels from independent constructions", :160–161), which the code does not enforce.
- `tests/unit/test_pattern_fibonacci.py:117–126` (`test_levels_within_tolerance_cluster`): asserts `spread == 0.2` at `atr=1.0` (tol=0.15) — pins the diameter violation (re-ran: 1 passed).
- Callers/boundary (mandatory grep): `confluence` is re-exported by `apex/pattern/__init__.py:42–55` but NEVER called in `apex/` outside its module — `detect.py` (full grep) implements its own touch-count logic (`_touch_count`, :586–587) and never imports fibonacci levels; harmonics are `RESEARCH_ONLY` with a scoring gate (`detect.py:160–164`, `assert_scoring_admissible` refuses RESEARCH_ONLY rows). No native decision path consumes `confluence` today.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONPATH=/home/user/Upstage python3 AUDIT/probes_V3c/L-010.py` + re-run of the pinning test. Probe: `AUDIT/probes_V3c/L-010.py` (real `confluence`). Raw output: `AUDIT/probes_V3c/L-010.out`. Result: single source `[100,100.1,100.2]` → 1 cluster, `count=3, spread=0.2 > tol=0.15` (auditor's case exactly); single-source 6-chain → `spread=0.5` (diameter unbounded — chaining); two-source `[100],[100.1]` → `spread=0.1` (legitimate cluster shape); existing test passes (pins the violation).

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). Single-source clustering, diameter overflow, and the pinning test all reproduce exactly; the chaining probe shows the diameter is unbounded, not just slightly over. S2 because `confluence` has no consumer in the checkout (research-only helper, scoring-gated harmonics) — the impact is a certified-wrong oracle awaiting a future caller, plus a test suite that blesses the wrong behavior. Distinct from N-010 (E02 streaming merge), which is the same single-linkage-vs-diameter theme in a different, RUNTIME engine — that one is S1; this one stays S2 for latency.

#### Root cause
Single-linkage clustering (cut on neighbor gap) without the two constraints the docstring implies: (1) minimum count of DISTINCT sources/legs, (2) complete-linkage/diameter cap (`spread ≤ tol`).

#### Direct impact
Confluence counts are inflated (one leg can "confirm" itself) and reported clusters can span many× the tolerance (0.5 vs 0.15 demonstrated) — any consumer would treat a lone noisy ladder as multi-source confirmation.

#### Secondary effects and interactions (upstream/downstream)
Upstream, the `confluence_atr_mult=0.15` tolerance (the θ_eq row) is the only governed input and is applied to gaps, not diameters — the tolerance's meaning is silently changed. Downstream, no native consumer exists; IF connected to pattern/stop/E07 logic later, entry confidence and stop placement would rest on phantom confirmation. Interaction: fixing the diameter without fixing source-independence (or vice versa) leaves half the hole — both constraints must land together, and the pinning test must be rewritten, not just updated.

#### Contract and decisions
Ch.9 §9.0 names confluence as a Fibonacci family member but does not quantify independence/diameter; the function's docstring ("independent constructions … within tolerance") is the operative spec and is violated. E02's `group_equal_levels_hierarchical` (diameter/median rule, cited by N-010) is the in-checkout precedent for the complete-linkage reading. No `PHASE2_DECISION_LOG.md` ruling covers fibonacci confluence. Precedence: docstring + E02 precedent govern until the owner quantifies "independent" (distinct legs? distinct sources? distinct families?) and the diameter rule.

#### Frozen status and non-frozen alternative
**NOT frozen:** `apex/pattern/fibonacci.py` is outside the frozen set. Fix directly; no alternative layer needed.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — enforce both constraints (single path, non-frozen):** require ≥2 distinct sources (per the owner-quantified independence rule) AND `spread ≤ tol` per cluster (split or reject over-diameter chains deterministically). Side effects: `test_levels_within_tolerance_cluster` MUST be rewritten (it pins spread=0.2>tol as correct); other confluence tests use in-tolerance multi-source cases (re-run to confirm); no callers exist, so no downstream changes; no hashes/caches/DB/retraining impact.

#### My recommendation
Ask the owner to quantify independence + diameter (one ruling), then implement A and rewrite the pinning test in the same change — never "fix" the code while leaving a test that certifies the old behavior.

#### Acceptance and regression tests
- Single source alone → no cluster; `spread>tol` chains → split/rejected per the ruling; legitimate multi-source in-tolerance sets still cluster with identical centres.
- Regression: `tests/unit/test_pattern_fibonacci.py` (with the rewritten test) passes; `detect.py` scoring-gate tests unaffected.
## L-011 — Fibonacci APIs refuse NaN but pass ±Inf through as valid levels

#### Auditor claim (short quote)
> "`level(100,200,inf)` gives `inf` and `extensions(...,ratios=(inf,))` gives `{inf:inf}`; the NaN comparison and the `r<1` check do not refuse Infinity. Infinite ATR and infinite levels can also pass through `confluence`, against the non-finite fail-closed contract."

#### What I read (files, line ranges, functions, callers)
- `apex/pattern/fibonacci.py` (complete, 266 lines): `level` (62–67) checks `r != r` (NaN only) — `inf` computes `a + inf·(b−a) = inf`; `extensions` (93–103) checks only `r < 1.0` — `inf` passes; verified asymmetry for NaN ratios: `retracements`/`expansion` compute inline WITHOUT calling `level`, so `ratios=(nan,)` passes through as `{nan:nan}` (supplementary probe in `L-011.out`), while `projections`/`extensions` route through `level` and refuse NaN; `retracements` (80–91) and `expansion` (106–123) validate only the segment/NaN-C, never ratios; `confluence` (160–177) refuses NaN levels (:174) but appends ±inf levels, and refuses only `atr<=0/NaN/None` (:168–169) — `atr=+inf` yields `tol=+inf`, clustering everything; `harmonic_prz` (126–157) has NO finite checks at all.
- Existing-test boundary: `tests/unit/test_pattern_fibonacci.py:54–63` pins NaN-`r` refusal + inf-SEGMENT refusal (`_validate_segment` is correct) + degenerate-leg refusal — the suite proves the authors intended fail-closed but covered only NaN ratios and inf segments.
- Callers/boundary: same as L-010 — `fibonacci` APIs are re-exported but never called in `apex/`; harmonics RESEARCH_ONLY with scoring gate; no native decision consumption.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONPATH=/home/user/Upstage python3 AUDIT/probes_V3c/L-011.py`. Probe: `AUDIT/probes_V3c/L-011.py` (real APIs). Raw output: `AUDIT/probes_V3c/L-011.out`. Result: `level(100,200,inf) → inf`; `extensions(ratios=(inf,)) → {inf:inf}`; `retracements(ratios=(inf,)) → {inf:-inf}` (beyond claim, same hole); NaN-`r` refused (control); `confluence` mixed finite+inf → `[]` (inf level silently dropped, no refusal); `confluence` two inf levels → cluster `{centre: inf, spread: nan}` (passes through); `confluence atr=inf` → 400-wide cluster of [100, 500] (passes through); `harmonic_prz` inf legs → `prz: nan` silently recorded as RESEARCH_ONLY output.

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). Both claimed pass-throughs reproduce, plus three same-family extras (inf retracement ratios, silent inf-drop in mixed confluence, NaN `prz` from inf legs). S2 because the module has no native consumer and harmonics are scoring-gated research-only — latent API surface. The `spread: nan` cluster is the nastiest shape: a NaN smuggled INSIDE a passed cluster record, which would poison any downstream comparison exactly like L-006.

#### Root cause
Asymmetric non-finite discipline: NaN checks (`!=`) placed per-function instead of a uniform `math.isfinite` gate on every numeric input AND every computed output; `inf` was simply never considered (comparisons like `r<1` and `atr<=0` are inf-transparent).

#### Direct impact
Infinite levels/ratios/ATRs produce infinite/NaN-carrying records presented as ordinary outputs (`{inf:inf}`, `{centre:inf, spread:nan}`, 400-wide "confluence") — no refusal, no reason code. Mixed finite+inf confluence silently drops the inf level and may return `[]` (indistinguishable from "no confluence").

#### Secondary effects and interactions (upstream/downstream)
Upstream, `_validate_segment` shows the correct pattern (finite + degenerate checks) — the ladders just do not extend it to ratios, and `harmonic_prz`/`confluence` never got it. Downstream, no native consumer; IF pattern/stop logic ever consumes these helpers, inf levels would corrupt stop placement and the `spread:nan` record would fail-open any `spread <= tol` check downstream (NaN comparison — the L-006 theme). Interaction with L-010: the diameter fix must ALSO refuse non-finite levels first, or `spread:nan` evades the diameter cap.

#### Contract and decisions
Ch.9 §9.0 (`Level(r) = A + r·(B−A)`, finite-price formula) presupposes finite inputs; the repo-wide non-finite fail-closed rule (§2.2 "NaN/Inf never return silently", `canonical_json` forbidding NaN/Inf, `measured_number` finite checks) governs all numeric APIs. No `PHASE2_DECISION_LOG.md` ruling covers fibonacci validation. Precedence: the fail-closed rule governs; no governed ratio/level domain beyond finiteness is documented, so finiteness is the minimum bar.

#### Frozen status and non-frozen alternative
**NOT frozen:** `apex/pattern/fibonacci.py` is outside the frozen set. Fix directly; no alternative layer needed.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — uniform isfinite gates (single path, non-frozen):** `math.isfinite` on every numeric input (a/b/c/r/ATR/levels/XABCD) before arithmetic AND on every computed output (level/ladder/prz/cluster fields) after arithmetic, with named `FIB_*_QX` refusals. Side effects: inf-input calls become refusals (intended); finite behavior bit-identical — existing tests use finite inputs (re-run to confirm); the NaN pins stay green. No callers exist: no downstream changes; no hashes/caches/DB/retraining impact.

#### My recommendation
Implement A together with the L-010 diameter/source fix (one coherent confluence/validation change; the L-010 acceptance tests must include non-finite cases so `spread:nan` cannot evade the diameter cap).

#### Acceptance and regression tests
- ±Inf/NaN in every a/b/c/r/ATR/level/XABCD position AND in every intermediate output → named refusal; ordinary levels bit-consistent (`ladder(100,200)` records unchanged).
- `confluence` mixed finite+inf → refusal (not silent `[]`); `harmonic_prz` inf legs → refusal (not `prz:nan`).
- Regression: `tests/unit/test_pattern_fibonacci.py` passes (NaN pins preserved).

## L-012 — Gate13 + risk adjudicate accept impossible calibration metrics (log_loss=+inf/−100 → ALLOW 2.5)

#### Auditor claim (short quote)
> "Gate13 checks only PRESENCE of the three metrics for non-bootstrap packages; `_clip01` refuses only NaN, clips `+inf→1` and negatives→0. With a synthetic versioned LIVE package (`cal=brier=0`, `log_loss` +inf and −100), both passed Gate13 and `adjudicate` on controlled risk input gave `ALLOW/sized_quantity=2.5`; no real calibrated/OOS package exists in the checkout. H-014 covers the forecast label separately; this row is the numeric control of the package in setup/risk."

#### What I read (files, line ranges, functions, callers)
- `apex/quality/vector.py:229–250` (`_clip01` + `bounded_model_quality`): `_clip01` raises only on NaN (`v != v`); `+inf→1.0`, any negative→`0.0`; the D59 bounded form `1 − (clip(cal) + clip(2·brier) + clip(log_loss/ln4))/3` then scores garbage as healthy (0.667 for +inf, 1.0 for −100).
- `apex/setup/gates.py:362–414` (`gate13_parameter_package`): non-bootstrap path requires the three keys present, computes the bounded form, compares `value < thr` (0.5) — no finiteness/domain check on the metrics; `ValueError` from `_clip01(NaN)` is caught as `GATE13_METRICS_MISSING` (fail) — so NaN fails while +inf/negatives pass (verified asymmetry).
- `apex/risk/kernel.py:441–498` (`adjudicate`): with `risk_input["package"]` set, calls gate13 and sizes on pass (`size()` → `sized_quantity`, :360–430); vetoes evaluated after the package check. Callers of gate13: `run_all` + `adjudicate` only.
- `PHASE2_TRACEABILITY_MATRIX.md:207` (C6-G13): "package must carry version+id; degraded/missing ⇒ block (…the risk kernel REFUSES to size on a degraded package…)" — impossible metrics are a degraded package the gate cannot see.
- Boundary: `apex/ops/engine_context.py::paper_package_binding` returns `BOOTSTRAP_UNCALIBRATED` with NO metric keys (verified in probe: keys contain no `rolling_calibration_error/brier/log_loss`) — the native PAPER path never exercises the recorded-metrics branch; no calibrated package artifact exists in the checkout (auditor's claim; consistent with `test_paper_package_is_named_uncalibrated_and_not_zero_metrics` and the absence of any package-producing code path writing metrics — grep shows metrics only in tests/probes).
- Existing tests: `test_setup_gates.py:172–191` (finite good `0.05/0.20/0.69 → PACKAGE_VALID`, finite degraded `1.0/1.0/2.0 → GATE13_PACKAGE_DEGRADED`), `test_cp146.py::test_t4` + `test_paper_package…` (finite triples) — all finite, so a pre-check breaks none.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONPATH=/home/user/Upstage python3 AUDIT/probes_V3c/L-012.py`. Probe: `AUDIT/probes_V3c/L-012.py` (real `_clip01`/`bounded_model_quality`/gate13/`adjudicate`; synthetic versioned package + controlled risk input with capital=10000, stop=20, min_q=0.1). Raw output: `AUDIT/probes_V3c/L-012.out`. Result: `_clip01(+inf)=1.0, _clip01(−100)=0.0, _clip01(nan)→ValueError`; `log_loss=+inf → score 0.6667 → PACKAGE_VALID`; `log_loss=−100 → 1.0 → PACKAGE_VALID`; `brier=−100 → 0.8341 → PACKAGE_VALID`; `log_loss=NaN → GATE13_METRICS_MISSING (fail)`; `adjudicate` on BOTH bad packages → `ALLOW/sized_quantity=2.5/reason=SIZED` (auditor's numbers exactly); native PAPER package carries no metrics.

#### Verdict and reasoning
**CONFIRMED — independent severity S1** (auditor S1 retained). Gate13 pass on impossible metrics and `ALLOW/2.5` sizing reproduce exactly, including the NaN-fails-but-inf-passes asymmetry. S1 (not S0) because exploitation needs a recorded-metrics package carrying bad values: the native PAPER path supplies a metric-less bootstrap package (different branch), and no calibrated-package producer exists in the checkout — so the hole is armed but unfed today. It is S1 rather than S2 because gate13 is a HARD safety gate whose verdict directly sizes real quantity in `adjudicate`, and the FIRST real (or corrupted, or hand-fed) metrics package with a bad value would sail through a gate whose traceability row promises refusal. No LIVE trading is proven or claimed — the probe sizes on synthetic inputs only.

#### Root cause
Missing domain validation before clipping: `_clip01` treats "not NaN" as "valid", and clipping (designed to bound VALID metrics per D59) silently rehabilitates impossible ones (+inf→worst-valid→bounded-pass, negatives→best-valid→pass). Gate13 then scores and thresholds the laundered numbers.

#### Direct impact
A package with statistically impossible metrics (`log_loss=+inf/−100`, negative brier/calibration, +inf anywhere) is judged `PACKAGE_VALID`, and `adjudicate` sizes positive quantity on it. The gate-13 verdict is unreliable as a package-health signal for any recorded-metrics package.

#### Secondary effects and interactions (upstream/downstream)
Upstream, the metrics have no producer in the checkout (no schema/provenance validation exists for the day one arrives) — the fix must cover metric INGEST (finite? non-negative? in-domain?) not just gate13. Downstream, `adjudicate`'s package check is the ONLY metric control before sizing — vetoes do not re-examine package metrics — so gate13's pass is final. Cross-refs: H-014 (forecast LABEL validity — the label side; this row is the numeric side, exactly as the auditor scopes it); D-026 (risk-kernel NaN permissiveness — adjacent theme, but veto inputs here were controlled/finite); L-006 (same clip/compare-without-validate family at the gate layer).

#### Contract and decisions
D59 item (2) (`PHASE2_DECISION_LOG.md:1177`) mandates the bounded FORM `1 − (clip(cal) + clip(2·brier) + clip(log_loss/ln4))/3` — the formula is owner-governed and must be preserved for valid inputs. D59 does NOT mandate the absence of validation, and its purpose (admit well-calibrated models, per `test_t4`) is about bounding valid metrics, not laundering invalid ones. C6-G13 (traceability :207) requires degraded-package refusal. Precedence: D59's formula stands; a finite+domain pre-check (finite? cal≥0? brier≥0? log_loss≥0?) with a named refusal reason implements C6-G13 WITHOUT altering D59's formula on any valid input — no D59 conflict, no new ruling strictly needed (though recording the domains in the decision log is advisable).

#### Frozen status and non-frozen alternative
**NOT frozen:** `apex/quality/vector.py`, `apex/setup/gates.py`, `apex/risk/kernel.py` are all outside the frozen set. Fix directly; no alternative layer needed. No frozen YAML/lock change (thresholds unchanged).

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — finite+domain pre-validation (single path, non-frozen):** before clipping, require each metric finite AND in its governed domain (cal≥0, brier≥0, log_loss≥0 — the natural statistical domains; record in decision log); violations → named refusal (`GATE13_METRIC_OUT_OF_DOMAIN` / `NONFINITE`), distinct from `METRICS_MISSING`. Apply in `bounded_model_quality` (so `q_forecast` shares it) or at gate13 entry — one place, shared by both callers. Side effects: impossible-metric packages now refuse (intended); ALL existing tests use finite in-domain metrics (good `0.05/0.20/0.69`, degraded `1.0/1.0/2.0`, `test_t4` triples) — none break; NaN behavior changes reason (`METRICS_MISSING` → named nonfinite reason — verify no test pins the NaN reason: none found); valid-input scores bit-identical (formula untouched). No hashes/caches/DB/retraining impact (pure functions).

#### My recommendation
Implement A with the three domains recorded in the decision log; add the probe's +inf/−100/negative matrix as gate13 regression tests. Do NOT "fix" by changing D59's formula.

#### Acceptance and regression tests
- `log_loss/brier/cal ∈ {+inf, −inf, negative, NaN}` → named refusal with the offending metric identified; finite in-domain triples keep bit-identical scores (good→VALID, degraded→DEGRADED).
- `adjudicate` with an impossible-metrics package → `REJECT/PARAMETER_PACKAGE_INVALID`, never sized.
- Regression: `tests/unit/test_setup_gates.py`, `tests/unit/test_quality.py`, `tests/unit/test_cp146.py` pass unchanged.
## L-013 — temporal_window_validity is a documented combiner input with weight 0 (dead by default)

#### Auditor claim (short quote)
> "`temporal_window_validity` is one of seven `CombinerInputs` but its default weight is 0; moving it 0→1 in the probe left confidence unchanged (0.9701133202). Gate8 checks only the `temporal_quality>=Q2` label and has nothing to do with this validity (e.g. `temporal_validity_projection("DEGRADED")=0` while Gate8 passes on Q2); Gate8 does not even receive validity. The contract names the other six weights and documents no weight for this input, so no non-zero value is assumed as approved without an owner decision; native E12 admission on this probe is not established."

#### What I read (files, line ranges, functions, callers)
- `apex/fabric/context.py` (complete, 648 lines): `DEFAULT_COMBINER_WEIGHTS` (113–122) with `"temporal_window_validity": 0.0` + comment "documented input, no documented weight"; `CombinerInputs` (264–340, seven slots incl. validity); `context_confidence` (342–384) multiplies `wn["temporal_window_validity"] * validity` — identically 0 for any validity at default weights (normalization divides by Σw=1.0, so no rescaling side effect either).
- `apex/setup/gates.py:259–264` (`gate8_temporal_window_quality(quality_class)`): compares the Q-class label against `gate_quality_min_class=2`; signature takes NO validity parameter (verified by inspection).
- `apex/ops/engine_context.py:431–437` (`temporal_validity_projection`: VALID→1.0, DEGRADED/INVALID→0.0, else BridgeError) and :2000–2018 (producer sets `"temporal_window_validity": temporal_validity_projection(temporal_event.validity)` alongside `"temporal_quality": temporal["quality"]`) — validity and the Q-label travel as SEPARATE context fields into different consumers (combiner vs gate8).
- `tests/unit/test_fabric_context.py:154–164` (`test_l1_default_weights_are_the_documented_ones`): pins the 0.0 weight AND Σ(six)=1.0 exactly (re-ran: 1 passed) — the dead input is certified by a passing test.
- `APEX_GEN5.md:14824–14839` (Ch.8 §8.0): combiner formula over seven `x[k]` slots INCLUDING `temporal_window_validity`, but "Governed L1 default weights" lists only six (0.35/0.20/0.15/0.15/0.10/0.05, Σ=1.0) with no weight for validity.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONPATH=/home/user/Upstage python3 AUDIT/probes_V3c/L-013.py` + re-run of the pinning test. Probe: `AUDIT/probes_V3c/L-013.py` (real combiner/gate8/projection; synthetic inputs). Raw output: `AUDIT/probes_V3c/L-013.out`. Result: validity 0→1 with all else equal gives IDENTICAL `confidence=0.9426758241011313, z=0.85` (invariance confirmed; absolute value differs from the auditor's 0.9701 only because inputs differ — the claim is invariance, which holds for every input); `gate8('Q2') → passed`; `temporal_validity_projection('DEGRADED') = 0.0`; gate8 signature has no validity parameter; weight-pinning test passes.

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). Zero weight, confidence invariance, gate8's label-only check, and the missing contract weight are all verified exactly as scoped (the auditor explicitly refuses to assume an approved non-zero value — I concur). S2 because the behavior is DOCUMENTED in code (comment + docstring + pinned test), the producer still feeds the field honestly (0.0 for DEGRADED), and gate8 provides a SEPARATE temporal-quality channel (Q-label) — so nothing is silently unsafe; the defect is a dead documented input that misleads ablation/interpretation (analysts varying validity will conclude "temporal quality does not matter") and a contract that lists an input without a weight. Downgrading to S3 was considered (it is documented behavior); S2 stands because a documented-but-dead safety-relevant input in a confidence combiner is more than documentation — it shapes wrong conclusions.

#### Root cause
Contract under-specification (seven slots, six weights) resolved in code by weight 0.0 — a defensible reading ("no invented weights") that silently disconnects the input, combined with gate8 consuming a DIFFERENT temporal signal (E12 Q-class) so no alarm fires.

#### Direct impact
At default weights, `temporal_window_validity` cannot influence `context_confidence` in any direction: fully-invalid temporal state (0.0) and fully-valid (1.0) score identically, and `Q2` temporal quality passes gate8 regardless of validity.

#### Secondary effects and interactions (upstream/downstream)
Upstream, the producer computes validity faithfully from the E12 event (`VALID→1, DEGRADED/INVALID→0`) — the data is good, the weight kills it. Downstream, `context_confidence` consumers (forecast/decision bands) and any ablation study inherit the blind spot; `validate_produced_context` range-checks the field (0–1) but cannot detect its irrelevance. Giving validity a positive weight WITHOUT renormalizing would break Σw=1 (the code normalizes anyway, rescaling the six governed weights — a governed-change side effect); giving it weight with renormalization changes EVERY confidence value. Either direction needs the owner decision the auditor asks for.

#### Contract and decisions
`APEX_GEN5.md:14824–14839` lists validity among `x[k]` (so it is MEANT to matter) but documents no weight (so no value is approved). The six governed weights sum to exactly 1.0, consistent with validity being an unweighted arrival. No `PHASE2_DECISION_LOG.md` ruling covers the validity weight. Precedence: the contract's slot list + the no-invention rule jointly support "weight 0 until the owner rules" — the code's choice is lawful but must be either completed (owner sets the role) or made explicit (owner drops the slot); it cannot remain a documented input with silent zero effect forever.

#### Frozen status and non-frozen alternative
**NOT frozen:** `apex/fabric/context.py`, `apex/setup/gates.py`, `apex/ops/engine_context.py` are all outside the frozen set. BUT the weight table is GOVERNED (SL-12: "all weights are governed") — changing 0.0 to any positive value is a governed-parameter change requiring owner approval even though no frozen FILE is touched. The `test_l1_default_weights…` pin must be updated in the same change.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
This row needs an owner DECISION first; the code change follows the decision:
**A — owner assigns validity a role:** positive weight (with renormalization of all seven + updated pin test + confidence-value migration note: EVERY historical confidence changes), or a separate validity gate/cap, or explicit slot removal (contract + `CombinerInputs` + producer field). Side effects: any variant changes confidence outputs and breaks the pinning test BY DESIGN (update it); the weight variant additionally rescales the six governed weights through normalization — record the new seven.
**B — document-and-hold (no behavior change):** record in the decision log that weight-0-until-ruled is intended, and add a combiner WARNING (reason field) when validity=0 so the dead input at least surfaces. Side effects: minimal; does not fix interpretation risk.

#### My recommendation
Request the owner decision (A's three variants are mutually exclusive and only the owner can choose); implement B's surfacing warning meanwhile so `validity=0` never passes silently through a confidence number again.

#### Acceptance and regression tests
- Post-decision: two contexts differing ONLY in validity produce the decision-specified versioned outputs; invalid-validity + Q2 is either end-to-end refused or its allowed path is documented.
- The pinning test reflects the ruled weights (Σ=1 over the ruled set).
- Regression: `tests/unit/test_fabric_context.py`, gate8 matrix tests, producer-bundle tests.

## L-014 — liquidity_regime_composite standardizes each series' mean against itself (always exactly 0)

#### Auditor claim (short quote)
> "`liquidity_regime_composite` takes the z-score of the MEAN OF THE SAME SERIES with that series' mean/std — which is zero; three different amihud/obi/kyle windows all gave composite=0. The 38-concept registry count proves nothing about its use/correctness."

#### What I read (files, line ranges, functions, callers)
- `apex/research/proxies.py:533–584` (`liquidity_regime_composite`, full file read): `_zscore` returns `(mean, var, sd)` of the input list (:521–531); each component is then `(sum(xs)/len(xs) − m)/s` where `m` IS `sum(xs)/len(xs)` of the same list (:566–573) — `(m−m)/s = 0` identically (same float ops → exactly `0.0`, not approximately). The weighted combination of three zeros is 0 regardless of weights/signs (the Amihud negative sign is dead).
- `tests/unit/test_research_proxies.py:231–237` (`test_composite_weights_and_sign`): asserts only component keys + `higher_is_better_liquidity` + `isfinite(composite)` — `0.0` passes, so the suite neither pins nor catches the bug.
- Callers (mandatory grep): NONE in `apex/` or `scripts/` — no runtime, optimizer, governance, or E11/E02 path calls `liquidity_regime_composite` (E02 has its own `kyle_lambda`; the registry `formula` field is metadata). The B08 registry row claims "composite … feeding context/regime" — no such feed exists in code.
- The docstring's intent ("standardized (z-scores within their own windows)") is ambiguous but CANNOT mean "z of the mean against itself" — that quantity is definitionally 0 and carries no information under any reading.

#### Reproduction (command, probe file, actual result)
Command: `PYTHONPATH=/home/user/Upstage python3 AUDIT/probes_V3c/L-014.py`. Probe: `AUDIT/probes_V3c/L-014.py` (real function; calm/trending/volatile synthetic windows). Raw output: `AUDIT/probes_V3c/L-014.out`. Result: all three regime-distinct windows → `composite=0.0` with all components `0.0` exactly.

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). The always-zero is structural (`(m−m)/s`), reproduced on three distinct windows with exact `0.0`. S2 because there is no caller (a wrong number nobody reads is latent), NOT S1: no risk/slippage/regime path consumes B08 today despite the registry row's "feeding context/regime" claim. Would escalate to S1 on first consumption (a regime-insensitive composite wired into sizing/slippage would silently flatten regime response).

#### Root cause
Wrong estimand: the code standardizes the window MEAN against the window distribution instead of standardizing the CURRENT observation against a historical baseline (or combining per-bar z-scores over time). The most likely intended formula given the signature (three windows, no separate baseline argument) is z of the LAST value vs the window, or mean-vs-baseline with a baseline the signature never accepted.

#### Direct impact
B08 carries zero information: every market regime maps to composite 0.0. Any present-or-future consumer reads a constant disguised as a measurement (with `q_label: Q3`, no less).

#### Secondary effects and interactions (upstream/downstream)
Upstream, the three input series are accepted and validated (`INSUFFICIENT_HISTORY_Z`, `ZERO_VARIANCE_Z` still fire — the function is not TOTALLY dead, only its VALUE is), which makes the bug harder to notice: errors flow, values do not. Downstream, nothing consumes it; the registry row's "feeding context/regime" integration claim is aspirational text, and `registry_summary` counts B08 as IMPLEMENTED — registry-completeness metrics overstate working functionality. Note `_zscore` uses sample variance (n−1) while catalog math uses population variance (n) — a consistency question for the fix, not part of this verdict.

#### Contract and decisions
Ch.20/AA.2–AA.4 (registry B08 row): "composite of Amihud + OBI proxy + Kyle λ feeding context/regime" — the code fulfills the registration, not the formula (no blueprint formula is quoted for B08 in the module; the module's EC-register discipline says unformulated concepts stay `REGISTERED_OPEN` with NO active value — B08 is marked IMPLEMENTED with an active, wrong value, violating that discipline). No `PHASE2_DECISION_LOG.md` ruling covers B08. Precedence: the EC-register discipline governs — B08 should either compute a real composite or drop to `REGISTERED_OPEN` with no value.

#### Frozen status and non-frozen alternative
**NOT frozen:** `apex/research/proxies.py` is outside the frozen set (only `research/bootstrap.py` and `research/backtest.py` are frozen). Fix directly; no alternative layer needed.

#### Fix options (A/B/C… each with side effects, or "single path" with justification)
**A — real composite (non-frozen):** standardize the CURRENT (last) value of each series against its window (PIT: last value scored, window as baseline — the L-003 lesson), or accept an explicit separate historical baseline per the auditor's suggestion; combine with the governed weights keeping the Amihud negative sign. Side effects: B08 values change 0→real (intended); existing test stays green (keys/finite/label assertions all still hold — strengthen it with a direction test); NO caller exists, so nothing downstream changes. No hashes/caches/DB/retraining impact.
**B — demote to REGISTERED_OPEN (non-frozen, if no formula is approved):** remove the active value per EC-register discipline until a governed formula exists. Side effects: `test_composite_weights_and_sign` must be reworked (no value to assert); registry counts shift IMPLEMENTED→OPEN (honest).

#### My recommendation
A if the owner approves the last-vs-window (or baseline) formula — it is a small, callerless, test-safe fix; otherwise B (an honest OPEN beats a wire-ready zero). Either way, correct the "feeding context/regime" integration text or wire the feed — not both states at once.

#### Acceptance and regression tests
- Regime-distinct windows give directionally-correct distinct composites (illiquid≪liquid given the higher-is-better convention); constant windows still raise `ZERO_VARIANCE_Z` (fail-closed preserved); no future leak (last-value scoring; shifting history must not change earlier outputs).
- Regression: `tests/unit/test_research_proxies.py` passes (strengthened, not weakened).
