"""K-030 probe — the snapshot's combined quality state is a fabricated zero while
the snapshot is reported VALID/Q1.

READ-ONLY. Real `apex.quality.pit.calc_snapshot_pit_window` /
`_min_q_and_weighted_mean`, real frozen `MarketObservation` from the Toobit
parser. Writes only this probe's .out file.
"""
import dataclasses
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
    from apex.data_catalog.contracts import MarketObservation
    from apex.data_catalog.ingest.toobit_public import parse_kline_to_observation
    from apex.quality.pit import calc_snapshot_pit_window, _min_q_and_weighted_mean

    HOUR = 3_600_000
    T0 = 1_672_531_200_000
    obs = [parse_kline_to_observation(
        "BTCUSDT", "1h",
        [T0 + i * HOUR, "100", "101", "99", "100.5", "10",
         T0 + (i + 1) * HOUR - 1], 0) for i in range(3)]

    say("# K-030 — snapshot quality_state is always zero")
    say()
    say("MarketObservation has a q_raw field = %r"
        % ("q_raw" in {f.name for f in dataclasses.fields(MarketObservation)},))
    say("fields carrying quality inputs = %r"
        % [f.name for f in dataclasses.fields(MarketObservation)
           if f.name in ("source_health", "gap_count", "expected_count",
                         "completeness_pct", "delay_seconds")])
    say("observation source_health/completeness = %r / %r"
        % (obs[0].source_health, obs[0].completeness_pct))

    say()
    say("_min_q_and_weighted_mean(perfectly healthy bars) = %r"
        % (_min_q_and_weighted_mean(obs),))

    snap, state, cls = calc_snapshot_pit_window(obs, ["1h"], minimum_bars=3)
    say()
    say("calc_snapshot_pit_window -> state=%r class=%r" % (state, cls))
    say("   snapshot['quality_state'] = %r" % (snap["quality_state"],))
    say("   source_state              = %r" % (snap["source_state"],))
    say("   -> min_q = 0.0 (a minimum-veto failure) is reported together with "
        "source_state VALID and class Q1")

    say()
    say("the value comes from apex/quality/pit.py:174 — "
        "getattr(obs, 'q_raw', 0.0) on a dataclass with no q_raw attribute; "
        "the docstring calls it 'Observations without a computed Q_raw count as Q0'")


if __name__ == "__main__":
    main()
    sys.stdout.write(OUT.read_text())
