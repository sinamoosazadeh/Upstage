# SESSION V3b — Independent Verification (K-013…K-034, L-001…L-015, X-V3b-001)

**Baseline:** `85b2c155d7b054a468379ddfd802eb239d0801f9` (verified with `git rev-parse HEAD`;
`git log -1 --oneline` = `85b2c15 Merge pull request #25 from sinamoosazadeh/arena/01a0d98b-upstage`).
All source line numbers are against this commit.

**Inputs:** full audit report `AUDIT/APEX_GEN5_AUDIT.md` @ `690e2d8899319a7c7a96456f92c3008878e59346`
(fetched to `/tmp/AUDIT.md`), index `AUDIT/APEX_GEN5_AUDIT_INDEX.md` @ same commit.
Session V3 (`AUDIT/VERIFY_V3.md` @ `6a7efb66d7b3e006b17efeb2586cb822ceb1a7d8`) verified
K-001…K-012; those rows are **not** re-verified here and its method (real repository code,
temporary/in-memory SQLite with the repository's own DDL, explicit synthetic-vs-device
boundary) is continued unchanged.

**Read-only discipline:** no repository source, config, test or document file was modified;
no pull request, no `main`, no order, no exchange/Telegram endpoint, no secret, no `.env`,
no `data/`. The only files added are under `AUDIT/`. Probe databases are written to `/tmp`.

**Environment:** `python3 -m pip install --break-system-packages -q -r requirements.lock pytest`
(numpy 1.26.0), SQLite 3.40.1, tests run as `python3 -m pytest -q -p no:cacheprovider <path>`.

**Synthetic boundary (applies to every row):** every reproduction below uses synthetic data
and a synthetic SQLite database built with the repository's own DDL and its own write
methods. Synthetic success is never proof about the owner's device database, and synthetic
failure proves the code path, not that it has already damaged a device record.

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---:|---:|---|---|---|
| X-V3b-001 | CONFIRMED (new finding, = ISSUE-079 + beyond) | New | S1 | No — producer is non-frozen | ISSUE-079, ISSUE-076 | A+B — PK-preserving join rewrite now, input-scoped fingerprint next |
| K-013 | CONFIRMED | S2 | S2 | Yes — `apex/data_catalog/**` is frozen | — | A — identity computed in the non-frozen producer/adapter layer and bound to the cache key |
| K-014 | CONFIRMED | S2 | S2 | Yes — parser, store and contracts are frozen | — | A — validate at the non-frozen ingest hop (`ingest_observations`) with named quarantine |
| K-015 | CONFIRMED | S1 | S1 | Source is non-frozen (`apex/ops/bootstrap_service.py`); the runner `apex/research/bootstrap.py` is frozen | — | A — distinguish a repeat-stop from a real exhaustion and refuse COMPLETE without an earliest-retained witness |
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

---

## X-V3b-001 — `_input_fingerprint`/`window()` join defeats the raw-store primary key (= ISSUE-079, with new measured scope)

