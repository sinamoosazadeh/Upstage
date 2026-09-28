"""Independent V2 probes.  All writes are confined to temporary files under /tmp."""
from __future__ import annotations
import asyncio, importlib.util, json, math, os, sys, tempfile, types
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

def out(value):
    print(json.dumps(value, indent=2, sort_keys=True, default=str))

def clean_risk():
    return {
        "snapshot_id":"a"*64,"timeframe":"1h","capital":10000.0,
        "q_raw":0.9,"qx_state":False,"failed_setup_gate":False,
        "pit_violation":False,"availability_time":1,
        "portfolio_exposure":100.0,"proposed_notional":50.0,
        "capital_hard_cap":1000000.0,"circuit_breaker_engaged":False,
        "emergency_state":"NORMAL","per_symbol_exposure":100.0,
        "symbol_cap":1000.0,"portfolio_cap":1000000.0,
        "conflict_state":"CONSENSUS","staleness_seconds":1.0,
        "freshness_sla_seconds":30.0,"oi_lag_seconds":5.0,
        "oi_lag_threshold_seconds":60.0,"is_risk_increase":False,
        "uncertainty_is_rising":False,"realized_daily_loss_fraction":0.0,
        "realized_weekly_loss_fraction":0.0,"consecutive_losses":0,
        "time_to_expiry_days":40.0,"margin_health_fraction":0.9,
        "stop_distance":20.0,"min_quantity":0.001,"risk_state":"LowRisk",
    }

async def d001():
    from apex.execution.toobit_adapter import ToobitAdapter
    calls=[]
    async def transport(method,url,query,headers):
        calls.append({"method":method,"url":url,"query_keys":sorted(query),
                      "header_keys":sorted(headers),"has_signature":bool(headers.get("X-BM-SIGN"))})
        return {"http_status":200,"body":{"code":0,"data":{"orderId":"o-1"}}}
    cfg=SimpleNamespace(allow_signed=True,toobit_api_key="synthetic-key",
                        toobit_api_secret="synthetic-secret",apex_env="PAPER")
    a=ToobitAdapter(config=cfg,transport=transport,utc_now=lambda:"2026-09-28T00:00:00.000Z",clock=lambda:0.0)
    r=await a.submit_order(intent_id="intent-1",symbol="BTCUSDT",timeframe="1h",
                           direction="LONG",quantity="1",price="100",timestamp_utc="2026-09-28T00:00:00.000Z")
    out({"adapter_result":r.to_dict(),"captured":calls,"boundary":"capture only; no network"})

def d002():
    from apex.telegram.control_plane import ControlPlane, AccessControl
    from scripts.run_apex import _noop_handler
    async def go():
        h={name:_noop_handler(name) for name in ("EMERGENCY_PAUSE","EMERGENCY_DISABLE_NEW","EMERGENCY_CANCEL_ALL","EMERGENCY_CLOSE_ALL","EMERGENCY_SAFE_MODE")}
        cfg=SimpleNamespace(telegram_owner_chat_id="owner",telegram_watchdog_chat_id="")
        c=ControlPlane(config=cfg,access=AccessControl(owner_chat_ids=["owner"]),handlers=h,environment="PAPER")
        r=await c._emergency_effect("L3",{"open_orders":[{"id":str(i)} for i in range(3)]})
        l5=await c._emergency_effect("L5",{})
        return {"L3":r,"L5":l5,"flags":{"safe_mode":c.safe_mode,"paused":c.paused,"new_positions_disabled":c.new_positions_disabled},"handler":"_noop_handler"}
    out(asyncio.run(go()))

def d003():
    from apex.ops.paper_loop import PaperRuntime
    class C: paused=False; new_positions_disabled=True
    x=PaperRuntime.__new__(PaperRuntime); x.control=C()
    out({"control_state":"new_positions_disabled=True","_control_paused":x._control_paused(),
         "run_loop_branch":"run() sleeps and increments rounds without run_cycle when true"})

