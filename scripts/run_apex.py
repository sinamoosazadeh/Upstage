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
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apex.bus import EventBus                                 # noqa: E402
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
from apex.telegram import signaling as SG                     # noqa: E402

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


COMMANDS = {"boot": _boot, "grid": _grid, "demo": _demo, "alerts": _alerts}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_apex.py", description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", default="boot",
                        choices=sorted(COMMANDS),
                        help="boot (default) | grid | demo | alerts")
    parser.add_argument("--json", action="store_true",
                        help="also print the machine-readable verdict")
    parser.add_argument("--env-file", default=None,
                        help="optional .env path (never overrides real env)")
    args = parser.parse_args(argv)
    cfg = Config(args.env_file)          # APEX_DOTENV_PATH/.env fill, no shadow
    try:
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
