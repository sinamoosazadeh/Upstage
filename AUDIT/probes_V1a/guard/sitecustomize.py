"""Offline pytest guard, loaded only by explicit PYTHONPATH in audit commands."""
import atexit
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
blocked = []
def guard(event, args):
    if event in {'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo', 'socket.sendto'}:
        blocked.append(event)
        raise RuntimeError('AUDIT_NETWORK_FORBIDDEN')
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        p = Path(os.fsdecode(args[0])).resolve()
        if p.name == '.env' or p.name.startswith('.env.') or p.is_relative_to(ROOT / 'data'):
            blocked.append('forbidden-file')
            raise RuntimeError('AUDIT_SECRET_OR_DATA_ACCESS_FORBIDDEN')
sys.addaudithook(guard)
atexit.register(lambda: print('AUDIT_GUARD blocked_attempts=' + repr(blocked)))
