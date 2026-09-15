# PHASE2 HANDOFF — CP-9 operational wiring (long-run bootstrap command · Telegram receive gateway · 24/7 PAPER loop)

## STATUS
LAW-ACK: G1..G20 + P1..P21 read 2026-09-14T23:25:26Z
DELIVERED (local, in-session): the three pieces the delivered analysis named as missing are
in-tree and green. Full suite at close of this increment: **2627 passed** (was 2553 at the
CP-8 closeout; +74 tests: 72 wiring +2 canonical mirror). Nothing reaches a network in any test.

## DELIVERED
| # | Artifact | What it is |
|---|---|---|
| 1 | `apex/ops/bootstrap_service.py` | the **long-run Phase-1 command**: `BootstrapRunner` (frozen CP-8 contract) + an async venue kline client behind a sync fetcher, an append-only ingest path, the CP-8 checkpoint store (resume), battery/disk preflight and the P0 notifier. Resumable by construction: a page budget or a venue refusal stops with a durable cursor and the next run continues from it. Mirrors every `research_bootstrap_progress` write to the canonical Ch.5 `bootstrap_progress` (phase P1, status DONE/RUNNING/PAUSED/ERROR, fixed-width ISO cursor, 6× locked retry) — ISSUE-CP9-002 & ISSUE-CP9-007. |
| 2 | `apex/telegram/gateway.py` | the **inbound half** of the CP-7 telegram plane: `getUpdates` long-poll source (token from env only), update normalisation, `UpdateDeduplicator` replay guard, OWNER-only routing, and the `BOOTSTRAP_CONTROL` action (`start│pause│resume│stop│progress│eta│continuous on│off`). |
| 3 | `apex/ops/paper_loop.py` | the **24/7 PAPER runtime**: one store + one ledger writer + the 140-cell scheduler + the execution FSM + exits. Nine stages per cell (`ingest → quality → features → engines → setup → gates → risk → decision → execution`), per-close cell de-duplication, cycle trade budget, storage guard, watchdog heartbeat, Telegram polling inside the loop, ledger-chain verification at the end of every run. |
| 4 | `scripts/run_apex.py` | the **composition root**: `bootstrap`, `status` and `serve` commands added on top of the CP-8 `boot│grid│demo│alerts`; `serve` wires store+ledger+bus+scheduler+FSM+gateway+watchdog and registers the `BOOTSTRAP_CONTROL` handler. |
| 5 | `tests/` | `tests/unit/test_ops_bootstrap_service.py` (20), `tests/unit/test_ops_telegram_gateway.py` (28), `tests/integration/test_ops_paper_loop.py` (19) + the store/OI/window fixes' tests. |

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
- ISSUE-CP9-006 (INFO, OPEN, owner-visible): the engine → fabric → setup → forecast → risk → plan
  bridge is the next increment; the runtime is complete up to the provider it does not yet own.
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
1. the plan bridge (ISSUE-CP9-006) — inject a provider; no other runtime change is needed;
2. owner-side: real Telegram token/chat id, a live-network Phase-1 catch-up, and the CP-8 escalations.