#### Auditor claim (short quote)
Not an audit row. Owner item ISSUE-079: “`EngineContextProducer._input_fingerprint()` reads,
per cell, ALL `market_observation` rows of the symbol across all timeframes JOINed to
`raw_observation` ON `m.observation_id='obs-'||r.event_id` (the expression prevents use of
`raw_observation`'s primary-key index, so SQLite chose SEARCH m + full SCAN r per row), plus
ALL `snapshot_pit` facts and the whole ledger, then hashes them; on the real device (~1.2M
rows) one cell did not finish in 7 hours. The same join shape exists in `window()`.”

#### What I read (files, line ranges, functions, callers)
`apex/ops/engine_context.py`: `_input_fingerprint` (1775–1797), `prepare` (1798–1830),
`get_bridge_context` (1831–1842), `_compose_bridge_context` (1843–2028), `quality_window`
(2030–2094), `mtf_inputs` (2095–2124), `paper_marks` (2125–2141), `adv_input` (2142–2162),
`ladder_input` (2163–2185), `paper_account_inputs` (2186–2282), `prepare_engine_bundle`
(2283–2336), `decision_inputs` (2337–2352), `_raw_content_hash` (2353–2366), `window`
(2367–2406), `training_dep_window` (2407–2419), `append_context_fact`/`read_context_fact`
(3544–3582), `paper_package_binding` (976–1010), `load_classifier`/`validate_classifier`
(527–601), `CELL_QUERY`/`TRAINING_QUERY` (1713–1727).
DDL: `apex/data_catalog/store/sqlite_store.py` — `CH4_DDL` (44–199: `market_observation`
PRIMARY KEY `observation_id` **and no other index**; `snapshot_pit` PRIMARY KEY
`snapshot_id` only; `ledger` PRIMARY KEY `ledger_id` only), `CH5_DDL` (207–237:
`raw_observation` PRIMARY KEY `event_id`, UNIQUE `content_hash`, one index
`idx_raw_sym_tf_asof(symbol,timeframe,as_of)`), `AI5_DDL` (245–288), triggers (289–312),
`ingest_raw` (383–446, builds `obs_id = "obs-" + event_id` at 387), `get_window` (498–521),
`insert_snapshot` (556–575).
`apex/ledger/store.py`: `LEDGER_COLUMNS` (93–97), `append` (362–423), `read_ledger`
(492–500), `trade_plans` (514–524) — the `ledger` table has no index on `timestamp`.
Callers (`grep -rn`): `prepare(` is called from `apex/ops/paper_loop.py` (per due cell, per
cycle) and from `get_bridge_context`; `window(` is called from `quality_window`,
`adv_input`, `prepare_engine_bundle`, `training_dep_window`; `_input_fingerprint` is called
only from `prepare`.

#### Reproduction (command, probe file, actual result)
Probes: `AUDIT/probes_V3b/X-V3b-001.py` (+ `.out`) and `AUDIT/probes_V3b/X-V3b-001b.py`
(+ `.out`).
Commands:
`python3 -B AUDIT/probes_V3b/X-V3b-001.py /tmp/v3b_big.db build|plans|timings|producer`
and `python3 -B AUDIT/probes_V3b/X-V3b-001b.py /tmp/v3b_big.db`.
Database: built with the **real** `SQLiteStore.open()` migrations and the **real**
`SQLiteStore.ingest_raw` / `insert_snapshot` / `LedgerWriter.append` (commit deferred in
bulk only): 200,000 `market_observation` + 200,000 `raw_observation` rows (2 symbols × 5
timeframes × 20,000 bars), 300,000 `snapshot_pit` rows, 2,000 ledger rows, 268 MB.

EXPLAIN QUERY PLAN, four index/statistics states (device indexes = the two manual indexes
named in ISSUE-076):

* **A — no device indexes, no ANALYZE:** `FP_RAW` → `SCAN r` + `SEARCH m USING INDEX
  sqlite_autoindex_market_observation_1 (observation_id=?)`; `WIN_META` → `SCAN r` +
  `SEARCH m` by PK.
* **B — no device indexes, after ANALYZE:** identical to A.
* **C — device indexes, no ANALYZE (the device configuration):** `FP_RAW` →
  **`SEARCH m USING INDEX idx_mo_sym_tf_open (symbol=?)` + `SCAN r`**; `WIN_META` →
  **`SEARCH m USING INDEX idx_mo_sym_tf_open (…open_time>? AND open_time<?)` + `SCAN r`**.
* **D — device indexes, after ANALYZE:** `FP_RAW` reverts to `SCAN r` + PK `SEARCH m`.
* The rewrite `ON r.event_id = substr(m.observation_id, 5)` yields
  `SEARCH r USING INDEX sqlite_autoindex_raw_observation_1 (event_id=?)` in **all four**
  states — i.e. it always uses `raw_observation`'s primary key, which the current
  `'obs-'||r.event_id` expression can never do.

Measured wall time (120 s budget per query, progress-handler abort):

| query | A | B | C (device-like) | D |
|---|---|---|---|---|
| `FP_RAW` (fingerprint join) | 25,753 rows / 0.096 s | 0.096 s | **1,332 of 25,753 rows in 120 s — ABORTED** | 0.224 s |
| `FP_RAW` rewrite | 0.117 s | 0.208 s | **0.108 s** | 0.317 s |
| `WIN_META` (window join, 334 rows) | 0.121 s | 0.230 s | **13.977 s** | 0.272 s |
| `WIN_META` rewrite | 0.029 s | 0.053 s | **0.002 s** | 0.002 s |
| `FP_FACTS` (100,000 rows) | 0.124 s | 0.203 s | 0.127 s | 0.285 s |
| `FP_PRIOR` (10,000 rows) | 0.055 s | 0.125 s | 0.018 s | 0.035 s |
| `FP_LEDGER` | `SCAN ledger` in every state | | | |

Real repository calls (`phase=producer`): `EngineContextProducer.window("BTCUSDT","1h",…,300)`
returned 299 observations in **0.208 s (A) / 0.168 s (B) / 12.407 s (C) / 0.138 s (D)**;
`_input_fingerprint` completed in **1.266 s (A) / 1.215 s (B) / 1.137 s (D)** and was not
run in state C because the identical `FP_RAW` plan had already failed to finish inside
1,690 s in an earlier full run of the same probe.

`X-V3b-001b.out`: the current join and the `substr` rewrite return byte-identical result
sets (100,000 rows each, `identical: True`), and 0 rows have an `observation_id` that does
not begin with `obs-`. `prepare_engine_bundle` passes `COUNT(*)` as `bars`, i.e. **20,000**
bars for BTCUSDT:1h in this database; the resulting full-history `WIN_META` took 0.167 s in
state A, 0.153 s in state D, and produced only **2,888 of 20,000 rows in 120 s (ABORTED)**
in state C.

Extrapolation (explicitly an extrapolation, not a device measurement): state C is a nested
loop of |m rows matching the predicate| × |full scan of raw_observation|. At 200k raw rows
`FP_RAW` progressed at ~11 rows/s ⇒ ~2,300 s for one cell; the device has ~1.2M rows, so the
inner scan is ~6× larger and the outer set ~6× larger ⇒ ~36× ⇒ ~23 h. This is consistent
with the owner's observation that one cell did not finish in 7 hours.

#### Verdict and reasoning
**CONFIRMED — independent severity S1.** Every element of ISSUE-079 is reproduced in
repository code: the join expression cannot use `raw_observation`'s primary key; with the
two manual device indexes present and no `ANALYZE`, SQLite chooses `SEARCH m` + full
`SCAN r`; the same join shape exists in `window()`; the fingerprint additionally reads all
`snapshot_pit` facts (100,000 rows here) and the whole `ledger` by full scan. Two elements
go **beyond** ISSUE-079 as written:
1. **`window()` is not merely “the same shape” — it is the hot path.** `prepare_engine_bundle`
   calls `window(symbol, timeframe, as_of, COUNT(*))`, i.e. the entire stored history of the
   cell, and `quality_window`/`mtf_inputs` call `window()` three more times (base,
   intermediate, HTF) plus `adv_input` once and `paper_marks` once per held symbol. One
   `prepare()` therefore issues at least six of these joins, one of which is unbounded in
   history.
2. **`ANALYZE` alone flips the plan.** State D (device indexes **plus** `sqlite_stat1`)
   restores the fast plan. The catastrophic behaviour is therefore a *statistics*
   accident, meaning it can appear or disappear on the device without any code change —
   which makes “it worked yesterday” worthless as evidence.
S1 rather than S0: PAPER boot is already blocked for other reasons (ISSUE-075), and this
defect destroys throughput and observability rather than producing a wrong order; but at
~14–83 min per cell it makes the governed cycle unreachable, so it is not S2.

#### Root cause
`ingest_raw` derives `observation_id = 'obs-' + event_id` (sqlite_store.py:387) and every
reader reconstructs the relation with the string expression `m.observation_id='obs-'||r.event_id`
instead of an indexable equality on `r.event_id`. SQLite can only use an index on the *left*
side of such a comparison for the table whose column appears bare; here both sides are
expressions from the loop-outer table's perspective, so `raw_observation` can only be
scanned. The secondary cause is scope: the fingerprint hashes the union of *all* timeframes
of the symbol, *all* non-CP14 `snapshot_pit` facts of *all* symbols, and the *entire* ledger,
although one cell reads only a small, enumerable subset of those.

#### Direct impact
`prepare()` — which `apex/ops/paper_loop.py` calls for every due cell, every cycle — can take
minutes to hours per cell on the device in the state-C configuration; the declared analysis
budget is 400 ms p95 (APEX_GEN5.md:121–146). The cache the fingerprint exists to protect is
therefore more expensive than the computation it guards.

#### Secondary effects and interactions (upstream/downstream)
Upstream: the cost grows with retained history, so it worsens monotonically as bootstrap
fills the 140-cell data scope; ISSUE-076's manual device indexes are what *trigger* the bad
plan, so the two items interact — “add indexes” made this worse, not better. Downstream:
`prepare()` blocks `paper_loop.run_cycle`; catch-up (ISSUE-077) multiplies the count of
`prepare()` calls; a timed-out or killed cycle leaves `BRIDGE_CONTEXT` unwritten, so the next
cycle repeats the full cost (no partial progress). Because the fingerprint is also the cache
**key**, any change to its scope changes every stored `BRIDGE_CONTEXT` fact's
`input_fingerprint` and forces a cold rebuild — the same invalidation surface K-003 (V3)
identified for correctness.

Exactly which inputs `_compose_bridge_context` actually reads (from the code above), i.e.
the true dependency set a correctly scoped fingerprint must cover:
* `prepare_engine_bundle` → classifier artifact file; `quality_window(symbol, tf, as_of, 300)`
  = `window()` + one `CP14_QUALITY_<observation_id>` fact per bar; `mtf_inputs` = the same for
  `tf`, `relative_mtf(tf)["intermediate"]`, `relative_mtf(tf)["htf"]`;
  `COUNT(*)` + `window(symbol, tf, as_of, COUNT(*))` (full cell history);
  `persist_complete_evidence` (writes `evidence_event`).
* `decision_inputs` → `read_family_record(FAMILY_ID)` and `read_public_venue_facts(symbol)`
  (both `snapshot_pit`).
* 48 most recent `CP14_COMPONENTS` facts for exactly `(symbol, timeframe)`; the previous
  `CP14_UNCERTAINTY` fact for `(symbol, timeframe)`.
* `paper_account_inputs` → the whole durable ledger ≤ as_of, `trade_plans()`, matching
  `outcome` rows, `paper_marks` = `quality_window(held_symbol, "1m", as_of, 1)` for every
  net-open symbol, and `read_public_venue_facts` for each such symbol.
* `ladder_input` → the last two `apex_risk_ladder_state` rows ≤ as_of.
* `adv_input` → `read_public_venue_facts(symbol)` + `window(symbol,"1h",as_of,~751)`.
* `read_public_funding_schedule(symbol, as_of)`; `load_params()`,
  `load_decision_runtime("PAPER")`, `GOVERNED_DEFAULTS`, and `paper_package_binding()` —
  the latter already hashes every governed YAML into `parameter_package_id`, so parameter
  files are covered by the `package` component of the fingerprint.
Consequently a fingerprint scoped to `symbol × {tf, intermediate, htf, 1h, 1m}` **plus**
`{held symbols} × {1m}` (held symbols are themselves derived from the ledger, which is
fingerprinted), plus `snapshot_pit` rows whose `symbol_scope` is in that symbol set, plus the
ladder, package and classifier, covers every input actually read — without weakening the
guarantee, because any input outside that set cannot reach the produced context.

#### Contract and decisions
APEX_GEN5.md:121–146 “Latency Budget (p95, DECLARED DESIGN TARGET — UNVERIFIED MEASUREMENT)”:
Budget 1 total **400 ms**, with the explicit caveat that the numbers are targets, not
measurements, and APEX_GEN5.md:19130 `T-NFR-001` “Analysis latency p95 < 400 ms on target
device”, gate `G-CAPACITY-001` (19252) still **OPEN/UNVERIFIED**. `PHASE2_DECISION_LOG.md`
contains no decision that suspends the analysis budget or authorises unbounded per-cell
reads. Owner items ISSUE-079 (this defect) and ISSUE-076 (the manual device indexes) govern;
ISSUE-079 has precedence over any contract prose about cache design because it is the later
owner statement of the problem.

#### Frozen status and non-frozen alternative
`apex/ops/engine_context.py` is **not** frozen (it is the producer/bridge layer); both the
join rewrite and the fingerprint scoping live there. The DDL in
`apex/data_catalog/store/sqlite_store.py` **is** frozen — so adding a persistent index or a
generated column to `market_observation`/`raw_observation` through `MIGRATIONS` requires an
owner ruling. No frozen file needs to change for options A or B below.

#### Fix options (A/B/C… each with side effects)
* **A — rewrite both joins to `ON r.event_id = substr(m.observation_id, 5)`** (producer
  only). Proven row-equivalent here (`identical: True`, and no `observation_id` lacks the
  `obs-` prefix). Side effects: none on identity/hashes (the rows returned are the same, so
  the fingerprint value is unchanged and no cached context is invalidated); no migration, no
  retraining; it removes the dependency on `ANALYZE`. Residual risk: if a future writer ever
  produced an `observation_id` not of the form `obs-<event_id>`, the rewrite could match a
  different row where the current form would match none — mitigate with the existing
  `raw_payload_hash`/`content_hash` check already present in `window()` (2395–2399) and an
  explicit `AND m.observation_id = 'obs-' || r.event_id` retained as a redundant filter.
* **B — scope the fingerprint to the enumerated dependency set** (producer only), using the
  input list above and aggregate hashing per scope instead of row-by-row hashing of 136k
  rows. Side effects: **every stored `BRIDGE_CONTEXT` fingerprint changes**, so the first
  run after deployment rebuilds every cached context (cold, not wrong); `tests/unit/
  test_engine_context*.py` assertions that pin fingerprint stability across unrelated
  inserts would need re-baselining; it must be paired with A or the scoped query still uses
  a bad plan.
* **C — run `ANALYZE` at boot (or `PRAGMA optimize` on close)**. Cheapest, no semantic
  change, and state D shows it restores the good plan. Side effect: it is a *mitigation*,
  not a fix — `sqlite_stat1` drifts as the database grows and can re-flip the plan; it also
  writes to the database at boot, which interacts with ISSUE-077 (boot self-test before
  ladder migrations) and with the disk-floor PAUSE of D57.
* **D — owner-approved index on `raw_observation` matching the expression** (frozen file;
  e.g. a `CREATE INDEX … ON market_observation(raw_payload_hash)` or a stored generated
  column). Side effects: frozen-DDL change, migration on the device, larger database, and it
  still leaves the unbounded scope of B.

#### My recommendation
**A now, B next, C as an interim operational mitigation.** A is semantics-preserving, proven
equivalent, touches no frozen file, invalidates no cache, and alone converts 12.4 s →
0.002 s on the window path and an unfinished query → 0.108 s on the fingerprint path. B is
the real fix for the fingerprint's cost and should be scheduled with the cold-rebuild
acknowledged. D should not be taken before A and B are measured on the device.

#### Acceptance and regression tests
1. A parity test asserting the rewritten join returns exactly the same rows as
   `'obs-'||r.event_id` over a store populated by `ingest_raw`, including a `correct_raw`
   chain (SUPERSEDED + CORRECTED rows present).
2. An `EXPLAIN QUERY PLAN` assertion test that both joins report
   `SEARCH r USING INDEX sqlite_autoindex_raw_observation_1` in all four index/statistics
   states (no device index/ANALYZE, index only, ANALYZE only, both).
3. A budget test: with ≥200k `market_observation` rows, `prepare()` for one cell completes
   under an explicit wall-time ceiling, executed in the device-like state (manual indexes
   present, `sqlite_stat1` deleted).
4. A fingerprint-sensitivity test for option B: inserting a row **inside** the enumerated
   dependency set changes the fingerprint; inserting one outside it (a different symbol's
   4h bar that no held position marks) does not — and the produced context is byte-identical
   in the second case.
5. Device evidence still needed (read-only): `sqlite3 <device.db> "EXPLAIN QUERY PLAN <FP_RAW>"`
   and `SELECT * FROM sqlite_stat1 WHERE tbl IN ('market_observation','raw_observation');`
   to confirm which of states C/D the device is actually in.

---

## K-013 — `Catalog.get` returns `snapshot_id=None` on every branch

#### Auditor claim (short quote)
> «هر شاخهٔ `Catalog.get`، از OK تا cache hit، `snapshot_id=None` می‌دهد؛ با وجود قرارداد feature که SHA-256 قطعی snapshot و dependency را لازم می‌داند.»
> — “Every branch of `Catalog.get`, from OK to cache hit, yields `snapshot_id=None`, although the feature contract requires a deterministic SHA-256 snapshot and dependency identity.”

#### What I read (files, line ranges, functions, callers)
`apex/data_catalog/catalog.py` read completely (395 lines): `FeatureRegistry`/`build_registry`
(79–229, incl. the declared `outputs=(…, "snapshot_id", …)` tuples at 126 and 179),
`Catalog.__init__`/`set_provider`/`set_code_revision` (236–255), `verify_completeness`
(258–288), **`Catalog.get` (290–379)** and `_feature_params` (381–392).
All six `CatalogResult(...)` constructions inside `get` are at lines 300, 308, 320, 328, 351
and 375, and the probe's source scan shows `snapshot_id=None` hard-coded at
catalog.py:303, 311, 324, 332, 356, 378 — i.e. the unregistered-feature branch, the
no-provider branch, the two PIT/format INVALID branches, the `TIER_CACHE_HIT` branch and
the normal computed-result branch. There is no other `snapshot_id` assignment in the file.
`apex/data_catalog/contracts.py:415–426` — `CatalogResult` is a frozen dataclass whose
`snapshot_id` is `Optional[str]`, so `None` is structurally admissible.
Callers (`grep -rn "catalog.get\|\.feature(" --include='*.py' apex scripts`): the only
production consumer path is `AnalystEngine.feature()` in the **frozen**
`apex/engines/base.py:157–167`, which forwards `CatalogResult` unchanged; no engine in
`apex/` currently calls `self.feature()` (the runtime path composes features natively in
`apex/ops/engine_context.py`). So today the missing identity is consumed by nobody — which
is exactly the auditor's own “اثر مشروط به مصرف L00” caveat.

#### Reproduction (command, probe file, actual result)
Command: `python3 -B AUDIT/probes_V3b/K-013.py`; probe `AUDIT/probes_V3b/K-013.py`, raw
output `AUDIT/probes_V3b/K-013.out`. With a real `SQLiteStore` (repository migrations,
120 real `ingest_raw` bars) attached as the window provider and the real `Catalog`:
`body_ratio` → `status=OK reason='' value=0.250000 snapshot_id=None`; `sweep` first call →
`OK/NO_SWEEP_IN_BLOCK snapshot_id=None`; `sweep` second call → `OK/TIER_CACHE_HIT
snapshot_id=None`; `volatility_regime` → `UNAVAILABLE snapshot_id=None`;
`UNREGISTERED_FEATURE_ID`, `PIT_FUTURE_AS_OF`, `NO_WINDOW_PROVIDER`,
`INVALID_AS_OF_FORMAT` → all `snapshot_id=None`. `verify_completeness()` passes
(`count=74, ATOM=44, MOLE=1, ORGN=29`), so this is not a registry defect.
`python3 -m pytest -q -p no:cacheprovider tests/unit/test_catalog.py` → **23 passed**; no
existing test asserts a non-None `snapshot_id`, which is why the gap survives the suite.

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). The claim is exact: all six
branches, including `TIER_CACHE_HIT`, return `None`. The auditor's qualifier that the
producer's own snapshot computation “is not a substitute for this API” is also correct —
`EngineContextProducer` computes identities for its own facts, not for `CatalogResult`.
S2, not S1: no production caller consumes `CatalogResult.snapshot_id` today, so no decision,
order or ledger row can currently be built on the missing identity; the damage is to
traceability and to any future L00 consumer.

