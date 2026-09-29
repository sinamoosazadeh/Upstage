## C-008 — formal verdict

### Auditor claim (short quote)

“پیش از تحویل اولین صفحه ... همهٔ تاریخچهٔ سلول” — the whole cell history is collected before the first delivered page. The full row also alleges repeated full-history filtering per delivered page, retained histories across cells, and repair's unfiltered fetchall even with `--cells`; it explicitly disclaims phone OOM evidence. Full row read from `/tmp/AUDIT.md`, not an index. Auditor S1.

### What I read (files, line ranges, functions, callers)

Complete ToobitKlineSource and its helper closure (bootstrap_service.py:1–826), service construction/open/fetch/ingest/run/status/report and frontier/checkpoint wrappers (827–1455); catch_up (1456–1565) was fully read for C-006; reporting tail 1566–1680 read across bounded chunks. Complete partial_bar_repair.py:1–544, including find_candidates, run_repair, live/evidence fallback and correct_raw call boundary. Complete frozen BootstrapRunner module (research/bootstrap.py:1–438); checkpoint DDL/lifecycle/bootstrap save/read methods (checkpoints.py:1–203). Native store DDL/ingest/get_window were reviewed under C-006 and ingest rechecked here. CLI bootstrap/repair callers were read under C-002; consumer grep saved in `remaining-consumers.out`. Relevant complete test functions: bootstrap tests at 228–244, 339–355 and tail-aligned venue/helper definitions; both entire related test files were executed, not claimed entirely line-by-line reviewed.

### Reproduction (command, probe file, actual result)

`PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-008.py`; `C-008.out`, exit 0. Real imported source, AsyncBridge thread and frozen wire parser; a **lazy async venue double** synthesizes only each requested page, avoiding an independently growing venue-side list. No AST source extraction, no venue contact. Measurements include tracemalloc overhead and are not phone timings.

- 10,000 bars: first 1,000-row delivery requires **10** client calls; cache 10,000; retained traced heap delta **9,748,050 B**, first-page time **4.215 s**.
- 20,000 bars: **20** client calls; cache 20,000; heap **19,097,088 B**, **8.585 s**. Both use max_pages=1; the *second* delivered-page request correctly refuses PAGE_BUDGET_REACHED after the full first walk. No extra empty HTTP page is needed because this fixture ends exactly at DEEP_START.
- 100,000 bars × **two cells**: 100 then 200 total client calls; retained histories 100,000 then **200,000** observations, heap **95,402,820 then 190,796,168 B** after GC. First deliveries take **39.741/38.205 s** with tracing. There is no global history eviction between these cells.
- Five subsequent pages from the cached 100k cell make no new client calls but invoke the real timestamp parser **500,010** times (100k history visits + two boundary parses per page), **3.885 s** without tracemalloc. A delegating counter calls the original parser; it does not reimplement source logic. This measures O(N) traversal per delivered page; O(N²/1000) complete-drain traversal follows from N/1000 pages, not a claimed measured full-drain time.

Repair uses **repository DDL with 200,000 market + 200,000 raw rows**, 1,000 PIT facts and 100 ledger records, all temporary. Actual `find_candidates(store,[('BTCUSDT','1m')])` returns 10,000 candidates but its captured SQL has no symbol/TF filter and materializes the entire CLOSED join first. Without/with both exact device indexes: **4.634/4.832 s**, peak traced allocation **159,103,868/158,716,615 B**. Both EQPs: **SCAN r → PK SEARCH m**. The market symbol/TF/open index cannot serve a missing predicate; the PIT index is irrelevant here. These allocation peaks are not permanent post-GC leak measurements. No repair/apply or external fetch occurs.

Guarded `python3 -m pytest -q -p no:cacheprovider tests/unit/test_ops_bootstrap_service.py tests/unit/test_ops_partial_bar_repair.py`: **97 passed in 4.51s**, raw `C-008-pytest.out`. Native and pytest guard attempts **[]**.

### Verdict and reasoning

**CONFIRMED / S1.** Native measurements replace the auditor's AST-only source experiment and demonstrate first-page traffic, history growth and repeated scanning. Later owner direction explicitly makes max-pages a **runner-page** budget: exceeding it in HTTP calls is not itself a breach of that approved definition. The confirmed defect is absent independent resource/traffic bounding, not an allegation that the current budget implementation contradicts its documented meaning. Synthetic 100k/cell is a stress case, not a claim that today's venue actually retains that much per cell.

### Root cause

