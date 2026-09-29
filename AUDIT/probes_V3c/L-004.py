"""V3c L-004 probe: _f21_oi_z drops None OIs, then counts survivors.

REAL code: Catalog.get("OI_z") -> _f21_oi_z. Synthetic bars: 20 valid OI
then a current bar with OI None, SAME as_of, two depths.
"""
import asyncio
import datetime as dt
from decimal import Decimal

from apex.data_catalog.catalog import Catalog
from apex.data_catalog.contracts import MarketObservation


def make_bar(i, oi):
    ts = (dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
          + dt.timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    o = Decimal(100) + Decimal(i)
    return MarketObservation(
        symbol="BTCUSDT", timeframe="15m", open=o, high=o + 5, low=o - 3,
        close=o + 2, volume=Decimal(10 + i),
        oi=(Decimal(oi) if oi is not None else None),
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
    rows = [make_bar(i, 500 + i) for i in range(20)] + [make_bar(20, None)]
    as_of = rows[-1].timestamp
    print(f"bars=21, current-bar OI={rows[-1].oi}, as_of={as_of} (same for both reads)")
    cat = Catalog()
    cat.set_provider(MemProvider(rows))
    r20 = asyncio.run(cat.get("OI_z", "BTCUSDT", "15m", as_of, lookback=20))
    print(f"lookback=20: status={r20.status.value} reason={r20.reason} "
          f"value={r20.value} q={r20.q_component}")
    r21 = asyncio.run(cat.get("OI_z", "BTCUSDT", "15m", as_of, lookback=21))
    print(f"lookback=21: status={r21.status.value} reason={r21.reason} "
          f"value={r21.value} q={r21.q_component}")
    # Control: current bar WITH valid OI at the same depth.
    rows2 = [make_bar(i, 500 + i) for i in range(21)]
    cat2 = Catalog()
    cat2.set_provider(MemProvider(rows2))
    rc = asyncio.run(cat2.get("OI_z", "BTCUSDT", "15m", rows2[-1].timestamp,
                              lookback=21))
    print(f"control (current OI valid): status={rc.status.value} "
          f"value={rc.value} q={rc.q_component}")


if __name__ == "__main__":
    main()
