"""V6 probe V-001: independent re-verification of the nominal config checks.
- universe: 10 symbols, 14 unique TFs, complete tick/step/min_notional/lev tables
- quality_weights: every Q_raw row sums to 1
- setup_weights: 12 weights sum to 1; family mass 0.70 (required 0.54 + optional)
- risk_defaults: leverage caps by TF group
Uses the REAL loader (apex.config.load_params).
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.config import load_params

p = load_params()
u = p.universe()
q = p.quality_weights()
s = p.setup_weights()
r = p.risk_defaults()

symbols = u["symbols"]
tfs = u["timeframes"]
print("symbols:", len(symbols), symbols)
print("timeframes:", len(tfs), tfs)
print("unique symbols:", len(set(symbols)), "| unique TFs:", len(set(tfs)))
for table in ("tick_size", "quantity_step", "min_notional", "exchange_max_leverage"):
    keys = set(u[table])
    print(f"{table}: covers all 10 symbols:", keys == set(symbols))

print()
rows = q["q_raw_weights_by_tf"]
bad = []
for tf, w in rows.items():
    total = sum(w.values())
    if abs(total - 1.0) > 1e-9:
        bad.append((tf, total))
print("q_raw rows:", len(rows), "| all sum to 1:", not bad, bad[:3])
print("q_raw TF coverage == 14:", set(rows) == set(tfs))
print("q_min_by_tf rows:", len(q["q_min_by_tf"]),
      "| q_thr rows:", len(q["q_thr_by_tf"]),
      "| freshness rows:", len(q["freshness_threshold_seconds"]),
      "| oi_lag rows:", len(q["oi_lag_threshold_seconds"]))

print()
weights = s["weights"]
print("setup weights sum:", round(sum(weights.values()), 10),
      "| count:", len(weights))
required = ["structure", "liquidity", "fvg", "trend", "regime", "temporal"]
optional = ["orderblock", "momentum"]
fam = s["family_engines"]
req_mass = sum(weights["w_" + e] for e in required if e in fam)
opt_mass = sum(weights["w_" + e] for e in optional if e in fam)
print("family_engines:", fam)
print("required evidence mass:", round(req_mass, 10),
      "| + optional:", round(req_mass + opt_mass, 10))
print("Q_setup denominator (family mass) = 0.70:",
      abs(req_mass + opt_mass - 0.70) < 1e-9)

print()
caps = r["system_leverage_cap_by_tf"]
groups = {"2": ["1m", "3m", "5m"], "3": ["15m", "30m"], "4": ["1h", "2h", "4h"],
          "5": ["6h", "8h", "12h", "1d", "1w", "1mo"]}
ok = all(caps[tf] == int(g) for g, tfs_ in groups.items() for tf in tfs_)
print("leverage caps match Y.2 groups (2/3/4/5):", ok, "| rows:", len(caps))
print("risk scalars: budget_per_trade", r["budget_per_trade"], "k_attn",
      r["k_attn"], "daily", r["daily_loss_cap"], "weekly", r["weekly_loss_cap"],
      "halt", r["consecutive_loss_halt"])
