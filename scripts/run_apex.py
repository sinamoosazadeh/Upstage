#!/usr/bin/env python3
"""APEX_GEN5 — the CP-7 runtime entry point (composition root).

One command, four surfaces, all fail-closed (G6):

    python scripts/run_apex.py boot     # environment init → dependency load →
                                        # reconcile-first boot → verdict
    python scripts/run_apex.py grid     # the 140-cell universe + min-cap
                                        # leverage + last TF closes (no orders)
    python scripts/run_apex.py demo     # the WHOLE PAPER loop on a fixture
                                        # clock against the fake Toobit
                                        # responder (test double, no network)
    python scripts/run_apex.py alerts   # the Ch.23 alert-policy self-check

The two LONG-RUN surfaces (the wiring increment, `apex/ops/*` + `apex/telegram/
gateway.py`):

    python scripts/run_apex.py bootstrap  # W.6 Phase 1: the FIRST LONG RUN —
                                          # 140 cells × 1000-bar pages from
                                          # 2020-01-01 into the raw store, with
                                          # a durable cursor (resume anytime)
    python scripts/run_apex.py serve      # the 24/7 runtime: reconcile-first
                                          # boot, the 140-cell scheduler, the
                                          # SL-5 → SL-6 trade_plan queue, the
                                          # execution FSM → venue, alerts,
                                          # watchdog heartbeat, storage guard
                                          # and the inbound Telegram gateway
    python scripts/run_apex.py status     # offline: bootstrap progress from the
                                          # durable checkpoints (no network)
    python scripts/run_apex.py repair-partial  # CP-13: governed repair of
                                          # partial bars stored before close
                                          # (dry-run by default; --apply
                                          # writes via frozen correct_raw)

CP-14.3 adds ONE research-only surface: `train-e11 --fit-study` evaluates the
named fit-protocol grid (P0..P9) over the D35 per-cell cache, prints one
FIT_STUDY line per variant and writes data/e11_fit_study_<UTC stamp>.json. It
never recomputes a feature, never writes a classifier artifact and never
touches params/.

Composition (Ch.23 L18253–18260): ONE event loop, ONE ledger writer queue, the
execution FSM as the only path to the venue, the scheduler as the only source of
cell timing, Telegram as the only display surface.

Secrets are read from the environment ONLY (never printed, never stored):
``TOOBIT_API_KEY``, ``TOOBIT_API_SECRET``, ``TELEGRAM_BOT_TOKEN``,
``TELEGRAM_OWNER_CHAT_ID``, ``TELEGRAM_WATCHDOG_CHAT_ID``. Governed switches:
``APEX_ENV`` (PAPER|LIVE|RESEARCH|BACKTEST — no SHADOW), ``APEX_ALLOW_SIGNED``
(required for any PAPER/LIVE order, Y.1 L17093), ``APEX_ECONOMIC_GATE_SIGNED``
(LIVE capital only — CP-7 never requires it), ``APEX_SQLITE_PATH``.

Exit codes: 0 = READY, 2 = DEGRADED / refused, 3 = RECOVERY_REQUIRED,
1 = unexpected error (fail-closed, never a silent success).
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apex.bus import EventBus, Priority                        # noqa: E402
from apex.config import Config                                # noqa: E402
from apex.data_catalog.contracts import (                     # noqa: E402
    CORE10_SYMBOLS, TIMEFRAMES_14)
from apex.data_catalog.store import sqlite_store as ss        # noqa: E402
from apex.errors import get_error_code                        # noqa: E402
from apex.execution import fsm as F                           # noqa: E402
from apex.execution.toobit_adapter import (                   # noqa: E402
    AdapterError, ToobitAdapter)
from apex.ledger import store as LS                           # noqa: E402
from apex.scheduler import clock as C                         # noqa: E402
from apex.telegram import control_plane as CP                    # noqa: E402
from apex.telegram import gateway as GW                        # noqa: E402
from apex.telegram import signaling as SG                      # noqa: E402
from apex.ops import bootstrap_service as BS                   # noqa: E402
from apex.ops import paper_loop as PL                          # noqa: E402
from apex.ops import partial_bar_repair as PR                  # noqa: E402
from apex.ops import engine_context as EC                      # noqa: E402
from apex.ops import plan_bridge as PB                          # noqa: E402
from apex.ops import watchdog as WD                            # noqa: E402

EXIT_READY = 0
EXIT_ERROR = 1
EXIT_DEGRADED = 2
EXIT_RECOVERY = 3


def _say(text: str = "") -> None:
    print(text, flush=True)


def _iso(ms: int) -> str:
    moment = dt.datetime.fromtimestamp(ms / 1000.0, dt.timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


def _redacted(cfg: Config) -> Dict[str, Any]:
    """The environment surface, with every secret shown as SET/UNSET only."""
    return {
        "APEX_ENV": cfg.apex_env,
        "APEX_ALLOW_SIGNED": bool(cfg.allow_signed),
        "APEX_ECONOMIC_GATE_SIGNED": bool(cfg.economic_gate_signed),
        "APEX_SQLITE_PATH": cfg.sqlite_path,
        "TOOBIT_API_KEY": "SET" if cfg.toobit_api_key else "UNSET",
        "TOOBIT_API_SECRET": "SET" if cfg.toobit_api_secret else "UNSET",
        "TELEGRAM_BOT_TOKEN": "SET" if cfg.telegram_bot_token else "UNSET",
        "TELEGRAM_OWNER_CHAT_ID": cfg.telegram_owner_chat_id or "UNSET",
        "TELEGRAM_WATCHDOG_CHAT_ID": cfg.telegram_watchdog_chat_id or "UNSET",
    }


def _credentials_present(cfg: Config) -> bool:
    return bool(cfg.allow_signed and cfg.toobit_api_key and cfg.toobit_api_secret)


async def _venue_server_time() -> Dict[str, Any]:
    """``GET /api/v1/time`` (unsigned; Ch.16 wire list L16881) — the reference
    for the AI.7 clock-drift measurement. This is NOT a sixth adapter
    operation: the adapter's surface stays exactly five operations."""
    import aiohttp

    from apex.execution.toobit_adapter import aiohttp_transport
    from apex.execution.toobit_map import BASE_URL
    async with aiohttp.ClientSession() as session:
        transport = aiohttp_transport(session)
        out = await transport("GET", f"{BASE_URL}/api/v1/time", "", {})
        return dict(out["body"])


async def _no_venue_time() -> Dict[str, Any]:
    raise RuntimeError("venue credentials absent (APEX_ALLOW_SIGNED / "
                       "TOOBIT_API_KEY / TOOBIT_API_SECRET) — drift is "
                       "UNMEASURABLE, never assumed zero")


class Runtime:
    """The CP-7 composition root: store + ONE ledger writer + bus, always
    closed (an aiosqlite thread left open would hang the interpreter)."""

    def __init__(self, cfg: Config, path: Optional[str] = None) -> None:
        self.cfg = cfg
        self.path = path or cfg.sqlite_path
        self.store: Optional[ss.SQLiteStore] = None
        self.ledger: Optional[LS.LedgerWriter] = None
        self.bus: Optional[EventBus] = None
        self.events: List[Any] = []
        self.migrations: Dict[str, Any] = {}

    async def start(self) -> "Runtime":
        self.store = ss.SQLiteStore(self.path)
        await self.store.open()
        self.ledger = LS.LedgerWriter(self.store)
        self.migrations = await self.ledger.initialize()
        await self.ledger.start()
        self.bus = EventBus()

        async def collector(event) -> None:
            self.events.append(event)

        for topic in ("execution.fsm.transition", "execution.boot",
                      "scheduler.cell", "telegram.message"):
            self.bus.subscribe(topic, collector)
        self.bus.start()
        return self

    async def stop(self) -> None:
        if self.bus is not None:
            await self.bus.stop()
        if self.ledger is not None and not self.ledger.closed:
            await self.ledger.stop()
        if self.store is not None:
            await self.store.close()

    def adapter(self) -> Optional[ToobitAdapter]:
        """The production adapter, or None when the venue cannot be reached
        (fail-closed: no credentials ⇒ no reconciliation ⇒ DEGRADED)."""
        if not _credentials_present(self.cfg):
            return None
        return ToobitAdapter(config=self.cfg)


