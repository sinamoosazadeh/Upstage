"""Shared deterministic synthetic OHLCV builders (no data/, no device)."""
import math


def zig(n=260, amp=6.0, leg=7, start=100.0, vol=900.0, jitter=0.0, seed=3,
        trend=0.0):
    """Alternating up/down legs (plus optional slow trend) so E01 finds
    swings and E01 breaks prior swing levels."""
    out = []
    x = start
    d = 1
    t = 0
    for i in range(n):
        # every `leg` bars flip direction, with a deterministic wobble
        if i % leg == 0 and i:
            d = -d
        drift = d * amp / leg + trend
        wob = jitter * math.sin(i * 1.7) if jitter else 0.0
        o = x
        c = x + drift + wob
        h = max(o, c) + amp * 0.12
        l = min(o, c) - amp * 0.12
        out.append({
            "O": round(o, 6), "H": round(h, 6), "L": round(l, 6),
            "C": round(c, 6), "V": round(vol * (1.0 + 0.25 * (i % 5)), 4),
            "open_time": "2026-01-%02dT%02d:%02d:00.000Z" % (1 + i // 1440, (i // 60) % 24, i % 60),
            "close_time": "2026-01-%02dT%02d:%02d:30.000Z" % (1 + i // 1440, (i // 60) % 24, i % 60),
            "availability_time": "2026-01-%02dT%02d:%02d:31.500Z" % (1 + i // 1440, (i // 60) % 24, i % 60),
        })
        x = c
    return out


def bars_from_candles(cs):
    """Plan-shaped bar view used by the setup family / plan bridge."""
    return [{"o": c["O"], "h": c["H"], "l": c["L"], "c": c["C"], "v": c["V"]}
            for c in cs]
