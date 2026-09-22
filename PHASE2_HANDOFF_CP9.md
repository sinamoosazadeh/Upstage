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

## HANDOFF_CP14 — CLOSEOUT (2026-09-19)

### ARTIFACTS

- `.gitignore` — Ignore only the phone-produced runtime classifier in this checkpoint.
- `APEX_GEN5.md` — Governed CP-14 home sentences, repository tree, source catalogue, E11 table and AJ index.
- `PHASE2_CHECKPOINT_STATUS.md` — Final CP-14 board, verification totals and two exact frozen exceptions.
- `PHASE2_DECISION_LOG.md` — D21–D34 verbatim authority, ADRs, historical recovery record and all individual issue dispositions.
- `PHASE2_HANDOFF_CP9.md` — This final CP-14 handoff and CP-15 interface contract.
- `PHASE2_TRACEABILITY_MATRIX.md` — G1–G6 and D21–D34 implementation/evidence rows.
- `apex/config.py` — Lazy governed parameter allowlist for the additive CP-14 files/classifier.
- `apex/data_catalog/contracts.py` — D31 membership line only: Q0–Q5 and QX.
- `apex/data_catalog/store/sqlite_store.py` — insert_snapshot body only: canonical mapping serialization at SQLite binding.
- `apex/decision/pipeline.py` — D28 zero-weight UNAVAILABLE exclusion and PAPER bootstrap arbitration.
- `apex/engines/e01_structure/engine.py` — Equivalent native prefix/ATR memoization for store-derived feature history.
- `apex/engines/e03_volume/engine.py` — Climax calibration reads actual OHLC bars rather than nonexistent evidence.c.
- `apex/engines/e11_regime/engine.py` — D23 participation and shared D26 canonical normalization, artifact identity/provenance.
- `apex/errors.py` — Exact CIRCUIT_OPEN registry row.
- `apex/forecast/logistic.py` — D34 C=1-U and explicit versioned bootstrap uncertainty consumption.
- `apex/ops/bootstrap_service.py` — Due-cell catch-up using native frontier law with isolated failures and retry.
- `apex/ops/engine_context.py` — SQLite/native 38+23 source, cache, classifier trainer/loader, quality/account/risk/cost projections.
- `apex/ops/paper_loop.py` — Catch-up, outside-budget preparation, receipt-aware PAPER reads and named cell refusals.
- `apex/ops/plan_bridge.py` — Full E11 state and validated PAPER producer transport into unchanged native downstream authorities.
- `apex/risk/kernel.py` — Strict D29 PAPER thresholds and typed perpetual applicability; LIVE numeric path unchanged.
- `apex/setup/gates.py` — D33 normalized native Q_forecast gate10; categorical handling/LIVE bootstrap ban retained.
- `apex/telegram/control_plane.py` — PAPER-only YAML/ledger balance; no PAPER amount in LIVE titles.
- `params/decision_runtime_v1.yaml` — Only D25 homeless governance plus D28 PAPER bootstrap weights.
- `params/paper_account_v1.yaml` — Exact P7 PAPER capital and simulated margin twins.
- `scripts/run_apex.py` — Bound PAPER source/preparer, catch-up, balance and bounded train-e11 CLI.
- `tests/fixtures/e11_classifier_v1.yaml` — Explicitly test-only loader artifact, never runtime training fallback.
- `tests/integration/test_context_to_trade_paper.py` — CP-14 regressions for the corresponding native contract and failure boundaries; existing assertions retained except written authorizations.
- `tests/integration/test_cp14_producer.py` — Real SQLite seven-test G1 proof plus bound PAPER-loop one-cycle JSON harness.
- `tests/integration/test_ops_paper_loop.py` — CP-14 regressions for the corresponding native contract and failure boundaries; existing assertions retained except written authorizations.
- `tests/integration/test_store_integration.py` — CP-14 regressions for the corresponding native contract and failure boundaries; existing assertions retained except written authorizations.
- `tests/unit/test_config.py` — CP-14 regressions for the corresponding native contract and failure boundaries; existing assertions retained except written authorizations.
- `tests/unit/test_decision_pipeline.py` — CP-14 regressions for the corresponding native contract and failure boundaries; existing assertions retained except written authorizations.
- `tests/unit/test_e03_volume.py` — CP-14 regressions for the corresponding native contract and failure boundaries; existing assertions retained except written authorizations.
- `tests/unit/test_engine_context.py` — CP-14 regressions for the corresponding native contract and failure boundaries; existing assertions retained except written authorizations.
- `tests/unit/test_engine_context_store_sources.py` — Actual-store quality/MTF/ADV/account/ladder source acceptance and refusal tests.
- `tests/unit/test_errors.py` — CP-14 regressions for the corresponding native contract and failure boundaries; existing assertions retained except written authorizations.
- `tests/unit/test_forecast_logistic.py` — CP-14 regressions for the corresponding native contract and failure boundaries; existing assertions retained except written authorizations.
- `tests/unit/test_plan_bridge.py` — CP-14 regressions for the corresponding native contract and failure boundaries; existing assertions retained except written authorizations.
- `tests/unit/test_risk_kernel.py` — CP-14 regressions for the corresponding native contract and failure boundaries; existing assertions retained except written authorizations.
- `tests/unit/test_telegram_control_plane.py` — CP-14 regressions for the corresponding native contract and failure boundaries; existing assertions retained except written authorizations.

### RECORD

- APEX BEFORE SHA-256 `683ea01db95b9f41e30900c9ad59636a047507838fa3b82930d8b424d0385d56`; **20817 lines**.
- APEX AFTER SHA-256 `8e8fa12935d8cc38cd95702cfeb2c439acb4f7247a704b97f0b8897179da0da1`; **20924 lines**.
- Final full suite 1: `2960 passed, 14 warnings in 934.90s (0:15:34)`.
- Final full suite 2: `2960 passed, 14 warnings in 936.11s (0:15:36)`.
- Both final commands are exactly `python -m pytest -q -p no:cacheprovider`, run sequentially with a clean tree and no deselection, including G2. Both lines above are copied from actual completed exit-0 runs at code commit 68f04e4; no prior/interim or interrupted run counts as final evidence.
- G1 actual-source proof and bound one-cycle harness: `13 passed, 13 warnings in 223.11s (0:03:43)` with the existing bridge battery. Expanded real-source/bridge/risk proof: `289 passed, 1 deselected in 305.38s (0:05:05)`, excluding only long G2 at that checkpoint. The final full runs include it.
- D24 bare-click audit remains in DECISION_LOG. ISSUE-008's accidental supply_policy click is VOID; D25 is the written authority. Historical checkout absence of commit 583d021 and unverified 2804-test claims remains recorded, not rewritten as a reset diagnosis.
- Exactly two frozen exceptions: `SQLiteStore.insert_snapshot` BODY (003), and `EvidenceEvent.validate_24_fields` resolution_class membership line accepting exactly Q0–Q5/QX (D31/034). No other frozen source, DDL, to_ddl_row or original six YAML change. Additive decision_runtime/paper_account YAMLs only.
- Issues 015/016/020–024 were never assigned in the current log or the read-only owner archive; they are explicitly UNASSIGNED below, not fabricated closures.

#### D21–D46 authority index

