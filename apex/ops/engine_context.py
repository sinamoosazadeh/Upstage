"""CP-14 store-context boundary helpers (Section 9.5 P1/P2/P7).

Artifact validation is lazy: missing classifier parameters never prevent boot,
status, bootstrap, or repair. PAPER accounting reads environment-tagged ledger
outcomes only. Freshness is a wiring measurement, not a reinterpretation of
raw availability_time. D22 catch-up admission is a separate concern.
"""
from __future__ import annotations

import hashlib
import math
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

from apex.config import Config, PARAMS_DIR, PARAMS_FILES, _YamlSubsetParser, load_params
from apex.data_catalog.contracts import CORE10_SYMBOLS, parse_utc_ms
from apex.engines.e11_regime import engine as E11
from apex.identity.canonical_json import canonical_json
from apex.ops.bootstrap_service import close_time_ms
from apex.ops.plan_bridge import BridgeError

ENGINE_ORDER = ("E01", "E02", "E12", "E04", "E03", "E10", "E09", "E05",
                "E06", "E11", "E07", "E08")
DEFAULT_TRAINING_SEED = 20260917
DEFAULT_TRAINING_TIMEFRAMES = ("1h", "4h")
DEFAULT_TRAINING_MAX_MINUTES = 20.0




def native_size_request(*, capital: Any, exposure: Any, risk_state: str,
                        atr: Any, stop_distance: Any, entry: Any,
                        contract_multiplier: Any, quantity_step: Any) -> dict:
    """D34/045: read-only request bound, never an authorization."""
    from apex.risk.kernel import size, ladder_state_for, RISK_LADDER_STATES
    from apex.engines.e04_volatility.engine import EPS
    a = measured_number(atr, "SIZE_INPUT_UNAVAILABLE")
    if a <= EPS:
        raise BridgeError("SIZE_INPUT_UNAVAILABLE", "ATR <= native E04 EPS")
    c = measured_number(capital, "SIZE_INPUT_UNAVAILABLE", lower=0)
    e = measured_number(exposure, "SIZE_INPUT_UNAVAILABLE", lower=0)
    price = measured_number(entry, "SIZE_INPUT_UNAVAILABLE", lower=0)
    multiplier = measured_number(contract_multiplier, "SIZE_INPUT_UNAVAILABLE", lower=0)
    step = measured_number(quantity_step, "SIZE_INPUT_UNAVAILABLE", lower=0)
    stop = measured_number(stop_distance, "SIZE_INPUT_UNAVAILABLE", lower=0)
    if min(c, price, multiplier, step, stop) <= 0 or e > c or risk_state not in RISK_LADDER_STATES:
        raise BridgeError("SIZE_INPUT_UNAVAILABLE", "invalid capital/exposure/geometry/spec/ladder")
    derived = ladder_state_for(e/c)
    state = max((risk_state, derived), key=RISK_LADDER_STATES.index)
    request = size(capital=c, stop_distance=stop, contract_multiplier=multiplier,
                   min_quantity=step, risk_state=state, atr_cap=1/a)
    return {"sized_quantity": request["sized_quantity"], "atr_cap": 1/a,
            "proposed_notional": request["sized_quantity"] * price * multiplier,
            "is_risk_increase": True, "request_only": True,
            "risk_state": state, "native_sizing": request}


def paper_close_marks(held_symbols: Any, observations: Mapping[str, Mapping], *, as_of_ms: int) -> dict:
    """D34/046: one PIT account mark set, independent of candidate TF."""
    sla = float(load_params()["quality_weights"]["freshness_threshold_seconds"]["1m"])
    marks, provenance = {}, {}
    for symbol in sorted(set(held_symbols)):
        row = observations.get(symbol)
        if not row or row.get("symbol") != symbol or row.get("timeframe") != "1m" or row.get("status") != "CLOSED":
            raise BridgeError("PAPER_MARK_UNAVAILABLE", symbol)
        try:
            opening, availability, receipt = (int(row[k]) for k in ("open_time_ms", "availability_ms", "receipt_ms"))
            close = close_time_ms(opening, "1m")
        except (KeyError, TypeError, ValueError) as exc:
            raise BridgeError("PAPER_MARK_UNAVAILABLE", symbol) from exc
        if (max(close, availability, receipt) > as_of_ms
                or (as_of_ms-close)/1000 > sla or max(0, receipt-close)/1000 > sla):
            raise BridgeError("PAPER_MARK_UNAVAILABLE", symbol + ": stale/future")
        price = measured_number(row.get("close_price"), "PAPER_MARK_UNAVAILABLE", lower=0)
        if price == 0:
            raise BridgeError("PAPER_MARK_UNAVAILABLE", symbol)
        marks[symbol] = price
        provenance[symbol] = {"model": "PAPER_CLOSE_MARK", "close_ms": close,
                              "availability_ms": availability, "receipt_ms": receipt}
    return {"marks": marks, "mark_provenance": provenance, "as_of_ms": as_of_ms,
            "mark_model": "PAPER_CLOSE_MARK"}


def uncertainty_trend(current: Mapping, previous: Mapping | None, *, is_risk_increase: bool) -> bool:
    """D34/047: strict same-cell consecutive/version-matched comparator."""
    from apex.fabric.conflict import _OUTPUT_RESTRICTION
    try:
        if previous is None:
            raise ValueError("missing prior state")
        for key in ("symbol", "timeframe", "parameter_version", "classifier_version"):
            if not current.get(key) or current[key] != previous.get(key):
                raise ValueError("comparison scope/version mismatch")
        if current.get("closed") is not True or previous.get("closed") is not True:
            raise ValueError("non-CLOSED state")
        if close_time_ms(int(previous["close_ms"]), current["timeframe"]) != int(current["close_ms"]):
            raise ValueError("not consecutive CLOSED observations")
        now_h = measured_number(current.get("entropy"), "UNCERTAINTY_TREND_UNAVAILABLE", lower=0)
        prev_h = measured_number(previous.get("entropy"), "UNCERTAINTY_TREND_UNAVAILABLE", lower=0)
        return (now_h > prev_h or _OUTPUT_RESTRICTION[current["conflict_state"]]
                > _OUTPUT_RESTRICTION[previous["conflict_state"]])
    except (KeyError, TypeError, ValueError, BridgeError) as exc:
        if not is_risk_increase:
            return False  # not permission: predicate is irrelevant for reductions
        raise BridgeError("UNCERTAINTY_TREND_UNAVAILABLE", str(exc)) from exc


def adv_base_volume(bars: Any, *, as_of_ms: int, volume_unit: str,
                    contract_multiplier: Any = None) -> float:
    """D34/044: native CLOSED 1h volume over 30 complete UTC days / 30."""
    import datetime as dt
    end = int(dt.datetime.fromtimestamp(as_of_ms/1000, dt.timezone.utc)
              .replace(hour=0, minute=0, second=0, microsecond=0).timestamp()*1000)
    start = end - 30*86400000
    if volume_unit not in ("BASE", "CONTRACT"):
        raise BridgeError("ADV_UNAVAILABLE", "unverified volume units")
    multiplier = 1. if volume_unit == "BASE" else measured_number(contract_multiplier, "ADV_UNAVAILABLE", lower=0)
    if multiplier <= 0:
        raise BridgeError("ADV_UNAVAILABLE", "invalid multiplier")
    selected = {}
    for bar in bars:
        opening = bar.get("open_time_ms")
        if not isinstance(opening, int):
            raise BridgeError("ADV_UNAVAILABLE", "missing candle timestamp")
        if not start <= opening < end:
            continue
        if (opening in selected or bar.get("timeframe") != "1h" or bar.get("status") != "CLOSED"
                or not isinstance(bar.get("availability_ms"), int) or bar["availability_ms"] > as_of_ms):
            raise BridgeError("ADV_UNAVAILABLE", "duplicate/nonclosed/non-PIT 1h volume")
        selected[opening] = measured_number(bar.get("volume"), "ADV_UNAVAILABLE", lower=0) * multiplier
    if set(selected) != set(range(start, end, 3600000)):
        raise BridgeError("ADV_UNAVAILABLE", "30 complete contiguous UTC days required")
    result = sum(selected.values())/30
    if result <= 0:
        raise BridgeError("ADV_UNAVAILABLE", "nonpositive daily volume")
    return result


