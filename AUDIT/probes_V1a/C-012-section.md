## C-012 — formal verdict

### Auditor claim (short quote)

“runner تا ابد همان cursor را ... retry می‌کند” — persistent rate-limit responses cause uncapped retries at the same cursor. The full row distinguishes bounded walk retries from the outer loop, capped delay from capped attempts, and successful-page budget from request/time budget. Full row read from `/tmp/AUDIT.md`. Auditor S1.

### What I read (files, line ranges, functions, callers)

Full ToobitKlineSource including __call__, backward walk, _get_klines_with_walk_backoff, _get_klines and AsyncBridge (bootstrap_service.py:245–818); entire frozen research/bootstrap.py:1–438 including command/pause/resume/run_phase1; full service caller/exception/report/checkpoint closure described under C-008/C-010. Direct frozen client constructor/session/_get/get_klines (toobit_public.py:174–295) and wire parser (122–172) reviewed, without constructing a network client. Checkpoint DDL/bootstrap methods: checkpoints.py:1–203. Consumers: `remaining-consumers.out`. Complete referenced persistent-limiter test (bootstrap tests:228–244), finite-recovery runner test and fixture (research tests:206–245), no-rewind/pause tests (246–280) read. CLI/bootstrap caller already read under C-002.

### Reproduction (command, probe file, actual result)

`PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-012.py`; raw `C-012.out`, exit 0. Native service, runner, source, AsyncBridge, actual checkpoint/canonical writes and frozen parser/store recovery. Async venue double raises ToobitPublicError with **code=-1003** or **HTTP 429**. Inner retry tuple `(0,0,0)` preserves four attempts per walk while removing real delays; outer delays `.01,.02,.03` preserve last-slot saturation. Source max_pages=1.

On the repository-DDL **200,000 market + 200,000 raw-row** fixture, repeat each refusal with neither/both supplied device indexes:

- At 0.32 seconds, all four scenarios still run: **48 client calls = 12 outer backoffs × 4 inner attempts**, **0 source pages**, zero ingested bars; checkpoint **IN_PROGRESS** at the original cursor `1788220800000`.
- Explicit native `runner.command('pause')` ends the -1003 case and saves **PAUSED** at the same cursor. The loop is not claimed unstoppable.
- Explicit task cancellation ends the 429 case during an async backoff; checkpoint remains **IN_PROGRESS**, same cursor, zero bars. This is external audit cancellation, not a production retry timeout or automatic PAUSED state.
- Fresh service/source on each same checkpoint, with the refusal removed, ingests **all three** fixture bars and returns **COMPLETE**, cursor `1788220980000`, two client calls for the backward walk. Recovery is measured once per action (without device indexes); both index configurations independently reproduce uncapped refusal behavior.

Captured refusal-path SQL: per-cell frontier `MAX(as_of)` uses **covering idx_raw_sym_tf_asof SEARCH** in both modes; no unindexed large-table scan occurs here. No market/PIT query is needed for a rejected page. The index pair cannot cap a Python retry loop. Recovery ingest/checkpoint behavior is native; its detailed SQL plan coverage is in C-010 rather than falsely presented as traced here. No model, order, secret, real venue rate limit or battery drain.

Guarded `python3 -m pytest -q -p no:cacheprovider tests/unit/test_ops_bootstrap_service.py::TestKlineSource::test_rate_limit_surfaces_when_walk_retries_exhaust tests/unit/test_research_bootstrap.py::TestPhase1::test_rate_limit_backs_off_and_never_skips`: **2 passed in 0.30s**, `C-012-pytest.out`; native and pytest guard attempts **[]**.

### Verdict and reasoning

**CONFIRMED / S1.** Bounded observation plus complete loop reading proves there is no intrinsic attempt/deadline termination while rate limits persist. A finite experiment cannot literally observe infinity; it demonstrates repeated outer cycles beyond the inner bound and then is deliberately terminated. No device/network duration is extrapolated from scaled delays. Explicit pause/stop checks do exist, and asynchronous backoff is cancellable; lack of an automatic bound is not lack of all control mechanisms.

### Root cause