#### Root cause
`Catalog.get` was implemented as a value/quality reader; the identity field declared in the
registry's `outputs` tuples (catalog.py:126,179) and in the Ch.5 result shape was never
computed. The tier cache (`apex/data_catalog/performance/__init__.py`) stores only
`(value, q)` keyed by `(alias, symbol, timeframe)` + bar index, so even if an identity were
computed it would not be cached with the value, and the cache-hit branch has nothing to
return.

#### Direct impact
A `CatalogResult` cannot be tied to the exact raw snapshot, parameters and code revision
that produced it; two structurally identical results from different inputs are
indistinguishable, and a cache hit is indistinguishable from a fresh computation.

#### Secondary effects and interactions (upstream/downstream)
Upstream this depends on K-011 (V3, CONFIRMED): the window the catalog reads is not itself
PIT-selected per raw availability, so an identity computed today would attest to a possibly
non-PIT input. Downstream, if an engine ever switches to `self.feature()`, evidence lineage,
dedup and cross-engine reuse would inherit a null identity; K-012 (V3, CONFIRMED) already
shows the shared `TierCache` is not bound to input identity, so the cache-hit branch is the
most dangerous of the six. Nothing here affects orders, risk or the ledger today.

#### Contract and decisions
APEX_GEN5.md:13709–13715 (feature 01 template, identical in every feature block):
“**Outputs:** body_ratio_t + Q_formula_valid + **snapshot_id deterministic SHA-256 identity**
+ validity 1 + confidence 1.0 + dependency [O,H,L,C,V,ATR]”, and “Tests: … determinism
Same input -> identical SHA256”. `apex/data_catalog/catalog.py:15–17` restates the Ch.5
result shape including `snapshot_id`. `PHASE2_DECISION_LOG.md` contains no decision
suspending feature identity; no owner item covers it. Precedence: the contract clause
stands unmodified.