def forecast_cost_projection(*, quantity: Any, entry: Any, stop_distance: Any,
                             contract_multiplier: Any, adv: Any, commission_rate: Any,
                             funding: Mapping, direction: int, start_ms: int,
                             end_ms: int, spread_available: bool) -> dict:
    """D34/044: explicit rate/schedule/units; native slippage and R floor."""
    from apex.decision.pipeline import slippage_model
    from apex.forecast.logistic import cost_r_floor
    from apex.research.governance import GOVERNED_DEFAULTS
    qty = measured_number(quantity, "COST_MODEL_UNAVAILABLE", lower=0)
    price = measured_number(entry, "COST_MODEL_UNAVAILABLE", lower=0)
    stop = measured_number(stop_distance, "COST_MODEL_UNAVAILABLE", lower=0)
    multiplier = measured_number(contract_multiplier, "COST_MODEL_UNAVAILABLE", lower=0)
    fee = measured_number(commission_rate, "VENUE_COMMISSION_RATE_UNAVAILABLE", lower=0)
    if min(price, stop, multiplier) <= 0 or direction not in (-1, 1) or end_ms <= start_ms:
        raise BridgeError("COST_MODEL_UNAVAILABLE", "invalid geometry/direction/horizon")
    try:
        rate = measured_number(funding.get("rate"), "FUNDING_UNAVAILABLE")
        interval = measured_number(funding.get("interval_ms"), "FUNDING_UNAVAILABLE", lower=1)
        next_time = funding["next_settlement_ms"]
        if (not isinstance(next_time, int) or interval != int(interval)
                or not isinstance(funding.get("observed_at_ms"), int)
                or funding["observed_at_ms"] > start_ms or not funding.get("source")):
            raise ValueError("unverified funding phase/PIT/provenance")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise BridgeError("FUNDING_UNAVAILABLE", str(exc)) from exc
    interval = int(interval)
    first = next_time + max(0, (start_ms-next_time)//interval + 1)*interval
    count = max(0, (end_ms-first)//interval+1)
    funding_fraction = max(0., direction*rate)*count
    alpha = next(float(p.l1_default) for p in GOVERNED_DEFAULTS if p.name == "alpha_spread")
    adv_value = None if adv is None else measured_number(adv, "ADV_UNAVAILABLE", lower=0)
    slip = slippage_model(order_size=qty*multiplier, adv=adv_value, alpha_spread=alpha)
    fractions = [2*fee, funding_fraction]
    if slip["available"]:
        fractions.append(slip["slippage"])
    else:
        # Unknown term remains typed unavailable in the native cost record;
        # only known terms are summed, with the governed total-cost floor.
        spread_available = False
    cost = sum(fractions)*price/stop
    if not spread_available:
        cost = max(cost, cost_r_floor())
    return {"forecast_cost_r": cost, "spread_available": spread_available,
            "slippage": slip, "funding_settlements": count,
            "funding_fraction": funding_fraction, "round_trip_fee_fraction": 2*fee,
            "funding_source": dict(funding)}


def realized_loss_projection(outcomes: Any, *, capital: Any, as_of_ms: int,
                             owner_reviews: Any = ()) -> dict:
    """D34/048: replay canonical completed outcomes, including breach latches.

    A replay of immutable outcomes reconstructs breaches even if profits
    recovered before the next cycle. The caller must resolve corrections or
    refuse; duplicate identities never silently double-count a trade.
    """
    import datetime as dt
    from apex.risk.kernel import frozen_risk_params
    C = _paper_decimal(capital, "PAPER capital", positive=True)
    def periods(stamp):
        d = dt.datetime.fromtimestamp(stamp/1000, dt.timezone.utc)
        return d.date().isoformat(), d.isocalendar()[:2]
    rows, seen = [], set()
    for index, row in enumerate(outcomes):
        if row.get("environment") not in ("PAPER", "LIVE", "RESEARCH", "BACKTEST"):
            raise BridgeError("PAPER_LOSS_UNAVAILABLE", "outcome environment unknown")
        if row["environment"] != "PAPER":
            continue
        if not isinstance(row.get("timestamp_ms"), int):
            raise BridgeError("PAPER_LOSS_UNAVAILABLE", "outcome timestamp unknown")
        if row["timestamp_ms"] > as_of_ms:
            continue
        identity = row.get("outcome_id")
        if not identity or identity in seen or row.get("completed") is not True:
            raise BridgeError("PAPER_LOSS_UNAVAILABLE", "duplicate/incomplete/unknown outcome")
        seen.add(identity)
        rows.append((row["timestamp_ms"], index, _paper_decimal(row.get("pnl"), "realized net P/L")))
    rows.sort(key=lambda r: (r[0], r[1]))
    base = C - sum((r[2] for r in rows), Decimal(0))
    if base <= 0:
        raise BridgeError("PAPER_LOSS_UNAVAILABLE", "invalid opening capital")
    caps = frozen_risk_params()
    daily, weekly, streak, breaches = {}, {}, 0, {}
    for stamp, _, pnl in rows:
        day, week = periods(stamp)
        base += pnl
        if base <= 0:
            raise BridgeError("PAPER_LOSS_UNAVAILABLE", "historical capital nonpositive")
        daily[day] = daily.get(day, Decimal(0)) + pnl
        weekly[week] = weekly.get(week, Decimal(0)) + pnl
        streak = streak + 1 if pnl < 0 else 0
        for kind, condition in (
            ("DAILY_LOSS_LIMIT", max(Decimal(0), -daily[day])/base > Decimal(str(caps["daily_loss_cap"]))),
            ("WEEKLY_LOSS_LIMIT", max(Decimal(0), -weekly[week])/base > Decimal(str(caps["weekly_loss_cap"]))),
            ("CONSECUTIVE_LOSSES", streak > caps["consecutive_loss_halt"])):
            if condition:
                breaches[kind] = stamp
    day, week = periods(as_of_ms)
    reviews = {}
    for review in owner_reviews:
        if review.get("actor") != "OWNER" or review.get("kind") not in ("WEEKLY_LOSS_LIMIT", "CONSECUTIVE_LOSSES") or not isinstance(review.get("timestamp_ms"), int):
            raise BridgeError("CIRCUIT_RESET_UNAVAILABLE", "invalid OWNER review provenance")
        if review["timestamp_ms"] <= as_of_ms:
            reviews[review["kind"]] = max(reviews.get(review["kind"], -1), review["timestamp_ms"])
    active = []
    for kind, stamp in breaches.items():
        old_day, old_week = periods(stamp)
        reset = (day != old_day if kind == "DAILY_LOSS_LIMIT" else
                 (week != old_week and reviews.get(kind, -1) > stamp) if kind == "WEEKLY_LOSS_LIMIT" else
                 reviews.get(kind, -1) > stamp)
        if not reset:
            active.append(kind)
    return {"realized_daily_loss_fraction": float(max(Decimal(0), -daily.get(day, Decimal(0)))/C),
            "realized_weekly_loss_fraction": float(max(Decimal(0), -weekly.get(week, Decimal(0)))/C),
            "consecutive_losses": streak, "loss_latches": sorted(active),
            "circuit_breaker_engaged": bool(active), "breach_timestamps": breaches}


def measured_number(value: Any, reason: str, *, lower: float | None = None,
                    upper: float | None = None) -> float:
    """No coercion of absent/bool/nonfinite measurements into permissions."""
    try:
        if value is None or isinstance(value, (bool, str)):
            raise ValueError("missing or untyped measurement")
        result = float(value)
        if not math.isfinite(result) or (lower is not None and result < lower) or (upper is not None and result > upper):
            raise ValueError("measurement outside domain")
        return result
    except (ValueError, TypeError, OverflowError) as exc:
        raise BridgeError(reason, str(value)) from exc


def window_quality_projection(qualities: Any) -> dict:
    """D33/037: native minimum veto and weighted mean, never last-bar only."""
    from apex.quality.vector import calc_window_quality
    pairs = [(measured_number(q, "QUALITY_PROVENANCE_UNAVAILABLE", lower=0, upper=1),
              measured_number(age, "QUALITY_PROVENANCE_UNAVAILABLE", lower=0))
             for q, age in qualities]
    value, reason, _ = calc_window_quality(pairs)
    if value is None:
        raise BridgeError("WINDOW_QUALITY_UNAVAILABLE", reason)
    return {"q_raw": value, "data_trust": value, "window_qualities": pairs}


def mtf_projection(symbol: str, timeframe: str, as_of_ms: int,
                   states: Mapping[str, Mapping[str, Any]]) -> dict:
    """D33/038: pattern-independent E09 alignment, including 1mo vacuity."""
    from apex.setup.family_sf_fvg_sweep_rev import relative_mtf
    from apex.fabric.context import MTF_STATE_SCORES
    scope = relative_mtf(timeframe)
    required = list(dict.fromkeys(tf for tf in (scope["intermediate"], scope["htf"]) if tf))
    directions, closes = [], {}
    for tf in [timeframe, *required]:
        state = states.get(tf)
        if (not isinstance(state, Mapping) or state.get("symbol") != symbol
                or state.get("timeframe") != tf or state.get("closed") is not True
                or not isinstance(state.get("as_of"), int) or state["as_of"] > as_of_ms):
            raise BridgeError("MTF_INSUFFICIENT", tf)
        if state.get("freshness_ok") is not True:
            raise BridgeError("MTF_STALE", tf)
        bias = measured_number(state.get("bias"), "MTF_INSUFFICIENT", lower=-1, upper=1)
        directions.append(0 if abs(bias) < .05 else (1 if bias > 0 else -1))
        closes[tf] = state["as_of"]
    nonzero = set(directions) - {0}
    if not required:
        label = "ALIGNED"
    elif len(nonzero) == 2:
        label = "CONFLICTING"
    elif 0 not in directions:
        label = "ALIGNED"
    else:
        label = "PARTIALLY_ALIGNED"
    return {"mtf_state": label, "mtf_align": MTF_STATE_SCORES[label],
            "available_closes": closes, "relative_mtf": scope}


def component_projection(admitted: Any, direction: int) -> dict:
    """D33/039. Input is the fabric's admitted refs, not unfiltered events."""
    from apex.fabric.context import COMPONENT_ENGINE
    from apex.setup.family_sf_fvg_sweep_rev import REQUIRED_EVIDENCE
    if direction not in (-1, 1):
        raise BridgeError("PATTERN_DIRECTION_UNAVAILABLE", str(direction))
    refs = list(admitted)
    si, qi = {}, {}
    for component, engine in COMPONENT_ENGINE.items():
        group = [r for r in refs if r.engine_id == engine]
        if not group:
            if engine in REQUIRED_EVIDENCE:
                raise BridgeError("REQUIRED_EVIDENCE_MISSING", engine)
            continue  # proven absence in the admitted set, not missing quality
        if any(r.state != "ACTIVE" or r.direction not in (-1, 0, 1) for r in group):
            raise BridgeError("COMPONENT_EVIDENCE_INVALID", engine)
        si[component] = float(any(r.direction in (0, direction) for r in group))
        qi[component] = min(measured_number(r.quality, "COMPONENT_QUALITY_UNAVAILABLE", lower=0, upper=1)
                            for r in group)
    return {"s_i": si, "q_i": qi}


def confirmation_quality(contributors: Any) -> float:
    """D33/039: explicit actual E07 contributors; no .9 startup default."""
    rows = list(contributors)
    if not rows:
        raise BridgeError("E07_CONFIRMATION_QUALITY_UNAVAILABLE", "no contributors")
    for row in rows:
        if row.get("engine_id") not in ("E01", "E02", "E03", "E05") or not row.get("evidence_id"):
            raise BridgeError("E07_CONFIRMATION_QUALITY_UNAVAILABLE", "contributor provenance")
    return sum(measured_number(row.get("quality"), "E07_CONFIRMATION_QUALITY_UNAVAILABLE", lower=0, upper=1)
               for row in rows) / len(rows)


def select_native_pattern(hits: Any, entities: Mapping[str, Any], bars: Any) -> Any:
    """D33/040 hybrid: direction conflicts veto; rank same-side hits only."""
    from apex.pattern.detect import assert_scoring_admissible, is_invalidated
    eligible = []
    for hit in hits:
        entity = entities.get(hit.pattern_id)
        if entity is None or entity.lifecycle_status != "ACTIVE":
            continue  # recorded catalogue/admission exclusion, never promotion
        assert_scoring_admissible(entity)
        if hit.direction not in (-1, 1) or not 0 <= hit.index < len(bars):
            raise BridgeError("PATTERN_CONTEXT_INVALID", hit.pattern_id)
        measured_number(hit.strength, "PATTERN_STRENGTH_UNAVAILABLE", lower=0, upper=1)
        if any(is_invalidated(hit, float(b["c"])) for b in bars[hit.index:]):
            continue
        eligible.append(hit)
    if not eligible:
        raise BridgeError("PATTERN_NOT_DETECTED", "no admitted still-valid confirmed hit")
    if len({h.direction for h in eligible}) != 1:
        raise BridgeError("PATTERN_SELECTION_AMBIGUOUS", "opposing admitted patterns")
    return sorted(eligible, key=lambda h: (-h.index, -h.strength, h.pattern_id))[0]


def temporal_validity_projection(validity: Any) -> float:
    """D33/041: explicit native category, distinct from the core flag."""
    if validity == "VALID":
        return 1.
    if validity in ("DEGRADED", "INVALID"):
        return 0.
    raise BridgeError("TEMPORAL_VALIDITY_UNAVAILABLE", str(validity))


def forecast_features(*, scores: Mapping[str, float], trend_bias: Any,
                      momentum_z: Any, regime_entropy: Any, vol_quantile: Any,
                      temporal_core: Any, rr: Any, cost_r: Any) -> dict:
    """D32/D33 full forecast vector; known optional absence is binary false."""
    from apex.forecast.logistic import logistic_bootstrap_p
    if not isinstance(temporal_core, bool):
        raise BridgeError("TEMPORAL_CORE_UNAVAILABLE", str(temporal_core))
    values = {}
    for feature, component in (("s_struct", "structure"), ("s_liq", "liquidity"),
                               ("s_vol", "volume"), ("s_fvg", "fvg"), ("s_ob", "orderblock")):
        if component in ("structure", "liquidity", "fvg") and component not in scores:
            raise BridgeError("REQUIRED_EVIDENCE_MISSING", component)
        value = scores.get(component, 0.)
        if value not in (0., 1.):
            raise BridgeError("FORECAST_FEATURE_INVALID", feature)
        values[feature] = float(value)
    rr = measured_number(rr, "FORECAST_GEOMETRY_UNAVAILABLE", lower=0)
    cost_r = measured_number(cost_r, "COST_MODEL_UNAVAILABLE", lower=0)
    if rr <= 0 or cost_r <= 0:
        raise BridgeError("FORECAST_LOG_DOMAIN_UNAVAILABLE", "RR and cost must be positive")
    values.update(trend_stack=measured_number(trend_bias, "TREND_UNAVAILABLE", lower=-1, upper=1),
                  momentum_z=measured_number(momentum_z, "MOMENTUM_UNAVAILABLE"),
                  regime_entropy=measured_number(regime_entropy, "REGIME_UNAVAILABLE", lower=0),
                  vol_quantile=measured_number(vol_quantile, "VOL_QUANTILE_UNAVAILABLE", lower=0, upper=1),
                  temporal_core_flag=float(temporal_core), log_rr=math.log(rr), log_cost_R=math.log(cost_r))
    logistic_bootstrap_p(values)  # use, never bypass, the native validator
    return values


def paper_bootstrap_uncertainty(regime_state: Mapping[str, Any], *, environment: str) -> dict:
    """D34's explicitly uncalibrated PAPER-only three-component model."""
    if environment != "PAPER":
        raise BridgeError("PAPER_UNCERTAINTY_NOT_LIVE", environment)
    try:
        snapshot = regime_state["snapshot_id"]
        probs = regime_state["probs"]
        values = list(probs.values()) if isinstance(probs, Mapping) else list(probs)
        if (not snapshot or len(values) != 9 or any(isinstance(v, bool) or not isinstance(v, (int, float))
                or not math.isfinite(v) or not 0 <= v <= 1 for v in values)
                or not math.isclose(sum(values), 1., abs_tol=1e-9)):
            raise ValueError("invalid same-snapshot probabilities")
    except (KeyError, TypeError, ValueError) as exc:
        raise BridgeError("FORECAST_UNCERTAINTY_UNAVAILABLE", str(exc)) from exc
    return {"model_version": "cp14_paper_bootstrap_uncertainty-v1",
            "e11_snapshot_id": snapshot, "calibration": .5, "ood": .5,
            "disagreement": 1. - max(values),
            **{k: {"state": "UNAVAILABLE"} for k in
               ("sampling", "data_quality", "regime_shift", "tail_risk")}}


def forecast_vol_quantile(states: Any, current: Any, *, timeframe: str) -> float:
    """D32: mid-rank of native HV30, prior same-cell E04 states only.

    The caller owns the per-cell native stream; no reconstructed HV or E04
    regime threshold availability is used. Cap by native bar history before
    discarding nonfinite HV measurements; current/future states never count.
    """
    from apex.engines.e04_volatility import engine as volatility
    try:
        seconds = volatility.TF_SECONDS[timeframe]
        value, stamp = float(current.hv30), int(current.as_of)
        window = max(30, int(round(volatility.E04_DEFAULTS["regime_window_days"]
                                   * 86400.0 / seconds)))
        prior = sorted((s for s in states if int(s.as_of) < stamp),
                       key=lambda s: int(s.as_of))[-window:]
        if len({int(s.as_of) for s in prior}) != len(prior):
            raise ValueError("duplicate native state timestamp")
        history = [float(s.hv30) for s in prior if math.isfinite(float(s.hv30))]
        if not math.isfinite(value) or len(history) < volatility.E04_DEFAULTS["min_bars"]:
            raise ValueError("nonfinite current HV or fewer than 50 finite prior states")
    except (KeyError, AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise BridgeError("VOL_QUANTILE_UNAVAILABLE", str(exc)) from exc
    return (sum(h < value for h in history) + .5 * sum(h == value for h in history)) / len(history)


def classifier_hash(W: Any, b: Any, seed: int) -> str:
    return hashlib.sha256(canonical_json(
        {"W": W, "b": b, "seed": seed}).encode("utf-8")).hexdigest()


def validate_classifier(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """P2: validate the complete artifact before any E11 computation."""
    required = {"W", "b", "K", "label_delay_candles", "seed", "training_window",
                "sample_count", "training_query_sha256", "artifact_sha256"}
    try:
        if not isinstance(artifact, Mapping) or set(artifact) != required:
            raise ValueError("artifact schema")
        if artifact["K"] != 9 or artifact["label_delay_candles"] != 48:
            raise ValueError("K or label delay")
        if type(artifact["seed"]) is not int:
            raise ValueError("seed")
        if type(artifact["sample_count"]) is not int or artifact["sample_count"] <= 0:
            raise ValueError("sample_count")
        W = np.asarray(artifact["W"], dtype=float)
        b = np.asarray(artifact["b"], dtype=float)
        if W.shape != (9, 8) or b.shape != (9,):
            raise ValueError("W/b shape")
        if not np.isfinite(W).all() or not np.isfinite(b).all():
            raise ValueError("non-finite W/b")
        window = artifact["training_window"]
        if set(window) != {"start", "end", "timeframes", "symbols", "default_timeframes", "default_symbols"}:
            raise ValueError("training_window")
        if (window["default_timeframes"] != list(DEFAULT_TRAINING_TIMEFRAMES)
                or window["default_symbols"] != list(CORE10_SYMBOLS)):
            raise ValueError("training scope defaults")
        scoped = training_scope(window["timeframes"], window["symbols"])
        if list(scoped[0]) != window["timeframes"] or list(scoped[1]) != window["symbols"]:
            raise ValueError("training scope ordering")
        if parse_utc_ms(window["start"]) > parse_utc_ms(window["end"]):
            raise ValueError("reversed training_window")
        query_hash = artifact["training_query_sha256"]
        if not isinstance(query_hash, str) or len(query_hash) != 64 or any(
                c not in "0123456789abcdef" for c in query_hash):
            raise ValueError("training_query_sha256")
        if classifier_hash(artifact["W"], artifact["b"], artifact["seed"]) != artifact["artifact_sha256"]:
            raise ValueError("artifact_sha256 mismatch")
    except (ValueError, TypeError, KeyError, OverflowError, BridgeError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", f"E11 {exc}") from exc
    return dict(artifact)


def load_classifier(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path is not None else PARAMS_DIR / "e11_classifier_v1.yaml"
    try:
        artifact = _YamlSubsetParser(path.read_text(encoding="utf-8")).parse()
    except (OSError, ValueError) as exc:
        # Do not print paths, file contents, or untrusted YAML in a refusal.
        raise BridgeError("CONFIGURATION_INVALID", "E11 artifact missing or unreadable") from exc
    return validate_classifier(artifact)


def freshness(window: Any, timeframe: str, *,
              receipt_time: float | None = None) -> dict[str, Any]:
    """D14 exact seconds and iff; never mutate a MarketObservation."""
    if window is None or len(window) == 0:
        raise BridgeError("NO_MARKET_DATA", "empty CLOSED candle window")
    receipt = time.time() if receipt_time is None else float(receipt_time)
    if not math.isfinite(receipt):
        raise BridgeError("CONFIGURATION_INVALID", "non-finite receipt time")
    open_ms = int(parse_utc_ms(window[-1].timestamp).timestamp() * 1000)
    closed = close_time_ms(open_ms, timeframe)
    staleness = max(0.0, receipt - closed / 1000.0)
    sla = float(load_params()["quality_weights"]["freshness_threshold_seconds"][timeframe])
    return {"staleness_seconds": staleness, "freshness_sla_seconds": sla,
            "freshness_ok": staleness <= sla,
            "receipt_time_ms": int(receipt * 1000), "close_time_ms": closed}


def load_paper_account() -> dict[str, Any]:
    account = load_params()["paper_account"]
    try:
        if set(account) != {"capital_usdt", "simulated_margin"}:
            raise ValueError("paper account schema")
        capital = Decimal(str(account["capital_usdt"]))
        if not capital.is_finite() or capital <= 0:
            raise ValueError("paper capital")
        margin = account["simulated_margin"]
        if set(margin) != {"warning_fraction", "action_fraction",
                           "liquidation_approach_fraction"}:
            raise ValueError("simulated margin schema")
        values = [float(margin[k]) for k in ("warning_fraction", "action_fraction",
                                            "liquidation_approach_fraction")]
        if not 1 >= values[0] > values[1] > values[2] >= 0:
            raise ValueError("simulated margin ordering")
    except (ValueError, TypeError, KeyError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", "invalid PAPER account") from exc
    return account


async def paper_balance(ledger: Any) -> Decimal:
    """D4: YAML capital plus realized PAPER P/L, never LIVE outcomes.

    OUTCOME is the existing LedgerWriter.append_outcome envelope. No ledger
    schema or execution-stage change is needed for this read-only projection.
    """
    total = Decimal(str(load_paper_account()["capital_usdt"]))
    for entry in await ledger.read_ledger():
        if entry.event_type != "OUTCOME":
            continue
        outcome = entry.raw.get("payload", {}).get("outcome", {})
        environment = outcome.get("context", {}).get("environment")
        if environment not in ("PAPER", "LIVE", "RESEARCH", "BACKTEST"):
            raise BridgeError("CONFIGURATION_INVALID", "outcome environment unavailable")
        if environment != "PAPER":
            continue
        amount = entry.raw.get("pnl")
        if amount in (None, ""):
            raise BridgeError("CONFIGURATION_INVALID", "PAPER realized P/L unavailable")
        delta = Decimal(str(amount))
        if not delta.is_finite():
            raise BridgeError("CONFIGURATION_INVALID", "non-finite PAPER realized P/L")
        total += delta
    return total


def _paper_decimal(value: Any, name: str, *, positive: bool = False) -> Decimal:
    try:
        if value is None or isinstance(value, bool):
            raise ValueError("missing number")
        number = Decimal(str(value))
        if not number.is_finite() or (positive and number <= 0):
            raise ValueError("invalid number")
        return number
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise BridgeError("PAPER_MARGIN_INPUT_INVALID", name) from exc


def paper_reservation_proxy(*, capital: Any, positions: list[dict], orders: list[dict],
                            environment: str) -> dict:
    """D29, also binding on CP-15's durable-state adapter. No leverage input.

    Positions carry signed quantity, mark_price and contract_multiplier.
    Orders carry known state, reduce_only/is_risk_increase, submitted and
    filled quantities, reference_price and contract_multiplier. All are facts,
    not permissions or synthetic defaults. Exposure caps are evaluated elsewhere.
    """
    from apex.risk.kernel import margin_health_state
    if environment != "PAPER":
        raise BridgeError("PAPER_ACCOUNT_NOT_LIVE", "reservation proxy is PAPER-only")
    C = _paper_decimal(capital, "capital", positive=True)
    open_notional = Decimal(0)
    for position in positions:
        quantity = _paper_decimal(position.get("quantity"), "position quantity")
        if quantity == 0:
            continue
        price = _paper_decimal(position.get("mark_price"), "position mark", positive=True)
        multiplier = _paper_decimal(position.get("contract_multiplier"), "contract multiplier", positive=True)
        open_notional += abs(quantity) * price * multiplier
    pending = Decimal(0)
    active = {"SUBMITTING", "ACKNOWLEDGED", "PARTIAL"}
    filled = {"FILLED", "PROTECTED", "MANAGED", "CLOSED"}
    cancelled = {"CANCELLED", "REJECTED"}
    for order in orders:
        state = order.get("state")
        if state not in active | filled | cancelled:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", str(state))
        if type(order.get("reduce_only")) is not bool or type(order.get("is_risk_increase")) is not bool:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "order risk classification missing")
        if order["reduce_only"] or not order["is_risk_increase"] or state in cancelled:
            continue
        quantity = _paper_decimal(order.get("quantity"), "order quantity", positive=True)
        done = _paper_decimal(order.get("filled_quantity"), "filled quantity")
        if not 0 <= done <= quantity:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "inconsistent filled quantity")
        remaining = quantity - done
        if state in filled and remaining != 0:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "full-fill state lacks complete fill records")
        if remaining:
            price = _paper_decimal(order.get("reference_price"), "pending order price", positive=True)
            multiplier = _paper_decimal(order.get("contract_multiplier"), "contract multiplier", positive=True)
            pending += remaining * price * multiplier
    N = open_notional + pending
    health = (C - N) / C
    if not Decimal(0) <= health <= Decimal(1):
        raise BridgeError("PAPER_MARGIN_OUT_OF_RANGE", "reservation exceeds capital; no clipping")
    return {"capital": C, "open_notional": open_notional, "pending_notional": pending,
            "reserved_notional": N, "margin_health_fraction": health,
            "margin_model": "PAPER_RESERVATION_PROXY_D29", "environment": "PAPER",
            "margin_status": margin_health_state(float(health), environment="PAPER")}


async def paper_account_state(ledger: Any, *, marks: Mapping[str, Any],
                              contract_specs: Mapping[str, Mapping], environment: str) -> dict:
    """Read-only D29 projection of the real append-only PAPER ledger.

    No inference of an order's completion from its age, no leverage discount,
    no unidentified fill, no PAPER capital in LIVE. Marks are supplied by the
    governed fresh CLOSED data-plane reader, not entry-price fallbacks.
    """
    if environment != "PAPER":
        raise BridgeError("PAPER_ACCOUNT_NOT_LIVE", "ledger projection is PAPER-only")
    if ledger is None:
        raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "ledger not bound")
    entries = await ledger.read_ledger()
    plans = await ledger.trade_plans()
    identities = {}
    for plan in plans:
        for key in {plan["proposal_id"], "i-" + plan["proposal_id"][-12:]}:
            if key in identities and identities[key]["proposal_id"] != plan["proposal_id"]:
                raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "ambiguous execution identity")
            identities[key] = plan
    transitions, submissions, environments = {}, {}, {}
    for entry in entries:
        if entry.event_type != "FSM_TRANSITION":
            continue
        payload = entry.raw.get("payload", {})
        env = payload.get("environment")
        if env not in ("PAPER", "LIVE", "RESEARCH", "BACKTEST"):
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "FSM environment unavailable")
        if entry.intent_id in environments and environments[entry.intent_id] != env:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "FSM environment conflict")
        environments[entry.intent_id] = env
        history = transitions.setdefault(entry.intent_id, [])
        history.append(payload.get("to_state"))
        if payload.get("trigger") == "SUBMIT_ORDER":
            if entry.intent_id in submissions:
                raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "multiple submissions for one intent")
            submissions[entry.intent_id] = payload.get("evidence", {})
    for plan in plans:
        if plan["environment"] != "PAPER" or plan["decision"] == "REJECT":
            continue
        if not any(k in transitions for k in (plan["proposal_id"], "i-" + plan["proposal_id"][-12:])):
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "materialized plan lacks order state")
    net, filled_qty, pnl = {}, {}, []
    for entry in entries:
        payload = entry.raw.get("payload", {})
        if entry.event_type == "OUTCOME":
            env = payload.get("outcome", {}).get("context", {}).get("environment")
            if env not in ("PAPER", "LIVE", "RESEARCH", "BACKTEST"):
                raise BridgeError("PAPER_MARGIN_INPUT_INVALID", "outcome environment unavailable")
            if env == "PAPER":
                pnl.append((entry.timestamp, _paper_decimal(entry.raw.get("pnl"), "realized PAPER P/L")))
        if entry.event_type != "FILL":
            continue
        plan = identities.get(entry.intent_id)
        env = environments.get(entry.intent_id)
        if plan is not None and env != plan["environment"]:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "fill plan/FSM environment mismatch")
        if env is None:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "fill has no environment-tagged order state")
        if env != "PAPER":
            continue
        side, symbol = payload.get("side"), payload.get("symbol")
        if side not in ("BUY_OPEN", "SELL_OPEN", "BUY_CLOSE", "SELL_CLOSE") or not symbol:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "fill symbol/side missing")
        qty = _paper_decimal(entry.quantity, "fill quantity", positive=True)
        net[symbol] = net.get(symbol, Decimal(0)) + (qty if side.startswith("BUY") else -qty)
        if side.endswith("_OPEN"):
            filled_qty[entry.intent_id] = filled_qty.get(entry.intent_id, Decimal(0)) + qty
    def multiplier(symbol):
        return _paper_decimal(contract_specs.get(symbol, {}).get("contract_multiplier"), "contract multiplier", positive=True)
    positions = [{"symbol": symbol, "quantity": qty, "mark_price": marks.get(symbol),
                  "contract_multiplier": multiplier(symbol)} for symbol, qty in net.items() if qty != 0]
    orders = []
    for intent, history in transitions.items():
        if environments[intent] != "PAPER":
            continue
        state = history[-1]
        if state == "RECONCILED":
            settled = [s for s in history[:-1] if s in ("CLOSED", "CANCELLED", "REJECTED")]
            if not settled:
                raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "reconciled order has no settled origin")
            state = settled[-1]
        submit = submissions.get(intent)
        if submit is None:
            if state in ("REJECTED", "CANCELLED"):
                continue  # explicit pre-submission refusal; no venue order
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "submission facts missing")
        symbol = submit.get("symbol")
        # Frozen FSM SUBMIT_ORDER submits phase=entry. Protective/exit orders
        # use the separate reduce-only path and never this entry transition.
        orders.append({"state": state, "symbol": symbol, "reduce_only": False,
                       "is_risk_increase": True, "quantity": submit.get("quantity"),
                       "filled_quantity": filled_qty.get(intent, Decimal(0)),
                       "reference_price": submit.get("price"),
                       "contract_multiplier": multiplier(symbol)})
    capital = Decimal(str(load_paper_account()["capital_usdt"])) + sum((v for _, v in pnl), Decimal(0))
    result = paper_reservation_proxy(capital=capital, positions=positions, orders=orders, environment=environment)
    return {**result, "positions": net, "realized_outcomes": pnl,
            "per_symbol_exposure": {p["symbol"]: abs(p["quantity"]) * _paper_decimal(p["mark_price"], "mark", positive=True)
                                     * p["contract_multiplier"] for p in positions}, "orders": orders}


