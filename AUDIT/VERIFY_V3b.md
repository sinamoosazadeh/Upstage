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
| K-016 | CONFIRMED (worse than claimed) | S1 | S1 | Source non-frozen; runner `apex/research/bootstrap.py` frozen | ISSUE-076 (per-row commits) | A — advance the delivery high-water mark only after a confirmed durable write |
| K-017 | CONFIRMED | S2 | S2 | No — `apex/ops/bootstrap_service.py` is non-frozen | — | A — persist per-cell drop evidence idempotently at every checkpoint, not only at COMPLETE |
| K-018 | CONFIRMED | S2 | S2 | No — `apex/ops/bootstrap_service.py` is non-frozen | K-017 (evidence durability) | A — announce completion on the durable COMPLETE transition, once, for both termination shapes |
| K-019 | CONFIRMED | S1 | S1 | No — `apex/ops/bootstrap_service.py` / `apex/ops/engine_context.py` are non-frozen | D22 (CATCH_UP_FAILED); K-017 (evidence durability) | A — durable per-observation publish outbox retried independently of `new_hashes`, cell status DEGRADED until reconciled |
| K-020 | CONFIRMED | S1 | S1 | Partly — `apex/research/bootstrap.py` frozen; the service, the coverage gate and `scripts/run_apex.py` are not | K-015 (walk stop reason), ISSUE-CP13-001 (empty page = only completion signal) | A — a separate non-frozen coverage gate; SKIPPED never counted as complete, never exit READY |
| K-021 | CONFIRMED | S2 | S2 | No — the wrapper lives in `apex/ops/bootstrap_service.py`; the two DDLs are frozen | ISSUE-CP9-007 (canonical table = resume authority); K-017 | A — surface the mirror failure as a named DEGRADED status and reconcile the two tables |
| K-022 | CONFIRMED | S2 | S2 | No — `apex/ops/partial_bar_repair.py` and `scripts/run_apex.py` are non-frozen | ISSUE-CP13-001 / CP-13.1 (governed repair) | A — classify the fetch failure, retry transients, and give an exhausted window its own verdict |
| K-023 | CONFIRMED | S2 | S2 | No — `apex/ops/partial_bar_repair.py` / `scripts/run_apex.py` | K-022 (same command), ISSUE-CP13-001 | A — unique run id + exclusive atomic create; report-write failure is a named non-READY outcome |
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

---

## K-016 — the delivery high-water mark survives a failed ingest and leaves a permanent hole

#### Auditor claim (short quote)
> «منبع `_served_upto` را **هنگام تحویل صفحه، قبل از ingest/checkpoint** جلو می‌برد؛ ingest خام هر سطر را جدا commit می‌کند. اگر سطر سوم از سه سطر fail شود و همان service.run دوباره اجرا گردد، `set_frontiers` فقط frontier دیتابیس را از سطر دوم می‌خواند و `_served_upto` قبلی (سطر سوم) را پاک نمی‌کند … `catch_up` با `begin_catch_up` reset جداگانه دارد.»
> — “The source advances `_served_upto` **at page delivery, before ingest/checkpoint**; raw ingest commits each row separately. If the third of three rows fails and the same `service.run` runs again, `set_frontiers` only reads the database frontier from row two and does not clear the previous `_served_upto` (row three) … `catch_up` has its own reset via `begin_catch_up`.”

#### What I read (files, line ranges, functions, callers)
`apex/ops/bootstrap_service.py:504–519` — `begin_catch_up`, which *does* clear
`_served_upto`, `_history`, `_history_end` and sets `_catch_up_floor`.
`apex/ops/bootstrap_service.py:521–537` — `set_frontiers`, whose docstring states the
behaviour verbatim: “`_served_upto` is **deliberately NOT cleared** here: it is the
within-process high-water mark that keeps a `--max-pages` stop resumable in the same
process.”
`apex/ops/bootstrap_service.py:588–621` — the serve filter (`open_ms <= frontier_ms`
→ skip, `open_ms <= served_upto` → skip) and the update at 612–617, which raises
`_served_upto[key]` to the last **delivered** bar, before the caller has ingested anything.
`apex/ops/bootstrap_service.py:622–632` — empty chunk ⇒ `_queue_cell_complete` + empty page.
`apex/ops/bootstrap_service.py:1042–1070` — `ingest_observations`: `await store.ingest_raw`
per row, and `SQLiteStore.ingest_raw` (sqlite_store.py:383–446) commits per row — the
per-row-commit behaviour named in ISSUE-076.
`apex/research/bootstrap.py:276–321` (frozen) — the page loop: `if rows: await self.ingest(...)`
(an ingest exception propagates out of `run_phase1`, so no checkpoint is written for that
page), cursor advance, `save_bootstrap`, and the default `verified: True` → `COMPLETE`.
`apex/ops/bootstrap_service.py:1399–1424` — `BootstrapService.run()`: `set_frontiers(await
self._read_frontiers())` once per run, then `runner.run_phase1(...)`; `_read_frontiers`
(1278–1300) is `SELECT MAX(as_of) FROM raw_observation` per cell.
`apex/ops/bootstrap_service.py:1485` — the only `begin_catch_up` caller, on the catch-up
path, not on the Phase-1 re-run path.

#### Reproduction (command, probe file, actual result)
Command: `python3 -B AUDIT/probes_V3b/K-016.py`; probe `AUDIT/probes_V3b/K-016.py`, output
`AUDIT/probes_V3b/K-016.out`. Real source, real `BootstrapRunner`, real
`ResearchCheckpointStore`, real `SQLiteStore.ingest_raw`; a venue with three retained closed
bars; the only fault injected is an ingest that raises on row 3.
```
run 1: run_phase1 raised RuntimeError: INJECTED_INGEST_FAILURE on row 3
run 1: rows durably stored  = [1726437600000, 1726441200000]
run 1: source._served_upto  = {('BTCUSDT', '1h'): 1726444800000}
run 1: store frontier now   = {('BTCUSDT', '1h'): 1726441200000}
run 2: set_frontiers({... : 1726441200000}) — _served_upto after handoff = {...: 1726444800000}
       run_phase1 status=COMPLETE
       rows durably stored = [1726437600000, 1726441200000]
       MISSING FOR EVER    = [1726444800000]
       checkpoint = status=COMPLETE cursor_ms=1726448400000 bars=0
run 3 (after begin_catch_up reset): _served_upto = {} ; rows stored unchanged;
       missing = [1726444800000]
```
So the claim reproduces exactly — and **run 3 shows it is worse than claimed**: even the
catch-up reset that the auditor credits as a mitigation does not recover the bar, because the
durable cursor (`cursor_ms=1726448400000`) has already advanced past the hole and the cell is
already `COMPLETE`, so the runner's `while cursor < end` loop never fetches again.

#### Verdict and reasoning
**CONFIRMED — independent severity S1** (auditor S1 retained; the defect is broader than
stated). Every step is reproduced with real code: the high-water mark is advanced at
delivery, `set_frontiers` intentionally preserves it, the re-run serves nothing, and the
cell is checkpointed `COMPLETE` with a hole. The additional finding is that
`begin_catch_up` does not repair an already-`COMPLETE` cell.

#### Root cause
Two independent progress markers exist with different durability: `_served_upto` (in-memory,
advanced at *delivery*) and the store frontier / `bootstrap_progress.cursor_ms` (durable,
advanced at *write*). Nothing reconciles them after a failure, and the reconciliation that
does exist (`set_frontiers`) is documented as deliberately one-way. Underneath, ingest is not
atomic per page (per-row commits), so a page can be half-written by construction.

#### Direct impact
A page that was delivered but not written is never re-delivered in the same process; the
missing bar becomes a permanent gap in a cell that reports `COMPLETE`, with
`bars_ingested=0` recorded for the completing page.

