# PHASE2 HANDOFF — CP-9 operational wiring (long-run bootstrap command · Telegram receive gateway · 24/7 PAPER loop)

## STATUS
LAW-ACK: G1..G20 + P1..P21 read 2026-09-14T23:25:26Z
DELIVERED (historical CP-9 base, local): the three operational pieces are in-tree and green.
The base suite at that close was **2627 passed** (was 2553 at the CP-8 closeout; +74 tests:
72 wiring +2 canonical mirror). Nothing reaches a network in any test. ISSUE-CP9-006 is
closed by the appended HANDOFF_BRIDGE increment below.

## DELIVERED
| # | Artifact | What it is |
|---|---|---|
| 1 | `apex/ops/bootstrap_service.py` | the **long-run Phase-1 command**: `BootstrapRunner` (frozen CP-8 contract) + an async venue kline client behind a sync fetcher, an append-only ingest path, the CP-8 checkpoint store (resume), battery/disk preflight and the P0 notifier. Resumable by construction: a page budget or a venue refusal stops with a durable cursor and the next run continues from it. Mirrors every `research_bootstrap_progress` write to the canonical Ch.5 `bootstrap_progress` (phase P1, status DONE/RUNNING/PAUSED/ERROR, fixed-width ISO cursor, 6× locked retry) — ISSUE-CP9-002 & ISSUE-CP9-007. |
| 2 | `apex/telegram/gateway.py` | the **inbound half** of the CP-7 telegram plane: `getUpdates` long-poll source (token from env only), update normalisation, `UpdateDeduplicator` replay guard, OWNER-only routing, and the `BOOTSTRAP_CONTROL` action (`start│pause│resume│stop│progress│eta│continuous on│off`). |
| 3 | `apex/ops/paper_loop.py` | the **24/7 PAPER runtime**: one store + one ledger writer + the 140-cell scheduler + the execution FSM + exits. Nine stages per cell (`ingest → quality → features → engines → setup → gates → risk → decision → execution`), per-close cell de-duplication, cycle trade budget, storage guard, watchdog heartbeat, Telegram polling inside the loop, ledger-chain verification at the end of every run. |
| 4 | `scripts/run_apex.py` | the **composition root**: `bootstrap`, `status` and `serve` commands added on top of the CP-8 `boot│grid│demo│alerts`; `serve` wires store+ledger+bus+scheduler+FSM+gateway+watchdog and registers the `BOOTSTRAP_CONTROL` handler. |
| 5 | `tests/` | `tests/unit/test_ops_bootstrap_service.py` (20), `tests/unit/test_ops_telegram_gateway.py` (28), `tests/integration/test_ops_paper_loop.py` (20), `tests/unit/test_plan_bridge.py` (3) + the store/OI/window fixes' tests. |

## INTERFACES
- `BootstrapService(config=None, *, cells=None, notifier=None, fetcher=None, store=None, now=None, continuous=False, max_pages_per_cell=…)` →
  `open()/close()`, `command(command: str)`, `status()`, `run(start_ms=None, end_ms=None)`, `run_phase2()`. Canonical mirror: `CANONICAL_PROGRESS_STATUS`, `_canonical_upsert`, `mirror_bootstrap_progress`, `CanonicalMirroredCheckpoints` (when store is not None, else pure delegation).
- `TelegramGateway(control, source, *, notifier=None, action_router=…)` → `run_once()`, `run(stop=None, interval=…)`, `stop()`, `aclose()`.
- `PaperRuntime(*, config, store, ledger, bus=None, adapter=None, signaling=None, control=None, gateway=None, watchdog=None, clock=None, environment="PAPER", cells=None, notifier=None, plan_provider=None, signal_source="DECISION_BRIDGE", max_trades_per_cycle=4, max_cells_per_cycle=None, fill_poll_attempts=…, fill_poll_delay=…, now=None)` → `boot()`, `run_cycle(now_ms=None)`, `run(cycles=None, interval=…, stop=None)`, `manage_positions(as_of=…)`, `close()`.
- All three modules are `CONTRACT_VERSION 4.0.0`; the frozen SL-5 → SL-6 seam is `plan_provider(symbol, timeframe, as_of) → Mapping|None`.

## DATA-CHANGES
- `market_observation.open_interest` now stores the canonical label `MISSING`/`INVALID` for OI-less bars (frozen CHECK forbids NULL and T-DC-004 forbids 0) — ISSUE-CP9-005.
- the research checkpoint table is `research_bootstrap_progress` (was colliding with the frozen Ch.5 `bootstrap_progress`) — ISSUE-CP9-002.
- canonical `bootstrap_progress` is mirrored on every research checkpoint (phase='P1', MAX cursor_open_time, SUM bars_written, COALESCE last_error, 6× locked retry) — ISSUE-CP9-007 (W.6 L17101).
- no new table, no DDL edit, no migration removal; the frozen Ch.5/Ch.4 DDLs are byte-identical.

## TESTS
```
.venv/bin/python -m pytest tests -q            # 2627 passed
.venv/bin/python -m pytest tests/integration/test_ops_paper_loop.py -q          # 19 passed
.venv/bin/python -m pytest tests/unit/test_ops_bootstrap_service.py -q          # 20 passed
.venv/bin/python -m pytest tests/unit/test_ops_telegram_gateway.py -q           # 28 passed
```
The PAPER-loop suite proves, with an injected provider and a venue double: plan → gates → `FSM.submit`
→ venue query → fill recorded → protection placed → management → stop/target exit → `outcome`
→ reconcile → `verify_chain`, plus every named refusal (`NO_PLAN_PROVIDER`, `NO_PLAN_FOR_CELL`,
`PLAN_ALREADY_MATERIALIZED`, `NO_SETUP_ROW_FOR_PLAN`, `PLAN_ENVIRONMENT_MISMATCH`,
`INTERVAL_DISABLED_FOR_CELL`, `TRADE_BUDGET_REACHED`, `BOOT_NOT_READY`, `NO_MARKET_DATA`,
`PLAN_MALFORMED`, `ENGINE_BRIDGE_PENDING`) and the pause honoured from the control plane.
The bootstrap mirror is proven by `test_complete_run_mirrors_canonical_done_and_cursor` (phase P1 DONE bars≥3 ISO cursor equality) and `test_budget_paused_mirrors_canonical_running_and_cursor` (RUNNING|PAUSED).

## DEVIATIONS
None. Every module is wired to the frozen surfaces it names; the plan bridge is a declared seam
(ISSUE-CP9-006), not a stub: without a provider every cell halts with a NAMED refusal and `serve`
prints it. The canonical mirror (ISSUE-CP9-007) is not a deviation: it restores the W.6 / L17101
requirement that `bootstrap_progress` be checkpointed and never rewound.

## OPEN-ISSUES
- ISSUE-CP9-006 is CLOSED by HANDOFF_BRIDGE below.
- carried over from CP-8: the owner-only escalations (ISSUE-CP8-006) and the AI.13 gates.

## HOW-TO-RUN
```bash
# 0. the sandbox does not persist .venv
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.lock

# 1. the long run, step 1: the W.6 Phase-1 data bootstrap (resumable, checkpointed)
.venv/bin/python scripts/run_apex.py bootstrap --cells BTCUSDT:1h      # exit 0 READY · 2 stopped/degraded · 3 reconciliation
.venv/bin/python scripts/run_apex.py status                            # progress, per-cell cursor, no venue needed
.venv/bin/python scripts/run_apex.py status --json

# 2. the 24/7 loop (PAPER; refuses LIVE without the economic-gate signature)
APEX_ENV=PAPER APEX_ALLOW_SIGNED=1 TELEGRAM_BOT_TOKEN=... TELEGRAM_OWNER_CHAT_ID=... \
  .venv/bin/python scripts/run_apex.py serve --cycles 0 --interval 60

# 3. Telegram (inbound): the WORDS the gateway accepts from the OWNER chat
#    start | pause | resume | stop | progress | eta | continuous on | continuous off
#    (any other message falls through to the CP-7 control plane: /start /lock /unlock /help /myid)
```
Exit codes: `0` READY · `1` error · `2` stopped/degraded (resumable or credentials missing) · `3` recovery required.

## REMAINING WORK LEDGER
1. owner-side: real Telegram token/chat id, a live-network Phase-1 catch-up, and the CP-8 escalations.

## HANDOFF_BRIDGE
LAW-ACK: G1..G20 + P1..P21 read 2026-09-15T01:39:42Z
STATUS: COMPLETE — ISSUE-CP9-006 is closed on the environment-pinned branch `arena/01a0a2a1-upstage`.

### CLAIM
The frozen fabric → pattern/setup → gates → forecast → risk/veto → decision chain is now
registered as `PaperRuntime.plan_provider` by `scripts/run_apex.py serve`. `PaperPlanBridge`
is PAPER-only and fail-closed: it does not import execution, write the ledger, contact a
venue, or invent raw-store evidence. The existing FSM remains the only venue path and the
existing ledger writer remains the only ledger writer.