# ---------------------------------------------------------------------------
# boot
# ---------------------------------------------------------------------------

async def _boot(cfg: Config, *, as_json: bool) -> int:
    _say("APEX_GEN5 — CP-7 boot (environment init → dependency load → "
         "reconcile-first → verdict)")
    _say(f"  environment surface: {json.dumps(_redacted(cfg), sort_keys=True)}")
    cfg.validate_environment()
    runtime = await Runtime(cfg).start()
    try:
        adapter = runtime.adapter()
        if adapter is None:
            _say("  venue credentials absent (or APEX_ALLOW_SIGNED=0) → the "
                 "boot cannot reconcile against the exchange and is DEGRADED "
                 "by rule (fail-closed, never assumed equal).")
        drift = await C.measure_drift(
            _venue_server_time if adapter is not None else _no_venue_time,
            C.SystemClock())
        _say(f"  clock drift: state={drift['state']} "
             f"drift_seconds={drift['drift_seconds']} "
             f"reason={drift.get('reason')}")
        machine = F.StartupReconciliation(
            ledger=runtime.ledger, adapter=adapter, bus=runtime.bus,
            clock=C.SystemClock().monotonic, utc_now=C.SystemClock().utc_now,
            environment=cfg.apex_env,
            drift_seconds=drift.get("drift_seconds"))
        verdict = await machine.run()
        for check in verdict["checks"]:
            _say(f"  [{check['status']:>11}] {check['name']}: {check['detail']}")
        _say(f"  boot_state={verdict['boot_state']} "
             f"new_trades_allowed={verdict['new_trades_allowed']} "
             f"drift_blocks_new_trades={verdict['drift_blocks_new_trades']}")
        _say(f"  migrations={runtime.migrations['migrations']} "
             f"ladder_state={runtime.migrations['ladder_state']}")
        if as_json:
            _say(json.dumps(verdict, default=str, indent=2, sort_keys=True))
        return {"READY": EXIT_READY, "DEGRADED": EXIT_DEGRADED}.get(
            verdict["boot_state"], EXIT_RECOVERY)
    finally:
        await runtime.stop()


# ---------------------------------------------------------------------------
# grid
# ---------------------------------------------------------------------------

async def _grid(cfg: Config, *, as_json: bool) -> int:
    clock = C.SystemClock()
    cells = C.universe_cells()
    _say(f"APEX_GEN5 — the trading universe: {len(cells)} cells "
         f"({len(CORE10_SYMBOLS)} Core-10 symbols × {len(TIMEFRAMES_14)} "
         "timeframes; 3d is not supported, monthly is 1mo)")
    drift = await C.measure_drift(
        _venue_server_time if _credentials_present(cfg) else _no_venue_time,
        clock)
    _say(f"  clock: state={drift['state']} drift_seconds={drift['drift_seconds']} "
         f"blocks_new_trades={drift['blocks_new_trades']}")
    scheduler = C.Scheduler(clock=clock, environment=cfg.apex_env)
    due = scheduler.due_cells()
    _say(f"  last closes (first 5 of {len(due)}):")
    for cell, close_ms in due[:5]:
        resolved = C.monotone_leverage(cell.timeframe, symbol=cell.symbol)
        _say(f"    {cell.cell_id:<14} close={_iso(close_ms)} "
             f"leverage<={resolved['leverage']} "
             f"(binding cap: {resolved['binding_cap']})")
    caps = {tf: C.monotone_leverage(tf, symbol="BTCUSDT")["leverage"]
            for tf in TIMEFRAMES_14}
    _say("  T_MONOTONE leverage ceilings (min over ALL caps, never "
         f"last-writer): {json.dumps(caps, sort_keys=True)}")
    _say(f"  HTF policy: {C.HTF_POLICY} · semaphore: {C.SCHEDULER_SEMAPHORE} · "
         f"stages: {' → '.join(C.PIPELINE_STAGES)}")
    if as_json:
        _say(json.dumps({"cells": [c.cell_id for c in cells],
                         "leverage_by_tf": caps, "drift": drift},
                        default=str, indent=2, sort_keys=True))
    return EXIT_READY


# ---------------------------------------------------------------------------
# demo — the whole PAPER loop on a fixture clock (test double, no network)
# ---------------------------------------------------------------------------