#### Frozen status and non-frozen alternative
**Frozen** — `apex/data_catalog/**` is in the frozen set, so `catalog.py` may not be edited
without an owner ruling. Non-frozen alternative: compute the identity in a producer/adapter
layer (`apex/ops/engine_context.py` or a thin wrapper around `Catalog.get`) from the same
canonical inputs the contract names (raw lineage ids + parameter package id + code revision
+ feature id/lookback), returning an enriched result object; the frozen `Catalog` stays
untouched. This only works if the wrapper also owns the cache decision, because the frozen
`TierCache` hit path cannot be made identity-aware from outside.

#### Fix options (A/B/C…)
* **A (non-frozen, recommended)** — an adapter in the producer layer that calls
  `Catalog.get`, computes the canonical SHA-256 over `(feature_id, symbol, timeframe,
  as_of, raw observation ids + content hashes, feature params, parameter_package_id,
  code_revision)` and returns it alongside the value, **bypassing** the frozen tier cache
  (as recommended for K-012) or keying its own cache by that identity. Side effects: no
  frozen file changes; a second cache layer must be memory-bounded (see C-003); no test
  currently asserts `snapshot_id`, so nothing breaks; no DB migration, no retraining.
* **B (frozen, owner ruling needed)** — compute `snapshot_id` inside `Catalog.get` and
  store `(value, q, snapshot_id)` in `TierCache`. Side effects: edits two frozen files
  (`catalog.py`, `performance/__init__.py`); every cached tuple shape changes; the 23
  `tests/unit/test_catalog.py` tests must be extended; no DB migration, but any future
  persisted `CatalogResult` identity becomes a new hash surface that must be versioned.