#### Secondary effects and interactions (upstream/downstream)
Upstream: any exception during ingest reaches this state — a disk-full event (D57's disk
floor), a transient SQLite lock (ISSUE-077), a DDL CHECK rejection (K-014's geometry law), or
a process-level error. Downstream: the hole is in the middle/end of the cell history, so it
corrupts `window()` continuity, `page_quality_measurements`' gap count for later pages, E11
label windows (49 consecutive CLOSED candles) and any ADV/feature computation crossing it;
K-015 makes such a cell indistinguishable from a complete one, and K-017 means the drop/skip
evidence is not durable either. `= ISSUE-076` for the per-row-commit part; the high-water
mark/no-reset part goes **beyond** ISSUE-076.

#### Contract and decisions
APEX_GEN5.md:17276 (Phase 1, normative): “insert closed bars into `raw_observation`;
checkpoint `bootstrap_progress`. **Resume from cursor, never rewind Phase 1.** −1003 backoff,
**do not skip**.” The observed behaviour skips a bar and then advances the cursor past it,
violating “do not skip”; the “never rewind” clause is what makes the damage permanent, so a
fix must re-deliver *before* the cursor advances rather than rewinding afterwards.
`PHASE2_DECISION_LOG.md` D50 (retry policy) and the CP-13 cursor-trap notes in the source
govern the serve boundary; no decision authorises treating an unwritten delivery as written.

#### Frozen status and non-frozen alternative
`apex/ops/bootstrap_service.py` is **not** frozen — `_served_upto`, `set_frontiers`,
`ingest_observations` and the service `run()` all live there, and that is enough for the fix.
`apex/research/bootstrap.py` **is** frozen; no change to it is required, because the service
controls both the source state and the `ingest` callable it passes to the runner.

#### Fix options (A/B/C…)
* **A (non-frozen, recommended)** — make the high-water mark *write-confirmed*: have the
  service's `ingest` callable report the last successfully stored open time back to the
  source, and advance `_served_upto` only to that value (or clear it in `set_frontiers` when
  the store frontier is behind it). Side effects: after a failure the same rows are served
  again — harmless because `ingest_raw` deduplicates by `content_hash`, but `pages_served`,
  `--max-pages` budgets and ETA figures change slightly; no frozen file, no migration, no
  hash change.
* **B** — make the page ingest atomic (one transaction per page) so a page is either fully
  written or not at all, then key resumption on the store frontier only. Side effects: the
  atomic writer must live outside the frozen `SQLiteStore` or be owner-approved inside it
  (same boundary as K-005 in V3); larger transactions increase memory and lock duration,
  interacting with ISSUE-077's transient-lock problem.
* **C** — call `begin_catch_up` on every Phase-1 re-run instead of `set_frontiers`. Side
  effects: cheapest change, but the probe's run 3 shows it is **insufficient alone** — it
  does not repair a cell whose cursor already advanced; it also discards the walk cache, so
  every re-run re-walks the venue.

#### My recommendation
**A + B**: A alone closes the reproduced hole with no frozen-file dependency; B removes the
half-written page as a class of failure and should be taken together with the K-005 atomic
writer decision. C is not sufficient. Additionally, a repair pass is needed for cells already
marked `COMPLETE`: a read-only coverage audit (bar-count vs expected per cell) must be able
to demote a cell back to incomplete, otherwise existing holes are unreachable.

#### Acceptance and regression tests
1. Fault on the last row of a page + re-run in the **same process**: all three bars are
   stored exactly once and the cell only reaches `COMPLETE` afterwards.
2. The same with a fresh process (new source object) — must also pass, and must not
   re-ingest duplicates (content-hash dedup proven by row counts).
3. A successful `--max-pages` budget stop must still resume exactly where it stopped, with no
   re-delivery — the behaviour `set_frontiers` was written to protect.
4. A cell already marked `COMPLETE` with a missing bar must be detectable and demotable by
   the coverage audit (new test).
5. Device evidence (read-only): per cell, compare
   `SELECT COUNT(*), MIN(open_time), MAX(open_time) FROM market_observation GROUP BY
   symbol,timeframe` against the expected bar count for the timeframe span, and list cells
   whose `bootstrap_progress.status='DONE'` but whose count is short.

---

## K-017 — drop evidence becomes durable only when the cell reaches COMPLETE

#### Auditor claim (short quote)
> «شمار/reason drop فقط هنگام `status=COMPLETE` در checkpoint durable می‌شود. تست budget-stop پس از دو drop صراحتاً `payload.invalid_bars_dropped=0` را انتظار دارد؛ status داخل همان process عدد ۲، ولی پس از خروج و پیش از تکمیل offline صفر است.»
> — “The drop count/reason becomes durable only at `status=COMPLETE`. The budget-stop test, after two drops, explicitly expects `payload.invalid_bars_dropped=0`; the in-process status says 2, but after exiting and before completion the offline status is zero.”

#### What I read (files, line ranges, functions, callers)
`apex/ops/bootstrap_service.py:713–740` — `_record_invalid_bar` (in-memory only:
`invalid_dropped`, `invalid_by_cell`, `invalid_reasons`, `invalid_offenders`) and
`_offenders_summary`; the only persistence-adjacent consumer is the wiring print in
`_queue_cell_complete` (742–764).
`apex/ops/bootstrap_service.py:946–1019` — `CanonicalMirroredCheckpoints.save_bootstrap`:
the `invalid_bars_dropped`/`invalid_reasons` merge is inside `if status == "COMPLETE"`;
the `else` branch (996–1007) only *carries forward* keys that already exist
(“Non-COMPLETE saves carry previously persisted evidence keys forward instead of wiping
them … First-run budget stops are unaffected (no old keys exist yet)” — the source states
the gap itself).
`apex/ops/bootstrap_service.py:1345–1380` — `status()`: `durable_total` from completed
cells' payloads **plus** `source_extra` from the live in-process source for cells that are
not yet complete; with no source (offline) the second term is 0 by construction.
`tests/unit/test_ops_bootstrap_service.py:1161–1183`
(`test_budget_stop_keeps_the_drop_evidence`) and **1738–1760**
(`test_budget_stop_reports_live_drops_but_persists_nothing`, whose name states the
behaviour and whose body asserts `row["payload"].get("invalid_bars_dropped", 0) == 0`).
Callers of `status()`: the CLI `status` command (`scripts/run_apex.py`) and the service's
own reporting.

#### Reproduction (command, probe file, actual result)
Commands: `python3 -B AUDIT/probes_V3b/K-017.py` and
`python3 -m pytest -q -p no:cacheprovider tests/unit/test_ops_bootstrap_service.py -k "budget_stop or drop_evidence or persists_nothing"` → **5 passed, 66 deselected**.
Probe output (`AUDIT/probes_V3b/K-017.out`), using the repository's own poison-row venue
helpers and the real service:
```
budget stop: status=BUDGET_REACHED resumable=True invalid_bars_dropped(reported)=2
durable checkpoint: status=IN_PROGRESS payload={}
in-process status(): invalid_bars_dropped=2
live source evidence: invalid_by_cell={('BTCUSDT','1d'): 2}
                      reasons={('BTCUSDT','1d'): {'LOW_ABOVE_MIN_OPEN_CLOSE':1,
                                                  'HIGH_BELOW_MAX_OPEN_CLOSE':1}}

AFTER EXIT — offline service.source is None: True
offline status(): invalid_bars_dropped=0 cells_completed=0
offline checkpoint: status=IN_PROGRESS payload={}
```
Two real poison bars were dropped with named reasons; nothing about them survives the
process. The offline operator view reports **0**.

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). The claim reproduces exactly,
including the existing test that pins the zero. S2 rather than S1: no wrong number reaches a
decision, and a later successful walk over the same retained window will re-count the
offenders; the damage is operator-visible truth (“0 dropped” is asserted, not “unknown”),
which is an observability failure. It is not S3 because the zero is indistinguishable from a
genuine clean run, and the evidence is unrecoverable once venue retention slides the poison
bar out of the window — exactly the caveat the auditor states.

#### Root cause
Drop evidence lives only in the source object's memory, and the single persistence hook was
attached to the COMPLETE transition. Every non-COMPLETE checkpoint (`IN_PROGRESS`, `PAUSED`,
budget stop) writes a payload that can only *preserve* evidence, never create it.

#### Direct impact
After a `--max-pages` budget stop, a pause or any process exit before completion, the
per-cell drop count and reasons are lost, and `status` reports `invalid_bars_dropped=0`
for that cell.

#### Secondary effects and interactions (upstream/downstream)
Upstream: the CP-12 hygiene gate (K-014's `_ohlc_violation`) is the producer of this
evidence, and only geometry violations are counted — so the figure is already narrower than
“bad data seen”. Downstream: the operator's completeness judgement for the 140-cell data
scope rests on this number; combined with K-015 (a truncated cell can be COMPLETE) and K-016
(a hole can be COMPLETE), the three together mean “COMPLETE, 0 dropped” carries almost no
information. Note a genuine mitigation the auditor did not credit: `status()` does merge
live in-process evidence for non-complete cells (bootstrap_service.py:1357–1364), so the
zero appears only after process exit — my probe separates the two cases explicitly.

#### Contract and decisions
APEX_GEN5.md:17276 (Phase 1, normative) requires checkpointing `bootstrap_progress` and
forbids skipping; §2.6/AI.5 (implemented at `sqlite_store.py:245–288`) requires that “every
correction, revocation, or deletion is logged with event_id, timestamp, reason, and actor
identity (immutable audit trail)” — a dropped venue bar is the closest analogue and is
currently logged only to stdout. No `PHASE2_DECISION_LOG.md` decision authorises discarding
drop evidence on a clean stop; CP-13/ISSUE-CP13-003 (quoted in the source at 900–914)
introduced the COMPLETE-only merge, so the gap is a known-scope limitation rather than an
owner ruling that non-COMPLETE evidence may be dropped.

#### Frozen status and non-frozen alternative
**Not frozen** — `apex/ops/bootstrap_service.py` owns `_record_invalid_bar`,
`CanonicalMirroredCheckpoints` and `status()`. The durable target
(`research_bootstrap_progress.payload_json`) already exists and already accepts arbitrary
payload keys, so no frozen DDL or frozen runner change is needed.

#### Fix options (A/B/C…)
* **A (recommended)** — merge `invalid_bars_dropped`/`invalid_reasons`/offenders into the
  payload on **every** `save_bootstrap`, not only at COMPLETE, using a max/union merge so
  re-walks cannot double-count (the COMPLETE branch's `max(cur, old)` rule already exists
  and can be reused). Side effects: `test_budget_stop_reports_live_drops_but_persists_nothing`
  must be rewritten (it asserts the current zero); payload rows grow slightly; the
  idempotence rule must be stated explicitly or a resumed walk inflates the count.
* **B** — write a separate append-only drop-evidence record (one row per dropped bar) at the
  moment of the drop. Side effects: strongest evidence (per-bar, with reason and raw repr)
  and naturally idempotent if keyed by `(symbol,timeframe,open_time,reason)`; needs a new
  table, i.e. a migration — in the **frozen** `sqlite_store.py` MIGRATIONS list unless it is
  placed in the non-frozen research checkpoint store, which is where it belongs.
* **C** — leave persistence as is and make `status()` report `unknown` instead of `0` when no
  source is attached and the cell is incomplete. Side effects: smallest change, removes the
  false zero but not the evidence loss; acceptable only as an interim measure.

#### My recommendation
**A now, C immediately as a one-line honesty fix, B when the checkpoint store next takes a
migration.** A restores the count with no new schema; C stops the `0` from being read as
“clean”; B is the only option that preserves *which* bars were dropped after retention slides
them out of the venue window.

#### Acceptance and regression tests
1. Two drops + `max_pages=1` + process exit: the offline status shows the same two
   offenders/reasons (or an explicit durable receipt), not `0`.
2. Resuming and completing the same cell must not double-count (still `2`).
3. A genuinely clean cell must still report `0` — the fix must not turn “no evidence” into
   “unknown” for completed clean cells.
4. Regression: `tests/unit/test_ops_bootstrap_service.py::test_budget_stop_keeps_the_drop_evidence`
   (in-process reporting) must keep passing; the `…persists_nothing` test must be re-baselined
   to the new durability guarantee.

---

## K-018 — no `CELL_COMPLETE` announcement when the run end falls exactly on a close boundary

#### Auditor claim (short quote)
> «چاپ `CELL_COMPLETE` فقط وقتی `__call__` صفحهٔ خالی برگرداند صف می‌شود؛ اگر آخرین کندل بسته‌شده دقیقاً در `end_ms` تمام شود، `next_cursor_ms=end_ms` و runner بدون درخواست empty از loop خارج و COMPLETE می‌کند … مجموع drop در خروجی قابل دیدن است، اما گزارش per-cell/offenders پیش‌فرض از دست می‌رود.»
> — “The `CELL_COMPLETE` print is queued only when `__call__` returns an empty page; if the last closed candle ends exactly at `end_ms`, `next_cursor_ms=end_ms` and the runner leaves the loop and completes without ever asking for an empty page … the total drop count is still visible, but the per-cell/offender report is lost.”

#### What I read (files, line ranges, functions, callers)
`apex/ops/bootstrap_service.py:609–644` — the serve path: `_served_upto` update, then
`if not chunk: self._queue_cell_complete(...)` (622–632) — the **only** call site of
`_queue_cell_complete` — and otherwise `close_last = close_time_ms(last_open_ms, tf_name);
next_cursor = close_last if close_last > cursor else cursor + 1` (639–640).
`apex/ops/bootstrap_service.py:742–764` — `_queue_cell_complete` builds the line with
`dropped=`, `open_excluded=` and `_offenders_summary`.
`apex/ops/bootstrap_service.py:1225–1240` — `_flush_cell_complete_prints` drains
`drain_cell_complete_prints()` into `self.report(..., kind="CELL_COMPLETE")`; called at
1425/1436/1494.
`apex/research/bootstrap.py:273–321` (frozen) — `while cursor < end:` … `cursor = new_cursor`;
when `new_cursor == end` the loop exits **without another fetch**, then the default
`verified: True` writes `COMPLETE`.
`scripts/run_apex.py:488–502,538–556` — the CLI surfaces notifications and the aggregate
`invalid_bars_dropped`.

#### Reproduction (command, probe file, actual result)
Command: `python3 -B AUDIT/probes_V3b/K-018.py`; probe/output
`AUDIT/probes_V3b/K-018.py|.out`. Real service, real source, repository poison-row venue,
two runs differing only in `end_ms`:
```
A. end_ms == close boundary (1677715200000): status=COMPLETE, invalid_bars_dropped=2,
   checkpoint payload={'invalid_bars_dropped': 2, 'invalid_reasons': {...}},
   CELL_COMPLETE notifications = 0
B. end_ms == close boundary + 5 s:            status=COMPLETE, invalid_bars_dropped=2,
   CELL_COMPLETE notifications = 1
   "cell=BTCUSDT:1d pages=2 bars=48 dropped=2 open_excluded=0
    offenders=[BTCUSDT:1d@1673395200000; BTCUSDT:1d@1677196800000]
    reasons=[HIGH_BELOW_MAX_OPEN_CLOSE=1; LOW_ABOVE_MIN_OPEN_CLOSE=1]"
```

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). The boundary sensitivity is
exact and reproduces on real code. Two refinements to the auditor's text, both in the
project's favour: the aggregate `invalid_bars_dropped=2` is still reported (as the auditor
also notes), **and** in this scenario the durable checkpoint payload is identical in both
runs, because the cell did reach COMPLETE and the K-017 merge ran. So the loss is exactly
the per-cell announcement with the offender list — an observability defect, S2.

