from common import obs
from apex.engines.e04_volatility.engine import VolatilityEngineV4
from apex.data_catalog.contracts import validate_market_observation
base=VolatilityEngineV4()
# Validate 20 baseline unit ranges and the 100-point outlier as closed observations.
for i in range(21):
    if i<20: validate_market_observation(obs(i,open_=100,close=100.5,high=101,low=100,volume=10))
    else: validate_market_observation(obs(i,open_=100,close=199,high=200,low=100,volume=10))
base.trs=[1.0]*20
print('validated_TR_history_n=20; raw_outlier_TR=100; _winsorize_tr=',base._winsorize_tr(100.0))
