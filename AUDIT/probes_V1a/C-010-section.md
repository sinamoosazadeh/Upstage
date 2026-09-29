## C-010 — formal verdict

### Auditor claim (short quote)

“free-disk و battery تنها هنگام شروع run() سنجیده” — disk and battery are measured only at run entry, not repeatedly during ingestion. The full row names per-observation commits, distinguishes PAPER's 15% storage guard, and makes physical exhaustion conditional. Read full row from `/tmp/AUDIT.md`. Auditor S1.

### What I read (files, line ranges, functions, callers)

Complete BootstrapService lifecycle/run and direct `_fetch`, `_ingest`, probes, checkpoint mirror/report/status closure (bootstrap_service.py:827–1455), full source and helper class (1–826), full frozen research/bootstrap.py (1–438). In particular service.run:1410–1424 calls disk **twice at entry**, battery once; run_phase1:249–302 receives scalar/snapshot values. Full ingest_observations/_count_raw:1040–1076 and frozen SQLiteStore.ingest_raw:383–445; repository DDL and checkpoint bootstrap DDL/save/load/open:1–203 reviewed. CLI bootstrap composition was read for C-002; full PAPER storage/control path for C-006. Shared consumers search: `remaining-consumers.out`. Complete relevant test classes/functions read: TestProbes (bootstrap service tests:539–563), TestHardwarePreflight (research tests:24–85), initial disk/battery tests (292–313). Entire related test files were run, not claimed fully line-by-line reviewed.

### Reproduction (command, probe file, actual result)

`PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-010.py`; `C-010.out`, exit 0. Native **BootstrapService → BootstrapRunner → ingest_observations → SQLiteStore.ingest_raw** plus actual research/canonical checkpoint writes. Repository-DDL fixture begins with **200,000 market and 200,000 raw rows**, 1,000 PIT facts and 100 ledger records; three new rows per scenario are really committed. The only resource/venue seams are local injected probe values and parsed synthetic pages. No real disk exhaustion, battery command, external network or orders.

Each scenario starts with 513 MB and 50% battery unplugged, continuous mode explicitly on. Immediately before page two is returned, the resource source changes either to **511 MB** or **4% battery**. Three one-row data pages and one terminal empty page execute. Repeat both cases with neither device index and with both exact indexes:

- Every run: **disk probe count 2, battery count 1**; **3 bars ingested, status COMPLETE**, durable checkpoint bars=3 at the terminal cursor.
- The last two data writes occur after the injected low-resource transition. Re-evaluating the **actual native hardware_preflight** against current values returns **PAUSE**, reason FREE_DISK_BELOW_512MB or CONTINUOUS_BATTERY_BELOW_5PCT.
- A new invocation with the same low resource returns **PAUSED** with no additional source call. The entry guard exists and works; it is stale within an invocation.

Captured actual ingest SELECT EQPs in both configurations: `_count_raw` uses **covering idx_raw_sym_tf_asof SEARCH**; content_hash dedup uses **unique raw content-hash index SEARCH**. No unindexed large-table SELECT appears in this measured ingestion path. The count still traverses the matching cell's indexed entries. Neither supplied market/PIT index participates in these raw predicates. Checkpoint methods use primary-key lookup/upsert and ordered small progress tables; the detailed captured EQPs are for the main store connection, not a falsely claimed trace of its separate checkpoint connection. Results are resource-control evidence, not ingestion throughput claims.

Guarded command: `python3 -m pytest -q -p no:cacheprovider tests/unit/test_research_bootstrap.py tests/unit/test_ops_bootstrap_service.py::TestProbes`; raw `C-010-pytest.out`: **46 passed in 0.43s**, guard attempts **[]**. Native guard attempts also **[]**. Existing tests assert initial thresholds and probe parsing; they do not test a resource transition during a run.

### Verdict and reasoning

**CONFIRMED / S1.** Two near-simultaneous disk reads are not periodic monitoring. The native ingestion path continues committing after a transition that the existing preflight would pause if refreshed. This confirms the audit's conditional long-run safety gap, not a measured disk-full failure, battery-drain rate, corruption or lost row. Exact probe cadence/reserve policy is not specified by W.6 and needs an explicit implementation/owner policy; do not invent a contractual per-row sampling interval.

### Root cause

Mutable device resources are converted to run-entry values. Neither the frozen paging loop nor non-frozen ingestion wrapper samples them again. Individual raw observations commit before the containing page's checkpoint. The separate PAPER cycle storage guard is not called by standalone bootstrap.