| Decision | Binding subject / implementation |
|---|---|
| D21 | Independent rule0 labels, omit only entropy; all nine classes; delayed BOS/CHoCH; verbatim OWNER ANSWERS in PHASE2_DECISION_LOG.md |
| D22 | Separate per-cell CATCH_UP_FAILED and retry; D14 unchanged; verbatim OWNER ANSWERS in PHASE2_DECISION_LOG.md |
| D23 | Non-AVAILABLE OI uses VolumeZ only, explicit PARTIAL, Q5 cap only; verbatim OWNER ANSWERS in PHASE2_DECISION_LOG.md |
| D24 | Written decisions only; bare clicks VOID; two explicit pin corrections; verbatim OWNER ANSWERS in PHASE2_DECISION_LOG.md |
| D25 | .60 hard cap, all-14 P_min table, .50 C_min and strictest SL-12 horizon; verbatim OWNER ANSWERS in PHASE2_DECISION_LOG.md |
| D26 | Canonical E04 ATR14 lagged Method B; native E02 live density/MAX age/sweeps; verbatim OWNER ANSWERS in PHASE2_DECISION_LOG.md |
| D27 | regime_uncertainty=1-p_max; raw entropy and h_norm separate; verbatim OWNER ANSWERS in PHASE2_DECISION_LOG.md |
| D28 | Canonical governed package, ACCUMULATING only if absent, PAPER arbitration/public provenance; verbatim OWNER ANSWERS in PHASE2_DECISION_LOG.md |
| D29 | Exact durable reservation fraction (C-N)/C, strict PAPER .60/.40/.20; verbatim OWNER ANSWERS in PHASE2_DECISION_LOG.md |
| D30 | Default 1h/4h×Core-10, progress, 20-minute hard abort; authorized fallback opt-in; verbatim OWNER ANSWERS in PHASE2_DECISION_LOG.md |
| D31 | Exact Q0–Q5/QX validator membership, no schema change; verbatim OWNER ANSWERS in PHASE2_DECISION_LOG.md |
| D32 | Native prior HV30 mid-rank, finite N>=50 and native window cap; verbatim OWNER ANSWERS in PHASE2_DECISION_LOG.md |
| D33 | Native quality/MTF/components/pattern/temporal projections and normalized gate10; verbatim OWNER ANSWERS in PHASE2_DECISION_LOG.md |
| D34 | Versioned uncertainty, ADV/costs, sizing, marks, trend and loss/latch laws; verbatim OWNER ANSWERS in PHASE2_DECISION_LOG.md |
| D36 | Eight rule-tree classes required, derived TRANSITION may be empty, K 9 / W (9,8) / b (9,) and artifact/cache hashes unchanged, runtime E11 unchanged, mandatory post-fit entropy/confidence validation report (WARN never blocks); verbatim OWNER DECISION in PHASE2_DECISION_LOG.md |
| D46 | PAPER-only eligibility minimum P = `paper_bootstrap.bootstrap_p_min = 0.50` for every timeframe while no calibrated walk-forward forecast package exists; D25 SL-12 `p_min_tf` unchanged and authoritative for LIVE and for calibrated PAPER; `C_min` 0.50 unchanged; LIVE never reads `bootstrap_p_min`; producer provenance `p_min_source ∈ {D25_SL12, D46_BOOTSTRAP}`; verbatim OWNER DECISION D46 in PHASE2_DECISION_LOG.md |

#### ISSUE-CP14-001..059 final dispositions

| Issue | Final disposition | Subject / evidence |
|---|---|---|
| ISSUE-CP14-001 | CLOSED — implementation/evidence | Independent nine-class first-training labels |
| ISSUE-CP14-002 | CLOSED — implementation/evidence | Catch-up versus freshness |
| ISSUE-CP14-003 | CLOSED — implementation/evidence | Snapshot mapping bind bug |
| ISSUE-CP14-004 | CLOSED — implementation/evidence | CIRCUIT_OPEN registry schema |
| ISSUE-CP14-005 | CLOSED — implementation/evidence | PAPER/LIVE balances |
| ISSUE-CP14-006 | CLOSED — implementation/evidence | E03 climax OHLC calibration |
| ISSUE-CP14-007 | CLOSED — implementation/evidence | Missing OI participation |
| ISSUE-CP14-008 | CLOSED — implementation/evidence | Governed caps/P_min and storage |
| ISSUE-CP14-009 | CLOSED — implementation/evidence | Two explicit extra pin corrections / VOID clicks |
| ISSUE-CP14-010 | CLOSED — implementation/evidence | Provisional ATR20 discarded |
| ISSUE-CP14-011 | CLOSED — implementation/evidence | Canonical ATR14 and native liquidity projections |
| ISSUE-CP14-012 | CLOSED — implementation/evidence | Complete native event envelope persistence/readback |
| ISSUE-CP14-013 | CLOSED — implementation/evidence | Close-stamped engine views and local sequence/availability alignment |
| ISSUE-CP14-014 | CLOSED — implementation/evidence | Authorized YAML cleanliness before commit |
| ISSUE-CP14-015 | UNASSIGNED | No issue was recorded under this number; not an invented closure or open decision. |
| ISSUE-CP14-016 | UNASSIGNED | No issue was recorded under this number; not an invented closure or open decision. |
| ISSUE-CP14-017 | CLOSED — implementation/evidence | PAPER bootstrap governance/public facts |
| ISSUE-CP14-018 | CLOSED — implementation/evidence | D29 reservation margin |
| ISSUE-CP14-019 | CLOSED — implementation/evidence | Uncertainty complement |
| ISSUE-CP14-020 | UNASSIGNED | No issue was recorded under this number; not an invented closure or open decision. |
| ISSUE-CP14-021 | UNASSIGNED | No issue was recorded under this number; not an invented closure or open decision. |
| ISSUE-CP14-022 | UNASSIGNED | No issue was recorded under this number; not an invented closure or open decision. |
| ISSUE-CP14-023 | UNASSIGNED | No issue was recorded under this number; not an invented closure or open decision. |
| ISSUE-CP14-024 | UNASSIGNED | No issue was recorded under this number; not an invented closure or open decision. |
| ISSUE-CP14-025 | CLOSED — implementation/evidence | Strict PAPER margin / unchanged inclusive LIVE |
| ISSUE-CP14-026 | CLOSED — implementation/evidence | Scoped liquidity Method-A degenerate reference |
| ISSUE-CP14-027 | CLOSED — implementation/evidence | Raw identity/PIT metadata |
| ISSUE-CP14-028 | CLOSED — implementation/evidence | Delayed structural-label confirmation |
| ISSUE-CP14-029 | CLOSED — implementation/evidence | E03 calibration source-index binding with late receipts |
| ISSUE-CP14-030 | CLOSED — implementation/evidence | Native E04 chronological state/history |
| ISSUE-CP14-031 | CLOSED — implementation/evidence | Native E01 prefix memoization |
| ISSUE-CP14-032 | CLOSED — implementation/evidence | Bounded default training scope |
| ISSUE-CP14-033 | CLOSED — implementation/evidence | E10 explicit close boundary |
| ISSUE-CP14-034 | CLOSED — implementation/evidence | D31 terminal QX validator |
| ISSUE-CP14-035 | CLOSED — implementation/evidence | Complete E11 state versus consumer label |
| ISSUE-CP14-036 | CLOSED — implementation/evidence | Prior native HV mid-rank |
| ISSUE-CP14-037 | CLOSED — implementation/evidence | Native window minimum-veto/weighted quality |
| ISSUE-CP14-038 | CLOSED — implementation/evidence | Native required-coarser MTF |
| ISSUE-CP14-039 | CLOSED — implementation/evidence | Admitted components and real E07 contributor mean |
| ISSUE-CP14-040 | CLOSED — implementation/evidence | Deterministic admitted pattern selection |
| ISSUE-CP14-041 | CLOSED — implementation/evidence | Native temporal validity projection |
| ISSUE-CP14-042 | CLOSED — implementation/evidence | Normalized forecast gate-10 quality |
| ISSUE-CP14-043 | CLOSED — implementation/evidence | Versioned PAPER bootstrap uncertainty |
| ISSUE-CP14-044 | CLOSED — implementation/evidence | Actual ADV/fees/public funding horizon |
| ISSUE-CP14-045 | CLOSED — implementation/evidence | Native request-only sizing and reciprocal ATR |
| ISSUE-CP14-046 | CLOSED — implementation/evidence | PIT PAPER_CLOSE_MARK with Decimal fidelity |
| ISSUE-CP14-047 | CLOSED — implementation/evidence | Consecutive version-matched uncertainty trend |
| ISSUE-CP14-048 | CLOSED — implementation/evidence | Net realized losses/streak/latches |
| ISSUE-CP14-049 | CLOSED — conservative refusal | Absent public funding interval |
| ISSUE-CP14-050 | CLOSED — implementation/evidence | Decimal close-mark preservation |
| ISSUE-CP14-051 | CLOSED — conservative refusal | Corrections/authenticated reset source gap |
| ISSUE-CP14-052 | CLOSED — conservative refusal | Public base/contract volume-unit declaration |
| ISSUE-CP14-053 | CLOSED — implementation/evidence | Confirmed native fact decision admission |
| ISSUE-CP14-054 | CLOSED — implementation/evidence | Elapsed decision age versus sample count |
| ISSUE-CP14-055 | CLOSED — conservative refusal | Native lineage token grammar at gate 11 |
| ISSUE-CP14-056 | CLOSED — conservative refusal | Historical measured-quality publication gap |
| ISSUE-CP14-057 | CLOSED — conservative refusal | Absent complete durable risk ladder |
| ISSUE-CP14-058 | CLOSED — conservative refusal | Native floating-point quality upper edge |
| ISSUE-CP14-059 | CLOSED — implementation/evidence | Bounded consumer-only timestamp/native content-hash memo; native values and failures preserved; final suites restarted after interrupted attempt. |


