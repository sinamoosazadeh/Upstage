"""Synthetic-only V8 helper. Every OHLC observation passes repository validation."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
from apex.data_catalog.contracts import MarketObservation, validate_market_observation

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

def obs(i, *, close=None, open_=None, high=None, low=None, volume=100.0,
        oi=None, status="CLOSED", timeframe="1h", timestamp=None):
    op = float(100.0 + 0.02 * i if open_ is None else open_)
    cl = float(op + 0.1 if close is None else close)
    hi = float(max(op, cl) + 0.5 if high is None else high)
    lo = float(min(op, cl) - 0.5 if low is None else low)
    t = timestamp or (T0 + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    o = MarketObservation(
        symbol="BTCUSDT", timeframe=timeframe, open=Decimal(str(op)),
        high=Decimal(str(hi)), low=Decimal(str(lo)), close=Decimal(str(cl)),
        volume=Decimal(str(volume)), oi=None if oi is None else Decimal(str(oi)),
        timestamp=t, sequence=i + 1, status=status,
        availability_time=t, oi_timestamp=t if oi is not None else None)
    validate_market_observation(o, prev_sequence=i if i else None)
    return o

def bar(i, *, close=None, open_=None, high=None, low=None, volume=100.0,
        oi=None, ts=None, gap_hours=0):
    # Validate the source OHLC as a repository MarketObservation before adaptation.
    o = obs(i, close=close, open_=open_, high=high, low=low,
            volume=volume, oi=oi)
    from apex.data_catalog.contracts import parse_utc_ms
    ts_ms = int(parse_utc_ms(o.timestamp).timestamp() * 1000)
    if ts is not None:
        ts_ms = ts
    available = ts_ms + 1000
    oi_ts = available if oi is not None else None
    return {"ts": ts_ms, "o": float(o.open), "h": float(o.high),
            "l": float(o.low), "c": float(o.close), "v": float(o.volume),
            "is_closed": o.status == "CLOSED", "tf": o.timeframe,
            "symbol": o.symbol, "oi": None if o.oi is None else float(o.oi),
            "oi_timestamp": oi_ts, "atr_prev": 2.0,
            "availability_time_ms": available,
            "oi_availability_time_ms": oi_ts or available,
            "atr_availability_time_ms": available,
            "temporal_window": o.timestamp[:10]}

def stable_bars(n, *, volume=100.0, base=100.0, step=0.02):
    out=[]
    for i in range(n):
        op=base+i*step; cl=op+0.1
        out.append(bar(i, open_=op, close=cl, high=cl+0.5, low=op-0.5,
                       volume=volume))
    return out