Source returns -1003 after exhausting its own attempts without incrementing pages_served. Runner increments backoffs, selects `backoff_seconds[min(count-1,last)]`, awaits that delay, and continues without advancing cursor or successful-page count. A saturated delay is not a global retry budget. A fresh source call begins another walk. The public client's own finite retry layer can add attempts underneath this loop but cannot terminate the outer one.

### Direct impact

Persistent throttling can keep acquisition pending indefinitely despite max-pages=1, with no completed-page progress and no automatic named retry-later result. Existing durable cursor is retained. Real request load/time depends on client, walk and outer delay settings; the 48 synthetic **client-method** calls are not claimed to be 48 actual HTTP requests.

### Secondary effects and interactions (upstream/downstream)

C-008 full backward walks may restart after a failed walk because no completed history is cached; traffic budget must include partial walks. C-010 resource checks stay stale during those repeated retries. Normal control routing must remain reachable during synchronous bridge/walk sleeps; the probe only proves controls during async outer waits, not production Telegram responsiveness.

**ISSUE-076:** ingestion/backfill costs follow a successful page; no data replay or row batching cap ends the rate-limit branch. **ISSUE-077:** lack of progress resembles that symptom but is not the DB-lock/ladder or gather cause; explicit persisted pause should not be confused with cancellation leaving IN_PROGRESS. **ISSUE-079:** fingerprint joins are unrelated to this refusal loop; reducing their latency will not change retry termination. No new X finding is assigned.

### Contract and decisions

APEX_GEN5.md:17276 requires “−1003 backoff, do not skip”, page checkpoints and resume-never-rewind; W.8 requires owner controls/persistent state. It does **not** mandate infinite retry in one invocation or give a numeric total retry cap. PHASE2_DECISION_LOG.md:176 authorizes bounded **walk-internal** backoff and runner-facing max-pages, not a global HTTP cap; CP13 frontier semantics remain later authority. A named resumable pause at unchanged cursor is consistent with never-skip; marking the cell COMPLETE/SKIPPED or advancing its cursor on throttle is not.

### Frozen status and non-frozen alternative

Outer runner and public catalog client are frozen. A change there needs owner permission. Service/source wrappers are non-frozen and can enforce an end-to-end wall/attempt budget, issue an existing pause command and preserve a pending cursor, with a named owner-facing reason. Retry-After exposure may require an authorized frozen-client change if no current interface carries it; do not pretend the string-only marker already provides headers.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

**A — governed global attempt/elapsed-time budget and named resumable pause in non-frozen wiring.** Count all relevant attempt layers, scope/reset explicitly by run/cell/progress, surface reason and retry-not-before without returning a fake empty success page. Existing PAUSED/checkpoint payload can represent state without changing frozen status enums; new durable policy metadata may need versioning, not raw data migration. Cancellation must not leave bridge work writing/publishing after its generation is obsolete. Adds counters/telemetry and possible scheduling delays; finite transient-recovery tests must remain valid below the cap, persistent-source tests should now assert bounded pause and same cursor.

**B — externally bounded jobs with fresh service restart at durable cursor.** No frozen edit and possibly no schema change; can bound process duration but wastes partial backward walks, loses process-local diagnostics and does not automatically produce a clean PAUSED receipt. Requires a supervisor, explicit termination/report policy and no concurrent writers. Safer than unbounded unattended retry but not complete in-process handling.

Reducing sleep to zero or skipping a throttled cell is not an acceptable fix. Global budgets must respect venue cooldown rather than amplify a 429 storm. No training/model changes or retraining are required; successful recovered rows, content hashes and PIT availability must remain identical. Preserve dedup, correction lineage and CP13 frontier semantics; never forge availability timestamps to disguise retry latency.

### My recommendation

A, using existing pause semantics and explicit audit reason; define budget/cooldown with owner approval rather than invent a numeric SLA. Keep bounded walk retries as a separate local defense and test the full layered path.

### Acceptance and regression tests

Always-limited -1003 and 429 fixtures must reach named resumable PAUSED/RETRY_LATER within the configured whole-invocation budget, with unchanged cursor and no false COMPLETE. Remove the limit and verify all rows exactly once after restart. Test pause, stop, cancellation during async waits and synchronous bridge activity, partial-walk recovery, Retry-After where exposed, and resource-pressure interaction. Keep native ≥200k-store frontier plans in both modes; no device throttle duration or battery impact is certified here.