async def _demo(cfg: Config, *, as_json: bool) -> int:
    if cfg.apex_env == "LIVE":
        _say("REFUSED: the demo drives the FAKE Toobit responder (a test "
             "double). It never runs in LIVE.")
        return EXIT_DEGRADED
    if not cfg.allow_signed:
        code = "SIGNED_NOT_ALLOWED"
        _say(f"REFUSED: {code} — PAPER orders require APEX_ALLOW_SIGNED=1 "
             "(Y.1 L17093). Re-run exactly:")
        _say("  APEX_ENV=PAPER APEX_ALLOW_SIGNED=1 "
             "TOOBIT_API_KEY=DEMO TOOBIT_API_SECRET=DEMO "
             "python scripts/run_apex.py demo")
        return EXIT_DEGRADED
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from fake_toobit_responder import FakeToobitResponder   # test double only

    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="apex-demo-"))
    clock = C.FixtureClock("2026-01-01T00:00:00.000Z")
    runtime = await Runtime(cfg, str(tmp / "apex.sqlite3")).start()
    try:
        ledger, bus = runtime.ledger, runtime.bus
        responder = FakeToobitResponder(
            api_key=cfg.toobit_api_key or "DEMO_KEY",
            api_secret=cfg.toobit_api_secret or "DEMO_SECRET",
            server_time_ms=clock.now_ms(), balance="10000",
            clock=clock.monotonic)
        adapter = ToobitAdapter(config=cfg, transport=responder,
                                utc_now=clock.utc_now, clock=clock.monotonic)
        telegram = SG.SignalingPlane(clock=clock.monotonic,
                                     utc_now=clock.utc_now, ledger=ledger,
                                     bus=bus,
                                     owner_chat_id=cfg.telegram_owner_chat_id
                                     or None)
        _say("APEX_GEN5 — CP-7 PAPER demo loop (fixture clock + fake Toobit "
             "responder; NO network, NO capital)")
        boot = F.StartupReconciliation(ledger=ledger, adapter=adapter, bus=bus,
                                       clock=clock.monotonic,
                                       utc_now=clock.utc_now,
                                       environment="PAPER", drift_seconds=0.0)
        verdict = await boot.run()
        _say(f"  boot_state={verdict['boot_state']} "
             f"new_trades_allowed={verdict['new_trades_allowed']}")
        if not verdict["new_trades_allowed"]:
            return EXIT_DEGRADED

        cell = C.BundleCell("BTCUSDT", "1h")
        resolved = C.monotone_leverage(cell.timeframe, symbol=cell.symbol)
        _say(f"  cell={cell.cell_id} leverage<={resolved['leverage']} "
             f"caps={resolved['caps']}")

        await runtime.store.db.execute(
            "INSERT OR IGNORE INTO setup_candidate (setup_id, timestamp, "
            "symbol, timeframe, direction, quality, snapshot_id) VALUES "
            "('su-demo-0001','2026-01-01T00:00:00.000Z','BTCUSDT','1h',"
            "'BULLISH','Q2','sn-demo-0001')")
        await runtime.store.db.commit()
        plan = F.build_trade_plan(
            proposal={"proposal_id": "pr-demo-0001", "setup_id": "su-demo-0001",
                      "direction": "LONG", "stop": 99.0,
                      "targets": [103.0, 106.0], "entry_logic_ref": "E-01/BOS",
                      "snapshot_id": "sn-demo-0001"},
            adjudication={"decision": "ALLOW", "sized_quantity": 0.10,
                          "vetoes_applied": [], "sizing": {"R_allowed": 10.0},
                          "snapshot_id": "sn-demo-0001"},
            symbol=cell.symbol, timeframe=cell.timeframe, environment="PAPER",
            as_of=clock.utc_now(), capital=10000.0, contract_multiplier=1.0,
            risk_state="LowRisk", package_version="4.0.0",
            created_utc=clock.utc_now(),
            lineage="demo:scripts/run_apex.py")
        machine = F.ExecutionFSM(intent_id="i-demo-0001", ledger=ledger,
                                 adapter=adapter, bus=bus,
                                 clock=clock.monotonic, utc_now=clock.utc_now,
                                 environment="PAPER")
        submitted = await machine.submit(plan, price="100", quantity="0.10")
        _say(f"  submit → outcome={submitted['outcome']} state={machine.state}")
        await machine.record_fill(fill_id="f-demo-0001", price="100",
                                  quantity="0.10")
        await machine.advance("FULL_FILL")
        protection = await machine.place_protection(stop_price="99",
                                                    target_price="103")
        _say(f"  protection → protected={protection['protected']} "
             f"state={machine.state}")
        await machine.activate_management()
        await machine.record_fill(fill_id="x-demo-0001", price="103",
                                  quantity="0.10", side="SELL_CLOSE")
        closed = await machine.close_position(exit_price="103",
                                              quantity="0.10",
                                              exit_reason="TARGET_1",
                                              setup_id="su-demo-0001",
                                              pnl="0.30")
        reconciled = await machine.reconcile()
        chain = await ledger.verify_chain()
        rows = await ledger.read_ledger()
        _say(f"  close → state={closed['state']} · reconcile → "
             f"agree={reconciled['agree']} delta={reconciled['delta']} "
             f"state={machine.state}")
        _say(f"  ledger: {len(rows)} records · chain intact={chain['intact']} · "
             f"types={[r.event_type for r in rows]}")
        _say(f"  wire calls: {[(c.method, c.path) for c in responder.calls]}")
        _say(f"  signature violations: "
             f"{len(responder.signature_violations())}")
        try:
            signal = await telegram.send(SG.SignalMessage(
                signal_id="sig-demo-0001",
                chat_id=cfg.telegram_owner_chat_id or "-1",
                text="Setup CONFIRMED — BTCUSDT 1h LONG entry 100, stop 99, "
                     "target 103 (Q2, validity 5–20 candles)",
                timestamp_utc=clock.utc_now(), snapshot_id="sn-demo-0001"))
            _say(f"  telegram: sent={signal.sent} state={signal.state} "
                 f"quality={signal.quality} reason={signal.reason}")
        except SG.SignalingError as exc:
            # Fail-closed and REPORTED: without TELEGRAM_BOT_TOKEN no alert can
            # be delivered (E-TELE-001) — the loop still completed, and the
            # refusal is printed, never swallowed.
            _say(f"  telegram: REFUSED {exc.reason} — set TELEGRAM_BOT_TOKEN "
                 "(env only) to deliver; the trading loop above is unaffected")
        if as_json:
            _say(json.dumps({"boot_state": verdict["boot_state"],
                             "final_state": machine.state,
                             "reconcile": reconciled, "chain": chain,
                             "ledger_types": [r.event_type for r in rows]},
                            default=str, indent=2, sort_keys=True))
        return EXIT_READY if machine.state == "RECONCILED" else EXIT_RECOVERY
    finally:
        await runtime.stop()


# ---------------------------------------------------------------------------
# alerts — the Ch.23 alert-policy self-check
# ---------------------------------------------------------------------------

async def _alerts(cfg: Config, *, as_json: bool) -> int:
    _say("APEX_GEN5 — Ch.23 Monitoring and Alert Policy self-check")
    for row in SG.ALERT_POLICY:
        _say(f"  {row['alert']:<14} metric={row['metric']:<28} "
             f"threshold={row['threshold']:<26} channel={row['channel']:<22} "
             f"escalation={row['escalation']} priority=P{int(row['priority'])}")
    targets = {f"P{int(k)}": v
               for k, v in SG.DECLARED_DELIVERY_TARGETS_SECONDS.items()}
    _say(f"  dedup window={SG.ALERT_DEDUP_WINDOW_SECONDS}s except "
         f"{sorted(SG.ALERT_DEDUP_EXEMPT)} · log retention="
         f"{SG.LOG_RETENTION_DAYS}d · declared targets={targets} (UNVERIFIED)")
    if not cfg.telegram_bot_token:
        code = get_error_code("E-TELE-001")
        _say(f"  REFUSED: {code.code} — TELEGRAM_BOT_TOKEN is env-only and is "
             "not set; no alert can be delivered (fail-closed, never faked).")
        return EXIT_DEGRADED
    plane = SG.SignalingPlane(config=cfg)
    verdict = await plane.check_storage(used_fraction=0.0,
                                        snapshot_id="self-check")
    _say(f"  storage check: alert={verdict['alert']} "
         f"(threshold {SG.STORAGE_ALERT_FRACTION:.0%})")
    if as_json:
        _say(json.dumps({"policy": [dict(r) for r in SG.ALERT_POLICY],
                         "storage": verdict}, default=str, indent=2,
                        sort_keys=True))
    return EXIT_READY


# ---------------------------------------------------------------------------
# bootstrap — W.6 Phase 1, the first long run (resumable, owner-controlled)
# ---------------------------------------------------------------------------

def _parse_cells(text: Optional[str]) -> Optional[List[Tuple[str, str]]]:
    if not text:
        return None
    cells: List[Tuple[str, str]] = []
    for item in str(text).split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"--cells expects SYMBOL:TIMEFRAME, got {item!r}")
        symbol, timeframe = item.split(":", 1)
        symbol, timeframe = symbol.strip().upper(), timeframe.strip()
        if symbol not in CORE10_SYMBOLS:
            raise ValueError(f"E-VAL-021: {symbol} not in Core-10")
        if timeframe not in TIMEFRAMES_14:
            raise ValueError(f"E-VAL-022: {timeframe} not in the 14 timeframes")
        cells.append((symbol, timeframe))
    return cells or None


def _parse_start(text: Optional[str]) -> int:
    if not text:
        return BS.DEEP_START_MS
    moment = dt.datetime.strptime(text, "%Y-%m-%d").replace(
        tzinfo=dt.timezone.utc)
    return int(moment.timestamp() * 1000)


