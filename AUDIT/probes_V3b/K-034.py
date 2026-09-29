"""K-034 probe — the bridge's own PIT window check (`PaperPlanBridge._window`)
only compares `timestamp`/`as_of` against `as_of`: it ignores the `ts` alias it
itself copies, ignores the bar's close time for the timeframe, ignores raw
availability (which `_normalise_bars` drops), and accepts a bar with no time
and no status at all.

READ-ONLY. Imports the real `apex.ops.plan_bridge` module objects and the real
`apex.data_catalog.contracts.MarketObservation`. Writes only this probe's .out.
"""
import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = pathlib.Path(__file__).with_suffix(".out")
_buf = []


def say(line=""):
    _buf.append(str(line))
    OUT.write_text("\n".join(_buf) + "\n")


OHLC = {"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.5, "v": 10.0}


def main():
    from apex.ops import plan_bridge as pb

    AS_OF = "2024-01-01T01:30:00.000Z"           # 1h cell, mid-candle
    say("# K-034 — PaperPlanBridge._window PIT check on a 1h window")
    say("as_of = %s   (the 01:00 candle closes at 02:00)" % AS_OF)
    say()

    bridge = pb.PaperPlanBridge.__new__(pb.PaperPlanBridge)   # no store needed: bars given

    cases = [
        ("bar open=01:00, CLOSED, closes 02:00 (AFTER as_of) — "
         "'timestamp' is the OPEN time",
         {**OHLC, "timestamp": "2024-01-01T01:00:00.000Z", "status": "CLOSED"}),
        ("same bar, plus availability_time=04:00 (published 2.5h after as_of)",
         {**OHLC, "timestamp": "2024-01-01T01:00:00.000Z", "status": "CLOSED",
          "availability_time": "2024-01-01T04:00:00.000Z"}),
        ("future bar carried on the 'ts' alias (02:00 > as_of)",
         {**OHLC, "ts": "2024-01-01T02:00:00.000Z", "status": "CLOSED"}),
        ("bar with NO time and NO status at all",
         dict(OHLC)),
        ("future bar on 'timestamp' (02:00 > as_of) — the one check that fires",
         {**OHLC, "timestamp": "2024-01-01T02:00:00.000Z", "status": "CLOSED"}),
        ("bar with status=PARTIAL",
         {**OHLC, "timestamp": "2024-01-01T00:00:00.000Z",
          "status": "PARTIAL"}),
    ]

    for label, bar in cases:
        ctx = {"bars": [bar]}
        try:
            out = asyncio.run(bridge._window(ctx, symbol="BTCUSDT",
                                             timeframe="1h", as_of=AS_OF))
            say("ACCEPTED  %s" % label)
            say("          normalised keys kept = %r" % sorted(out[0].keys()))
        except Exception as exc:
            say("REJECTED  %s" % label)
            say("          %s: %s" % (type(exc).__name__, exc))
        say()

    say("What _normalise_bars keeps from a real MarketObservation:")
    from apex.data_catalog.contracts import MarketObservation
    import dataclasses
    say("   MarketObservation fields = %r"
        % [f.name for f in dataclasses.fields(MarketObservation)])
    from decimal import Decimal
    obs = MarketObservation(
        symbol="BTCUSDT", timeframe="1h",
        open=Decimal("100.0"), high=Decimal("101.0"), low=Decimal("99.0"),
        close=Decimal("100.5"), volume=Decimal("10.0"), oi=None,
        timestamp="2024-01-01T01:00:00.000Z", sequence=1, status="CLOSED",
        source="toobit", availability_time="2024-01-01T04:00:00.000Z")
    row = pb._normalise_bars([obs])[0]
    say("   -> normalised row keys = %r" % sorted(row.keys()))
    say("   availability_time survived = %r" % ("availability_time" in row))

    say()
    say("For contrast, the native producer EngineContextProducer.window "
        "(engine_context.py:2367-2405) filters with "
        "close_time_ms(ts, timeframe) <= end, requires raw availability "
        "(RAW_LINEAGE_INVALID when NULL) and skips rows whose "
        "availability_time > end.")
    from apex.ops.engine_context import close_time_ms, _iso_to_ms
    open_ms = _iso_to_ms("2024-01-01T01:00:00.000Z")
    say("   close_time_ms(01:00, '1h') = %d  vs  as_of = %d  -> native %s"
        % (close_time_ms(open_ms, "1h"), _iso_to_ms(AS_OF),
           "DROPS the bar"
           if close_time_ms(open_ms, "1h") > _iso_to_ms(AS_OF) else "keeps it"))


if __name__ == "__main__":
    main()
    sys.stdout.write(OUT.read_text())
