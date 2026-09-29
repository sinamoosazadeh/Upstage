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
