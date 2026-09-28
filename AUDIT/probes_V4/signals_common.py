"""Synthetic transport, synthetic config; never instantiate a live bot or read env."""
from types import SimpleNamespace
from apex.telegram.signaling import SignalingPlane, SignalMessage
from apex.bus import Priority
ISO='2026-01-01T00:00:00.000Z'
CHAT='12345'
CONFIG=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id='')
class Transport:
    def __init__(self, fail=0):
        self.calls=0
        self.fail=fail
    async def send_message(self, **kwargs):
        self.calls+=1
        if self.calls<=self.fail: raise OSError('INJECTED_TRANSPORT')
        return {'message_id':str(self.calls)}
    async def send_photo(self, **kwargs):
        return await self.send_message(**kwargs)
def plane(transport, clock=None, ledger=None):
    return SignalingPlane(config=CONFIG, transport=transport, owner_chat_id=CHAT,
        ledger=ledger, clock=clock, utc_now=lambda:ISO)
def message(i, priority=Priority.P3):
    return SignalMessage(signal_id='s'+str(i),chat_id=CHAT,text='test',
        timestamp_utc=ISO,priority=priority,snapshot_id='synthetic')
