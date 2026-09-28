"""M-002 / M-003 final isolation: conflict-free fabric, hash-order search."""
import sys
sys.path.insert(0, "/home/user/Upstage")
from apex.fabric.evidence import EvidenceFabric, FabricEvidenceRef
from apex.setup.family_sf_fvg_sweep_rev import (REQUIRED_EVIDENCE,
    OPTIONAL_EVIDENCE, evaluate_cell, fvg_gate, _evidence_directions)
from apex.playbook.pb_fvg_sweep_rev_a import build_stops
ENGINE_SET = REQUIRED_EVIDENCE + OPTIONAL_EVIDENCE
SCORED = ("structure","liquidity","fvg","trend","regime","temporal",
          "orderblock","momentum")
def mkbars(n=25, *, low_t=95.0, high_t=105.0, close=None):
    b=[{"o":100.0,"h":101.0,"l":99.0,"c":100.0,"v":1000.0} for _ in range(n-1)]
    b.append({"o":100.0,"h":high_t,"l":low_t,"c":99.7 if close is None else close,"v":2000.0})
    return b
def clean_fabric():
    refs=[FabricEvidenceRef(evidence_id=f"ev_{e}",engine_id=e,symbol="BTCUSDT",
        timeframe="1h",state="ACTIVE",direction=1,quality=0.9,
        resolution_class="Q3",age_bars=0,as_of=1000,snapshot_id=f"{hash(e)&0xffff:016x}"+"0"*48,
        lineage=(f"obs-{e}",)) for i,e in enumerate(ENGINE_SET)]
    return EvidenceFabric.assemble(symbol="BTCUSDT",timeframe="1h",as_of=1000,
        evidence=refs,data_trust=0.9)
def run(fabric, **over):
    kw=dict(symbol="BTCUSDT",timeframe="1h",as_of=1000,fabric=fabric,bars=mkbars(),
        atr=1.0,direction=1,fvg_zones=[{"index":24,"filled":False}],
        bos={"s_struct":0.6,"direction":1},regime_state="TREND",q_forecast=0.6,
        forecast={"quality":"Q3","h_norm":0.4},
        package={"package_version":1,"parameter_package_id":"pkg-1",
                 "calibration":"BOOTSTRAP_UNCALIBRATED"},
        lineage=tuple(f"obs-{i}" for i in range(len(ENGINE_SET))),
        s_i={c:1.0 for c in SCORED},q_i={c:0.9 for c in SCORED})
    kw.update(over); return evaluate_cell(**kw)

print("="*78); print("M-002  isolated: conflict-free fabric, only the FVG zone changes")
print("="*78)
fab=clean_fabric()
bear=[{"index":24,"filled":False,"low":120.0,"high":126.0,"fate":"ACTIVE","snapshot_id":"e"*64}]
bull=[{"index":24,"filled":False,"low":96.0,"high":99.0,"fate":"ACTIVE","snapshot_id":"e"*64}]
alien=[{"index":24,"filled":False,"low":90.0,"high":95.0,"fate":"UNKNOWN","snapshot_id":"9"*64}]
for name,z in (("bullish zone (correct side)",bull),("BEARISH zone (wrong side)",bear),
               ("zone absent from the fabric",alien)):
    ev=run(fab,fvg_zones=z)
    print(f"  {name:30} step4={ev.entry_logic_steps['4_fvg']['reason']:26} "
          f"status={ev.status:12} score={ev.final_score:.4f} reason={ev.reason}")
    st=build_stops(direction=1,entry=100.0,atr=1.0,sweep_extreme=95.0,
                   fvg_low=z[0]["low"],fvg_high=z[0]["high"])
    print(f"  {'':30} build_stops -> stop={st['stop']} R={st['R']} target={st['target']}")
print("  plan_bridge's own re-pick (no 12-bar window, no PIT check):")
for name,z in (("bullish",bull),("bearish",bear)):
    r=next((q for q in reversed(z) if not bool(q.get("filled",False))),None)
    print(f"    {name:10} -> index {r['index']} (fvg_gate chose "
          f"{fvg_gate(z,current_index=24)['fvg_index']})")

print(); print("="*78)
print("M-003  does the OPPOSING E01 vote ever get lost by the hash order?")
print("="*78)
others=[e for e in ENGINE_SET if e!="E01"]
def two_e01(snap_lo_dir, snap_hi_dir):
    refs=[FabricEvidenceRef(evidence_id=f"ev_{e}",engine_id=e,symbol="BTCUSDT",
        timeframe="1h",state="ACTIVE",direction=1,quality=0.9,
        resolution_class="Q3",age_bars=0,as_of=1000,
        snapshot_id=sha(e),lineage=(f"obs-{e}",)) for e in others]
    for i,(d,s) in enumerate(((snap_lo_dir,"a"*64),(snap_hi_dir,"f"*64))):
        refs.append(FabricEvidenceRef(evidence_id=f"evE01_{i}",engine_id="E01",
            symbol="BTCUSDT",timeframe="1h",state="ACTIVE",direction=d,
            quality=0.9,resolution_class="Q3",age_bars=0,as_of=1000,
            snapshot_id=s,lineage=(f"obs-E01-{i}",)))
    return EvidenceFabric.assemble(symbol="BTCUSDT",timeframe="1h",as_of=1000,
        evidence=refs,data_trust=0.9)
def sha(e): return f"{abs(hash(e))&0xffffffff:08x}"+"1"*56
lost=0; total=0
for trial in range(12):
    f=two_e01(-1,+1)
    _,pe=_evidence_directions(f)
    e01=[m for m in f.members if m.engine_id=="E01"]
    ev=run(f)
    total+=1
    lost += (pe["E01"]==+1)
    if trial<3:
        print(f"  trial{trial}: E01 members in hash order="
              f"{[(m.evidence_id,m.direction) for m in e01]} -> kept {pe['E01']:+d} "
              f"required_conflict={ev.entry_logic_steps['conflict']['required_conflict']} "
              f"status={ev.status} score={ev.final_score:.4f}")
print(f"  over {total} fabric hashes, the OPPOSING (-1) E01 vote was LOST in "
      f"{lost} cases (kept {total-lost})")
print("  -> the collapse is deterministic per fabric hash, so which of the two")
print("     contradicting E01 witnesses survives is decided by content_id")
print("     ordering, not by time or by any consensus rule.")
