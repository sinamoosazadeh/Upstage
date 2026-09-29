"""K-028 probe — calc_snapshot_pit_window counts entries, not distinct valid bars,
and never uses freshness_threshold.

READ-ONLY. Real `apex.quality.pit.calc_snapshot_pit_window` with real
MarketObservation objects built by the frozen Toobit parser. Writes only this
probe's .out file.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = pathlib.Path(__file__).with_suffix(".out")
_buf = []


def say(line=""):
    _buf.append(str(line))
    OUT.write_text("\n".join(_buf) + "\n")


def main():
    from apex.data_catalog.ingest.toobit_public import parse_kline_to_observation
    from apex.quality.pit import calc_snapshot_pit_window

    HOUR = 3_600_000
    T0 = 1_672_531_200_000          # 2023-01-01T00:00:00Z

    def bar(open_ms):
        return parse_kline_to_observation(
            "BTCUSDT", "1h",
            [open_ms, "100", "101", "99", "100.5", "10", open_ms + HOUR - 1], 0)

    say("# K-028 — snapshot PIT window sufficiency and freshness")
    say()
    one = bar(T0)
    say("1. 114 copies of ONE 1h bar, minimum_bars=100")
    snap, state, cls = calc_snapshot_pit_window([one] * 114, ["1h"],
                                                minimum_bars=100)
    say("   state/class      = %r / %r" % (state, cls))
    say("   mtf_states       = %r" % (snap["mtf_states"],))
    say("   overall_mtf      = %r" % (snap["overall_mtf"],))
    say("   observation_windows['1h'] = %r" % (snap["observation_windows"]["1h"],))
    say("   distinct open times in the input = %d"
        % len({o.timestamp for o in [one] * 114}))

    say()
    say("2. the same call with a 1-second freshness_threshold on a 2023 bar")
    snap2, state2, cls2 = calc_snapshot_pit_window(
        [one] * 114, ["1h"], minimum_bars=100, freshness_threshold=1.0)
    say("   state/class      = %r / %r" % (state2, cls2))
    say("   identical snapshot_id as case 1 = %r"
        % (snap2["snapshot_id"] == snap["snapshot_id"],))
    src = pathlib.Path(ROOT / "apex/quality/pit.py").read_text().splitlines()
    body = "\n".join(src[59:166])
    say("   occurrences of 'freshness_threshold' in the function body = %d "
        "(the signature parameter only)" % body.count("freshness_threshold"))

    say()
    say("3. 114 DISTINCT consecutive bars (the honest window)")
    many = [bar(T0 + i * HOUR) for i in range(114)]
    snap3, state3, cls3 = calc_snapshot_pit_window(many, ["1h"],
                                                   minimum_bars=100)
    say("   state/class      = %r / %r" % (state3, cls3))
    say("   distinct open times = %d" % len({o.timestamp for o in many}))
    say("   -> cases 1 and 3 are reported identically apart from as_of/hash")

    say()
    say("4. the PIT loop (apex/quality/pit.py:79-82)")
    say("   as_of_ms = max(availability) over the same list it then compares "
        "against, so `_availability_ms(obs) > as_of_ms` is unreachable: "
        "PIT_VIOLATION cannot be returned by this helper.")


if __name__ == "__main__":
    main()
    sys.stdout.write(OUT.read_text())
