"""Q-030: engine get_params() only rejects UNKNOWN keys; out-of-domain
values (th_int=0, negative weights, window_macro=0, w_position=100) are
accepted without any range validation across E07/E08/E09."""
from apex.engines.e07_rtm import engine as e07
from apex.engines.e08_wyckoff import engine as e08
from apex.engines.e09_trend import engine as e09

p7 = e07.get_params({"th_int": 0.0, "th_weight": -5.0, "w_sweep": -1.5})
print("E07 accepted: th_int=%s th_weight=%s w_sweep=%s" % (
    p7.th_int, p7.th_weight, p7.w_sweep))
assert p7.th_int == 0.0 and p7.th_weight == -5.0

p8 = e08.get_params({"w_position": 100.0, "entropy_threshold": -1.0})
print("E08 accepted: w_position=%s entropy_threshold=%s" % (
    p8.w_position, p8.entropy_threshold))
assert p8.w_position == 100.0

p9 = e09.get_params({"window_macro": 0, "adx_n": -14})
print("E09 accepted: window_macro=%s adx_n=%s" % (
    p9.window_macro, p9.adx_n))
assert p9.window_macro == 0

# unknown keys ARE rejected (only guard present):
for mod, bad in ((e07, {"nope": 1}), (e08, {"nope": 1}), (e09, {"nope": 1})):
    try:
        mod.get_params(bad)
        print(mod.__name__, "accepted unknown key (unexpected)")
    except Exception as exc:
        print(mod.__name__, "rejects unknown key:", type(exc).__name__)
print("Q-030 CONFIRMED: unknown-key guard only; no domain/range validation")