### Direct impact

A long successful run may continue writing below the operational pause threshold until it ends or an actual storage/process failure occurs. Initial successful preflight in the report can conceal later deterioration. This experiment observes continued successful writes under simulated low-resource readings, not physical exhaustion.

### Secondary effects and interactions (upstream/downstream)

C-008's long first walk can consume time/resources before a runner page returns; a guard only at page-write boundaries would not supervise that walk. Downstream, a mid-page stop must not advance the page cursor over an uncommitted suffix. Already committed raw rows need duplicate-safe replay and accurate counters, not deletion or fabricated completion.

**ISSUE-076:** per-row commits and quality backfill amplify write/resource cost; batching must preserve coverage and checkpoint semantics. **ISSUE-077:** durable state/lock contention matters to a pause that must persist before disk fills; this probe does not reproduce boot lock or gather failures. **ISSUE-079:** fingerprint/read stalls can delay independent operational monitoring, but its expression join is not the cause here. User D57's disk-floor PAUSE/durable L1/L2 roadmap does not show that this bootstrap invocation already has periodic W.6 monitoring; do not substitute PAPER's percentage guard for the bootstrap absolute floor.

### Contract and decisions

APEX_GEN5.md:17276–17279: per-page checkpoint and never-rewind; “pause if free disk < 512 MB”, continuous pause below 5% unplugged; missing battery API “do not skip”. Nightly 15% skip is a distinct policy; the test deliberately uses continuous mode, not an assumption that Phase 1 is a nightly job. W.7's 20 GB is explicitly an estimate, not a hard start requirement. W.8 (17302–17314) requires persistent state/owner controls. Later CP11–13 frontier/closed-bar decisions preserve ingestion identity and coverage; none identified authorizes ignoring a later threshold breach. Frozen module status constrains the repair, not the verdict.

### Frozen status and non-frozen alternative

Research/bootstrap.py and catalog/store are frozen; owner permission required for edits there. Service/probe/wrapper code is non-frozen. A non-frozen resource supervisor/admission wrapper can pause or stop safely at a durable boundary using the existing command surface; an additive progress reason may require a separate governed state field, not a silent change to frozen status CHECK constraints.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

**A — fresh bounded resource checks before page admission/write plus independent walk supervision.** Cache probes only for a documented short interval; sample actual DB/WAL/spool filesystem, not an arbitrary current directory. Reserve enough headroom to commit a pause/checkpoint; a sampled free-space number cannot guarantee an arbitrarily large page fits. Blocking Termux probes have cost/timeouts and must not starve controls. Pause at an acknowledged page boundary, or abort before its uncommitted suffix with durable retry semantics. If a source page was fetched but not ingested, served_upto must reset to persisted frontier on resume. Tests need resource-transition injection; no existing threshold/absent-battery/parity test should weaken.

**B — bounded invocation/page chunks with fresh entry preflight between them.** Can reduce the stale interval without editing frozen runner, but max-pages is delivered pages, not C-008 walk traffic; not complete coverage during a long fetch. Repeated source initialization increases HTTP, hash lookups and checkpoint writes. A reused source's cumulative pages_served must not make every subsequent chunk refuse immediately. No DB schema necessarily needed, but restart/resume coverage proof is mandatory.

Both options must keep original raw/PIT hashes, canonical correction identities and training inputs; no retraining is inherently required. New pause metadata should be additive/versioned and not rewrite historical checksums. Changing frozen transaction/runner behavior needs owner authorization; a safe wrapper is preferable. Battery API absence stays unknown/proceed, never fabricated zero.

### My recommendation

A, with separately bounded fetch/walk work and explicit safe persistence reserve. B is an interim only. Preserve exact W.6 thresholds and separate continuous/nightly meanings; do not silently elevate the W.7 hardware estimate into policy.

### Acceptance and regression tests

Re-run these native ≥200k-row tests in both index modes: threshold transition before page two must produce a named safe pause without writing that next page, while prior rows/cursor remain valid. Add partial-page failure, retry dedup, storage-pressure during pause persistence, charging changes, absent/malformed battery and bounded probe timeout. Verify state after restart, no skipped suffix, unchanged hashes and no false COMPLETE. Keep initial floor/battery tests and measure real device probe overhead/WAL headroom separately. No real storage fault or battery life has been measured here.
