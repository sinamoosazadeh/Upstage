import asyncio
from types import SimpleNamespace
from apex.telegram.control_plane import ControlPlane,AccessControl,ControlPlaneError
from apex.telegram.gateway import TelegramGateway,UpdateSource
CFG=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id='')
class Source(UpdateSource):
 async def get_updates(self,**kw):
  return [{'update_id':10,'callback_query':{'id':'bad','from':{'id':123},'message':{'chat':{'id':123}},'data':'SCREEN:NOT_A_SCREEN'}},
          {'update_id':11,'message':{'chat':{'id':123},'text':'/myid','from':{'id':123}}}]
async def notify(*args): return {'sent':True}
async def main():
 cp=ControlPlane(config=CFG,access=AccessControl(owner_chat_ids=['123']))
 g=TelegramGateway(control=cp,source=Source(),notifier=notify)
 try: print('run_once=',await g.run_once())
 except ControlPlaneError as e: print('escaped=',e.reason,'handled=',g.handled,'poll_errors=',g.poll_errors,'offset=',g.offset)
asyncio.run(main())