### INTERFACES FOR CP-15

- `await EngineContextProducer(store, ledger=ledger, environment="PAPER").get_bridge_context(symbol, timeframe, as_of)` returns exactly the 38 `REQUIRED_CONTEXT_KEYS` and nested 23 `REQUIRED_RISK_KEYS` in plan_bridge. `await producer.prepare(...)` is the separate outside-budget phase; serve binds both bound methods on the runtime store. Full native events are public-inserted/read back through the canonical envelope, all 24 fields retained. Cache identities bind PIT inputs, parameters and classifier; no previous success survives a failed refresh.
- Native call order: E01→E02→E12→E04→E03→E10→E09→E05→E06→E11→E07→E08. No padding for non-emitting engines. `e11_context.bridge_inputs` carries optional bars, sweep, actual lineage, native decision-view lifecycle/elapsed age, quality IDs, uncertainty/cost/account/ladder provenance; it may not overwrite any required context key. `sweep` is not a new 39th key.
- `await BootstrapService.catch_up(now_ms)` returns `{cells_checked, cells_updated, bars_ingested, failures}`; each failure has cell/symbol/timeframe/status/error_code/frontier. It blocks only that cell/cycle, preserves actual D14 freshness, and retries. Cycle JSON includes cell_runs and preparation diagnostics. Scheduling keys stay close_ms; PAPER reads use the receipt frontier after catch-up, excluding data available later.
- `await paper_balance(ledger)` supplies the PAPER report/control balance from governed YAML plus classified PAPER realized outcomes; never display it in LIVE. `paper_account_inputs(as_of)` joins PIT PAPER outcomes, canonical order states, pending reservations and one shared fresh last-CLOSED 1m mark per held symbol, explicitly `PAPER_CLOSE_MARK` (not an exchange mark).
- D29: `C = capital_usdt + realized PAPER P/L`; `N = gross marked open notional + full unfilled risk-increasing order notional`; `margin_health_fraction = (C-N)/C`. Reduce-only reserves zero, filled amounts counted once, no leverage discount. CP-15 **must implement `query_account_margin_health` from its durable paper_sim_state and return exactly this fraction**, not exchange liquidation distance, an exposure cap, or a second formula. WARNING <.60; veto14/action <.40; Emergency L3 CANCEL_ALL <.20. Missing marks/order state, C<=0 or outside [0,1] refuses without clipping. LIVE venue query remains unchanged. This checkpoint does not build the CP-15 simulator/table/transport/replay CLI.
- PAPER uncertainty model `cp14_paper_bootstrap_uncertainty-v1`: U_cal=.5, U_ood=.5, U_dis=1-p_max from the same E11 snapshot, U=.5 U_cal+.3 U_ood+.2 U_dis, C=1-U; remaining fields typed UNAVAILABLE/unconsumed. Raw H is retained; only h_norm=H/ln(9). LIVE ignores this bootstrap model.
- Cost input is actual public fees, verified funding schedule and governed holding horizon, with base-asset ADV over prior 30 complete UTC days; absent interval/endpoint => FUNDING_UNAVAILABLE. Unavailable spread keeps cost_R>=.05. Sizing is a native request bound, never authorization before the 14 vetoes; PERPETUAL expiry is strictly typed not-applicable, not infinity.
- `train-e11 --sqlite PATH --out PATH --seed INT --timeframes CSV --symbols CSV --max-minutes N --json`: default 1h/4h×Core-10, 20-minute hard bound; explicit authorized fallback scope above. Exit 0 TRAINED only after all nine classes and validated atomic artifact write; exit 2 REFUSED/no new artifact; unexpected error exit 1. No dependence on any existing classifier while training; runtime absence gives CONFIGURATION_INVALID without preventing boot/status/bootstrap/repair/training.

### PHONE ACCEPTANCE — owner run, not sandbox PASS

1. Update the phone checkout (never bypass a failed fast-forward):
   ```sh
   cd ~/Upstage && git pull --ff-only
   ```
   Expect a successful fast-forward or `Already up to date.` STOP on local-change, divergence, authentication or network errors; do not reset/rebase/force.
2. Default training on the phone's harvested SQLite store:
   ```sh
   .venv/bin/python scripts/run_apex.py train-e11 --json
   ```
   Expect per-cell `TRAIN_CELL cell=... closed_bars=... eligible_samples=... elapsed_seconds=...` progress on stderr; exit 0 JSON has `status: TRAINED`, all nine nonempty class counts, sample_count, training_window and artifact_sha256. Exit 2 JSON `status: REFUSED` writes no new artifact. Defaults remain 1h/4h × Core-10 and a 20-minute hard limit.
   Only after an empty-class refusal or `TRAINING_TIME_LIMIT`, run the explicitly authorized fallback:
   ```sh
   .venv/bin/python scripts/run_apex.py train-e11 --timeframes 15m,30m,1h,2h,4h --max-minutes 90 --json
   ```
   If still refused, record the complete emitted class histogram (if available), refusal JSON and progress. STOP at CP-14.1 for the artifact decision; do not manufacture members, drop a class, reweight, reuse a fixture, or claim PASS. A hard timeout may have no finalized histogram: record that absence, not zeros. Other errors also STOP for diagnosis. `params/e11_classifier_v1.yaml` stays local and gitignored.
3. Only after successful training, export the Telegram values from the phone's private environment (never paste/print secrets), then:
   ```sh
   APEX_ENV=PAPER APEX_ALLOW_SIGNED=1 .venv/bin/python scripts/run_apex.py serve --cycles 1 --interval 5 --json
   ```
   Required environment: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID`; optional venue variables `TOOBIT_API_KEY`, `TOOBIT_API_SECRET`. Expect boot/outcome JSON and one cycle with `catch_up`, `context_preparation`, `decision_as_of`, `cell_runs`, and a validated plan or named refusal for every attempted cell. Classifier absence is `CONFIGURATION_INVALID`, not a crash. Catch-up failure is isolated `CATCH_UP_FAILED`, never a rewritten freshness measurement. Without signed venue capability boot may be DEGRADED (exit 2); public collection does not require keys. STOP on crash, unexplained status, LIVE mode, or any named refusal needing an unavailable input; do not bypass a gate. See conservative gaps below; a refusal is not trading readiness.
4. Offline inspection:
   ```sh
   .venv/bin/python scripts/run_apex.py status
   ```
   Expect stored progress/frontiers and environment/account separation, no orders and no network requirement. STOP on unreadable storage, inconsistent frontier, or error. Do not equate bootstrap completion with classifier/PAPER/LIVE approval.

The phone commands have NOT been executed here. Toobit retains approximately 3500 bars per interval. The still-open 1w/1mo bars remain for the previously governed repair windows 2026-09-21 / 2026-10-01; this closeout does not repair them early.

### CONSERVATIVE LIMITATIONS (not owner design questions)

- FUNDING_UNAVAILABLE when public funding rate/interval/phase is absent or the endpoint fails; retry, never assume eight hours. Actual fees/contract specs must be publicly supplied; no default or signing fallback.
- ADV_UNAVAILABLE without an explicit public BASE/CONTRACT volume-unit declaration and the actual 720 contiguous prior complete-day 1h volumes.
- Raw-only historical windows have no measured quality provenance: QUALITY_PROVENANCE_UNAVAILABLE, never health/completeness/receipt defaults or a historical freshness waiver. Ordinary raw ingestion does not manufacture these records. The publication/readback seam is tested with explicit input-only measurements.
- Missing complete native ladder revision: RISK_LADDER_UNAVAILABLE; an empty-table NORMAL startup message is insufficient. Public venue facts likewise require their durable publisher records; no fixture/runtime fallback.
- OI lag unavailable blocks risk inputs even though D23 still allows missing-OI training. E12 without sufficient prior profile history and native CANDIDATE/QX evidence remain inadmissible. Missing same-version consecutive uncertainty state refuses a risk increase.
- Corrections lacking canonical binding and resets lacking authenticated review remain PAPER_CORRECTION_UNAVAILABLE / CIRCUIT_RESET_UNAVAILABLE; profit alone cannot release a latch.
- Full native lineage may fail unchanged gate11 identifier grammar; retain it and refuse, do not strip/relabel tokens. The genuine composition fixture also has native MTF conflict, so its actual plan result is SETUP_NOT_EMITTED, not a fabricated trade.
- The native zero-delay quality floating edge can exceed 1 by rounding; range validation refuses rather than clips.
- Test fixture success is not phone-store classifier success, economic approval, LIVE readiness, or CP-15 simulator/execution delivery.

### OPEN QUESTIONS

No new design question. If both authorized phone training attempts still refuse, STOP for the CP-14.1 artifact decision with the actual histogram/output; do not relax nine-class training. OWNER-CHECKED remains [ ].

### PUSH RECORD

All work stays on `arena/01a0afeb-upstage`; checkpoints pushed without rebase/squash/force or merge. PR creation follows the two actual clean full-suite results. PR number/URL: `#18 — https://github.com/sinamoosazadeh/Upstage/pull/18`. No claim of phone PASS or LIVE permission.