* **C** — document the field as permanently unused and remove it from the Ch.5 result
  shape. Requires an owner contract amendment; contradicts the per-feature “Outputs”
  clause in ~74 places, so it is not a documentation-only change.

#### My recommendation
**A**, and only if/when an L00 consumer is actually wired. Until then this stays a real but
dormant contract gap; spending a frozen-file ruling (B) on a path with no consumer is not
justified, while A can be added together with the K-011/K-012 producer-side PIT reader that
is needed anyway.

#### Acceptance and regression tests
1. Two calls with identical inputs return the same 64-hex identity; changing any raw row,
   feature parameter, parameter package or code revision changes it (the contract's
   “determinism / Same input -> identical SHA256” test).
2. A cache-hit result carries the same valid identity as the computing call — and a cache
   hit whose underlying window changed must **not** return the old identity (ties into
   K-012).
3. All four refusal branches (`UNREGISTERED_FEATURE_ID`, `NO_WINDOW_PROVIDER`,
   `PIT_FUTURE_AS_OF`, `INVALID_AS_OF_FORMAT`) keep `snapshot_id=None` and stay refusals —
   an identity must never be minted for a refusal.
4. Regression: `tests/unit/test_catalog.py` (23 tests) must still pass unchanged under
   option A, proving the frozen surface was not altered.

---

## K-014 — negative volume is stored: the ingest boundary never calls the contract validator

#### Auditor claim (short quote)
> «parser حجم منفی را Decimal می‌کند؛ hygiene فقط هندسهٔ OHLC را می‌سنجد و `ingest_raw`، validator اصلی را فراخوانی نمی‌کند. نمونهٔ OHLC سالم با volume=−۱ از gate گذشت و در هر دو جدول raw/market … ذخیره شد، درحالی‌که `validate_market_observation` همان ورودی را `QX_INVALID` رد می‌کند.»
> — “The parser turns a negative volume into a Decimal; hygiene judges only OHLC geometry and `ingest_raw` does not call the real validator. A healthy-OHLC sample with volume=−1 passed the gate and was stored in both raw/market tables, while `validate_market_observation` rejects the same input as `QX_INVALID`.”

