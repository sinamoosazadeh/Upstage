import asyncio
from types import SimpleNamespace
from apex.telegram.control_plane import AccessControl, ControlPlane
from apex.ops.paper_loop import PaperRuntime

async def main():
    cp = ControlPlane(access=AccessControl(owner_chat_ids=['1']), config=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id=''))
    result = await cp.handle_command('1', '/lock')
    print('command=', result['command'], 'ok=', result['ok'], 'locked=', cp.locked)
    print('flags=', {x: getattr(cp, x) for x in ('paused','new_positions_disabled','read_only','safe_mode')})
    loop = object.__new__(PaperRuntime)
    loop.control = cp
    print('paper_loop_paused=', loop._control_paused())
    print('locked_verdict_OTHER=', cp.locked_verdict('OTHER'))
    cp2 = ControlPlane(access=AccessControl(owner_chat_ids=['1']), config=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id=''))
    print('new_instance_locked=', cp2.locked)
asyncio.run(main())
