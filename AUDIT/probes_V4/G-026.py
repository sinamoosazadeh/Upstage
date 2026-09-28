import asyncio
from signals_common import plane,Transport,CHAT,message
from scripts.run_apex import _telegram_reply
from apex.telegram.signaling import SignalMessage
async def main():
 p=plane(Transport())
 result=await _telegram_reply(p)(CHAT,'synthetic operator response')
 row=p.outbox[-1]
 print('reply_result=',result,'outbox=',row,'outbox_has_snapshot=', 'snapshot_id' in row,'has_text=', 'text' in row,'has_lineage=', 'lineage' in row)
 print('SignalMessage_fields=',list(SignalMessage.__dataclass_fields__),'default_snapshot=',repr(SignalMessage(signal_id='x',chat_id=CHAT,text='x').snapshot_id))
asyncio.run(main())