#### What I read (files, line ranges, functions, callers)
`apex/data_catalog/ingest/toobit_public.py:122–170` — `parse_kline_to_observation` in full:
`_dec()` accepts any `Decimal`-parsable string including `-1`; the only rejections are
non-decimal fields, short rows, unexpected row types and bad timestamps.
`apex/ops/bootstrap_service.py:110–178` — `_OHLC_NAMES`, `_decimal_or_none`,
`_kline_ohlc_fields`, `_ohlc_violation`; the docstring is explicit: “Only OHLC is judged —
volume/quote-volume/trade-count fields are **NEVER** a drop reason.”
`apex/ops/bootstrap_service.py:686–711` — the `_walk_backward` hygiene gate, described in
the source as “**THE single boundary into the history**”, which calls `_ohlc_violation` and
nothing else. `apex/ops/bootstrap_service.py:1042–1070` — `ingest_observations`: checks only
`symbol`/`timeframe` identity and then calls `store.ingest_raw` per row.
`apex/data_catalog/store/sqlite_store.py:383–446` — `ingest_raw`: Core-10 and TF membership
checks, OI-state handling, hashes, two INSERTs; **no call to any validator**; the
`market_observation` row is written with `quality_state='Q0'` unconditionally (line 444).
`apex/data_catalog/contracts.py:185–242` — `validate_market_observation`, step 4:
`if obs.volume < 0: raise ValidationError("QX_INVALID", "negative volume")` and
`if obs.volume == 0 and obs.status != "OPEN": raise ValidationError("E-Q-001", …)`.
Consumers of the validator (`grep -rn validate_market_observation --include='*.py' apex`):
only `apex/ops/engine_context.py:3586–3598` (`quality_flags_for_observation`, D52 mapping),
used at 3730 and 3802 — i.e. at *quality publication*, downstream of storage.
`apex/quality/vector.py:74–112` — `calc_quality_vector` does implement the hard gate
`if obs.volume < 0: return None, "QUARANTINED_VOLUME_NEG", "QX"`, again downstream.

#### Reproduction (command, probe file, actual result)
Command: `python3 -B AUDIT/probes_V3b/K-014.py`; probe `AUDIT/probes_V3b/K-014.py`,
output `AUDIT/probes_V3b/K-014.out`. Real parser, real hygiene gate, real
`ingest_observations` → real `SQLiteStore.ingest_raw` on a temporary DB:
* volume `-1`: parser → `Decimal('-1')`, `_ohlc_violation` → `None`,
  `validate_market_observation` → `ValidationError QX_INVALID: negative volume`;
* volume `0`, status CLOSED: `_ohlc_violation` → `None`, validator →
  `ValidationError E-Q-001: zero volume only permitted for OPEN status`;
* `ingest_observations` returned `{'rows': 3, 'inserted': 3, 'duplicates': 0, …}` and both
  tables hold all three rows:
  `market_observation … volume='-1' candle_status=CLOSED quality_state=Q0` and
  `raw_observation … volume='-1' status=CLOSED`.
So the invalid row is persisted **and labelled Q0**, and because `raw_observation` is
immutable by trigger it cannot be deleted except by the governed retention purge.

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). Every element reproduces on
real code. Severity stays S2 rather than S1 because the quality plane does still quarantine
the observation before it can influence a decision (`calc_quality_vector` →
`QUARANTINED_VOLUME_NEG`, QX), so the failure is “poisoned durable history + false Q0 label
+ late refusal”, not “bad number reaches risk”. It is not S3 because the row is permanent:
the immutability trigger means a wrong row can only be purged by the retention path.

#### Root cause
Validation was placed on the *read/quality* side (D52 mapping in the producer) instead of at
the *write* boundary. The CP-12 hygiene gate deliberately restricts itself to the OHLC law
(so that the frozen DDL CHECK is never hit), and `ingest_raw` trusts its caller. No component
between “venue bytes” and “durable row” applies `validate_market_observation`.

#### Direct impact
A CLOSED row with volume < 0 (or = 0) becomes permanent history with `quality_state='Q0'`,
i.e. the stored label asserts the highest raw-quality class for a row the contract calls QX.

#### Secondary effects and interactions (upstream/downstream)
Upstream: the venue is the only source of the value, and the frozen parser will not reject
it. Downstream: VWAP/VolumeZ/OBV-type features, ADV (`adv_input` sums `float(obs.volume)`
directly, engine_context.py:2157) and any training sample built from this cell consume the
value before the quality plane's verdict is consulted, and `adv_input` performs **no**
quality check at all — a negative volume therefore reduces measured ADV and, through
`forecast_cost_projection`, the cost estimate. Interacts with K-013 (no feature identity to
trace the poisoned input) and with the V3-confirmed K-001 (a later correction of the same
bar may be silently deduplicated). No owner D/ISSUE covers ingest-side validation.

#### Contract and decisions
APEX_GEN5.md:618–632 (`calc_quality_vector`, the 13 hard gates):
`if MarketObservation.V < 0: return None, "QUARANTINED_VOLUME_NEG", "QX"` — a **quarantine**,
which in §2.1 (“a veto or a failed hard gate quarantines the observation OUTRIGHT (QX
INVALID)”) is not a storage-with-Q0 outcome. Note a genuine contract tension the auditor did
not state: APEX_GEN5.md:487 defines `Q_volume` as “`0.5` if `V==0` (**degraded, not
invalid**)”, whereas `contracts.validate_market_observation` treats zero volume on a CLOSED
bar as `E-Q-001`. The auditor's acceptance criterion “closed zero → named rejection”
therefore conflicts with line 487; only the **negative** case is unambiguous.
`PHASE2_DECISION_LOG.md` has no decision moving validation to the read side.

#### Frozen status and non-frozen alternative
**Frozen**: `apex/data_catalog/ingest/toobit_public.py`, `apex/data_catalog/contracts.py` and
`apex/data_catalog/store/sqlite_store.py` are all inside `apex/data_catalog/**`.
Non-frozen alternative: `apex/ops/bootstrap_service.py` (`_walk_backward`'s hygiene gate and
`ingest_observations`) is **not** frozen and is already “THE single boundary into the
history”; the validator can be invoked there, with the existing `_record_invalid_bar`
evidence mechanism supplying the named drop reason.