def training_rule0(vector: Mapping[str, float], *, turbulence: float) -> str:
    """D21(b): the exact ordered training tree, with no entropy branch.

    The 15.5 training threshold is explicitly owner-governed by D21. Runtime
    keeps E11's full tree and its unchanged Section 6 parameters.
    """
    v = vector
    if turbulence >= 15.5 or v["volatility"] >= 0.85:
        return "CRISIS"
    if v["expansion"] >= 0.6 and v["participation"] >= 0.4:
        return "EXPANSION"
    if v["trendiness"] >= 0.6 and v["expansion"] >= 0.5:
        return "TREND_EXPANSION"
    if v["trendiness"] >= 0.6 and v["compression"] >= 0.6:
        return "TREND_CONTRACTION"
    if v["trendiness"] >= 0.6:
        return "TREND"
    if v["compression"] >= 0.6 and v["volatility"] <= 0.4:
        return "COMPRESSION"
    if v["participation"] <= 0.25 and v["liquidity_stability"] <= 0.3:
        return "CHOP"
    return "RANGE"


def delayed_training_labels(rule0: list[str], structural_confirmation: list[bool]
                            ) -> list[str]:
    """D21(c/d): only t whose t+48 is present; no label for the tail."""
    if len(rule0) != len(structural_confirmation):
        raise ValueError("training label/confirmation lengths differ")
    if any(label not in E11.REGIMES or label == "TRANSITION" for label in rule0):
        raise ValueError("rule0 must contain only the eight non-entropy labels")
    return [rule0[t] if any(structural_confirmation[t + 1:t + 49])
            else "TRANSITION" for t in range(max(0, len(rule0) - 48))]


