"""V3c L-005 probe: catalog-math RSI returns 100 on a flat market; E10/contract say 50.

REAL code: apex.data_catalog.math.rsi_wilder, Catalog.get("RSI"), and E10
rsi_series (governing formula). Synthetic closes only.
"""
import asyncio
import datetime as dt
from decimal import Decimal

from apex.data_catalog import math as cmath
from apex.data_catalog.catalog import Catalog
from apex.data_catalog.contracts import MarketObservation
from apex.engines.e10_momentum.engine import rsi_series


def make_bar(i, close):
    ts = (dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
          + dt.timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    o = Decimal(close)
    return MarketObservation(
        symbol="BTCUSDT", timeframe="15m", open=o, high=o + 1, low=o - 1,
        close=o, volume=Decimal(10), oi=Decimal(500),
        timestamp=ts, sequence=i, status="CLOSED", source="TOOBIT",
        availability_time=ts)


class MemProvider:
    def __init__(self, rows):
        self._rows = rows

    def get_window(self, symbol, timeframe, as_of, bars):
        return [o for o in self._rows if o.timestamp <= as_of][-bars:]

    def max_availability_time(self, symbol, timeframe, as_of):
        return as_of


def main():
    flat = [Decimal(100)] * 15
    up = [Decimal(100 + i) for i in range(15)]
    down = [Decimal(100 - i) for i in range(15)]
    for name, closes in (("flat", flat), ("pure-up", up), ("pure-down", down)):
        cm = cmath.rsi_wilder(closes, 14)
        e10 = rsi_series([float(c) for c in closes], 14)[-1]
        print(f"{name:9s} catalog-math rsi_wilder={cm}   E10 rsi_series={e10}")

    rows = [make_bar(i, 100) for i in range(15)]
    cat = Catalog()
    cat.set_provider(MemProvider(rows))
    as_of = rows[-1].timestamp
    r1 = asyncio.run(cat.get("RSI", "BTCUSDT", "15m", as_of))
    r15 = asyncio.run(cat.get("RSI", "BTCUSDT", "15m", as_of, lookback=15))
    print(f'flat-market Catalog.get("RSI") default: {r1.status.value}/{r1.reason} '
          f"value={r1.value}")
    print(f'flat-market Catalog.get("RSI", lookback=15): {r15.status.value} '
          f"value={r15.value} (E10/contract §3.3 edge = 50)")


if __name__ == "__main__":
    main()