### DELIVERED
- `apex/ops/plan_bridge.py`: consumes a complete governed context or complete persisted
  ACTIVE evidence, assembles SL-14 Evidence Fabric/conflict/context, admits the frozen
  pattern, runs `EL_SWEEP_RECLAIM_FVG` and all 13 setup gates, builds the bootstrap PAPER
  forecast, strategy proposal/arbitration, all 14 Risk Kernel vetoes before sizing, and
  the frozen `PaperRuntime` plan mapping; it materializes `setup_candidate` before runtime
  admission. E11 IC inputs, history windows, `W=(9,8)`, `b=(9,)`, and regime context are
  required and shape-checked, not recomputed or defaulted.
- `scripts/run_apex.py`: composition root registers one bridge instance as
  `plan_provider`; a missing store context is a named refusal, never `NO_PLAN_PROVIDER`
  or a synthetic plan.
- `tests/integration/test_ops_paper_loop.py`: raw GF-shaped bars are ingested into the
  fixture SQLite store; a bootstrap-style store-double context supplies complete ACTIVE
  evidence and engine-owned outputs; fixture-clock scripted venue proves plan → gates →
  FSM → fill → protection → target exit → outcome → reconcile and byte-stable bridge
  replay.
- `tests/unit/test_plan_bridge.py`: PAPER-only, raw-store/context-unavailable, and
  reduced-persisted-evidence refusal contracts.

### INTERFACES
- `PaperPlanBridge(store, environment="PAPER", context_source=None)` is an async
  callable `(symbol, timeframe, as_of) -> Mapping | None`, with `refusals`, `plans`, and
  `traces` audit views. A context source may be sync or awaitable and must provide
  `REQUIRED_CONTEXT_KEYS` plus `REQUIRED_RISK_KEYS`.
- The store seam checks `get_bridge_context`, `get_engine_context`,
  `read_bridge_context`, `read_engine_context`, then `bridge_contexts`; no raw SQL row is
  promoted to a governed event.
- The plan mapping remains the CP-7 `PaperRuntime` contract; no frozen DDL columns or
  parameter YAML values were changed.

### DATA-CHANGES
None. No migration, frozen DDL, parameter YAML, `APEX_GEN5.md`, or `PROMPT.md` was edited.
Setup materialization writes the existing frozen `setup_candidate` row only.

### TESTS
- `python -m pytest -q tests/unit/test_plan_bridge.py tests/integration/test_ops_paper_loop.py::test_governed_bridge_drives_fixture_paper_lifecycle` — 4 passed.
- `python -m pytest -q` — 2631 passed / 0 failed, repeated twice deterministically.
- `sha256sum APEX_GEN5.md` — `216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e`.

### DEVIATIONS
None. Missing engine context/evidence remains a named refusal; this increment does not
turn raw bars into ungoverned evidence or create a live adapter path.

### OPEN-ISSUES
No executor-actionable ISSUE-CP9-006 item remains. Owner-only Telegram/live-network and
CP-8 escalation procedures are carried in the base CP-9 ledger.

### PUSH RECORD
`d115709` was pushed to `origin/arena/01a0a2a1-upstage`; GitHub PR **#11** is open
(`main` ← `arena/01a0a2a1-upstage`) for the owner's plain merge. The immutable
`APEX_GEN5.md` hash was rechecked immediately before push: `216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e`.

## HANDOFF_CP10_HOTFIX
LAW-ACK: G1..G20 + P1..P21 read 2026-09-16T00:25:00Z
STATUS: COMPLETE — ISSUE-CP10-001 is closed on the environment-pinned branch `arena/01a0a796-upstage`.

### CLAIM
Public Toobit client (`apex/data_catalog/ingest/toobit_public.py`) response-shape bug is fixed at a single client choke point (`unwrap_toobit_response` in `_get`). Handles bare-array (`/quote/v1/klines`) and bare-object (`/quote/v1/openInterest`) shapes discovered during owner device live probe as well as wrapped dict envelopes. HTTP-200 non-zero error codes raise `ToobitPublicError` preserving numeric code and message; `-1003` is mapped to rate limit backoff by `bootstrap_service` (W.6 preserved), and non-rate-limit errors fail closed rather than collapsing to empty rows (silent-completion hole eliminated). Legitimate HTTP 200 `[]` preserved as end-of-history for that cell.

### DELIVERED
- `apex/data_catalog/ingest/toobit_public.py`:
  - `unwrap_toobit_response(body, endpoint)` choke-point unwrap function.
  - `ToobitPublicClient._get`: calls `unwrap_toobit_response(body, endpoint=path)`.
  - `ToobitPublicClient.get_klines`: consumes unwrapped responses; supports both bare lists and wrapped envelopes; handles list rows and dict rows via `parse_kline_to_observation`; never collapses non-zero error dicts into empty rows; legitimate `[]` returns `[]`.
  - `ToobitPublicClient.get_open_interest`: consumes bare objects, bare dicts, and wrapped envelopes; returns `Decimal` or `None` (MISSING, never 0; T-DC-004).
  - `ToobitPublicClient.get_depth`: consumes bare objects and wrapped envelopes.
  - `ToobitPublicClient.get_funding_rate`: consumes bare arrays and wrapped envelopes without AttributeError.
  - Module docstring documents response shapes and live probe findings without touching frozen `params/*.yaml`.
- `tests/unit/test_toobit_public.py`:
  - 20 new tests (33 total passed):
  - Verbatim real device probe fixtures for klines, openInterest, depth, and fundingRate.
  - Both bare-array and wrapped-dict shapes for `get_klines` and `get_open_interest`.
  - Legitimate empty list `[]` on HTTP 200.
  - `-1003` on HTTP 200 raises `ToobitPublicError` containing `-1003` and message.
  - Seam test: `ToobitKlineSource` from `bootstrap_service` maps `-1003` on HTTP 200 to backoff (`{"code": -1003, "rows": [], "next_cursor_ms": None}`).
  - Non-zero error codes (-1120, 1001) fail closed as `BootstrapError("FETCH_FAILED")`, never empty rows.
  - Direct contract tests for `unwrap_toobit_response`.

### INTERFACES
- `unwrap_toobit_response(body: Any, endpoint: str = "") -> Any`:
  - bare list -> returns `body`
  - dict with non-zero "code" -> raises `ToobitPublicError(endpoint, f"code={code} msg={msg}")`
  - dict with "data" -> returns `body["data"]`
  - bare dict without "data" or error "code" -> returns `body`
- `ToobitPublicClient._get(path: str, params: Optional[Dict[str, Any]] = None) -> Any`
- `ToobitPublicClient.get_klines(...) -> List[MarketObservation]`

### DATA-CHANGES
None. No migration, frozen DDL, parameter YAML (`params/*.yaml` FROZEN), `APEX_GEN5.md`, or `PROMPT.md` was edited.

### TESTS
- `python -m pytest tests/unit/test_toobit_public.py -q` — 33 passed (13 baseline + 20 hotfix).
- `python -m pytest tests/unit/test_ops_bootstrap_service.py -q` — 20 passed.
- `python -m pytest tests -q` — 2651 passed / 0 failed, repeated twice deterministically (was 2631 passed; +20 tests).
- `sha256sum APEX_GEN5.md` — `216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e`.

### DEVIATIONS
None. Frozen CP-1 bug-fix authorized under the ISSUE-CP9-001 precedent.

### OPEN-ISSUES
None. ISSUE-CP10-001 is CLOSED-with-evidence.

### PUSH RECORD
Commit range `cbed6cc..HEAD` (dbbfbf7 implementation + tests · docs closeout) pushed to `origin/arena/01a0a796-upstage`; PR opened (`main` ← `arena/01a0a796-upstage`). The immutable `APEX_GEN5.md` hash was rechecked immediately before push: `216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e`.

## HANDOFF_CP11_HOTFIX
LAW-ACK: G1..G20 + P1..P21 read 2026-09-16T03:20:00Z
STATUS: COMPLETE — ISSUE-CP11-001 is closed on the environment-pinned branch `arena/01a0a838-upstage`.

### CLAIM
`ToobitKlineSource` (wiring layer, `apex/ops/bootstrap_service.py`) is now venue-adaptive for tail-aligned Toobit public klines. The frozen W.6 runner (`apex/research/bootstrap.py`) is byte-untouched. On the first page call per `(symbol, timeframe)` the source walks the venue BACKWARD from `end_ms`, collects the retained history (dedup-guarded), then serves the runner ASCENDING `PAGE_LIMIT` chunks filtered by the durable cursor. Empty-first-page zero-bar COMPLETE (owner pilot: `completed=1 pages=0 bars=0`) is closed. `--max-pages` still counts runner-facing pages; walk-internal −1003/429 uses bounded exponential backoff; non-rate-limit errors remain named fail-closed; resume-with-forward-cursor does not re-ingest already-collected bars.

### DELIVERED
- `apex/ops/bootstrap_service.py`:
  - `ToobitKlineSource._walk_backward` / `_get_klines_with_walk_backoff` / per-cell `_history` cache.
  - Ascending serve with `open_time < cursor` filter; empty-page shape `next_cursor_ms=end_ms` on exhaustion.
  - `WALK_BACKOFF_SECONDS=(5.0, 15.0, 60.0)` injected by `BootstrapService._ensure_source`; default empty backoff preserves the CP-10 −1003 surface-to-runner seam.
  - `pages_served` = runner-facing only; `walk_pages` / `rate_limited` counters for observability.
