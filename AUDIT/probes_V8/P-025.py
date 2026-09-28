from common import bar
from apex.engines.e06_orderblock.engine import OrderBlockEngine,get_params
class Spy(OrderBlockEngine):
 def __init__(self,*a,**k): super().__init__(*a,**k); self.updated=[]
 def update_with_bar(self,i): self.updated.append(i); return super().update_with_bar(i)
bars=[]
for i in range(19):
 op=100+i*.01; bars.append(bar(i,open_=op,close=op+.1,high=op+.5,low=op-.5,volume=100))
vol=[{'snapshot_id':f'v{i}','as_of_ts':b['ts']+1000,'availability_time_ms':b['ts'],'volume_sma':100.,'volume_ratio':1.5} for i,b in enumerate(bars)]
atr=[{'snapshot_id':f'a{i}','as_of':b['ts']+1000,'atr_n':2.} for i,b in enumerate(bars)]
e=Spy(get_params({'max_age_bars':8})); e.run_full(bars,{}, {},vol,atr)
print('validated_bars=',len(bars),'disp_max_k=',e.p.disp_max_k,'run_full_scan_bound=',len(bars)-e.p.disp_max_k-1)
print('update_indices=',e.updated,'max_updated_index=',max(e.updated) if e.updated else None,'last_input_index=',len(bars)-1)
