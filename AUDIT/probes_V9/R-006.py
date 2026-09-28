"""R-006: get_params wraps the governed YAML load in
`except Exception: raw_yaml = {}` — any config failure silently reverts
theta_H/quality_H_Q2/quality_H_Q5 from the D49-calibrated YAML values
(1.105878/1.229880/0.564415) to the stale chapter defaults (0.65/0.8/0.4)
with no error, no event, no yaml_assertions."""
import apex.config as config
from apex.engines.e11_regime.engine import get_params

# 1) healthy load through the REAL loader + REAL params/e11_params_v4.yaml
p_ok = get_params()
print("healthy YAML: theta_H=%s Q2=%s Q5=%s" % (
    p_ok.entropy_threshold, p_ok.quality_H_Q2, p_ok.quality_H_Q5))
print("yaml_assertions (%d):" % len(p_ok.yaml_assertions))
for a in p_ok.yaml_assertions:
    print("   ", a)
assert abs(p_ok.entropy_threshold - 1.105878) < 1e-9

# 2) simulate a config failure (permissions, corrupt YAML, missing file...)
orig = config.load_params
def broken():
    raise OSError("simulated: params/e11_params_v4.yaml unreadable")
config.load_params = broken
try:
    p_bad = get_params()
finally:
    config.load_params = orig
print("broken loader: theta_H=%s Q2=%s Q5=%s yaml_assertions=%s" % (
    p_bad.entropy_threshold, p_bad.quality_H_Q2, p_bad.quality_H_Q5,
    p_bad.yaml_assertions))
assert p_bad.entropy_threshold == 0.65
assert p_bad.quality_H_Q2 == 0.8 and p_bad.quality_H_Q5 == 0.4
assert p_bad.yaml_assertions == []
print("delta on theta_H: %.4f nats — silently applied" % (
    p_ok.entropy_threshold - p_bad.entropy_threshold))
print("R-006 CONFIRMED: silent fallback to ungoverned defaults on any "
      "loader exception; no refusal, no assertion, no event")
