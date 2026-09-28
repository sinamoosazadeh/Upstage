import asyncio
from types import SimpleNamespace
from apex.telegram.control_plane import ControlPlane, AccessControl
from apex.ops.paper_loop import PaperRuntime
CFG=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id='')
async def ok(payload): return {'ok':True, 'synthetic':True}
async def main():
 cp=ControlPlane(config=CFG,access=AccessControl(owner_chat_ids=['123']),handlers={'EMERGENCY_PAUSE':ok})
 start=await cp.handle_callback('123','EMERGENCY:L1')
 confirmed=await cp.handle_callback('123','CONFIRM:'+start['nonce']+':YES:EMERGENCY_L1')
 before=(cp.ratchet.level,cp.paused,cp.new_positions_disabled,cp.safe_mode,cp.read_only)
 result=await cp.handle_callback('123','RECOVER')
 after=(cp.ratchet.level,cp.paused,cp.new_positions_disabled,cp.safe_mode,cp.read_only)
 runtime=object.__new__(PaperRuntime); runtime.control=cp
 print('confirmed=',confirmed['ok'],'before=',before,'recover=',result,'after=',after,'loop_paused=',runtime._control_paused())
asyncio.run(main())