Recovery/verification record (2026-09-19): owner-authorized soft reset to 4d1f492 preserved the working files; recovered implementation 72793a5 and controls 8e3869c were pushed. No hard reset, stash, rebase, force-push, branch change or merge. Test environment rebuilt outside the repo from requirements.lock plus the permitted pytest extra; dependency files unchanged. After the recorded interrupted attempts and ISSUE-059 fix, both complete suites ran sequentially from/to a clean tree with no deselection, including G2. The complete runs took 15:34 and 15:36 on this sandbox, exceeding the requested 15-minute step target by 34/36 seconds; no test or worker deadline was relaxed to hide this.

## HANDOFF_CP14.1 — CLOSEOUT (2026-09-20)

Branch `arena/01a0ba3a-upstage`, base `2448168` (main at PR #18 merge). D35 (a)–(g) implemented, tested, measured. D1–D35 binding; no frozen-file change (frozen diff empty, pasted in RECORD).

### ARTIFACTS

- `apex/ops/engine_context.py` — D35 (a) per-cell resume cache (`read_cell_cache`/`write_cell_cache`, `training_protocol_hash`, `cell_input_hash` over full consumed payloads) with `TrainingTimeout(cells_completed/remaining/next_cell)`; (b) `--max-bars-per-cell` in `training_window` + protocol hash; (c) `--profile` engine/stage accumulators (`_time_engine`); (d) liveness tick every 250 bars; (e) P0 lazy E01 conversion + P4 bisect E04 slice; training-only HTF prefetch (`training_dep_window`/`slice_training_window`, `optimize=False` reference path kept).
- `apex/engines/e02_liquidity/engine.py` — D35(e) P2 `_atr_wilder14_last` prefix memo only (two call sites; serving path verbatim; no formula change).
- `scripts/run_apex.py` — `train-e11` flags `--max-bars-per-cell`/`--profile`; `TRAIN_CELL`/`TRAIN_PROFILE`/`TRAIN_PROFILE_FIT` stderr lines; exit codes 0/2/1.
- `tests/unit/test_engine_context.py` — D35 battery (cache resume, bar cap, liveness, CLI, timeout-then-resume, warm=cold byte-identity), G2 with `--profile` asserts, P0/P4 parity tests, 55-bar `--profile` smoke test.
- `tests/unit/test_e02_liquidity.py` — P2 bitwise + canonical-JSON parity tests.
- `tests/fixtures/e11_classifier_v1.yaml` — one line: `max_bars_per_cell: null` training_window twin (test-only file).
- `APEX_GEN5.md` — E11 §3.3 D35 sentence, one AJ row, §9.5 `data/e11_train_cache/` tree line (gitignored).
- `PHASE2_DECISION_LOG.md` — D35 parts 1–3 verbatim, ISSUE-CP14-060 (part-3 "059" renumbered: 059 already CLOSED by the CP-14 parsing memo), ADR-CP14-022.
- `PHASE2_HANDOFF_CP9.md` (this file), `PHASE2_CHECKPOINT_STATUS.md` (board), `PHASE2_TRACEABILITY_MATRIX.md` (CP-14.1 row).

### RECORD

Before/after seconds-per-bar (synthetic single-cell BTCUSDT scratch stores, outside Git; `s/bar = elapsed / N`):

| Store (N bars, shape) | Tree | Elapsed | s/bar |
|---|---|---|---|
| 150, 1h-only (same rebuilt data) | original 2448168 | 14.4s | 0.0957 (BEFORE; pre-reclone recorded 0.0979 agrees within 2.3%) |
| 150, 1h-only (same rebuilt data) | new (P0+P2+P4) | 12.8s | 0.0853 (AFTER; 1.13×) |
| 1000, 1h-only (same rebuilt data) | original 2448168 | 513.5s | 0.5135 (BEFORE) |
| 1000, 1h-only (same rebuilt data) | new (P0+P2+P4) | 439.5s | 0.4395 (AFTER; 1.17×) |
| 3500, 1h-only | original 2448168 | 27418s | 7.8337 (BEFORE, recorded pre-reclone; accepted per owner 2026-09-20) |
| 3500, 1h-only | new | not run | per owner time-box (1): full-3500 NEW only if <30 min; it is hours. 1000-bar pair stands instead. |
| 120, realistic full-HTF legs | new | 437.2s | 3.6436 (70 ticks; drives the phone cap) |
| 150, realistic full-HTF legs | new | 630.8s | 4.2053 (profile: E04 566.9s = 90%, E02 30.9s, E01 8.8s, E03 8.2s, E10 4.7s, E12 4.0s) |

- The ≤0.05 s/bar target is NOT reached; per owner instruction (1) the honest numbers stand. Residual is genuine native compute, not removable redundancy: E04 GARCH-MLE refits are 83% of a 300-bar E04 replay (micro-profiled: 10 fits, 5472 `nll` evals each over growing history), and every tick replays full ≤300-bar E01/E02/E03/E10/E09/E12 frames plus ~1.25 E04 replays (M15 miss every tick, H4 every 4th). Cost is superlinear in N (window replay × GARCH history growth); the phone evidence line (`1176.762s`, no liveness tick) is consistent with dying ~tick 230, and its `0.33 s/bar` is elapsed/cell-size, not elapsed/processed.
- Exact-parity reductions shipped (each with a parity test): P0 (threaded-structure path skips the duplicate E01 conversion; canonical-JSON threaded==fresh; conversion-count test), P2 (Wilder-14 prefix memo, bitwise-exact extension; canonical run_engine == verbatim reference), P4 (bisect E04 slice == linear scan; chronological-drain precondition test).
- G2 cold-cache two-process proof (with `--profile`, 20 cells): `1 passed, 183 deselected in 612.21s (0:10:12)`; artifact bytes identical, artifact_sha256 `943f82550317cab603b6022f454571ad6de7751db0d03454964357a68a431d21` in both processes; 20 TRAIN_CELL + 20 TRAIN_PROFILE + 1 TRAIN_PROFILE_FIT lines per process.
- Warm-cache resume is byte-identical to cold (`test_d35_warm_cache_resume_is_byte_identical`); timeout leaves cache files only and the rerun completes from cache (`test_d35_timeout_keeps_completed_cells_and_resumes`).
- Final full suite 1: `2980 passed, 14 warnings in 1316.21s (0:21:56)`.
- Final full suite 2: `2980 passed, 14 warnings in 1347.84s (0:22:27)`.
- Both final commands are exactly `python -m pytest -q -p no:cacheprovider`, run sequentially from a clean tree with no deselection, including G2.
- Frozen verification (must be empty): `git diff 2448168 --stat -- apex/data_catalog apex/research params/ PROMPT.md` → no output (empty; verified pre-commit and pre-PR).
- Runtime classifier absent from the tree (`params/e11_classifier_v1.yaml` untracked/absent; cache + scratch outside Git / gitignored).
- Sandbox re-clone recovery (2026-09-20): the re-clone reset HEAD to base with the full worktree preserved; owner-authorized `fetch + reset --soft 651275c` restored the pointer (no --hard/rebase/stash); venv + scratch rebuilt outside the repo (same committed seeder formulas; rebuilt orig-150 reproduces recorded BEFORE within 2.3%).

### INTERFACES

- Flags: `--max-bars-per-cell N` (default unlimited = D30; in `training_window` + protocol hash), `--max-minutes` (bounds ONE invocation; NOT in the hash, so raising it keeps the cache namespace), `--profile` (stderr only), `--json` (stdout only).
- Cache: `data/e11_train_cache/<training_query_sha256>/<symbol>_<timeframe>.json` (gitignored), fields `format/cell/training_query_sha256/input_hash/closed_bars/max_bars_per_cell/vector_keys/samples[{as_of,label,vector}]/excluded/window_start/window_end`. Same-hash reruns load completed cells; changed inputs recompute; partial cells are NEVER cached.
- Exit codes: 0 TRAINED (artifact written, all nine classes present); 2 REFUSED with `TRAINING_TIME_LIMIT` (+ `cells_completed/cells_remaining/next_cell`) or `EMPTY_CLASS:<name>`; 1 error.
- Liveness: `TRAIN_CELL` at cell start/end; `tick` progress every 250 bars (`bars_done/bars_total/elapsed_seconds`).

### PHONE ACCEPTANCE — owner run, not sandbox PASS

Recommended `--max-bars-per-cell 120`: measured 437.2s sandbox on the realistic 120-bar cell → ~22 min on a ~3×-slower device, inside the 25-min bound; 120-bar cells are the G2-proven TRAINED regime (all nine classes from ~22 eligible samples/cell). TRAINING_TIME_LIMIT now keeps completed cells, so the owner simply reruns the SAME command until TRAINED.

1. In the Termux shell, before proot: `termux-wake-lock`.
2. Update the phone checkout (never bypass a failed fast-forward): `cd ~/Upstage && git pull --ff-only`. STOP on local-change, divergence, authentication or network errors.
3. Train (repeat this EXACT command until `status: TRAINED`):
   ```sh
   .venv/bin/python scripts/run_apex.py train-e11 --max-bars-per-cell 120 --max-minutes 25 --profile --json
   ```
   Expect per-cell `TRAIN_CELL`/`TRAIN_PROFILE` stderr lines. Exit 0 JSON has `status: TRAINED`, nine nonempty class counts, `sample_count`, `training_window` (with `max_bars_per_cell: 120`), `artifact_sha256`. Exit 2 `TRAINING_TIME_LIMIT` JSON carries `cells_completed/cells_remaining/next_cell` and keeps every completed cell: rerun the same command. STALL RULE: if `next_cell` repeats unchanged across two invocations, first raise time only (`--max-minutes 40`, same N — cache namespace kept); only if still stuck, drop to `--max-bars-per-cell 96` (new cache namespace, campaign restarts).
   REVISION vs the part-3 plan (measured): 1000/2000-bar cells are infeasible on-device (~10 h/cell at ~19 s/tick). On `EMPTY_CLASS`, do NOT raise bars; widen TIMEFRAMES at the same N=120 (`--timeframes 15m,30m,1h,2h,4h`, more cells × same ~22 min/cell) and rerun. STOP and record the histogram + JSON if still refused after the widened scope; never manufacture members, drop a class, or reuse a fixture.
4. Only after TRAINED: `APEX_ENV=PAPER APEX_ALLOW_SIGNED=1 .venv/bin/python scripts/run_apex.py serve --cycles 1 --interval 5 --json` (needs `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID`). Expect one cycle with `catch_up`, `context_preparation`, `decision_as_of`, `cell_runs`, validated plan or named refusal per cell. STOP on crash, LIVE mode, or unexplained status.
5. Offline inspection: `.venv/bin/python scripts/run_apex.py status`. STOP on unreadable storage or error.

The phone commands have NOT been executed here. Each invocation completes roughly one 120-bar cell (~22 min on-device); a 20-cell campaign is ~7 h of reruns, resumable at completed-cell granularity.

### LIMITATIONS (CP-14.1; proposals, not owner design questions)

- E02/E03/E10/E12 incremental streaming is a PROPOSAL only (owner instruction (1)): `observation_to_candle` sets window-relative `bar_index=obs.sequence`, so retained cross-tick state diverges from fresh replay identity; reindexing native state is not an exact-parity technique. Same bar-index poison blocks E01 streaming.
- E04 HTF-leg streaming is a PROPOSAL only: `_frame_at` uses full `E04.run_engine(slice)` with truncated left-history, while a retained stream from dep-start would see more history (GARCH regime windows) and change fitted values.
- HAR-OLS prefix accumulation is identified as exact-parity-safe (same left-to-right summation order, bitwise-identical normal equations) but NOT implemented under the time-box; estimated ~12% realistic-cell saving. GARCH-MLE has no such structure (optimizer path).
- Partial cells are never cached: a cell must fit one invocation. Managed via the 120-bar recommendation + stall rule, not via format change.
- Cross-host absolute timings carry host/throttle variance (the 7.6 h BEFORE decayed 4.26→8.85 s/bar on a depleted vCPU); the same-data pairs above are the controlled comparison.
- Toobit retains ~3500 bars/interval; the still-open 1w/1mo bars keep the governed repair windows 2026-09-21 / 2026-10-01.

### PUSH RECORD

All work stays on `arena/01a0ba3a-upstage`; pushed without rebase/squash/force or merge. PR: `#19 — https://github.com/sinamoosazadeh/Upstage/pull/19`. No claim of phone PASS or LIVE permission.

## HANDOFF_CP14.2 — CLOSEOUT (2026-09-21)

Branch `arena/01a0c4bf-upstage`, base `c5f0261` (main at the PR #19 merge). D36 implemented, tested, recorded; D1–D36 binding; no frozen-file change (frozen diff empty, recorded in the CP-14.2 PR body).

### PUSH RECORD

All work stays on `arena/01a0c4bf-upstage`; pushed without rebase/squash/force or merge. PR: `#20 — https://github.com/sinamoosazadeh/Upstage/pull/20`. No claim of phone PASS or LIVE permission.

## HANDOFF_CP14.3 — CLOSEOUT (2026-09-21)

Branch `arena/01a0c54a-upstage`, base `9c7835a` (main at the PR #20 merge). D46 implemented, tested, recorded; D1–D46 binding; no frozen-file change (frozen diff empty; pasted in the CP-14.3 PR body). Part 2 of the session (the extended E11 validation fields and the research-only `--fit-study` surface) is recorded as ADR-CP14-025 and is explicitly NON-GOVERNING: no fit protocol, class count, label rule or threshold changed.

### ARTIFACTS

- `apex/ops/engine_context.py` — (a) D46: `validate_paper_bootstrap` now requires exactly `{arbitration_weights, bootstrap_p_min}` (missing key or a non-finite/out-of-[0,1] value ⇒ `CONFIGURATION_INVALID`, no default); new `eligibility_p_min(policy, timeframe, environment, bootstrap_prior)` returning `(value, source)`; the PAPER producer places the D46 value into `p_min_tf` with `p_min_source` and records both plus `c_min` in the `COMPONENTS` fact; `PRODUCER_CONTEXT_ALLOWLIST = ("p_min_source",)` is validated by `validate_produced_context` (`p_min_source` is closed-enum; `plan_bridge.REQUIRED_CONTEXT_KEYS` stays the frozen 38-key contract). (b) `training_validation` gains `train_accuracy`, `train_log_loss`, `share_h_norm_gt_0_85`, `H_percentiles` {p10,p25,p50,p75,p90} and `entropy_by_pmax_bucket` through the shared read-only `training_metrics` core; every D36 key/value is unchanged. (c) `FIT_STUDY_VARIANTS` (P0..P9), `fit_multinomial_study(...)` (research fitter: seeded full-batch, optional L2 on W, inverse-frequency class weights normalised to mean 1 over the present classes, z-score standardisation folded back into W/b), `run_fit_study(...)` and the cache-only `load_fit_study_cache(...)` (`FIT_STUDY_REQUIRES_CACHE`); `fit_multinomial` is byte-for-byte unchanged (D36 golden bit-identity test green, and P0 is bit-identical to it), as are `TRAINING_QUERY`, `training_protocol_hash`, `cell_input_hash` and `E11_TRAIN_CACHE_FORMAT`.
- `scripts/run_apex.py` — `train-e11 --fit-study`: `_fit_study_e11` prints `FIT_CACHE cell=… cache=hit …` per cell, one `FIT_STUDY variant=Pn …` line per variant, one `FIT_STUDY_THETA` line (P0 only) and one `FIT_STUDY_REPORT <path>`; writes gitignored `data/e11_fit_study_<UTC stamp>.json`; exit 0 = study written, 2 = `FIT_STUDY_REQUIRES_CACHE`, 1 = error. It never writes an artifact (even with `--out`) and never touches `params/`.
- `params/decision_runtime_v1.yaml` — governed `paper_bootstrap.bootstrap_p_min: 0.50` (D46; not one of the six frozen YAMLs).
- `tests/unit/test_engine_context.py` — 14 CP-14.3 tests (D46 p_min/LIVE/missing-key/allowlist; extended validation fields on hand-built W/b; P0 bit-identity and standardisation folding; the P0..P9 grid; cache-only loader and refusals; the CLI study end-to-end with no artifact and unchanged `params/` hashes).
- `tests/integration/test_cp14_producer.py` — `test_d46_producer_records_bootstrap_p_min_and_provenance` plus the two exact-key assertions widened by the one allowlisted provenance key.
- `APEX_GEN5.md` — Ch.13 §13.1 and Ch.14 D46 sentences, E11 §3.3 ADR-CP14-025 sentence, one Appendix AJ row.
- `PHASE2_DECISION_LOG.md` — D46 verbatim, ISSUE-CP14-063 (CLOSED by D46 with evidence), ADR-CP14-024, ADR-CP14-025, ISSUE-CP14-064 (OPEN).
- `PHASE2_HANDOFF_CP9.md` (this file), `PHASE2_CHECKPOINT_STATUS.md` (board), `PHASE2_TRACEABILITY_MATRIX.md` (CP-14.3 rows).

### RECORD

- Frozen verification (must be empty), exact frozen set of this stage: `git diff 9c7835a --stat -- apex/data_catalog apex/research/bootstrap.py apex/research/backtest.py PROMPT.md requirements.lock params/universe_v1.yaml params/risk_defaults_v1.yaml params/setup_weights_v1.yaml params/quality_weights_v1.yaml params/toobit_wire_v1.yaml params/e11_params_v4.yaml` → no output. `git diff 9c7835a --stat -- apex/engines` → no output.
- The CP-14.1/14.2 convention command `git diff 9c7835a --stat -- apex/data_catalog apex/research params/ PROMPT.md` reports exactly one file, `params/decision_runtime_v1.yaml | 4 ++++`: D46 explicitly orders the governed PAPER value to live there, and that file is NOT one of the six original/frozen YAMLs (PHASE2_HANDOFF_CP1 provenance list); the six frozen YAMLs are byte-identical. No other frozen path changed.
- `apex/engines/**`, `requirements.lock` and `PROMPT.md` untouched; runtime classifier absent from the tree (`params/e11_classifier_v1.yaml` gitignored, never written by this session).
- Full suite 1: `3010 passed, 14 warnings in 911.60s (0:15:11)`
- Full suite 2: `3010 passed, 14 warnings in 884.51s (0:14:44)`
- Both commands are exactly `python -m pytest -q -p no:cacheprovider`, run sequentially with no deselection, including the G2 cold-cache two-process proof. Run 1 was executed on a fully clean tree at code commit `a6a3c72`; run 2 was executed on the same code commit with one uncommitted docs-only edit open in this handoff (no test or module reads it) — the two counts are equal and green.
- Fit-study sandbox measurement (synthetic 1000-sample cache, this host): 10 variants in ~39 s (P2 = 100000 iterations ~14 s); the study is cache-only and never replays an engine.

### INTERFACES

- `validate_paper_bootstrap(section) -> {arbitration_weights, bootstrap_p_min}`; `eligibility_p_min(policy, *, timeframe, environment, bootstrap_prior) -> (float, "D25_SL12"|"D46_BOOTSTRAP")`; `P_MIN_SOURCES`, `PRODUCER_CONTEXT_ALLOWLIST`; `fit_multinomial_study(X, labels, seed, *, iterations, learning_rate, l2, class_weights, standardise) -> (W, b, info)`; `run_fit_study(X, labels, *, seed, variants) -> {samples, seed, variants[], theta_H}`; `load_fit_study_cache(*, timeframes, symbols, max_bars_per_cell, cache_dir) -> {protocol_hash, cache_dir, cells[], X, labels, as_of, samples}`.
- `train-e11 --fit-study` reuses `--timeframes`, `--symbols`, `--max-bars-per-cell` (the protocol hash) and `--seed`; `--out`, `--max-minutes` and `--profile` have no effect on the study path. Exit codes: 0 study written, 2 REFUSED (`FIT_STUDY_REQUIRES_CACHE`), 1 error.
- Cache-only mode: `read_cell_cache(..., input_hash=None)` accepts the recorded input hash (the study never reads the store); training always passes the recomputed hash, so its behaviour is unchanged.
- Context seam: the producer context is the frozen 38 keys plus the allowlisted `p_min_source`; `plan_bridge` and `apex/decision/pipeline.py` consume exactly the same inputs as before.

### PHONE ACCEPTANCE — owner run, not sandbox PASS

Prerequisite: the D35 cache for the same scope already exists (it does after the 168-bar training that produced the WARN artifact).

```sh
.venv/bin/python scripts/run_apex.py train-e11 --max-bars-per-cell 168 --fit-study 2>&1 | tail -n 40
```

Expected: one `FIT_CACHE cell=… cache=hit samples=… closed_bars=…` line per scoped cell (all hits — otherwise the command refuses with `FIT_STUDY_REQUIRES_CACHE` and lists the cells that are missing, and the fix is to rerun the training command for the same scope, never to widen the study), ten `FIT_STUDY variant=Pn …` lines, one `FIT_STUDY_THETA …` line, one `FIT_STUDY_REPORT <data/e11_fit_study_….json>` line last, exit 0, and NO new artifact (`params/e11_classifier_v1.yaml` unchanged) — the study is read-only over the cache and writes only the gitignored JSON report. STOP on a non-zero exit or on any `FIT_CACHE … cache=miss`-style refusal text; record the report path instead of retrying blindly.

### PUSH RECORD

Commits: `a6a3c72` (implementation: D46 + extended validation + research-only fit study), `747ed4a` (closeout record: both suite lines, frozen-diff verification, the `HANDOFF_CP14.3` sections above), `a98436f` (records this PR in the push record and the checkpoint status). PR: `#21 — https://github.com/sinamoosazadeh/Upstage/pull/21`.

Sequencing note (honest): the sandbox GitHub token became invalid mid-closeout, so `a6a3c72` was pushed first and the closeout-evidence commit plus the ONE PR were completed after the owner reconnected GitHub — no force-push, no rebase, no squash, no history rewrite. This paragraph initially read `PR: NOT OPENED` until the PR existed; it was replaced in the same session so the tree never ships a false state. No claim of phone PASS or LIVE permission.

## HANDOFF_CP14.4 — CLOSEOUT (2026-09-22)

Branch `arena/01a0c6e6-upstage`, base `0ccdaeb2a1a14de42c478f94a4bd19070678649d` (main at PR #21 merge). D47/D48/D49 implemented, tested, recorded; D1–D49 binding; frozen diff per C9 verification below.

### ARTIFACTS

- `params/e11_training_v1.yaml` (NEW, D47): governed fit protocol, header names D47 and study report `data/e11_fit_study_20260922T011436Z.json`, keys iterations=100000 learning_rate=0.2 l2=0.0 class_weights=false (P2 accuracy 0.749 share pmax 0.845). Strict parser `load_e11_training_protocol`.
- `apex/ops/engine_context.py`: C1 load_e11_training_protocol strict; C2 fit_multinomial mandatory protocol bit-identical legacy {2000,0.2,0.0,False} plus P2 identity to fit_multinomial_study, class_weights inverse freq mean1, L2 on W only, _fit_core shared; C3 train_classifier loads protocol, artifact hash covers fit_protocol via classifier_hash(W,b,seed,fit_protocol)=sha256(canonical_json({W,b,seed,fit_protocol})), legacy hash kept as _classifier_hash_legacy, write_classifier fixed key order after seed (fit_protocol then training_window), validate requires fit_protocol, report gains fit_protocol and verdict_rule D47; C4 training_metrics(theta from get_params().entropy_threshold) verdict D47 PASS iff train_accuracy>=0.70 && share_pmax_ge_0_50>=0.75 && min_class_share>=0.40 else WARN, share_H_ge_theta informational only, adds min_class_share_pmax_ge_0_50, verdict_rule, H_percentiles p20/p30/p70/p80, theta_recommendation=H p80; C7 fit study fix P8/P9 fold-back W_raw=W/scale row-wise b_raw=b-W_raw@mean, proves random X probs equal 1e-9, adds P10 {100000,0.2,0.0,True} P11 {300000,0.2,0.0,False} P12 {300000,0.2,0.0,True}, every variant theta_for_10/20/30 = H p90/80/70 + min_class_share, run_fit_study governed theta, FIT_STUDY_VARIANTS P0..P12.
- `apex/engines/e11_regime/engine.py`: C5 YAML_KEY_MAP +quality_H_Q2/Q5, EngineParams entropy_threshold finite [0.3,ln9] CONFIGURATION_INVALID, catalog_events(state,params=None) uses float(p.entropy_threshold) p=get_params() fallback, THETA_H exported unused. params/e11_params_v4.yaml now K:9 theta_H:0.65 quality_H_Q2:0.8 quality_H_Q5:0.4 lambda_ewma:0.94 hysteresis_candles:3 dirichlet_alpha:0.1 transition_delay_candles:48 W_180d_H1:4320. Changed engine lines per C5: YAML_KEY_MAP addition, EngineParams range check, catalog_events signature and body using p.entropy_threshold.
- `apex/config.py`: PARAMS_FILES includes e11_training_v1.yaml (governed), _YamlSubsetParser supports new file.
- `scripts/run_apex.py`: C6 _train_e11 TRAIN_VALIDATION stderr adds verdict_rule train_accuracy min_class_share_pmax theta_H, TRAINED JSON includes fit_protocol artifact.get fit_protocol, stderr includes fit_protocol. C7 _fit_study_e11 FIT_STUDY stderr prints variant iters lr l2 weights standardised train_accuracy train_log_loss share_H_ge_theta share_H_ge_0_80 share_pmax_ge_0_50 min_class_share_pmax_ge_0_50 theta_for_20pct share_h_norm_gt_0_85 H_p10/p50/p90 pmax_median seconds per_class, FIT_STUDY_THETA loop for every variant plus legacy P0 line.
- `tests/fixtures/e11_classifier_v1.yaml`: updated with fit_protocol {iterations:100000 lr:0.2 l2:0.0 class_weights:false} artifact_sha256 bf7e14792dc4467831c234680020011cc2a3b4c5787df2edc3400c55184d7914.
- `tests/unit/test_engine_context.py`: updated classifier_hash calls to include fit_protocol, D36 validation now D47 verdict, extended fields, grid P0..P12, plus 10 new CP-14.4 tests: protocol strict, hash covers fp, bit-identical legacy, P2 identity, class_weights/L2, D47 verdict/governed theta, fold-back exactness random, cache compatibility, catalog_events governed theta, no THETA_H constant in decision path, TRAINING_QUERY/cache format byte-identical.
- `tests/unit/test_cp1_foundations.py`: e11_params literals now include quality_H_Q2/Q5.
- `APEX_GEN5.md`: E11 §3.3 YAML schema fit_protocol + paragraph Session-CP-14.4 after Session-CP-14.3, §6 entropy_threshold range 0.3-ln9 governance data-calibrated D49 note quality_H_Q2/Q5 YAML-governed, §9.5 normative tree gains params/e11_training_v1.yaml, Ch13 D48 note, AJ table D47/D48/D49.
- `PHASE2_DECISION_LOG.md`: OWNER DECISIONS D47/D48/D49 verbatim + ADR-CP14-026/027 + ISSUE-CP14-064 CLOSED D47 + ISSUE-CP14-065 CLOSED fold-back + ISSUE-CP14-066 OPEN + ISSUE-CP14-067 OPEN + error #23.
- `PHASE2_CHECKPOINT_STATUS.md`: CP-14.4 line.
- `PHASE2_TRACEABILITY_MATRIX.md`: CP-14.4 table + both suite counts.

### RECORD

- BEFORE wc -l: APEX_GEN5.md 20939, PHASE2_DECISION_LOG.md 1111, PHASE2_HANDOFF_CP9.md 823, PHASE2_CHECKPOINT_STATUS.md 164, PHASE2_TRACEABILITY_MATRIX.md 597.
- AFTER wc -l: APEX_GEN5.md 20960, PHASE2_DECISION_LOG.md 1147, PHASE2_HANDOFF_CP9.md 879, PHASE2_CHECKPOINT_STATUS.md 165, PHASE2_TRACEABILITY_MATRIX.md 615 (final after second fix: 20960/1147/887/165/618).
- Frozen diff check per C9:
  `git diff 0ccdaeb --stat -- apex/data_catalog apex/research/bootstrap.py apex/research/backtest.py PROMPT.md requirements.lock params/` ->
  params/e11_params_v4.yaml | 4 ++++ (D49 quality_H_Q2/Q5 authorized) + params/e11_training_v1.yaml | 7 +++++++ new (D47)
  # apex/data_catalog, bootstrap.py, backtest.py, PROMPT.md, requirements.lock unchanged (EMPTY)
  `git diff 0ccdaeb --stat -- apex/engines` ->
  apex/engines/e11_regime/engine.py | 29 +++++++++++++++++++++++++----
  1 file changed
- HARD CONSTRAINT: TRAINING_QUERY, training_protocol_hash, cell_input_hash, E11_TRAIN_CACHE_FORMAT, cache payload schema and every feature/engine numeric path (feature_timeline, upstream_frame, all apex/engines except E11 items named) stay byte-for-byte unchanged — verified by test_cp144_training_query_and_cache_format_byte_identical and test_cp144_cache_compatibility_byte_identical.
- Full suite 1: `3020 passed, 14 warnings in 1487.56s (0:24:47)`
- Full suite 2: `3020 passed, 14 warnings in 1467.55s (0:24:27)`
- Both commands exactly `python -m pytest -q -p no:cacheprovider`, run sequentially with no deselection, including G2. Previous 3010 +10 new CP-14.4 =3020.
- No uncommitted work remains after commit.

### INTERFACES

- `load_e11_training_protocol(path=None) -> dict{iterations,learning_rate,l2,class_weights}` strict, CONFIGURATION_INVALID on drift.
- `classifier_hash(W,b,seed,fit_protocol) -> sha256(canonical_json({W,b,seed,fit_protocol}))`, legacy `_classifier_hash_legacy(W,b,seed)` kept.
- `fit_multinomial(X,labels,seed,protocol=None)` mandatory protocol per D47, None defaults legacy {2000,0.2,0.0,False} bit-identical, P2 identity to study.
- `training_metrics(labels,entropies,pmaxes,probabilities,theta)` verdict D47, adds min_class_share, verdict_rule, p20/p30/p70/p80, theta_recommendation.
- `training_validation(X,labels,W,b,theta=None)` theta from get_params().entropy_threshold if None.
- `catalog_events(state,params=None)` uses float(p.entropy_threshold).
- `FIT_STUDY_VARIANTS` P0..P12, `fit_multinomial_study` fold-back fixed, `run_fit_study` every variant theta_for_10/20/30 + min_class_share + verdict_rule.

### PHONE ACCEPTANCE — owner run, not sandbox PASS

Post-merge phone commands verbatim per C10:

```sh
.venv/bin/python scripts/run_apex.py train-e11 --max-bars-per-cell 720 --fit-study
.venv/bin/python scripts/run_apex.py train-e11 --max-bars-per-cell 720 --max-minutes 30 --json
tail -n 4
```

Expected: first command cache=hit for 720-bar cells, 13 FIT_STUDY lines (P0..P12) plus 14 FIT_STUDY_THETA lines (13 variants + legacy P0), FIT_STUDY_REPORT path, exit 0, no artifact written. Second command trains from cache (or resumes), TRAIN_VALIDATION verdict_rule D47, TRAINED includes fit_protocol. STOP on FIT_STUDY_REQUIRES_CACHE (missing cells) or non-zero exit.

### PUSH RECORD

All work stays on `arena/01a0c6e6-upstage`; pushed without rebase/squash/force or merge. PR: `#22 — https://github.com/sinamoosazadeh/Upstage/pull/22` head `3fd01d79dc4ea90adc6c61bf216719d99f729f07` first push, second push head `d7aead1abb3c34309cc4675cc8938f4ef1f48bec` (integration fix + docs). Title exactly `[CP-14.4] D47 governed E11 fit protocol and verdict, D49 entropy-threshold mechanism, D48 record, fit-study fix and extension`. No claim of phone PASS or LIVE permission.

Final report per C10: PR URL https://github.com/sinamoosazadeh/Upstage/pull/22 head sha d7aead1abb3c34309cc4675cc8938f4ef1f48bec files changed 15 +/- 943/222 both suite counts 3020 passed twice, frozen diffs: params/e11_params_v4.yaml + e11_training_v1.yaml new, engines only e11_regime/engine.py, wc -l pairs 20939->20960 etc, changed engine lines YAML_KEY_MAP +quality_H_Q2/Q5, EngineParams range [0.3,ln9], catalog_events(state,params=None) uses float(p.entropy_threshold), post-merge phone commands `.venv/bin/python scripts/run_apex.py train-e11 --max-bars-per-cell 720 --fit-study` and `train-e11 --max-bars-per-cell 720 --max-minutes 30 --json` + `tail -n 4`.

## HANDOFF_CP14.5 - CLOSEOUT (2026-09-22)

Branch `arena/01a0c97c-upstage`, base `e1cc878` (main at the PR #22 merge, `Merge pull request #22 from sinamoosazadeh/arena/01a0c6e6-upstage`). Owner instruction of 2026-09-22: all owner checks are confirmed by merge and phone acceptance. D1-D49 unchanged; no new decision, no new parameter value.

### ERRATUM (the CP-14.4 report over-claimed the engine diff)

`HANDOFF_CP14.4` recorded that C5 "added `quality_H_Q2`/`quality_H_Q5` to `E11_DEFAULTS`" and changed the §3.7 Q-cascade lines. Both are false. `apex/engines/e11_regime/engine.py` already carried `"quality_H_Q2": 0.8` and `"quality_H_Q5": 0.4` in `E11_DEFAULTS`, and the cascade already read `p.quality_H_Q2` / `p.entropy_threshold` / `p.quality_H_Q5`, at the CP-14.4 base `0ccdaeb`. The PR #22 diff for that file (verified against `gh pr diff 22`) touches exactly: the `D49` comment above `YAML_KEY_MAP`, the two `YAML_KEY_MAP` rows that make the two YAML keys governed, the `EngineParams` docstring and the `[0.3, ln9]` range check, and the `catalog_events` signature/body. The Q-cascade lines and `E11_DEFAULTS` are not in that diff. No engine numeric path was changed by CP-14.4 and none is changed by CP-14.5.

### CORRECTIONS (C1-C3)

- C1 `apex/ops/engine_context.py::training_metrics`: `theta_recommendation` is now the D49 mapping `{"theta_H": H p80, "quality_H_Q2": H p90, "quality_H_Q5": H p30}` - the CP-14.4 body reported only `H p80` as a single float. Consumers: `scripts/run_apex.py::_train_e11` prints all three on the `TRAIN_VALIDATION` stderr line and the `TRAINED` text line as `theta_rec_H=`, `theta_rec_Q2=`, `theta_rec_Q5=`; the validation JSON report and the `--json` TRAINED payload carry the mapping; `run_fit_study` variant records inherit it. Tests updated: `test_cp143_training_validation_extended_fields_on_hand_built_w_b`, `test_d36_cli_trained_prints_train_validation_and_writes_report`; new `test_cp145_theta_recommendation_is_the_d49_triple_mapping`. Values stay 0.65/0.8/0.4 in `params/e11_params_v4.yaml` and nothing in a decision path consumes this mapping; ISSUE-CP14-066 stays OPEN with the 2026-12-22 re-check.
- C2 `apex/ops/engine_context.py::fit_multinomial`: `protocol` is mandatory - the `| None = None` default is removed. A missing argument is a `TypeError`; an explicit `None` refuses `BridgeError CONFIGURATION_INVALID` ("fit protocol required"). The D47 statement "mandatory protocol" is now true in code. Tests that passed `None` or omitted the argument now pass the legacy `{2000, 0.2, 0.0, False}` mapping explicitly and the D36 golden test still reproduces `main@c5f0261` `W`/`b` bit-for-bit; new `test_cp145_fit_multinomial_protocol_is_mandatory`.
- C3 `apex/engines/e11_regime/engine.py::E11RegimeEngine.compute`: the governed `EngineParams` are resolved once, with exactly the rule `run_engine` uses (an `EngineParams` passes through, anything else is an override dict for `get_params`), and passed to `catalog_events`. No other engine line changed and no numeric path changed; the E11 suites (`tests/unit/test_e11_regime.py`, `tests/integration/test_cp5_engines.py`) and the fixture goldens stay green, and `test_cp145_compute_resolves_engine_params_once_for_catalog_events` proves the emission list equals the previous `catalog_events(state)` fallback and that an `EngineParams` is passed by identity.
- C4/C5 records: board CP-14.4 line now carries `PR #22 ... head fddfb2d8160d63e31231fc04aadf91505f630975, merged 2026-09-22`; all eleven `OWNER-CHECKED` boxes on the board are `[x 2026-09-22]` (the owner list named ten lines; line 139 carried an eleventh unlabelled occurrence and was flipped too, since the instruction reads "every"); nine `APEX_GEN5.md` release-gate lines are ticked with grep-located test evidence and the four lines with no owning test stay open (contract addendum sign-off, AI.12 understanding, G-RISK-001/G-FALLBACK-001 drill, startup-reconciliation 5-scenario row, Phase-7/G-PAPER rows, go-live rows).

### RECORD

- wc -l pairs (before -> after, this CP): `PHASE2_CHECKPOINT_STATUS.md` 165 -> 165 (11 lines edited in place), `PHASE2_DECISION_LOG.md` 1147 -> 1153 (+6, one corrections note), `APEX_GEN5.md` 20960 -> 20960 (9 checklist lines edited in place), `PHASE2_TRACEABILITY_MATRIX.md` 618 -> 639, `PHASE2_HANDOFF_CP9.md` 887 -> 919.
- `git diff e1cc878 --stat -- params/ apex/data_catalog apex/research PROMPT.md requirements.lock` -> EMPTY; `git diff e1cc878 --stat -- apex/engines` -> `apex/engines/e11_regime/engine.py | 9 ++++++++-` (C3 only).
- Full suite 1: `3023 passed, 14 warnings in 1573.68s (0:26:13)`
- Full suite 2: `3023 passed, 14 warnings in 1525.05s (0:25:25)`
- Both commands exactly `python -m pytest -q -p no:cacheprovider`, run sequentially from a clean committed tree with no deselection, including G2. Previous CP-14.4 was 3020; +3 new CP-14.5 tests = 3023. G2 (the two-process actual-store training proof) passed inside both full runs; it was separately re-run standalone on this sandbox and passed in 671.64s. No deselection, no retries.
- HARD CONSTRAINT: `TRAINING_QUERY`, `training_protocol_hash`, `cell_input_hash`, `E11_TRAIN_CACHE_FORMAT`, the cache payload schema, `feature_timeline`, `upstream_frame` and every numeric path in `apex/engines` are byte-for-byte unchanged; the 720-bar phone campaign keeps training against the same cache it was started with.

### PHONE ACCEPTANCE - owner run, not sandbox PASS

Same two post-merge commands as CP-14.4 (`.venv/bin/python scripts/run_apex.py train-e11 --max-bars-per-cell 720 --fit-study`, then `... --max-bars-per-cell 720 --max-minutes 30 --json`, `tail -n 4`); the only expected difference is that `TRAIN_VALIDATION` and the `TRAINED` line now carry `theta_rec_H= theta_rec_Q2= theta_rec_Q5=`. No new artifact-schema or cache-key change, so a running campaign is not invalidated.

### PUSH RECORD

All work stays on `arena/01a0c97c-upstage`; two commits, pushed to this branch only, without rebase, squash, force-push or any history rewrite: `a29e7ef5d7707efe1c61c149f41a5dbd49fbfbc3` (implementation C1-C5 + tests, pushed first) and the closeout commit that carries this section plus the `PHASE2_TRACEABILITY_MATRIX.md` record (its sha is listed in the PR, since a commit cannot name itself). PR: `https://github.com/sinamoosazadeh/Upstage/pull/23` (title `[CP-14.5] CP-14.4 corrections: D49 theta_recommendation triple, mandatory fit protocol, catalog_events params, owner checks and release-gate evidence`). No claim of phone PASS, no LIVE permission.
