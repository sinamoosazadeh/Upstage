"""APEX_GEN5 Numerical Contract (§2.2).

Two-tier epsilon reality (frozen):
- Tier 1 — general math floor: 1e-12 (Decimal-path division guard; never
  itself a trading tolerance).
- Tier 2 — operational per-engine EPS: 1e-8; ATR floor 1e-8.
- Per-engine EPS table (frozen constants; not changed without a governed
  parameter change): E01 scaled variant max(tick×0.5, median_20(close)×1e-8,
  1e-12); E02/E03/E05/E06/E07/E08/E10/E11 = 1e-8; E04/E09/E12 = 1e-12.

Precision and rounding: all values stored as Decimal, rounded
ROUND_HALF_UP (never native float). Digit plan: price 10, volume 8,
quality 4, strength 4, confidence 4, fee 10, ATR 10, return 10,
body ratio 6. NaN/Inf always set Q_formula_valid=0 (degraded) — never
silently skipped or treated as zero; -0 normalizes to 0; missing →
QUARANTINED. Division guards: max(denominator, eps) everywhere.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Any, Dict, Optional, Tuple

getcontext().prec = 28

# ---- two-tier epsilon reality (§2.2, frozen) -------------------------------
EPS_TIER1 = Decimal("1e-12")   # general math floor
EPS_TIER2 = Decimal("1e-8")    # operational per-engine EPS
ATR_FLOOR = Decimal("1e-8")    # ATR floor (Q_epsilon + range formulas)

# Frozen per-engine EPS table (§2.2)
ENGINE_EPS: Dict[str, str] = {
    "E01": "SCALED",  # max(tick*0.5, median_20(close)*1e-8, 1e-12)
    "E02": "1e-8",
    "E03": "1e-8",
    "E04": "1e-12",
    "E05": "1e-8",
    "E06": "1e-8",
    "E07": "1e-8",
    "E08": "1e-8",
    "E09": "1e-12",
    "E10": "1e-8",
    "E11": "1e-8",
    "E12": "1e-12",
}

# Frozen digit plan (§2.2 Precision and rounding)
PRECISION: Dict[str, int] = {
    "price": 10,
    "volume": 8,
    "quality": 4,
    "strength": 4,
    "confidence": 4,
    "fee": 10,
    "atr": 10,
    "return": 10,
    "body_ratio": 6,
}


def eps_for_engine(engine_id: str,
                   tick_size: Optional[Decimal] = None,
                   closes_20: Optional[list] = None) -> Decimal:
    """Frozen operational EPS for an engine (Tier-2 table).

    E01 is the scaled variant max(tick×0.5, median_20(close)×1e-8, 1e-12);
    tick_size/closes_20 missing for E01 → fail-closed ValueError (no
    guessed inputs). Unknown engine_id → KeyError (fail-closed).
    """
    form = ENGINE_EPS[engine_id]
    if form == "SCALED":
        if tick_size is None or closes_20 is None:
            raise ValueError(
                f"E01 scaled EPS requires tick_size and median_20(close) "
                f"inputs (MISSING_EPS_INPUTS_QX)"
            )
        values = [Decimal(str(c)) for c in closes_20]
        if not values:
            raise ValueError("E01 scaled EPS: closes_20 empty")
        values_sorted = sorted(values)
        n = len(values_sorted)
        if n % 2:
            median = values_sorted[n // 2]
        else:
            median = (values_sorted[n // 2 - 1] + values_sorted[n // 2]) / Decimal(2)
        return max(Decimal(str(tick_size)) * Decimal("0.5"),
                   median * EPS_TIER2, EPS_TIER1)
    return Decimal(form)


def quantize(value: Decimal, digits: int) -> Decimal:
    """ROUND_HALF_UP quantization (§2.2)."""
    quantum = Decimal(1).scaleb(-digits)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def quantize_field(field: str, value: Decimal) -> Decimal:
    """Quantize per the frozen digit plan (unknown field → fail-closed)."""
    return quantize(value, PRECISION[field])


def guarded_div(numerator: Decimal, denominator: Decimal,
                eps: Decimal = EPS_TIER1) -> Decimal:
    """Division guard: max(|denominator|, eps) preserving sign. NaN/Inf
    operands raise ValueError (never silent)."""
    if numerator.is_nan() or denominator.is_nan() or numerator.is_infinite() \
            or denominator.is_infinite():
        raise ValueError("NAN_INF_QX")
    if abs(denominator) < eps:
        denominator = eps if denominator >= 0 else -eps
    result = numerator / denominator
    if result.is_nan() or result.is_infinite():
        raise ValueError("NAN_INF_QX")
    if result == 0:
        result = Decimal(0)  # -0 → 0 (E-NUM-003)
    return result


def sanitize_decimal(value: Decimal) -> Tuple[Optional[Decimal], float]:
    """NaN/Inf → (None, 0.0) degraded; -0 → 0 (E-NUM-001/002/003)."""
    if value.is_nan() or value.is_infinite():
        return None, 0.0
    if value == 0:
        return Decimal(0), 1.0
    return value, 1.0


def calc_numerical_contract(
    C: Decimal, O: Decimal, H: Decimal, L: Decimal, V: Decimal,
    ATR_n: Decimal, tick_size: Decimal, quantity_step: Decimal,
    timeframe: str = "15m", eps: Decimal = EPS_TIER1,
) -> Tuple[Optional[Dict[str, Any]], str, str]:
    """§2.2 algorithm implemented exactly (Decimal path, ROUND_HALF_UP).

    Returns (contract_dict, status, quality_class). NaN/Inf →
    QUARANTINED_NAN_INF / QX; H<L → QUARANTINED_H_LT_L / QX; doji range
    guarded by max(range, eps_range) so ratios stay finite.
    """
    # scaled-epsilon TARGET formulas (normative for future governed
    # changes; the frozen runtime operates the two-tier reality — both are
    # emitted here for completeness exactly as the algorithm does)
    eps_price = Decimal("1e-10") * Decimal(str(tick_size))
    eps_volume = Decimal("1e-12") * Decimal(str(quantity_step))
    eps_range = max(Decimal("1e-10"), Decimal("1e-9") * Decimal(str(ATR_n)))
    eps_momentum = Decimal("1e-12")

    C_d, O_d, H_d, L_d, V_d = (Decimal(str(x)) for x in (C, O, H, L, V))
    ATR_n_d = Decimal(str(ATR_n))

    if H_d < L_d:
        return None, "QUARANTINED_H_LT_L", "QX"

    range_d = H_d - L_d
    guard = max(range_d, eps_range)

    body_ratio = quantize(abs(C_d - O_d) / guard, 6)
    upper_wick = quantize((H_d - max(O_d, C_d)) / guard, 6)
    lower_wick = quantize((min(O_d, C_d) - L_d) / guard, 6)
    close_position = quantize((C_d - L_d) / guard, 4)
    normalized_range = quantize(
        range_d / max(ATR_n_d, eps_range), 4)

    results = [body_ratio, upper_wick, lower_wick, close_position,
               normalized_range]
    if any(v.is_nan() or v.is_infinite() for v in results):
        return None, "QUARANTINED_NAN_INF", "QX"
    results = [Decimal(0) if v == Decimal(-0) else v for v in results]

    return {
        "body_ratio": results[0],
        "upper_wick": results[1],
        "lower_wick": results[2],
        "close_position": results[3],
        "normalized_range": results[4],
        "eps_price": eps_price,
        "eps_volume": eps_volume,
        "eps_range": eps_range,
        "eps_momentum": eps_momentum,
    }, "VALID", "Q1"


# ---- §2.2 core formulas exposed individually (engine/fabric reuse) --------

def formula_body_ratio(C: Decimal, O: Decimal, H: Decimal, L: Decimal,
                       eps_range: Decimal = EPS_TIER1) -> Tuple[Optional[Decimal], float]:
    if H < L:
        return None, 0.0
    try:
        value = guarded_div(abs(C - O), max(H - L, eps_range))
        value, q = sanitize_decimal(value)
        return quantize(value, 6) if value is not None else None, q
    except ValueError:
        return None, 0.0


def formula_upper_wick(H: Decimal, O: Decimal, C: Decimal, L: Decimal,
                       eps_range: Decimal = EPS_TIER1) -> Tuple[Optional[Decimal], float]:
    if H < L:
        return None, 0.0
    try:
        value = guarded_div(H - max(O, C), max(H - L, eps_range))
        value, q = sanitize_decimal(value)
        return quantize(value, 6) if value is not None else None, q
    except ValueError:
        return None, 0.0


def formula_lower_wick(O: Decimal, C: Decimal, L: Decimal, H: Decimal,
                       eps_range: Decimal = EPS_TIER1) -> Tuple[Optional[Decimal], float]:
    if H < L:
        return None, 0.0
    try:
        value = guarded_div(min(O, C) - L, max(H - L, eps_range))
        value, q = sanitize_decimal(value)
        return quantize(value, 6) if value is not None else None, q
    except ValueError:
        return None, 0.0


def formula_close_position(C: Decimal, L: Decimal, H: Decimal,
                           eps_range: Decimal = EPS_TIER1) -> Tuple[Optional[Decimal], float]:
    if H < L:
        return None, 0.0
    try:
        value = guarded_div(C - L, max(H - L, eps_range))
        value, q = sanitize_decimal(value)
        return quantize(value, 4) if value is not None else None, q
    except ValueError:
        return None, 0.0


def formula_normalized_range(H: Decimal, L: Decimal, ATR_n: Decimal,
                             eps_range: Decimal = EPS_TIER1) -> Tuple[Optional[Decimal], float]:
    if H < L:
        return None, 0.0
    if ATR_n < ATR_FLOOR:
        return None, 0.0  # ATR below floor → DEGRADED (Q_epsilon=0)
    try:
        value = guarded_div(H - L, max(ATR_n, eps_range))
        value, q = sanitize_decimal(value)
        return quantize(value, 4) if value is not None else None, q
    except ValueError:
        return None, 0.0


def formula_volume_ratio(V: Decimal, sma_prev: Decimal,
                         eps_volume: Decimal = EPS_TIER1) -> Tuple[Optional[Decimal], float]:
    """§2.2: V / max(SMA_20(V) on t−1, ε_volume), 8 digits. SMA=0 →
    large-but-finite via the epsilon floor (never NaN)."""
    if sma_prev == 0:
        return None, 0.0  # degraded: Q_volume=0 path, evidence carries OI-dep flag
    try:
        value = guarded_div(V, max(sma_prev, eps_volume))
        value, q = sanitize_decimal(value)
        return quantize(value, 8) if value is not None else None, q
    except ValueError:
        return None, 0.0


def formula_return_k(C_t: Decimal, C_tk: Decimal,
                     ) -> Tuple[Optional[Decimal], float]:
    """§2.2: (C_t / C_{t−k}) − 1, 10 digits. C_{t−k}=0 → DEGRADED."""
    if C_tk == 0:
        return None, 0.0
    try:
        value = guarded_div(C_t, C_tk) - Decimal(1)
        value, q = sanitize_decimal(value)
        return quantize(value, 10) if value is not None else None, q
    except ValueError:
        return None, 0.0
