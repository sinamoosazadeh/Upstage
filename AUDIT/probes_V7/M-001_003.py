"""M-001..M-016 — real apex modules only (no re-implementation).

Fixture shape follows the repository's own
tests/unit/test_setup_family_sf_fvg_sweep_rev.py.
"""
import asyncio
import sqlite3
import sys

sys.path.insert(0, "/home/user/Upstage")

from apex.fabric.evidence import EvidenceFabric, FabricEvidenceRef
from apex.setup.family_sf_fvg_sweep_rev import (
    REQUIRED_EVIDENCE, OPTIONAL_EVIDENCE, evaluate_cell, structure_gate,
    fvg_gate, mtf_gate, relative_mtf, atr_gate, _evidence_directions)
from apex.setup import gates
from apex.decision.pipeline import (generate_candidates, build_proposal,
                                    units_of_r, rank, NO_TRADE)
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


def fabric_for(timeframe="1h", *, engines=ENGINE_SET, direction=1,
               symbol="BTCUSDT", quality=0.9):
    refs = []
    for i, eng in enumerate(engines):
        d = direction.get(eng, 1) if isinstance(direction, dict) else direction
        refs.append(FabricEvidenceRef(
            evidence_id=f"ev_{i}", engine_id=eng, symbol=symbol,
            timeframe=timeframe, state="ACTIVE", direction=d,
            quality=quality, resolution_class="Q3", age_bars=0, as_of=1000,
            snapshot_id=f"{i:064d}", lineage=(f"obs-{i}",)))
    return EvidenceFabric.assemble(symbol=symbol, timeframe=timeframe,
                                   as_of=1000, evidence=refs, data_trust=0.9)


def base_kwargs(timeframe="1h", **over):
    kw = dict(symbol="BTCUSDT", timeframe=timeframe, as_of=1000,
              fabric=fabric_for(timeframe), bars=mkbars(), atr=1.0,
              direction=1,
              fvg_zones=[{"index": 24, "filled": False}],
              bos={"s_struct": 0.6, "direction": 1}, regime_state="TREND",
              q_forecast=0.6, forecast={"quality": "Q3", "h_norm": 0.4},
              package={"package_version": 1, "parameter_package_id": "pkg-1",
                       "calibration": "BOOTSTRAP_UNCALIBRATED"},
              lineage=tuple(f"obs-{i}" for i in range(len(ENGINE_SET))),
              s_i={c: 1.0 for c in SCORED}, q_i={c: 0.9 for c in SCORED})
    kw.update(over)
    return kw


def run(**over):
    tf = over.pop("timeframe", "1h")
    return evaluate_cell(**base_kwargs(tf, **over))


print("=" * 78)
print("M-001  structure_gate checks direction != 0, never direction agreement")
print("=" * 78)
for d in (1, -1, 0):
    g = structure_gate({"s_struct": 0.6, "direction": d}, s_min=0.55)
    print(f"  structure_gate(direction={d:+d}) -> ok={g['ok']} "
          f"reason={g['reason']}")
ev = run(direction=1, bos={"s_struct": 0.6, "direction": -1})
print(f"  evaluate_cell(direction=+1 (BULLISH setup), bos.direction=-1) -> "
      f"status={ev.status} reason={ev.reason} "
      f"step5={ev.entry_logic_steps['5_structure']['reason']}")
print(f"  final_score={ev.final_score:.4f}  all_pass="
      f"{ev.gate_block.get('all_pass')}")
print("  the setup's own direction is NOT an argument of structure_gate:")
import inspect
print("   ", inspect.signature(structure_gate))
print("  producer selection (engine_context.py:1927-1931):")
import subprocess
print(subprocess.run(["sed", "-n", "1927,1931p", "apex/ops/engine_context.py"],
                     capture_output=True, text=True).stdout)

print()
print("=" * 78)
print("M-002  fvg_gate takes the newest UNFILLED zone with no direction check;")
print("       the bridge re-picks a (possibly different) zone afterwards")
print("=" * 78)
zones = [{"index": 23, "filled": False, "low": 96.0, "high": 98.0,
          "fate": "ACTIVE"},                       # bullish gap below price
         {"index": 24, "filled": False, "low": 120.0, "high": 126.0,
          "fate": "ACTIVE"}]                      # BEARISH gap above price
