import asyncio
from signals_common import plane, Transport, message
class BrokenLedger:
    async def append(self, **kw): raise OSError('INJECTED_LEDGER')
async def main():
    t=Transport(); p=plane(t,ledger=BrokenLedger())
    try: await p.emit_alert(alert='STORAGE',metric='usage',threshold='80%',observed='81%')
    except OSError as e: print('ledger_fault=',e,'transport_calls=',t.calls,'audit_count=',len(p.alert_audit))
    q=plane(t)
    q.transport=lambda: (_ for _ in ()).throw(OSError('INJECTED_TRANSPORT_FACTORY'))
    try: await q.send(message(1))
    except OSError as e: print('factory_fault=',e,'outbox_count=',len(q.outbox))
asyncio.run(main())
