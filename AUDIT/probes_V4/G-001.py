"""Synthetic configuration only; bypass __init__ so no environment/.env read."""
from apex.config import Config
from scripts.run_apex import _redacted
import json
cfg=object.__new__(Config)
cfg._env={'TELEGRAM_OWNER_CHAT_ID':'111222333444','TELEGRAM_WATCHDOG_CHAT_ID':'555666777888',
          'TOOBIT_API_KEY':'synthetic-not-a-key','TELEGRAM_BOT_TOKEN':'synthetic-not-a-token'}
r=repr(cfg); boot=json.dumps(_redacted(cfg),sort_keys=True)
for name,value in [('owner','111222333444'),('watchdog','555666777888'),('bot','synthetic-not-a-token')]:
 print(name,'repr_contains=',value in r,'boot_contains=',value in boot)
print('repr=',r)
print('boot_surface=',boot)
