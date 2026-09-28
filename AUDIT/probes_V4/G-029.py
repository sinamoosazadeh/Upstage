import asyncio
from apex.telegram.signaling import format_markdown_v2,format_caption,SignalMessage
from signals_common import plane,Transport,CHAT,ISO
class Capture(Transport):
 async def send_photo(self,**kw):
  self.args=kw;self.calls+=1;return {'message_id':'101'}
async def main():
 m=format_markdown_v2('x'*4095+'.')
 print('text_length=',len(m['text']),'truncated=',m['truncated'],'trailing_backslash=',m['text'].endswith('\\'),'tail_repr=',repr(m['text'][-5:]))
 cap=format_caption('[BTC] +1.5%');print('caption_formatted=',repr(cap['caption']))
 t=Capture();p=plane(t)
 r=await p.send(SignalMessage(signal_id='caption',chat_id=CHAT,text='synthetic',image=b'fake-image-bytes',caption='[BTC] +1.5%',timestamp_utc=ISO))
 print('sent=',r.sent,'photo_caption=',repr(t.args['caption']),'parse_mode=',t.args['parse_mode'])
asyncio.run(main())
