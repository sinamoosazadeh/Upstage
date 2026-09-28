"""Composition-only synthetic bus event; no order, network or repository DB."""
import asyncio,tempfile
from pathlib import Path
from apex.config import Config
from apex.bus import make_event,Priority
from scripts.run_apex import Runtime
from signals_common import Transport, CONFIG, CHAT, ISO
from apex.telegram.signaling import SignalingPlane
async def main():
 cfg=object.__new__(Config);cfg._env={'APEX_ENV':'PAPER','APEX_SQLITE_PATH':'unused-synthetic'}
 with tempfile.TemporaryDirectory(prefix='verify_v4_') as d:
  rt=await Runtime(cfg,path=str(Path(d)/'tmp.sqlite3')).start()
  try:
   transport=Transport()
   s=SignalingPlane(config=CONFIG, transport=transport, owner_chat_id=CHAT,
                    bus=rt.bus, utc_now=lambda:ISO)
   print('subscriptions=',{k:len(v) for k,v in rt.bus._subscribers.items()})
   await rt.bus.publish(make_event(Priority.P0,'execution.fsm.transition',{'state':'RECOVERY_REQUIRED','synthetic':True}))
   await rt.bus.publish(make_event(Priority.P0,'risk.veto',{'veto':10,'synthetic':True}))
   print('collected=',[(x.topic,x.payload) for x in rt.events],'alert_audit=',s.alert_audit,'transport_calls=',transport.calls)
  finally: await rt.stop()
asyncio.run(main())
