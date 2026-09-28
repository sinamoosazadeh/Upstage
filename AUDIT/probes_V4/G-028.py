import asyncio
from signals_common import plane,message,Transport
class MissingReceipt(Transport):
 async def send_message(self,**kw):self.calls+=1;return {}
async def main():
 t=MissingReceipt();p=plane(t)
 r=await p.send(message('missing'))
 print('calls=',t.calls,'sent=',r.sent,'state=',r.state,'quality=',r.quality,'message_id=',r.message_id,'outbox=',p.outbox)
asyncio.run(main())