#### Root cause
The completion *announcement* is attached to a fetch-path side effect (the empty page)
instead of to the state transition that actually means completion (the runner's
`status=COMPLETE` save). A run end that coincides with a close boundary is a normal,
frequent case for a scheduler aligned to close boundaries.

#### Direct impact
For every cell whose last closed bar ends exactly at the run end, the owner sees no
per-cell completion line and no offender/reason list, even when bars were dropped.

#### Secondary effects and interactions (upstream/downstream)
Upstream, `end_ms` is chosen by the caller: `BootstrapService.run(end_ms=...)` and the
scheduler's close boundaries make exact coincidence likely, not exotic. Downstream, the
offender list is the only place where the *identity* of dropped bars is shown to a human
(K-017 shows it is not durable in the non-COMPLETE case; here it is durable but unannounced).
Interacts with K-015/K-020: a cell can complete without any announcement and without any
coverage proof.

#### Contract and decisions
APEX_GEN5.md:17276 makes `bootstrap_progress` checkpointing normative but says nothing about
the announcement channel; the Telegram command surface in the same clause
(`start|pause|resume|stop|progress|eta|continuous on|off`) implies the operator learns
progress from the service, and §2.6/AI.5's audit-trail principle implies a drop must be
visible. No `PHASE2_DECISION_LOG.md` decision governs the announcement trigger; the CP-13
source comment calling the empty page “the ONLY completion signal” is an implementation
note, not an owner ruling.

#### Frozen status and non-frozen alternative
**Not frozen** — everything involved (`_queue_cell_complete`, `_flush_cell_complete_prints`,
the mirrored checkpoint wrapper) is in `apex/ops/bootstrap_service.py`. The frozen runner
need not change: `CanonicalMirroredCheckpoints.save_bootstrap` already observes every
status transition and is the natural hook.

#### Fix options (A/B/C…)
* **A (recommended)** — emit the announcement from the mirrored checkpoint wrapper when a
  cell transitions to `COMPLETE` (dedup by cell id so the empty-page path does not produce a
  second line). Side effects: the announcement now fires for cells completed without a walk
  in this process (re-runs), so the text must state “no walk in this process” rather than
  printing a stale zero — the same distinction K-017's merge already makes; tests that count
  notifications must be extended.
* **B** — also request one final page after the loop so the empty-page signal always occurs.
  Side effects: an extra venue call per cell per run (rate-limit budget, C-012), and it
  would have to happen inside the **frozen** runner — rejected.
* **C** — leave the trigger and print the offender summary in the run report instead of a
  per-cell notification. Side effects: weakest; loses the one-line-per-cell format the owner
  already reads.

#### My recommendation
**A** — it fixes both termination shapes with one non-frozen hook and composes with the
K-017 durability fix (same merge point).

#### Acceptance and regression tests
1. `end_ms` exactly on the close boundary, with `dropped>0`: exactly **one** CELL_COMPLETE
   notification containing the offender list.
2. `end_ms` a few seconds later: still exactly **one** notification (no duplicate from the
   empty-page path).
3. `open_excluded>0` (a still-open bar at the end) reports the same single notification with
   the excluded open time.
4. A re-run over an already complete cell must not print a misleading `dropped=0`.

---

## K-019 — a failed catch-up quality publish is recorded, never retried, and still counts as success

#### Auditor claim (short quote)
> «`catch_up` پس از ingestِ commitشده quality fact را publish می‌کند؛ exception/`failures` فقط در `quality_publish.failures` می‌رود، `successful` همچنان True و boundary جلو می‌رود … boundary بعدی هیچ quality retry نداشت؛ زیرا `new_hashes` فقط hashهای هنوز در raw غایب را می‌گیرد. `quality_window` بدون fact با `QUALITY_PROVENANCE_UNAVAILABLE` امتناع می‌کند.»
> — “`catch_up` publishes the quality fact after the committed ingest; the exception/`failures` only lands in `quality_publish.failures`, `successful` stays True and the boundary advances … the next boundary performs no quality retry, because `new_hashes` only collects hashes still absent from raw. `quality_window` then refuses with `QUALITY_PROVENANCE_UNAVAILABLE`.”

#### What I read (files, line ranges, functions, callers)
`apex/ops/bootstrap_service.py:1456–1564` — the whole of `BootstrapService.catch_up`:
`successful = True` (1472); per cell `frontier = MAX(as_of) FROM raw_observation` (1479–1483);
`new_hashes` built **only** from rows whose `content_hash` is *not yet* in `raw_observation`
(1495–1505); `await self._ingest(rows, symbol, tf)` (1506) commits first; then
`if new_hashes:` → `publish_catch_up_quality(...)` (1507–1521) wrapped in
`except Exception as exc:` (1522–1534) which appends to
`result["quality_publish"]["failures"]` and **does not touch `successful`**; the `else`
branch (1535–1539) likewise only *accumulates* `published["failures"]`. The cell-level
`except` (1541–1548) that does set `successful = False` is never reached, so
`if successful: self._catch_up_boundary[timeframe] = boundary` (1562–1563) runs.
`apex/ops/engine_context.py:3765–3812` — `publish_catch_up_quality`: `only_hashes` filter
(3778–3780), duplicate-fact skip (3792–3797), per-row `BridgeError` collected into
`failures` (3808–3810) — i.e. a partial failure is also non-fatal.
`apex/ops/engine_context.py:3813–3840` + `2030–2049` — `publish_quality_observation`'s
`QUALITY_PROVENANCE_UNAVAILABLE` refusals, and the consumer:
`EngineContext.quality_window` raises `BridgeError("QUALITY_PROVENANCE_UNAVAILABLE", identity)`
for any window bar whose fact is missing (2046–2048).
`tests/unit/test_engine_context.py:149–185` — `test_catch_up_quality_publish_failure_is_named`
asserts exactly the failure list and `bars_ingested == 1`; it asserts nothing about retry,
boundary or `successful`.
Callers: `grep -rn "publish_catch_up_quality"` → one production call site
(`bootstrap_service.py:1509/1517`) and one test monkeypatch. `grep -rn "QUALITY_PROVENANCE_UNAVAILABLE"`
→ 9 production sites, all refusals.

