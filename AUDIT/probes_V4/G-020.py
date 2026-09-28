from unittest.mock import patch
from matplotlib.axes import Axes
from apex.telegram.signaling import render_chart
plotted=[]
original=Axes.plot
def spy(self,*args,**kwargs):
 plotted.append(list(args[1]))
 return original(self,*args,**kwargs)
with patch.object(Axes,'plot',spy):
 chart=render_chart(ohlcv=[[0,1,2,0.5,1.5,10],[1,2,3,0.7,2.6,11]],layers=['BOS','FVG'],snapshot_id='synthetic')
print('plotted_y=',plotted,'expected_close=',[1.5,2.6],'reported_layers=',chart['layers'],'unavailable=',chart['layers_unavailable'],'png_size=',len(chart['image']),'dimensions=',chart['width'],chart['height'])
