"""K-023 probe — repair report durability: same-second overwrite and an
unwritable report that still exits READY.

READ-ONLY with respect to the repository: the CLI's REPO_ROOT and
APEX_SQLITE_PATH are redirected to a temp directory exactly as the repository's
own CLI tests do (tests/unit/test_ops_partial_bar_repair.py:475-481), so the
repo's data/ is never touched. Writes only this probe's .out file.

A. `PR.report_filename()` for two moments inside the same second.
B. Two consecutive real `run_apex._repair_partial` dry runs: how many report
   files exist in <tmp>/data afterwards?
C. The report directory is made read-only after a successful analysis: what is
   printed and what exit code does the CLI return?
"""
import asyncio
import datetime as dt
import importlib.util
import io
import os
import pathlib
import stat
import sys
import tempfile
from contextlib import redirect_stdout

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
    import run_apex
    from apex.config import Config
    from apex.ops import partial_bar_repair as PR

    say("# K-023 — repair report durability")
    say()
    say("A. report_filename() resolution")
    m1 = dt.datetime(2026, 9, 16, 12, 0, 0, 100_000, tzinfo=dt.timezone.utc)
    m2 = dt.datetime(2026, 9, 16, 12, 0, 0, 900_000, tzinfo=dt.timezone.utc)
    say("   %s -> %s" % (m1.isoformat(), PR.report_filename(m1)))
    say("   %s -> %s" % (m2.isoformat(), PR.report_filename(m2)))
    say("   identical = %r" % (PR.report_filename(m1) == PR.report_filename(m2),))

    # ---- real CLI, redirected at tmp (never the repo's data/) -------------
    db = pathlib.Path(tmp) / "apex.sqlite3"
    store = await h.open_store(db)
    try:
        await h.seed(store, h.T0, created_iso=h.BS._ms_to_iso(h.T0 + 1_000))
    finally:
        await store.close()
    evidence = h.write_evidence_f6a(
        pathlib.Path(tmp) / "store_vs_venue.json", "BTCUSDT", "1h", h.T0,
        h.STORE_OHLCV, h.wire(h.T0))

    async def no_live(*a, **k):
        return None
    real_fetch = PR.fetch_live_bar
    PR.fetch_live_bar = no_live
    real_root = run_apex.REPO_ROOT
    run_apex.REPO_ROOT = pathlib.Path(tmp)
    os.environ["APEX_SQLITE_PATH"] = str(db)
    data_dir = pathlib.Path(tmp) / "data"

    try:
        say()
        say("B. two consecutive dry runs of the real CLI")
        codes = []
        for i in (1, 2):
            sink = io.StringIO()
            with redirect_stdout(sink):
                codes.append(await run_apex._repair_partial(
                    Config(), as_json=False, evidence=[evidence], apply=False,
                    cells=None))
            line = [l for l in sink.getvalue().splitlines()
                    if "summary:" in l or "report:" in l]
            say("   run %d exit=%r  %s" % (i, codes[-1], " | ".join(
                s.strip() for s in line)))
        reports = sorted(p.name for p in data_dir.glob(
            "repair_partial_report_*.json"))
        say("   report files after two runs = %d %r" % (len(reports), reports))

        say()
        say("C. report directory read-only, analysis still succeeds")
        for existing in data_dir.glob("repair_partial_report_*.json"):
            existing.unlink()          # force a fresh create in a read-only dir
        os.chmod(data_dir, stat.S_IRUSR | stat.S_IXUSR)
        sink = io.StringIO()
        with redirect_stdout(sink):
            code = await run_apex._repair_partial(
                Config(), as_json=False, evidence=[evidence], apply=False,
                cells=None)
        for line in sink.getvalue().splitlines():
            if "summary:" in line or "report:" in line or "verdict=" in line:
                say("   " + line.strip())
        say("   exit code = %r  (EXIT_READY=%r)" % (code, run_apex.EXIT_READY))
        os.chmod(data_dir, stat.S_IRWXU)
    finally:
        PR.fetch_live_bar = real_fetch
        run_apex.REPO_ROOT = real_root
        os.environ.pop("APEX_SQLITE_PATH", None)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        asyncio.run(main(tmp))
    sys.stdout.write(OUT.read_text())
