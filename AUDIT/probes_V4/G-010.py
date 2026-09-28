import asyncio
from types import SimpleNamespace
from apex.telegram.control_plane import ControlPlane, AccessControl
CFG=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id='')
async def main():
 cp=ControlPlane(config=CFG,access=AccessControl(owner_chat_ids=['123']),utc_now=lambda:'2026-01-01T00:00:00.000Z')
 start=await cp.handle_callback('123','EMERGENCY:L5')
 print('unconfirmed_level=',cp.ratchet.level,'safe_mode=',cp.safe_mode,'nonce=',start['nonce'])
 no=await cp.handle_callback('123','CONFIRM:'+start['nonce']+':NO:EMERGENCY_L5')
 lower=await cp.handle_callback('123','EMERGENCY:L1')
 print('NO=',no['authorized'],'level_after_NO=',cp.ratchet.level,'L1_ok=',lower['ok'],'reason=',lower.get('reason'))
asyncio.run(main())
