"""M-002 / M-003 refined constructions."""
import inspect
import sys

sys.path.insert(0, "/home/user/Upstage")

from apex.fabric.evidence import EvidenceFabric, FabricEvidenceRef
from apex.setup.family_sf_fvg_sweep_rev import (REQUIRED_EVIDENCE,
                                                 OPTIONAL_EVIDENCE,
                                                 evaluate_cell, fvg_gate,
                                                 _evidence_directions)
from apex.playbook.pb_fvg_sweep_rev_a import build_stops

ENGINE_SET = REQUIRED_EVIDENCE + OPTIONAL_EVIDENCE
SCORED = ("structure", "liquidity", "fvg", "trend", "regime", "temporal",
          "orderblock", "momentum")


def mkbars(n=25, *, low_t=95.0, high_t=105.0, close=None):
    bars = [{"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0, "v": 1000.0}
            for _ in range(n - 1)]
    bars.append({"o": 100.0, "h": high_t, "l": low_t,
                 "c": 99.7 if close is None else close, "v": 2000.0})
    return bars


def run(fabric, **over):
    kw = dict(symbol="BTCUSDT", timeframe="1h", as_of=1000, fabric=fabric,
              bars=mkbars(), atr=1.0, direction=1,
              fvg_zones=[{"index": 24, "filled": False}],
              bos={"s_struct": 0.6, "direction": 1}, regime_state="TREND",
              q_forecast=0.6, forecast={"quality": "Q3", "h_norm": 0.4},
              package={"package_version": 1, "parameter_package_id": "pkg-1",
                       "calibration": "BOOTSTRAP_UNCALIBRATED"},
              lineage=tuple(f"obs-{i}" for i in range(len(ENGINE_SET))),
              s_i={c: 1.0 for c in SCORED}, q_i={c: 0.9 for c in SCORED})
    kw.update(over)
    return evaluate_cell(**kw)


print("=" * 78)
print("M-003  two OPPOSING ACTIVE E01 members; which one survives the collapse")
print("=" * 78)
refs = []
for i, eng in enumerate(ENGINE_SET):
    if eng == "E01":
        continue
    refs.append(FabricEvidenceRef(
        evidence_id=f"ev_{eng}", engine_id=eng, symbol="BTCUSDT",
        timeframe="1h", state="ACTIVE", direction=1, quality=0.9,
        resolution_class="Q3", age_bars=0, as_of=1000,
        snapshot_id=f"{i:064d}", lineage=(f"obs-{eng}",)))
# two opposing E01 refs with DIFFERENT snapshot ids
a = FabricEvidenceRef(evidence_id="evA", engine_id="E01", symbol="BTCUSDT",
                      timeframe="1h", state="ACTIVE", direction=-1,
                      quality=0.9, resolution_class="Q3", age_bars=0,
                      as_of=1000, snapshot_id="f" * 64, lineage=("obs-A",))
b = FabricEvidenceRef(evidence_id="evB", engine_id="E01", symbol="BTCUSDT",
                      timeframe="1h", state="ACTIVE", direction=+1,
                      quality=0.9, resolution_class="Q3", age_bars=0,
                      as_of=1000, snapshot_id="0" * 64, lineage=("obs-B",))
fab = EvidenceFabric.assemble(symbol="BTCUSDT", timeframe="1h", as_of=1000,
                              evidence=refs + [a, b], data_trust=0.9)
print("  fabric members in D50 hash (content_id) order:")
for m in fab.members:
    print(f"    {m.engine_id} direction={m.direction:+d} "
          f"content_id={m.content_id[:12]}… evidence_id={m.evidence_id}")
_bd, _pe = _evidence_directions(fab)
print(f"  per_engine after the collapse: "
      f"{ {k: v for k, v in sorted(_pe.items())} }")
print(f"  ALL members carrying E01: "
      f"{[(m.evidence_id, m.direction) for m in fab.members if m.engine_id == 'E01']}")
ev = run(fab)
print(f"  evaluate_cell(direction=+1) -> status={ev.status} reason={ev.reason} "
      f"score={ev.final_score:.4f}")
print(f"  conflict step: {ev.entry_logic_steps.get('conflict')}")
print(f"  -> the DIRECTION of the setup is not in the conflict law; only the")
print(f"     collapsed per-engine votes are.  A genuine E01 contradiction")
print(f"     (-1 and +1 in the same ACTIVE fabric) is scored only if the hash")
print(f"     order happens to leave -1 last.")
ev2 = run(fab, bos={"s_struct": 0.6, "direction": 1})
print(f"  same fabric, all other requireds +1: required_conflict="
      f"{ev2.entry_logic_steps['conflict']['required_conflict']}  "
      f"multiplier={ev2.entry_logic_steps['conflict']['multiplier']}")
# force the opposite hash order by swapping the snapshot ids
a2 = FabricEvidenceRef(evidence_id="evA", engine_id="E01", symbol="BTCUSDT",
                       timeframe="1h", state="ACTIVE", direction=-1,
                       quality=0.9, resolution_class="Q3", age_bars=0,
                       as_of=1000, snapshot_id="0" * 64, lineage=("obs-A",))
b2 = FabricEvidenceRef(evidence_id="evB", engine_id="E01", symbol="BTCUSDT",
                       timeframe="1h", state="ACTIVE", direction=+1,
                       quality=0.9, resolution_class="Q3", age_bars=0,
                       as_of=1000, snapshot_id="f" * 64, lineage=("obs-B",))
fab2 = EvidenceFabric.assemble(symbol="BTCUSDT", timeframe="1h", as_of=1000,
                               evidence=refs + [a2, b2], data_trust=0.9)
_pd2, pe2 = _evidence_directions(fab2)
print(f"  same two E01 refs, snapshot ids swapped -> per_engine E01="
      f"{pe2['E01']:+d}  (the hash order, not any consensus, decides)")
ev3 = run(fab2)
print(f"  evaluate_cell on that fabric -> status={ev3.status} "
      f"score={ev3.final_score:.4f} "
      f"required_conflict={ev3.entry_logic_steps['conflict']['required_conflict']} "
      f"multiplier={ev3.entry_logic_steps['conflict']['multiplier']}")

print()
print("=" * 78)
print("M-002  opposite-direction FVG accepted; and a zone that is NOT in the")
print("       fabric / NOT from E05 is accepted just the same")
print("=" * 78)
bear = [{"index": 24, "filled": False, "low": 120.0, "high": 126.0,
         "fate": "ACTIVE", "snapshot_id": "e" * 64}]
g = fvg_gate(bear, current_index=24)
print(f"  LONG setup, only a BEARISH FVG present (above price):")
print(f"    fvg_gate -> ok={g['ok']} idx={g['fvg_index']} zone={g['zone']}")
ev4 = run(fab2, fvg_zones=bear)
print(f"    evaluate_cell -> status={ev4.status} reason={ev4.reason} "
      f"step4={ev4.entry_logic_steps['4_fvg']['reason']}")
# a zone whose snapshot_id is in NO fabric member
alien = [{"index": 24, "filled": False, "low": 90.0, "high": 95.0,
          "fate": "UNKNOWN", "snapshot_id": "9" * 64}]
ev5 = run(fab2, fvg_zones=alien)
print(f"  a zone with snapshot_id not present in the fabric and fate='UNKNOWN':")
print(f"    fvg_gate -> {fvg_gate(alien, current_index=24)['reason']}")
print(f"    evaluate_cell -> status={ev5.status} reason={ev5.reason}")
st_a = build_stops(direction=1, entry=100.0, atr=1.0, sweep_extreme=95.0,
                   fvg_low=alien[0]["low"], fvg_high=alien[0]["high"])
st_b = build_stops(direction=1, entry=100.0, atr=1.0, sweep_extreme=95.0,
                   fvg_low=None, fvg_high=None)
print(f"    build_stops with the alien zone: stop={st_a['stop']} R={st_a['R']} "
      f"target={st_a['target']}")
print(f"    build_stops with NO zone     : stop={st_b['stop']} R={st_b['R']} "
      f"target={st_b['target']}")
print(f"    -> identical here (sweep_extreme=95 < alien low=90? no: 90<95, so")
print(f"       min(95,90)=90 differs) : "
      f"{'DIFFERS' if st_a['stop'] != st_b['stop'] else 'same'}")
st_c = build_stops(direction=1, entry=100.0, atr=1.0, sweep_extreme=95.0,
                   fvg_low=120.0, fvg_high=126.0)
print(f"    with the BEARISH zone (low=120 > sweep 95): stop={st_c['stop']} "
      f"R={st_c['R']} -> {'SAME as no-zone' if st_c['stop'] == st_b['stop'] else 'DIFFERS'}")
print("  -> a genuinely opposite-side zone normally does NOT move the LONG stop")
print("     (min() picks the sweep extreme), but the gate ACCEPTANCE itself is")
print("     wrong and a zone whose boundary is beyond the sweep extreme does")
print("     move R/target/sizing.")
print("DONE M-002 / M-003 refined")
