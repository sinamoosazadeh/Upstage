import asyncio
from types import SimpleNamespace
from apex.telegram.control_plane import ControlPlane,AccessControl
from apex.telegram.gateway import TelegramGateway,UpdateSource
CFG=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id='')
calls=[]
async def handler(payload): calls.append(payload['command']); return {'ok':True,'accepted':True}
async def notify(chat,text): return {'sent':True}
class Source(UpdateSource):
 async def get_updates(self,**kwargs): return [{'update_id':91,'message':{'chat':{'id':'123','type':'private'},'from':{'id':'123'},'text':'pause'}}]
async def one():
 cp=ControlPlane(config=CFG,access=AccessControl(owner_chat_ids=['123']),handlers={'BOOTSTRAP_CONTROL':handler})
 g=TelegramGateway(control=cp,source=Source(),notifier=notify)
 result=await g.run_once()
 return result,cp,g
async def main():
 a,cp,g=await one();b,cp2,g2=await one()
 print('first=',a,'second_fresh=',b,'handler_calls=',calls,'old_offset=',g.offset,'new_offset=',g2.offset)
asyncio.run(main())
