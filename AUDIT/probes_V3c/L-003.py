"""V3c L-003 probe: catalog-math zscore includes the current bar; F74 repeats it.

REAL code: apex.data_catalog.math.zscore, molecular.features.compute_sweep /
_volume_z, and E03 zscore_pit (prior-only boundary). Synthetic bars only.
Auditor's example: prior vols 1..20, sweep-bar vol 23, low=89 < extreme=90,
close=95 back inside.
"""
import datetime as dt
from decimal import Decimal

from apex.data_catalog import math as cmath
from apex.data_catalog.contracts import MarketObservation
from apex.data_catalog.molecular.features import _volume_z, compute_sweep
from apex.engines.e03_volume.engine import zscore_pit


def make_bar(i, o, h, l, c, v):
    ts = (dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
          + dt.timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return MarketObservation(
        symbol="BTCUSDT", timeframe="15m", open=Decimal(o), high=Decimal(h),
        low=Decimal(l), close=Decimal(c), volume=Decimal(v),
        oi=Decimal(500), timestamp=ts, sequence=i, status="CLOSED",
        source="TOOBIT", availability_time=ts)


def main():
    prior_vols = [Decimal(i) for i in range(1, 21)]
    current_vol = Decimal(23)

    # 1) catalog-math zscore over prior+current (what _f19/_f34 do with window[-n:]).
    got = cmath.zscore(prior_vols + [current_vol], 20)
    # contract §3.1: baseline = 20 values BEFORE the candle.
    mu = sum(prior_vols, Decimal(0)) / Decimal(20)
    var = sum((v - mu) ** 2 for v in prior_vols) / Decimal(20)
    contract_z = (current_vol - mu) / var.sqrt()
    print(f"catalog zscore(prior+current,20) = {got}")
    print(f"contract  (current vs prior-only) = {contract_z}")
    print(f"E03 zscore_pit(23, 1..20, 20)     = "
          f"{zscore_pit(23.0, [float(i) for i in range(1, 21)], 20)}")

    # 2) F74 on the auditor's sweep geometry.
    prior = [make_bar(i, 100 + i, 105 + i, 90 + i, 102 + i, i + 1)
             for i in range(20)]
    print(f"rolling prior low extreme = {min(o.low for o in prior)}")
    sweep_bar = make_bar(20, 94, 96, 89, 95, 23)  # low 89 < 90, close 95 inside
    block = [sweep_bar] + [make_bar(21 + j, 100, 105, 95, 102, 10)
                           for j in range(4)]
    print(f"F74 _volume_z(prior, sweep_bar) = {_volume_z(prior, sweep_bar)} "
          f"(gate needs >= 2)")
    value, q, status, reason = compute_sweep(prior + block, {}, {})
    print(f"compute_sweep -> value={value} q={q} status={status} reason={reason}")


if __name__ == "__main__":
    main()