- `tests/unit/test_ops_bootstrap_service.py`:
  - `TailAlignedVenue` fake session emulating owner-probe shapes (startTime ignored; short historical window → `[]`; rolling retention tail).
  - `TestTailAlignedSource`: full-walk ascending; empty-first-page recovers tail; budget on facing pages; backoff inside walk; dedup-stop; resume-with-cursor; resume-across-restart; non-rate-limit fail-closed.
  - Service pilot-regression `test_tail_aligned_pilot_regression_completes_with_bars`.
  - Existing 20 wiring tests retained/adapted (30 total).

### INTERFACES
- `ToobitKlineSource(..., walk_backoff_seconds: Optional[Sequence[float]] = None)` — default `()` surfaces −1003 immediately; production path passes `WALK_BACKOFF_SECONDS`.
- Frozen fetcher contract unchanged: `{"rows", "next_cursor_ms", "code", "oi_available"}`.
- `BootstrapService` source factory injects `walk_backoff_seconds=WALK_BACKOFF_SECONDS`.

### DATA-CHANGES
None. No migration, frozen DDL, parameter YAML, `research/bootstrap.py`, `APEX_GEN5.md`, or `PROMPT.md` was edited.

### TESTS
- `python -m pytest tests/unit/test_ops_bootstrap_service.py -q` — 30 passed.
- `python -m pytest tests/unit/test_toobit_public.py tests/unit/test_ops_bootstrap_service.py -q` — 63 passed (CP-10 seam preserved).
- `python -m pytest tests -q` — 2661 passed / 0 failed, repeated twice deterministically (was 2651; +10 CP-11 tests).
- `sha256sum APEX_GEN5.md` — `216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e`.

### DEVIATIONS
None. Frozen runner law preserved; adaptation is wiring-only under the ISSUE-CP9-001 bug-fix precedent.

### OPEN-ISSUES
None. ISSUE-CP11-001 is CLOSED-with-evidence.

### PUSH RECORD
Implementation + tests + docs closeout pushed to `origin/arena/01a0a838-upstage`; PR opened (`main` ← `arena/01a0a838-upstage`). The immutable `APEX_GEN5.md` hash was rechecked immediately before push: `216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e`.

## HANDOFF_CP12_HOTFIX
LAW-ACK: G1..G20 + P1..P21 read 2026-09-16T05:00:00Z
STATUS: COMPLETE — ISSUE-CP12-001 is closed on the environment-pinned branch `arena/01a0a890-upstage`.

### CLAIM
`ToobitKlineSource` (wiring layer, `apex/ops/bootstrap_service.py`) is now venue-data-hygienic. The owner's first long post-CP-11 run advanced ~25 cells / 76,366 clean bars and then died named-fail-closed at `BTCUSDT:1d` with `IntegrityError: CHECK constraint failed: CAST(high_price AS REAL)>=max(open,close) AND low<=min(open,close) AND high>=low` — the frozen store DDL meeting Toobit's legacy Huobi-era 1d candles. The owner's read-only venue probe (2026-09-16, walking every interval backward exactly as this source does) measured `1m`=0, `5m`=0, `15m`=0, `1h`=0, `4h`=0 violations and `1d`=2 of 1747 rows. Repairing/clipping a venue value is fabrication (forbidden) and a silent skip breaks W.6's never-skip law, so the sanctioned interim behavior is drop-with-observable-evidence at the single boundary where a walked row is appended into the per-cell history. The frozen runner (`apex/research/bootstrap.py`), the frozen client (`toobit_public.py`), the store DDL, `params/*.yaml` and `APEX_GEN5.md` are byte-untouched.

### DELIVERED
- `apex/ops/bootstrap_service.py`:
  - `_ohlc_violation` / `_kline_ohlc_fields` / `_decimal_or_none`: the frozen DDL law clause-for-clause (OHLC numeric-parseable, `high>=max(open,close)`, `low<=min(open,close)`, `high>=low`) judged over observation, raw-list and raw-dict row shapes; volume/quote-volume/trade-count fields are never judged, so the frozen client's tolerant parse of them stays as-is.
  - `ToobitKlineSource._walk_backward`: the gate sits on the append boundary into `_history` (fresh walks and cursor-filtered resume passes both pass through it); a failing row is counted and never enters the history, so it can never be served to the runner nor reach the store.
  - Walk-stop conditions unchanged and still venue-owned (empty page / repeated first row / no backward progress); every returned open time counts as seen, so a page whose rows are ALL invalid drops them without ending the walk or completing the cell.
  - Evidence: `invalid_dropped` (per source), `invalid_by_cell`, `invalid_reasons`, `invalid_offenders` capped at `INVALID_BAR_OFFENDER_RETENTION=20` per cell as `(symbol, timeframe, open_time_ms, repr(row)[:160])` with named reasons; `cell_prints` + `drain_cell_complete_prints()`.
  - Wiring print: `bootstrap Phase 1 cell complete: cell=SYMBOL:TF pages=<facing> bars=<served> dropped=<n>` plus `offenders=[…] reasons=[…]` when `n>0`, drained by `BootstrapService._flush_cell_complete_prints` (per ingest and at run end) into the existing owner report path.
  - Mirrors: `status()["invalid_bars_dropped"]` (offline, read-only, 0 until a source exists) and `run()` result `invalid_bars_dropped` + `invalid_offenders`.
- `tests/unit/test_ops_bootstrap_service.py`:
  - `TestOhlcLaw`: both verbatim poison rows judged in every row shape; a 625-case table proving keep/drop equals the frozen DDL predicate; unparseable OHLC named per field; rows without OHLC not judged.
  - `TestVenueDataHygiene`: (a) both verbatim rows dropped with valid neighbours served and `dropped=2` in the print; (b) an all-poison page that neither ends the walk nor completes the cell, and an all-poison cell completing at zero bars with 20-of-25 offenders retained; (c) hostile volume/quote/trades kept; (d) poison never re-served across a resume or a restart re-walk; (e) −1003 inside a poisoned walk backs off and never skips; (f) a −1120-class venue error still fails closed as `FETCH_FAILED`. Unparseable volume stays the client's named failure, never a drop.
  - `TestVenueDataHygieneService`: against the REAL frozen store — cell `COMPLETE` at 48 bars, `IntegrityError` unreachable, untouched DDL still refuses the verbatim bar, prints/mirrors carry the evidence, clean cell reports `dropped=0`, budget stop keeps the evidence, offline status reports 0.
  - Existing 30 wiring tests retained (fakes extended additively via `HygieneVenue`); 49 total.

### INTERFACES
- `ToobitKlineSource` fetcher contract unchanged: `{"rows", "next_cursor_ms", "code", "oi_available"}`.
- New source attributes (read-only for the owner/scripts): `invalid_dropped`, `invalid_by_cell`, `invalid_reasons`, `invalid_offenders`, `drain_cell_complete_prints()`, `cell_prints`.
- `BootstrapService.status()` adds `invalid_bars_dropped`; `run()` result adds `invalid_bars_dropped` and `invalid_offenders`. `scripts/run_apex.py status|bootstrap --json` surface both without any change to the CLI file.
- Module constants: `INVALID_BAR_OFFENDER_RETENTION=20`, `INVALID_BAR_ROW_REPR_CHARS=160`, reason names `REASON_HIGH_BELOW_MAX_OPEN_CLOSE` / `REASON_LOW_ABOVE_MIN_OPEN_CLOSE` / `REASON_HIGH_BELOW_LOW` / `REASON_OHLC_NOT_PARSEABLE`.

### DATA-CHANGES
None. No migration, no frozen DDL, no `params/*.yaml`, no `apex/research/bootstrap.py`, no `apex/data_catalog/**`, no `APEX_GEN5.md`/`PROMPT.md` edit. The raw store keeps every value exactly as the venue gave it — the gate changes what is served, never what is recorded.

### TESTS
- `python -m pytest tests/unit/test_ops_bootstrap_service.py -q` — 49 passed (30 baseline + 19 CP-12).
- `python -m pytest tests/unit/test_toobit_public.py tests/unit/test_ops_bootstrap_service.py -q` — 82 passed (CP-10 seam preserved).
- `python -m pytest tests -q` twice — 2680 passed / 0 failed each run (baseline 2661 + 19), deterministic.
- `sha256sum APEX_GEN5.md` — `216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e` (re-checked immediately before push).

### DEVIATIONS
None beyond the owner-authorized hotfix scope: reliability only (a poison bar can no longer abort a long run), no behavior change to the frozen law, no new product rule. The cell-complete print is emitted even when `announce=False`, because drop evidence is never suppressible.

### OPEN-ISSUES
None blocking. ISSUE-CP12-001 is CLOSED-with-evidence and asks one owner confirmation: accept drop-with-evidence for `1d` (this hotfix), or decree the venue-faithful alternative (store the bar, gate it downstream) — the latter needs a frozen-file change and was therefore NOT implemented here.

### PUSH RECORD
Implementation + tests + docs closeout pushed to `origin/arena/01a0a890-upstage`; PR opened (`main` ← `arena/01a0a890-upstage`), not merged. The immutable `APEX_GEN5.md` hash was rechecked immediately before push: `216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e`.

