import asyncio
from types import SimpleNamespace
from scripts.run_apex import _noop_handler
from apex.telegram.control_plane import ControlPlane, AccessControl, validate_export_request
CFG=SimpleNamespace(telegram_owner_chat_id='',telegram_watchdog_chat_id='')
async def main():
    p=ControlPlane(config=CFG, access=AccessControl(owner_chat_ids=['123']))
    for name in ('EXPORT','BACKTEST_RUN'):
        p.register(name,_noop_handler(name))
        print(name,'dispatch=',await p.dispatch(name,{'run_id':'synthetic'}))
    v=validate_export_request(items=['Positions'],time_range='1h',environment='PAPER',fmt='CSV',path='/Download/APEX_Reports/report.csv')
    print('valid_export_request=',v['valid'])
asyncio.run(main())
