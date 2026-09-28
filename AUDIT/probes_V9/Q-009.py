"""Q-009: with §4/§9 weights (sum=1) and every component score in [0,1],
the softmax logit spread over the 8 phases is at most 1.0, so
p_max <= e/(e+7) ~ 0.2797 and H >= ~1.99 nats > entropy_threshold 0.85:
the engine is structurally ALWAYS AMBIGUOUS; no phase can ever be ACTIVE."""
import itertools, math
from apex.engines.e08_wyckoff.engine import (
    softmax, entropy, phase_probabilities, phase_score_matrix, phase_weights,
    get_params, PHASES, SCORE_COMPONENTS, WyckoffEngineV4)

p = get_params()
w = phase_weights(p)
print("weights:", w, "sum =", sum(w), "| phases:", len(PHASES))

# analytic bound with engine's own softmax/entropy
z_best = [1.0] + [0.0] * (len(PHASES) - 1)
probs = softmax(z_best)
H_min = entropy(probs)
print("best-case z spread 1.0: p_max=%.4f H=%.4f nats (threshold %.2f)"
      % (max(probs), H_min, p.entropy_threshold))
assert max(probs) < 0.28 and H_min > p.entropy_threshold

# exhaustive-ish grid over extreme component scores through the REAL matrix
worst = (1.0, 0.0)
best = None
for pos in (0.0, 1.0):
    for evr in (-9.0, 0.0, 9.0):
        for vr in (0.0, 5.0):
            for st in (None, "BULL", "BEAR"):
                for age in (0.0, 96.0):
                    scores, _ = phase_score_matrix(pos * 200 - 50, 0, 100,
                                                   evr, vr, st, age, p)
                    pr, H = phase_probabilities(scores, w, PHASES)
                    if H < worst[0]:
                        worst = (H, max(pr.values()))
                        best = (pos, evr, vr, st, age)
print("min H over extreme grid = %.4f (p_max %.4f) at %s" % (
    worst[0], worst[1], best))
assert worst[0] > p.entropy_threshold

# a real accumulation-looking bar stream stays AMBIGUOUS too
eng = WyckoffEngineV4()
bars = [{"ts": i, "o": 100, "h": 101, "l": 99, "c": 99.4, "v": 1000}
        for i in range(15)]
recs = eng.run_full(bars, atr_by_idx={i: 1.0 for i in range(15)},
                    vol_ratio_by_idx={i: (3.0 if i == 13 else 1.0)
                                      for i in range(15)},
                    evr_by_idx={i: 1.0 for i in range(15)},
                    structure_by_idx={i: "BULL" for i in range(15)})
print("real run last fate =", recs[-1]["fate"],
      "entropy = %.4f" % recs[-1]["entropy"])
assert all(r.get("fate") in ("AMBIGUOUS", "Q0_INVALID") for r in recs)
print("Q-009 CONFIRMED: AMBIGUOUS is unreachable-from; ACTIVE fate "
      "mathematically impossible with governed weights/threshold")
