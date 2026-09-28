"""M-009..M-016 — real repository modules + the repository's own CH4_DDL."""
import sqlite3
import sys

sys.path.insert(0, "/home/user/Upstage")

from apex.data_catalog.store.sqlite_store import CH4_DDL
from apex.pattern import detect as D
from apex.setup import gates
from apex.setup.family_sf_fvg_sweep_rev import (REQUIRED_EVIDENCE,
                                                 OPTIONAL_EVIDENCE,
                                                 evaluate_cell, mtf_gate)
from apex.fabric.evidence import EvidenceFabric, FabricEvidenceRef
from apex.decision.pipeline import (build_proposal, generate_candidates,
                                    units_of_r, rank, NO_TRADE)
from apex.ops.plan_bridge import _SETUP_COLUMNS
from apex.playbook.pb_fvg_sweep_rev_a import build_stops

ENGINE_SET = REQUIRED_EVIDENCE + OPTIONAL_EVIDENCE
SCORED = ("structure", "liquidity", "fvg", "trend", "regime", "temporal",
          "orderblock", "momentum")


def db():
    c = sqlite3.connect(":memory:")
    c.executescript(CH4_DDL)
    return c


print("=" * 78)
print("M-009  pattern_evidence is a declared-but-unused table; the bridge")
print("       mints ACTIVE PatternEntity records straight from the legacy")
print("       CATALOGUE, and never looks the pattern up in the store")
print("=" * 78)
import apex.ops.plan_bridge as PB
c = db()
n = c.execute("SELECT count(*) FROM pattern_evidence").fetchone()[0]
print(f"  a FRESH repository CH4_DDL database: pattern_evidence rows = {n}")
try:
    e = PB._pattern_entity("PAT-STR-001")
    print(f"  _pattern_entity('PAT-STR-001') on that EMPTY db -> pattern_id="
          f"{e.pattern_id} lifecycle_status={e.lifecycle_status} "
          f"contribution={e.setup_score_contribution_class}")
    print(f"    provenance_class={e.provenance_class}")
except Exception as exc:
    print(f"  _pattern_entity('PAT-STR-001') -> {type(exc).__name__}: {exc}")
supplied = D.entity_for(next(r for r in D.CATALOGUE
                              if r.pattern_id == "PAT-STR-005"))
try:
    e2 = PB._pattern_entity("PAT-STR-001", supplied)
    print(f"  a caller-supplied PAT-STR-005 entity, requested as PAT-STR-001 -> "
          f"ACCEPTED, entity.pattern_id={e2.pattern_id}")
except Exception as exc:
    print(f"  supplied-entity ID mismatch -> {type(exc).__name__}: {exc}")
print("  SELECT/INSERT against pattern_evidence anywhere in apex/:")
import subprocess
print(subprocess.run(["grep", "-rnE", "FROM pattern_evidence|INTO pattern_evidence",
                      "--include=*.py", "apex/"], capture_output=True,
                     text=True).stdout or
      "  -> NONE.  The table is declared in CH4_DDL and never read or written.")
print("  every mention of the table in apex/:")
print("   ", subprocess.run(["grep", "-rn", "pattern_evidence", "--include=*.py",
                            "apex/"], capture_output=True, text=True).stdout
      .replace("\n", " | ").strip())
print("  the accept path (plan_bridge.py:750-758) with no pattern_hit and no")
print("  pattern_detected flag at all -> PATTERN_NOT_DETECTED is not raised:")
print("   ", [ln.strip() for ln in
          __import__("inspect").getsource(PB).splitlines()
          if "pattern_detected" in ln])
print("  there is no `pattern_hit` table in CH4_DDL:",
      [r[0] for r in c.execute(
          "SELECT name FROM sqlite_master WHERE type='table'")])

print()
print("=" * 78)
print("M-010  setup_id is a short hash of the inputs; the same cell with a")
print("        different stop/confidence/regime collides on INSERT OR IGNORE")
print("=" * 78)
import inspect as _i
from apex.setup.family_sf_fvg_sweep_rev import SetupEvaluation
print("  ", [_l.strip() for _l in _i.getsource(SetupEvaluation).splitlines()
             if "setup_id" in _l])
print("  ", [_l.strip() for _l in
       open("/home/user/Upstage/apex/ops/plan_bridge.py").read().splitlines()
       if "INSERT OR IGNORE INTO setup_candidate" in _l])


def fab_tf(tf="1h"):
    refs = [FabricEvidenceRef(evidence_id=f"ev_{e}", engine_id=e,
                              symbol="BTCUSDT", timeframe=tf, state="ACTIVE",
                              direction=1, quality=0.9, resolution_class="Q3",
                              age_bars=0, as_of=1000, snapshot_id=f"{i:064d}",
                              lineage=(f"obs-{e}",))
            for i, e in enumerate(ENGINE_SET)]
    return EvidenceFabric.assemble(symbol="BTCUSDT", timeframe=tf, as_of=1000,
                                   evidence=refs, data_trust=0.9)


