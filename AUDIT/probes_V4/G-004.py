import asyncio
from types import SimpleNamespace
from apex.telegram.gateway import TelegramGateway
from apex.telegram.control_plane import ControlPlane, AccessControl
from apex.ops.bootstrap_service import BootstrapService, SignalingNotifier
CFG=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id='')
async def false_notifier(*args): return {'sent': False, 'reason':'INJECTED_FAILURE'}
async def main():
 p=ControlPlane(config=CFG,access=AccessControl())
 g=TelegramGateway(control=p,notifier=false_notifier)
 print('gateway=',await g.reply('123','synthetic'))
 s=object.__new__(BootstrapService); s._notifier=false_notifier; s.notifications=[]
 print('bootstrap_report=',await s.report('synthetic'))
 plane=SimpleNamespace(send=lambda msg: async_false_result())
 n=SignalingNotifier(plane,chat_id='123',utc_now=lambda:'2026-01-01T00:00:00.000Z')
 print('real_notifier=',await n('synthetic'))
async def async_false_result(): return SimpleNamespace(sent=False,state='INVALIDATED',reason='INJECTED_FAILURE')
asyncio.run(main())