async def _notifier_for(cfg: Config) -> Any:
    """The owner channel, or None when there is no bot token (the refusal is
    then REPORTED by the service — never a silent drop)."""
    if not cfg.telegram_bot_token or not cfg.telegram_owner_chat_id:
        return None
    plane = SG.SignalingPlane(config=cfg)
    clock = C.SystemClock()
    return BS.SignalingNotifier(plane, chat_id=cfg.telegram_owner_chat_id,
                                utc_now=clock.utc_now)


def _cell_complete_has_evidence(text: str) -> bool:
    """True when a CELL_COMPLETE line carries drop/open evidence (CP-13)."""
    import re
    try:
        dropped = re.search(r"dropped=(\d+)", str(text or ""))
        opened = re.search(r"open_excluded=(\d+)", str(text or ""))
        return ((int(dropped.group(1)) > 0 if dropped else False)
                or (int(opened.group(1)) > 0 if opened else False))
    except (ValueError, TypeError):
        return False


def _print_cell_complete_evidence(notifications: List[Dict[str, Any]]) -> None:
    """Print EVERY CELL_COMPLETE line with evidence (CP-13, ISSUE-CP13-003).

    Without Telegram only the last three notifications reached the screen and
    the per-cell ``dropped=<n> offenders=...`` prints were lost (F5). Every
    evidence-carrying line is now printed in full, not just counted.
    """
    for note in list(notifications or []):
        if note.get("kind") != "CELL_COMPLETE":
            continue
        text = str(note.get("text") or "")
        if _cell_complete_has_evidence(text):
            _say(f"  cell: {text}")


async def _bootstrap(cfg: Config, *, as_json: bool, cells: Optional[str] = None,
                     start: Optional[str] = None,
                     max_pages: Optional[int] = None) -> int:
    _say("APEX_GEN5 — W.6 Phase 1: the FIRST LONG RUN (data acquisition)")
    _say(f"  environment surface: {json.dumps(_redacted(cfg), sort_keys=True)}")
    selected = _parse_cells(cells)
    start_ms = _parse_start(start)
    notifier = await _notifier_for(cfg)
    if notifier is None:
        _say("  owner channel: NOT WIRED (TELEGRAM_BOT_TOKEN/OWNER_CHAT_ID "
             "unset) — progress is printed here and recorded as a refusal")
    service = BS.BootstrapService(config=cfg, cells=selected, notifier=notifier,
                                  max_pages=max_pages)
    await service.open()
    try:
        try:
            result = await service.run(start_ms=start_ms)
        except BS.BootstrapError as exc:
            # A venue failure is ENVIRONMENTAL and the run is resumable (the
            # durable cursor is the resume point): the verdict is DEGRADED, not
            # an error, and nothing was skipped or invented.
            _say(f"  STOPPED (resumable): {exc.reason} — {exc.detail}")
            _say("  the durable cursor is kept; re-run the same command to "
                 "resume (Phase 1 never rewinds)")
            progress = await service.status()
            _say(f"  progress: completed={progress['cells_completed']} "
                 f"remaining={progress['cells_remaining']} bars="
                 f"{progress['bars_ingested']} pages={progress['pages_fetched']}")
            _print_cell_complete_evidence(service.notifications)
            _say(f"  invalid_bars_dropped={progress.get('invalid_bars_dropped', 0)} "
                 f"open_bars_excluded={progress.get('open_bars_excluded', 0)}")
            if as_json:
                _say(json.dumps(progress, default=str, indent=2, sort_keys=True))
            return EXIT_DEGRADED
        _say(f"  raw store: {result.get('raw_store')} · checkpoints: "
             f"{result.get('checkpoint_path')}")
        _say(f"  preflight={result['preflight']['action']} "
             f"({result['preflight']['reason']}) · pages={result.get('pages')} "
             f"backoffs={result.get('backoffs')} bars={result.get('bars_ingested')}")
        if result.get("status") == "BUDGET_REACHED":
            _say(f"  BUDGET REACHED — resumable: pages="
                 f"{result.get('pages_fetched')} remaining="
                 f"{result.get('cells_remaining')}; re-run with a larger "
                 f"--max-pages (the cursor is durable)")
        else:
            _say(f"  status={result['status']} completed="
                 f"{len(result.get('completed_cells') or ())} pending="
                 f"{len(result.get('pending_cells') or ())}")
        _say(f"  resume rule: {result.get('resume_rule', 'cursor is durable')}")
        _say(f"  oi policy: {result.get('oi_policy', 'oi_state=MISSING (never 0)')}")
        _print_cell_complete_evidence(service.notifications)
        _say(f"  invalid_bars_dropped={result.get('invalid_bars_dropped', 0)} "
             f"open_bars_excluded={result.get('open_bars_excluded', 0)}")
        for note in service.notifications[-3:]:
            _say(f"  notify[{note['kind']}]: delivered={note['delivered']} "
                 f"{note.get('reason', '')}")
        if as_json:
            _say(json.dumps({k: v for k, v in result.items()},
                            default=str, indent=2, sort_keys=True))
        status = result.get("status")
        if status == "COMPLETE":
            return EXIT_READY
        if status in ("PAUSED", "BUDGET_REACHED", "STOPPED"):
            return EXIT_DEGRADED          # not complete — and resumable
        return EXIT_RECOVERY
    finally:
        await service.close()


# ---------------------------------------------------------------------------
# status — offline progress (the durable checkpoints are the truth)
# ---------------------------------------------------------------------------

async def _status(cfg: Config, *, as_json: bool) -> int:
    service = BS.BootstrapService(config=cfg)
    await service.open()
    try:
        status = await service.status()
        _say("APEX_GEN5 — bootstrap status (offline; no venue call)")
        _say(f"  cells={status['cells_total']} completed="
             f"{status['cells_completed']} remaining={status['cells_remaining']} "
             f"checkpointed={status['checkpointed_cells']}")
        _say(f"  current_cell={status['current_cell']} bars="
             f"{status['bars_ingested']} pages={status['pages_fetched']} "
             f"backoffs={status['backoffs']}")
        _say(f"  invalid_bars_dropped={status.get('invalid_bars_dropped', 0)} "
             f"open_bars_excluded={status.get('open_bars_excluded', 0)}")
        _say(f"  state={status['state']} eta="
             f"{status['eta'].get('eta_seconds')} "
             f"({status['eta'].get('basis', 'measured')})")
        artifact_path = EC.PARAMS_DIR / "e11_classifier_v1.yaml"
        try:
            EC.load_classifier(artifact_path)
            artifact_name = "E11_ARTIFACT"
        except EC.BridgeError as exc:
            artifact_name = exc.reason
        _say(f"  artifact={artifact_name}")
        status["artifact"] = artifact_name
        if as_json:
            _say(json.dumps(status, default=str, indent=2, sort_keys=True))
        return EXIT_READY if status["cells_remaining"] == 0 else EXIT_DEGRADED
    finally:
        await service.close()


# ---------------------------------------------------------------------------
# repair-partial — CP-13 governed repair of partial bars (dry-run by default)
# ---------------------------------------------------------------------------

