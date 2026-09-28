from types import SimpleNamespace
from apex.telegram.control_plane import ControlPlane, AccessControl
p=ControlPlane(config=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id=''),access=AccessControl())
print('without_store=',{k:p.screen_info()['sections'][k] for k in ('System Status','Data Coverage')})