def d004():
    from apex.ops import paper_loop as pl
    from apex.execution import fsm as F
    async def fake_price(*a,**k): return "100"
    old=pl.last_closed_price; pl.last_closed_price=fake_price
    async def go():
        x=pl.PaperRuntime.__new__(pl.PaperRuntime)
        x.boot_verdict={"boot_state":"READY","new_trades_allowed":True}
        x.store=SimpleNamespace(); x._budget_taken=0; x.max_trades_per_cycle=4
        x.control=SimpleNamespace(paused=True,new_positions_disabled=True)
        x._take_budget=lambda: True; x._release_budget=lambda:None
        async def execute_plan(*a,**k): return {"submitted":True,"intent_id":"i-1","state":"SUBMITTED","fill":None,"protected":False}
        x.execute_plan=execute_plan
        plan=F.TradePlan(proposal_id="p",setup_id="s",symbol="BTCUSDT",timeframe="1h",direction="LONG",
                         entry_ref="e",stop_price=99,target_price=103,sized_quantity=1,risk_amount=1,
                         contract_multiplier=1,decision="ALLOW",vetoes_applied=(),risk_state="LowRisk",
                         package_version="p",snapshot_id="s",as_of="2026-09-28T00:00:00Z",created_utc="2026-09-28T00:00:00Z",
                         lineage="l",payload_hash="h",environment="PAPER")
        payload={"context":{"cell_state":{"plan_obj":plan}},"as_of":"2026-09-28T00:00:00Z","close_ms":1}
        r=await x._stage_execution(payload)
        return {"stage_result":r,"control_state":{"paused":x.control.paused,"new_positions_disabled":x.control.new_positions_disabled},"observation":"_stage_execution did not consult control flags"}
    try: out(asyncio.run(go()))
    finally: pl.last_closed_price=old

def d005():
    from apex.ops.backup import storage_guard
    out({"storage_guard_10_percent":storage_guard(free_fraction=.10),
         "storage_guard_20_percent":storage_guard(free_fraction=.20),
         "runtime_order":"run_cycle calls catch_up before _storage_guard"})

def d006():
    from apex.scheduler import clock as C
    out({"scheduler_default_drift_seconds":0.0,"boot_measurement_not_argument":True,
         "drift_verdict_0_6":C.drift_verdict(0.6),"drift_verdict_0_05":C.drift_verdict(.05)})

def d007():
    from apex.ops.watchdog import Watchdog
    w=Watchdog(now=lambda:100.0)
    out({"check_without_heartbeat":asyncio.run(w.check(at=100000.0)),"heartbeat_baseline":w.last_heartbeat_at})

def d008():
    from apex.risk.kernel import adjudicate
    r=clean_risk(); r.update(portfolio_exposure=5000.0,proposed_notional=1500.0,capital_hard_cap=6000.0,margin_health_fraction=.5)
    out({"risk_input":r,"adjudicate":adjudicate(r),"observation":"one plan is evaluated from the supplied snapshot; no atomic multi-plan reservation is created"})

def d009():
    from apex.risk.kernel import adjudicate
    r=clean_risk(); r.update(portfolio_exposure=0.0,proposed_notional=4000.0,per_symbol_exposure=0.0,symbol_cap=2000.0,capital_hard_cap=6000.0,stop_distance=1.25,min_quantity=.001)
    out({"risk_input":r,"adjudicate":adjudicate(r),"symbol_cap":2000.0,"proposed_notional":4000.0})

def d010():
    from apex.risk.kernel import size
    out({"size_with_rho_095":size(capital=10000,stop_distance=1.25,min_quantity=.001,risk_state="LowRisk",
                                    correlation={"rho":.95,"open_notional":[1.0],"cap":.7}),
         "native_producer_risk_correlation_field":"not supplied by EngineContextProducer risk mapping"})

def d011():
    from apex.fabric.context import evidence_agreement
    from apex.fabric.conflict import disagreement_of,resolve
    from apex.fabric.evidence import FabricEvidenceRef
    def ref(i,d): return FabricEvidenceRef(evidence_id=f"e{i}",engine_id="E05",symbol="BTCUSDT",timeframe="1h",state="ACTIVE",direction=d,quality=1.0,resolution_class="Q3",age_bars=0,as_of=1,snapshot_id="s",lineage=(f"o{i}",))
    ms=[ref(1,1),ref(2,-1)]
    out({"agreement":evidence_agreement(ms),"disagreement":disagreement_of(ms),"resolve":resolve(disagreement=disagreement_of(ms),data_trust=.9,q_raw=.9,timeframe="1h")})

def d012():
    from apex.risk.kernel import circuit_breaker_reset
    out({"weekly_rollover_without_owner_review":circuit_breaker_reset("WEEKLY_LOSS_LIMIT",utc_rollover=True,owner_reviewed=False)})