async def _repair_partial(cfg: Config, *, as_json: bool,
                          evidence: Optional[List[str]] = None,
                          apply: bool = False,
                          cells: Optional[str] = None) -> int:
    _say("APEX_GEN5 — CP-13 repair-partial: governed repair of partial bars")
    _say(f"  environment surface: {json.dumps(_redacted(cfg), sort_keys=True)}")
    selected = _parse_cells(cells)
    evidence_paths: List[str] = []
    for item in list(evidence or []):
        if isinstance(item, (list, tuple)):
            evidence_paths.extend(str(p) for p in item)
        elif item:
            evidence_paths.append(str(item))
    if evidence_paths:
        _say(f"  evidence: {', '.join(evidence_paths)}")
    else:
        _say("  evidence: none (LIVE venue only)")
    _say(f"  mode: {'APPLY (corrections will be written)' if apply else 'DRY-RUN (writes nothing)'}")
    store = ss.SQLiteStore(cfg.sqlite_path)
    await store.open()
    try:
        import aiohttp
        from apex.data_catalog.ingest.toobit_public import ToobitPublicClient
        async with aiohttp.ClientSession() as session:
            client = ToobitPublicClient(session=session)
            try:
                report = await PR.run_repair(
                    store, client=client, evidence_paths=evidence_paths,
                    apply=apply, cells=selected)
            except FileNotFoundError as exc:
                _say(f"  REFUSED: {exc}")
                return EXIT_ERROR
            except ValueError as exc:
                _say(f"  REFUSED: {exc}")
                return EXIT_ERROR
        for row in report["candidates"]:
            line = (f"  {row['symbol']} {row['timeframe']} "
                    f"open={row['open_time']} created={row['created_at']} "
                    f"verdict={row['verdict']} ")
            if row["verdict"] == PR.VERDICT_SKIPPED_STILL_OPEN:
                line += f"closes_at={row.get('closes_at') or '-'} "
            _say(line
                 + f"store_close={row['store_close']} "
                 + f"store_vol={row['store_volume']} "
                 + f"repl_close={row.get('repl_close') or '-'} "
                 + f"repl_vol={row.get('repl_volume') or '-'} "
                 + f"source={row.get('replacement') or '-'}")
        counts = report["counts"]
        _say(f"  summary: candidates={counts['candidates']} "
             f"verified={counts['verified']} corrected={counts['corrected']} "
             f"unrepairable={counts['unrepairable']} refused={counts['refused']} "
             f"skipped_still_open={counts.get('skipped_still_open', 0)}")
        data_dir = REPO_ROOT / "data"
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            leaf = PR.report_filename()
            with open(str(data_dir / leaf), "w", encoding="utf-8") as handle:
                json.dump({"captured_at": dt.datetime.now(dt.timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.000Z"), "apply": bool(apply),
                    "evidence": evidence_paths,
                    "cells": ([f"{s}:{t}" for s, t in selected]
                              if selected else None),
                    **report}, handle, indent=2, sort_keys=True, default=str)
            _say(f"  report: data/{leaf}")
        except OSError as exc:
            _say(f"  report: UNWRITABLE ({exc}) — counts above still stand")
        if as_json:
            _say(json.dumps(report, default=str, indent=2, sort_keys=True))
        # Exit 0 when nothing is left unrepaired (spec wording "nothing is
        # left unrepairable" read strictly: both UNREPAIRABLE and REFUSED
        # leave the row partial and untouched, so both need owner attention).
        if counts["unrepairable"] == 0 and counts["refused"] == 0:
            return EXIT_READY
        return EXIT_DEGRADED
    finally:
        await store.close()


# ---------------------------------------------------------------------------
# serve — the 24/7 runtime (long loop)
# ---------------------------------------------------------------------------

async def _serve(cfg: Config, *, as_json: bool, cycles: Optional[int] = None,
                 interval: float = 60.0, report_every: int = 1) -> int:
    if cfg.apex_env == "LIVE" and not cfg.economic_gate_signed:
        code = "LIVE_CAPITAL_LOCKED"
        _say(f"REFUSED: {code} — APEX_ENV=LIVE is not a capital switch; LIVE "
             "capital stays locked until APEX_ECONOMIC_GATE_SIGNED=1 (Y.1 "
             "L17093) and the owner's written approval. Run PAPER first.")
        return EXIT_DEGRADED
    if not cfg.allow_signed:
        _say("REFUSED: SIGNED_NOT_ALLOWED — PAPER orders require "
             "APEX_ALLOW_SIGNED=1 (Y.1 L17093). Re-run exactly:")
        _say("  APEX_ENV=PAPER APEX_ALLOW_SIGNED=1 TOOBIT_API_KEY=... "
             "TOOBIT_API_SECRET=... TELEGRAM_BOT_TOKEN=... "
             "TELEGRAM_OWNER_CHAT_ID=... python scripts/run_apex.py serve")
        return EXIT_DEGRADED

    runtime = await Runtime(cfg).start()
    service = BS.BootstrapService(config=cfg, store=runtime.store)  # one raw writer
    await service.open()
    gateway = None
    try:
        ledger, bus = runtime.ledger, runtime.bus
        clock = C.SystemClock()
        adapter = runtime.adapter()
        notifier = await _notifier_for(cfg)
        signaling = (SG.SignalingPlane(config=cfg, ledger=ledger, bus=bus,
                                       owner_chat_id=cfg.telegram_owner_chat_id
                                       or None)
                     if cfg.telegram_bot_token else None)
        control = CP.ControlPlane(
            signaling=signaling, config=cfg, clock=clock.monotonic,
            utc_now=clock.utc_now, bus=bus, environment=cfg.apex_env,
            paper_balance=(await EC.paper_balance(ledger)
                           if cfg.apex_env == "PAPER" else "0"))
        control.register("BOOTSTRAP_CONTROL", _bootstrap_handler(service))
        for name in ("EMERGENCY_PAUSE", "EMERGENCY_DISABLE_NEW",
                     "EMERGENCY_CANCEL_ALL", "EMERGENCY_CLOSE_ALL",
                     "EMERGENCY_SAFE_MODE", "EXPORT", "BACKTEST_RUN"):
            control.register(name, _noop_handler(name))
        if cfg.telegram_bot_token:
            gateway = GW.TelegramGateway(
                control=control, source=GW.AiogramUpdateSource(config=cfg),
                notifier=_telegram_reply(signaling),
                bootstrap=service, clock=clock.monotonic,
                utc_now=clock.utc_now, poll_timeout=5.0)
        watchdog = WD.Watchdog(telegram_plane=signaling,
                               recovery_log=WD.RecoveryLog(path=cfg.sqlite_path),
                               now=time.time)
        # CP-9 bridge: the provider is registered at the composition root, so
        # every PAPER cell now asks the governed store/context → pattern/setup
        # → gates → forecast → risk/decision chain for a real plan.  Missing
        # persisted engine context remains a named fail-closed refusal; the
        # provider never falls back to a hand-built plan.
        producer = (EC.EngineContextProducer(runtime.store, ledger=ledger,
                    environment="PAPER") if cfg.apex_env == "PAPER" else None)
        plan_bridge = PB.PaperPlanBridge(
            store=runtime.store, environment=cfg.apex_env,
            context_source=producer.get_bridge_context if producer is not None else None,
            context_preparer=producer.prepare if producer is not None else None)
        async def catch_up(now_ms: int) -> Dict[str, Any]:
            result = await service.catch_up(now_ms)
            if cfg.apex_env == "PAPER":
                control.paper_balance = CP.comma_format(await EC.paper_balance(ledger))
            return result

        driver = PL.PaperRuntime(
            config=cfg, store=runtime.store, ledger=ledger, bus=bus,
            adapter=adapter, signaling=signaling, control=control,
            gateway=gateway, watchdog=watchdog, clock=clock,
            environment=cfg.apex_env, notifier=notifier,
            plan_provider=plan_bridge, catch_up=catch_up)
        _say("APEX_GEN5 — 24/7 runtime (reconcile-first boot → the 140-cell "
             "scheduler → the SL-5 → SL-6 trade_plan queue → execution FSM)")
        drift = await C.measure_drift(
            _venue_server_time if adapter is not None else _no_venue_time, clock)
        boot = await driver.boot(drift_seconds=drift.get("drift_seconds"))
        try:
            EC.load_classifier()
            artifact_name = "E11_ARTIFACT"
        except EC.BridgeError as exc:
            artifact_name = exc.reason
        _say(f"  boot_state={boot['boot_state']} "
             f"new_trades_allowed={boot['new_trades_allowed']} "
             f"drift={drift['state']} ({drift.get('reason') or 'measured'}) "
             f"artifact={artifact_name}")
        if driver.plan_provider is None:
            _say("  plan seam: NO PLANS WIRED — every cell halts with the named "
                 "refusal NO_PLAN_PROVIDER")
        else:
            _say("  plan seam: WIRED — governed PAPER store bridge "
                 "(missing context refuses by name; no synthetic plan)")
        _say(f"  signal_source={driver.signal_source} · cells=140 · "
             f"max_trades_per_cycle={driver.max_trades_per_cycle} · "
             f"telegram={'WIRED' if gateway is not None else 'DISABLED (no token)'}")
        _say("  (Ctrl-C stops the loop; the ledger chain and the durable "
             "cursors stay consistent)")
        outcome = await driver.run(cycles=cycles, interval=interval)
        for cycle in driver.cycles[-3:]:
            _say(f"  cycle {cycle['cycle']}: cells={cycle['cells_due']} "
                 f"complete={cycle['cells_complete']} "
                 f"halted={cycle['cells_halted']} blocked={cycle['cells_blocked']} "
                 f"trades={len(cycle['trades'])} open={len(cycle['open_intents'])}")
            if cycle.get("halt_reasons"):
                _say(f"    named refusals: "
                     f"{json.dumps(cycle['halt_reasons'], sort_keys=True)}")
        _say(f"  cycles={outcome['cycles']} trades={outcome['trades']} "
             f"open={outcome['open_intents']} refusals={outcome['refusals']} "
             f"ledger_chain_intact={outcome['ledger_chain_intact']}")
        if as_json:
            _say(json.dumps({"boot": boot, "outcome": outcome,
                             "cycles": driver.cycles}, default=str, indent=2,
                            sort_keys=True))
        return EXIT_READY if boot["boot_state"] == "READY" else EXIT_DEGRADED
    finally:
        if gateway is not None:
            await gateway.aclose()
        await service.close()
        await runtime.stop()


def _bootstrap_handler(service: "BS.BootstrapService"):
    """Routes the W.8-2 owner words to the bootstrap service."""

    async def handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        verdict = await service.command(str(payload.get("command", "")),
                                       caller=str(payload.get("chat_id", "")))
        return {"ok": bool(verdict.get("accepted", verdict.get("command"))),
                "result": verdict}

    return handler


def _noop_handler(name: str):
    """Records the control-plane effect and reports it honestly (the effect
    itself belongs to the recovery path, which runs outside this loop)."""

    async def handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "effect": name, "recorded": True,
                "detail": "control-plane effect recorded by the runtime; the "
                          "protective path is the FSM/AI.9 recovery"}

    return handler


