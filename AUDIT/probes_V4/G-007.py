import asyncio
from types import SimpleNamespace
from apex.telegram.control_plane import ControlPlane,AccessControl
from apex.telegram.gateway import TelegramGateway,extract_update
CFG=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id='')
calls=[]
async def effect(payload): calls.append(payload); return {'ok':True,'accepted':True}
async def notify(*args): return {'sent':True}
async def main():
 group='-1001234567890'; sender='987654321'
 cp=ControlPlane(config=CFG,access=AccessControl(owner_chat_ids=[group]),handlers={'BOOTSTRAP_CONTROL':effect})
 g=TelegramGateway(control=cp,notifier=notify)
 message={'update_id':1,'message':{'chat':{'id':int(group),'type':'supergroup'},'from':{'id':int(sender)},'text':'pause'}}
 callback={'update_id':2,'callback_query':{'id':'synthetic','from':{'id':int(sender)},'message':{'chat':{'id':int(group),'type':'supergroup'}},'data':'EMERGENCY:L1'}}
 print('extracted_message=',extract_update(message),'extracted_callback=',extract_update(callback))
 print('message_route=',await g.handle_update(message),'effect_count=',len(calls))
 print('callback_route=',await g.handle_update(callback),'level=',cp.ratchet.level)
asyncio.run(main())