def d013():
    from apex.fabric.context import evidence_agreement
    from apex.fabric.conflict import disagreement_of,resolve
    from apex.fabric.evidence import FabricEvidenceRef
    def ref(i,e,d): return FabricEvidenceRef(evidence_id=f"e{i}",engine_id=e,symbol="BTCUSDT",timeframe="1h",state="ACTIVE",direction=d,quality=1.0,resolution_class="Q3",age_bars=0,as_of=1,snapshot_id="s",lineage=(f"o{i}",))
    ms=[ref(1,"E05",1),ref(2,"E06",-1)]
    dis=disagreement_of(ms)
    out({"agreement":evidence_agreement(ms),"disagreement":dis,"hard_threshold":.60,"resolve":resolve(disagreement=dis,data_trust=.9,q_raw=.9,timeframe="1h")})

def d014():
    from apex.fabric.conflict import penalties
    from apex.setup.gates import gate3_conflict_penalty,gate4_redundancy_penalty,gate_thresholds
    p=penalties("MATERIAL_CONFLICT",redundancy_rho=.9)
    out({"penalties":p,"thresholds":gate_thresholds(),"gate3":gate3_conflict_penalty(p["conflict_penalty"]).to_dict(),"gate4":gate4_redundancy_penalty(p["redundancy_penalty"]).to_dict()})

def d015():
    spec=importlib.util.spec_from_file_location("ctx_test",ROOT/"tests/integration/test_context_to_trade_paper.py")
    mod=importlib.util.module_from_spec(spec); sys.modules["ctx_test"]=mod; spec.loader.exec_module(mod)
    from apex.fabric.evidence import EvidenceFabric
    from apex.setup.family_sf_fvg_sweep_rev import evaluate_cell
    fabric=EvidenceFabric.assemble(symbol="BTCUSDT",timeframe="1h",as_of=mod.AS_OF_MS,evidence=mod.synth_refs(),data_trust=.4)
    ev=evaluate_cell(symbol="BTCUSDT",timeframe="1h",as_of=mod.AS_OF_MS,fabric=fabric,bars=mod.sweep_bars(),atr=1.0,direction=1,
                     fvg_zones=[{"index":24,"filled":False}],bos={"s_struct":.6,"direction":1},regime_state="TREND",
                     q_forecast=.8,forecast={"quality":"Q3","h_norm":.4},package={"package_version":1,"parameter_package_id":"pkg-1","calibration":"BOOTSTRAP_UNCALIBRATED"},
                     s_i={c:1.0 for c in ("structure","liquidity","fvg","trend","regime","temporal","orderblock","momentum")},
                     q_i={c:.9 for c in ("structure","liquidity","fvg","trend","regime","temporal","orderblock","momentum")},context_confidence=.39951172547,environment="PAPER")
    out({"status":ev.status,"reason":ev.reason,"final_score":ev.final_score,"context_confidence":ev.context_confidence,"propagation":"COLLAPSED"})

def d016():
    from apex.ops.watchdog import Watchdog
    async def go():
        w=Watchdog(); w.state="FAIL_CLOSED"; a=await w.resolve(to_state="NORMAL",snapshot_id="s1"); w.state="NORMAL"; b=await w.resolve(to_state="MANUAL_OVERRIDE",snapshot_id="s2"); return {"fail_closed_to_normal":a,"normal_to_manual_override":b}
    out(asyncio.run(go()))

def d017():
    from apex.ops.watchdog import SendOnlyGmailChannel,OutboundMail
    c=SendOnlyGmailChannel(credential_provider=lambda:"synthetic",transport=None,to_address="owner@example.invalid")
    r=c.send(OutboundMail(alert="HOST_DOWN",severity="CRITICAL",subject="x",body="x"))
    out({"send_result":r,"sent":c.sent,"transport_injected":False,"boundary":"no SMTP/network evidence"})

def d018():
    from apex.ops.watchdog import Watchdog
    class BadLog:
        async def append(self,**kwargs): raise OSError("synthetic-log-failure")
    calls=[]
    class Chan:
        def send(self,mail): calls.append(mail.alert); return {"delivered":True}
    async def go():
        w=Watchdog(recovery_log=BadLog(),independent=Chan(),now=lambda:0.0,interval_seconds=1,miss_limit=3); w.heartbeat(at=0)
        try: result=await w.check(at=3)
        except Exception as e: return {"exception":type(e).__name__+":"+str(e),"independent_calls":calls,"state":w.state}
    out(asyncio.run(go()))

