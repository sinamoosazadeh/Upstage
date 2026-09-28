"""R-014: E12TemporalProvider.temporal_window DOES report
rollover_active=True, but E07's provider branch hardcodes
"rollover_active": False in its return dict — the rollover signal is
computed upstream and then discarded at the E07 boundary."""
import datetime
from apex.engines.e12_temporal.engine import E12TemporalProvider
from apex.engines.e07_rtm.engine import utc_activity_window_check

# a rollover window covering 13:00-14:00 UTC
roll = [{"weekdays": [0, 1, 2, 3, 4], "start_h": 13.0, "end_h": 14.0}]
prov = E12TemporalProvider(rollover_windows=roll)
ts = int(datetime.datetime(2026, 3, 2, 13, 30,
                           tzinfo=datetime.timezone.utc).timestamp() * 1000)
raw = prov.temporal_window(ts)
print("provider says:", {k: raw[k] for k in ("utc_activity_window",
                                             "is_overlap",
                                             "rollover_active")})
kz = utc_activity_window_check(ts, temporal_provider=prov)
print("E07 kz_info:  ", {k: kz[k] for k in ("utc_activity_window",
                                            "is_overlap",
                                            "rollover_active", "source")})
assert raw["rollover_active"] is True
assert kz["rollover_active"] is False
print("R-014 CONFIRMED: provider rollover flag dropped — E07 consumers "
      "can never see an active rollover")
