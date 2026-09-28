"""R-017: window_phase is structurally degenerate: UTC_W0 (7h) and UTC_W3
(3h) are ALWAYS 'MID' (no EARLY/LATE ever), UTC_W1's EARLY is exactly one
hour (7:00-8:00) of a 5.5h window and W2's EARLY is 30 minutes
(12:30-13:00) of an 8.5h window — the phases are neither thirds nor any
consistent fraction across windows."""
import datetime
from apex.engines.e12_temporal.engine import (utc_activity_window_of,
                                              UTC_ACTIVITY_WINDOWS)

def phase(hh, mm=0):
    ts = datetime.datetime(2026, 3, 2, hh, mm,
                           tzinfo=datetime.timezone.utc)
    r = utc_activity_window_of(ts)
    return r["temporal_window"], r["window_phase"]

print("registry:", UTC_ACTIVITY_WINDOWS)
# W0: 0-7h, W3: 21-24h — scan every 30 min: only MID
w0 = {phase(h, m) for h in range(0, 7) for m in (0, 30)}
w3 = {phase(h, m) for h in range(21, 24) for m in (0, 30)}
print("W0 phases:", w0)
print("W3 phases:", w3)
assert w0 == {("UTC_W0", "MID")} and w3 == {("UTC_W3", "MID")}
# W1 (7-12.5): EARLY < 8.0, LATE >= 11.5
print("W1: 07:00->%s 07:59->%s 08:00->%s 11:29->%s 11:30->%s" % (
    phase(7)[1], phase(7, 59)[1], phase(8)[1], phase(11, 29)[1],
    phase(11, 30)[1]))
assert phase(7)[1] == "EARLY" and phase(8)[1] == "MID" \
       and phase(11, 30)[1] == "LATE"
# W2 (12.5-21): EARLY < 13.0 (30 min), LATE >= 20.5 (30 min)
print("W2: 12:30->%s 12:59->%s 13:00->%s 20:29->%s 20:30->%s" % (
    phase(12, 30)[1], phase(12, 59)[1], phase(13)[1], phase(20, 29)[1],
    phase(20, 30)[1]))
assert phase(12, 30)[1] == "EARLY" and phase(13)[1] == "MID" \
       and phase(20, 30)[1] == "LATE"
# fractions: W1 EARLY = 1h/5.5h = 18%; W2 EARLY = 0.5h/8.5h = 6%;
# W0/W3 EARLY = 0%
print("EARLY share: W0=0%% W1=%.0f%% W2=%.0f%% W3=0%%" % (
    1.0 / 5.5 * 100, 0.5 / 8.5 * 100))
print("R-017 CONFIRMED: phase taxonomy inconsistent across windows; "
      "W0/W3 consumers can never react to open/close phases")
