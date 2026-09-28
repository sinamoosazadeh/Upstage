import asyncio
from types import SimpleNamespace
from apex.telegram.control_plane import ControlPlane, AccessControl
CFG=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id='')
async def main():
 p=ControlPlane(config=CFG,access=AccessControl(owner_chat_ids=['123']))
 print('user_lock=',await p.handle_command('456','/lock'),'state=',p.locked)
 print('user_unlock=',await p.handle_command('456','/unlock'),'state=',p.locked)
 print('owner_unlock=',await p.handle_command('123','/unlock'),'state=',p.locked)
asyncio.run(main())
