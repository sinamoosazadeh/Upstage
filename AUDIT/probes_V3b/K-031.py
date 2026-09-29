"""K-031 probe — SnapshotBarrier calls itself immutable but is freely mutable,
and its id is computed only once.

READ-ONLY. Real `apex.identity.snapshot.SnapshotBarrier`,
`snapshot_id_from_payload`, and the real builder
`apex.quality.pit.build_snapshot_barrier`. Writes only this probe's .out file.
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
    from apex.identity.snapshot import SnapshotBarrier, snapshot_id_from_payload
    from apex.quality.pit import build_snapshot_barrier

    windows = {"1h": {"start": 0, "end": 3_600_000, "timeframe": "1h",
                      "bars": 114}}
    quality = {"min_q": 0.9, "weighted_q": 0.95}
    scope = ["BTCUSDT"]
    barrier = build_snapshot_barrier(
        as_of_ms=1_672_534_800_000, symbol_scope=scope,
        timeframe_scope=["1h"], source_state="VALID", mhash="a" * 64,
        parameter_package_id="pkg-1", code_version="4.0.0",
        quality_state=quality, observation_windows=windows,
        mtf_states={"1h": "ALIGNED"}, overall_mtf="ALIGNED")

    say("# K-031 — SnapshotBarrier mutability")
    say()
    say("constructed snapshot_id = %s" % barrier.snapshot_id)
    say("payload hash recomputed = %s"
        % snapshot_id_from_payload(barrier._canonical_payload()))

    say()
    say("1. mutate public fields after construction")
    barrier.quality_state["min_q"] = 0.0
    barrier.source_state = "INVALID"
    say("   quality_state now = %r  source_state now = %r"
        % (barrier.quality_state, barrier.source_state))

    say()
    say("2. mutate a NESTED dict through the caller's own object "
        "(constructor does dict(...) — a shallow copy)")
    windows["1h"]["bars"] = 1
    say("   caller changed windows['1h']['bars'] -> barrier sees %r"
        % (barrier.observation_windows["1h"]["bars"],))

    say()
    say("3. grow symbol_scope past the §2.3 limit of 10")
    for i in range(10):
        barrier.symbol_scope.append("SYM%02d" % i)
    say("   len(symbol_scope) = %d" % len(barrier.symbol_scope))
    try:
        SnapshotBarrier(
            as_of="2023-01-01T01:00:00.000Z", symbol_scope=barrier.symbol_scope,
            timeframe_scope=["1h"], source_state="VALID", manifest_hash="a" * 64,
            parameter_package_id="pkg-1", code_version="4.0.0",
            quality_state={}, observation_windows={}, mtf_states={},
            overall_mtf="ALIGNED")
        say("   constructing a NEW barrier with 11 symbols: ACCEPTED")
    except ValueError as exc:
        say("   constructing a NEW barrier with 11 symbols: refused (%s)" % exc)

    say()
    say("4. identity vs current content")
    say("   to_dict()['snapshot_id']      = %s" % barrier.to_dict()["snapshot_id"])
    say("   hash of the CURRENT payload   = %s"
        % snapshot_id_from_payload(barrier._canonical_payload()))
    say("   equal = %r" % (barrier.to_dict()["snapshot_id"]
                           == snapshot_id_from_payload(barrier._canonical_payload()),))


if __name__ == "__main__":
    main()
    sys.stdout.write(OUT.read_text())