#### Fix options (A/B/C…)
* **A (non-frozen, recommended)** — call `validate_market_observation` in
  `ingest_observations` (and/or extend the `_ohlc_violation` gate with a
  `REASON_VOLUME_NEGATIVE`), dropping with the existing named-evidence path. Side effects:
  bars that the venue really reports with negative volume become drops instead of rows, so
  coverage counts change and K-017's drop-evidence durability problem becomes more visible;
  `tests/unit/test_ops_bootstrap_service.py` cases that ingest arbitrary synthetic volumes
  may need adjustment; no frozen file, no migration, no hash change (the dropped row never
  existed).
* **B (frozen, owner ruling)** — validate inside `ingest_raw`. Side effects: touches a frozen
  file; **every** writer (including `correct_raw` and the repair path) inherits the refusal,
  which is the strongest guarantee but can turn an existing device write path into a hard
  failure mid-bootstrap; `tests/integration/test_store_integration.py` would need new cases.
* **C** — leave storage as is and make the quality plane's QX authoritative everywhere
  (i.e. forbid any consumer from reading `market_observation.volume` without the quality
  record). Side effects: `adv_input` and any direct reader must be rewritten; the false
  `quality_state='Q0'` column stays wrong; does not stop the row becoming permanent history.

#### My recommendation
**A**, restricted to the unambiguous negative-volume (and non-finite) cases, with the
zero-volume-on-CLOSED question referred to the owner because APEX_GEN5.md:487 and
`contracts.py` step 4 disagree. Option B is the more complete guarantee but should wait for
an owner ruling on the frozen boundary and on the zero-volume conflict.

#### Acceptance and regression tests
1. `volume < 0` on a CLOSED bar is dropped with a named reason **before** any INSERT; both
   tables stay empty and the drop is recorded as evidence.
2. A healthy bar (`volume=12.5`) and a bar with absent OI are ingested exactly as today
   (no behaviour change) — regression against `tests/integration/test_store_integration.py`.
3. `quality_state` written by `ingest_raw` is never `Q0` for a row the quality plane
   quarantines — or, under option A, such a row can no longer exist.
4. Owner-decision test once the zero-volume conflict is resolved: either `V==0` on CLOSED is
   a drop (contracts.py behaviour) or it is stored with `Q_volume=0.5` (APEX_GEN5.md:487) —
   the test must pin whichever the owner chooses, in both `contracts.py` and the gate.

---

## K-015 — a venue stuck on its retained tail completes the cell as if the history were exhausted

#### Auditor claim (short quote)
> «وقتی venue پنجرهٔ قبلی را تکرار کند یا endTime را نادیده بگیرد، `_walk_backward` با repeated-first/no-new/no-progress **عادی** برمی‌گردد، نه با خطای پوشش؛ منبع سپس empty-page و checkpoint COMPLETE می‌دهد. نمونهٔ چهار کندل موجود با StickyTail خود تست: فقط دو کندل جدید تحویل و دو کندل قدیمی گم شدند.»
> — “When the venue repeats the previous window or ignores endTime, `_walk_backward` returns **normally** on repeated-first/no-new/no-progress, not with a coverage error; the source then emits an empty page and the checkpoint becomes COMPLETE. With the test's own StickyTail and four available candles only two were delivered and two old candles were lost.”

#### What I read (files, line ranges, functions, callers)
`apex/ops/bootstrap_service.py:647–711` — `_walk_backward` in full. Its four exits are all
plain `break` statements returning `collected`: `if not page: break` (679), the dedup stop
`if prev_first_ms is not None and first_ms == prev_first_ms: break` (682–683), `if not
new_any: break` (707–708) and the no-progress stop `if next_end >= walk_end: break`
(711–712). None of them records a reason, raises, or marks the cell inconclusive.
`apex/ops/bootstrap_service.py:538–645` — `ToobitKlineSource.__call__`: the walk result is
cached in `self._history[key]`, filtered by frontier/served_upto/close-time, and
**line 622–632**: `if not chunk: self._queue_cell_complete(...); return {"rows": [], …,
"code": None}`. The source comment itself calls this “the ONLY completion signal”.
`apex/ops/bootstrap_service.py:742–764` — `_queue_cell_complete` only formats a print line
(`dropped=`, `open_excluded=`); it asserts nothing about coverage.
`apex/research/bootstrap.py:265–321` (frozen) — the phase-1 loop: `while cursor < end`,
ingest, advance cursor; and at 308–315
`verification = {"verified": True, "reason": "PHASE1_PAGE_WALK_DONE"}`; only if
`self.phase1_verifier is not None` is that overridden; `status = "COMPLETE" if
verification.get("verified") else "SKIPPED"`, then `save_bootstrap(..., status=status)`.
`grep -rn phase1_verifier --include='*.py' apex scripts tests` → constructor/attribute in
`apex/research/bootstrap.py:167,176`, the call at 309–310, and **exactly one** user:
`tests/unit/test_research_bootstrap.py:217`. No production code ever supplies a verifier, so
the default `verified: True` always applies.
`tests/unit/test_ops_bootstrap_service.py:372–405` — `test_dedup_stop_on_repeated_first_row`
asserts `opens == sticky.series[-2:]`, i.e. the test **pins** the loss of the two older bars
as correct behaviour, exactly as the auditor says.

#### Reproduction (command, probe file, actual result)
Command: `python3 -B AUDIT/probes_V3b/K-015.py`; probe `AUDIT/probes_V3b/K-015.py`, output
`AUDIT/probes_V3b/K-015.out`. Real `ToobitKlineSource` + real `ingest_observations` + real
`SQLiteStore`, driven with two venue doubles that retain the **same four bars**:
* **A — StickyTail** (ignores `endTime`, always answers with its newest two bars):
  bars served `[1726441200000, 1726444800000]`, durably stored `2`,
  **missing `[1726434000000, 1726437600000]`**, page 2 is an EMPTY page with `code=None`,
  and “source reported an error/refusal at any point: **no**”.