## HANDOFF_CP13_HOTFIX
LAW-ACK: G1..G20 + P1..P21 read 2026-09-16T23:43:28Z
STATUS: COMPLETE — ISSUE-CP13-001 and ISSUE-CP13-003 are closed, ISSUE-CP13-002 is filed (frozen), on the environment-pinned branch `arena/01a0ac9a-upstage`.

### CLAIM
The venue's tail-aligned klines return the CURRENTLY OPEN candle as their last row, the frozen client labels every row `status=CLOSED`, and the pre-CP-13 wiring served it — so every run stored a snapshot of an open bar as an immutable CLOSED row (owner measurement 2026-09-16: 91 stored bars differ from the venue's final closed bar, each with `created_at` strictly earlier than its bar close; the CP12-001 OWNER DECISION files 45 confirmed mismatches). Re-running bootstrap can never heal them (the durable cursor is already past them; resume-never-rewind). Worse, merely filtering the open bar would hole it forever: the next run's `cursor=previous_end` fails the `cursor <= open_time` resume filter for the now-closed bar, while `next_cursor_ms == cursor` is frozen-impossible (`CURSOR_NOT_ADVANCING`). This hotfix (a) serves a walked row only when `close_time_ms(open) <= end_ms` (wiring-layer close law, `1mo` calendar-aware) and reports the excluded open bar instead of storing it; (b) resumes from the store frontier (`open > MAX(as_of) AND open > served_upto AND close <= end`) so the bar ingests exactly once after close with the cursor trap unreachable; (c) heals the stored partials through a governed `repair-partial` path (LIVE-first, owner-evidence fallback, frozen `correct_raw` only); (d) prints every evidence-carrying cell line without Telegram and persists drop evidence in the COMPLETE checkpoint payload for offline `status`. The frozen runner, client, store DDL, `params/*.yaml`, `APEX_GEN5.md` and `PROMPT.md` are byte-untouched.

### DELIVERED
- `apex/ops/bootstrap_service.py`:
  - `close_time_ms(open_ms, timeframe)`: the wiring-layer close law over all 14 timeframes — fixed intervals add their exact length, `1w` adds 7 days, `1mo` is the first instant of the next calendar month in UTC (December rolls the year; February follows the real calendar incl. leap years; unaligned opens close at the next month start); unknown timeframes fail closed with `BootstrapError("TIMEFRAME_QX")`. The frozen runner's 30-day `1mo` approximation is never used here.
  - `ToobitKlineSource.set_frontiers` + `__call__` frontier rule: serves `open_time > store_frontier AND open_time > served_upto AND close_time_ms(open) <= end_ms`; bars with `open <= end` but `close > end` are excluded (never served, never counted) and the newest is reported; future bars (`open > end`) are ignored. The cached walk is re-walked whenever `end_ms` advances past the cached walk's end, so a stale open-bar snapshot is never served as closed. Direct-source callers that never set frontiers keep the pre-CP-13 cursor contract.
  - `next_cursor_ms = max(close_time_ms(last_served_open), cursor + 1)`: strictly greater than the incoming cursor in every branch (fresh, newly-closed resume, nothing-new resume, budget resume) — `CURSOR_NOT_ADVANCING` is unreachable; the empty page stays the only completion signal.
  - Cell-complete print extended: `… dropped=<n> open_excluded=<m>` plus `open_time=<iso>` when `m>0`, drained through the existing owner-report path.
  - `CanonicalMirroredCheckpoints.save_bootstrap`: COMPLETE payload merge (`invalid_bars_dropped`/`invalid_reasons` from the current walk, max-preserved when retention slid or no walk ran) and evidence-key carry-forward on non-COMPLETE saves (the frozen runner re-saves `IN_PROGRESS`/`payload=None` before COMPLETE on re-runs).
  - `BootstrapService.run`: frontier handoff once per run (best-effort, doubles unaffected); result adds `open_bars_excluded`. `status()`: durable COMPLETE-payload sum + live-source counters for incomplete cells only; `open_bars_excluded` is the live temporal total.
