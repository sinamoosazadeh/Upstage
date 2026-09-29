"""K-024 probe — partial-bar detection keys on created_at (commit time), so a
pre-close snapshot committed after the close is invisible to the repair path.

READ-ONLY. Uses the real SQLiteStore, the repository's own seeding helper
(tests/unit/test_ops_partial_bar_repair.py::seed — the same two INSERTs
`ingest_raw` performs, with a chosen created_at) and the real
partial_bar_repair.find_candidates. Writes only this probe's .out file.

Rows seeded (all 1h, all stored with candle_status CLOSED):
  1. open T0            created = close - 60 s   -> written before the close
  2. open T0 + 1h       created = close + 600 s  -> SAME pre-close snapshot,
                                                    committed 10 min later
  3. open T0 + 2h       created = close + 600 s  -> a genuinely closed bar
Rows 2 and 3 are byte-indistinguishable in the store.
"""
import asyncio
import importlib.util
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
OUT = pathlib.Path(__file__).with_suffix(".out")
_buf = []


def say(line=""):
    _buf.append(str(line))
    OUT.write_text("\n".join(_buf) + "\n")


def load_helpers():
    spec = importlib.util.spec_from_file_location(
        "t_repair", ROOT / "tests" / "unit" / "test_ops_partial_bar_repair.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


async def main(tmp):
    h = load_helpers()
    from apex.ops import bootstrap_service as BS
    from apex.ops import partial_bar_repair as PR

    HOUR = h.HOUR
    T0 = h.T0
    store = await h.open_store(pathlib.Path(tmp) / "apex.sqlite3")
    plan = [
        (T0, T0 + HOUR - 60_000, "written 60 s BEFORE its close (partial)"),
        (T0 + HOUR, T0 + 2 * HOUR + 600_000,
         "pre-close snapshot, COMMITTED 10 min after the close (partial)"),
        (T0 + 2 * HOUR, T0 + 3 * HOUR + 600_000,
         "genuinely closed bar, committed 10 min after the close"),
    ]
    say("# K-024 — candidate detection uses commit time, not capture time")
    say()
    say("SKEW_MARGIN_SECONDS = %r" % PR.SKEW_MARGIN_SECONDS)
    for open_ms, created_ms, label in plan:
        await h.seed(store, open_ms, created_iso=BS._ms_to_iso(created_ms))
        say("  seeded open=%s created=%s  (%s)"
            % (BS._ms_to_iso(open_ms), BS._ms_to_iso(created_ms), label))

    cur = await store.db.execute(
        "SELECT as_of, created_at, availability_time FROM raw_observation "
        "ORDER BY as_of")
    rows = [tuple(r) for r in await cur.fetchall()]
    await cur.close()
    say()
    say("stored rows (as_of | created_at | availability_time):")
    for r in rows:
        say("   %s | %s | %s" % r)
    say("   note: availability_time is DERIVED (= close time, "
        "apex/data_catalog/ingest/toobit_public.py:169), not a measured receipt")

    candidates = await PR.find_candidates(store, cells=[("BTCUSDT", "1h")])
    say()
    say("find_candidates -> %d candidate(s)" % len(candidates))
    for c in candidates:
        say("   open=%s created=%s" % (c["as_of"], c["created_at"]))
    say()
    say("rows 2 and 3 are indistinguishable in the store: same columns, "
       "same created_at relationship to close; only row 1 is repairable.")
    await store.close()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        asyncio.run(main(tmp))
    sys.stdout.write(OUT.read_text())
