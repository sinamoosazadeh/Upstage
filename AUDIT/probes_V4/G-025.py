import asyncio
from types import SimpleNamespace
from apex.telegram.control_plane import ControlPlane,AccessControl
from apex.telegram.gateway import TelegramGateway,AiogramUpdateSource
CFG=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id='',telegram_bot_token='')
class Bot:
 def __init__(self):self.acks=[];self.polls=0
 async def get_updates(self,**kw):
  self.polls+=1
  return [{'update_id':2,'callback_query':{'id':'callback-abc','from':{'id':123},'message':{'chat':{'id':123}},'data':'SCREEN:INFO'}}]
 async def answer_callback_query(self,**kw): self.acks.append(kw)
async def notify(*args):return {'sent':True}
async def main():
 bot=Bot();source=AiogramUpdateSource(config=CFG,bot=bot)
 p=ControlPlane(config=CFG,access=AccessControl(owner_chat_ids=['123']))
 g=TelegramGateway(control=p,source=source,notifier=notify)
 print('parsed=',await g.run_once(),'bot_polls=',bot.polls,'callback_ack_calls=',bot.acks,'handled=',g.handled[-1]['screen'])
asyncio.run(main())