- `apex/ops/partial_bar_repair.py` (NEW — ADR-P2-003, this handoff is the DELIVERED record):
  - B1 `find_candidates`: store-only detection — market `CLOSED` rows with `created_at < close_time_ms(open) + 5 s` (`SKEW_MARGIN_SECONDS`; errs toward checking), optional `--cells` filter; SUPERSEDED/CORRECTED rows never resurface (idempotent).
  - B2 `fetch_live_bar` + `repair_one`: LIVE first via the frozen client (`endTime=close-1`, `LIVE_FETCH_LIMIT=5`, returned `open_time` must equal the candidate's), else F6a (`differs`) / F6b (`rows`) `--evidence` entries matched by `(symbol, timeframe, open)` and accepted only on Decimal-equal store OHLCV; the replacement is parsed with the frozen `parse_kline_to_observation` and judged by the CP-12 `_ohlc_violation` law.
  - B3 `run_repair` + `report_filename`: ordered run with `counts={candidates, verified, corrected, unrepairable, refused}`; writes only under `--apply` via frozen `store.correct_raw(event_id, replacement, "MISSING", reason, actor="OPS_REPAIR_CP13")` with `reason="PARTIAL_BAR_STORED_BEFORE_CLOSE created_at=<iso> close_time=<iso> replacement=VENUE_LIVE|EVIDENCE_FILE:<basename>"`.
  - B4 audit (module docstring): every direct `raw_observation` reader reviewed for the two-rows-one-`as_of` shape — `raw_store_current` shows both (FROZEN, filed, read by no production code); engines/`get_window` see exactly the corrected bar.
  - Verdicts `VERIFIED_CLOSED` / `CORRECTED` (+`dry_run` when not applied) / `UNREPAIRABLE_VENUE_WINDOW_PASSED` / `REFUSED_OHLC_*` / `REFUSED_EVIDENCE_MISMATCH` / `REFUSED_PARSE`; exit 0 iff `unrepairable==0` and `refused==0` (a refused row is also left partial, so it also needs the owner).
- `scripts/run_apex.py`:
  - `bootstrap` prints EVERY `CELL_COMPLETE` line carrying evidence (`_print_cell_complete_evidence`, F5 fix) plus the final `invalid_bars_dropped=<n> open_bars_excluded=<m>` line on success and on resumable stop; `status` prints both counters.
  - NEW `repair-partial` command (dry-run default; `--evidence` repeatable, `--apply`, `--cells`, `--json`): per-candidate lines, summary counts, `data/repair_partial_report_<UTC>.json`, exit 0/1/2 mapping.
- `tests/unit/test_ops_bootstrap_service.py` (+22, 71 total, no existing line changed):
  - `TestCloseTimeMs` (5): all 14 fixed lengths, Dec→Jan, leap/non-leap February, unaligned opens, unknown-timeframe fail-closed.
  - `TestClosedBarLaw` (7): (i) open excluded/closed stored; (ii) newly closed ingested exactly once across a restart AND in one process (re-walk + `served_upto`, no dup); (iii) seconds-later no-op COMPLETE; (iv) 1001-bar `--max-pages` frontier resume; (v) `1mo` year boundary; the 31-day next-cursor trap the frozen approximation would spring.
  - `TestCursorAlwaysAdvances` (4): `next_cursor_ms > cursor` on every page of a fresh run, a newly-closed resume, a nothing-new resume and a budget resume.
  - `TestDropEvidencePersistence` (6): COMPLETE payload content, offline durable sum, budget-stop live-only reporting with nothing persisted, same-end re-run preservation, the evidence-line detector + print-every tests.
- `tests/unit/test_ops_partial_bar_repair.py` (NEW, 20 — ADR-P2-003): B1 detection incl. the exact skew boundary; B2 LIVE-first (`endTime=close-1`, limit 5) + F6a/F6b fallback incl. open-mismatch and store-mismatch gates; B3 `correct_raw` lineage (actor/reason/SUPERSEDED/CORRECTED, `get_window` sees one corrected bar) + idempotent re-apply; B4 untouched-unrepairable; B5 named refusals + malformed-evidence fail-closed; CLI exit mapping hermetic (`APEX_SQLITE_PATH`+`REPO_ROOT` on tmp, LIVE stubbed).

### INTERFACES
- `ToobitKlineSource` fetcher contract unchanged: `{"rows", "next_cursor_ms", "code", "oi_available"}`; `-1003` surface, `PAGE_BUDGET_REACHED` on runner-facing pages, `FETCH_FAILED` — all unchanged.
- New: `close_time_ms`, `set_frontiers(frontiers)`, read-only `open_bars_excluded` / `open_excluded_by_cell`; `BootstrapService.status()` adds `open_bars_excluded` (durable `invalid_bars_dropped` semantics: COMPLETE payloads + live incomplete extra); `run()` result adds `open_bars_excluded`.
- New module `apex.ops.partial_bar_repair`: `find_candidates`, `fetch_live_bar`, `repair_one`, `run_repair`, `load_evidence_files`, `report_filename`; constants `SKEW_MARGIN_SECONDS=5`, `REPAIR_ACTOR="OPS_REPAIR_CP13"`, `LIVE_FETCH_LIMIT=5`, verdict names.
- CLI: `repair-partial [--evidence F …] [--apply] [--cells S:T,…] [--json]` → exit 0 (nothing unrepairable/refused) / 1 (refused invocation) / 2 (attention needed); report `data/repair_partial_report_<UTC>.json`.

### DATA-CHANGES
No migration, no frozen DDL, no `params/*.yaml`, no `apex/research/bootstrap.py`, no `apex/data_catalog/**`, no `APEX_GEN5.md`/`PROMPT.md` edit, nothing written under `data/` by this change itself. Two governed data effects at RUNTIME only: (a) checkpoint `payload_json` gains `invalid_bars_dropped`/`invalid_reasons` on COMPLETE rows (the research store already accepts `payload` — read, not changed); (b) `repair-partial --apply` appends correction rows through the frozen `correct_raw` (original immutable, `raw_revision` + `retention_event` with `OPS_REPAIR_CP13`, market SUPERSEDED/CORRECTED) — no other writer is added.

### TESTS
- `python -m pytest tests/unit/test_ops_bootstrap_service.py -q` — 71 passed (49 baseline + 22 CP-13).
- `python -m pytest tests/unit/test_ops_partial_bar_repair.py -q` — 20 passed (new module).
- `python -m pytest tests -q` twice — 2722 passed / 0 failed each run (baseline 2680 + 42), deterministic.
- `sha256sum APEX_GEN5.md` — `216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e` (re-checked immediately before push).

### DEVIATIONS
None beyond the owner-authorized hotfix scope: reliability + governed repair only, no behavior change to any frozen law, no new product rule. Two judgment calls of record: (1) exit 0 requires BOTH `unrepairable==0` and `refused==0` — the brief's "nothing is left unrepairable" read strictly, because a `REFUSED_*` row is likewise left partial and untouched and needs the owner; (2) the 1001-bar frontier-resume test walks two facing pages of real ingests (~seconds) rather than a toy cell, so the `--max-pages` mid-cell resume is proven, not mocked.

### OPEN-ISSUES
None blocking. (a) ISSUE-CP13-002 (`availability_time` 1970, venue `close_time=0`) is FILED and asks one owner decree: want a wiring-layer derivation or accept the venue's stamp (a change needs a frozen-file edit — NOT implemented). (b) The 91 stored partials: `repair-partial` heals LIVE-visible bars automatically; window-passed bars need owner `--evidence` captures (F6a/F6b). (c) `raw_store_current` shows both rows of a corrected `as_of` (FROZEN, filed in the B4 audit; no production reader).

### DEVICE-RUNBOOK
On the owner device (Termux), from the repo root, after pulling this branch:
1. Resume the harvest (nothing special — the law is automatic): `python scripts/run_apex.py bootstrap` — the still-open bar of each cell is now EXCLUDED and reported (`open_excluded=1 open_time=…`), never stored; re-running later ingests it exactly once after close. Resume rule unchanged: the cursor is durable, never rewinds.
2. Check progress offline any time: `python scripts/run_apex.py status` — prints `invalid_bars_dropped=<durable+live> open_bars_excluded=<this-process>`; drops for completed cells survive restarts.
3. Preview partial-bar repair (writes nothing): `python scripts/run_apex.py repair-partial --evidence <capture.json>` (repeat `--evidence` for several captures) — prints one line per candidate (`VERIFIED_CLOSED` / `CORRECTED` dry-run / `UNREPAIRABLE_VENUE_WINDOW_PASSED` / `REFUSED_*`), summary counts, and `data/repair_partial_report_<UTC>.json`. No `--evidence` = LIVE venue only.
4. Apply after reviewing the report: add `--apply` — corrections append via the frozen path (originals immutable, `raw_revision` actor `OPS_REPAIR_CP13`); re-running is a no-op. Exit 0 = nothing left unrepairable/refused; 2 = attention needed (names printed); 1 = refused invocation (e.g. missing evidence file).
5. Narrow any step to cells: append `--cells BTCUSDT:1h,ETHUSDT:1d`. Telegram is optional throughout — every evidence line is printed locally.

### PUSH RECORD
Implementation + tests + docs closeout pushed to `origin/arena/01a0ac9a-upstage`; PR opened (`main` ← `arena/01a0ac9a-upstage`), not merged. The immutable `APEX_GEN5.md` hash was rechecked immediately before push: `216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e`.

---

## HANDOFF_CP13.1_HOTFIX — repair-partial close-time-vs-now guard (ISSUE-CP13-004)

### STATUS
- CLAIM — executor = Arena Agent Mode, same environment-pinned workspace/branch family rule as every prior handoff, 2026-09-17; LAW-ACK: G1..G20 + P1..P21 (re-read before editing, same session).
- Device evidence (owner dry-run 2026-09-17T04:33:03Z, report `data/repair_partial_report_20260917T043303Z.json`, kept off-repo): `candidates=163 corrected=163 unrepairable=0 refused=0`, all replacements `VENUE_LIVE` — but **20 of the 163 candidates are the CURRENT still-open 1w/1mo bars of all 10 symbols** (1w open 2026-09-15T00:00Z closes 2026-09-22T00:00Z; 1mo open 2026-09-01T00:00Z closes 2026-10-01T00:00Z): without a close-time-vs-now guard, an `--apply` run would replace a partial bar with another partial bar on every run. Root cause: spec omission in the CP-13 repair spec (detection law stated, close-time guard missing). `--apply` has NOT been run by the owner and must remain unused until this fix is merged (ISSUE-CP13-004, MAJOR).
- CP-13.1 delivers the guard: a candidate whose bar has not closed by `now_ms - SKEW_MARGIN_SECONDS*1000` is SKIPPED_STILL_OPEN — never fetched, never repaired, never counted as unrepairable or refused, never degrading the exit code — and listed with `closes_at` so the owner sees exactly the 20 still-open bars and when they become repairable. CONTRACT_VERSION 4.0.0 → 4.1.0 (backward-compatible minor). Full suite twice: 2728 passed / 0 failed (was 2722; +6).

### CLAIM
1. `run_repair` (and only it) takes an explicit `now_ms` (int, UTC epoch milliseconds; `None` → `int(time.time()*1000)`, the single wall-clock read of the repair path; tests inject it). A candidate with `close_ms > now_ms - SKEW_MARGIN_SECONDS*1000` (strict `>`) is NOT repaired and NO live fetch is made for it — report row: `verdict=SKIPPED_STILL_OPEN`, `replacement` null, `closes_at` = ISO-8601 UTC millisecond string of `close_ms` — counted under the NEW counts bucket `skipped_still_open` (present whenever ≥1), never as unrepairable, never as refused.
2. `repair-partial` exit semantics unchanged: READY (0) iff `unrepairable == 0` and `refused == 0`; skipped rows never degrade it. Summary line carries `skipped_still_open=N`; a skipped row prints `verdict=SKIPPED_STILL_OPEN closes_at=<iso>`. After all 143 repairable bars of the 163 are corrected, the next `--apply` run shows `corrected=0` and exactly 20 `SKIPPED_STILL_OPEN` rows remaining — and must exit 0.
3. This hotfix stays inside the CP-13 allowed set: only `apex/ops/partial_bar_repair.py`, the `repair-partial` summary/row print of `scripts/run_apex.py`, the repair test file (append-only), and the control docs (`PHASE2_CHECKPOINT_STATUS.md`, `PHASE2_DECISION_LOG.md`, `PHASE2_HANDOFF_CP9.md`, `PHASE2_TRACEABILITY_MATRIX.md`) are touched. Everything frozen is untouched: `apex/research/bootstrap.py`, `apex/data_catalog/**` (including `toobit_public.py` and the store DDL), `params/*.yaml`, `APEX_GEN5.md`, `PROMPT.md`, `data/`. `find_candidates` / `repair_one` / `report_filename` / the frozen `correct_raw` usage are byte-untouched (the guard is applied at candidate iteration inside `run_repair`, before any fetch or write).

### DELIVERED
| file | change |
|---|---|
| `apex/ops/partial_bar_repair.py` | `CONTRACT_VERSION` 4.0.0 → 4.1.0; new verdict constant `VERDICT_SKIPPED_STILL_OPEN` ("SKIPPED_STILL_OPEN") next to the existing verdict constants and exported; `run_repair(..., now_ms=None)` — single wall-clock read, skip guard before `repair_one`, skipped rows carry `closes_at`, new `skipped_still_open` counts bucket (added when ≥1); `find_candidates`/`repair_one`/`report_filename` unchanged. |
| `scripts/run_apex.py` | `repair-partial` row print: skipped rows show `closes_at=<iso>` after the verdict; summary line appends `skipped_still_open=N`; exit mapping untouched (READY iff nothing unrepairable/refused). |
| `tests/unit/test_ops_partial_bar_repair.py` | Appended `TestSkippedStillOpen` (6 tests: (a) still-open skipped + ZERO live-fetch calls; (b) after close+skew processed normally; (c) 4 s future / 3 s past / 4 999 ms past all still open, exact boundary not skipped; (d) `--apply` writes nothing for skipped rows; (e) mixed 1 skipped + 1 corrected + 1 verified counts + JSON round-trip; (f) CLI summary `skipped_still_open=1` + exit 0 when only skipped rows, live-fetch patched to raise). All 20 CP-13 tests untouched. |

### INTERFACES
- `PR.VERDICT_SKIPPED_STILL_OPEN = "SKIPPED_STILL_OPEN"` — exported in `__all__`:
  ```python
  f"{symbol} {timeframe} open=... created=... verdict=SKIPPED_STILL_OPEN "
  f"closes_at=2026-09-22T00:00:00.000Z store_close=... source=-"
  ```
- `run_repair` signature (all new/changed names pinned):
  ```python
  await PR.run_repair(store, client=<source>, evidence_paths=(...),
                      apply=<bool>, cells=None, now_ms=None)  ->  report_dict
  ```
  - report row extra: `closes_at` (present exactly on skipped rows; ISO-8601 UTC ms string of `close_ms`);
  - `counts["skipped_still_open"]` — present whenever at least one candidate was still open.
- CLI: `python scripts/run_apex.py repair-partial [--evidence f.json ...] [--apply] [--json]` — same as CP-13; summary now ends `... refused=N skipped_still_open=M`; exit 0 when everything is verified/corrected/skipped.

### DATA-CHANGES
- None new beyond CP-13: skipped rows produce NO writes at all (no `correct_raw`, no `INSERT`, no `raw_revision`); corrected rows keep the CP-13 path exactly (`store.correct_raw(..., actor="OPS_REPAIR_CP13")` — raw stays APPEND-only, `new_status=CORRECTED`, lineage `corrects_event_id`). After a full `--apply` the only remaining candidates are the 20 still-open bars, which stay raw-untouched until after `closes_at + 5 s`.

### TESTS
- `tests/unit/test_ops_partial_bar_repair.py` — 26 passed (20 baseline untouched + 6 `TestSkippedStillOpen`); (a) asserts ZERO `get_klines` calls on the stub for a still-open 1w candidate — the no-live-fetch law is wired and asserted;
- `tests/unit/test_ops_bootstrap_service.py` — 71 passed (untouched);
- Full suite twice: 2728 passed / 0 failed in each run.

### DEVIATIONS
- None beyond ISSUE-CP13-004 itself; no frozen file touched; counts bucket `skipped_still_open` is additive-when-present (absent when 0) — that keeps every CP-13 exact-dict-equality test byte-valid while still NAMING the metric in every printed summary and on every non-zero report.

### OPEN-ISSUES
- The 20 still-open bars become repairable after their closes (+5 s skew): ten 1w from 2026-09-22T00:00:05.000Z, ten 1mo from 2026-10-01T00:00:05.000Z. Until then any `repair-partial` run (dry-run or `--apply`) shows exactly `skipped_still_open=20` and exit 0. The owner's `--apply` remains BLOCKED until this hotfix is merged and the runbook below is executed with the fixed code.

### DEVICE-RUNBOOK
Executed on the owner's phone (Termux + proot Ubuntu), working tree at `~/Upstage`, checkout synced to this hotfix (`git pull` after the PR is merged to `main` and the device fast-forwards to it).

1. Environment:
   ```bash
   proot-distro login ubuntu
   cd ~/Upstage
   git pull
   .venv/bin/python -m pytest tests/unit/test_ops_partial_bar_repair.py tests/unit/test_ops_bootstrap_service.py -q
   # EXPECTED: 97 passed   (26 repair + 71 bootstrap)
   ```
2. Dry-run repair with BOTH `--evidence` captures used for the 04:33:03Z report (`data/partial_bar_evidence_20260916T223404Z.json` is the documented one; substitute the owner's second capture path for `<second-capture>` — i.e. the same `--evidence` file list used for the 04:33:03Z dry-run):
   ```bash
   .venv/bin/python scripts/run_apex.py repair-partial \
     --evidence data/partial_bar_evidence_20260916T223404Z.json \
     --evidence data/<second-capture>.json
   # EXPECTED (same inputs as the 04:33:03Z run):
   #   20 rows:   verdict=SKIPPED_STILL_OPEN closes_at=2026-09-22T00:00:00.000Z  (10× 1w)
   #              verdict=SKIPPED_STILL_OPEN closes_at=2026-10-01T00:00:00.000Z (10× 1mo)
   #   no live fetch happens for those 20 (their report rows show source=-)
   #   summary: candidates=163 verified=0 corrected=143 unrepairable=0 refused=0 skipped_still_open=20
   #   EXIT: 0 (READY)
   #   report: data/repair_partial_report_<UTC>.json (counts include skipped_still_open)
   ```
3. Only after the dry-run above prints `skipped_still_open=20` and exit 0 — apply with the same two `--evidence` captures:
   ```bash
   .venv/bin/python scripts/run_apex.py repair-partial \
     --evidence data/partial_bar_evidence_20260916T223404Z.json \
     --evidence data/<second-capture>.json --apply
   # EXPECTED:
   #   143 rows verdict=CORRECTED (or VERIFIED_CLOSED if a bar matched exactly), dry_run absent
   #   20 rows  verdict=SKIPPED_STILL_OPEN closes_at=... (untouched, source=-)
   #   summary: candidates=163 ... corrected=143 ... skipped_still_open=20 ... EXIT: 0
   ```
4. Re-run WITHOUT `--apply` (healing must be idempotent; nothing left to correct):
   ```bash
   .venv/bin/python scripts/run_apex.py repair-partial
   # EXPECTED:
   #   NO verdict=CORRECTED rows at all (corrected=0)
   #   exactly the 20 still-open bars remain, all verdict=SKIPPED_STILL_OPEN
   #   summary: candidates=20 verified=0 corrected=0 unrepairable=0 refused=0 skipped_still_open=20
   #   EXIT: 0
   ```
5. Confirm no writes happened for the 20: in the step-3/4 reports every skipped row shows `source=-`; the store's `raw_revision` contains only the 143 CP-13 corrections with `actor=OPS_REPAIR_CP13`.

### PUSH RECORD
- Branch `arena/01a0adc6-upstage` → PR pending (number/URL recorded in the CP-13.1 checkpoint board line and the executor's report) — `[CP-13.1] HOTFIX close-time-vs-now guard for repair-partial — ISSUE-CP13-004`. Suite twice: 2728 passed / 0 failed. Suite file counts: 67 unit + 9 integration + 1 e2e + 4 perf files; 95 node API tests (unchanged).

---

## HANDOFF_SESSION_A — DESIGN PATCH (2026-09-17; doc-only)

### SCOPE
Executor for SESSION A DESIGN PATCH on branch `arena/01a0ae7b-upstage`: in-place `APEX_GEN5.md` patches P1–P8 per owner D1–D20, one Appendix AJ row per patch, record sha256 before/after. No code, no tests, no YAML, no new files. Owner D1–D20 block in DECISION_LOG untouched.

### DELIVERED
| # | Artifact | What it is |
|---|---|---|
| 1 | `APEX_GEN5.md` P1 (§9.5 item 14) | Per-close catch-up (D5) + runtime engine order `E01→E02→E12→E04→E03→E10→E09→E05→E06→E11→E07→E08` + engine-context producer contract (38 context + 23 risk keys, every key with its authoritative producer, store seam = public methods only, persisted-rows `events`) + wiring staleness law (D14). CP-14 interface. |
| 2 | `APEX_GEN5.md` P2 (E11 §3.3) | `params/e11_classifier_v1.yaml` artifact (W 9×8, b 9, K 9, label_delay 48, seed, training window/count/query-sha, artifact_sha256; renamed Session-A F2 2026-09-17) + deterministic training procedure (§3.2 labels, 48-candle delay, fixed seed, never zeros/random) + degenerate-class refusal + fail-closed runtime. No formula rewritten. |
| 3 | `APEX_GEN5.md` P3 (Ch.16) | PAPER simulator = same five-op surface off the same `fsm.submit`/`seal` path, no network packet, no signature; `APEX_ALLOW_SIGNED=1` permits the loop, never a packet (D1). |
| 4 | `APEX_GEN5.md` P4 (W.6 Phase 2) | `scripts/run_apex.py replay` CLI contract: whole-store deterministic double run, per-cell canonical hash, byte-identical verdict + zero exceptions, printed envelope feeding G-PAPER-001. CP-15 builds it. |
| 5 | `APEX_GEN5.md` P5 (AI.13/AI.14/Exact Remaining Gates) | D6 sequencing: G-PAPER-001 = Phase-2 double run (entry to PAPER); G-PAPER-002 = 5-day passive measurement (exit towards LIVE); G-TOOBIT-*/G-CAPACITY-*/G-RESTORE-001/G-RISK-001/G-FALLBACK-001/G-LEDGER-001 = pre-LIVE checklist; G-ADAPTER-001 = N/A. Nothing deleted. |
| 6 | `APEX_GEN5.md` P6 (Ch.7) | `CIRCUIT_OPEN` joins the error registry (D9) so vetoes 10–12 carry a code; `apex/errors.py` one-liner deferred to CP-14. |
| 7 | `APEX_GEN5.md` P7 (§9.5 tree + YAML items) | `params/paper_account_v1.yaml` (`capital_usdt: 10000.0` per D4 + simulated-margin inputs) feeds control-plane `paper_balance`; risk thresholds stay in `risk_defaults_v1.yaml` (D8); algorithm/YAML twin rule (§6 wins). |
| 8 | `APEX_GEN5.md` P8 (Ch.23 + AI.13) | 24/7 host = owner phone (Termux+proot+Boot, D19); secrets only in phone `.env` (D17); watchdog chat = owner chat (D20); new G-TOOBIT-004 rotation-evidence row (pre-LIVE checklist). |
| 9 | `APEX_GEN5.md` AJ rows (R.9) | 8 traceability rows, one per patch, dated 2026-09-17. |
| 10 | `PHASE2_DECISION_LOG.md` §C | ADR-SA-001..004 + ISSUE-SESSION-A-001..007 (doc-vs-code conflicts the patch resolved, with line numbers). |
| 11 | `PHASE2_CHECKPOINT_STATUS.md` | CONTINUE(Session A DESIGN PATCH) board line (this session). |
| 12 | `PHASE2_TRACEABILITY_MATRIX.md` | 8 Session A rows (one per patch). |

### RECORD
- BEFORE `sha256(APEX_GEN5.md)` = `216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e` (20551 lines; re-verified immediately pre-edit).
- AFTER `sha256(APEX_GEN5.md)` = `132f702fafbb9cac99488427bf572c1168ad114d7666c85c64a548c9c9539989` (20782 lines; +231).
- AFTER-2 (follow-up F1–F4, same branch/PR) `sha256(APEX_GEN5.md)` = `683ea01db95b9f41e30900c9ad59636a047507838fa3b82930d8b424d0385d56` (20817 lines): F1 tail restored (GC paragraph + blank + one "End of merged document."); F2 artifact renamed to `params/e11_classifier_v1.yaml` + YAML schema; F3 simulator fill law (a)–(f); F4 events wording.
- Suite: `python -m pytest tests -q` twice = 2728 passed / 0 failed each at AFTER, once more = 2728 passed / 0 failed at AFTER-2 (untouched code; pytest + requirements.lock installed into this sandbox only, no repo change).

### INTERFACES (for CP-14 / CP-15)
- CP-14: engine-context producer (P1 key tables are the contract) + `get_bridge_context` store reader + E11 training to `params/e11_classifier_v1.yaml` (P2) + `params/paper_account_v1.yaml` + YAML-fed `paper_balance` + wiring staleness + `CIRCUIT_OPEN` in `apex/errors.py`.
- CP-15: PAPER simulator transport (P3 five ops, no packet) + `scripts/run_apex.py replay` CLI (P4 envelope) satisfying G-PAPER-001.

### OPEN QUESTIONS
1. D9's `apex/errors.py` one-liner and the two new `params/` files are CP-14's; confirm CP-14 owns all three (yes per Programme, but the errors.py split was the executor's call). — ANSWERED 2026-09-17: yes, CP-14 owns all three.
2. The executor brief draft said `capital_usdt: 1000.0`; P7 specifies `10000.0` per owner D4 — confirm 10000 stands. — ANSWERED 2026-09-17: yes, 10000.0 stands.

### PUSH RECORD
- Branch `arena/01a0ae7b-upstage` → exactly ONE PR to `main` (number/URL recorded in the Session A checkpoint board line and the executor's report) — `[Session A] DESIGN PATCH P1–P8 per owner D1–D20`. Suite twice: 2728 passed / 0 failed.

## HANDOFF_CP14 — IN PROGRESS (2026-09-17)

### ARTIFACTS
- `apex/ops/engine_context.py`: implemented lazy P2 artifact validation/hash, D21 training rule0 and delayed-label helpers, D14 freshness measurement, and P7 PAPER account/ledger balance readers. **Not yet an engine-context producer or a store-only trainer CLI**; no get_bridge_context completion claim.
- `params/paper_account_v1.yaml`: exact two-key P7 block, with a comment reference to authoritative risk_defaults; the six existing YAML files are unchanged.
- `tests/fixtures/e11_classifier_v1.yaml`: explicitly synthetic loader-test artifact only. `params/e11_classifier_v1.yaml` remains absent and is not added to .gitignore.
- `apex/ops/bootstrap_service.py`: public catch_up(now_ms), calendar-aware per-timeframe boundary detection, per-cell persisted frontier, source retry reset, existing CP-13 validation/closed-bar law/public ingest path, per-cell failure isolation and counts. Existing bootstrap and manual repair contracts unchanged.
- `apex/ops/paper_loop.py`: optional catch_up callable before stages, JSON catch_up/cell_runs, per-cycle CATCH_UP_FAILED plan admission and next-cycle retry. Execution-stage body unchanged.
- `scripts/run_apex.py`: serve shares the runtime raw store with BootstrapService, wires catch_up, and feeds the control plane the PAPER YAML/ledger balance. **The engine-context bound method is not wired yet.**
- `apex/errors.py`: exact Ch.7 CIRCUIT_OPEN row; no new severity schema, no other registry additions.
- `apex/telegram/control_plane.py`: non-PAPER title no longer displays paper_balance; explicit UNAVAILABLE without that environment's own account source.
- `apex/config.py`: allowlist extended for the two P2/P7 YAMLs; lazy loading retained.
- `apex/data_catalog/store/sqlite_store.py`: only insert_snapshot's body changed under ISSUE-CP14-003, after a reproduced SQLite mapping bind failure; canonical JSON binding for quality_state, no DDL or other method change.
- `apex/engines/e03_volume/engine.py`: ISSUE-CP14-006 fixes the climax calibration's nonexistent ParticipationEvidence.c lookup by passing the actual input bars.
- Tests: new `tests/unit/test_engine_context.py` (28 passing); appended snapshot and E03 regression tests; owner-authorized 23-to-24 registry pin and exact CIRCUIT_OPEN handling test.

### RECORD
- Branch: `arena/01a0afeb-upstage`; unchanged base HEAD `d77ce13a8cde9d241b2bfa368f2f32fec8317e84`. Fetch/head/hash/line-count guard and push dry-run succeeded before repository edits.
- BEFORE `sha256(APEX_GEN5.md)` = `683ea01db95b9f41e30900c9ad59636a047507838fa3b82930d8b424d0385d56` (20817 lines).
- Current AFTER (not final closeout) = `c26603f708f6dc6dfcdf0afaa2d31d96015079b83cc9714f65a0bedf52fae33f` (20841 lines). Only G1 additive tree/traceability and owner-authorized D21/D22 clarifications; no engine formula rewritten.
- Baseline full suite: 2728 passed, 14 warnings, 85.54 s. Initial sandbox pytest absence resolved by installing requirements.lock and the permitted pytest dev extra, without dependency-file changes.
- Post-edit targeted suite: error/config/control-plane/bootstrap/paper-loop = 213 passed, 2 failed (the two obsolete assertions in ISSUE-CP14-009). Snapshot regression passes after its recorded pre-fix ProgrammingError. E03/context/errors targeted = 84 passed before two additional catch-up tests; latest context-only = 28 passed. **No final twice-green suite, no new full-suite total, no completion claim.**

### INTERFACES FOR CP-15
- `BootstrapService.catch_up(now_ms)` returns `{cells_checked, cells_updated, bars_ingested, failures}`; each failure carries cell/symbol/timeframe, status CATCH_UP_FAILED, error_code, attempted frontier (open-time milliseconds or null). Retry resets source delivery state to the fresh persisted maximum; failures do not rewrite raw rows or freshness.
- `PaperRuntime(..., catch_up=async_callable)` invokes catch-up before stages. The failed cell is blocked at setup, no plan_provider call, and its scheduler close is not consumed, allowing retry. Other cells proceed; JSON includes cell_runs. Execution remains unchanged and may not be reached at all if setup/gates refuse. With no adapter and non-READY boot, execution refuses BOOT_NOT_READY; there is no newly added execution DECLARED_SKIP status.
- D22 regression: failed catch-up while the last stored close is within SLA retains freshness_ok=true, reports CATCH_UP_FAILED, produces no plan, and retries next cycle.
- `freshness(window, timeframe, receipt_time=UTC_seconds)` implements exact D14 measurement and iff without touching availability_time. Empty windows fail explicitly NO_MARKET_DATA. The full producer must consume this helper; its integration is pending.
- `load_classifier(path=None)` validates exact P2 schema, 9x8/9 tensors, K=9, delay=48, finite values, recorded metadata and recomputed artifact hash; missing/corrupt artifact raises BridgeError(CONFIGURATION_INVALID). `classifier_hash` uses the canonical JSON authority. No boot-time eager artifact load.
- `training_rule0` and `delayed_training_labels` implement D21 only; feature production, fitting, serialization, process-determinism tests and train-e11 CLI remain pending.
- `paper_balance(ledger)` starts at YAML capital, sums only environment-tagged PAPER OUTCOME P/L, refuses unclassified/missing P/L rather than guessing; LIVE/RESEARCH/BACKTEST outcomes never contribute.

### OPEN QUESTIONS
- ISSUE-CP14-007: absent OI term in store-only E11 training; owner decision required.
- ISSUE-CP14-008: owner capital hard cap and missing P_min timeframe policy/storage; owner decision required.
- ISSUE-CP14-009: permission to replace two obsolete test assertions conflicting with the new requirements.
- Remaining known-pitfall verification, full producer, store-only trainer, real 61-key validation, persisted full-event round trip, engine order test, and final twice-green suite are not complete.
- CP-15 simulator transport, simulator table, replay CLI and execution-stage changes remain out of scope and untouched. Phone acceptance is **not ready**; do not run a nonexistent train-e11 command expecting PASS.

### PUSH RECORD
- No implementation commit or push yet; no PR opened. Exactly one final PR to main remains pending CP-14 completion and the required twice-green suite. No other branch touched; no squash or trained runtime artifact.

### CP-14 continuation record — 2026-09-17 (supersedes stale pending statements above)
- D21(a)–(f) reaffirmed unchanged in explicit owner text, recorded under ISSUE-CP14-001. D23/D24/D25 have resolved issues 007/009/008 design-side; do not re-ask them. The new outstanding decision is ISSUE-CP14-011, the undefined E11 ATR_z and liquidity consumer projections, not initial labels.
- ARTIFACTS: engine_context now includes EngineContextProducer.window/feature_timeline scaffolding, actual first-seven-engine adapter, deterministic full-batch multinomial fitter, atomic supported-YAML writer, and full 24-field EvidenceEvent envelope persistence/readback through insert_evidence. train-e11 --sqlite/--out/--seed/--json is now a real CLI command, but its feature path fails closed while 011 is unresolved. It has not passed successful whole-store training. No get_bridge_context bound method, remaining E05–E08/E11 pipeline, complete 38+23 inputs or serve context_source integration yet.
- ARTIFACTS: decision_runtime_v1.yaml has D25 policy and config allowlist. E11 forwards the artifact hash into snapshot param_hash; D23 dependency markers are in the wrapper, evidence observation_window and snapshot payload. Frozen RegimeState schema remains unchanged. Runtime validated-artifact loading into the bound producer is still pending.
- RECORD: discarded provisional ATR20/20-bar z-score and guessed active-level liquidity aggregation; they were not owner-authorized. The adapter now returns explicit unavailable projections and training refuses, with no artifact write. Raw availability stays unchanged. No trained runtime artifact, no data/ additions, no dependency-file change.
- RECORD: targeted E11/context = 125 passed in 1.51 s, including two-process byte equality of fitter/writer output from a labelled numerical matrix; this is explicitly NOT the required store-derived successful training determinism proof. Two further tests cover actual first-seven engines and the public store derived-close window boundary. Latest expanded targeted suite = 315 passed in 3.11 s. A final fit-only all-nine-class guard was added after that run and awaits the next targeted verification.
- RECORD: full suite run = 2777 passed, 1 failed, 14 warnings in 84.95 s. The sole failure is CP-8's params git-clean assertion because two authorized additive YAMLs are not committed (ISSUE-CP14-014). Preserve that test; commit normally only when appropriate, then perform the required final twice-green runs. This was not a final acceptance run.
- INTERFACES: persist_complete_evidence/read_complete_evidence preserve every semantic field and original explanation; malformed/legacy reduced SQL rows refuse EVIDENCE_CONTEXT_INVALID. Public insert only; no frozen-store change beyond the previously authorized insert_snapshot body.
- OPEN QUESTIONS: owner adjudication of ISSUE-CP14-011 is needed before completing train/serve features. Subsequent audit must still verify full PIT confirmation availability independent of feature refusals, gaps/zero-volume/gap-vector handling shared with runtime, non-H1 history policy, ledger/risk authorities, and actual successful store training in two processes. None is claimed complete here.
- PUSH RECORD: still no implementation commit/push/PR. Execution-stage implementation remains untouched; no simulator/replay or fabricated DECLARED_SKIP.
- Latest verification after the fitter class guard: expanded targeted suite 315 passed in 3.01 s; git diff --check clean. Current AFTER (interim, not closeout) plan SHA256 = acbcd8a32748db3c14179c1383c28023afe6290a242229fa45640eb60740c248, 20856 lines; BEFORE = 683ea01db95b9f41e30900c9ad59636a047507838fa3b82930d8b424d0385d56, 20817 lines. Frozen-path diff lists only the authorized insert_snapshot body; all six original YAMLs and other frozen paths remain unchanged.

### CP-14 D26-A continuation — 2026-09-17
- ARTIFACTS: owner D26-A recorded verbatim in DECISION_LOG. E11 Method-B reference calculation is shared with atr_z_input; the adapter and shared training timeline use E04 VolatilityState.atr14_wilder, prior same-cell history, existing E11 window/minimum/EPS, and the explicit sigma+EPS denominator. No added ATR20 implementation remains; E04 source matches HEAD. E03 consumes lagged published ATR14. Known-series, short-history, window-cap, unchanged-sigmoid, source-alignment, lag and cell-isolation tests added.
- RECORD: before this continuation, plan hash acbcd8a32748db3c14179c1383c28023afe6290a242229fa45640eb60740c248 / 20856 lines; current interim AFTER 6e1570d948767ccdd554f4de2c46368ba46cfe2b67b4fc39cc26a2579049957d / 20858 lines. Exact E11 Section 1.2 sentence and one Appendix AJ row added. Checkpoint BEFORE remains 683ea01db95b9f41e30900c9ad59636a047507838fa3b82930d8b424d0385d56 / 20817 lines.
- TESTS: context/E11/E04/E03 = 250 passed in 25.48 s; final context/E11 = 134 passed in 1.85 s; diff-check clean. No new full-suite run or final twice-green claim; prior full-suite result and ISSUE-CP14-014 remain as recorded.
- INTERFACES / OPEN QUESTIONS: atr_z_input shares E11 rolling_method_b_reference and raises the original INVALID_E11_HISTORY on insufficient/degenerate reference; upstream_frame reports unavailable atr_z, never fills it. ATR history advances independently of unrelated feature refusals, after the current projection. ISSUE-CP14-011 part 1 is resolved by D26-A; awaiting the owner's announced part 2 on liquidity, without reopening D21 or assuming approval of the old recommendation. Complete bound producer/remaining engine order/risk integration and successful store training remain unfinished.
- PUSH RECORD: no commit/push/PR; CP-14 remains IN-PROGRESS, OWNER-CHECKED:[ ]; CP-15 and execution remain untouched.

### HANDOFF_CP14 — D27/D28 current-checkout continuation (2026-09-18)

**ARTIFACTS:** D27 exact uncertainty helper; D28 canonical package/lifecycle/public-fact helpers and EngineContextProducer.decision_inputs; bridge/arbitration zero-weight UNAVAILABLE support; added unit and real-bridge integration tests; ADR-CP14-005; Ch.12, Section 2 snapshot binding, P1 correction, tree annotation and two separate AJ rows. Local commit `4999d86` adds only paper_account_v1.yaml and decision_runtime_v1.yaml including D28. Remaining implementation/docs/tests are uncommitted, not pushed. Runtime classifier absent and never committed.

**RECORD:** D28 recorded verbatim under OWNER ANSWERS. Canonical package input is a filename-keyed map of parsed governed YAMLs using the existing canonical serializer; optional classifier included once; full parameter SHA retained, package suffix is 12 hex, snapshots retain full 64-hex identity. Existing family records survive unchanged; an absent record yields ACCUMULATING without a write. Public facts come only through unsigned public-client reads and retain source/payload hashes and observed-at. Failure snapshots stop stale-success fallback per symbol. LIVE ignores bootstrap; a missing/invalid positive-weight measurement refuses. G1 composition is still pending, not hidden behind a synthetic complete context.

**INTERFACES:** paper_package_binding / paper_bootstrap_inputs are explicitly environment-scoped. read_family_record reads owner SETUP_FAMILY_REGISTRY snapshot payloads without writes. collect_public_venue_facts uses get_exchange_info/get_funding_rate; persist_public_venue_facts requires an explicit PAPER environment and appends via the public snapshot API; read_public_venue_facts enforces full binding and PIT. decision_inputs assembles these source facts for the future complete producer. Their existence does not mean scripts/run_apex.py serve is already bound to them. The bridge now preserves UNAVAILABLE for zero-weight arbitration inputs and never treats them as measured zero/one.

**VALIDATION:** focused suite = 152 passed, 13 warnings, 7.49 s. Full `python -m pytest tests -q` once = 2812 passed, 0 failed, 14 warnings, 95.20 s. Two-process determinism was verified for D28 package identity only, not a successful E11 store-training artifact. Actual public-client tests use the network-free required fake transport; no assertion that today's venue supplies all fact fields. Original six YAMLs, confidence combiner/weights, execution files and cleanliness test unchanged.

**OPEN QUESTIONS:** ISSUE-CP14-018 has no owner answer; do not select a PAPER margin formula, leverage discount, pending-order treatment or CP-15 state. D27/D28 need no re-asking. The current checkout lacked the earlier reported late G1/G2 implementation; reconciliation remains needed (including authorized D26-B projection and complete twelve-engine runtime assembly). Preserve D21 and D27's acceptance of a genuine missing-class refusal on sandbox data; no fabricated class members. Current targeted/full results do not prove full G1/G2 readiness or authorize completion.

**HASH / PUSH RECORD:** current plan AFTER `ffd0681e3af215fa80359139c6da002d67f8aadc7c0f07ed4c7aa0a910841538` / 20865 lines; checkpoint BEFORE `683ea01db95b9f41e30900c9ad59636a047507838fa3b82930d8b424d0385d56` / 20817. Branch `arena/01a0afeb-upstage`; local policy commit 4999d86; no push/PR. The ONE owner-titled completion PR remains due after remaining decisions, implementation/reconciliation and final twice-green verification. OWNER-CHECKED:[ ].
