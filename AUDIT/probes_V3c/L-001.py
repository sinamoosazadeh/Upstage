"""V3c L-001 probe: ATOM default window depth vs per-formula bar needs.

Uses the REAL repository code: FeatureRegistry/Catalog from
apex.data_catalog.catalog, REAL ATOM computers via catalog.get, and the REAL
EngineBase.feature signature. Synthetic bars only (in-memory provider).
"""
import asyncio
import datetime as dt
import inspect
from decimal import Decimal

from apex.data_catalog.catalog import Catalog, build_registry
from apex.data_catalog.contracts import MarketObservation
from apex.engines.base import EngineBase


def make_bar(i, base_ms):
    ts = (dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
          + dt.timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    o = Decimal(100) + Decimal(i)
    return MarketObservation(
        symbol="BTCUSDT", timeframe="15m", open=o, high=o + 5, low=o - 3,
        close=o + 2, volume=Decimal(10 + i), oi=Decimal(500 + i),
        timestamp=ts, sequence=i, status="CLOSED", source="TOOBIT",
        availability_time=ts)


class MemProvider:
    def __init__(self, rows):
        self._rows = rows

    def get_window(self, symbol, timeframe, as_of, bars):
        rows = [o for o in self._rows if o.timestamp <= as_of]
        return rows[-bars:]

    def max_availability_time(self, symbol, timeframe, as_of):
        return as_of  # frontier == as_of: no PIT_FUTURE_AS_OF


def main():
    registry, _ = build_registry()
    atoms = [c for c in registry.all() if c.id.super_layer == "ATOM"]
    print(f"ATOM count: {len(atoms)}")
    distinct = sorted({(c.lookback, c.warmup) for c in atoms})
    print(f"distinct (lookback, warmup) over all ATOM contracts: {distinct}")

    rows = [make_bar(i, 0) for i in range(40)]
    as_of = rows[-1].timestamp
    cat = Catalog()
    cat.set_provider(MemProvider(rows))

    print(f"EngineBase.feature signature default lookback: "
          f"{inspect.signature(EngineBase.feature).parameters['lookback'].default}")

    for fid in ("TR_t", "ATR", "SMA", "RSI", "VolumeZ", "return_k", "OBV"):
        r1 = asyncio.run(cat.get(fid, "BTCUSDT", "15m", as_of))
        try:
            r22 = asyncio.run(cat.get(fid, "BTCUSDT", "15m", as_of, lookback=22))
            r22s = (f"status={r22.status.value:11s} "
                    f"reason={r22.reason:22s} value={r22.value}")
        except Exception as exc:  # noqa: BLE001 - probe reports, not hides
            r22s = f"RAISED {type(exc).__name__}: {exc}"
        print(f"{fid:9s} default(1): status={r1.status.value:11s} reason={r1.reason:22s} "
              f"value={r1.value} | lookback=22: {r22s}")


if __name__ == "__main__":
    main()
