"""Compare CP-4/CP-5 integration fixture timestamps with their stated AS_OF."""
from __future__ import annotations
import datetime as dt
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def ms(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)

for name in ("cp4", "cp5"):
    ns = runpy.run_path(str(ROOT / "tests" / "integration" / f"test_{name}_engines.py"))
    cutoff = ms(ns["AS_OF"])
    if name == "cp4":
        bars = ns["lcg_window"](30)
        fixture_label = "lcg_window(30), used by CP4 E07 emission fixture"
    else:
        bars = ns["BARS"]
        fixture_label = "BARS=lcg_window(60), used by CP5 E10-E12 fixtures"
    stamps = [int(bar["ts"]) for bar in bars]
    before = sum(ts < cutoff for ts in stamps)
    equal = sum(ts == cutoff for ts in stamps)
    after = sum(ts > cutoff for ts in stamps)
    print(f"{name.upper()} AS_OF={ns['AS_OF']} ({cutoff})")
    print(f"  AS_OF_MS constant={ns['AS_OF_MS']} delta_ms={ns['AS_OF_MS']-cutoff}")
    print(f"  fixture={fixture_label}; n={len(stamps)}")
    print(f"  first={dt.datetime.fromtimestamp(min(stamps)/1000,dt.timezone.utc).isoformat()}")
    print(f"  last={dt.datetime.fromtimestamp(max(stamps)/1000,dt.timezone.utc).isoformat()}")
    print(f"  timestamp comparison: before={before}, equal={equal}, after={after}")
    observations = ns["obs_window"](bars)
    obs_stamps = [ms(o.timestamp) for o in observations]
    print(f"  obs_window preserves timestamps: {obs_stamps == stamps}; after_as_of={sum(t > cutoff for t in obs_stamps)}")
    if name == "cp5":
        candles = ns["e11_candles"](bars)
        print(f"  e11_candles preserves future ts/as_of: {sum(c['ts'] > cutoff for c in candles)} ts; "
              f"{sum(c['as_of'] > cutoff for c in candles)} as_of")
    print()
