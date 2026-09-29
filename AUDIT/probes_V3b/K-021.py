"""K-021 probe — the canonical mirror swallows every failure, and last_error is sticky.

READ-ONLY. Uses the real CanonicalMirroredCheckpoints, the real ResearchCheckpointStore
and the real SQLiteStore (temporary files only). Writes only this probe's .out file.

A. Mirror failure: the canonical `bootstrap_progress` table is made unusable in a TEMP
   copy of the real store DDL (DROP TABLE on the temp file), then a COMPLETE checkpoint
   is saved through the real wrapper. Does the caller see an error? What does each of the
   two progress tables hold afterwards? What does BootstrapService.status() report?
B. Sticky last_error: with an intact canonical table, save SKIPPED (mirrored as
   ERROR + PHASE1_VERIFICATION_SKIPPED) and then COMPLETE (mirrored as DONE).
   Does `last_error=COALESCE(excluded.last_error, old)` keep the stale error?
   Does `bars_written = old + excluded` accumulate across saves?
"""
import asyncio
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = pathlib.Path(__file__).with_suffix(".out")
_buf = []


def say(line=""):
    _buf.append(str(line))
    OUT.write_text("\n".join(_buf) + "\n")


async def canonical_rows(store):
    cur = await store.db.execute(
        "SELECT symbol, timeframe, phase, cursor_open_time, status, "
        "bars_written, last_error FROM bootstrap_progress")
    rows = [tuple(r) for r in await cur.fetchall()]
    await cur.close()
    return rows


async def main(tmp):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.research.checkpoints import ResearchCheckpointStore
    from apex.ops import bootstrap_service as BS

    say("# K-021 — checkpoint mirror coordination")
    say()
    say("A. canonical mirror cannot write (table dropped in a TEMP db)")
    store = await SQLiteStore(os.path.join(tmp, "a-market.sqlite3")).open()
    await store.db.execute("DROP TABLE bootstrap_progress")
    await store.db.commit()
    cps = await ResearchCheckpointStore(path=os.path.join(tmp, "a-prog.sqlite3")).open()
    wrapper = BS.CanonicalMirroredCheckpoints(cps, store)
    err = None
    try:
        await wrapper.save_bootstrap(
            cell_id="BTCUSDT:1d", symbol="BTCUSDT", timeframe="1d", phase=1,
            status="COMPLETE", cursor_ms=1726444800000, bars_ingested=7)
    except Exception as exc:                      # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"
    say("   caller saw exception   = %r" % err)
    row = await cps.load_bootstrap("BTCUSDT:1d")
    say("   research row           = status=%r cursor_ms=%r bars=%r"
        % (row["status"], row["cursor_ms"], row["bars_ingested"]))
    try:
        rows = await canonical_rows(store)
    except Exception as exc:                      # noqa: BLE001
        rows = f"{type(exc).__name__}: {exc}"
    say("   canonical rows         = %r" % (rows,))
    svc = BS.BootstrapService(store=store,
                              checkpoint_path=os.path.join(tmp, "a-prog.sqlite3"),
                              cells=[("BTCUSDT", "1d")])
    await svc.open()
    st = await svc.status()
    say("   service.status()       = completed=%r remaining=%r (reads the research table)"
        % (st["cells_completed"], st["cells_remaining"]))
    await svc.close()
    await cps.close()
    await store.close()

    say()
    say("B. intact canonical table: SKIPPED then COMPLETE")
    store2 = await SQLiteStore(os.path.join(tmp, "b-market.sqlite3")).open()
    cps2 = await ResearchCheckpointStore(path=os.path.join(tmp, "b-prog.sqlite3")).open()
    wrapper2 = BS.CanonicalMirroredCheckpoints(cps2, store2)
    await wrapper2.save_bootstrap(
        cell_id="BTCUSDT:1d", symbol="BTCUSDT", timeframe="1d", phase=1,
        status="SKIPPED", cursor_ms=1726444800000, bars_ingested=5)
    say("   after SKIPPED  canonical = %r" % (await canonical_rows(store2),))
    await wrapper2.save_bootstrap(
        cell_id="BTCUSDT:1d", symbol="BTCUSDT", timeframe="1d", phase=1,
        status="COMPLETE", cursor_ms=1726531200000, bars_ingested=9)
    say("   after COMPLETE canonical = %r" % (await canonical_rows(store2),))
    row2 = await cps2.load_bootstrap("BTCUSDT:1d")
    say("   research row             = status=%r cursor_ms=%r bars=%r"
        % (row2["status"], row2["cursor_ms"], row2["bars_ingested"]))
    await cps2.close()
    await store2.close()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        asyncio.run(main(tmp))
    sys.stdout.write(OUT.read_text())
