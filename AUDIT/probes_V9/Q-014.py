"""Q-014: E08._to_evidence stamps EVERY event with the FINAL cycle state and
reads final.get("age") — a key the cycle record does not carry (it carries
"age_bars") — so age=0.0 and decay=1.0 for all evidence, and early events
(e.g. the SC from 80 bars ago) are labelled with today's state/fate."""
from apex.engines.e08_wyckoff.engine import E08WyckoffEngine, WyckoffEngineV4

eng = WyckoffEngineV4()
bars = [{"ts": i, "o": 100, "h": 100.6, "l": 99.4, "c": 100, "v": 1000}
        for i in range(14)]
bars.append({"ts": 14, "o": 100.5, "h": 100.6, "l": 96.0, "c": 97.5,
             "v": 5000})                                     # SC bar
bars += [{"ts": 15 + i, "o": 97.5, "h": 98.4, "l": 97.0, "c": 97.9,
          "v": 1000} for i in range(40)]                     # 40 bars later
n = len(bars)
recs = eng.run_full(bars, atr_by_idx={i: 1.0 for i in range(n)},
                    vol_ratio_by_idx={i: (3.0 if i == 14 else 1.0)
                                      for i in range(n)},
                    evr_by_idx={i: 0.0 for i in range(n)})
final = recs[-1]
print("cycle record keys:", sorted(final.keys()))
print('"age" in record:', "age" in final,
      '| range.age_bars =', final["range"]["age_bars"])

e08 = E08WyckoffEngine()
sc_ev = next(e for e in eng.events if e["code"] == "EV_WYK_002")
ev = e08._to_evidence(sc_ev, "BTCUSDT", "1h", 0.9, final)  # SC event
print("SC event ts:", sc_ev["ts"], sc_ev["code"])
print("evidence age=%s decay=%s observation_window=%s" % (
    ev.age, ev.decay, ev.observation_window))
print("evidence explanation:", ev.explanation)
assert final["range"]["age_bars"] > 30         # real range age is large
assert "age" not in final                      # the key _to_evidence reads
assert ev.age == 0.0 and ev.decay == 1.0       # but evidence says fresh
assert f"state={final.get('state')}" in ev.explanation
print("Q-014 CONFIRMED: final.get('age') key mismatch (age_bars) => age=0/"
      "decay=1 on all evidence; events stamped with final state, not their own")
