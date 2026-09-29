"""K-020 probe — the harvest completion gate: an empty venue completes, and a
rejected (SKIPPED) cell is counted as completed.

READ-ONLY. Uses the real BootstrapService / BootstrapRunner / ResearchCheckpointStore
and the repository's own fake Toobit responder. Writes only this probe's .out file.

A. Real BootstrapService over a venue that retains NO bars: does the cell reach COMPLETE
   with zero ingested bars and an empty pending list?
B. Real BootstrapRunner with a phase1_verifier that refuses every cell: are the cells
   SKIPPED while `pending_cells()`, `progress_async()` and the run status still report
   everything as done (which is what `scripts/run_apex.py` maps to exit READY)?
C. Does production ever construct a verifier?
"""
import asyncio
import importlib.util
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


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


async def scenario_a(tmp):
    helper = load("t_engine_context", "tests/unit/test_engine_context.py")
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.ops import bootstrap_service as BS

    start = 1767225600000
    rows = {("BTCUSDT", "1h"): []}          # venue retains nothing at all
    client = helper._StoredKlineResponder(rows)
    bridge = BS.AsyncBridge().start()
    store = await SQLiteStore(os.path.join(tmp, "a.sqlite3")).open()
    source = BS.ToobitKlineSource(client=client, bridge=bridge)
    service = BS.BootstrapService(
        store=store, source=source,
        checkpoint_path=os.path.join(tmp, "a-progress.sqlite3"),
        cells=list(rows))
    await service.open()
    say("A. empty venue (zero retained bars), real BootstrapService")
    say("   runner phase1_verifier = %r" % service.runner.phase1_verifier)
    result = await service.run(start_ms=start, end_ms=start + 24 * 3600_000,
                               announce=False)
    say("   status          = %r" % result["status"])
    say("   completed_cells = %r" % result.get("completed_cells"))
    say("   skipped_cells   = %r" % result.get("skipped_cells"))
    say("   pending_cells   = %r" % result.get("pending_cells"))
    say("   bars_ingested   = %r" % result.get("bars_ingested"))
    st = await service.status()
    say("   status(): completed=%r remaining=%r bars=%r"
        % (st["cells_completed"], st["cells_remaining"], st["bars_ingested"]))
    say("   -> scripts/run_apex.py:565-566 maps status COMPLETE to EXIT_READY")
    say("   -> scripts/run_apex.py:604 maps cells_remaining==0 to EXIT_READY")
    rows_db = await (await store.db.execute(
        "SELECT COUNT(*) FROM raw_observation")).fetchone()
    say("   durable raw_observation rows = %r" % (rows_db[0],))
    await service.close()
    await store.close()
    bridge.close()


async def scenario_b(tmp):
    from apex.research import bootstrap as bs
    from apex.research.checkpoints import ResearchCheckpointStore

    def fetcher(symbol, timeframe, cursor, end, limit):
        return {"rows": [], "next_cursor_ms": end, "code": None}

    async def ingest(rows, symbol, timeframe):
        return len(rows)

    def refusing_verifier(payload):
        return {"verified": False, "reason": "COVERAGE_INSUFFICIENT"}

    runner = bs.BootstrapRunner(
        fetcher=fetcher, ingest=ingest,
        store=ResearchCheckpointStore(path=os.path.join(tmp, "b.sqlite3")),
        cells=[("BTCUSDT", "15m"), ("ETHUSDT", "15m")],
        phase1_verifier=refusing_verifier)
    say()
    say("B. real runner, verifier refuses EVERY cell")
    async with runner.store as store:
        result = await runner.run_phase1(start_ms=1_000_000,
                                         end_ms=1_000_000 + 900_000)
        progress = await runner.progress_async()
        pending = await runner.pending_cells()
        statuses = [(r["cell_id"], r["status"]) for r in await store.bootstrap_rows()]
    say("   durable statuses = %r" % statuses)
    say("   result status    = %r" % result["status"])
    say("   completed_cells  = %r" % result["completed_cells"])
    say("   skipped_cells    = %r" % result["skipped_cells"])
    say("   pending_cells    = %r" % result["pending_cells"])
    say("   pending_cells()  = %r" % pending)
    say("   progress_async   = completed=%r remaining=%r"
        % (progress["cells_completed"], progress["cells_remaining"]))


def scenario_c():
    import subprocess
    say()
    say("C. production construction of a verifier")
    out = subprocess.run(["grep", "-rn", "phase1_verifier", "--include=*.py", "."],
                         cwd=str(ROOT), capture_output=True, text=True).stdout
    for line in out.strip().splitlines():
        say("   " + line)


if __name__ == "__main__":
    say("# K-020 — harvest completion gate")
    say()
    with tempfile.TemporaryDirectory() as tmp:
        asyncio.run(scenario_a(tmp))
        asyncio.run(scenario_b(tmp))
    scenario_c()
    sys.stdout.write(OUT.read_text())
