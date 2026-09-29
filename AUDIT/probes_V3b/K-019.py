"""K-019 probe — catch_up quality-fact publish failure is recorded but never retried.

READ-ONLY. Imports the real repository code (BootstrapService, SQLiteStore, the
repository's own fake Toobit responder through tests/unit/test_engine_context.py's
_StoredKlineResponder helper). Writes only this probe's .out file.

Scenario
  1. PAPER env, one cell BTCUSDT:1h, one closed bar. `publish_catch_up_quality` is
     replaced (module attribute, exactly like tests/unit/test_engine_context.py:150-185)
     by a function that raises BridgeError -> catch_up ingests the bar and records the
     failure in report["quality_publish"]["failures"].
  2. Report the run-level failure list, `successful` (through the boundary map) and the
     durable state: raw_observation count and whether a QUALITY_<observation_id> fact
     exists for the ingested bar.
  3. Restore the real publisher, add the NEXT bar, run catch_up again at the next
     boundary. Show whether the first bar's missing fact is retried.
"""
import asyncio
import importlib.util
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = pathlib.Path(__file__).with_suffix(".out")
_buf = []


def say(line=""):
    _buf.append(str(line))
    OUT.write_text("\n".join(_buf) + "\n")


def load_helper():
    spec = importlib.util.spec_from_file_location(
        "t_engine_context", ROOT / "tests" / "unit" / "test_engine_context.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


async def fact_for(store, ec, symbol, tf, open_ms, as_of):
    row = await (await store.db.execute(
        "SELECT observation_id FROM market_observation WHERE symbol=? AND timeframe=? "
        "AND open_time=?", (symbol, tf, ec._ms_to_iso(open_ms)))).fetchone()
    if row is None:
        return None, None
    fact = await ec.read_context_fact(store, "QUALITY_" + row[0], symbol, tf, as_of)
    return row[0], fact


async def main(tmp):
    helper = load_helper()
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.ops import bootstrap_service as BS
    from apex.ops import engine_context as EC
    from apex.ops.plan_bridge import BridgeError

    start = 1767225600000           # 2026-01-01T00:00:00Z, 1h open
    hour = 3600_000
    rows = {("BTCUSDT", "1h"): [helper._row(start)]}
    client = helper._StoredKlineResponder(rows)
    bridge = BS.AsyncBridge().start()
    store = await SQLiteStore(os.path.join(tmp, "market.sqlite3")).open()
    source = BS.ToobitKlineSource(client=client, bridge=bridge)
    service = BS.BootstrapService(
        store=store, source=source,
        checkpoint_path=os.path.join(tmp, "progress.sqlite3"),
        cells=list(rows))
    service.config = type("Cfg", (), {"apex_env": "PAPER"})()
    await service.open()

    real_publish = EC.publish_catch_up_quality

    async def boom(*a, **k):
        raise BridgeError("QUALITY_PUBLISH_REFUSED", "BTCUSDT")

    say("# K-019 — quality publish failure in catch_up")
    say()
    say("1. first catch_up, publisher raises BridgeError")
    EC.publish_catch_up_quality = boom
    try:
        report = await service.catch_up(start + hour)
    finally:
        EC.publish_catch_up_quality = real_publish
    say("   bars_ingested      = %r" % report["bars_ingested"])
    say("   cells_updated      = %r" % report["cells_updated"])
    say("   failures (cell)    = %r" % report["failures"])
    say("   quality_publish    = %r" % report["quality_publish"])
    say("   catch_up boundary  = %r" % dict(service._catch_up_boundary))
    import time as _t0
    obs_id, fact = await fact_for(store, EC, "BTCUSDT", "1h", start,
                                  EC._ms_to_iso(int(_t0.time() * 1000) + 60_000))
    say("   durable bar        = %r" % obs_id)
    say("   durable QUALITY fact for that bar = %r" % fact)

    say()
    say("2. next boundary, publisher healthy again, one NEW bar appears")
    rows[("BTCUSDT", "1h")].append(helper._row(start + hour))
    report2 = await service.catch_up(start + 2 * hour)
    say("   bars_ingested      = %r" % report2["bars_ingested"])
    say("   failures (cell)    = %r" % report2["failures"])
    say("   quality_publish    = %r" % report2["quality_publish"])
    say("   catch_up boundary  = %r" % dict(service._catch_up_boundary))
    import time as _t
    # facts are stamped with the real receipt wall-clock, so read them as-of now
    as_of = EC._ms_to_iso(int(_t.time() * 1000) + 60_000)
    for open_ms, label in ((start, "bar 1 (failed publish)"),
                           (start + hour, "bar 2 (healthy publish)")):
        obs_id, fact = await fact_for(store, EC, "BTCUSDT", "1h", open_ms, as_of)
        say("   %-24s %s -> fact %s" % (
            label, obs_id, "PRESENT" if fact else "MISSING"))

    say()
    say("3. consumer view: engine_context.quality_window refuses on a missing fact")
    say("   apex/ops/engine_context.py:2046-2048 ->"
        " raise BridgeError('QUALITY_PROVENANCE_UNAVAILABLE', identity)")

    await service.close()
    await store.close()
    bridge.close()


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        asyncio.run(main(tmp))
    sys.stdout.write(OUT.read_text())
