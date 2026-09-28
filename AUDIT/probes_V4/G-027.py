import asyncio
from types import SimpleNamespace
from apex.telegram.control_plane import ControlPlane,AccessControl
CFG=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id='')
class FakeSignaling:
 owner_chat_id='123'
 def __init__(self): self.alerts=[]
 async def emit_alert(self,**kw): self.alerts.append(kw); return {'emitted':True}
async def effect(kw): return {'ok':True,'synthetic':True}
async def main():
 sig=FakeSignaling()
 cp=ControlPlane(config=CFG,access=AccessControl(owner_chat_ids=['123']),handlers={'EMERGENCY_PAUSE':effect},signaling=sig)
 n=await cp.handle_callback('123','EMERGENCY:L1')
 r=await cp.handle_callback('123',f"CONFIRM:{n['nonce']}:YES:EMERGENCY_L1")
 print('confirmed=',r['ok'],'alerts=',sig.alerts)
 from apex.telegram.signaling import ALERT_POLICY
 print('circuit_policy=',[x for x in ALERT_POLICY if x['alert']=='CIRCUIT_OPEN'])
asyncio.run(main())