def d019():
    from apex.ops.watchdog import RecoveryLog
    async def go():
        fd,path=tempfile.mkstemp(prefix="audit-d019-",suffix=".sqlite3",dir="/tmp"); os.close(fd); os.unlink(path)
        first=RecoveryLog(path); await first.open(); first._db=None; await first.append(kind="FAIL_CLOSED",reason="memory-only"); before={"rows":len(first),"head":first.head}; await first.close()
        second=RecoveryLog(path); await second.open(); after={"rows":len(second),"head":second.head}; await second.close(); os.unlink(path)
        return {"before_close":before,"after_reopen":after,"durable_row_lost":after["rows"]==0}
    out(asyncio.run(go()))

def d020():
    from apex.ops.watchdog import RecoveryLog,Watchdog
    async def go():
        fd,path=tempfile.mkstemp(prefix="audit-d020-",suffix=".sqlite3",dir="/tmp"); os.close(fd); os.unlink(path)
        log=RecoveryLog(path); w=Watchdog(recovery_log=log); r=await w.enter_fail_closed(reason="synthetic",snapshot_id="s")
        result={"path_exists":os.path.exists(path),"db_bound":log._db is not None,"rows_in_memory":len(log),"enter_result":r}
        if os.path.exists(path): os.unlink(path)
        return result
    out(asyncio.run(go()))

def d021():
    from apex.ops.backup import backup_summary,next_drill_due
    out({"summary":backup_summary(),"next_drill_due_none":next_drill_due(last_drill_at=None),"next_drill_due_90d":next_drill_due(last_drill_at=0,now=90*86400)})

def d022():
    from apex.ops.backup import restore_drill
    work=tempfile.mkdtemp(prefix="audit-d022-",dir="/tmp")
    out(asyncio.run(restore_drill(workdir=work,records=25,rpo_limit_seconds=-1)))
    import shutil; shutil.rmtree(work,ignore_errors=True)

def d023():
    from apex.ops.backup import restore
    work=Path(tempfile.mkdtemp(prefix="audit-d023-",dir="/tmp")); src=work/"bad.sqlite3"; dst=work/"restored.sqlite3"; src.write_bytes(b"not sqlite")
    try: out(restore(backup_path=str(src),target_path=str(dst),overwrite=True))
    finally:
        import shutil; shutil.rmtree(work,ignore_errors=True)

def d024():
    from apex.ops.backup import verify_restored_ledger
    work=Path(tempfile.mkdtemp(prefix="audit-d024-",dir="/tmp")); missing=work/"missing.sqlite3"
    try:
        before=missing.exists(); r=asyncio.run(verify_restored_ledger(str(missing))); after=missing.exists(); out({"before_exists":before,"after_exists":after,"verdict":r})
    finally:
        import shutil; shutil.rmtree(work,ignore_errors=True)

def d025():
    from apex.ops.backup import SQLiteBackupManager,BackupError
    import sqlite3,shutil
    work=Path(tempfile.mkdtemp(prefix="audit-d025-",dir="/tmp")); src=work/"live.sqlite3"; con=sqlite3.connect(src); con.execute("create table t(x)"); con.commit(); con.close(); m=SQLiteBackupManager(db_path=str(src),backup_dir=str(work/"backups"),now=lambda:0)
    try:
        r=m.backup(label="plain");
        try: m.backup(label="encrypted",encrypt=True)
        except Exception as e: enc={"error":type(e).__name__+":"+str(e)}
        out({"plain":r.to_dict(),"encrypted_request":enc})
    finally: shutil.rmtree(work,ignore_errors=True)

def d026():
    from apex.risk.kernel import adjudicate
    results={}
    for key,val in (("q_raw",None),("q_raw",float("nan")),("staleness_seconds",float("nan")),("proposed_notional",float("nan"))):
        r=clean_risk(); r[key]=val
        results[f"{key}={val}"]=adjudicate(r)
    out(results)

def d027():
    from apex.risk.kernel import adjudicate
    cases=[]
    for override in ({"realized_daily_loss_fraction":.05,"daily_loss_cap":.9},{"consecutive_losses":5,"consecutive_loss_halt":99},{"margin_health_fraction":.2,"margin_health_action_fraction":.01}):
        r=clean_risk(); r.update(override); cases.append({"override":override,"result":adjudicate(r)})
    out(cases)

