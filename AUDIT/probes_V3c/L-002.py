"""V3c L-002 probe: catalog-math obv_series prev-type bug.

REAL code: apex.data_catalog.math.obv_series, Catalog.get("OBV"), and the
separate E03 obv_series_wilder (boundary: E03 runtime does not use catalog math).
Synthetic bars only.
"""
import asyncio
import datetime as dt
import traceback
from decimal import Decimal

from apex.data_catalog import math as cmath
from apex.data_catalog.catalog import Catalog
from apex.data_catalog.contracts import MarketObservation
from apex.engines.e03_volume.engine import obv_series_wilder


def make_bar(i, close):
    ts = (dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
          + dt.timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    o = Decimal(close)
    return MarketObservation(
        symbol="BTCUSDT", timeframe="15m", open=o, high=o + 5, low=o - 3,
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
    up = [make_bar(0, 100), make_bar(1, 105)]   # rising close
    down = [make_bar(0, 105), make_bar(1, 100)]  # falling close
    flat = [make_bar(0, 100), make_bar(1, 100)]  # flat close

    for name, window in (("rising", up), ("falling", down), ("flat", flat)):
        try:
            print(f"obv_series 1-bar [{name}]: {cmath.obv_series(window[:1])}")
        except Exception as exc:  # noqa: BLE001
            print(f"obv_series 1-bar [{name}]: RAISED {type(exc).__name__}: {exc}")
        try:
            print(f"obv_series 2-bar [{name}]: {cmath.obv_series(window)}")
        except Exception as exc:  # noqa: BLE001
            print(f"obv_series 2-bar [{name}]: RAISED {type(exc).__name__}: {exc}")

    rows = [make_bar(i, 100 + i) for i in range(5)]
    as_of = rows[-1].timestamp
    cat = Catalog()
    cat.set_provider(MemProvider(rows))
    r1 = asyncio.run(cat.get("OBV", "BTCUSDT", "15m", as_of))
    print(f'Catalog.get("OBV") default: status={r1.status.value} '
          f"reason={r1.reason!r} value={r1.value}")
    try:
        r2 = asyncio.run(cat.get("OBV", "BTCUSDT", "15m", as_of, lookback=2))
        print(f'Catalog.get("OBV", lookback=2): status={r2.status.value} '
              f"value={r2.value}")
    except Exception:  # noqa: BLE001
        print('Catalog.get("OBV", lookback=2): RAISED:')
        traceback.print_exc(limit=3)

    # Boundary: E03's independent implementation on the same closes.
    print("E03 obv_series_wilder rising [100,105] vols [10,10]:",
          obv_series_wilder([100.0, 105.0], [10.0, 10.0]))
    print("E03 obv_series_wilder falling [105,100] vols [10,10]:",
          obv_series_wilder([105.0, 100.0], [10.0, 10.0]))
    print("E03 obv_series_wilder flat [100,100] vols [10,10]:",
          obv_series_wilder([100.0, 100.0], [10.0, 10.0]))


if __name__ == "__main__":
    main()