def _telegram_reply(signaling: Any):
    async def notifier(chat_id: str, text: str) -> Dict[str, Any]:
        if signaling is None:
            raise SG.SignalingError("E-TELE-001",
                                    "TELEGRAM_BOT_TOKEN is unset (env-only)")
        clock = C.SystemClock()
        moment = clock.utc_now()
        result = await signaling.send(SG.SignalMessage(
            signal_id=f"reply-{moment}-{abs(hash(text)) % 10**6}",
            chat_id=str(chat_id), priority=Priority.P1, text=text,
            timestamp_utc=moment, snapshot_id="gateway",
            alert="CONTROL_REPLY", metric="telegram_inbound",
            threshold="Ch.21 §5", observed=text[:60],
            lineage="apex.telegram.gateway"))
        return {"sent": bool(getattr(result, "sent", False)),
                "reason": getattr(result, "reason", None)}

    return notifier


async def _fit_study_e11(cfg: Config, *, as_json: bool,
                         seed: int = EC.DEFAULT_TRAINING_SEED,
                         timeframes: str = "1h,4h",
                         symbols: str = ",".join(CORE10_SYMBOLS),
                         max_bars_per_cell: Optional[int] = None,
                         cache_dir: Optional[str] = None) -> int:
    """CP-14.3 RESEARCH-ONLY fit study: cache-only, no artifact, no params/.

    Loads the D35 per-cell cache for the same protocol hash (``--timeframes``,
    ``--symbols``, ``--max-bars-per-cell``), refuses with
    FIT_STUDY_REQUIRES_CACHE when any scoped cell is not a cache hit, and
    never recomputes a feature, writes a classifier artifact or touches
    params/. The report is gitignored data/e11_fit_study_<UTC stamp>.json.
    """
    try:
        loaded = EC.load_fit_study_cache(timeframes=timeframes, symbols=symbols,
                                         max_bars_per_cell=max_bars_per_cell,
                                         cache_dir=cache_dir)
    except PB.BridgeError as exc:
        result = {"status": "REFUSED", "reason": exc.reason, "detail": exc.detail,
                  "artifact_written": False}
        _say(json.dumps(result, sort_keys=True) if as_json else
             f"REFUSED {exc.reason}: {exc.detail}")
        return EXIT_DEGRADED
    for cell in loaded["cells"]:
        print(f"FIT_CACHE cell={cell['cell']} cache=hit samples={cell['samples']} "
              f"closed_bars={cell['closed_bars']} "
              f"input_hash={(cell['input_hash'] or '-')[:12]}", file=sys.stderr, flush=True)
    study = EC.run_fit_study(loaded["X"], loaded["labels"], seed=seed)
    for record in study["variants"]:
        shares = ",".join(f"{name}:{record['per_class'][name]['share_pmax_ge_0_50']:.4f}"
                          for name in EC.FIT_STUDY_PER_CLASS_ROW)
        # C7 required stderr: variant iters weights acc log_loss share_pmax min_class_share_pmax theta_for_20pct seconds
        print(f"FIT_STUDY variant={record['variant']} iters={record['iterations']} "
              f"lr={record['learning_rate']} l2={record['l2']} "
              f"weights={record['weights']} standardised={record['standardised']} "
              f"train_accuracy={record['train_accuracy']:.6f} "
              f"train_log_loss={record['train_log_loss']:.6f} "
              f"share_H_ge_theta={record['share_H_ge_theta']:.6f} "
              f"share_H_ge_0_80={record['share_H_ge_0_80']:.6f} "
              f"share_pmax_ge_0_50={record['share_pmax_ge_0_50']:.6f} "
              f"min_class_share_pmax_ge_0_50={record['min_class_share_pmax_ge_0_50']:.6f} "
              f"theta_for_20pct={record['theta_for_20pct']:.6f} "
              f"share_h_norm_gt_0_85={record['share_h_norm_gt_0_85']:.6f} "
              f"H_p10={record['H_percentiles']['p10']:.6f} "
              f"H_p50={record['H_percentiles']['p50']:.6f} "
              f"H_p90={record['H_percentiles']['p90']:.6f} "
              f"pmax_median={record['pmax_median']:.6f} "
              f"seconds={record['seconds']:.3f} per_class_pmax_ge_0_50={shares}",
              file=sys.stderr, flush=True)
    # C7: FIT_STUDY_THETA for every variant, P0 legacy line still present
    for record in study["variants"]:
        print(f"FIT_STUDY_THETA variant={record['variant']} "
              f"theta_for_10pct={record['theta_for_10pct']:.6f} "
              f"theta_for_20pct={record['theta_for_20pct']:.6f} "
              f"theta_for_30pct={record['theta_for_30pct']:.6f}",
              file=sys.stderr, flush=True)
    p0 = study["variants"][0]
    # Legacy P0 line kept for compatibility
    print(f"FIT_STUDY_THETA variant=P0 theta_for_10pct={p0['theta_for_10pct']:.6f} "
          f"theta_for_20pct={p0['theta_for_20pct']:.6f} "
          f"theta_for_30pct={p0['theta_for_30pct']:.6f}", file=sys.stderr, flush=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPO_ROOT / "data" / f"e11_fit_study_{stamp}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**study, "status": "FIT_STUDY", "generated_utc": stamp,
               "protocol_hash": loaded["protocol_hash"],
               "cache_dir": loaded["cache_dir"], "cells": loaded["cells"],
               "artifact_written": False}
    report_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print(f"FIT_STUDY_REPORT {report_path}", file=sys.stderr, flush=True)
    result = {"status": "FIT_STUDY", "samples": loaded["samples"],
              "cells": len(loaded["cells"]), "protocol_hash": loaded["protocol_hash"],
              "variants": [record["variant"] for record in study["variants"]],
              "theta_for_10pct": p0["theta_for_10pct"],
              "theta_for_20pct": p0["theta_for_20pct"],
              "theta_for_30pct": p0["theta_for_30pct"],
              "report_path": str(report_path), "artifact_written": False}
    _say(json.dumps(result, sort_keys=True) if as_json else
         f"FIT_STUDY {loaded['samples']} cached samples; report={report_path}; "
         f"no artifact written")
    return EXIT_READY


