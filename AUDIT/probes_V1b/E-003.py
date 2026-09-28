"""Read-only synthetic probe: real FSM/adapter, in-memory fake venue; no network/DB."""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dataclasses import dataclass
from apex.execution.fsm import ExecutionFSM, build_trade_plan
from apex.execution.toobit_adapter import ToobitAdapter
from tests.fake_toobit_responder import FakeToobitResponder, TEST_API_KEY, TEST_API_SECRET

ISO="2026-01-01T00:00:00.000Z"
class C:
    allow_signed=True; apex_env="PAPER"
    toobit_api_key=TEST_API_KEY; toobit_api_secret=TEST_API_SECRET
@dataclass
class Proposal:
    proposal_id:str="p-1"; setup_id:str="s-1"; symbol:str="BTCUSDT"; timeframe:str="1h"; direction:str="LONG"; stop:float=99.; targets:tuple=(103.,); entry_logic_ref:str="x"; snapshot_id:str="sn-1"
    def to_dict(self): return self.__dict__

def plan():
    return build_trade_plan(proposal=Proposal(), adjudication={"decision":"ALLOW","sized_quantity":0.1,"vetoes_applied":[],"sizing":{"R_allowed":10},"snapshot_id":"sn-1"}, symbol="BTCUSDT",timeframe="1h",environment="PAPER",as_of=ISO,capital=10000,contract_multiplier=1,risk_state="LowRisk",package_version="4.0.0",created_utc=ISO)
async def main():
    venue=FakeToobitResponder(api_key=TEST_API_KEY,api_secret=TEST_API_SECRET)
    adapter=ToobitAdapter(config=C(),transport=venue,utc_now=lambda:ISO,clock=lambda:0)
    f=ExecutionFSM(intent_id="i-e003",adapter=adapter,utc_now=lambda:ISO,clock=lambda:0)
    submitted=await f.submit(plan(),price="100",quantity="0.1")
    await f.advance("FULL_FILL")
    venue.fail_next(-1022,1)
    result=await f.place_protection(stop_price="99",target_price="103")
    posts=venue.calls_to("/api/v1/futures/order","POST")
    print(json.dumps({"submit":submitted,"protection":result,"state":f.state,"post_count":len(posts),"post_kinds":[p.params.get("type") for p in posts],"venue_open_orders":venue.open_order_count(),"venue_position":venue.positions},default=str,sort_keys=True,indent=2))
asyncio.run(main())
