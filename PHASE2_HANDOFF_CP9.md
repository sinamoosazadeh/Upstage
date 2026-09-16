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