#### Reproduction (command, probe file, actual result)
Command: `python3 -B AUDIT/probes_V3b/K-019.py`; probe/output `AUDIT/probes_V3b/K-019.py|.out`.
Real `BootstrapService`, real `SQLiteStore`, the repository's own fake Toobit responder
(via `tests/unit/test_engine_context.py::_StoredKlineResponder`):
```
1. first catch_up, publisher raises BridgeError
   bars_ingested = 1   cells_updated = 1   failures (cell) = []
   quality_publish = {'written': 0, 'skipped': 0,
                      'failures': [{'symbol':'BTCUSDT','timeframe':'1h',
                                    'reason':'QUALITY_PUBLISH_REFUSED'}]}
   catch_up boundary = {'1h': 1767229200000}      <-- advanced
   durable QUALITY fact for that bar = None
2. next boundary, publisher healthy again, one NEW bar appears
   bars_ingested = 1   failures (cell) = []
   quality_publish = {'written': 1, 'skipped': 0, 'failures': []}
   bar 1 (failed publish)  obs-…ae41 -> fact MISSING
   bar 2 (healthy publish) obs-…eabe -> fact PRESENT
```
Existing tests stay green: `python3 -m pytest -q -p no:cacheprovider
tests/unit/test_engine_context.py -k catch_up` → **9 passed, 218 deselected** — i.e. the
behaviour is *pinned*, not accidental.

#### Verdict and reasoning
**CONFIRMED — independent severity S1** (auditor S1 retained). Every element of the claim is
reproduced on real code: failure recorded but not fatal, boundary advanced, the healthy next
cycle repairs nothing because the bar is no longer "new", and the consumer refuses. The gap
is permanent under automatic operation: nothing in the runtime ever revisits a bar that is
already in `raw_observation` but has no `QUALITY_` fact. S1 rather than S2 because it
silently converts a *stored* bar into an unusable one and the only recovery path
(`backfill_facts_in_window` / manual backfill) writes `BACKFILL`/
`HISTORICAL_BACKFILL_BOOTSTRAP_DEFAULTS` provenance, which `quality_window` rejects outside
PAPER (`QUALITY_PROVENANCE_BACKFILL_NOT_LIVE`, engine_context.py:2052–2054) — so the manual
route cannot restore LIVE-usable provenance either.

#### Root cause
Two independent writes (raw ingest, quality fact) are sequenced without a transaction, a
receipt or an outbox, and the *retry trigger* is derived from the wrong predicate: the
"is there work to do" test is `content_hash not in raw_observation`, which is by construction
false immediately after the ingest that preceded the failed publish. Additionally the error
class chosen for the publish failure (`quality_publish.failures`) is outside the D22
`failures[]`/`CATCH_UP_FAILED` channel that the plan stage actually consults.

#### Direct impact
A bar exists in the raw store with no quality witness for ever. Any `quality_window`
covering it — i.e. the whole 300-bar window containing that timestamp, for as long as it is
in the window — refuses with `QUALITY_PROVENANCE_UNAVAILABLE`, so no plan/decision is
produced for that cell even though data and freshness are fine.

#### Secondary effects and interactions (upstream/downstream)
Upstream: the `new_hashes` block is guarded by `apex_env == "PAPER"`, so in any other
environment **no** fact is published by catch-up at all — the same hole, permanently open,
which makes the LIVE path depend entirely on another publisher. Downstream: `quality_window`
→ `EngineContext.bundle` → plan/decision; the cell fails closed, which is correct behaviour
for a missing witness but is caused here by an internal write failure, not a data problem.
Interacts with **K-017** (drop evidence also survives only on the happy path) and with
**K-015/K-016** (progress markers advancing past unfinished durable work) — all three are the
same anti-pattern: a progress/completion marker advanced by delivery rather than by confirmed
durable state. Also interacts with D22: because the failure is not in `failures[]`, the cell
is *not* marked `CATCH_UP_FAILED`, so the "next cycle retries" guarantee D22 relies on is
never engaged.

#### Contract and decisions
* `APEX_GEN5.md:18751` (Ch.5 read/write ownership): **“Fail-closed: on write failure, halt
  ingestion and alert; do not cache and retry silently.”** A committed raw row whose quality
  write failed is neither halted nor alerted as a cell failure — it is reported in a side
  field and the boundary advances. Direct violation.
* `APEX_GEN5.md:5068`: a degraded status “MUST be carried as a degraded quality/provenance
  flag” and “MUST NOT bypass a hard data-quality, PIT, …” gate — the run reports success.
* `PHASE2_DECISION_LOG.md:284` (**D22**, binding): a catch-up failure “is recorded separately:
  the cycle JSON `catch_up.failures[]` entry carries the cell, the error code and the frontier
  it tried from, and the cell receives a per-cycle named status `CATCH_UP_FAILED` … the next
  cycle retries the catch-up.” Precedence: D22 is an owner decision and is *more specific*
  than the Ch.5 bullet; both point the same way, and the quality-publish failure satisfies
  neither — it is in `quality_publish.failures`, not `failures[]`, with no named cell status
  and no retry.
* `PHASE2_DECISION_LOG.md:275` (ISSUE-CP14-002 interim) explicitly says engine/plan evaluation
  must be refused on catch-up failure; here evaluation is refused later, by the consumer, for
  a reason the operator cannot connect to the cycle that caused it.

