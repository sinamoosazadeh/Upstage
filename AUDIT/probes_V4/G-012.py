import asyncio
from types import SimpleNamespace
from apex.telegram.control_plane import ControlPlane, AccessControl
CFG=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id='')
async def ok(payload): return {'ok': True, 'synthetic': True}
def state(c): return {'locked':c.locked,'level':c.ratchet.level,'paused':c.paused,'new_positions_disabled':c.new_positions_disabled,'safe_mode':c.safe_mode,'read_only':c.read_only}
async def main():
 a=ControlPlane(config=CFG,access=AccessControl(owner_chat_ids=['123']),handlers={'EMERGENCY_SAFE_MODE':ok})
 n=await a.handle_callback('123','EMERGENCY:L5')
 confirm=await a.handle_callback('123',f"CONFIRM:{n['nonce']}:YES:EMERGENCY_L5")
 await a.handle_command('123','/lock')
 b=ControlPlane(config=CFG,access=AccessControl(owner_chat_ids=['123']))
 print('confirmed=',confirm['ok'],'old=',state(a),'recreated=',state(b))
asyncio.run(main())
