"""K-033 probe — `EvidenceFabric` is a frozen dataclass whose
`redundancy_state` dict is mutable in place: `to_dict()` changes while
`hash`/`fabric_id` stay at their construction values.

READ-ONLY. Real `apex.fabric.evidence.EvidenceFabric` / `make_hash` /
`make_fabric_id`, real `apex.setup.family_sf_fvg_sweep_rev.evaluate_cell`.
Writes only this probe's .out file.
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
    from apex.fabric.evidence import (EvidenceFabric, FabricEvidenceRef,
                                      make_fabric_id, make_hash)
    from apex.setup.family_sf_fvg_sweep_rev import (
        OPTIONAL_EVIDENCE, REQUIRED_EVIDENCE, evaluate_cell)

    engines = REQUIRED_EVIDENCE + OPTIONAL_EVIDENCE
    scored = ("structure", "liquidity", "fvg", "trend", "regime", "temporal",
              "orderblock", "momentum")
    refs = [FabricEvidenceRef(
        evidence_id="ev_%d" % i, engine_id=eng, symbol="BTCUSDT",
        timeframe="1h", state="ACTIVE", direction=1, quality=0.9,
        resolution_class="Q3", age_bars=0, as_of=1000, snapshot_id="a" * 64,
        lineage=("obs-%d" % i,)) for i, eng in enumerate(engines)]

    caller_state = {"G1": 0.1}
    fab = EvidenceFabric.assemble(symbol="BTCUSDT", timeframe="1h", as_of=1000,
                                  evidence=refs, data_trust=0.9,
                                  redundancy_state=caller_state)

    say("# K-033 — EvidenceFabric(frozen=True) with a mutable nested dict")
    say()
    say("dataclass frozen = %r" % dataclasses.fields(EvidenceFabric)[0].name
        if False else "dataclass params frozen = %r"
        % EvidenceFabric.__dataclass_params__.frozen)
    say("fabric_id = %s" % fab.fabric_id)
    say("hash      = %s" % fab.hash)
    say("redundancy_state = %r" % fab.redundancy_state)

    say()
    say("1. attribute assignment is refused (this is what frozen=True buys)")
    try:
        fab.data_trust = 0.0
        say("   fab.data_trust = 0.0 -> ACCEPTED")
    except Exception as exc:
        say("   fab.data_trust = 0.0 -> %s: %s" % (type(exc).__name__, exc))

    say()
    say("2. the nested dict is mutated in place instead")
    fab.redundancy_state["G1"] = 0.99
    fab.redundancy_state["G9"] = 0.5
    say("   fab.redundancy_state = %r" % fab.redundancy_state)
    say("   fab.hash      = %s   (unchanged)" % fab.hash)
    say("   fab.fabric_id = %s   (unchanged)" % fab.fabric_id)
    d = fab.to_dict()
    say("   to_dict()['redundancy_state'] = %r" % d["redundancy_state"])
    say("   to_dict()['hash']             = %s" % d["hash"])

    body = {"as_of": fab.as_of, "symbol": fab.symbol,
            "timeframe": fab.timeframe,
            "evidence": [r.content_id for r in fab.members],
            "data_trust": fab.data_trust,
            "conflict_state": fab.conflict_state,
            "redundancy_state": dict(sorted(fab.redundancy_state.items()))}
    recomputed = make_hash(body)
    say("   hash recomputed from the CURRENT body = %s" % recomputed)
    say("   matches stored hash = %r" % (recomputed == fab.hash,))
    say("   fabric_id that the current body would get = %s"
        % make_fabric_id(recomputed))

    say()
    say("3. is the caller's own dict shared? (assemble does dict(sorted(...)))")
    caller_state["G1"] = -1.0
    say("   caller mutated its dict -> fabric sees %r"
        % fab.redundancy_state.get("G1"))

    say()
    say("4. effect on the default setup path (payload=None)")
    kw = dict(symbol="BTCUSDT", timeframe="1h", as_of=1000, fabric=fab,
              bars=[{"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0,
                     "v": 1000.0}] * 24
                   + [{"o": 100.0, "h": 100.5, "l": 95.0, "c": 99.7,
                       "v": 2000.0}],
              atr=1.0, direction=1,
              fvg_zones=[{"index": 24, "filled": False}],
              bos={"s_struct": 0.6, "direction": 1}, regime_state="TREND",
              q_forecast=0.6, forecast={"quality": "Q3", "h_norm": 0.4},
              package={"package_version": 1, "parameter_package_id": "pkg-1",
                       "calibration": "BOOTSTRAP_UNCALIBRATED"},
              lineage=tuple("obs-%d" % i for i in range(len(engines))),
              s_i={c: 1.0 for c in scored}, q_i={c: 0.9 for c in scored})
    ev = evaluate_cell(**kw)
    say("   payload=None : status=%s reason=%r"
        % (ev.status, getattr(ev, "reason", None)))
    custom = {"as_of": fab.as_of, "symbol": fab.symbol,
              "timeframe": fab.timeframe,
              "evidence": [m.content_id for m in fab.members],
              "data_trust": fab.data_trust,
              "conflict_state": fab.conflict_state,
              "redundancy_state": dict(fab.redundancy_state)}
    ev2 = evaluate_cell(payload=custom, **kw)
    say("   payload=<current body> : status=%s all_pass=%s"
        % (ev2.status, ev2.gate_block.get("all_pass")))


if __name__ == "__main__":
    main()
    sys.stdout.write(OUT.read_text())
