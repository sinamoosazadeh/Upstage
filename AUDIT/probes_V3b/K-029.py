"""K-029 probe — snapshot identity is not bound to the data and is not
deterministic across processes.

READ-ONLY. Real `apex.quality.pit.calc_snapshot_pit_window` and real
MarketObservations from the frozen parser. Writes only this probe's .out file.

1. Same window, different OHLCV (close/volume corrected) -> same snapshot_id?
2. Same bytes, four subprocesses with PYTHONHASHSEED=1..4 -> how many IDs?
3. parameter_package_id / symbol_scope handling.
"""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = pathlib.Path(__file__).with_suffix(".out")
_buf = []


def say(line=""):
    _buf.append(str(line))
    OUT.write_text("\n".join(_buf) + "\n")


HOUR = 3_600_000
T0 = 1_672_531_200_000


def bars(symbols=("BTCUSDT",), n=2, close="100.5", volume="10"):
    from apex.data_catalog.ingest.toobit_public import parse_kline_to_observation
    out = []
    for sym in symbols:
        for i in range(n):
            open_ms = T0 + i * HOUR
            out.append(parse_kline_to_observation(
                sym, "1h",
                [open_ms, "100", "101", "99", close, volume,
                 open_ms + HOUR - 1], 0))
    return out


def snapshot_for(obs):
    from apex.quality.pit import calc_snapshot_pit_window
    snap, state, cls = calc_snapshot_pit_window(obs, ["1h"], minimum_bars=2)
    return snap, state


def child_mode():
    """Print one snapshot_id for a fixed multi-symbol input (hash-seed test)."""
    obs = bars(symbols=("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"), n=2)
    snap, _ = snapshot_for(obs)
    sys.stdout.write("%s manifest=%s\n" % (snap["snapshot_id"],
                                            snap["manifest_hash"]))


def main():
    say("# K-029 — snapshot identity binding and determinism")
    say()
    say("1. identical window, corrected OHLCV")
    a, _ = snapshot_for(bars(close="100.5", volume="10"))
    b, _ = snapshot_for(bars(close="999.9", volume="4242"))
    say("   close=100.5 volume=10     -> snapshot_id=%s" % a["snapshot_id"])
    say("   close=999.9 volume=4242   -> snapshot_id=%s" % b["snapshot_id"])
    say("   identical                 = %r" % (a["snapshot_id"] == b["snapshot_id"],))
    say("   manifest_hash identical   = %r"
        % (a["manifest_hash"] == b["manifest_hash"],))

    say()
    say("2. same bytes, four subprocesses with different PYTHONHASHSEED")
    ids = []
    for seed in ("1", "2", "3", "4"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=str(ROOT))
        res = subprocess.run([sys.executable, "-B", __file__, "--child"],
                             capture_output=True, text=True, env=env,
                             cwd=str(ROOT))
        line = res.stdout.strip() or res.stderr.strip()[-200:]
        ids.append(line.split(" ")[0])
        say("   PYTHONHASHSEED=%s -> %s" % (seed, line))
    say("   distinct snapshot_ids for identical input = %d" % len(set(ids)))

    say()
    say("3. other identity fields")
    say("   parameter_package_id = %r" % a["parameter_package_id"])
    say("   code_version         = %r" % a["code_version"])
    say("   apex/quality/pit.py:117 hard-codes 'params_v1_frozen' "
        "(comment: 'package id placeholder replaced by CP-6 governance')")
    say("   symbol_scope is list(set(...))[:10] — over-scope is silently "
        "truncated although the module docstring says 'symbol_scope > 10 -> BLOCK'")


if __name__ == "__main__":
    if "--child" in sys.argv:
        child_mode()
    else:
        main()
        sys.stdout.write(OUT.read_text())