async def _train_e11(cfg: Config, *, as_json: bool, sqlite: Optional[str] = None,
                     out: Optional[str] = None,
                     seed: int = EC.DEFAULT_TRAINING_SEED,
                     timeframes: str = "1h,4h", symbols: str = ",".join(CORE10_SYMBOLS),
                     max_minutes: float = EC.DEFAULT_TRAINING_MAX_MINUTES,
                     max_bars_per_cell: Optional[int] = None,
                     profile: bool = False) -> int:
    """Store-only first training; a refusal never replaces an artifact."""
    target = Path(out) if out is not None else EC.PARAMS_DIR / "e11_classifier_v1.yaml"
    def progress(row):
        if row["kind"] == "tick":
            print(f"TRAIN_PROGRESS cell={row['cell']} bars_done={row['bars_done']} "
                  f"bars_total={row['bars_total']} elapsed_seconds={row['elapsed_seconds']:.3f}",
                  file=sys.stderr, flush=True)
            return
        print(f"TRAIN_CELL cell={row['cell']} closed_bars={row['closed_bars']} "
              f"eligible_samples={row['eligible_samples']} elapsed_seconds={row['elapsed_seconds']:.3f}",
              file=sys.stderr, flush=True)
        if profile and "profile" in row:
            engines = ",".join(f"{name}:{row['profile']['engines'].get(name, 0.0):.3f}"
                               for name in EC.PROFILE_ENGINE_ORDER)
            excluded = ",".join(f"{reason}:{row['excluded'][reason]}"
                                for reason in sorted(row["excluded"])) or "-"
            print(f"TRAIN_PROFILE cell={row['cell']} cache={row.get('cache', 'miss')} "
                  f"elapsed_seconds={row['elapsed_seconds']:.3f} engines={engines} "
                  f"stages=window_read:{row['profile']['window_read_seconds']:.3f},"
                  f"label_confirmation:{row['profile']['label_confirmation_seconds']:.3f} "
                  f"excluded={excluded}", file=sys.stderr, flush=True)
    try:
        artifact, report = await EC.train_classifier_bounded(sqlite or cfg.sqlite_path, seed=seed,
            timeframes=timeframes, symbols=symbols, max_minutes=max_minutes,
            max_bars_per_cell=max_bars_per_cell, profile=profile, progress=progress)
    except EC.DegenerateTraining as exc:
        result = {"status": "REFUSED", "reason": exc.reason,
                  "refusing_class": exc.refusing_class,
                  "sample_count": sum(exc.histogram.values()),
                  "per_class_counts": exc.histogram,
                  "training_window": exc.training_window,
                  "excluded": exc.excluded, "artifact_written": False}
        _say(json.dumps(result, sort_keys=True) if as_json else
             f"REFUSED {exc.reason}: {exc.detail}; histogram={exc.histogram}")
        return EXIT_DEGRADED
    except EC.TrainingTimeout as exc:
        result = {"status": "REFUSED", "reason": exc.reason, "artifact_written": False,
                  "cells_completed": exc.cells_completed,
                  "cells_remaining": exc.cells_remaining, "next_cell": exc.next_cell}
        _say(json.dumps(result, sort_keys=True) if as_json else
             f"REFUSED {exc.reason}: {exc.detail}; completed={exc.cells_completed}")
        return EXIT_DEGRADED
    except PB.BridgeError as exc:
        result = {"status": "REFUSED", "reason": exc.reason, "artifact_written": False}
        _say(json.dumps(result, sort_keys=True) if as_json else f"REFUSED {exc.reason}: {exc.detail}")
        return EXIT_DEGRADED
    EC.write_classifier(artifact, target)
    if profile:
        print(f"TRAIN_PROFILE_FIT fit_seconds={report['fit_seconds']:.3f} "
              f"samples={artifact['sample_count']}", file=sys.stderr, flush=True)
    # D36: mandatory post-fit entropy/confidence validation. The full report
    # is written to gitignored data/ and its path printed; a WARN verdict is
    # reported to the owner and never blocks — the exit code stays 0 TRAINED.
    validation = report["validation"]
    # CP-14.5 C1: D49 triple recommendation (theta_H=H p80, quality_H_Q2=H p90,
    # quality_H_Q5=H p30), printed in full on both the stderr and the text line.
    theta_rec = validation["theta_recommendation"]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPO_ROOT / "data" / f"e11_train_report_{stamp}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(validation, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    # C6: TRAIN_VALIDATION stderr adds verdict_rule train_accuracy min_class_share_pmax theta_H
    # CP-14.5 C1: and the full D49 triple theta_rec_H/theta_rec_Q2/theta_rec_Q5
    print(f"TRAIN_VALIDATION verdict={validation['verdict']} "
          f"verdict_rule={validation.get('verdict_rule','D47')} "
          f"train_accuracy={validation['train_accuracy']:.6f} "
          f"share_pmax_ge_0_50={validation['share_pmax_ge_0_50']:.6f} "
          f"min_class_share_pmax_ge_0_50={validation['min_class_share_pmax_ge_0_50']:.6f} "
          f"theta_H={validation['theta_H']:.6f} "
          f"theta_rec_H={theta_rec['theta_H']:.6f} "
          f"theta_rec_Q2={theta_rec['quality_H_Q2']:.6f} "
          f"theta_rec_Q5={theta_rec['quality_H_Q5']:.6f} "
          f"share_H_ge_theta={validation['share_H_ge_theta']:.6f} "
          f"samples={validation['samples']}", file=sys.stderr, flush=True)
    print(f"TRAIN_REPORT {report_path}", file=sys.stderr, flush=True)
    # C6: TRAINED includes fit_protocol
    result = {"status": "TRAINED", "sample_count": artifact["sample_count"],
              "training_window": artifact["training_window"],
              "artifact_sha256": artifact["artifact_sha256"],
              "artifact_path": str(target), "seed": seed,
              "fit_protocol": artifact.get("fit_protocol", report.get("fit_protocol")),
              **report}
    _say(json.dumps(result, sort_keys=True) if as_json else
         f"TRAINED {artifact['sample_count']} samples; artifact={target}; "
         f"validation verdict={validation['verdict']} verdict_rule={validation.get('verdict_rule','D47')} "
         f"train_accuracy={validation['train_accuracy']:.6f} "
         f"share_pmax_ge_0_50={validation['share_pmax_ge_0_50']:.6f} "
         f"min_class_share_pmax_ge_0_50={validation['min_class_share_pmax_ge_0_50']:.6f} "
         f"theta_H={validation['theta_H']:.6f} "
         f"theta_rec_H={theta_rec['theta_H']:.6f} "
         f"theta_rec_Q2={theta_rec['quality_H_Q2']:.6f} "
         f"theta_rec_Q5={theta_rec['quality_H_Q5']:.6f} "
         f"fit_protocol={artifact.get('fit_protocol')}")
    return EXIT_READY



