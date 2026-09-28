import asyncio
from types import SimpleNamespace
from apex.telegram.control_plane import ControlPlane,AccessControl
from apex.telegram.gateway import TelegramGateway
CFG=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id='')
sent=[]
async def notifier(*args): sent.append(args); return {'sent':True}
async def main():
 cp=ControlPlane(config=CFG,access=AccessControl(owner_chat_ids=['123']))
 g=TelegramGateway(control=cp,notifier=notifier)
 r=await g.handle_update({'update_id':1,'message':{'chat':{'id':'123','type':'private'},'from':{'id':'123'},'text':'/start'}})
 kb=cp.render('MAIN_MENU','123')['inline_keyboard']; print('gateway_route=',r['route'],'sent_arg_counts=',[len(x) for x in sent],'has_keyboard_argument=',any(len(x)>2 for x in sent))
 print('first_button=',kb[0][0],'back_button=',kb[-1][0]);
 for data in (kb[0][0]['callback_data'],kb[-1][0]['callback_data']):
  result=await cp.handle_callback('123',data)
  print('callback=',data,'result=',result)
asyncio.run(main())
