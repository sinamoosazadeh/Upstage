import asyncio
from signals_common import plane, Transport
async def main():
    t=Transport(fail=3); p=plane(t)
    kw=dict(alert='STORAGE',metric='usage',threshold='80%',observed='81%',snapshot_id='synthetic')
    a=await p.emit_alert(**kw)
    print('first=',a['emitted'],a['reason'],'transport_calls=',t.calls)
    b=await p.emit_alert(**kw)
    print('second=',b['emitted'],b['reason'],'transport_calls=',t.calls)
asyncio.run(main())
