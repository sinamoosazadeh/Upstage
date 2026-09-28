"""W.8 synthetic command/catch-up check with isolated temporary DB; no source network."""
import asyncio,tempfile
from pathlib import Path
from apex.config import Config
from apex.ops.bootstrap_service import BootstrapService
from scripts.run_apex import _bootstrap,_serve,_bootstrap_handler

class Source:
 def __init__(self): self.calls=[]
 def begin_catch_up(self,*args): self.calls.append(('begin',args))
 def __call__(self,*args):
  self.calls.append(('page',args[:2]))
  return {'code':0,'rows':[]}

async def main():
 cfg=object.__new__(Config)
 with tempfile.TemporaryDirectory(prefix='verify_v4_') as d:
  cfg._env={'APEX_ENV':'PAPER','APEX_SQLITE_PATH':str(Path(d)/'synthetic.sqlite3')}
  clock=[1000000.0]
  source=Source()
  s=BootstrapService(config=cfg,cells=[('BTCUSDT','1m')],source=source,now=lambda:clock[0])
  await s.open()
  try:
   handler=_bootstrap_handler(s)
   print('CLI bootstrap references gateway=', 'TelegramGateway' in _bootstrap.__code__.co_names, 'serve references gateway=', 'TelegramGateway' in _serve.__code__.co_names)
   print('start=',(await handler({'command':'start','chat_id':'synthetic-owner'}))['result']['accepted'])
   paused=await handler({'command':'pause','chat_id':'synthetic-owner'})
   print('pause accepted=',paused['result']['accepted'],'paused=',s.runner.state.paused)
   result=await s.catch_up(1735689600000)
   print('while paused catch_up cells_checked=',result['cells_checked'],'source_calls=',source.calls,'failures=',result['failures'])
   clock[0]+=25*3600
   resume=await handler({'command':'resume','chat_id':'synthetic-owner'})
   print('resume=',resume['result']['accepted'],'health_recheck=',resume['result']['health_recheck'],'paused=',s.runner.state.paused)
   stopped=await handler({'command':'stop','chat_id':'synthetic-owner'})
   print('stop accepted=',stopped['result']['accepted'],'stopped=',s.runner.state.stopped)
   source.calls.clear(); s._catch_up_boundary.clear()
   result=await s.catch_up(1735689660000)
   print('while stopped catch_up cells_checked=',result['cells_checked'],'source_calls=',source.calls,'failures=',result['failures'])
  finally: await s.close()
  s2=BootstrapService(config=cfg,cells=[('BTCUSDT','1m')],source=Source(),now=lambda:clock[0]);await s2.open()
  try: print('new service state stopped=',s2.runner.state.stopped,'paused=',s2.runner.state.paused)
  finally:await s2.close()
asyncio.run(main())
