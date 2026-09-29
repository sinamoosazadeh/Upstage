"""K-032 probe — a tampered Evidence-Fabric hash is caught only when
`payload is None`; supplying any self-consistent `payload` skips the
fabric self-integrity check and Gate 11 compares the payload against an id
derived from that same payload.

READ-ONLY. Imports the real `apex.setup.family_sf_fvg_sweep_rev.evaluate_cell`,
the real `apex.fabric.evidence.EvidenceFabric` and the real
`apex.setup.gates.run_all`. Fixture inputs mirror
`tests/unit/test_setup_family_sf_fvg_sweep_rev.py::base_kwargs`.
Writes only this probe's .out file.
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
    from apex.fabric.evidence import EvidenceFabric, FabricEvidenceRef
    from apex.identity.canonical_json import canonical_json
    from apex.identity.hashes import sha256_hex
    from apex.setup.family_sf_fvg_sweep_rev import (
        OPTIONAL_EVIDENCE, REQUIRED_EVIDENCE, evaluate_cell)
    from apex.setup.gates import gate11_snapshot_lineage

    engines = REQUIRED_EVIDENCE + OPTIONAL_EVIDENCE
    scored = ("structure", "liquidity", "fvg", "trend", "regime", "temporal",
              "orderblock", "momentum")

    def mkbars(n=25):
        bars = [{"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0, "v": 1000.0}
                for _ in range(n - 1)]
        bars.append({"o": 100.0, "h": 100.5, "l": 95.0, "c": 99.7, "v": 2000.0})
        return bars

    def fabric_for():
        refs = [FabricEvidenceRef(
            evidence_id="ev_%d" % i, engine_id=eng, symbol="BTCUSDT",
            timeframe="1h", state="ACTIVE", direction=1, quality=0.9,
            resolution_class="Q3", age_bars=0, as_of=1000,
            snapshot_id="a" * 64, lineage=("obs-%d" % i,))
            for i, eng in enumerate(engines)]
        return EvidenceFabric.assemble(symbol="BTCUSDT", timeframe="1h",
                                       as_of=1000, evidence=refs,
                                       data_trust=0.9)

    def kwargs(fab, payload=None):
        return dict(
            symbol="BTCUSDT", timeframe="1h", as_of=1000, fabric=fab,
            bars=mkbars(), atr=1.0, direction=1,
            fvg_zones=[{"index": 24, "filled": False}],
            bos={"s_struct": 0.6, "direction": 1}, regime_state="TREND",
            q_forecast=0.6, forecast={"quality": "Q3", "h_norm": 0.4},
            package={"package_version": 1, "parameter_package_id": "pkg-1",
                     "calibration": "BOOTSTRAP_UNCALIBRATED"},
            lineage=tuple("obs-%d" % i for i in range(len(engines))),
            s_i={c: 1.0 for c in scored}, q_i={c: 0.9 for c in scored},
            payload=payload)

    say("# K-032 — fabric-hash check is conditional on `payload is None`")
    say()

    # ---- baseline: untampered fabric, no payload ----
    fab = fabric_for()
    ev = evaluate_cell(**kwargs(fab))
    say("baseline (genuine fabric, payload=None)")
    say("   status=%s all_pass=%s reason=%r"
        % (ev.status, ev.gate_block.get("all_pass"), getattr(ev, "reason", None)))
    say("   fabric.hash = %s" % fab.hash)

    # ---- tampered fabric hash, payload=None ----
    bad = fabric_for()
    object.__setattr__(bad, "hash", "f" * 64) if hasattr(bad, "__dataclass_fields__") \
        else setattr(bad, "hash", "f" * 64)
    ev2 = evaluate_cell(**kwargs(bad))
    say()
    say("A. tampered fabric.hash = %s , payload=None" % bad.hash)
    say("   status=%s reason=%r" % (ev2.status, getattr(ev2, "reason", None)))

    # ---- same tampered fabric, but a caller-supplied payload ----
    custom = {"as_of": 1000, "symbol": "BTCUSDT", "timeframe": "1h",
              "evidence": [m.content_id for m in bad.members],
              "data_trust": bad.data_trust,
              "conflict_state": bad.conflict_state,
              "redundancy_state": dict(bad.redundancy_state)}
    ev3 = evaluate_cell(**kwargs(bad, payload=custom))
    say()
    say("B. SAME tampered fabric.hash, payload=<caller-supplied dict>")
    say("   status=%s all_pass=%s reason=%r"
        % (ev3.status, ev3.gate_block.get("all_pass"),
           getattr(ev3, "reason", None)))
    say("   gate_block keys = %r" % sorted(ev3.gate_block.keys()))
    res = ev3.gate_block.get("results")
    g11 = (res.get(11) if isinstance(res, dict)
           else [g for g in res if isinstance(g, dict)
                 and g.get("gate") == 11])
    say("   gate 11 entry = %r" % (g11,))

    # ---- payload need not even describe this fabric ----
    unrelated = {"anything": "at all", "symbol": "ETHUSDT", "as_of": 1}
    ev4 = evaluate_cell(**kwargs(bad, payload=unrelated))
    say()
    say("C. SAME tampered fabric.hash, payload={'anything':'at all',"
        " 'symbol':'ETHUSDT','as_of':1}  (unrelated to the cell)")
    say("   status=%s all_pass=%s" % (ev4.status, ev4.gate_block.get("all_pass")))
    say("   snapshot_id emitted = %s"
        % sha256_hex(canonical_json(unrelated)))

    # ---- gate 11 in isolation: fabric_hash is an optional argument ----
    say()
    say("D. gate11 alone — the fabric_hash argument that the family never passes")
    r_no = gate11_snapshot_lineage(sha256_hex(canonical_json(unrelated)),
                                   unrelated, ["obs-0"])
    r_yes = gate11_snapshot_lineage(sha256_hex(canonical_json(unrelated)),
                                    unrelated, ["obs-0"], fabric_hash="f" * 64)
    say("   without fabric_hash: passed=%s reason=%r"
        % (r_no.passed, r_no.reason))
    say("   with fabric_hash='f'*64: passed=%s reason=%r"
        % (r_yes.passed, r_yes.reason))
    say("   (family gate_ctx keys never include 'fabric_hash' → "
        "gates.run_all passes None)")


if __name__ == "__main__":
    main()
    sys.stdout.write(OUT.read_text())
