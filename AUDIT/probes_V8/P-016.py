from common import stable_bars
from apex.engines.e04_volatility.engine import run_engine,E04VolatilityEngine
xs=stable_bars(55); r=run_engine(xs,timeframe='1h'); e=r['engine']; state=r['states'][-1]
public=E04VolatilityEngine()._to_evidence(state,'BTCUSDT','1h',1.0)
print('validated_bars=55; garch_status=',e.garch_state.get('status'))
print('state_garch_equals_ewma=',state.garch_vol==state.ewma_vol,'fields_has_garch_status=',hasattr(state,'garch_status'))
print('evidence_validity=',public.validity,'resolution=',public.resolution_class,'explanation=',public.explanation)
