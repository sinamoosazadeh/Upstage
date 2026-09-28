"""Offline, partial C-002 evidence. Does NOT run CLI main/serve or place orders.
Run: PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-002.py
Config's environment loader is deliberately bypassed: no real secrets or .env.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.clear()
os.environ.update({"MPLCONFIGDIR": str(ROOT / "AUDIT/probes_V1a/.mpl"),
                   "PYTHONDONTWRITEBYTECODE": "1"})
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
blocked = []


def guard(event, args):
    if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo", "socket.sendto"}:
        blocked.append(event)
        raise RuntimeError("NETWORK_FORBIDDEN_BY_PROBE")
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if path.name == ".env" or path.name.startswith(".env.") or path.is_relative_to(ROOT / "data"):
            blocked.append("forbidden-file")
            raise RuntimeError("SECRET_OR_DEVICE_DATA_FORBIDDEN_BY_PROBE")


sys.addaudithook(guard)
import asyncio
import json
import numpy
from apex.config import Config
from apex.execution import fsm as F
from apex.ledger import store as LS
from apex.ops.paper_loop import PaperRuntime, CellRefusal
from scripts.run_apex import Runtime


def config(credentials):
    cfg = object.__new__(Config)
    cfg._env = {"APEX_ENV": "PAPER", "APEX_ALLOW_SIGNED": "1", "APEX_SQLITE_PATH": ":memory:"}
    if credentials:
        cfg._env.update(TOOBIT_API_KEY="synthetic-not-a-secret", TOOBIT_API_SECRET="synthetic-not-a-secret")
    return cfg


async def main():
    print("numpy=" + numpy.__version__)
    for credentials in (False, True):
        cfg = config(credentials)
        runtime = await Runtime(cfg).start()
        try:
            adapter = runtime.adapter()
            print(json.dumps({"synthetic_credentials": credentials, "adapter": type(adapter).__name__}))
            if adapter is not None:
                result = await adapter.query_open_positions(timestamp_utc="2026-09-28T00:00:00.000Z", nonce="verification")
                print(json.dumps({"query_outcome": result.outcome, "error": result.error_code,
                                  "attempts": len(result.attempts), "ok": result.ok}))
                assert result.outcome == "UNKNOWN" and result.error_code == "TRANSPORT_SESSION_MISSING"
            for drift in (None, 0.0):
                driver = PaperRuntime(config=cfg, store=runtime.store, ledger=runtime.ledger,
                                      adapter=adapter, environment="PAPER")
                boot = await driver.boot(drift_seconds=drift)
                print(json.dumps({"credentials": credentials, "injected_drift": drift,
                                  "boot_state": boot["boot_state"], "ready": boot["ready"],
                                  "reconciliation": boot["reconciliation"], "checks": boot["checks"]}, sort_keys=True))
                assert not boot["ready"]
                # Exercise the real execution gate only; sentinel plan is never submitted.
                payload = {"context": {"cell_state": {"plan_obj": object()}}}
                try:
                    await driver._stage_execution(payload)
                except CellRefusal as exc:
                    print("execution_gate=" + str(exc))
                    assert exc.reason == "BOOT_NOT_READY"
                else:
                    raise AssertionError("execution gate unexpectedly passed")
            # Actual repository DDL, empty synthetic database: planner evidence only.
            sql = "SELECT " + ",".join(LS.LEDGER_COLUMNS) + " FROM ledger ORDER BY rowid"
            for indexed in (False, True):
                if indexed:
                    await runtime.store.db.execute("CREATE INDEX idx_mo_sym_tf_open ON market_observation(symbol,timeframe,open_time)")
                    await runtime.store.db.execute("CREATE INDEX idx_pit_scope_asof ON snapshot_pit(source_state,symbol_scope,timeframe_scope,as_of)")
                cur = await runtime.store.db.execute("EXPLAIN QUERY PLAN " + sql)
                print(json.dumps({"device_indexes": indexed, "query": sql, "plan": await cur.fetchall()}))
        finally:
            await runtime.stop()
    print("guard_blocked_attempts=" + json.dumps(blocked))
    assert not blocked
    print("PASS: limited offline assertions only; not device/serve acceptance")


if __name__ == "__main__":
    asyncio.run(main())