* **B — HonestVenue** (same four bars, `endTime` honoured): bars served = all four, stored
  `4`, missing `[]`, and the run ends with the **identical** empty page / `code=None`.
The two cases are indistinguishable from the runner's side; with the default
`verified: True` the checkpoint for case A becomes `COMPLETE` with half the history absent.

#### Verdict and reasoning
**CONFIRMED — independent severity S1** (auditor S1 retained). The claim is exact in all
three parts: the walk stops silently, the empty page is the only completion signal, and the
existing test blesses the lossy outcome. S1 because the durable record of a cell is declared
complete while it is not, and no downstream consumer (training, features, coverage reporting)
can detect the difference; it is not S0 because it needs a misbehaving/limited venue and
does not by itself place an order.

#### Root cause
Two different facts — “the venue has no more history” and “the venue stopped giving me new
history” — are mapped onto the same signal (an empty page), and the phase-1 completion
predicate defaults to `True` with no coverage witness. The walk's stop conditions were
designed to prevent an infinite loop (a correct goal) but the loop-guard verdict was reused
as an exhaustion verdict.

#### Direct impact
`bootstrap_progress.status = COMPLETE` for a cell whose earliest bars were never fetched,
with no recorded reason, no `last_end`/`first_seen` evidence and no retry strategy.

#### Secondary effects and interactions (upstream/downstream)
Upstream: rate-limit handling (C-012) and the `_catch_up_floor` shape the walk window;
a partially-served page interacts with K-016's `_served_upto` high-water mark, because
`_served_upto` advances on delivery while coverage was never proven. Downstream: the 20-cell
D30 training scope and the 140-cell data scope are both computed from these checkpoints, so
E11 training, feature history, ADV and any backtest silently use a truncated history; and
because the gap is at the **old** end, the damage is invisible to freshness checks. No owner
D/ISSUE covers venue-repeat detection (ISSUE-076/077 concern indexes, commits and boot
ordering, not coverage).

#### Contract and decisions
APEX_GEN5.md:17276 (Phase 1, normative): “for each of 140 cells, page `GET /quote/v1/klines`
limit=1000 **from `2020-01-01T00:00:00Z` to now**; insert closed bars into `raw_observation`;
checkpoint `bootstrap_progress`. Resume from cursor, never rewind Phase 1. −1003 backoff,
**do not skip**.” A cell whose 2020-onwards window was never actually reached does not
satisfy this clause, and “do not skip” is precisely what the silent stop does.
`PHASE2_DECISION_LOG.md`: D30 fixes the *training* scope to 20 base cells and explicitly
keeps the data scope separate; no decision authorises declaring a cell complete without a
coverage witness. Precedence: the contract clause stands; D30 does not weaken it.

#### Frozen status and non-frozen alternative
Mixed. `apex/ops/bootstrap_service.py` (the walk, the serve boundary, `_queue_cell_complete`)
is **not** frozen. `apex/research/bootstrap.py` (the runner that turns the empty page into
`COMPLETE`) **is** frozen — but it already exposes the non-frozen seam
`phase1_verifier`, which the service can supply without touching the frozen file. That is
the clean alternative: the service passes a verifier that refuses `COMPLETE` unless the walk
recorded a genuine exhaustion.

#### Fix options (A/B/C…)
* **A (non-frozen, recommended)** — record the walk's stop reason per cell
  (`EMPTY_PAGE` / `REPEATED_FIRST_ROW` / `NO_NEW_ROWS` / `NO_BACKWARD_PROGRESS`) together
  with `last_end`, `first_seen` and the oldest collected open time, expose it through the
  page dict, and have the service install a `phase1_verifier` that returns
  `verified=False` (→ `SKIPPED`, i.e. not complete) for any stop that is not a true
  exhaustion, or that cannot show an earliest-retained witness. Side effects: cells against
  limited venues stop reporting COMPLETE, so the operator-visible 140-cell progress number
  will fall — that is the point, but it changes every coverage report; a retry/backoff policy
  must be defined or cells will retry forever (interacts with C-012);
  `tests/unit/test_ops_bootstrap_service.py:372–405` must be **rewritten**, because it
  currently asserts the lossy behaviour is correct.
* **B (frozen, owner ruling)** — make `apex/research/bootstrap.py` require an explicit
  coverage proof instead of defaulting to `verified: True`. Side effects: frozen-file change;
  every existing runner caller (including tests that rely on the default) changes behaviour;
  strictly stronger than A but not needed, since the `phase1_verifier` seam already exists.
* **C** — treat the repeated-window case as a rate-limit-style retryable condition inside the
  walk (retry with a stepped-back `endTime` before giving up). Side effects: more venue calls
  and longer bootstraps; can still not *prove* exhaustion, so it must be combined with A.

#### My recommendation
**A**, with the stop reason persisted next to the checkpoint so the operator can see *why* a
cell is not complete, plus C's one stepped-back retry as a cheap disambiguation. B should be
held back unless the owner wants the guarantee inside the frozen runner.

#### Acceptance and regression tests
1. The StickyTail venue (4 retained bars, 2-bar sticky answer) must **not** reach
   `COMPLETE`: the checkpoint records a named non-exhaustion stop and the missing opens.
2. The HonestVenue (same 4 bars, `endTime` honoured) must still reach `COMPLETE` with all
   four bars stored — the fix must not make honest exhaustion unreachable.
3. A venue that genuinely returns an empty page at the deep start still completes.
4. Regression: the existing `test_dedup_stop_on_repeated_first_row` must be re-expressed as
   “the walk stops without spinning **and** the cell is not completed”, and the
   `2 <= len(calls) <= 5` anti-spin bound must still hold.
5. Device evidence (read-only): per cell,
   `SELECT symbol,timeframe,status,cursor_open_time,bars_written FROM bootstrap_progress;`
   together with `SELECT symbol,timeframe,MIN(open_time),COUNT(*) FROM market_observation
   GROUP BY symbol,timeframe;` — a `DONE` cell whose `MIN(open_time)` is far later than
   2020-01-01 is a live instance of this defect.
