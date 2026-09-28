"""Q-018: score_age enters EVERY phase's logit with the same weight, so the
softmax is invariant to age: an 96-bar-old hypothesis has exactly the same
phase probabilities as a fresh one — the §3.2 age decay does nothing."""
from apex.engines.e08_wyckoff.engine import (phase_score_matrix,
                                             phase_probabilities,
                                             phase_weights, get_params,
                                             PHASES)

p = get_params()
w = phase_weights(p)
base = dict(close=99.6, range_lo=99.0, range_hi=101.0, evr_value=1.2,
            vol_ratio=0.8, structure="BULL")
out = {}
for age in (0, 10, 48, 96, 100000):
    scores, _ = phase_score_matrix(base["close"], base["range_lo"],
                                   base["range_hi"], base["evr_value"],
                                   base["vol_ratio"], base["structure"],
                                   float(age), p)
    probs, H = phase_probabilities(scores, w, PHASES)
    out[age] = (probs, H)
    print("age=%6d H=%.6f top3=%s" % (
        age, H, sorted(probs.items(), key=lambda kv: -kv[1])[:3]))
p0 = out[0][0]
for age, (probs, H) in out.items():
    for ph in PHASES:
        assert abs(probs[ph] - p0[ph]) < 1e-12, (age, ph)
print("Q-018 CONFIRMED: probabilities bit-identical across ages 0..100000 "
      "(uniform additive shift cancels in softmax)")
