"""K-022 probe — partial-bar repair cannot tell a transient venue failure from
an exhausted retention window.

READ-ONLY. Uses the real SQLiteStore, the real partial_bar_repair module
(find_candidates / fetch_live_bar / repair_one) and the real ToobitPublicError.
Writes only this probe's .out file.

A real partial bar is written to a TEMP store (a CLOSED row whose created_at is
earlier than its close time), detected by the real `find_candidates`, and then
offered to the real `repair_one` with four different clients:
  1. HTTP 429 rate limit (transient)          -> ToobitPublicError
  2. network timeout (transient)              -> asyncio.TimeoutError
  3. HTTP 500 (transient/server)              -> ToobitPublicError
  4. healthy venue, empty window (retention)  -> returns []
"""
import asyncio
import os
import pathlib
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = pathlib.Path(__file__).with_suffix(".out")
_buf = []


def say(line=""):
    _buf.append(str(line))
    OUT.write_text("\n".join(_buf) + "\n")


class RaisingClient:
    def __init__(self, exc):
        self.exc = exc
        self.calls = 0

    async def get_klines(self, *a, **k):
        self.calls += 1
        raise self.exc


class EmptyWindowClient:
    def __init__(self):
        self.calls = 0

    async def get_klines(self, *a, **k):
        self.calls += 1
        return []


async def main(tmp):
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.data_catalog.ingest.toobit_public import (
        ToobitPublicError, parse_kline_to_observation)
    from apex.ops import partial_bar_repair as PR

    store = await SQLiteStore(os.path.join(tmp, "market.sqlite3")).open()
    # A 1h bar that is still open right now -> the row is written BEFORE its
    # close, which is exactly the CP-13 partial-bar shape find_candidates looks
    # for (created_at < close + 5 s skew).
    now_ms = int(time.time() * 1000)
    open_ms = now_ms - (now_ms % 3600_000)   # the hour that is open right now
    obs = parse_kline_to_observation(
        "BTCUSDT", "1h", [open_ms, "100", "102", "99", "101", "10", 0], 0)
    await store.ingest_raw(obs, "MISSING")

    candidates = await PR.find_candidates(store, cells=[("BTCUSDT", "1h")])
    say("# K-022 — repair verdicts do not distinguish the cause")
    say()
    say("candidates found by the real find_candidates = %d" % len(candidates))
    cand = candidates[0]
    say("  cell=%s:%s open=%s created=%s close_ms=%d"
        % (cand["symbol"], cand["timeframe"], cand["as_of"],
           cand["created_at"], cand["close_ms"]))
    say()

    cases = [
        ("HTTP 429 rate limit (transient)",
         RaisingClient(ToobitPublicError("klines", "HTTP 429 rate limit"))),
        ("network timeout (transient)",
         RaisingClient(asyncio.TimeoutError("read timeout"))),
        ("HTTP 500 server error (transient)",
         RaisingClient(ToobitPublicError("klines", "HTTP 500 server error"))),
        ("healthy venue, window truly empty (retention)",
         EmptyWindowClient()),
    ]
    for label, client in cases:
        live = await PR.fetch_live_bar(
            client, cand["symbol"], cand["timeframe"],
            cand["open_ms"], cand["close_ms"])
        row = await PR.repair_one(store, cand, client=client, evidence={},
                                  apply=False)
        say("%-46s fetch_live_bar=%r calls=%d" % (label, live, client.calls))
        say("%-46s verdict=%r detail=%r"
            % ("", row["verdict"], row.get("detail")))

    say()
    say("end-to-end run_repair with an injected now_ms past the close "
        "(so the bar is no longer 'still open'), venue returning HTTP 429:")
    client = RaisingClient(ToobitPublicError("klines", "HTTP 429 rate limit"))
    report = await PR.run_repair(store, client=client, apply=False,
                                 cells=[("BTCUSDT", "1h")],
                                 now_ms=cand["close_ms"] + 60_000)
    say("   counts  = %r" % (report["counts"],))
    say("   verdict = %r" % (report["candidates"][0]["verdict"],))

    say()
    say("CLI mapping: scripts/run_apex.py:683-686 — "
        "unrepairable>0 or refused>0 -> EXIT_DEGRADED, with no cause field")
    await store.close()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        asyncio.run(main(tmp))
    sys.stdout.write(OUT.read_text())
