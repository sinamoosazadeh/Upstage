from apex.engines.e04_volatility.engine import annualized_hv,realized_var
import math
r=[.01]*30; rv=realized_var(r)
print('RV=sum(r^2)=',rv)
print('annualized_hv(tf=1h,days=365)=',annualized_hv(rv,3600,365))
print('daily_contract_sqrt(RV*365)=',math.sqrt(rv*365))
print('ratio=',annualized_hv(rv,3600,365)/math.sqrt(rv*365))
print('result requires interpretation of whether RV is a single daily RV or intraday window RV')