def load_decision_runtime(*, environment: str | None = None) -> dict[str, Any]:
    """D25 governed policy, shared by PAPER/LIVE, never an account source."""
    from apex.data_catalog.contracts import TIMEFRAMES_14
    environment = Config().apex_env if environment is None else environment
    try:
        p = load_params()["decision_runtime"]
        if set(p) - {"paper_bootstrap"} != {"capital_hard_cap_fraction", "p_min_tf", "c_min"}:
            raise ValueError("schema")
        if set(p["p_min_tf"]) != set(TIMEFRAMES_14):
            raise ValueError("timeframes")
        expected = {tf: 0.55 for tf in TIMEFRAMES_14}
        expected.update({"1m": 0.52, "1d": 0.50})
        if p["p_min_tf"] != expected or p["capital_hard_cap_fraction"] != 0.60 or p["c_min"] != 0.50:
            raise ValueError("SL-12/D25 twin mismatch")
        core = {k: v for k, v in p.items() if k != "paper_bootstrap"}
        if environment == "PAPER":
            core["paper_bootstrap"] = validate_paper_bootstrap(p["paper_bootstrap"])
        return core
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", "decision-runtime policy unavailable or invalid") from exc


def validate_paper_bootstrap(section: Any) -> dict[str, Any]:
    """D28: governed YAML values, never a runtime constant-weight fallback."""
    try:
        if not isinstance(section, Mapping) or set(section) != {"arbitration_weights"}:
            raise ValueError("bootstrap schema")
        weights = section["arbitration_weights"]
        if not isinstance(weights, Mapping) or set(weights) != {"quality", "alignment", "recency"}:
            raise ValueError("weights schema")
        if any(type(w) not in (int, float) or not math.isfinite(w) or w < 0 for w in weights.values()):
            raise ValueError("weights must be finite and nonnegative")
        if sum(weights.values()) <= 0:
            raise ValueError("empty weights")
        return {"arbitration_weights": dict(weights)}
    except (ValueError, TypeError, KeyError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", "invalid PAPER bootstrap policy") from exc


def regime_uncertainty_input(state: Mapping[str, Any]) -> float:
    """D27: Ch.8 confidence complement; never raw or normalized entropy."""
    try:
        probs = [float(v) for v in state["probs"]]
        if len(probs) != 9 or not all(math.isfinite(p) and 0 <= p <= 1 for p in probs):
            raise ValueError("invalid probabilities")
        if not math.isclose(sum(probs), 1.0, rel_tol=0.0, abs_tol=E11.EPS):
            raise ValueError("invalid simplex")
        return 1.0 - max(probs)
    except (KeyError, TypeError, ValueError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", "E11 probabilities unavailable or invalid") from exc


def paper_package_binding(*, environment: str, params_dir: str | Path | None = None) -> dict | None:
    """D28 filename-bound canonical YAML values; LIVE never reads bootstrap.

    Canonical bytes = canonical_json({filename: parsed_yaml, ...}).encode('utf-8').
    The optional classifier is included once; no random/time/process inputs.
    """
    if environment != "PAPER":
        return None
    directory = Path(params_dir) if params_dir is not None else PARAMS_DIR
    documents = {}
    try:
        for filename in sorted(set(PARAMS_FILES.values())):
            path = directory / filename
            if filename == "e11_classifier_v1.yaml" and not path.exists():
                continue
            documents[filename] = _YamlSubsetParser(path.read_text(encoding="utf-8")).parse()
        policy = validate_paper_bootstrap(documents["decision_runtime_v1.yaml"]["paper_bootstrap"])
        if "e11_classifier_v1.yaml" in documents:
            validate_classifier(documents["e11_classifier_v1.yaml"])
        digest = hashlib.sha256(canonical_json(documents).encode("utf-8")).hexdigest()
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", "governed PAPER package unreadable") from exc
    return {"parameter_package_id": "cp14_paper_bootstrap-v1.0.0-" + digest[:12],
            "package_version": "v1.0.0", "parameter_sha256": digest,
            "parameter_files": sorted(documents), "environment": "PAPER",
            "paper_bootstrap": policy}


def paper_bootstrap_inputs(*, environment: str, family_record: Mapping | None,
                           params_dir: str | Path | None = None) -> dict | None:
    """D28: a verified absent registry row is distinct from a read failure."""
    package = paper_package_binding(environment=environment, params_dir=params_dir)
    if package is None:
        return None
    if family_record is None:
        status, origin = "ACCUMULATING", "NO_REGISTRY_RECORD"
    else:
        status, origin = family_record.get("status"), "SETUP_FAMILY_REGISTRY"
        if status not in ("ACCUMULATING", "PROMOTED", "DEGRADING", "DEMOTED"):
            raise BridgeError("FAMILY_REGISTRY_INVALID", "existing family status is invalid")
    return {"package": package, "family_status": status, "family_status_source": origin,
            "arbitration": {"composite_weights": dict(package["paper_bootstrap"]["arbitration_weights"]),
                            "alignment": "UNAVAILABLE", "recency": "UNAVAILABLE"}}


async def read_family_record(store: Any, family_id: str, as_of: str) -> dict | None:
    """Read owner registry snapshots; never write an ACCUMULATING fallback.

    Existing snapshot quality_state.family_registry maps family_id to a
    record with status. Later snapshots omitting a family do not erase it.
    """
    import json
    parse_utc_ms(as_of)
    rows = await (await store.db.execute(
        "SELECT snapshot_id,vector_quality_state FROM snapshot_pit WHERE "
        "source_state='SETUP_FAMILY_REGISTRY' AND as_of<=? ORDER BY as_of DESC,rowid DESC",
        (as_of,))).fetchall()
    for snapshot_id, payload in rows:
        try:
            registry = json.loads(payload)["family_registry"]
            if not isinstance(registry, dict):
                raise ValueError("registry schema")
            if family_id in registry:
                record = registry[family_id]
                if not isinstance(record, dict) or record.get("status") not in (
                        "ACCUMULATING", "PROMOTED", "DEGRADING", "DEMOTED"):
                    raise ValueError("family schema")
                return {**record, "registry_snapshot_id": snapshot_id}
        except (ValueError, KeyError, TypeError) as exc:
            raise BridgeError("FAMILY_REGISTRY_INVALID", "cannot establish family lifecycle") from exc
    return None


async def collect_public_venue_facts(symbol: str, *, client: Any = None,
                                   now: Callable[[], float] = time.time) -> dict:
    """D28 public exchangeInfo/funding reads only; no signing fallback.

    Only explicit exchangeInfo fields are admitted. In particular, lack of
    commissionRate/takerCommissionRate never authorizes a fixture/default fee.
    """
    if client is None:
        import aiohttp
        from apex.data_catalog.ingest.toobit_public import ToobitPublicClient
        async with aiohttp.ClientSession() as session:
            return await collect_public_venue_facts(symbol, client=ToobitPublicClient(session=session), now=now)
    from apex.execution.toobit_map import to_wire_symbol
    try:
        info = await client.get_exchange_info()
    except Exception as exc:
        raise BridgeError("VENUE_EXCHANGE_INFO_UNAVAILABLE", symbol) from exc
    rows = info.get("symbols") if isinstance(info, Mapping) else None
    if not isinstance(rows, list):
        raise BridgeError("VENUE_CONTRACT_UNAVAILABLE", symbol)
    matches = [r for r in rows if isinstance(r, dict) and r.get("symbol") in (symbol, to_wire_symbol(symbol))]
    if len(matches) != 1:
        raise BridgeError("VENUE_CONTRACT_UNAVAILABLE", symbol)
    record = matches[0]
    def number(value, name, *, positive=False):
        try:
            if isinstance(value, bool) or value is None:
                raise ValueError("missing numeric fact")
            parsed = Decimal(str(value))
            if not parsed.is_finite() or (positive and parsed <= 0):
                raise ValueError("invalid numeric fact")
            return parsed
        except (ValueError, TypeError, ArithmeticError) as exc:
            raise BridgeError("VENUE_" + name + "_UNAVAILABLE", symbol) from exc
    # Do not interpret maker-only commission as the liquidity-taking fee.
    if "takerCommissionRate" in record:
        fee_key, commission = "takerCommissionRate", record["takerCommissionRate"]
    else:
        fee_key, commission = "commissionRate", record.get("commissionRate")
        if isinstance(commission, Mapping):
            fee_key, commission = "commissionRate.takerCommissionRate", commission.get("takerCommissionRate")
    commission = number(commission, "COMMISSION_RATE")
    multiplier = number(record.get("contractMultiplier"), "CONTRACT_MULTIPLIER", positive=True)
    contract_type = record.get("contractType")
    if contract_type not in ("PERPETUAL", "CURRENT_QUARTER", "NEXT_QUARTER", "DELIVERY"):
        raise BridgeError("VENUE_CONTRACT_TYPE_UNAVAILABLE", symbol)
    expiry = record.get("deliveryDate")
    if contract_type == "PERPETUAL":
        if expiry not in (None, 0, "0"):
            raise BridgeError("VENUE_EXPIRY_UNAVAILABLE", "conflicting perpetual expiry")
        expiry_time = None  # explicit PERPETUAL semantics, not absent contract type
    else:
        expiry_ms = number(expiry, "EXPIRY", positive=True)
        if expiry_ms != int(expiry_ms):
            raise BridgeError("VENUE_EXPIRY_UNAVAILABLE", symbol)
        try:
            expiry_time = _ms_to_iso(int(expiry_ms))
        except (ValueError, OverflowError, OSError) as exc:
            raise BridgeError("VENUE_EXPIRY_UNAVAILABLE", symbol) from exc
    try:
        funding, _ = await client.get_funding_rate(symbol)
    except Exception as exc:
        raise BridgeError("VENUE_FUNDING_RATE_UNAVAILABLE", symbol) from exc
    funding = number(funding, "FUNDING_RATE")
    observed_at = _ms_to_iso(int(now() * 1000))
    sources = {"exchange_info": {"endpoint": "/api/v1/exchangeInfo", "record": record},
               "funding": {"endpoint": "/api/v1/futures/fundingRate", "rate": funding}}
    return {"symbol": symbol, "observed_at": observed_at, "commission_rate": commission,
            "funding_rate": funding, "contract_multiplier": multiplier,
            "contract_type": contract_type, "expiry_time": expiry_time,
            "commission_field": fee_key, "sources": sources,
            "source_sha256": hashlib.sha256(canonical_json(sources).encode("utf-8")).hexdigest()}


async def persist_public_venue_facts(store: Any, symbol: str, *, environment: str,
                                    client: Any = None,
                                    now: Callable[[], float] = time.time) -> dict:
    package = paper_package_binding(environment=environment)
    if package is None:
        raise BridgeError("LIVE_GOVERNANCE_UNAVAILABLE", "PAPER publisher is not a LIVE package source")
    refusal = None
    try:
        facts = await collect_public_venue_facts(symbol, client=client, now=now)
        payload, observed_at = {"venue_facts": facts}, facts["observed_at"]
    except BridgeError as exc:
        # Append failure too: a later missing fact must not resurrect an old
        # successful measurement. This never affects another symbol's row.
        refusal = exc
        observed_at = _ms_to_iso(int(now() * 1000))
        payload = {"venue_fact_refusal": {"symbol": symbol, "observed_at": observed_at,
                                          "reason": exc.reason}}
    bound = {"source_state": "PUBLIC_VENUE_FACTS", **payload,
             "parameter_package_id": package["parameter_package_id"]}
    identity = hashlib.sha256(canonical_json(bound).encode("utf-8")).hexdigest()
    exists = await (await store.db.execute("SELECT snapshot_id FROM snapshot_pit WHERE snapshot_id=?", (identity,))).fetchone()
    if exists is None:
        await store.insert_snapshot({"snapshot_id": identity, "as_of": observed_at,
            "symbol_scope": [symbol], "source_state": "PUBLIC_VENUE_FACTS",
            "parameter_package_id": package["parameter_package_id"], "code_version": "CP14-D28-v1",
            "quality_state": payload})
    if refusal is not None:
        raise refusal
    return facts


async def read_public_venue_facts(store: Any, symbol: str, as_of: str) -> dict:
    import json
    parse_utc_ms(as_of)
    rows = await (await store.db.execute(
        "SELECT snapshot_id,vector_quality_state,as_of,parameter_package_id FROM snapshot_pit WHERE source_state='PUBLIC_VENUE_FACTS' "
        "AND symbol_scope=? AND as_of<=? ORDER BY as_of DESC,rowid DESC LIMIT 1", (symbol, as_of))).fetchall()
    try:
        payload = json.loads(rows[0][1])
        bound = {"source_state": "PUBLIC_VENUE_FACTS", **payload, "parameter_package_id": rows[0][3]}
        expected = hashlib.sha256(canonical_json(bound).encode("utf-8")).hexdigest()
        if expected != rows[0][0]:
            raise ValueError("venue facts payload binding mismatch")
        failed = "venue_fact_refusal" in payload
        facts = payload["venue_fact_refusal" if failed else "venue_facts"]
        if facts["observed_at"] != rows[0][2] or facts["symbol"] != symbol or parse_utc_ms(facts["observed_at"]) > parse_utc_ms(as_of):
            raise ValueError("venue facts identity/PIT mismatch")
        if failed:
            raise BridgeError(facts["reason"], symbol)
        if facts["source_sha256"] != hashlib.sha256(canonical_json(facts["sources"]).encode("utf-8")).hexdigest():
            raise ValueError("venue facts source hash mismatch")
        return facts
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise BridgeError("VENUE_FACTS_UNAVAILABLE", symbol) from exc


def participation_input(volume_z: float, oi_z: float | None, oi_state: str) -> dict[str, Any]:
    """Owner D23, shared by training and serve; no imputed OI series."""
    if oi_state not in ("AVAILABLE", "MISSING", "STALE", "INVALID", "DEGRADED"):
        raise BridgeError("CONFIGURATION_INVALID", "unknown OI state")
    if volume_z is None or not math.isfinite(float(volume_z)):
        raise BridgeError("CONFIGURATION_INVALID", "VolumeZ unavailable")
    partial = oi_state != "AVAILABLE"
    if not partial and (oi_z is None or not math.isfinite(float(oi_z))):
        raise BridgeError("CONFIGURATION_INVALID", "AVAILABLE OI lacks OI_z")
    raw = float(volume_z) if partial else 0.6 * float(volume_z) + 0.4 * float(oi_z)
    return {"participation_raw": raw, "oi_state": oi_state,
            "contributing_features": {"participation": "PARTIAL" if partial else "COMPLETE"}}


# Engine namespaces are the authorities; this module only maps their contracts.
from apex.engines.e01_structure import engine as E01
from apex.engines.e02_liquidity import engine as E02
from apex.engines.e03_volume import engine as E03
from apex.engines.e04_volatility import engine as E04
from apex.engines.e05_fvg import engine as E05
from apex.engines.e06_orderblock import engine as E06
from apex.engines.e07_rtm import engine as E07
from apex.engines.e08_wyckoff import engine as E08
from apex.engines.e09_trend import engine as E09
from apex.engines.e10_momentum import engine as E10
from apex.engines.e12_temporal import engine as E12
from apex.ops.bootstrap_service import _iso_to_ms, _ms_to_iso


def closed_engine_window(window: Any, timeframe: str) -> list[Any]:
    """Open-time store observations -> close-boundary engine observations.

    This is an in-memory projection only. CORRECTED current market rows are
    final observations, while their persisted lifecycle remains CORRECTED.
    """
    from dataclasses import replace
    result = []
    for index, obs in enumerate(window):
        if obs.status not in ("CLOSED", "CORRECTED"):
            raise BridgeError("DATA_QUALITY_QX", "non-final candle")
        result.append(replace(obs, timestamp=_ms_to_iso(close_time_ms(
            _iso_to_ms(obs.timestamp), timeframe)), status="CLOSED", sequence=index))
    return result


def _trend_swings(structure: Mapping[str, Any], window: list[Any]) -> list[dict[str, Any]]:
    """E01 HIGH/LOW -> E09 HH/HL/LH/LL, confirmed through t-1 only."""
    indices = {obs.timestamp: i for i, obs in enumerate(window)}
    previous: dict[str, float] = {}
    result = []
    for swing in sorted(structure["swings"], key=lambda s: s["index"]):
        side, price = swing["type"], float(swing["price"])
        old = previous.get(side)
        previous[side] = price
        confirmation = indices[swing["confirmed_at"]]
        if old is None or confirmation >= len(window) - 1:
            continue  # no comparison predecessor / E09's explicit t-1 boundary
        label = ("EQ" if price == old else
                 ("HH" if price > old else "LH") if side == "HIGH" else
                 ("HL" if price > old else "LL"))
        result.append({"idx": swing["index"], "price": price, "type": label,
                       "confirmed_at_idx": confirmation})
    return result


def atr_z_input(state: Any, prior_atr14: list[float]) -> float:
    """D26-A: E04's published ATR14, E11's Method-B lag-one reference.

    No new ATR, lookback/minimum constant, clipping or sigmoid. The caller
    supplies only prior observations of this same symbol/timeframe cell.
    """
    current = float(state.atr14_wilder)
    reference = prior_atr14[-E11.W_180D_H1:]
    mu, sigma = E11.rolling_method_b_reference(current, reference)
    return (current - mu) / (sigma + E11.EPS)



CONFIRMED_SWEEP_EVENT_TYPES = frozenset({"EV_LIQ_005", "EV_LIQ_006"})
SWEEP_PREREQUISITES = frozenset({"P1_valid_level", "P2_penetration", "P3_rejection",
                                "P4_temporal", "P5_data_quality"})


def structure_projection(raw_window: list[Any], symbol: str, timeframe: str) -> dict:
    window = closed_engine_window(raw_window, timeframe)
    if not window:
        raise BridgeError("NO_MARKET_DATA", "empty confirmation window")
    duration = (close_time_ms(_iso_to_ms(raw_window[-1].timestamp), timeframe)
                - _iso_to_ms(raw_window[-1].timestamp)) // 1000
    params = E01.get_params()
    params["tick_size"] = E01.resolve_tick_size(symbol)
    return E01.run_pipeline([E01.observation_to_candle(o, timeframe, duration) for o in window], params)


def structural_confirmation(raw_window: list[Any], symbol: str, timeframe: str, *, result: dict | None = None) -> bool:
    result = structure_projection(raw_window, symbol, timeframe) if result is None else result
    return any(event["candle_index"] == len(raw_window) - 1 and event["event_type"].startswith(
        ("EV_STR_007", "EV_STR_008", "EV_STR_009", "EV_STR_010")) for event in result["events"])


def contiguous_label_horizon(window: list[Any], index: int, timeframe: str) -> bool:
    """Exactly t+48 calendar-aware closes; a retained-row offset is not time."""
    horizon = window[index:index + 49]
    return len(horizon) == 49 and all(
        close_time_ms(_iso_to_ms(a.timestamp), timeframe) == _iso_to_ms(b.timestamp)
        for a, b in zip(horizon, horizon[1:]))


def liquidity_inputs(liquidity: Any) -> dict:
    """D26-B: actual E02 live levels and confirmed retained-window sweeps.

    The native retained-window constant is shared via volume_profile_bars;
    WickOnly and incomplete prerequisite sets never count as sweeps.
    """
    retained = [bar for bar in liquidity.candles[-liquidity.volume_profile_bars:] if bar.is_closed]
    if not retained:
        raise BridgeError("INVALID_E11_HISTORY", "empty CLOSED E02 retained window")
    current = retained[-1].bar_index
    live = [level for level in liquidity.levels.values() if level.fate in ("ACTIVE", "STRENGTHENED")]
    density = age = 0.0
    if len(live) >= 2:
        span = max(level.price for level in live) - min(level.price for level in live)
        if not math.isfinite(span) or span <= 0:
            raise BridgeError("INVALID_E11_FEATURE", "nonpositive live-level price span")
        density = len(live) / span
        age = float(max(current - level.last_touch for level in live))
        if age < 0:
            raise BridgeError("INVALID_E11_FEATURE", "future level touch")
    indices = {bar.bar_index for bar in retained}
    sweeps = [event for event in liquidity.events
              if event.get("event_type") in CONFIRMED_SWEEP_EVENT_TYPES and event.get("at_bar") in indices
              and SWEEP_PREREQUISITES.issubset(event.get("payload", {}).get("prereq", {}))
              and all(event["payload"]["prereq"][key] is True for key in SWEEP_PREREQUISITES)]
    rate = len(sweeps) / len(retained)
    return {"level_density": density, "age_score": age, "sweep_rate": rate,
            "liquidity_raw": density * age / (1.0 + rate)}

def upstream_frame(raw_window: list[Any], symbol: str, timeframe: str,
                   *, emit: bool = False,
                   atr14_history: list[float] | None = None,
                   structure_result: dict | None = None,
                   volatility_stream: dict | None = None) -> dict[str, Any]:
    """P1's first seven engines, in order, with explicit producer projections.

    A 300-bar engine window is the existing paper runtime window. The E11
    normalization history is assembled separately, over all prior frames.
    """
    if not raw_window:
        raise BridgeError("NO_MARKET_DATA", "empty engine window")
    window = closed_engine_window(raw_window, timeframe)
    end = window[-1].timestamp
    duration = (close_time_ms(_iso_to_ms(raw_window[-1].timestamp), timeframe)
                - _iso_to_ms(raw_window[-1].timestamp)) // 1000
    base = {"window": window}
    events = []
    order = []
    def collect(code, cls, context):
        order.append(code)
        if emit:
            events.extend(cls().compute(symbol, timeframe, end, context))

    params = E01.get_params()
    params["tick_size"] = E01.resolve_tick_size(symbol)
    collect("E01", E01.E01StructureEngine, base)
    candles = [E01.observation_to_candle(o, timeframe, duration) for o in window]
    structure = E01.run_pipeline(candles, params) if structure_result is None else structure_result
    bos_events = [ev for ev in structure["events"] if ev["event_type"].startswith(
        ("EV_STR_007", "EV_STR_008"))]
    structural_events = [ev for ev in structure["events"] if ev["event_type"].startswith(
        ("EV_STR_007", "EV_STR_008", "EV_STR_009", "EV_STR_010"))]
    bos = bos_events[-1] if bos_events else None
    collect("E02", E02.E02LiquidityEngine, base)
    liquidity = E02.run_engine([E02.observation_to_candle(o) for o in window])
    collect("E12", E12.E12TemporalEngine, base)
    temporal = E12.run_engine([E12.observation_to_candle(o) for o in window])["temporal_state"]
    order.append("E04")
    bars = [E04.observation_to_bar(o, timeframe) for o in window]
    if volatility_stream is None:
        volatility = E04.run_engine(bars, timeframe=timeframe)
    else:
        # Native chronological E04, never a partial/reimplemented indicator.
        # Drain only observations already reached by this feature timeline.
        for bar in volatility_stream["pending"]:
            evidence = volatility_stream["engine"].ingest_bar(bar)
            if evidence is not None:
                volatility_stream["evidence"].append(evidence)
        volatility_stream["pending"].clear()
        retained = [e for e in volatility_stream["evidence"] if bars[0]["ts"] <= e.state.as_of <= bars[-1]["ts"]]
        volatility = {"engine": volatility_stream["engine"], "states": [e.state for e in retained],
                      "events": [event for e in retained for event in e.events], "atr_series": [e.atr_scalar for e in retained]}
    if emit:
        emitter = E04.E04VolatilityEngine()
        quality = emitter._window_quality(window)
        events.extend(emitter._to_evidence(state, symbol, timeframe, quality) for state in volatility["states"] if state.snapshot_id)
    # D26-A supersedes the provisional ATR20 addition. Consume the actual
    # published E04 schema and align by as_of, not emitted-list position.
    atr_by_close = {state.as_of: state.atr14_wilder for state in volatility["states"]}
    atr14 = [atr_by_close.get(_iso_to_ms(o.timestamp)) for o in window]
    atr_prev = [None] + atr14[:-1]
    volume_context = {**base, "atr_prev": atr_prev,
                      "atr_availability_time_ms": [_iso_to_ms(o.timestamp) for o in window]}
    collect("E03", E03.E03VolumeEngine, volume_context)
    volume_bars = [E03.observation_to_bar(o, timeframe, atr_prev[i], None, _iso_to_ms(o.timestamp))
                   for i, o in enumerate(window)]
    volume = E03.run_engine(volume_bars)
    if not volume.emitted or not volatility["states"]:
        raise BridgeError("INSUFFICIENT_HISTORY", "E03/E04 warmup")
    vol = volume.emitted[-1]
    if volume.history_bars[-1]["ts"] != _iso_to_ms(end):
        raise BridgeError("ENGINE_CONTEXT_UNAVAILABLE", "E03 latest candle unavailable")
    vlt = volatility["states"][-1]
    # E10's Candle contract distinguishes open/close. Its generic wrapper
    # adds an interval to timestamp; feeding our close-stamped view would
    # therefore postdate every event. Supply both boundaries explicitly,
    # including calendar-month closes, to the unchanged native driver.
    order.append("E10")
    momentum_bars = [{**E10.observation_to_bar(raw, timeframe), "is_closed": True,
                      "close_time": _iso_to_ms(closed.timestamp)}
                     for raw, closed in zip(raw_window, window)]
    momentum_result = E10.run_engine(momentum_bars, symbol=symbol, interval=timeframe,
                                    volatility_context=vars(vlt))
    momentum = momentum_result["state"]
    if emit and "snapshot_id" in momentum:
        emitter = E10.E10MomentumEngine()
        emitter._last_n_bars = int(momentum_result["n_bars"])
        quality = emitter._window_quality(window)
        events.extend(emitter._to_evidence(event, symbol, timeframe, quality, momentum)
                      for event in momentum_result["events"])
    swings = _trend_swings(structure, window)
    trend_context = {**base, "swings": swings, "atr": vlt.atr14_wilder,
                     "tf_seconds": duration, "bos_event": bos, "oi_state": vol.oi_state}
    collect("E09", E09.E09TrendEngine, trend_context)
    trend = E09.run_engine(bars, swings=swings, atr=vlt.atr14_wilder,
                          tf_seconds=duration, bos_event=bos, oi_state=vol.oi_state)
    # ISSUE-CP14-011 projections are resolved by owner D26-A/B.
    # An explicit empty history is unavailable, never replaced by a fallback.
    prior = ([state.atr14_wilder for state in volatility["states"]
              if state.as_of < _iso_to_ms(end)]
             if atr14_history is None else atr14_history)
    projection_refusals = []
    try:
        atr_z = atr_z_input(vlt, prior)
    except ValueError as exc:
        if not str(exc).startswith("INVALID_E11_HISTORY:"):
            raise
        atr_z = None
        projection_refusals.append("INVALID_E11_HISTORY")
    part = participation_input(vol.volume_z, vol.oi_z, vol.oi_state)
    macro = trend["stack"]["MACRO"]
    raw_trend = sum(weight * (trend["stack"][scale] * macro > 0)
                    for scale, weight in E09.W_STACK_CORRECTED.items())
    is_bos = bool(bos and bos["candle_index"] == len(window) - 1)
    ic = {"trendiness_raw": raw_trend, "vol_ratio": vlt.vol_ratio,
          "expansion_raw": vlt.vol_ratio * is_bos, **liquidity_inputs(liquidity),
          "structure_score": float(bos["strength"]["S"]) if bos else 0.0,
          "momentum_state_raw": E10.momentum_state_projection(momentum)["momentum_state_raw"],
          "atr_z": atr_z, **part}
    return {"window": window, "raw_window": raw_window, "bars": bars, "ic": ic,
            "structure": structure, "structural_events": structural_events,
            "confirmation": any(e["candle_index"] == len(window) - 1 for e in structural_events),
            "liquidity": liquidity, "volume": volume, "volume_bars": volume_bars,
            "volatility": volatility, "vlt": vlt, "atr14": atr14,
            "momentum": momentum, "trend": trend, "temporal": temporal,
            "events": events, "engine_order": order,
            "projection_refusals": projection_refusals}


def complete_engine_bundle(item: Mapping[str, Any], symbol: str, timeframe: str,
                           artifact: Mapping[str, Any], *, rtm_context: Mapping[str, Any]) -> dict:
    """Native twelve-engine assembly from the shared PIT feature timeline.

    No fixture defaults, replacement indicator or incomplete EvidenceEvent.
    Native warmup is represented by missing optional evidence, not invented
    volume/ATR scalars. E06 starts at the actual joint dependency frontier.
    """
    from dataclasses import asdict
    artifact = validate_classifier(artifact)
    for key in ("avg_quality", "mtf_align"):
        value = rtm_context.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
            raise BridgeError("E07_CONTEXT_UNAVAILABLE", key)
    if "vector" not in item:
        raise BridgeError("E11_CONTEXT_UNAVAILABLE", str(item.get("reason", "missing vector")))
    original = item["frame"]
    prior_atr = [state.atr14_wilder for state in original["volatility"]["states"][:-1]]
    frame = upstream_frame(original["raw_window"], symbol, timeframe, emit=True,
        atr14_history=prior_atr, structure_result=original["structure"],
        volatility_stream=item["volatility_stream"])
    # The timeline's IC/history is authoritative, including the full prior
    # ATR reference; emission preparation must not replace it with a slice.
    frame["ic"] = dict(item["ic"])
    events, order = frame["events"], frame["engine_order"]
    window, end = frame["window"], item["as_of"]
    atr_by_idx = {i: value for i, value in enumerate(frame["atr14"]) if value is not None}
    by_time = {_iso_to_ms(obs.timestamp): i for i, obs in enumerate(window)}
    struct = {}
    for event in frame["structural_events"]:
        i = event["candle_index"]
        direction = "UP" if "BULLISH" in event["event_type"] else "DOWN"
        struct.setdefault(i, []).append({"idx": i, "dir": direction, "direction": direction,
            "kind": "BOS" if event["event_type"].startswith(("EV_STR_007", "EV_STR_008")) else "CHoCH",
            "valid_at_idx": i, "confirmed_at_idx": i, "source": event})
    order.append("E05")
    fvg = E05.run_engine([E05.observation_to_bar(o) for o in window], symbol=symbol,
        tick_size=E01.resolve_tick_size(symbol), atr_by_idx=atr_by_idx, bos_by_idx=struct)
    fvg_emitter = E05.E05FVGEngine()
    objects = sorted(fvg["active"] + fvg["history"], key=lambda obj: obj.created_at_idx)
    events.extend(fvg_emitter._to_evidence(obj, symbol, timeframe, fvg_emitter._window_quality(window)) for obj in objects)
    fvg_by_idx = {}
    for obj in objects:
        fvg_by_idx.setdefault(obj.created_at_idx, []).append(asdict(obj))
    volume_by_idx = {}
    for evidence in frame["volume"].emitted:
        source_index = evidence.pit_meta["history_len"]
        source_time = frame["volume"].history_bars[source_index]["ts"]
        volume_by_idx[by_time[source_time]] = dict(vars(evidence))
    volatility_by_idx = {by_time[state.as_of]: {"atr_n": state.atr14_wilder,
        "tr_method": "WILDER", "as_of": state.as_of, "snapshot_id": state.snapshot_id}
        for state in frame["volatility"]["states"] if state.as_of in by_time}
    order.append("E06")
    joint = sorted(set(volume_by_idx) & set(volatility_by_idx))
    if not joint or joint != list(range(joint[0], len(window))):
        raise BridgeError("E06_DEPENDENCY_UNAVAILABLE", "no contiguous mature volume/volatility suffix")
    first = joint[0]
    ob_context = {"window": window[first:],
        "volume_evidence": [volume_by_idx[i] for i in joint],
        "volatility_evidence": [volatility_by_idx[i] for i in joint],
        "struct_events_by_idx": {i-first: [{**e, "valid_at_idx": i-first} for e in es] for i, es in struct.items() if i >= first},
        "fvg_by_idx": {i-first: es for i, es in fvg_by_idx.items() if i >= first}}
    events.extend(E06.E06OrderBlockEngine().compute(symbol, timeframe, end, ob_context))
    order.append("E11")
    candle = E11.observation_to_candle(window[-1], dict(item["ic"]))
    candle.update(prev_close=float(window[-2].close), atr_prev=frame["atr14"][-2],
        timeframe_seconds=(close_time_ms(_iso_to_ms(original["raw_window"][-1].timestamp), timeframe)
                           - _iso_to_ms(original["raw_window"][-1].timestamp)) // 1000)
    regime_context = {"candles": [candle], "W": artifact["W"], "b": artifact["b"],
        "classifier_artifact_sha256": artifact["artifact_sha256"], "history": item["history"],
        "mu0": item["mu"], "Sigma0": item["Sigma"], "prev_mom": item["prev_mom"]}
    regime_engine = E11.E11RegimeEngine()
    events.extend(regime_engine.compute(symbol, timeframe, end, regime_context))
    result = regime_engine._last_result
    state = result["regime_state"]
    if "snapshot_id" not in state:
        raise BridgeError("E11_CONTEXT_UNAVAILABLE", str(state.get("reason", state.get("error", "invalid state"))))
    order.append("E07")
    direction = "UP" if frame["trend"]["bias"] >= 0 else "DOWN"
    confirmations = []
    def confirm(cid, stamp):
        if stamp not in by_time:
            raise BridgeError("E07_CONTEXT_UNAVAILABLE", "confirmation outside retained window")
        confirmations.append({"cid": cid, "t_confirm_ms": stamp,
                              "p_confirm": float(window[by_time[stamp]].close)})
    for i, sources in struct.items():
        for source in sources:
            if source["direction"] == direction:
                confirm(source["kind"].lower(), _iso_to_ms(window[i].timestamp))
    for source in frame["liquidity"].events:
        prerequisites = source.get("payload", {}).get("prereq", {})
        if (source.get("event_type") in CONFIRMED_SWEEP_EVENT_TYPES
                and SWEEP_PREREQUISITES.issubset(prerequisites)
                and all(prerequisites[key] is True for key in SWEEP_PREREQUISITES)):
            i = source["at_bar"]
            if 0 <= i < len(window):
                confirm("sweep", _iso_to_ms(window[i].timestamp))
    for obj in objects:
        if obj.direction == direction:
            confirm("fvg", obj.created_at_ts)
    for i, evidence in volume_by_idx.items():
        if any(str(code).startswith("EV_VOL_001") for code in evidence["events"]):
            confirm("vol_confirm", _iso_to_ms(window[i].timestamp))
    events.extend(E07.E07RTMEngine().compute(symbol, timeframe, end, {
        "window": window, "events": confirmations, "direction": direction,
        "avg_quality": rtm_context["avg_quality"], "mtf_align": rtm_context["mtf_align"],
        "as_of_ms": _iso_to_ms(end), "temporal_provider": E12.E12TemporalProvider()}))
    order.append("E08")
    events.extend(E08.E08WyckoffEngine().compute(symbol, timeframe, end, {"window": window,
        "atr_by_idx": atr_by_idx,
        "vol_ratio_by_idx": {i: ev["volume_ratio"] for i, ev in volume_by_idx.items()},
        "evr_by_idx": {i: ev["evr"] for i, ev in volume_by_idx.items()},
        "structure_by_idx": {i: ("BULL" if es[-1]["direction"] == "UP" else "BEAR") for i, es in struct.items()},
        "bos_by_idx": {i: {"confirmed_at_idx": i, "direction": es[-1]["direction"]} for i, es in struct.items()}}))
    for event in events:
        try:
            event.validate_24_fields()
        except ValueError as exc:
            raise BridgeError("EVIDENCE_CONTEXT_INVALID",
                              f"{event.engine_id} resolution_class={event.resolution_class}: {exc}") from exc
        if _iso_to_ms(event.availability_time) > _iso_to_ms(end):
            raise BridgeError("BRIDGE_PIT_VIOLATION", event.engine_id)
    return {**frame, "feature_vector": item["vector"], "rtm_confirmations": confirmations, "regime_state": state, "e11_result": result,
        "e11_context": {"ic_inputs": dict(item["ic"]), "history_windows": item["history"],
                        "classifier_W": artifact["W"], "classifier_b": artifact["b"],
                        "classifier_artifact_sha256": artifact["artifact_sha256"], "regime_state": state},
        "fvg_objects": objects, "struct_by_idx": struct,
        "volume_by_idx": volume_by_idx, "volatility_by_idx": volatility_by_idx}


CELL_QUERY = ("SELECT symbol,timeframe,MAX(open_time),COUNT(*) FROM market_observation "
              "WHERE candle_status IN ('CLOSED','CORRECTED') GROUP BY symbol,timeframe "
              "ORDER BY symbol,timeframe")
TRAINING_QUERY = canonical_json({
    "cell_discovery": CELL_QUERY,
    "window_reader": "SQLiteStore.get_window(symbol,timeframe,as_of,bars)",
    "window_predicate": "candle_status IN (CLOSED,CORRECTED) AND open_time <= as_of",
    "window_order": "last bars by open_time DESC, returned open_time ASC",
    "closed_filter": "close_time_ms(open_time,timeframe) <= as_of",
    "label_boundary": "49 consecutive CLOSED candles t..t+48 with independent E01 confirmation; D21 unchanged",
    "raw_metadata": "immutable observation_id/content hash binding restores availability_time and OI timestamp; availability<=as_of",
    "E04_replay": "native chronological VolatilityEngineV4, each CLOSED observation once; no future-state reuse",
    "D30_scope": "selected base timeframes 1h/4h and Core-10 symbols only; default 20 cells; one shared runtime classifier",
})
HISTORY_KEYS = {"trend": "trendiness_raw", "vol": "vol_ratio", "exp": "expansion_raw",
                "liq": "liquidity_raw", "part": "participation_raw", "sq": "structure_score"}


class EngineContextProducer:
    """Public store-to-bridge seam, with no fixture or network dependency."""
    def __init__(self, store: Any, *, ledger: Any = None,
                 classifier_path: str | Path | None = None, environment: str | None = None,
                 now: Callable[[], float] = time.time) -> None:
        self.store, self.ledger = store, ledger
        self.classifier_path, self.now = classifier_path, now
        self.environment = Config().apex_env if environment is None else environment
        self.diagnostics: dict[str, Any] = {}
        self._frames: dict[tuple, dict] = {}
        self._raw_lineage: dict[tuple, dict] = {}

    async def prepare_engine_bundle(self, symbol: str, timeframe: str, as_of: str,
                                    *, rtm_context: Mapping[str, Any]) -> dict:
        """Compute and persist a complete native bundle before plan admission.

        Final bridge/risk projection is separate; this method never presents
        an engine-only bundle as all REQUIRED_CONTEXT_KEYS/REQUIRED_RISK_KEYS.
        """
        from dataclasses import replace
        artifact = load_classifier(self.classifier_path)
        rows = await (await self.store.db.execute(
            "SELECT COUNT(*) FROM market_observation WHERE symbol=? AND timeframe=? "
            "AND candle_status IN ('CLOSED','CORRECTED') AND open_time<=?",
            (symbol, timeframe, as_of))).fetchone()
        window = await self.window(symbol, timeframe, as_of, int(rows[0]))
        if not window:
            raise BridgeError("NO_MARKET_DATA", f"{symbol}:{timeframe}")
        last = None
        async for item in self.feature_timeline(symbol, timeframe, window):
            last = item
        if last is None or "vector" not in last:
            raise BridgeError("E11_CONTEXT_UNAVAILABLE", str((last or {}).get("reason", "empty timeline")))
        bundle = complete_engine_bundle(last, symbol, timeframe, artifact, rtm_context=rtm_context)
        lineage = tuple(self._raw_lineage[(symbol, timeframe, obs.timestamp, obs.content_hash())]["observation_id"]
                        for obs in bundle["raw_window"])
        available = max([_iso_to_ms(bundle["window"][-1].timestamp)] + [_iso_to_ms(obs.availability_time) for obs in bundle["raw_window"]])
        events = [replace(event, lineage=tuple(dict.fromkeys((*event.lineage, *lineage))),
                          availability_time=_ms_to_iso(max(_iso_to_ms(event.availability_time), available)))
                  for event in bundle["events"]]
        bundle["events"] = await persist_complete_evidence(self.store, events)
        bundle["raw_observation_ids"] = lineage
        bundle["classifier_artifact_sha256"] = artifact["artifact_sha256"]
        self.diagnostics[f"{symbol}:{timeframe}"] = {"status": "ENGINE_BUNDLE_PREPARED",
            "engine_order": list(bundle["engine_order"]), "evidence_count": len(events),
            "as_of": last["as_of"], "classifier_artifact_sha256": artifact["artifact_sha256"]}
        return bundle

    async def decision_inputs(self, symbol: str, timeframe: str, as_of: str) -> dict:
        """D28 stored governance/venue inputs; not a fabricated complete context."""
        if self.environment != "PAPER":
            raise BridgeError("LIVE_GOVERNANCE_UNAVAILABLE", "PAPER bootstrap is not a LIVE source")
        from apex.setup.family_sf_fvg_sweep_rev import FAMILY_ID
        record = await read_family_record(self.store, FAMILY_ID, as_of)
        governance = paper_bootstrap_inputs(environment=self.environment, family_record=record)
        venue = await read_public_venue_facts(self.store, symbol, as_of)
        return {**governance, "environment": "PAPER", "commission_rate": venue["commission_rate"],
                "funding_rate": venue["funding_rate"], "venue_provenance": venue,
                "contract_specs": {symbol: {k: venue[k] for k in (
                    "contract_multiplier", "contract_type", "expiry_time")}}}

    async def window(self, symbol: str, timeframe: str, as_of: str, bars: int) -> list[Any]:
        end = _iso_to_ms(as_of)
        window = await self.store.get_window(symbol, timeframe, as_of, bars)
        if window is None:
            raise BridgeError("NO_MARKET_DATA", "store returned no window")
        from dataclasses import replace
        window = [o for o in window if close_time_ms(_iso_to_ms(o.timestamp), timeframe) <= end]
        if not window:
            return []
        # get_window is the authoritative bar reader. Its legacy projection
        # substitutes retrieved_at for raw availability and loses OI lineage.
        # Recover ONLY metadata through the immutable identity, never rewrite
        # a market/raw row or substitute the derived close for raw availability.
        rows = await (await self.store.db.execute(
            "SELECT m.open_time,m.observation_id,m.raw_payload_hash,r.content_hash,"
            "r.availability_time,r.oi_timestamp,r.oi_state FROM market_observation m "
            "JOIN raw_observation r ON m.observation_id='obs-'||r.event_id "
            "WHERE m.symbol=? AND m.timeframe=? AND m.candle_status IN ('CLOSED','CORRECTED') "
            "AND m.open_time>=? AND m.open_time<=? ORDER BY m.open_time",
            (symbol, timeframe, window[0].timestamp, window[-1].timestamp))).fetchall()
        metadata = {}
        for row in rows:
            if row[0] in metadata:
                raise BridgeError("RAW_LINEAGE_INVALID", "ambiguous active observation")
            metadata[row[0]] = row
        result = []
        for obs in window:
            row = metadata.get(obs.timestamp)
            if row is None or row[3] != obs.content_hash() or row[2] != hashlib.sha256(row[3].encode()).hexdigest():
                raise BridgeError("RAW_LINEAGE_INVALID", "observation/raw content binding missing")
            if row[4] is None:
                raise BridgeError("RAW_LINEAGE_INVALID", "raw availability unavailable")
            if _iso_to_ms(row[4]) > end:
                continue  # never expose not-yet-available observations
            oi_lag = (max(0., (end - _iso_to_ms(row[5])) / 1000.) if row[5] is not None else None)
            result.append(replace(obs, availability_time=row[4], oi_timestamp=row[5], oi_lag_seconds=oi_lag))
            self._raw_lineage[(symbol, timeframe, obs.timestamp, obs.content_hash())] = {
                "observation_id": row[1], "oi_state": row[6], "availability_time": row[4]}
        return result

    async def _frame_at(self, symbol: str, timeframe: str, as_of: str) -> dict[str, Any]:
        window = await self.window(symbol, timeframe, as_of, 301)
        if len(window) < 51:
            raise BridgeError("INSUFFICIENT_HISTORY", f"{symbol}:{timeframe}")
        window = window[-300:]
        key = (symbol, timeframe, hashlib.sha256(canonical_json(window).encode()).hexdigest())
        if key not in self._frames:
            self._frames[key] = upstream_frame(window, symbol, timeframe)
            if len(self._frames) > 32:
                del self._frames[next(iter(self._frames))]
        return self._frames[key]

    async def feature_timeline(self, symbol: str, timeframe: str, window: list[Any]):
        """Shared PIT training/runtime X_t stream; explicit warmup refusals.

        HTF bias observations are strictly last-closed as of each historical
        close, never current bias projected backward into a training sample.
        """
        history = {key: [] for key in HISTORY_KEYS}
        atr14_history: list[float] | None = None
        seed_state = E11.RegimeEngine()
        mu, sigma, previous_momentum = seed_state.mu, seed_state.Sigma, seed_state.prev_mom
        volatility_stream = {"engine": E04.VolatilityEngineV4(timeframe=timeframe), "pending": [], "evidence": []}
        for index, obs in enumerate(window):
            as_of = _ms_to_iso(close_time_ms(_iso_to_ms(obs.timestamp), timeframe))
            volatility_stream["pending"].append(E04.observation_to_bar(closed_engine_window([obs], timeframe)[0], timeframe))
            if index < 50:
                yield {"index": index, "as_of": as_of, "reason": "UPSTREAM_WARMUP", "confirmation": False}
                continue
            source_window = window[max(0, index - 299):index + 1]
            if any(o.availability_time is None or _iso_to_ms(o.availability_time) > _iso_to_ms(as_of) for o in source_window):
                yield {"index": index, "as_of": as_of, "confirmation": None, "reason": "PIT_VIOLATION"}
                continue
            structure = structure_projection(source_window, symbol, timeframe)
            confirmation = structural_confirmation(source_window, symbol, timeframe, result=structure)
            try:
                frame = upstream_frame(source_window, symbol, timeframe, atr14_history=atr14_history,
                                       structure_result=structure, volatility_stream=volatility_stream)
                # Advance the independent same-cell ATR reference AFTER its
                # lag-one projection, even while another feature is refused.
                if atr14_history is None:
                    atr14_history = [state.atr14_wilder for state in frame["volatility"]["states"]]
                else:
                    atr14_history.append(frame["vlt"].atr14_wilder)
                atr14_history = atr14_history[-E11.W_180D_H1:]
                if frame.get("projection_refusals"):
                    yield {"index": index, "as_of": as_of, "confirmation": confirmation,
                           "reason": ("INVALID_E11_HISTORY" if "INVALID_E11_HISTORY" in frame["projection_refusals"]
                                      else "E11_PROJECTION_UNCONFIGURED"),
                           "projection_refusals": list(frame["projection_refusals"])}
                    continue
                ic = dict(frame["ic"])
                biases = {}
                for label, tf in (("H4", "4h"), ("H1", "1h"), ("M15", "15m")):
                    htf = frame if tf == timeframe else await self._frame_at(symbol, tf, as_of)
                    biases[label] = float(htf["trend"]["bias"])
                ic["bias_per_TF"] = biases
                ic["trendiness_raw"] = sum(w * (frame["trend"]["stack"][scale] * biases["H4"] > 0)
                                             for scale, w in E09.W_STACK_CORRECTED.items())
            except (BridgeError, ValueError) as exc:
                yield {"index": index, "as_of": as_of,
                       "reason": getattr(exc, "reason", str(exc).split(":")[0]), "confirmation": confirmation}
                continue
            item = {"index": index, "as_of": as_of, "ic": ic, "frame": frame,
                    "volatility_stream": volatility_stream,
                    "confirmation": confirmation, "history": {k: list(v) for k, v in history.items()},
                    "mu": mu.copy(), "Sigma": sigma.copy(), "prev_mom": previous_momentum}
            try:
                vector, bias = E11.compute_state_vector(ic, history, previous_momentum)
                x = E11.vector_to_array(vector)
                turbulence = E11.mahalanobis_turbulence(x, mu, sigma)
                item.update(vector=vector, bias=bias, turbulence=turbulence,
                            rule0=training_rule0(vector, turbulence=turbulence))
                mu, sigma = E11.ewma_update(mu, sigma, x)
                previous_momentum = vector["momentum_state"]
            except ValueError as exc:
                item["reason"] = str(exc).split(":")[0]
            yield item
            # Normalization history can contain finite observations even when
            # its old window was degenerate. No invalid X_t updates the EWMA.
            for key, source in HISTORY_KEYS.items():
                history[key].append(float(ic[source]))
                history[key] = history[key][-E11.W_180D_H1:]


class DegenerateTraining(BridgeError):
    def __init__(self, histogram: dict[str, int], excluded: dict[str, int], window: dict):
        self.histogram, self.excluded, self.training_window = histogram, excluded, window
        self.refusing_class = next(name for name in E11.REGIMES if histogram[name] == 0)
        super().__init__("CONFIGURATION_INVALID", f"zero delayed-label members: {self.refusing_class}")


def fit_multinomial(X: list[list[float]], labels: list[str], seed: int) -> tuple[list, list]:
    """Fixed-order full-batch multinomial log-loss descent, nine classes.

    No class reweighting, synthetic members, dropped classes or runtime random
    weights. The optimizer's seeded initialization exists only during training.
    """
    x = np.asarray(X, dtype=float)
    y = np.array([E11.REGIMES.index(label) for label in labels])
    if x.shape != (len(labels), 8) or not np.isfinite(x).all() or not len(labels):
        raise BridgeError("CONFIGURATION_INVALID", "invalid training matrix")
    if len(set(y.tolist())) != 9:
        raise BridgeError("CONFIGURATION_INVALID", "all nine classes required for fitting")
    rng = np.random.default_rng(seed % (2 ** 128))
    W = rng.normal(0.0, 0.01, (9, 8))
    b = np.zeros(9)
    # Deterministic optimization protocol, recorded in ADR-CP14-004.
    for _ in range(2000):
        z = x @ W.T + b
        z -= np.max(z, axis=1, keepdims=True)
        probabilities = np.exp(z)
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        probabilities[np.arange(len(y)), y] -= 1.0
        gradient_W = probabilities.T @ x / len(y)
        gradient_b = probabilities.mean(axis=0)
        W -= 0.2 * gradient_W
        b -= 0.2 * gradient_b
    if not np.isfinite(W).all() or not np.isfinite(b).all():
        raise BridgeError("CONFIGURATION_INVALID", "non-finite fitted parameters")
    return W.tolist(), b.tolist()


def training_scope(timeframes=DEFAULT_TRAINING_TIMEFRAMES, symbols=CORE10_SYMBOLS) -> tuple[tuple, tuple]:
    """D30: only subsets of the two base TFs/Core-10, in canonical order."""
    def selected(value, allowed):
        values = [v.strip() for v in value.split(",")] if isinstance(value, str) else list(value)
        if not values or len(values) != len(set(values)) or any(v not in allowed for v in values):
            raise BridgeError("TRAINING_SCOPE_INVALID", "use base timeframes 1h,4h and Core-10 symbols only")
        return tuple(v for v in allowed if v in values)
    return selected(timeframes, DEFAULT_TRAINING_TIMEFRAMES), selected(symbols, CORE10_SYMBOLS)


def training_time_limit(minutes: float) -> float:
    value = float(minutes)
    if not math.isfinite(value) or value < 0:
        raise BridgeError("TRAINING_LIMIT_INVALID", "max-minutes must be finite and nonnegative")
    return value * 60.0


async def train_classifier(store: Any, *, seed: int = DEFAULT_TRAINING_SEED,
                           now: Callable[[], float] = time.time,
                           timeframes: Any = DEFAULT_TRAINING_TIMEFRAMES,
                           symbols: Any = CORE10_SYMBOLS,
                           max_minutes: float = DEFAULT_TRAINING_MAX_MINUTES,
                           progress: Callable[[dict], None] | None = None,
                           monotonic: Callable[[], float] = time.monotonic) -> tuple[dict, dict]:
    """Train from actual store windows only. No file or fixture fallback."""
    timeframes, symbols = training_scope(timeframes, symbols)
    limit = training_time_limit(max_minutes)
    started = monotonic()
    def check_deadline():
        if monotonic() - started >= limit:
            raise BridgeError("TRAINING_TIME_LIMIT", "D30 maximum elapsed training time reached")
    check_deadline()
    counts = {(r[0], r[1]): r[3] for r in await (await store.db.execute(CELL_QUERY)).fetchall()}
    producer = EngineContextProducer(store, now=now)
    histogram = {name: 0 for name in E11.REGIMES}
    excluded: dict[str, int] = {}
    X, labels, stamps = [], [], []
    end_ms = int(now() * 1000)
    for symbol, timeframe in [(symbol, tf) for symbol in symbols for tf in timeframes]:
        check_deadline()
        cell_start, eligible_before = monotonic(), len(labels)
        count = counts.get((symbol, timeframe), 0)
        window = await producer.window(symbol, timeframe, _ms_to_iso(end_ms), int(count)) if count else []
        def report_cell(kind="cell"):
            if progress:
                progress({"kind": kind, "cell": symbol + ":" + timeframe,
                          "closed_bars": len(window), "eligible_samples": len(labels) - eligible_before,
                          "elapsed_seconds": monotonic() - cell_start})
        report_cell("started")
        if not window:
            excluded["EMPTY_CLOSED_WINDOW"] = excluded.get("EMPTY_CLOSED_WINDOW", 0) + 1
            report_cell()
            continue
        pending = []
        async for item in producer.feature_timeline(symbol, timeframe, window):
            check_deadline()
            report_cell("tick")
            # Keep just the 48 delayed candidates, not full engine states.
            pending.append({key: item[key] for key in ("index", "as_of", "confirmation", "vector", "rule0", "reason") if key in item})
            if len(pending) <= 48:
                continue
            candidate = pending.pop(0)
            if "vector" not in candidate:
                reason = candidate.get("reason", "INVALID_FEATURE")
                excluded[reason] = excluded.get(reason, 0) + 1
                continue
            if not contiguous_label_horizon(window, candidate["index"], timeframe):
                excluded["NONCONTIGUOUS_LABEL_HORIZON"] = excluded.get("NONCONTIGUOUS_LABEL_HORIZON", 0) + 1
                continue
            if any(type(f.get("confirmation")) is not bool for f in pending):
                excluded["LABEL_CONFIRMATION_UNAVAILABLE"] = excluded.get("LABEL_CONFIRMATION_UNAVAILABLE", 0) + 1
                continue
            label = candidate["rule0"] if any(f["confirmation"] for f in pending) else "TRANSITION"
            histogram[label] += 1
            labels.append(label)
            X.append([candidate["vector"][key] for key in E11.VECTOR_KEYS])
            stamps.append(candidate["as_of"])
        excluded["UNFINALIZED_TAIL"] = excluded.get("UNFINALIZED_TAIL", 0) + len(pending)
        report_cell()
    check_deadline()
    training_window = {"start": min(stamps) if stamps else None, "end": max(stamps) if stamps else None,
                       "timeframes": list(timeframes), "symbols": list(symbols),
                       "default_timeframes": list(DEFAULT_TRAINING_TIMEFRAMES), "default_symbols": list(CORE10_SYMBOLS)}
    if any(count == 0 for count in histogram.values()):
        raise DegenerateTraining(histogram, excluded, training_window)
    W, b = fit_multinomial(X, labels, seed)
    check_deadline()
    artifact = {"W": W, "b": b, "K": 9, "label_delay_candles": 48,
                "seed": seed, "training_window": training_window, "sample_count": len(X),
                "training_query_sha256": hashlib.sha256(canonical_json({"protocol": TRAINING_QUERY, "timeframes": timeframes, "symbols": symbols}).encode()).hexdigest(),
                "artifact_sha256": classifier_hash(W, b, seed)}
    validate_classifier(artifact)
    return artifact, {"per_class_counts": histogram, "excluded": excluded}


def _training_worker(connection, sqlite: str, seed: int, timeframes: tuple, symbols: tuple, max_minutes: float):
    """Isolated CPU worker. It never knows an output path or writes artifacts."""
    import asyncio
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def run():
        store = await SQLiteStore(sqlite).open()
        try:
            artifact, report = await train_classifier(store, seed=seed, timeframes=timeframes,
                symbols=symbols, max_minutes=max_minutes, progress=connection.send)
            connection.send({"kind": "result", "artifact": artifact, "report": report})
        except DegenerateTraining as exc:
            connection.send({"kind": "degenerate", "histogram": exc.histogram, "excluded": exc.excluded,
                             "training_window": exc.training_window})
        except BridgeError as exc:
            connection.send({"kind": "error", "reason": exc.reason, "detail": exc.detail})
        except Exception as exc:
            connection.send({"kind": "error", "reason": "TRAINING_WORKER_FAILED", "detail": type(exc).__name__})
        finally:
            await store.close()
    try:
        asyncio.run(run())
    finally:
        connection.close()


async def train_classifier_bounded(sqlite: str, *, seed=DEFAULT_TRAINING_SEED,
        timeframes=DEFAULT_TRAINING_TIMEFRAMES, symbols=CORE10_SYMBOLS,
        max_minutes=DEFAULT_TRAINING_MAX_MINUTES, progress=None) -> tuple[dict, dict]:
    """Hard wall-time supervisor, including CPU-bound native engine calls.

    asyncio.wait_for alone cannot interrupt those calls. Only the parent may
    return a verified artifact to the atomic writer after successful training.
    """
    import asyncio
    import multiprocessing
    scope = training_scope(timeframes, symbols)
    deadline = time.monotonic() + training_time_limit(max_minutes)
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_training_worker, args=(sender, sqlite, seed, *scope, max_minutes))
    current = None
    try:
        process.start()
        sender.close()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if current is not None and progress:
                    progress({**current, "kind": "cell", "status": "ABORTED"})
                raise BridgeError("TRAINING_TIME_LIMIT", "D30 maximum elapsed training time reached")
            ready = await asyncio.to_thread(receiver.poll, min(.1, remaining))
            if not ready:
                if not process.is_alive():
                    raise BridgeError("TRAINING_WORKER_FAILED", "worker exited without a result")
                continue
            try:
                message = receiver.recv()
            except EOFError as exc:
                raise BridgeError("TRAINING_WORKER_FAILED", "worker closed its result channel") from exc
            if time.monotonic() >= deadline:
                raise BridgeError("TRAINING_TIME_LIMIT", "D30 maximum elapsed training time reached")
            kind = message["kind"]
            if kind in ("started", "tick"):
                current = message
            elif kind == "cell":
                if progress:
                    progress(message)
                current = None
            elif kind == "degenerate":
                raise DegenerateTraining(message["histogram"], message["excluded"], message["training_window"])
            elif kind == "error":
                raise BridgeError(message["reason"], message["detail"])
            elif kind == "result":
                validate_classifier(message["artifact"])
                return message["artifact"], message["report"]
    finally:
        sender.close()
        receiver.close()
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            await asyncio.to_thread(process.join, 1.0)
            if process.is_alive():
                process.kill()
                await asyncio.to_thread(process.join, 1.0)
            process.close()


def write_classifier(artifact: dict[str, Any], path: str | Path) -> None:
    """Deterministic supported YAML; atomic replacement only after validation."""
    import json
    import os
    import tempfile
    validate_classifier(artifact)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = "W:\n" + "".join("  - " + json.dumps(row, separators=(",", ":")) + "\n" for row in artifact["W"])
    for key in ("b", "K", "label_delay_candles", "seed"):
        text += key + ": " + json.dumps(artifact[key], separators=(",", ":")) + "\n"
    text += "training_window:\n"
    for key in ("start", "end", "timeframes", "symbols", "default_timeframes", "default_symbols"):
        text += "  " + key + ": " + json.dumps(artifact["training_window"][key]) + "\n"
    for key in ("sample_count", "training_query_sha256", "artifact_sha256"):
        text += key + ": " + json.dumps(artifact[key]) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".e11-", suffix=".yaml", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


EVIDENCE_ENVELOPE = "APEX.CP14.EvidenceEvent.v1"


def evidence_storage_copy(event: Any) -> Any:
    """Full contract in the existing raw TEXT column, no frozen-store edit.

    insert_evidence maps explanation to raw. Only the storage copy carries
    the envelope; the original explanation is preserved inside its payload.
    """
    from dataclasses import asdict, replace
    event.validate_24_fields()
    payload = asdict(event)
    digest = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
    return replace(event, explanation=canonical_json({
        "schema": EVIDENCE_ENVELOPE, "payload_sha256": digest, "event": payload}))


def evidence_from_raw(raw: str) -> Any:
    import json
    from dataclasses import fields
    from apex.data_catalog.contracts import EvidenceEvent, LifecycleState
    try:
        envelope = json.loads(raw)
        if set(envelope) != {"schema", "payload_sha256", "event"} or envelope["schema"] != EVIDENCE_ENVELOPE:
            raise ValueError("complete-event envelope required")
        payload = envelope["event"]
        if set(payload) != {f.name for f in fields(EvidenceEvent)}:
            raise ValueError("complete 24-field payload required")
        if hashlib.sha256(canonical_json(payload).encode()).hexdigest() != envelope["payload_sha256"]:
            raise ValueError("event hash mismatch")
        payload["fate_state"] = LifecycleState(payload["fate_state"])
        payload["feature_dependencies"] = tuple(payload["feature_dependencies"])
        payload["lineage"] = tuple(payload["lineage"])
        event = EvidenceEvent(**payload)
        event.validate_24_fields()
        return event
    except (ValueError, TypeError, KeyError) as exc:
        raise BridgeError("EVIDENCE_CONTEXT_INVALID", "missing or corrupt complete event") from exc


async def read_complete_evidence(store: Any, evidence_ids: list[str]) -> list[Any]:
    """Read in requested order; never reconstruct missing fields from SQL."""
    events = []
    for identity in evidence_ids:
        row = await (await store.db.execute(
            "SELECT raw,engine_id,snapshot_id FROM evidence_event WHERE evidence_id=?",
            (identity,))).fetchone()
        if row is None:
            raise BridgeError("EVIDENCE_CONTEXT_INVALID", "persisted event missing")
        event = evidence_from_raw(row[0])
        if (event.evidence_id, event.engine_id, event.snapshot_id) != (identity, row[1], row[2]):
            raise BridgeError("EVIDENCE_CONTEXT_INVALID", "event envelope/projection mismatch")
        events.append(event)
    return events


async def persist_complete_evidence(store: Any, events: list[Any]) -> list[Any]:
    """Use the canonical public insert, then verify full readback equality."""
    for event in events:
        row = await (await store.db.execute(
            "SELECT raw FROM evidence_event WHERE evidence_id=?",
            (event.evidence_id,))).fetchone()
        if row is not None:
            if canonical_json(evidence_from_raw(row[0])) != canonical_json(event):
                raise BridgeError("EVIDENCE_CONTEXT_INVALID", "evidence identity collision")
        else:
            await store.insert_evidence(evidence_storage_copy(event))
    result = await read_complete_evidence(store, [e.evidence_id for e in events])
    if canonical_json(result) != canonical_json(events):
        raise BridgeError("EVIDENCE_CONTEXT_INVALID", "complete-event round trip mismatch")
    return result


async def collect_public_funding_schedule(symbol: str, *, client: Any = None,
                                          now: Callable[[], float] = time.time) -> dict:
    """D34 additive unsigned read, preserving schedule fields frozen helper drops.

    Only unit-explicit schedule fields are interpreted. A bare rate or an
    ambiguous interval never authorizes an assumed eight-hour schedule.
    """
    if client is None:
        import aiohttp
        from apex.data_catalog.ingest.toobit_public import ToobitPublicClient
        async with aiohttp.ClientSession() as session:
            return await collect_public_funding_schedule(symbol,
                client=ToobitPublicClient(session=session), now=now)
    from apex.execution.toobit_map import to_wire_symbol
    path = "/api/v1/futures/fundingRate"
    try:
        raw = await client._get(path, params={"symbol": to_wire_symbol(symbol)})
        data = raw.get("data", raw) if isinstance(raw, Mapping) else raw
        if isinstance(data, list):
            data = data[-1]
        if not isinstance(data, Mapping):
            raise ValueError("funding record missing")
        rate = Decimal(str(data["fundingRate"]))
        if "fundingIntervalSeconds" in data:
            interval = Decimal(str(data["fundingIntervalSeconds"]))*1000
        elif "fundingIntervalHours" in data:
            interval = Decimal(str(data["fundingIntervalHours"]))*3600000
        else:
            raise ValueError("public interval and its units unavailable")
        phase = Decimal(str(data["nextFundingTime"]))
        if (not rate.is_finite() or not interval.is_finite() or interval <= 0
                or interval != int(interval) or not phase.is_finite() or phase <= 0 or phase != int(phase)):
            raise ValueError("invalid funding rate/interval/phase")
        return {"rate": rate, "interval_ms": int(interval), "next_settlement_ms": int(phase),
                "observed_at_ms": int(now()*1000), "source": {"endpoint": path, "payload": raw}}
    except Exception as exc:
        raise BridgeError("FUNDING_UNAVAILABLE", f"{symbol}: {type(exc).__name__}") from exc