_walk_backward accumulates a dict and seen set, then sorted history; __call__ scans history and builds eligible on every request. Histories survive cell completion. `begin_catch_up` clears the selected cell on a new catch-up; increasing end replaces that cell history, neither is a fixed global bar/memory bound. Repair fetchall precedes Python cell selection and skew predicates.

### Direct impact

No runner-page checkpoint can be reached before the initial source walk returns; traffic and memory scale with retained source history, not max-pages. A restricted repair still pays the full CLOSED join/materialization cost. An initial IN_PROGRESS checkpoint can already exist before walking, so “no checkpoint at all” would be too broad.

### Secondary effects and interactions (upstream/downstream)

Upstream tail alignment and CP-12 poison evidence forbid blindly taking a forward venue window or truncating at a guessed cap. Downstream runner cursor, CP-13 store frontier/served_upto and empty-page completion must remain coherent. Replacing an exhausted resource budget by `rows=[]` would falsely certify completion. Repair must preserve calendar close/skew checks, immutable raw revisions, evidence matching and idempotency.

**ISSUE-076:** per-row ingestion/quality commits are downstream, additive costs; neither batching nor market/PIT indexes bounds this source cache. **ISSUE-077:** boot/migration locks and gather-before-persist are separate; this source can delay first progress before that gather stage is even reached. **ISSUE-079:** repair shares the expression-join identity pattern, but its measured plan remains raw-scan→market-PK in both modes; do not assume C-006's indexed nested-raw plan here. This is resource behavior of an already audited row, not a new X finding.

### Contract and decisions

APEX_GEN5.md:17251–17279 requires all available history, per-page checkpoints, “Resume from cursor, never rewind”, and “−1003 backoff, do not skip”; hardware estimates are not start requirements. PHASE2_DECISION_LOG.md:176 (CP11-001) expressly mandates backward adaptation and **runner-facing** max-pages. CP12 owner decision (181) accepts OHLC-drop-with-evidence; CP13 (183) replaces cursor-only serving with frontier/closed-bar semantics; CP13.1 (189–190) preserves still-open repair protection. Those later decisions take precedence over the earlier simple forward-paging interpretation. Memory/latency acceptance still needs target-device evidence (contract 18445–18451, 18883–18885).

### Frozen status and non-frozen alternative

Source/repair/service are non-frozen. Research bootstrap and catalog/parser/store are frozen; do not edit them without owner permission. A bounded non-frozen disk spool/source adapter and SQL-filtered repair can retain the runner and correction APIs. Any new spool schema belongs to an explicitly additive non-frozen migration, not the frozen store migration list.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

**A — bounded durable backward spool, ascending delivery cursor, independent traffic/time budget; filtered keyset repair.** Preserves coverage while reducing memory and repeated traversal. Adds disk/write load, staging identity/version, crash/resume recovery and migration/cleanup policy; cannot purge spool until ingestion/checkpoint acknowledgement. Retain invalid-bar evidence and fresh re-fetch of formerly open bars. Repair ordering must be stable through corrections, with exactly-once event identity and equivalent candidate output. Tests asserting runner-page budgets stay valid; add independent walk-budget tests rather than silently reinterpret max-pages.

**B — index cached open times / ascending delivery offset and release completed cell caches.** Non-frozen, no required DB migration, reduces repeated traversal/cross-cell retention but leaves the first walk and one large cell unbounded. Reuse must account for changing end, frontier reset and failed-ingest retry; stale open snapshots must never become final data. SQL filtering helps repair but does not bound a huge selected cell unless batched.

Neither pure parity option changes native values, content/replay hashes or training protocol; no retraining is required. If historical coverage is deliberately reduced, owner permission and new completeness/input identities are necessary; training/default D30 scope (20 cells, not 140) must not silently change. Regressions must include warm/cold/restart equality, poison counts, dedup and correction lineage.

### My recommendation

A, with B only as a measured interim reduction. Preserve CP11–13 semantics, introduce named resumable exhaustion rather than empty-page completion, and budget disk spool as well as RAM.

### Acceptance and regression tests

Retain ≥200k-row repair EQPs in both index modes and two-cell 200k-bar venue stress; verify fixed working-memory/traffic bounds and exact coverage with interrupted walks/resume. Enforce no false COMPLETE on resource/rate-limit stop, no duplicate/omitted observations, valid open-to-closed refresh and all existing 97 regression tests. Measure actual target-device heap/RSS, first-checkpoint delay and operator responsiveness separately; no OOM threshold/time is inferred here.