g = fvg_gate(zones, current_index=24)
print(f"  fvg_gate(setup direction +1) -> {g['reason']} idx={g['fvg_index']} "
      f"zone={g['zone']}")
ev2 = run(direction=1, fvg_zones=zones)
print(f"  evaluate_cell -> status={ev2.status} "
      f"step4_idx={ev2.entry_logic_steps['4_fvg']['fvg_index']} "
      f"reason={ev2.reason}")
recent = next((z for z in reversed(zones) if not bool(z.get("filled", False))), None)
print(f"  plan_bridge re-pick: recent_zone = {recent}  (index "
      f"{recent['index']}, fvg gate used index {g['fvg_index']})")
print(f"  same zone here, but note: the bridge re-pick has NO 12-bar window and")
print(f"  NO snapshot/fate check, only `not filled`.")
st = build_stops(direction=1, entry=100.0, atr=1.0, sweep_extreme=95.0,
                 fvg_low=recent["low"], fvg_high=recent["high"])
print(f"  build_stops(LONG) with that zone -> stop={st['stop']} R={st['R']:.4f} "
      f"target={st['target']}")
# now push the bullish zone out of the 12-bar window
zones2 = [{"index": 5, "filled": False, "low": 96.0, "high": 98.0},
          {"index": 24, "filled": False, "low": 120.0, "high": 126.0}]
g2 = fvg_gate(zones2, current_index=24)
r2 = next((z for z in reversed(zones2) if not bool(z.get("filled", False))), None)
print(f"  zone at index 5 (OUTSIDE the 12-bar window) + zone 24:")
print(f"    fvg_gate -> {g2['reason']} idx={g2.get('fvg_index')}")
print(f"    plan_bridge re-pick -> index {r2['index']}  "
      f"({'SAME' if r2['index'] == g2.get('fvg_index') else 'DIFFERENT'})")
print("  MITIGATED fate is not read by fvg_gate either:",
      [ln.strip() for ln in inspect.getsource(fvg_gate).splitlines()
       if "filled" in ln or "fate" in ln])

print()
print("=" * 78)
print("M-003  _evidence_directions keeps only the LAST direction per engine")
print("=" * 78)
fab = fabric_for(direction={"E01": -1})
by_dir, per_engine = _evidence_directions(fab)
print(f"  fabric with E01.direction=-1 and the rest +1")
print(f"    per_engine = {per_engine}")
refs = list(fab.members)
print(f"    members in hash order: {[(m.engine_id, m.direction) for m in refs]}")
# two opposing ACTIVE E01 members
a = FabricEvidenceRef(evidence_id="evA", engine_id="E01", symbol="BTCUSDT",
                      timeframe="1h", state="ACTIVE", direction=-1,
                      quality=0.9, resolution_class="Q3", age_bars=0, as_of=1000,
                      snapshot_id="a" * 64, lineage=("obs-a",))
b = FabricEvidenceRef(evidence_id="evB", engine_id="E01", symbol="BTCUSDT",
                      timeframe="1h", state="ACTIVE", direction=+1,
                      quality=0.9, resolution_class="Q3", age_bars=0, as_of=1000,
                      snapshot_id="b" * 64, lineage=("obs-b",))
fab2 = EvidenceFabric.assemble(symbol="BTCUSDT", timeframe="1h", as_of=1000,
                               evidence=[a, b], data_trust=0.9)
print(f"  two opposing ACTIVE E01 refs: "
      f"{[(m.engine_id, m.direction) for m in fab2.members]}")
_bd, _pe = _evidence_directions(fab2)
print(f"    per_engine after the collapse = {_pe}  <-- ONE of -1/+1 survives")
ev3 = run(fabric=fab, bos={"s_struct": 0.6, "direction": 1})
print(f"  evaluate_cell with an E01 that votes -1 while the setup is +1 -> "
      f"status={ev3.status} reason={ev3.reason} "
      f"score={ev3.final_score:.4f}")
print(f"  required_conflict step = {ev3.entry_logic_steps.get('conflict')}")
print(f"  conflict multiplier = "
      f"{ev3.entry_logic_steps.get('conflict', {}).get('multiplier')}")
print("  Evaluate_cell source lines for required_conflict:")
print("   ", [ln.strip() for ln in inspect.getsource(evaluate_cell).splitlines()
                if "required_conflict" in ln][:3])
print("DONE M-001..M-003")
