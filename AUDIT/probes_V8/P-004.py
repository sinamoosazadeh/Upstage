from common import stable_bars
from apex.engines.e03_volume.engine import E03VolumeEngine, ParticipationEvidence
bars=stable_bars(52)
for b in bars: b['o']=100.; b['h']=101.; b['l']=99.; b['c']=100.
bars[49].update(o=100.,h=101.,l=99.,c=100.)
bars[50].update(o=100.,h=101.,l=99.,c=100.)
ev=ParticipationEvidence(climax=True, volume_ratio=3., volume_sma=100.,
                         quality='Q1', as_of_ts=bars[49]['availability_time_ms'])
later=ParticipationEvidence(climax=False,volume_ratio=1.,volume_sma=100.,quality='Q1',as_of_ts=bars[50]['availability_time_ms'])
conf_a=E03VolumeEngine._climax_calibration([ev,later],bars,source_indices=[49,50])
bars_future=[dict(b) for b in bars]
bars_future[50]['c']=102.; bars_future[50]['h']=102.5
conf_b=E03VolumeEngine._climax_calibration([ev,later],bars_future,source_indices=[49,50])
print('validated_ohlc=52; climax_source_index=49; confidence_prefix_t=',conf_a)
print('confidence_after_future_close_index50=',conf_b)
print('same_source_event_as_of_ms=',ev.as_of_ts,'source_bar_availability_ms=',bars[49]['availability_time_ms'])