#### Frozen status and non-frozen alternative
**Not frozen.** `apex/ops/bootstrap_service.py` and `apex/ops/engine_context.py` are both
outside the frozen set (`apex/engines/**`, `apex/data_catalog/**`,
`apex/research/bootstrap.py`, `apex/research/backtest.py`, the six original params YAMLs,
`requirements.lock`). Note the *store* DDL is frozen, so a new outbox table must go in the
non-frozen checkpoint/ops database (the same place K-017's evidence rows would live), not in
the frozen market store schema.

#### Fix options (A/B/C…)
* **A (recommended)** — durable publish outbox keyed by `observation_id`: written in the same
  transaction as (or immediately after) the ingest, cleared only when the fact is confirmed
  present. Each catch-up cycle first drains the outbox (retry independent of `new_hashes`),
  and any cell with a non-empty outbox reports a named status (`QUALITY_PUBLISH_PENDING`)
  through the D22 `failures[]` channel so the cell is DEGRADED/blocking until reconciled.
  Side effects: new non-frozen table + migration in the ops DB; `catch_up`'s return shape
  gains entries in `failures[]`, so `test_catch_up_quality_publish_failure_is_named`
  (tests/unit/test_engine_context.py:149–185) must be extended (it currently asserts the
  failure is *only* in `quality_publish.failures`); PAPER cycle JSON fixtures that assert
  `failures == []` need updating; no hash or frozen file is touched.
* **B** — reconciliation sweep: derive the missing set with a query
  (`market_observation` LEFT JOIN the quality facts for the cell window) and republish.
  Side effects: no new table, but a per-cell scan each cycle (cost; see X-V3b-001 for how
  expensive an unindexed per-cell join is on the device) and it can only republish while the
  original receipt/http metadata is still obtainable — provenance would degrade.
* **C** — make the publish failure fatal for the cell (`successful = False`, `failures[]`
  entry) without an outbox, relying on D22's "next cycle retries". Side effects: cheapest,
  but on its own it does **not** heal the bar — the next cycle still computes an empty
  `new_hashes`, so it must be combined with B or A; alone it only makes the damage visible.
* **D** — remove the `apex_env == "PAPER"` guard so every environment publishes. Side effects:
  necessary for LIVE correctness but orthogonal; must be owner-approved because it changes
  what LIVE writes.

#### My recommendation
**A + C**: the outbox makes recovery automatic and the D22 status makes the degradation
visible in the cycle that caused it. Raise **D** with the owner separately, since as written
the non-PAPER path never publishes a catch-up fact at all.

#### Acceptance and regression tests
1. Publish fails once, then the publisher is healthy: no duplicate `raw_observation` row, the
   fact for the original bar appears on the **next** cycle with correct
   `receipt_time_ms`/lineage (not BACKFILL provenance), and the outbox is empty afterwards.
2. While the fact is missing, the cell reports `CATCH_UP_FAILED`/`QUALITY_PUBLISH_PENDING` in
   `failures[]`, the timeframe boundary does **not** advance, and no plan is produced for that
   cell.
3. `quality_window` over a window containing the healed bar succeeds after reconciliation and
   refuses before it (`QUALITY_PROVENANCE_UNAVAILABLE`).
4. Idempotence: draining an outbox entry whose fact already exists is a no-op (`skipped`),
   never a second fact.
5. Non-PAPER environment: assert explicitly what is expected (currently: nothing published) so
   option D is a deliberate, tested change.

---

## K-020 — harvest "completion" means the walk ended, not that data was acquired or accepted

#### Auditor claim (short quote)
> «runner در production verifier ندارد و حتی وقتی منبع **هیچ بار** تحویل نداده، empty-page را COMPLETE می‌کند؛ probe سلول با صفر ingest، status COMPLETE و pending=[] داد. اگر verifier سفارشی false دهد، status سلول `SKIPPED` می‌شود ولی `pending_cells` و `progress_async` آن را completed حساب می‌کنند؛ وقتی همه SKIPPED باشند result اصلی هم COMPLETE و CLI status exit READY می‌دهد.»
> — “In production the runner has no verifier and completes on the empty page even when the source delivered **no bar at all**; the probe's cell with zero ingest gave status COMPLETE and pending=[]. If a custom verifier returns false the cell status becomes `SKIPPED`, but `pending_cells` and `progress_async` count it as completed; when all are SKIPPED the top-level result is COMPLETE too and the CLI status exits READY.”

#### What I read (files, line ranges, functions, callers)
`apex/research/bootstrap.py:257–334` (frozen) — `run_phase1`: the walk `while cursor < end`,
then `verification = {"verified": True, "reason": "PHASE1_PAGE_WALK_DONE"}` (307) overridden
only `if self.phase1_verifier is not None` (309–313); `status = "COMPLETE" if
verification.get("verified") else "SKIPPED"` (314); the result's top-level `status` is
`"STOPPED"/"PAUSED"/"COMPLETE"` (323–325) and depends only on stop/pause flags — never on
`skipped_cells`.
`apex/research/bootstrap.py:336–346` — `pending_cells`: `done = {... if r["status"] in
("COMPLETE", "SKIPPED")}`, i.e. a refused cell is *not* pending.
`apex/research/bootstrap.py:409–424` — `progress_async`: `complete = [r for r in rows if
r["status"] in ("COMPLETE","SKIPPED")]`, `cells_remaining = len(cells) - len(complete)`;
`_percent()` is a page-count heuristic, not coverage.
`apex/research/bootstrap.py:167,176` — `phase1_verifier` is a constructor parameter that
defaults to `None`.
`apex/ops/bootstrap_service.py:1170–1179` — `BootstrapService.open()` constructs
`BootstrapRunner(fetcher=…, ingest=…, store=…, cells=…, now=…)` — **no `phase1_verifier`
argument**; `grep -rn "phase1_verifier" --include=*.py .` returns only the definition sites
and `tests/unit/test_research_bootstrap.py:217`.
`apex/ops/bootstrap_service.py:1396–1454` — `run()` decorates the runner result with
preflight/drop/offender/open-excluded fields; it does not re-judge completion.
`apex/ops/bootstrap_service.py:609–640` — the serve path whose empty page is the only
completion signal (ISSUE-CP13-001), reached identically when the venue retains nothing and
when every retained bar was dropped as invalid.
`scripts/run_apex.py:504–571` — `_bootstrap`: prints `completed=len(completed_cells)
pending=len(pending_cells)` and `if status == "COMPLETE": return EXIT_READY`.
`scripts/run_apex.py:577–605` — `_status`: `return EXIT_READY if
status["cells_remaining"] == 0 else EXIT_DEGRADED`.
`tests/unit/test_ops_bootstrap_service.py:940–957` —
`test_all_poison_cell_completes_with_zero_bars_and_full_evidence` pins exactly this: 25
poison bars, `rows == []`, `next_cursor_ms == end` — “the ONLY completion signal”, `bars=0`.

#### Reproduction (command, probe file, actual result)
Command: `python3 -B AUDIT/probes_V3b/K-020.py`; probe/output `AUDIT/probes_V3b/K-020.py|.out`.
Real `BootstrapService`, real `BootstrapRunner`, real `ResearchCheckpointStore`:
```
A. empty venue (zero retained bars), real BootstrapService
   runner phase1_verifier = None
   status = 'COMPLETE'  completed_cells = ['BTCUSDT:1h']  skipped_cells = []
   pending_cells = []   bars_ingested = 0
   status(): completed=1 remaining=0 bars=0
   durable raw_observation rows = 0
B. real runner, verifier refuses EVERY cell
   durable statuses = [('BTCUSDT:15m','SKIPPED'), ('ETHUSDT:15m','SKIPPED')]
   result status = 'COMPLETE'  completed_cells = []  skipped_cells = [both]
   pending_cells = []   pending_cells() = []
   progress_async = completed=2 remaining=0
C. grep -rn phase1_verifier --include=*.py .  -> definition sites +
   tests/unit/test_research_bootstrap.py:217 only (no production construction)
```
Both CLI exit mappings therefore yield **READY**: `_bootstrap` on `status == "COMPLETE"`
(run_apex.py:565–566) and `_status` on `cells_remaining == 0` (run_apex.py:604).

#### Verdict and reasoning
**CONFIRMED — independent severity S1** (auditor S1 retained). Every element reproduces on
real code, including the part that is easiest to doubt (SKIPPED counted as done in *three*
places: `pending_cells`, `progress_async`, and by omission in the top-level status). The
severity is S1 because the failure mode is a false readiness signal that the operator is
explicitly told to trust, and because it is silent: an operator seeing `completed=140
remaining=0 … READY` cannot distinguish 140 fully harvested cells from 140 empty ones.

#### Root cause
Two different questions are answered by one flag. "Did the page walk terminate?" is a
mechanical property of the fetch loop; "does this cell hold enough correct data to be used?"
is a coverage property of the store (first/last bar, gap count, drop ratio, minimum bars).
The frozen runner only knows the first, and the wiring never adds the second: it never
installs a verifier, and the two owner-facing aggregations (`pending_cells`,
`progress_async`) fold the "refused" state into the "finished" set.

#### Direct impact
A cell with zero bars, a partially retained window, or 100 % dropped bars is reported
COMPLETE / not pending, and `run_apex.py bootstrap|status` exits READY. Downstream work
(research, quality, PAPER) is authorised on a coverage that was never measured.

#### Secondary effects and interactions (upstream/downstream)
Upstream: the venue itself is the arbiter of the completion signal — the same empty page is
produced by exhaustion, by a venue that retains nothing, and by a repeat-stopping venue
(**K-015**), and after a poison-only cell (`test_all_poison_cell_completes_with_zero_bars…`).
Combined with **K-016**, a cell that lost a bar to a failed write also reaches COMPLETE.
Downstream: `_status`'s READY is consumed as the go/no-go for the next phase; **K-018** means
the per-cell announcement may not even be printed, so nothing else contradicts the READY.
Scope note: per **D30** the default E11 training scope is 20 base cells, which must not be
confused with the 140-cell data scope of `APEX_GEN5.md:17276` — a readiness gate must state
which scope it measured (the auditor makes the same point).

#### Contract and decisions
* `APEX_GEN5.md:17276` (**Phase 1 algorithm, normative**): “for each of **140 cells**, page
  `GET /quote/v1/klines` limit=1000 **from `2020-01-01T00:00:00Z` to now**; insert closed bars
  into `raw_observation`; checkpoint `bootstrap_progress`.” The normative unit of completion
  is the *covered window*, not the loop exit; nothing in the clause authorises declaring a
  cell done with zero rows.
* `APEX_GEN5.md:17294+` — Phase 3 “completes when **all** symbol×timeframe cells have been
  swept at least once”; the same all-cells language is used for readiness, again by coverage.
* `APEX_GEN5.md:5068` — a degraded status “MUST be carried as a degraded quality/provenance
  flag … MUST NOT bypass a hard data-quality … gate”: SKIPPED being summed into
  `cells_completed` is exactly such a bypass.
* `PHASE2_DECISION_LOG.md:182` (**ISSUE-CP13-001**, CLOSED-with-evidence) makes the empty page
  “the only completion signal” of the **serve law** and is deliberately about cursor safety,
  not about data sufficiency. Precedence: ISSUE-CP13-001 governs *how the walk terminates*;
  APEX_GEN5.md:17276 governs *what Phase 1 must have achieved*. They do not conflict — the
  gap is that no artefact implements the second.
* No decision in `PHASE2_DECISION_LOG.md` defines a coverage/readiness criterion or authorises
  counting SKIPPED as complete.

#### Frozen status and non-frozen alternative
`apex/research/bootstrap.py` is **frozen**, so `run_phase1`, `pending_cells` and
`progress_async` may not be edited. Non-frozen alternatives exist and are sufficient:
(i) `BootstrapService.open()` (bootstrap_service.py:1176) can pass a real `phase1_verifier`
— the frozen runner already supports the hook and maps a refusal to `SKIPPED`;
(ii) `BootstrapService.status()` / the run result can recompute its own
completed/remaining/refused counts from the durable rows instead of reusing
`progress_async`; (iii) `scripts/run_apex.py` can require `skipped == 0` **and** a coverage
verdict before `EXIT_READY`. No frozen file needs to be touched.

#### Fix options (A/B/C…)
* **A (recommended)** — install a non-frozen coverage verifier and fix the counting:
  a `phase1_verifier` that measures, per cell, first/last stored bar vs the requested window,
  missing-bar count, drop ratio and minimum bar count, returning
  `{"verified": False, "reason": …}` on failure; plus a service-level status that reports
  `completed / refused / pending` as three disjoint sets, and a CLI that exits READY only
  when `refused == 0 and pending == 0` for the declared scope (140 data cells, stated
  explicitly, separate from D30's 20 fit cells). Side effects: cells that are genuinely
  incomplete start reporting DEGRADED, which will change existing CLI expectations and any
  test asserting `EXIT_READY` after a fixture run (`tests/unit/test_ops_bootstrap_service.py`
  completion tests and the run_apex CLI tests must be re-baselined to the new tri-state);
  the verifier adds one store query per cell per run — keep it indexed and bounded (see
  X-V3b-001 for the cost of an unindexed per-cell query on the device); no frozen file, no
  hash, no migration.
* **B** — leave the verifier absent and only fix the aggregations (SKIPPED reported
  separately, READY requires `skipped == 0`). Side effects: minimal and immediate, but does
  nothing for the empty-venue case, which is the S1 half of this finding.
* **C** — gate readiness outside the bootstrap entirely, in a separate `coverage-report`
  command that the operator must run. Side effects: honest, but an out-of-band step that
  nothing enforces; acceptable only as an addition to A.
* **D** — change the frozen runner so that `skipped_cells` demotes the top-level status.
  **Rejected**: frozen file, and A achieves the same from the wiring.

#### My recommendation
**A**, with **B** shipped first as the one-line risk reduction (stop counting SKIPPED as
complete, stop exiting READY with refusals). Keep the empty-page serve law untouched — the
defect is the missing second gate, not the walk termination rule.

#### Acceptance and regression tests
1. Empty venue: status DEGRADED/refused for the cell, `pending`/`refused` non-empty, CLI exit
   **not** READY.
2. Partial window (venue retains only the last N bars of the requested range): refused with a
   named coverage reason carrying first/last stored bar vs requested.
3. All bars invalid (the existing poison-only fixture): walk still completes, but the cell is
   refused and the drop ratio is reported.
4. Verifier returns false: `SKIPPED` appears in its own bucket; `cells_completed` excludes it;
   `pending_cells`-equivalent service output includes it; exit not READY.
5. Full coverage over the declared scope: the only case that yields READY, and the scope size
   (140 data cells) is asserted explicitly and kept distinct from D30's 20-cell fit scope.

---

## K-021 — the canonical checkpoint mirror swallows every failure, and `last_error` is sticky

#### Auditor claim (short quote)
> «`CanonicalMirroredCheckpoints.save_bootstrap` ابتدا research row را commit می‌کند و **تمام** خطاهای mirror canonical را خاموش می‌بلعد. در probe `canonical.db.execute` خطا داد اما research `COMPLETE` ثبت شد و caller موفق برگشت؛ status/CLI فقط research را می‌خوانند. همچنین `last_error=COALESCE(new,old)` خطای SKIPPED قدیمی را پس از DONE احتمالی پاک نمی‌کند.»
> — “`CanonicalMirroredCheckpoints.save_bootstrap` commits the research row first and silently swallows **all** canonical mirror errors. In the probe `canonical.db.execute` raised, yet research recorded `COMPLETE` and the caller returned successfully; status/CLI read only research. Also `last_error=COALESCE(new,old)` does not clear a stale SKIPPED error after a later DONE.”
> The auditor also notes: “نبود reader عملیاتی canonical در این خوانش، اثر معامله‌ای مستقیم را اثبات نمی‌کند” — no operational reader of the canonical table was found, so no direct trading impact is proven.

#### What I read (files, line ranges, functions, callers)
`apex/ops/bootstrap_service.py:832–857` — `_canonical_upsert`: the `ON CONFLICT … DO UPDATE`
with `cursor_open_time=MAX(...)`, `status=excluded.status`,
`bars_written=bootstrap_progress.bars_written+excluded.bars_written`,
**`last_error=COALESCE(excluded.last_error, bootstrap_progress.last_error)`**.
`apex/ops/bootstrap_service.py:859–898` — `mirror_bootstrap_progress`: status map, `SKIPPED →
ERROR` + `last_error="PHASE1_VERIFICATION_SKIPPED"`, 6 attempts with backoff **only** when
`"locked" in str(exc).lower()`; any other error is re-raised to the caller…
`apex/ops/bootstrap_service.py:900–1032` — `CanonicalMirroredCheckpoints.save_bootstrap`:
the research store is written and committed **first** (1010–1020), then
```
try: await mirror_bootstrap_progress(...)
except Exception: pass                # ← every mirror error, silently
```
(1023–1032). Note also the two evidence-merge `except Exception: pass` blocks (990, 1008)
documented under K-017.
`apex/ops/bootstrap_service.py:1165–1179` — `open()` installs the wrapper only when
`self._store is not None`; otherwise pure delegation (offline status).
`apex/research/checkpoints.py:146–172` — `ResearchCheckpointStore.save_bootstrap`, the
authority actually read by `status()`/`pending_cells()` (`cursor_ms=MAX(...)`,
`bars_ingested = old + excluded`, `payload_json=excluded.payload_json`).
`tests/unit/test_ops_bootstrap_service.py:714–781` —
`test_complete_run_mirrors_canonical_done_and_cursor` and
`test_budget_paused_mirrors_canonical_running_and_cursor` assert the mirror **on the happy
path only**; no test covers a failing mirror.
Callers/readers: `grep -rn "bootstrap_progress" --include=*.py` shows the canonical table is
written by the mirror and read by tests; `BootstrapService.status()` reads
`research_bootstrap_progress` through the runner. This corroborates the auditor's own caveat.

#### Reproduction (command, probe file, actual result)
Command: `python3 -B AUDIT/probes_V3b/K-021.py`; probe/output `AUDIT/probes_V3b/K-021.py|.out`.
Real wrapper, real `ResearchCheckpointStore`, real `SQLiteStore` (temp files; the canonical
table is dropped **in the temp copy** to produce a genuine SQLite failure rather than a stub):
```
A. canonical mirror cannot write
   caller saw exception = None
   research row         = status='COMPLETE' cursor_ms=1726444800000 bars=7
   canonical rows       = 'OperationalError: no such table: bootstrap_progress'
   service.status()     = completed=1 remaining=0   (reads the research table)
B. intact canonical table: SKIPPED then COMPLETE
   after SKIPPED  = [('BTCUSDT','1d','P1','2024-09-16T00:00:00.000Z','ERROR',5,
                      'PHASE1_VERIFICATION_SKIPPED')]
   after COMPLETE = [('BTCUSDT','1d','P1','2024-09-17T00:00:00.000Z','DONE',14,
                      'PHASE1_VERIFICATION_SKIPPED')]
   research row   = status='COMPLETE' cursor_ms=1726531200000 bars=14
```

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). Both halves reproduce exactly:
a total mirror failure is invisible to the caller, to `status()` and to the CLI, and a
`DONE` row keeps the stale `PHASE1_VERIFICATION_SKIPPED` error for ever. I keep S2 rather
than S1 for the reason the auditor states himself: I could not find an operational consumer
of `bootstrap_progress`, so today the damage is confined to the audit trail and to any future
resume that follows ISSUE-CP9-007's rule. Two additions of my own:
(i) the divergence is not only "different status" but **row absent entirely** while research
says COMPLETE; (ii) `bars_written` accumulates (`5 + 9 = 14`) on both sides, so a re-run of
the same cell double-counts the canonical bar total — the mirror cannot be used to verify the
row count it is supposed to attest.

#### Root cause
Two durable records of the same fact with no transaction, no receipt and no reconciliation:
the secondary write is attempted after the primary has already committed, and its failure is
converted into silence by a bare `except Exception: pass`. The retry policy inside
`mirror_bootstrap_progress` distinguishes lock contention from other errors carefully — and
then the caller discards that distinction. `last_error` uses `COALESCE(new, old)`, which is
correct for "do not lose an error" but wrong for "clear an error that no longer applies",
and no clearing policy exists.

#### Direct impact
`research_bootstrap_progress` and `bootstrap_progress` can disagree arbitrarily (including
one being empty) with no warning anywhere; an owner reading the canonical table sees ERROR /
stale `last_error` / accumulated `bars_written` for a cell the service calls COMPLETE.

#### Secondary effects and interactions (upstream/downstream)
Upstream, the same `save_bootstrap` carries the K-017 drop evidence, whose merge is also
wrapped in `except Exception: pass` — a single unhealthy store therefore loses both the
mirror and the evidence, silently, in one call. Downstream, ISSUE-CP9-007 designates the
canonical table as the **resume authority**: any future resume implementation that honours
that decision would read a row that may be missing or stale, and `pending_cells` (research
side) would disagree — the exact "silent COMPLETE" the auditor warns about. Interacts with
K-020 (readiness computed from the research table only) and K-016 (progress markers advanced
without confirmed durable state).

#### Contract and decisions
* `PHASE2_DECISION_LOG.md:170` (**ISSUE-CP9-007**, MAJOR, CLOSED-with-evidence): “the
  canonical table is the **resume authority**; the research table is the cell cursor but must
  mirror (ADR-P2-003 additive, ISSUE-CP9-002)”, implemented by `CanonicalMirroredCheckpoints`
  with the very `_canonical_upsert` and `6× retry on 'locked'` described above. A mirror that
  may silently not happen contradicts the decision's own premise: the authority may be
  missing while the non-authority says COMPLETE.
* `APEX_GEN5.md:18751` (Ch.5 read/write ownership): “**Fail-closed: on write failure, halt
  ingestion and alert; do not cache and retry silently.**” `except Exception: pass` is neither
  halt nor alert.
* `APEX_GEN5.md:18744–18746` (correction/purge audit events): every correction is “logged with
  event_id, timestamp, reason, and actor identity” — a `last_error` that survives a later DONE
  with no lifecycle rule is the opposite of a governed audit field.
* `APEX_GEN5.md:17276` requires Phase 1 to “checkpoint `bootstrap_progress`” — the canonical
  table is named normatively, so its write is not optional. Precedence: the APEX_GEN5 clause
  names the artefact; ISSUE-CP9-007 (owner decision, later and more specific) makes it the
  resume authority. Both are violated by a silent skip; neither is violated by the mirror
  mechanism itself.

#### Frozen status and non-frozen alternative
The wrapper, `mirror_bootstrap_progress` and `_canonical_upsert` are all in
`apex/ops/bootstrap_service.py` — **not frozen**. The two schemas are frozen
(`apex/data_catalog/**` DDL for `bootstrap_progress`, and the research migrations are the
checkpoint store's own), so the fix must not add columns to `bootstrap_progress`; a
reconciliation/outbox record must live in the non-frozen ops/checkpoint database (the same
place K-017's evidence rows and K-019's outbox would live).

#### Fix options (A/B/C…)
* **A (recommended)** — replace `except Exception: pass` with: record the failure (cell,
  status, cursor, exception reason) in a non-frozen `mirror_pending` table, mark the run
  DEGRADED with a named reason, and drain/reconcile the pending set at the start of the next
  save/run; expose a `mirror_divergence` count in `status()` so the CLI can refuse READY.
  Side effects: `status()` gains fields and a run that previously "succeeded" can now report
  DEGRADED — the two mirror tests (tests/unit/test_ops_bootstrap_service.py:714–781) still
  pass (happy path), but any test asserting an exact `status()` dict must be updated; new
  non-frozen table + migration; no frozen file, no hash change.
* **B** — make the mirror failure fatal (propagate the exception). Side effects: simplest and
  fully fail-closed, but a transient canonical-store problem would abort a long Phase-1 run
  after the research row is already committed, i.e. it converts a silent divergence into a
  loud stop without repairing anything; acceptable only with A's reconciliation.
* **C** — write both rows in one transaction. Side effects: only possible when both tables
  live in the same SQLite file (the tests use one path, but `db_path` and `checkpoint_path`
  are independent parameters), so it cannot be relied on; rejected as the primary fix.
* **D (`last_error`)** — set `last_error = excluded.last_error` (i.e. clear it) whenever the
  new canonical status is `DONE`, and keep COALESCE otherwise; or add an explicit
  `last_error_cleared_at` audit line in the ops DB. Side effects: changes the semantics of a
  frozen-DDL column's content — must be owner-approved as an explicit policy (the audit
  discipline says an error is never silently erased), which is why I keep it separate from A.

#### My recommendation
**A** now (visibility + reconciliation is what turns a silent divergence into a repairable
one), then **D** as an owner-approved `last_error` lifecycle policy. Do not ship **B** alone.

#### Acceptance and regression tests
1. Mirror write fails (table missing / locked beyond the 6 retries): the run reports a named
   DEGRADED reason, `status()` exposes a non-zero divergence count, and the CLI does not exit
   READY.
2. After the canonical store becomes healthy, the next save reconciles the pending entries;
   the two tables then agree on status **and** on the ISO cursor
   (`_iso_to_ms(cursor_open_time) == cursor_ms`, as the existing happy-path tests assert).
3. A locked canonical store still succeeds through the existing 6× backoff without producing
   a divergence entry (no regression of ISSUE-CP9-007's retry).
4. SKIPPED → DONE: `last_error` follows the approved policy explicitly (asserted either
   cleared or retained with a recorded reason), never left ambiguous.
5. Re-running an already complete cell does not double `bars_written` on either side, or the
   accumulation is documented and asserted as intentional.

---

## K-022 — repair cannot distinguish a transient venue failure from an exhausted retention window

#### Auditor claim (short quote)
> «`fetch_live_bar` همهٔ خطاهای fetch، حتی ۴۲۹/timeout را `None` می‌کند؛ اگر evidence نباشد `repair_one` بی‌تمایز `UNREPAIRABLE_VENUE_WINDOW_PASSED` می‌دهد. در probe ۴۲۹ گذرا، دقیقاً همین verdict و پیام «venue window passed» برگردانده شد؛ retention واقعاً تمام نشده بود.»
> — “`fetch_live_bar` turns every fetch error, even 429/timeout, into `None`; with no evidence, `repair_one` returns an undifferentiated `UNREPAIRABLE_VENUE_WINDOW_PASSED`. In the probe a transient 429 produced exactly that verdict and the ‘venue window passed’ message, while retention had not in fact expired.”

#### What I read (files, line ranges, functions, callers)
`apex/ops/partial_bar_repair.py:327–348` — `fetch_live_bar`: the docstring itself states
“Any venue failure — window passed, rate-limit exhausted, network error — is `None`”, and the
body is `except (ToobitPublicError, Exception): return None` (a clause that catches
everything, the first alternative being redundant). No retry, no classification, no logging of
the exception.
`apex/ops/partial_bar_repair.py:389–426` — `repair_one`: “1. LIVE first” →
`live = await fetch_live_bar(...)`; on `None` the evidence fallback runs; when neither yields
a replacement, `return {... "verdict": UNREPAIRABLE_VENUE_WINDOW_PASSED,
"detail": "venue window passed and no evidence entry"}` (423–425) — a single verdict with a
hard-coded causal claim.
`apex/ops/partial_bar_repair.py:119–129` — the verdict vocabulary: `VERIFIED_CLOSED`,
`CORRECTED`, `UNREPAIRABLE_VENUE_WINDOW_PASSED`, `REFUSED_OHLC_*`,
`REFUSED_EVIDENCE_MISMATCH`, `REFUSED_PARSE`, `SKIPPED_STILL_OPEN` — there is **no**
"venue unavailable / retry later" verdict.
`apex/ops/partial_bar_repair.py:457–525` — `run_repair`: still-open candidates are skipped
before any fetch (CP-13.1 / ISSUE-CP13-004); everything else goes through `repair_one`;
`counts["unrepairable"]` aggregates the single verdict.
`apex/ops/partial_bar_repair.py:281–320` — `find_candidates` (the real detector used by the
probe).
`scripts/run_apex.py:648–686` — the CLI prints `verdict=` per row and
`summary: … unrepairable=… refused=…`, writes the JSON report, and
`if counts["unrepairable"] == 0 and counts["refused"] == 0: return EXIT_READY` else
`EXIT_DEGRADED` — no cause is carried, so a rate-limited run and a genuinely unrepairable
history produce the same operator-visible outcome.

#### Reproduction (command, probe file, actual result)
Command: `python3 -B AUDIT/probes_V3b/K-022.py`; probe/output `AUDIT/probes_V3b/K-022.py|.out`.
A real partial bar is written to a temp `SQLiteStore` (`ingest_raw` of a bar that is still
open, i.e. `created_at < close`), detected by the real `find_candidates`, and offered to the
real `fetch_live_bar`/`repair_one` with four clients:
```
candidates found by the real find_candidates = 1
  cell=BTCUSDT:1h open=2026-09-29T01:00:00.000Z created=2026-09-29T01:47:24.540Z
HTTP 429 rate limit (transient)        fetch_live_bar=None  verdict='UNREPAIRABLE_VENUE_WINDOW_PASSED'
network timeout (transient)            fetch_live_bar=None  verdict='UNREPAIRABLE_VENUE_WINDOW_PASSED'
HTTP 500 server error (transient)      fetch_live_bar=None  verdict='UNREPAIRABLE_VENUE_WINDOW_PASSED'
healthy venue, window truly empty      fetch_live_bar=None  verdict='UNREPAIRABLE_VENUE_WINDOW_PASSED'
   (all four details: 'venue window passed and no evidence entry')
end-to-end run_repair (now_ms injected past the close, venue returning HTTP 429):
   counts  = {'candidates': 1, 'verified': 0, 'corrected': 0, 'unrepairable': 1, 'refused': 0}
   verdict = 'UNREPAIRABLE_VENUE_WINDOW_PASSED'
```
Four causally different situations, one verdict and one identical detail string; the CLI maps
all of them to `EXIT_DEGRADED` with `unrepairable=1`.

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). The behaviour is reproduced on
real code end to end, including through `run_repair` and the CLI counting. S2 rather than S1
because nothing incorrect is written to the store — `repair_one` refuses rather than
fabricates, the raw row is untouched, and the run exits DEGRADED, so the failure is
conservative. The harm is decision-quality: the verdict asserts a cause ("venue window
passed") that the code never established.

#### Root cause
The fetch layer erases the error class (`except (ToobitPublicError, Exception): return None`)
and the verdict layer then names a cause that only the erased information could justify. There
is also no retry at this layer, although the repository's own public client already implements
`RETRY_ATTEMPTS = 3` with `RETRY_BACKOFF_SECONDS = (1.0, 2.0, 4.0)` — the repair path discards
whatever it raises.

#### Direct impact
A repairable row is reported as permanently unrepairable whenever the venue is momentarily
rate-limited or unreachable, and the JSON report written to `data/` records that false cause
for the audit trail.

#### Secondary effects and interactions (upstream/downstream)
Upstream this is the CP-13 governed-repair path for exactly the partial bars that
ISSUE-CP13-001 left behind (the owner's 45/91 confirmed mismatches), i.e. the rows where the
operator most needs a reliable cause. Downstream the auditor's concern is the operator: told
the venue window has passed, the operator may abandon the row or reach for a manual/`--evidence`
correction that carries weaker provenance, when simply retrying later would have succeeded.
Interacts with **K-015** (an ambiguous venue silence read as a definitive state) and **K-019**
(a transient failure recorded in a side field and never retried) — the same class of
error-erasure. It does **not** interact with the immutable-raw guarantees: no write happens in
any of the failing branches.

#### Contract and decisions
* `APEX_GEN5.md:16978` — retry/fill discipline: “never to blind retry”; and
  `APEX_GEN5.md:18950` “**No blind retry after UNKNOWN exchange response**”. Read together
  with `APEX_GEN5.md:144/14738` (the governed 3× exponential backoff 1s/2s/4s), the contract's
  position is that an UNKNOWN response must be *classified*, not guessed — the current code
  does the opposite: it converts UNKNOWN into a definite negative conclusion.
* `APEX_GEN5.md:18744–18746` — “Every correction, revocation, or deletion is logged with
  event_id, timestamp, reason, **and actor identity**”: a logged `reason` that is not the
  actual reason defeats the clause.
* `APEX_GEN5.md:5068` — an unavailable/degraded status “MUST be carried as a degraded
  quality/provenance flag”, not resolved into a factual claim.
* `PHASE2_DECISION_LOG.md:182` (**ISSUE-CP13-001**) defines the repair path and its verdict
  set — `UNREPAIRABLE_VENUE_WINDOW_PASSED` / `REFUSED_*` — and requires the CLI to exit 0
  “iff nothing is left unrepairable or refused”. Precedence: the decision *names* the verdict
  but does not license using it for a transient failure; adding a distinct
  venue-unavailable verdict is additive and consistent with its exit rule (such a row is also
  "left unrepaired", so exit stays DEGRADED). CP-13.1 / ISSUE-CP13-004 already established the
  precedent that a non-repairable-yet row gets **its own** verdict (`SKIPPED_STILL_OPEN`) with
  a `closes_at` field telling the owner when to retry — exactly the shape the transient case
  needs.

#### Frozen status and non-frozen alternative
**Not frozen**: `apex/ops/partial_bar_repair.py` and `scripts/run_apex.py` are wiring, added
by CP-13 itself. The frozen public client (`apex/data_catalog/ingest/toobit_public.py`) needs
no change — its exceptions merely have to be *propagated* rather than erased.

#### Fix options (A/B/C…)
* **A (recommended)** — classify the failure in `fetch_live_bar` (return a small result object
  or raise a typed error: `EMPTY_WINDOW`, `RATE_LIMITED`, `TRANSPORT_ERROR`, `HTTP_5XX`),
  apply the governed 3× 1s/2s/4s backoff to the transient classes, and add a distinct verdict
  `UNREPAIRABLE_VENUE_UNAVAILABLE` (with `retry_after`/last error detail) kept separate from
  `UNREPAIRABLE_VENUE_WINDOW_PASSED` — mirroring the existing `SKIPPED_STILL_OPEN` precedent.
  Side effects: `run_repair`'s `counts` gains a bucket and the CLI summary/JSON report grows a
  field, so `tests/unit/test_ops_partial_bar_repair.py` (20 tests, several asserting exact
  verdicts and counts) and any stored report fixture must be extended; the exit rule stays
  DEGRADED for the new bucket, so no behaviour the owner relies on is weakened; no frozen
  file, no migration, no invalidated hash.
* **B** — keep one verdict but attach the real cause in `detail` (e.g. the exception type and
  message). Side effects: one-line change, immediately stops the false "window passed" claim,
  but machine consumers still see `unrepairable` and cannot select rows worth retrying.
* **C** — retry only, without classification. Side effects: hides most transients but still
  reports the wrong cause for the rest, and adds latency to genuinely empty windows.
* **D** — probe retention explicitly (fetch a nearby known-present bar to prove the venue is
  alive before concluding the window passed). Side effects: extra venue calls against the
  rate-limit budget; useful as a confirmation step inside A, not on its own.

#### My recommendation
**A**, with **B** as the same-day mitigation (stop asserting a cause that was not measured).

#### Acceptance and regression tests
1. Client raises `ToobitPublicError("klines", "HTTP 429 …")`: verdict is the new
   venue-unavailable class after the governed retries, not `…WINDOW_PASSED`; the store row is
   unchanged.
2. Client raises `asyncio.TimeoutError` and, separately, an HTTP 500: same treatment, each
   with its cause recorded in `detail`.
3. Healthy client returning an empty window: verdict stays
   `UNREPAIRABLE_VENUE_WINDOW_PASSED`, and the test asserts the venue was actually reachable.
4. Valid `--evidence` entry present: the evidence fallback still wins over a transient failure
   (existing F6a/F6b behaviour preserved, with the store-equality gate).
5. Counts/exit: transient-only run exits DEGRADED with the new bucket non-zero and
   `unrepairable` (window-passed) zero; a clean run still exits READY.
6. No branch of the failing paths performs any write (`correct_raw` not called).

---

## K-023 — the repair report can be silently overwritten, and losing it does not stop exit READY

#### Auditor claim (short quote)
> «نام JSON repair فقط دقت ثانیه دارد و CLI با `open(...,"w")` می‌نویسد؛ دو dry-run/apply در همان ثانیه گزارش قبلی را overwrite می‌کنند. اگر نوشتن گزارش بعد از correction شکست بخورد، صرفاً «UNWRITABLE» چاپ می‌شود و در نبود refusal، exit همچنان READY است؛ raw_revision شاهد محدود دارد ولی فهرست تمام verdictهای بررسی از دست می‌رود.»
> — “The repair JSON name has only second resolution and the CLI writes with `open(...,"w")`; two dry-runs/applies in the same second overwrite the earlier report. If writing the report fails after a correction, it merely prints ‘UNWRITABLE’ and, absent a refusal, the exit is still READY; `raw_revision` keeps limited evidence but the full list of verdicts is lost.”

#### What I read (files, line ranges, functions, callers)
`apex/ops/partial_bar_repair.py:527–533` — `report_filename`:
`strftime("%Y%m%dT%H%M%SZ")` → **second** resolution, no run id, no counter.
`scripts/run_apex.py:665–682` — the writer:
```
data_dir = REPO_ROOT / "data"
data_dir.mkdir(parents=True, exist_ok=True)
leaf = PR.report_filename()
with open(str(data_dir / leaf), "w", encoding="utf-8") as handle: json.dump(...)
except OSError as exc: _say(f"  report: UNWRITABLE ({exc}) — counts above still stand")
```
— truncating open, no `x` mode, no temp-file + `os.replace`, no fsync, no hash/receipt.
`scripts/run_apex.py:683–686` — the exit rule depends **only** on
`counts["unrepairable"] == 0 and counts["refused"] == 0`; the report outcome is not an input.
`apex/ops/partial_bar_repair.py:457–525` — `run_repair` returns the verdict rows that exist
nowhere else once the process exits (the store keeps only `raw_revision` rows for *corrected*
bars — VERIFIED/UNREPAIRABLE/REFUSED/SKIPPED rows leave no durable trace).
`tests/unit/test_ops_partial_bar_repair.py:379–384` — `test_report_filename_shape` pins the
second-resolution name; `:482–503` — `test_cli_verified_exits_zero_and_writes_report` asserts
`len(reports) == 1` after **one** run, so the overwrite is untested rather than intended.

#### Reproduction (command, probe file, actual result)
Command: `python3 -B AUDIT/probes_V3b/K-023.py`; probe/output `AUDIT/probes_V3b/K-023.py|.out`.
The real CLI `run_apex._repair_partial` with `REPO_ROOT`/`APEX_SQLITE_PATH` redirected to a
temp directory (exactly the repository's own CLI-test technique — the repo's `data/` is never
touched), the real store seeded through the repository's own fixture helper:
```
A. 2026-09-16T12:00:00.100000+00:00 -> repair_partial_report_20260916T120000Z.json
   2026-09-16T12:00:00.900000+00:00 -> repair_partial_report_20260916T120000Z.json
   identical = True
B. run 1 exit=0  summary: candidates=1 verified=1 …  report: data/…T014948Z.json
   run 2 exit=0  summary: candidates=1 verified=1 …  report: data/…T014948Z.json
   report files after two runs = 1
C. report directory read-only (fresh create):
   verdict=VERIFIED_CLOSED …
   report: UNWRITABLE ([Errno 13] Permission denied: …) — counts above still stand
   exit code = 0  (EXIT_READY=0)
```

#### Verdict and reasoning
**CONFIRMED — independent severity S2** (auditor S2 retained). Both halves reproduce against
the real CLI. S2, not higher: no incorrect data is written to the store, the correction path
itself is unaffected, and `raw_revision` still records applied corrections; what is lost is
the audit artefact and the dry-run↔apply comparison.

#### Root cause
The report is treated as a print-out rather than as evidence: its name is a wall-clock string
with a resolution coarser than the operation it identifies, the write is a truncating
non-atomic `open(..., "w")`, and its success is not part of the command's success criterion.

#### Direct impact
Two runs in the same second (trivially achievable — the probe's two dry runs took far less
than a second) leave exactly one file, silently; an unwritable/full filesystem after an
`--apply` run yields exit READY with no artefact recording what was corrected, verified or
refused.

#### Secondary effects and interactions (upstream/downstream)
Upstream: the operator's standard procedure for CP-13 is dry-run → inspect → `--apply`; both
runs are named by the same scheme in the same directory, so the *comparison* artefact is the
one most likely to be destroyed. Downstream: **K-022**'s cause-less
`UNREPAIRABLE_VENUE_WINDOW_PASSED` rows exist only in this report — losing it removes the only
record that they were examined at all. Also related to **K-017**/**K-021**: evidence written
outside a transaction and allowed to fail quietly.

#### Contract and decisions
* `APEX_GEN5.md:18744–18746`: “Every correction, revocation, or deletion is logged with
  event_id, timestamp, reason, and actor identity. Purge decisions are approved … and
  **recorded before execution**.” A correction whose report silently vanishes (or is
  overwritten by a later run) does not satisfy “recorded”.
* `APEX_GEN5.md:18751`: “Fail-closed: on write failure, halt … and alert; do not cache and
  retry silently.” The report write failure produces neither a halt nor a non-zero exit.
* `APEX_GEN5.md:18736–18740` (backup/restore integrity: manifests, re-hash on restore) sets
  the repository's own standard for durable artefacts — a hash/receipt is expected, and the
  report has none.
* `PHASE2_DECISION_LOG.md:182` (**ISSUE-CP13-001**) specifies the repair CLI, its verdicts and
  “exit 0 iff nothing is left unrepairable or refused”. Precedence: the decision defines the
  *exit rule*, and it is silent about the report's durability — so tightening the artefact is
  additive and does not contradict it. Note that making a lost report non-READY is a *change*
  to that exit rule and therefore needs owner sign-off; the alternative (own exit code /
  explicit REFUSED verdict) keeps the decision's wording intact.

#### Frozen status and non-frozen alternative
**Not frozen** — both files are CP-13 wiring. No frozen DDL is involved; the report is a plain
file under `data/` (which this audit never touches).

#### Fix options (A/B/C…)
* **A (recommended)** — make the artefact unique and atomic: leaf name
  `repair_partial_report_<ISO-ms>_<run_id>.json` (run id = a uuid4/ULID also embedded in the
  JSON), write via `tempfile` + `os.replace` after `fsync`, create with `O_EXCL`, and add a
  `sha256` of the payload to the printed summary. Side effects:
  `test_report_filename_shape` (tests/unit/test_ops_partial_bar_repair.py:379–384) and the
  CLI test's glob/`len(reports) == 1` assertion must be updated; any owner tooling that
  globs the old name keeps working (the prefix is unchanged); no frozen file, no migration.
* **B** — keep the name but refuse to overwrite (`open(..., "x")`, falling back to a `-2`
  suffix). Side effects: minimal, removes the silent data loss, but still no atomicity or
  receipt.
* **C** — treat a failed report write as a non-READY outcome (its own exit code or a
  `REFUSED_REPORT_UNWRITABLE` verdict row) — **owner decision required** because it alters
  ISSUE-CP13-001's exit rule. Side effects: an `--apply` run that corrected rows correctly
  would now exit non-zero; this is the honest signal (the corrections are already committed
  and must never be rolled back blindly, which the auditor also stresses), but it must be
  documented so the operator does not re-run `--apply`.
* **D** — persist the verdict rows in the non-frozen ops database instead of (or in addition
  to) the JSON file. Side effects: new table + migration; makes the audit trail independent of
  the filesystem; the natural companion to A.

#### My recommendation
**A + C** (unique atomic artefact with a receipt, and a failed write that is not READY), with
**D** as the durable follow-up so the verdict history survives regardless of `data/`.

#### Acceptance and regression tests
1. Two runs inside the same second produce **two** distinct report files, both readable and
   both listing their own run id.
2. `--apply` followed by a read-only `data/`: the command reports the failure with a named
   verdict/exit that is **not** READY, while the already-committed corrections are neither
   rolled back nor repeated on a re-run (idempotence, as CP-13 already requires).
3. The written file's recorded sha256 matches its bytes (receipt verification).
4. A partially written report can never be observed (kill between write and rename leaves
   either the old file or the complete new one).
5. Existing CP-13 CLI expectations (`verified=1` exit 0, evidence-fallback path) remain green
   with the new naming.