def mkbars(n=25, *, low_t=95.0, high_t=105.0, close=None):
    b = [{"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0, "v": 1000.0}
         for _ in range(n - 1)]
    b.append({"o": 100.0, "h": high_t, "l": low_t,
              "c": 99.7 if close is None else close, "v": 2000.0})
    return b


def mk(atr=1.0, s_i=None, regime="TREND", direction=1, quality=0.9):
    kw = dict(symbol="BTCUSDT", timeframe="1h", as_of=1000, fabric=fab_tf(),
              bars=mkbars(), atr=atr, direction=direction,
              fvg_zones=[{"index": 24, "filled": False}],
              bos={"s_struct": 0.6, "direction": direction},
              regime_state=regime, q_forecast=quality,
              forecast={"quality": "Q3", "h_norm": 0.4},
              package={"package_version": 1, "parameter_package_id": "pkg-1",
                       "calibration": "BOOTSTRAP_UNCALIBRATED"},
              lineage=tuple(f"obs-{i}" for i in range(len(ENGINE_SET))),
              s_i=s_i or {x: 1.0 for x in SCORED},
              q_i={x: 0.9 for x in SCORED})
    return evaluate_cell(**kw)


a = mk()
b_ = mk(atr=3.0, s_i={x: 0.2 for x in SCORED}, regime="RANGE")
print(f"  evaluation A: setup_id={a.to_setup_event()['setup_id']}")
print(f"                stop_loss={a.to_setup_event()['stop_loss']} "
      f"confidence={a.to_setup_event()['confidence']} "
      f"regime={a.to_setup_event()['regime']}")
print(f"  evaluation B: setup_id={b_.to_setup_event()['setup_id']}")
print(f"                stop_loss={b_.to_setup_event()['stop_loss']} "
      f"confidence={b_.to_setup_event()['confidence']} "
      f"regime={b_.to_setup_event()['regime']}")
print(f"  SAME setup_id for materially different setups? "
      f"{a.to_setup_event()['setup_id'] == b_.to_setup_event()['setup_id']}")
print(f"    A: atr=1.0 raw={a.raw:.4f} final={a.final_score:.4f} "
      f"risk_reference={a.risk_reference}")
print(f"    B: atr=3.0 raw={b_.raw:.4f} final={b_.final_score:.4f} "
      f"risk_reference={b_.risk_reference}")
c2 = db()
cols = list(_SETUP_COLUMNS)
print(f"  _SETUP_COLUMNS has {len(cols)} entries: {cols}")


def insert(ev, regime):
    vals = []
    for col in cols:
        v = ev.get(col)
        vals.append(v)
    c2.execute("INSERT OR IGNORE INTO setup_candidate (" + ",".join(cols)
               + ") VALUES (" + ",".join("?" * len(cols)) + ")", tuple(vals))
    c2.commit()


insert(a.to_setup_event(), "TREND")
insert(b_.to_setup_event(), "RANGE")
rows = c2.execute("SELECT setup_id, stop_loss, confidence, regime, quality "
                  "FROM setup_candidate").fetchall()
print(f"  after two INSERT OR IGNORE of DIFFERENT payloads sharing the id: "
      f"{len(rows)} row(s)")
for r in rows:
    print(f"    {r}")
print("  -> the second evaluation is silently discarded; no revision, no error.")

print()
print("=" * 78)
print("M-011  setup_candidate has no family_id column")
print("=" * 78)
sc = [r[1] for r in c2.execute("PRAGMA table_info(setup_candidate)")]
oc = [r[1] for r in c2.execute("PRAGMA table_info(outcome)")]
print(f"  setup_candidate columns ({len(sc)}): {sc}")
print(f"  family_id in setup_candidate? {'family_id' in sc}")
print(f"  outcome columns: {oc}")
print(f"  family_id in outcome? {'family_id' in oc}")
ev_a = a.to_setup_event()
print(f"  to_setup_event() keys: {sorted(ev_a)}")
print(f"  family_id value produced by the family: {ev_a.get('family_id')}")
print("  AD.1 says family_id is field 22, but the durable DDL stops at 21:")
c2.execute("INSERT INTO setup_candidate (setup_id,timestamp,symbol,timeframe,"
           "direction,confidence) VALUES ('x','t','s','1h','BULLISH',0.5)")
print(f"  rows stored with only 6 of 21 columns: "
      f"{c2.execute('SELECT count(*) FROM setup_candidate').fetchone()[0]}")
print("  -> family membership of a durable setup/outcome row cannot be")
print("     reconstructed from the store at all.")

print()
print("=" * 78)
print("M-012  SetupEvent.stop_loss is the sweep risk_reference, not the")
print("        protective stop the playbook actually sends")
print("=" * 78)
evb = a.to_setup_event()
print(f"  SetupEvent stop_loss   = {evb['stop_loss']}")
print(f"  SetupEvent take_profit = {evb.get('take_profit')!r}")
print(f"  SetupEvent risk_reward = {evb.get('risk_reward')!r}")
st = build_stops(direction=1, entry=100.0, atr=1.0, sweep_extreme=95.0,
                 fvg_low=96.0, fvg_high=99.0)
print(f"  build_stops(LONG)       -> stop={st['stop']} target={st['target']} "
      f"R={st['R']}")
print(f"  SetupEvent stop_loss == protective stop? "
      f"{evb['stop_loss'] == st['stop']}  (risk_reference is the sweep low)")
c3 = db()
c3.execute("INSERT INTO setup_candidate (setup_id,timestamp,symbol,timeframe,"
           "direction,stop_loss,take_profit,risk_reward,confidence) "
           "VALUES ('s1','t','BTCUSDT','1h','BULLISH',?,?,?,0.9)",
           (str(evb['stop_loss']), evb.get('take_profit'), evb.get('risk_reward')))
c3.commit()
print("  as persisted:", c3.execute("SELECT stop_loss,take_profit,risk_reward FROM setup_candidate").fetchall())
print(f"  the plan that was actually built carried stop={st['stop']} "
      f"target={st['target']} R={st['R']}")
print("  -> the durable setup row disagrees with the order's protective stop,")
print("     and take_profit / risk_reward stay NULL.")

print()
print("=" * 78)
print("M-013  evaluate_cell never calls mtf_gate; gate6 only sees the tier")
print("=" * 78)
src = _i.getsource(evaluate_cell)
print(f"  'mtf_gate' appears in evaluate_cell source? {'mtf_gate' in src}")
print("  gate6_mtf_sufficient source:")
print(_i.getsource(gates.gate6_mtf_sufficient))
print(f"  gate6_mtf_sufficient('ALIGNED')  -> "
      f"{gates.gate6_mtf_sufficient('ALIGNED')}")
print(f"  gate6_mtf_sufficient('ALIGNED', has_coarser_bars=False) -> "
      f"{gates.gate6_mtf_sufficient('ALIGNED', has_coarser_bars=False)}")
from apex.setup.family_sf_fvg_sweep_rev import relative_mtf, mtf_gate
print(f"  relative_mtf('1d') = {relative_mtf('1d')}  -> no coarser tier: "
      f"vacuous by law")
print(f"  mtf_gate(timeframe='1d', available_closes={{}}) -> "
      f"{mtf_gate(timeframe='1d', available_closes={})}")
print(f"  mtf_gate(timeframe='1h', available_closes={{}}) -> "
      f"{mtf_gate(timeframe='1h', available_closes={})}")
print(f"  1h fabricate the required bar to show the helper does work when the")
print(f"  family actually calls it:")
need = relative_mtf("1h")
closes = {t: 1000 for t in dict.fromkeys(
    (need["intermediate"], need["htf"])) if t}
print(f"    mtf_gate('1h', available_closes={closes}) -> "
      f"{mtf_gate(timeframe='1h', available_closes=closes)}")
print("  but evaluate_cell has no available_closes parameter at all:")
print("   ", _i.signature(evaluate_cell))
print(f"  and its own step 6 for 1d: {a.entry_logic_steps.get('6_mtf')}")
fab_d = fab_tf("1d")
kw = dict(symbol="BTCUSDT", timeframe="1d", as_of=1000, fabric=fab_d,
          bars=mkbars(), atr=1.0, direction=1,
          fvg_zones=[{"index": 24, "filled": False}],
          bos={"s_struct": 0.6, "direction": 1}, regime_state="TREND",
          q_forecast=0.6, forecast={"quality": "Q3", "h_norm": 0.4},
          package={"package_version": 1, "parameter_package_id": "pkg-1",
                   "calibration": "BOOTSTRAP_UNCALIBRATED"},
          lineage=tuple(f"obs-{i}" for i in range(len(ENGINE_SET))),
          s_i={x: 1.0 for x in SCORED}, q_i={x: 0.9 for x in SCORED})
ev1d = evaluate_cell(**kw)
print(f"  evaluate_cell(timeframe='1d', NO coarser bars supplied, no available_closes"
      f" argument) -> status={ev1d.status} reason={ev1d.reason}")
print(f"    step6 = {ev1d.entry_logic_steps.get('6_mtf')}")

print()
print("=" * 78)
print("M-014  gate10_forecast_quality accepts a bare self-declared label")
print("=" * 78)
print(f"  gates.gate10_forecast_quality({{'quality':'Q3'}}, environment='LIVE') "
      f"-> {gates.gate10_forecast_quality({'quality': 'Q3'}, environment='LIVE')}")
print(f"  gate10_forecast_quality({{}}, environment='LIVE') -> "
      f"{gates.gate10_forecast_quality({}, environment='LIVE')}")
print(f"  gate10_forecast_quality({{'quality':'Q3','bootstrap_prior':True}}, "
      f"environment='LIVE') -> "
      f"{gates.gate10_forecast_quality({'quality': 'Q3', 'bootstrap_prior': True}, environment='LIVE')}")
print(f"  gate10_forecast_quality({{'quality':'Q3'}}, environment='LIVE') -> "
      f"{gates.gate10_forecast_quality({'quality': 'Q3'}, environment='LIVE')}")
print("  fields the docstring calls the 'full P/U/C contract' and the fields")
print("  the body actually reads:")
print("   ", [ln.strip() for ln in _i.getsource(gates.gate10_forecast_quality).splitlines()
              if "forecast.get" in ln or '"quality"' in ln or "q_forecast" in ln][:6])
print("  an evidence/identity/calibration field is never consulted:",
      [k for k in ("snapshot_id", "lineage", "p_hat", "u", "c", "evidence",
                   "calibration", "package_version") if k not in
       __import__("inspect").getsource(gates.gate10_forecast_quality)])
print(_i.getsource(gates.gate10_forecast_quality)[:1100])

print()
print("=" * 78)
print("M-015  build_proposal(NO_TRADE).proposal_id raises")
print("=" * 78)
p = build_proposal(setup_id="s1", direction=NO_TRADE,
                   entry_logic_ref="PB-FVG-SWEEP-REV-A",
                   stop=None, targets=(), p_hat=0.0, u=0.0, c=0.0,
                   conflict_state="NONE", snapshot_id="a" * 64,
                   r_penalty=0.0, cost_unit=0.0)
print(f"  EU = {p.EU}")
try:
    print(f"  proposal_id -> {p.proposal_id}")
except Exception as e:
    print(f"  proposal_id -> {type(e).__name__}: {e}")
from apex.identity.canonical_json import canonical_json
try:
    canonical_json(p.to_dict())
    print("  canonical_json(p.to_dict()) -> OK")
except Exception as e:
    print(f"  canonical_json(p.to_dict()) -> {type(e).__name__}: {e}")
print("  the same call for a TRADE proposal:")
p2 = build_proposal(setup_id="s1", direction="LONG",
                    entry_logic_ref="PB-FVG-SWEEP-REV-A", stop=94.75,
                    targets=(115.75,), p_hat=0.6, u=0.4, c=0.01,
                    conflict_state="NONE", snapshot_id="a" * 64,
                    r_penalty=0.0, cost_unit=0.01, entry=100.0)
print(f"    proposal_id = {p2.proposal_id}")

print()
print("=" * 78)
print("M-016  generate_candidates mirrors one geometry onto BOTH sides;")
print("        units_of_r uses abs() so inverted geometry passes")
print("=" * 78)
setup = {"setup_id": "s1", "entry": 100.0, "stop": 97.0, "target": 109.0,
         "P": 0.6, "C": 0.01, "U_sum": 0.4, "cost_unit": 0.01,
         "r_penalty": 0.0}
cands = generate_candidates([setup])
for cd in cands:
    print(f"  side={cd['side']:5} RR={cd['RR']:.4f} R={cd['R']:.4f} "
          f"EU={cd['EU']:.4f}   (LONG wants stop<entry<target; "
          f"SHORT wants target<entry<stop)")
print(f"  -> a SHORT with stop 97 BELOW entry 100 and target 109 ABOVE entry "
      f"100 is ranked at full EU {cands[1]['EU']:.4f}")
print(f"  rank() order: {[c['side'] for c in rank(cands)]}")
p3 = build_proposal(setup_id="s1", direction="SHORT",
                    entry_logic_ref="PB-FVG-SWEEP-REV-A", stop=97.0,
                    targets=(109.0,), p_hat=0.6, u=0.4, c=0.01,
                    conflict_state="NONE", snapshot_id="a" * 64,
                    r_penalty=0.0, cost_unit=0.01, entry=100.0)
print(f"  build_proposal(direction='SHORT', stop=97 < entry=100 < target=109)")
print(f"    -> EU={p3.EU:.4f} sizing_request={p3.sizing_request}")
print(f"    direction={p3.direction!r} stop={p3.stop} targets={p3.targets}")
print(f"  units_of_r(entry=100, stop=97, target=109) = "
      f"{units_of_r(entry=100.0, stop=97.0, target=109.0)}")
print(f"  units_of_r(entry=100, stop=103, target=91) [a genuine SHORT] = "
      f"{units_of_r(entry=100.0, stop=103.0, target=91.0)}")
print("DONE M-009..M-016")