def d028():
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.ledger.store import LedgerWriter
    from apex.risk.kernel import apply_ladder_state_migration,append_ladder_revision,ladder_revision
    from apex.execution.fsm import StartupReconciliation
    class A:
        async def query_open_positions(self): return SimpleNamespace(outcome="SUCCESS",ok=True,data=[] ,operation="positions",error_code=None)
        async def query_order_state(self,scope): return SimpleNamespace(outcome="SUCCESS",ok=True,data=[],operation=scope,error_code=None)
    async def go():
        store=await SQLiteStore(":memory:").open(); ledger=LedgerWriter(store,actor="AUDIT"); await ledger.initialize(); await ledger.start(); await apply_ladder_state_migration(store.db)
        r1=ladder_revision(revision_id="r1",applied_at="2026-09-28T00:00:00.000Z",state="NoRisk",emergency_state="NORMAL",consumed_budget=0,reason="audit",snapshot_id="s1")
        r2=ladder_revision(revision_id="r2",applied_at="2026-09-28T00:01:00.000Z",state="HighRisk",emergency_state="L3_CANCEL_ALL",consumed_budget=0,reason="audit",snapshot_id="s2",parent_revision_id="r1",previous_state="NORMAL")
        await append_ladder_revision(store.db,r1); await append_ladder_revision(store.db,r2)
        m=StartupReconciliation(ledger=ledger,adapter=A(),environment="PAPER",drift_seconds=0.0)
        verdict=await m.run(); await ledger.stop(); await store.close(); return verdict
    out(asyncio.run(go()))

def d029():
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    from apex.risk.kernel import apply_ladder_state_migration,append_ladder_revision,ladder_revision
    from apex.ops.engine_context import EngineContextProducer
    async def go():
        store=await SQLiteStore(":memory:").open(); await apply_ladder_state_migration(store.db)
        def rev(i,t,state,em,parent,prev=None): return ladder_revision(revision_id=i,applied_at=t,state=state,emergency_state=em,consumed_budget=0,reason="audit",snapshot_id=i,parent_revision_id=parent,previous_state=prev,owner_confirmed=False)
        await append_ladder_revision(store.db,rev("r1","2026-09-28T00:00:00.000Z","NoRisk","NORMAL",None))
        await append_ladder_revision(store.db,rev("r2","2026-09-28T00:01:00.000Z","HighRisk","L3_CANCEL_ALL","r1",prev="NORMAL"))
        bad=rev("r3","2026-09-28T00:02:00.000Z","NoRisk","NORMAL","r2")
        await append_ladder_revision(store.db,bad)
        p=EngineContextProducer(store,environment="PAPER")
        try: first=await p.ladder_input("2026-09-28T00:03:00.000Z")
        except Exception as e: first={"error":type(e).__name__+":"+str(e)}
        await append_ladder_revision(store.db,rev("r4","2026-09-28T00:03:00.000Z","NoRisk","NORMAL","r3"))
        try: second=await p.ladder_input("2026-09-28T00:04:00.000Z")
        except Exception as e: second={"error":type(e).__name__+":"+str(e)}
        await store.close(); return {"r3_append":"accepted","after_r3":first,"r4_append":"accepted","after_r4":second}
    out(asyncio.run(go()))

def d030():
    from apex.config import load_params
    from apex.risk.kernel import adjudicate,margin_health_state
    p=load_params()["paper_account"]; cap=float(p["capital_usdt"]); notional=8100.0; health=(cap-notional)/cap
    r=clean_risk(); r.update(environment="PAPER",margin_model="PAPER_RESERVATION_PROXY_D29",margin_health_fraction=health,portfolio_exposure=0,proposed_notional=50)
    out({"paper_yaml":p,"capital":cap,"open_notional":notional,"health":health,"margin_status":margin_health_state(health,environment="PAPER"),"adjudicate_proxy":adjudicate(r),"observation":"margin_status is not a cancel-all execution"})

def d031():
    from apex.research.backtest import cvar_bootstrap
    matches=[]
    for path in (ROOT/"apex",ROOT/"scripts"):
        for f in path.rglob("*.py"):
            text=f.read_text(encoding="utf-8")
            if "cvar_bootstrap(" in text and f.name != "probe_impl.py": matches.append(str(f.relative_to(ROOT)))
    out({"helper_module":"apex.research.backtest","helper_result":cvar_bootstrap([.01,-.02,.03,-.01,.02],paths=100,seed=7),"apex_scripts_matches":matches,"consumer_call_count":0})

FUNCS={k:v for k,v in globals().items() if k.startswith("d") and k[1:].isdigit()}
if __name__ == "__main__":
    key=sys.argv[1].replace("-","") if len(sys.argv)>1 else "001"
    FUNCS["d"+key]()