async def _publish_quality_backfill(cfg: Config, *, as_json: bool,
                                    symbol: Optional[str] = None,
                                    timeframe: Optional[str] = None) -> int:
    """D52 B. Refused unless APEX_ENV=PAPER."""
    if cfg.apex_env != "PAPER":
        payload = {"status": "REFUSED", "reason": "BACKFILL_PAPER_ONLY",
                   "environment": cfg.apex_env}
        _say(f"REFUSED: BACKFILL_PAPER_ONLY (APEX_ENV={cfg.apex_env})")
        if as_json:
            _say(json.dumps(payload, sort_keys=True))
        return EXIT_DEGRADED
    store = ss.SQLiteStore(cfg.sqlite_path)
    await store.open()
    try:
        report = await EC.publish_quality_backfill(
            store, environment="PAPER", symbol=symbol, timeframe=timeframe)
    finally:
        await store.close()
    _say(json.dumps(report, default=str, sort_keys=True))
    return EXIT_READY


COMMANDS = {"boot": _boot, "grid": _grid, "demo": _demo, "alerts": _alerts,
            "bootstrap": _bootstrap, "status": _status, "serve": _serve,
            "repair-partial": _repair_partial, "train-e11": _train_e11,
            "publish-quality-backfill": _publish_quality_backfill}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_apex.py", description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", default="boot",
                        choices=sorted(COMMANDS),
                        help="boot (default) | grid | demo | alerts | "
                             "bootstrap | status | serve | repair-partial | "
                             "publish-quality-backfill")
    parser.add_argument("--json", action="store_true",
                        help="also print the machine-readable verdict")
    parser.add_argument("--env-file", default=None,
                        help="optional .env path (never overrides real env)")
    parser.add_argument("--cells", default=None,
                        help="bootstrap/repair-partial: comma-separated "
                             "SYMBOL:TIMEFRAME subset (default: all 140 cells)")
    parser.add_argument("--start", default=None,
                        help="bootstrap: first bar date YYYY-MM-DD "
                             "(default 2020-01-01, the W.6 deep scope)")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="bootstrap: page budget — stops CLEANLY and "
                             "resumably (the durable cursor is kept)")
    parser.add_argument("--cycles", type=int, default=None,
                        help="serve: run this many cycles then exit "
                             "(default: until interrupted)")
    parser.add_argument("--interval", type=float, default=60.0,
                        help="serve: seconds between cycles (default 60)")
    parser.add_argument("--evidence", action="append", default=None,
                        help="repair-partial: owner evidence JSON file "
                             "(repeatable; F6a/F6b shapes)")
    parser.add_argument("--apply", action="store_true",
                        help="repair-partial: perform corrections "
                             "(default is dry-run, writes nothing)")
    parser.add_argument("--sqlite", default=None,
                        help="train-e11: harvested SQLite store (default APEX_SQLITE_PATH)")
    parser.add_argument("--out", default=None,
                        help="train-e11: output artifact (default params/e11_classifier_v1.yaml)")
    parser.add_argument("--seed", type=int, default=EC.DEFAULT_TRAINING_SEED,
                        help="train-e11: fixed recorded optimizer seed")
    parser.add_argument("--timeframes", default="1h,4h", help="train-e11: base TF subset (default 1h,4h)")
    parser.add_argument("--symbols", default=",".join(CORE10_SYMBOLS), help="train-e11: Core-10 subset (default all ten)")
    parser.add_argument("--max-minutes", type=float, default=EC.DEFAULT_TRAINING_MAX_MINUTES,
                        help="train-e11: hard training time limit (default 20 minutes)")
    parser.add_argument("--max-bars-per-cell", type=int, default=None,
                        help="train-e11: latest N CLOSED bars per cell (default unlimited)")
    parser.add_argument("--profile", action="store_true",
                        help="train-e11: per-cell engine/stage timing lines on stderr")
    parser.add_argument("--fit-study", action="store_true",
                        help="train-e11: RESEARCH-ONLY fit-protocol study over the D35 "
                             "cache (no artifact, no params/, never recomputes features)")
    parser.add_argument("--symbol", default=None,
                        help="publish-quality-backfill: optional single symbol")
    parser.add_argument("--timeframe", default=None,
                        help="publish-quality-backfill: optional single timeframe")
    args = parser.parse_args(argv)
    cfg = Config(args.env_file)          # APEX_DOTENV_PATH/.env fill, no shadow
    try:
        if args.command == "train-e11" and args.fit_study:
            return asyncio.run(_fit_study_e11(cfg, as_json=args.json, seed=args.seed,
                                             timeframes=args.timeframes, symbols=args.symbols,
                                             max_bars_per_cell=args.max_bars_per_cell))
        if args.command == "train-e11":
            return asyncio.run(_train_e11(cfg, as_json=args.json,
                                         sqlite=args.sqlite, out=args.out, seed=args.seed,
                                         timeframes=args.timeframes, symbols=args.symbols, max_minutes=args.max_minutes,
                                         max_bars_per_cell=args.max_bars_per_cell, profile=args.profile))
        if args.command == "bootstrap":
            return asyncio.run(_bootstrap(cfg, as_json=args.json,
                                          cells=args.cells, start=args.start,
                                          max_pages=args.max_pages))
        if args.command == "serve":
            return asyncio.run(_serve(cfg, as_json=args.json,
                                      cycles=args.cycles,
                                      interval=args.interval))
        if args.command == "publish-quality-backfill":
            return asyncio.run(_publish_quality_backfill(
                cfg, as_json=args.json, symbol=args.symbol,
                timeframe=args.timeframe))
        if args.command == "repair-partial":
            return asyncio.run(_repair_partial(
                cfg, as_json=args.json, evidence=args.evidence,
                apply=args.apply, cells=args.cells))
        return asyncio.run(COMMANDS[args.command](cfg, as_json=args.json))
    except KeyboardInterrupt:
        _say("interrupted — fail-closed, nothing left running")
        return EXIT_ERROR
    except AdapterError as exc:
        _say(f"REFUSED {exc.reason}: {exc.detail}")
        return EXIT_DEGRADED
    except Exception as exc:                      # fail-closed, never silent
        _say(f"ERROR {type(exc).__name__}: {exc}")
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
