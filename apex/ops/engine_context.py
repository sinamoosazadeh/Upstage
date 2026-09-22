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

from apex.config import Config, PARAMS_DIR, PARAMS_FILES, REPO_ROOT, _YamlSubsetParser, load_params
from apex.data_catalog.contracts import CORE10_SYMBOLS, parse_utc_ms
from apex.engines.e11_regime import engine as E11
from apex.identity.canonical_json import canonical_json
from apex.ops.bootstrap_service import close_time_ms
from apex.ops.plan_bridge import BridgeError

ENGINE_ORDER = ("E01", "E02", "E12", "E04", "E03", "E10", "E09", "E05",
                "E06", "E11", "E07", "E08")
DEFAULT_TRAINING_SEED = 20260917
DEFAULT_TRAINING_TIMEFRAMES = ("1h", "4h")
AUTHORIZED_TRAINING_TIMEFRAMES = ("15m", "30m", "1h", "2h", "4h")
DEFAULT_TRAINING_MAX_MINUTES = 20.0
# D35: None keeps the D30 unlimited behavior; a positive int caps every cell
# at its latest N CLOSED bars and enters training_window + the protocol hash.
DEFAULT_MAX_BARS_PER_CELL = None
# D35 liveness: a progress message at least this often inside a long cell.
TRAIN_PROGRESS_EVERY_BARS = 250
# D35 --profile engine column order: E01..E11 per the decision, plus E12
# (temporal runs inside upstream_frame; omitting it would leave real training
# cost unattributed). E05-E08 never run during training and report 0.0 there.
PROFILE_ENGINE_ORDER = ("E01", "E02", "E03", "E04", "E05", "E06", "E07",
                        "E08", "E09", "E10", "E11", "E12")
# D35 resumable cache. data/ is gitignored (ADR-P2-013); the classifier rule
# (ADR-CP14-021) is unaffected: the worker writes cache only, never artifacts.
E11_TRAIN_CACHE_ROOT = REPO_ROOT / "data" / "e11_train_cache"
E11_TRAIN_CACHE_FORMAT = "e11-train-cache-v1"


def load_e11_training_protocol(path: str | Path | None = None) -> dict[str, Any]:
    """D47: strict parser for params/e11_training_v1.yaml.

    Exactly four keys: iterations, learning_rate, l2, class_weights.
    iterations int >0, learning_rate finite >0, l2 finite >=0, class_weights bool.
    Any schema drift, extra key, wrong type, non-finite or out-of-range refuses
    with CONFIGURATION_INVALID (fail-closed).
    """
    target = Path(path) if path is not None else PARAMS_DIR / "e11_training_v1.yaml"
    try:
        raw_text = target.read_text(encoding="utf-8")
        parsed = _YamlSubsetParser(raw_text).parse()
    except (OSError, ValueError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", "E11 training protocol missing or unreadable") from exc
    try:
        if not isinstance(parsed, dict):
            raise ValueError("protocol not a mapping")
        expected_keys = {"iterations", "learning_rate", "l2", "class_weights"}
        if set(parsed) != expected_keys:
            raise ValueError(f"protocol keys must be {expected_keys}")
        iterations = parsed["iterations"]
        learning_rate = parsed["learning_rate"]
        l2 = parsed["l2"]
        class_weights = parsed["class_weights"]
        if type(iterations) is not int or iterations <= 0:
            raise ValueError("iterations must be positive int")
        if type(learning_rate) not in (int, float) or not math.isfinite(float(learning_rate)) or float(learning_rate) <= 0:
            raise ValueError("learning_rate must be finite >0")
        if type(l2) not in (int, float) or not math.isfinite(float(l2)) or float(l2) < 0:
            raise ValueError("l2 must be finite >=0")
        if type(class_weights) is not bool:
            raise ValueError("class_weights must be bool")
        return {
            "iterations": int(iterations),
            "learning_rate": float(learning_rate),
            "l2": float(l2),
            "class_weights": bool(class_weights),
        }
    except (ValueError, TypeError, KeyError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", f"E11 training protocol invalid: {exc}") from exc




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
        marks[symbol] = _paper_decimal(row["close_price"], "PAPER close mark", positive=True)
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


def classifier_hash(W: Any, b: Any, seed: int, fit_protocol: Mapping[str, Any]) -> str:
    """D47: artifact_sha256 = sha256(canonical_json({W,b,seed,fit_protocol}))."""
    return hashlib.sha256(canonical_json(
        {"W": W, "b": b, "seed": seed, "fit_protocol": dict(fit_protocol)}).encode("utf-8")).hexdigest()


def _classifier_hash_legacy(W: Any, b: Any, seed: int) -> str:
    """Legacy hash without fit_protocol, kept for reference only."""
    return hashlib.sha256(canonical_json(
        {"W": W, "b": b, "seed": seed}).encode("utf-8")).hexdigest()


def validate_classifier(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """P2 + D47: validate the complete artifact before any E11 computation.

    D47: artifact must contain fit_protocol mapping with exactly
    iterations, learning_rate, l2, class_weights; artifact_sha256 covers it;
    missing fit_protocol => CONFIGURATION_INVALID.
    """
    required = {"W", "b", "K", "label_delay_candles", "seed", "fit_protocol",
                "training_window", "sample_count", "training_query_sha256", "artifact_sha256"}
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
        # D47 fit_protocol validation (same rules as loader)
        fp = artifact["fit_protocol"]
        if not isinstance(fp, Mapping) or set(fp) != {"iterations", "learning_rate", "l2", "class_weights"}:
            raise ValueError("fit_protocol schema")
        it = fp["iterations"]
        lr = fp["learning_rate"]
        l2 = fp["l2"]
        cw = fp["class_weights"]
        if type(it) is not int or it <= 0:
            raise ValueError("fit_protocol iterations")
        if type(lr) not in (int, float) or not math.isfinite(float(lr)) or float(lr) <= 0:
            raise ValueError("fit_protocol learning_rate")
        if type(l2) not in (int, float) or not math.isfinite(float(l2)) or float(l2) < 0:
            raise ValueError("fit_protocol l2")
        if type(cw) is not bool:
            raise ValueError("fit_protocol class_weights")
        window = artifact["training_window"]
        if set(window) != {"start", "end", "timeframes", "symbols", "default_timeframes", "default_symbols",
                           "max_bars_per_cell"}:
            raise ValueError("training_window")
        if window["max_bars_per_cell"] is not None and (
                type(window["max_bars_per_cell"]) is not int or window["max_bars_per_cell"] <= 0):
            raise ValueError("max_bars_per_cell")
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
        expected_hash = classifier_hash(artifact["W"], artifact["b"], artifact["seed"], artifact["fit_protocol"])
        if expected_hash != artifact["artifact_sha256"]:
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
    """D28 / D46: governed YAML values, never a runtime constant-weight fallback.

    D46 (2026-09-21, binding): exactly two keys — the D28 arbitration weights
    and the PAPER bootstrap eligibility minimum ``bootstrap_p_min``, a finite
    float in [0, 1]. A missing key is CONFIGURATION_INVALID: fail closed, no
    default. This section is read for PAPER only.
    """
    try:
        if (not isinstance(section, Mapping)
                or set(section) != {"arbitration_weights", "bootstrap_p_min"}):
            raise ValueError("bootstrap schema")
        weights = section["arbitration_weights"]
        if not isinstance(weights, Mapping) or set(weights) != {"quality", "alignment", "recency"}:
            raise ValueError("weights schema")
        if any(type(w) not in (int, float) or not math.isfinite(w) or w < 0 for w in weights.values()):
            raise ValueError("weights must be finite and nonnegative")
        if sum(weights.values()) <= 0:
            raise ValueError("empty weights")
        bootstrap_p_min = section["bootstrap_p_min"]
        if (type(bootstrap_p_min) not in (int, float)
                or not math.isfinite(bootstrap_p_min)
                or not 0.0 <= bootstrap_p_min <= 1.0):
            raise ValueError("bootstrap_p_min must be a finite float in [0,1]")
        return {"arbitration_weights": dict(weights),
                "bootstrap_p_min": float(bootstrap_p_min)}
    except (ValueError, TypeError, KeyError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", "invalid PAPER bootstrap policy") from exc


# D46 (2026-09-21; ADR-CP14-024): while no calibrated walk-forward forecast
# package exists (build_forecast with package None => p_hat = p_raw = 0.5),
# the PAPER eligibility minimum P is the governed bootstrap value. The D25
# SL-12 p_min_tf table stays authoritative for LIVE and for PAPER as soon as
# a calibrated package is present; LIVE never reads bootstrap_p_min.
D46_BOOTSTRAP_P_MIN_SOURCE = "D46_BOOTSTRAP"
D25_SL12_P_MIN_SOURCE = "D25_SL12"
P_MIN_SOURCES = (D25_SL12_P_MIN_SOURCE, D46_BOOTSTRAP_P_MIN_SOURCE)

# D46 producer-side provenance key. plan_bridge.REQUIRED_CONTEXT_KEYS stays the
# frozen 38-field bridge contract ("not a 39th required key"); this allowlist
# is validated here and ignored by the decision bridge.
PRODUCER_CONTEXT_ALLOWLIST = ("p_min_source",)


def eligibility_p_min(policy: Mapping[str, Any], *, timeframe: str, environment: str,
                      bootstrap_prior: bool) -> tuple[float, str]:
    """D46: the eligibility minimum P and its provenance for one cell.

    PAPER + bootstrap forecast (no calibrated package) => the governed
    ``paper_bootstrap.bootstrap_p_min``, source D46_BOOTSTRAP. Everywhere else
    => the D25 SL-12 ``p_min_tf`` value, source D25_SL12. LIVE never reads
    bootstrap_p_min, and a missing value fails closed.
    """
    try:
        if str(environment).upper() == "PAPER" and bootstrap_prior:
            value = policy["paper_bootstrap"]["bootstrap_p_min"]
            source = D46_BOOTSTRAP_P_MIN_SOURCE
        else:
            value = policy["p_min_tf"][timeframe]
            source = D25_SL12_P_MIN_SOURCE
        if type(value) not in (int, float) or not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("eligibility minimum P out of range")
        reduced = float(value)
    except (KeyError, TypeError, ValueError) as exc:
        raise BridgeError("CONFIGURATION_INVALID",
                          "eligibility minimum P unavailable or invalid") from exc
    return reduced, source


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
from apex.ops.bootstrap_service import _iso_to_ms as _native_iso_to_ms, _ms_to_iso
from functools import lru_cache


@lru_cache(maxsize=16384, typed=True)
def _iso_to_ms(timestamp: str) -> int:
    """Bounded memo of the unchanged parser, never a different clock law.

    Native rolling windows revisit the same immutable timestamps. This cache
    is local to the consumer; bootstrap/LIVE parsing and failures are unchanged.
    """
    return _native_iso_to_ms(timestamp)


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


def _time_engine(engine_profile: dict | None, engine: str, func, *args, **kwargs):
    """D35 --profile: accumulate native-engine seconds. None disables timing.

    Observational only: the wrapped call, its arguments and its return value
    are unchanged, so profiled and unprofiled runs produce identical outputs.
    """
    if engine_profile is None:
        return func(*args, **kwargs)
    start = time.monotonic()
    try:
        return func(*args, **kwargs)
    finally:
        engine_profile[engine] += time.monotonic() - start


def structure_projection(raw_window: list[Any], symbol: str, timeframe: str, *,
                         engine_profile: dict | None = None) -> dict:
    window = closed_engine_window(raw_window, timeframe)
    if not window:
        raise BridgeError("NO_MARKET_DATA", "empty confirmation window")
    duration = (close_time_ms(_iso_to_ms(raw_window[-1].timestamp), timeframe)
                - _iso_to_ms(raw_window[-1].timestamp)) // 1000
    params = E01.get_params()
    params["tick_size"] = E01.resolve_tick_size(symbol)
    return _time_engine(engine_profile, "E01", E01.run_pipeline,
                        [E01.observation_to_candle(o, timeframe, duration) for o in window], params)


def structural_confirmation(raw_window: list[Any], symbol: str, timeframe: str, *,
                            result: dict | None = None, engine_profile: dict | None = None) -> bool:
    if result is None:
        result = structure_projection(raw_window, symbol, timeframe, engine_profile=engine_profile)
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

def _retained_e04_evidence(evidence: list, start_ms: int, end_ms: int) -> list:
    """D35(e) P4: bisect slice of chronological E04 evidence, inclusive.

    The volatility_stream drain appends evidence in timeline order, so
    state.as_of is sorted ascending and this slice equals the linear
    inclusive scan element-for-element. Values identical, fewer scans.
    """
    from bisect import bisect_left, bisect_right
    keys = [e.state.as_of for e in evidence]
    return evidence[bisect_left(keys, start_ms):bisect_right(keys, end_ms)]

def upstream_frame(raw_window: list[Any], symbol: str, timeframe: str,
                   *, emit: bool = False,
                   atr14_history: list[float] | None = None,
                   structure_result: dict | None = None,
                   volatility_stream: dict | None = None,
                   temporal_profile: dict | None = None,
                   engine_profile: dict | None = None) -> dict[str, Any]:
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
    # D35(e) P0: the E01 candle conversion (timestamp parse + content hash
    # per bar) is pure in its inputs and is discarded whenever the caller
    # threads a structure_result (the training timeline always does), so
    # build it lazily only for the uncached reference path. Values are
    # bitwise-identical either way; this removes one repeated re-parse.
    if structure_result is None:
        candles = [E01.observation_to_candle(o, timeframe, duration) for o in window]
        structure = _time_engine(
            engine_profile, "E01", E01.run_pipeline, candles, params)
    else:
        structure = structure_result
    bos_events = [ev for ev in structure["events"] if ev["event_type"].startswith(
        ("EV_STR_007", "EV_STR_008"))]
    structural_events = [ev for ev in structure["events"] if ev["event_type"].startswith(
        ("EV_STR_007", "EV_STR_008", "EV_STR_009", "EV_STR_010"))]
    bos = bos_events[-1] if bos_events else None
    collect("E02", E02.E02LiquidityEngine, base)
    liquidity = _time_engine(engine_profile, "E02", E02.run_engine,
                              [E02.observation_to_candle(o) for o in window])
    collect("E12", E12.E12TemporalEngine, {**base, "profile": temporal_profile})
    temporal = _time_engine(engine_profile, "E12", E12.run_engine,
                            [E12.observation_to_candle(o) for o in window],
                            profile=temporal_profile)["temporal_state"]
    order.append("E04")
    bars = [E04.observation_to_bar(o, timeframe) for o in window]
    if volatility_stream is None:
        volatility = _time_engine(engine_profile, "E04", E04.run_engine, bars, timeframe=timeframe)
    else:
        # Native chronological E04, never a partial/reimplemented indicator.
        # Drain only observations already reached by this feature timeline.
        drain_start = time.monotonic() if engine_profile is not None else 0.0
        for bar in volatility_stream["pending"]:
            evidence = volatility_stream["engine"].ingest_bar(bar)
            if evidence is not None:
                volatility_stream["evidence"].append(evidence)
        volatility_stream["pending"].clear()
        if engine_profile is not None:
            engine_profile["E04"] += time.monotonic() - drain_start
        retained = _retained_e04_evidence(volatility_stream["evidence"], bars[0]["ts"], bars[-1]["ts"])
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
    volume = _time_engine(engine_profile, "E03", E03.run_engine, volume_bars)
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
    momentum_result = _time_engine(engine_profile, "E10", E10.run_engine, momentum_bars,
                                    symbol=symbol, interval=timeframe,
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
    trend = _time_engine(engine_profile, "E09", E09.run_engine, bars, swings=swings,
                          atr=vlt.atr14_wilder, tf_seconds=duration, bos_event=bos,
                          oi_state=vol.oi_state)
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
    derive_quality = rtm_context.get("derive_avg_quality") is True
    for key in ("avg_quality", "mtf_align"):
        if key == "avg_quality" and derive_quality:
            continue
        value = rtm_context.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
            raise BridgeError("E07_CONTEXT_UNAVAILABLE", key)
    if "vector" not in item:
        raise BridgeError("E11_CONTEXT_UNAVAILABLE", str(item.get("reason", "missing vector")))
    original = item["frame"]
    prior_atr = [state.atr14_wilder for state in original["volatility"]["states"][:-1]]
    frame = upstream_frame(original["raw_window"], symbol, timeframe, emit=True,
        atr14_history=prior_atr, structure_result=original["structure"],
        volatility_stream=item["volatility_stream"], temporal_profile=item.get("temporal_profile"))
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
    quality_contributors = []
    if derive_quality:
        used = set()
        for confirmation in confirmations:
            cid, stamp = confirmation["cid"], confirmation["t_confirm_ms"]
            engine = {"bos": "E01", "choch": "E01", "sweep": "E02",
                      "vol_confirm": "E03", "fvg": "E05"}[cid]
            matched = [ev for ev in events if ev.engine_id == engine
                       and _iso_to_ms(ev.event_time) == stamp
                       and (cid not in ("bos", "choch") or str(ev.condition_state).startswith(
                            ("EV_STR_007", "EV_STR_008") if cid == "bos" else ("EV_STR_009", "EV_STR_010")))
                       and (cid != "sweep" or ev.condition_state in CONFIRMED_SWEEP_EVENT_TYPES)]
            if not matched:
                raise BridgeError("E07_CONFIRMATION_QUALITY_UNAVAILABLE", f"{engine}:{cid}:{stamp}")
            for ev in matched:
                if ev.evidence_id not in used:
                    used.add(ev.evidence_id)
                    quality_contributors.append({"engine_id": engine, "evidence_id": ev.evidence_id,
                        "snapshot_id": ev.snapshot_id, "confirmation_ms": stamp, "quality": ev.quality})
        avg_quality = confirmation_quality(quality_contributors)
    else:
        avg_quality = rtm_context["avg_quality"]
    events.extend(E07.E07RTMEngine().compute(symbol, timeframe, end, {
        "window": window, "events": confirmations, "direction": direction,
        "avg_quality": avg_quality, "mtf_align": rtm_context["mtf_align"],
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
    return {**frame, "feature_vector": item["vector"], "rtm_confirmations": confirmations,
        "rtm_avg_quality": avg_quality, "rtm_quality_contributors": quality_contributors, "regime_state": state, "e11_result": result,
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
    "D35_resume": "per-cell finalized-sample cache under training_query_sha256; same-hash reruns load completed cells; bar cap recorded; engine/stage timing observational only",
})
HISTORY_KEYS = {"trend": "trendiness_raw", "vol": "vol_ratio", "exp": "expansion_raw",
                "liq": "liquidity_raw", "part": "participation_raw", "sq": "structure_score"}


def slice_training_window(rows: list[Any], as_of_ms: int, timeframe: str, bars: int) -> list[Any]:
    """In-memory equivalent of window(symbol, timeframe, as_of, bars).

    D35 training-only prefetch serving. `rows` are lineage-verified CLOSED
    observations in ascending open order (see training_dep_window) covering
    every per-bar slice of one training cell. The open/close/availability
    gates are re-applied per as_of exactly as window() applies them, and the
    wiring-only OI lag is recomputed against this as_of, so each slice
    equals the corresponding live window() call (parity-tested).
    """
    from bisect import bisect_right
    from dataclasses import replace
    if not rows:
        return []
    end = bisect_right(rows, as_of_ms, key=lambda o: _iso_to_ms(o.timestamp))
    result = []
    for obs in rows[max(0, end - bars):end]:
        if close_time_ms(_iso_to_ms(obs.timestamp), timeframe) > as_of_ms:
            continue
        if obs.availability_time is None or _iso_to_ms(obs.availability_time) > as_of_ms:
            continue
        oi_lag = (max(0., (as_of_ms - _iso_to_ms(obs.oi_timestamp)) / 1000.)
                  if obs.oi_timestamp is not None else None)
        result.append(replace(obs, oi_lag_seconds=oi_lag))
    return result


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
        self._content_hashes: dict[tuple, str] = {}
        self._ready: dict[tuple, dict] = {}
        self._failed: dict[tuple, BridgeError] = {}
        self._timelines: dict[tuple, dict] = {}

    async def _input_fingerprint(self, symbol: str, timeframe: str, as_of: str) -> str:
        """Cache inputs, never its own output; additions invalidate a success."""
        from apex.ops.bootstrap_service import latest_close_boundary
        artifact = load_classifier(self.classifier_path)
        tables = {}
        for name, sql, args in (
            ("raw", "SELECT m.observation_id,m.raw_payload_hash,r.availability_time,r.oi_timestamp,r.oi_state "
             "FROM market_observation m JOIN raw_observation r ON m.observation_id='obs-'||r.event_id "
             "WHERE m.symbol=? AND r.availability_time<=? ORDER BY m.timeframe,m.open_time,m.observation_id",(symbol,as_of)),
            ("facts", "SELECT snapshot_id FROM snapshot_pit WHERE as_of<=? AND "
             "source_state NOT IN ('CP14_BRIDGE_CONTEXT','CP14_UNCERTAINTY','CP14_COMPONENTS','CP14_SL14_ADMISSION') ORDER BY snapshot_id",(as_of,)),
            ("prior", "SELECT snapshot_id FROM snapshot_pit WHERE source_state IN ('CP14_UNCERTAINTY','CP14_COMPONENTS') "
             "AND symbol_scope=? AND timeframe_scope=? AND as_of<? ORDER BY snapshot_id",
             (symbol,timeframe,_ms_to_iso(latest_close_boundary(_iso_to_ms(as_of),timeframe)))),
            ("ledger", "SELECT ledger_id,payload_hash FROM ledger WHERE timestamp<=? ORDER BY rowid",(as_of,))):
            tables[name] = [list(row) for row in await (await self.store.db.execute(sql,args)).fetchall()]
        exists = await (await self.store.db.execute("SELECT name FROM sqlite_master WHERE name='apex_risk_ladder_state'")).fetchone()
        if exists:
            tables["ladder"] = [list(r) for r in await (await self.store.db.execute(
                "SELECT * FROM apex_risk_ladder_state WHERE applied_at<=? ORDER BY rowid",(as_of,))).fetchall()]
        return hashlib.sha256(canonical_json({"inputs":tables,"classifier":artifact["artifact_sha256"],
            "package":paper_package_binding(environment=self.environment),"symbol":symbol,"timeframe":timeframe,"as_of":as_of}).encode()).hexdigest()

    async def prepare(self, symbol: str, timeframe: str, as_of: str) -> None:
        """Outside-budget source preparation; a failed refresh clears success."""
        key = (symbol,timeframe,as_of)
        self._ready.pop(key,None)
        self._failed.pop(key,None)
        try:
            if self.environment != "PAPER":
                raise BridgeError("PAPER_ONLY_EXECUTION",self.environment)
            from apex.data_catalog.contracts import TIMEFRAMES_14
            if symbol not in CORE10_SYMBOLS or timeframe not in TIMEFRAMES_14:
                raise BridgeError("CELL_OUT_OF_UNIVERSE",f"{symbol}:{timeframe}")
            parse_utc_ms(as_of)
            fingerprint = await self._input_fingerprint(symbol,timeframe,as_of)
            saved = await read_context_fact(self.store,"BRIDGE_CONTEXT",symbol,timeframe,as_of,exact=True)
            if saved and saved["input_fingerprint"] == fingerprint:
                context = saved["context"]
                context["events"] = await read_complete_evidence(self.store,context["events"])
            else:
                context = await self._compose_bridge_context(symbol,timeframe,as_of)
                await append_context_fact(self.store,"BRIDGE_CONTEXT",symbol,timeframe,as_of,
                    {"input_fingerprint":fingerprint,"context":{**context,"events":[e.evidence_id for e in context["events"]]}})
            validate_produced_context(context)
            self._ready[key] = context
        except BridgeError as exc:
            self._failed[key] = exc
            raise
        except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
            refusal = BridgeError("ENGINE_CONTEXT_INVALID",f"{type(exc).__name__}: {exc}")
            self._failed[key] = refusal
            raise refusal from exc

    async def get_bridge_context(self, symbol: str, timeframe: str, as_of: str) -> dict:
        """Exactly 38 context fields / 23 risk fields; no fixture fallback.

        PAPER serve binds prepare separately so this accessor is a cheap copy
        inside the scheduler budget. A standalone caller may prepare lazily.
        """
        import copy
        key = (symbol,timeframe,as_of)
        if key in self._failed:
            raise self._failed[key]
        if key not in self._ready:
            await self.prepare(symbol,timeframe,as_of)
        return copy.deepcopy(self._ready[key])

    async def _compose_bridge_context(self, symbol: str, timeframe: str, as_of: str) -> dict:
        from dataclasses import asdict
        from apex.ops.plan_bridge import _fabric_ref, _normalise_bars
        from apex.fabric.evidence import EvidenceFabric, expiry_age_bars
        from apex.fabric.conflict import resolve, disagreement_of, quality_asymmetry_of, stale_fraction_of, penalties
        from apex.fabric.context import COMPONENT_ENGINE, redundancy_rho
        from apex.pattern.detect import detect_all, CATALOGUE, entity_for
        from apex.setup.family_sf_fvg_sweep_rev import sweep_and_reclaim, ENTRY_LOGIC_REF, PLAYBOOK_ID, HORIZON_BARS
        from apex.playbook.pb_fvg_sweep_rev_a import build_stops
        from apex.forecast.logistic import ForecastEvent, build_forecast
        from apex.research.governance import GOVERNED_DEFAULTS
        import json
        end = _iso_to_ms(as_of)
        bundle = await self.prepare_engine_bundle(symbol,timeframe,as_of)
        q, mtf = bundle["measured_quality"], bundle["measured_mtf"]
        governance = await self.decision_inputs(symbol,timeframe,as_of)
        package = governance["package"]
        state = bundle["regime_state"]
        uncertainty = regime_uncertainty_input(state)
        refs = [_fabric_ref(e,symbol=symbol,timeframe=timeframe,as_of_ms=end) for e in bundle["events"]]
        ages = {e.evidence_id: decision_evidence_age(e.event_time,timeframe,end) for e in bundle["events"]}
        from dataclasses import replace
        refs = [replace(r,age_bars=ages[r.evidence_id]) for r in refs]
        from apex.fabric.evidence import advance_lifecycle
        admission = {}
        for i,(event,ref) in enumerate(zip(bundle["events"],refs)):
            target = None
            if ref.state == "CONFIRMED" and event.validity == "VALID" and event.resolution_class != "QX" and ref.as_of <= end:
                target = "ACTIVE"
            if ref.state == "ACTIVE" and event.engine_id == "E05":
                obj = next((o for o in bundle["fvg_objects"] if o.snapshot_id == event.snapshot_id),None)
                if obj is not None and obj.fate in ("EXPIRED","INVALIDATED","MITIGATED"):
                    target = obj.fate
                elif obj is not None and obj.fate == "FILLED":
                    target = "MITIGATED"
            if target is not None:
                state_to = advance_lifecycle(ref.state,target)
                admission[event.evidence_id] = {"from":ref.state,"to":state_to,"reason":"NATIVE_EMISSION_OR_ZONE_FATE"}
                refs[i] = replace(ref,state=state_to)
        await append_context_fact(self.store,"SL14_ADMISSION",symbol,timeframe,as_of,{"transitions":admission})
        fabric = EvidenceFabric.assemble(symbol=symbol,timeframe=timeframe,as_of=end,evidence=refs,
            data_trust=q["data_trust"],raw_observation_ids=bundle["raw_observation_ids"])
        if fabric.is_empty():
            raise BridgeError("FABRIC_NO_ACTIVE_EVIDENCE",str(fabric.excluded))
        close = _iso_to_ms(bundle["window"][-1].timestamp)
        history_rows = await (await self.store.db.execute("SELECT vector_quality_state FROM snapshot_pit "
            "WHERE source_state='CP14_COMPONENTS' AND symbol_scope=? AND timeframe_scope=? AND as_of<? "
            "ORDER BY as_of DESC,rowid DESC LIMIT 48",(symbol,timeframe,_ms_to_iso(close)))).fetchall()
        histories = [json.loads(row[0])["data"] for row in reversed(history_rows)]
        histories = [h for h in histories if h["parameter_version"] == package["parameter_package_id"]
                     and h["classifier_version"] == bundle["classifier_artifact_sha256"]]
        series = {name:[h["s_i"][name] for h in histories if name in h["s_i"]] for name in COMPONENT_ENGINE}
        rho_records = [redundancy_rho(series[a],series[b]) for i,a in enumerate(series)
                       for b in list(series)[i+1:]]
        known_rhos = [r["rho"] for r in rho_records if r["rho"] is not None]
        rho = max(known_rhos,key=abs) if known_rhos else None
        redundancy = penalties("CONSENSUS",redundancy_rho=rho)["redundancy_penalty"]
        conflict = resolve(disagreement=disagreement_of(fabric.members),data_trust=q["data_trust"],q_raw=q["q_raw"],
            timeframe=timeframe,mtf_conflict=mtf["mtf_state"],uncertainty=uncertainty,
            stale_fraction=stale_fraction_of([r.age_bars for r in fabric.members],expiry_age_bars(timeframe)),
            redundancy=redundancy,redundancy_rho=rho,quality_asymmetry=quality_asymmetry_of([r.quality for r in fabric.members]),
            regime_state=state["state"],package_id=package["parameter_package_id"],snapshot_id=fabric.hash,
            lineage=bundle["raw_observation_ids"])
        current = {"symbol":symbol,"timeframe":timeframe,"closed":True,"close_ms":close,
            "parameter_version":package["parameter_package_id"],"classifier_version":bundle["classifier_artifact_sha256"],
            "entropy":state["entropy"],"conflict_state":conflict["output"],"e11_snapshot_id":state["snapshot_id"]}
        previous = await read_context_fact(self.store,"UNCERTAINTY",symbol,timeframe,_ms_to_iso(close-1))
        await append_context_fact(self.store,"UNCERTAINTY",symbol,timeframe,as_of,current)
        rising = uncertainty_trend(current,previous,is_risk_increase=True)
        bars = _normalise_bars(bundle["raw_window"])
        atr = measured_number(bundle["vlt"].atr14_wilder,"ATR_UNAVAILABLE",lower=E04.EPS)
        hits = detect_all(bars,atr)["hits"]
        hit = select_native_pattern(hits.values(),{row.pattern_id:entity_for(row) for row in CATALOGUE},bars)
        direction = hit.direction
        components = component_projection(fabric.members,direction)
        sweep = sweep_and_reclaim(bars,direction=direction)
        if not sweep["ok"]:
            raise BridgeError("NO_SETUP_GEOMETRY",sweep["reason"])
        zones = [{"index":o.created_at_idx,"low":o.lower,"high":o.upper,
                  "filled":o.fate in ("FILLED","INVALIDATED","EXPIRED"),"fate":o.fate,"snapshot_id":o.snapshot_id}
                 for o in bundle["fvg_objects"]]
        zone = next((z for z in reversed(zones) if not z["filled"] and len(bars)-1-z["index"] <= 12),None)
        if zone is None:
            raise BridgeError("NO_UNFILLED_FVG","native lifecycle/retained window")
        bos_native = next((b for b in reversed(bundle["structural_events"]) if "strength" in b),None)
        if bos_native is None:
            raise BridgeError("BOS_STRENGTH_UNAVAILABLE","native E01 strength.S required")
        bos = {"s_struct":bos_native["strength"]["S"],"direction":1 if "BULLISH" in bos_native["event_type"] else -1,
               "snapshot_id":bos_native["snapshot_id"],"event_type":bos_native["event_type"]}
        stops = build_stops(direction=direction,entry=bars[-1]["c"],atr=atr,sweep_extreme=sweep["extreme"],
                            fvg_low=zone["low"],fvg_high=zone["high"])
        account = await self.paper_account_inputs(as_of)
        ladder = await self.ladder_input(as_of)
        venue = governance["venue_provenance"]
        multiplier = Decimal(str(venue["contract_multiplier"]))
        filters = venue["sources"]["exchange_info"]["record"].get("filters",[])
        lot = [f for f in filters if f.get("filterType") == "LOT_SIZE"]
        if len(lot) > 1:
            raise BridgeError("QUANTITY_FILTER_UNAVAILABLE","ambiguous LOT_SIZE")
        step = (Decimal(str(lot[0]["stepSize"])) if lot else load_params()["universe"]["quantity_step"][symbol])
        request = native_size_request(capital=account["capital"],exposure=account["open_notional"],risk_state=ladder["state"],
            atr=atr,stop_distance=stops["R"],entry=bars[-1]["c"],contract_multiplier=multiplier,quantity_step=step)
        funding = await read_public_funding_schedule(self.store,symbol,as_of)
        adv = await self.adv_input(symbol,as_of)
        cost = forecast_cost_projection(quantity=request["sized_quantity"],entry=bars[-1]["c"],stop_distance=stops["R"],
            contract_multiplier=multiplier,commission_rate=Decimal(str(venue["commission_rate"])),adv=adv["adv"],
            funding=funding,direction=direction,start_ms=end,end_ms=governed_holding_end(end,timeframe),spread_available=False)
        rr = abs(stops["target"]-bars[-1]["c"])/stops["R"]
        temporal = bundle["temporal"]
        x = forecast_features(scores=components["s_i"],trend_bias=bundle["trend"]["bias"],
            momentum_z=bundle["momentum"]["momentum"]["momentum_z"],regime_entropy=state["entropy"],
            vol_quantile=forecast_vol_quantile(bundle["volatility_history"],bundle["vlt"],timeframe=timeframe),
            temporal_core=temporal["is_utc_activity_window"],rr=rr,cost_r=cost["forecast_cost_r"])
        model = paper_bootstrap_uncertainty(state,environment=self.environment)
        forecast = build_forecast(ForecastEvent(f"{PLAYBOOK_ID}:TARGET_3R",f"{ENTRY_LOGIC_REF}:SWEEP_LOW_INVALIDATION",
            HORIZON_BARS,ENTRY_LOGIC_REF,symbol,timeframe,end),x=x,uncertainty=model,rr=rr,cost_r=cost["forecast_cost_r"],
            risk_state=ladder["state"],spread_available=cost["spread_available"],environment="PAPER")
        if venue["contract_type"] == "PERPETUAL" and venue["expiry_time"] is None:
            expiry = {"applicable":False,"contract_type":"PERPETUAL"}
        elif venue["contract_type"] in ("CURRENT_QUARTER","NEXT_QUARTER","DELIVERY") and venue["expiry_time"]:
            expiry = (_iso_to_ms(venue["expiry_time"])-end)/86400000
        else:
            raise BridgeError("VENUE_EXPIRY_UNAVAILABLE",symbol)
        latest = bundle["raw_window"][-1]
        if latest.oi_timestamp is None or latest.oi is None:
            raise BridgeError("OI_LAG_UNAVAILABLE",symbol)
        oi_lag = max(0.,(end-_iso_to_ms(latest.oi_timestamp))/1000)
        cfg = load_decision_runtime(environment="PAPER")
        # D46 (ADR-CP14-024): PAPER + bootstrap forecast (no calibrated
        # walk-forward package) uses the governed bootstrap minimum P;
        # otherwise the D25 SL-12 per-timeframe table.
        p_min_tf, p_min_source = eligibility_p_min(
            cfg, timeframe=timeframe, environment="PAPER",
            bootstrap_prior=bool(forecast.bootstrap_prior))
        def cap(name):
            text = next(p.l1_default for p in GOVERNED_DEFAULTS if p.name == name)
            return float(str(text).rstrip("%"))/100*float(account["capital"])
        risk = {"capital":float(account["capital"]),"portfolio_exposure":float(account["open_notional"]),
            "proposed_notional":request["proposed_notional"],"capital_hard_cap":cfg["capital_hard_cap_fraction"]*float(account["capital"]),
            "circuit_breaker_engaged":account["circuit_breaker_engaged"] or ladder["emergency_state"] != "NORMAL",
            "emergency_state":ladder["emergency_state"],"per_symbol_exposure":float(sum(v for s,v in account["per_symbol_exposure"].items() if s == symbol)),
            "symbol_cap":cap("symbol_exposure_cap"),"portfolio_cap":cap("portfolio_exposure_cap"),
            "staleness_seconds":q["staleness_seconds"],"freshness_sla_seconds":q["freshness_sla_seconds"],
            "oi_lag_seconds":oi_lag,"oi_lag_threshold_seconds":load_params()["quality_weights"]["oi_lag_threshold_seconds"][timeframe],
            "is_risk_increase":request["is_risk_increase"],"uncertainty_is_rising":rising,
            **{k:account[k] for k in ("realized_daily_loss_fraction","realized_weekly_loss_fraction","consecutive_losses")},
            "time_to_expiry_days":expiry,"margin_health_fraction":float(account["margin_health_fraction"]),
            "min_quantity":float(step),"contract_multiplier":float(multiplier),"risk_state":ladder["state"]}
        divergence = bundle["momentum"]["events"]["divergence"]
        if divergence["present"] is False:
            divergence_magnitude = float(divergence["D_mag"])
        else:
            div_events = [e for e in bundle["events"] if e.engine_id == "E10" and
                any(e.condition_state.startswith(code) for code in E10.KIND_TO_EVENT.values())]
            if not div_events:
                raise BridgeError("DIVERGENCE_UNAVAILABLE","native normalized event required")
            divergence_magnitude = max(div_events,key=lambda e:e.event_time).strength
        temporal_event = next(e for e in reversed(bundle["events"]) if e.engine_id == "E12")
        transport = {"bars":bars,"raw_observation_ids":list(bundle["raw_observation_ids"]),
            "available_closes":mtf["available_closes"],"sl14_admission":admission,"evidence_age_bars":ages,"forecast_uncertainty":model,"uncertainty":uncertainty,
            "q_forecast":forecast.q_forecast,"spread_available":cost["spread_available"],"component_series":series,
            "redundancy":redundancy,"redundancy_observations":rho_records,"sweep":sweep,"pattern_hit":asdict(hit),"cost_model":cost,
            "account":account,"risk_revision":ladder,"engine_order":list(bundle["engine_order"]),
            "quality_snapshot_ids":q["quality_snapshot_ids"],"risk_transport":{"environment":"PAPER",
                "margin_model":account["margin_model"],"atr_cap":request["atr_cap"]}}
        if rho is not None: transport["redundancy_rho"] = rho
        context = {"events":bundle["events"],"data_trust":q["data_trust"],"q_raw":q["q_raw"],
            "market_regime":state["state"],"mtf_state":mtf["mtf_state"],"utc_window_state":temporal["temporal_window"],
            "is_overlap":temporal["is_overlap"],"volatility_state":bundle["vlt"].regime,
            "structure_state":bos_native["event_type"],"regime_confidence":max(state["probs"]),"regime_uncertainty":uncertainty,
            "divergence_magnitude":divergence_magnitude,"temporal_window_validity":temporal_validity_projection(temporal_event.validity),
            "atr":atr,"fvg_zones":zones,"bos":bos,"regime_state":state,
            "e11_context":{**bundle["e11_context"],"bridge_inputs":transport},"direction":direction,"pattern_id":hit.pattern_id,
            "x":x,"forecast_quality":forecast.q_forecast,"forecast_rr":rr,"forecast_cost_r":cost["forecast_cost_r"],
            "window_qualities":q["window_qualities"],"temporal_quality":temporal["quality"],"volatility_quality":bundle["vlt"].q_tag,
            **components,"package":package,"p_min_tf":p_min_tf,"p_min_source":p_min_source,"c_min":cfg["c_min"],
            "freshness_ok":q["freshness_ok"],"risk":risk,"risk_state":ladder["state"],"h_norm":E11.entropy_normalized(state["entropy"]),
            "family_status":governance["family_status"],"arbitration":governance["arbitration"]}
        await append_context_fact(self.store,"COMPONENTS",symbol,timeframe,as_of,
            {"s_i":{k:components["s_i"].get(k,0.) for k in COMPONENT_ENGINE},"parameter_version":package["parameter_package_id"],"classifier_version":bundle["classifier_artifact_sha256"],
             "p_min_tf":p_min_tf,"p_min_source":p_min_source,"c_min":cfg["c_min"]})
        # JSON-normalize metadata so cold SQLite recovery equals the first call.
        events = context.pop("events")
        context = json.loads(canonical_json(context))
        context["events"] = events
        return context

    async def quality_window(self, symbol: str, timeframe: str, as_of: str,
                             bars: int = 300) -> dict:
        """Hydrate measured metadata only after immutable raw identity checking.

        Raw-only SQLite rows do not prove source health, gap/sequence status or
        receipt time. Absence of the quality-plane record is a refusal, not an
        invitation to use MarketObservation constructor defaults.
        """
        from dataclasses import replace
        from apex.quality.vector import calc_quality_vector, QualityFlags
        window = await self.window(symbol, timeframe, as_of, bars)
        if not window:
            raise BridgeError("NO_MARKET_DATA", f"{symbol}:{timeframe}")
        hydrated, qualities, facts = [], [], []
        for index, obs in enumerate(window):
            identity = self._raw_lineage[(symbol, timeframe, obs.timestamp, obs.content_hash())]["observation_id"]
            fact = await read_context_fact(self.store, "QUALITY_"+identity, symbol, timeframe, as_of)
            if fact is None:
                raise BridgeError("QUALITY_PROVENANCE_UNAVAILABLE", identity)
            try:
                if (fact["observation_id"] != identity or fact["content_hash"] != obs.content_hash()
                        or not fact["measurement_source"] or type(fact["receipt_time_ms"]) is not int
                        or fact["receipt_time_ms"] > _iso_to_ms(fact["fact_as_of"])
                        or fact["receipt_time_ms"] < close_time_ms(_iso_to_ms(obs.timestamp), timeframe)):
                    raise ValueError("quality/raw identity or receipt mismatch")
                flags = fact["flags"]
                if set(flags) != set(QualityFlags.__dataclass_fields__) or any(type(v) is not bool for v in flags.values()):
                    raise ValueError("invalid quality flags")
                measurements = fact["measurements"]
                if set(measurements) != {"source_health", "gap_count", "expected_count", "completeness_pct", "delay_seconds"}:
                    raise ValueError("incomplete measured metadata")
                for key in ("gap_count", "expected_count"):
                    if type(measurements[key]) is not int or measurements[key] < (1 if key == "expected_count" else 0):
                        raise ValueError("invalid measured counts")
                measured_number(measurements["source_health"], "QUALITY_PROVENANCE_UNAVAILABLE", lower=0, upper=1)
                measured_number(measurements["completeness_pct"], "QUALITY_PROVENANCE_UNAVAILABLE", lower=0, upper=100)
                measured_number(measurements["delay_seconds"], "QUALITY_PROVENANCE_UNAVAILABLE", lower=0)
                delay = freshness([obs], timeframe, receipt_time=fact["receipt_time_ms"]/1000)["staleness_seconds"]
                if delay != measurements["delay_seconds"]:
                    raise ValueError("receipt/delay binding mismatch")
                lag = (max(0., (fact["receipt_time_ms"]-_iso_to_ms(obs.oi_timestamp))/1000)
                       if obs.oi_timestamp is not None else None)
                measured = replace(obs, **measurements, oi_lag_seconds=lag)
                q, state, tier = calc_quality_vector(measured, QualityFlags(**flags))
                if q is None:
                    raise BridgeError("WINDOW_QUALITY_UNAVAILABLE", state)
                if (q != fact.get("q_raw") or state != fact["quality_state"] or tier != fact["quality_class"]):
                    raise ValueError("native quality readback mismatch")
            except (ValueError, KeyError, TypeError) as exc:
                raise BridgeError("QUALITY_PROVENANCE_UNAVAILABLE", f"{identity}: {exc}") from exc
            hydrated.append(measured)
            qualities.append((q, len(window)-index-1))
            facts.append(fact["fact_snapshot_id"])
        quality = window_quality_projection(qualities)
        latest = await read_context_fact(self.store, "QUALITY_"+identity, symbol, timeframe, as_of)
        fresh = freshness(hydrated, timeframe, receipt_time=latest["receipt_time_ms"]/1000)
        return {"window": hydrated, **quality, **fresh,
                "quality_snapshot_ids": facts, "receipt_time_ms": latest["receipt_time_ms"]}

    async def mtf_inputs(self, symbol: str, timeframe: str, as_of: str) -> dict:
        """D33 actual E09 base/intermediate/HTF states, no injected alignment."""
        from apex.setup.family_sf_fvg_sweep_rev import relative_mtf
        from apex.ops.bootstrap_service import latest_close_boundary
        scope = relative_mtf(timeframe)
        frames, states = {}, {}
        for tf in dict.fromkeys((timeframe, scope["intermediate"], scope["htf"])):
            if tf is None:
                continue
            try:
                quality = await self.quality_window(symbol, tf, as_of)
                actual_close = close_time_ms(_iso_to_ms(quality["window"][-1].timestamp), tf)
                if actual_close != latest_close_boundary(_iso_to_ms(as_of), tf):
                    raise BridgeError("MTF_INSUFFICIENT", f"{tf}: latest CLOSED frontier missing")
                if len(quality["window"]) < 51:
                    raise BridgeError("INSUFFICIENT_HISTORY", tf)
                frame = upstream_frame(quality["window"], symbol, tf)
            except BridgeError as exc:
                if exc.reason in ("NO_MARKET_DATA", "INSUFFICIENT_HISTORY"):
                    raise BridgeError("MTF_INSUFFICIENT", f"{tf}: {exc.reason}") from exc
                raise
            state = {"symbol": symbol, "timeframe": tf, "closed": True,
                     "as_of": close_time_ms(_iso_to_ms(quality["window"][-1].timestamp), tf),
                     "freshness_ok": quality["freshness_ok"], "bias": frame["trend"]["bias"],
                     "receipt_time_ms": quality["receipt_time_ms"],
                     "quality_snapshot_ids": quality["quality_snapshot_ids"]}
            states[tf] = state
            frames[tf] = frame
        projection = mtf_projection(symbol, timeframe, _iso_to_ms(as_of), states)
        return {**projection, "states": states, "frames": frames}

    async def paper_marks(self, held_symbols: Any, as_of: str) -> dict:
        """One shared D34 last-CLOSED-1m account mark set from actual SQLite."""
        if self.environment != "PAPER":
            raise BridgeError("PAPER_ACCOUNT_NOT_LIVE", self.environment)
        rows = {}
        for symbol in sorted(set(held_symbols)):
            try:
                quality = await self.quality_window(symbol, "1m", as_of, 1)
                obs = quality["window"][-1]
                rows[symbol] = {"symbol": symbol, "timeframe": "1m", "status": obs.status,
                    "open_time_ms": _iso_to_ms(obs.timestamp), "availability_ms": _iso_to_ms(obs.availability_time),
                    "receipt_ms": quality["receipt_time_ms"], "close_price": obs.close}
            except BridgeError as exc:
                raise BridgeError("PAPER_MARK_UNAVAILABLE", f"{symbol}: {exc.reason}") from exc
        return paper_close_marks(held_symbols, rows, as_of_ms=_iso_to_ms(as_of))

    async def adv_input(self, symbol: str, as_of: str) -> dict:
        """D34 base-asset ADV; units must be declared by the public venue."""
        import datetime as dt
        venue = await read_public_venue_facts(self.store, symbol, as_of)
        unit = venue["sources"]["exchange_info"]["record"].get("volumeUnit")
        if unit not in ("BASE", "CONTRACT"):
            raise BridgeError("ADV_UNAVAILABLE", "public venue volume units unavailable")
        end_ms = _iso_to_ms(as_of)
        midnight = int(dt.datetime.fromtimestamp(end_ms/1000,dt.timezone.utc)
                       .replace(hour=0,minute=0,second=0,microsecond=0).timestamp()*1000)
        window = await self.window(symbol,"1h",as_of,30*24+int((end_ms-midnight)//3600000)+1)
        rows = [{"open_time_ms":_iso_to_ms(obs.timestamp), "timeframe":"1h", "status":obs.status,
                 "availability_ms":_iso_to_ms(obs.availability_time), "volume":float(obs.volume)} for obs in window]
        value = adv_base_volume(rows, as_of_ms=end_ms, volume_unit=unit,
                                contract_multiplier=Decimal(str(venue["contract_multiplier"])))
        return {"adv":value, "volume_unit":unit, "as_of":as_of,
                "period_start_ms":midnight-30*86400000, "period_end_ms":midnight,
                "venue_source_sha256":venue["source_sha256"],
                "observation_ids":[self._raw_lineage[(symbol,"1h",obs.timestamp,obs.content_hash())]["observation_id"]
                    for obs in window if midnight-30*86400000 <= _iso_to_ms(obs.timestamp) < midnight]}

    async def ladder_input(self, as_of: str) -> dict:
        """Read the native append-only risk revision, never bootstrap NORMAL."""
        from apex.risk.kernel import LADDER_ROW_COLUMNS, EMERGENCY_LADDER, ladder_multiplier, ratchet_allow
        exists = await (await self.store.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='apex_risk_ladder_state'")).fetchone()
        if not exists:
            raise BridgeError("RISK_LADDER_UNAVAILABLE", "native ladder table absent")
        rows = await (await self.store.db.execute("SELECT "+",".join(LADDER_ROW_COLUMNS)+
            " FROM apex_risk_ladder_state WHERE applied_at<=? ORDER BY applied_at DESC,rowid DESC LIMIT 2",(as_of,))).fetchall()
        if not rows:
            raise BridgeError("RISK_LADDER_UNAVAILABLE", "no PIT native ladder revision")
        result = dict(zip(LADDER_ROW_COLUMNS,rows[0]))
        if (result["emergency_state"] not in EMERGENCY_LADDER or not result["snapshot_id"]
                or result["multiplier"] != ladder_multiplier(result["state"])):
            raise BridgeError("RISK_LADDER_UNAVAILABLE", "invalid native revision")
        if len(rows) > 1:
            previous = dict(zip(LADDER_ROW_COLUMNS,rows[1]))
            if result["parent_revision_id"] != previous["revision_id"]:
                raise BridgeError("RISK_LADDER_UNAVAILABLE", "revision parent binding unavailable")
            if not ratchet_allow(previous["emergency_state"],result["emergency_state"])["allowed"]:
                raise BridgeError("CIRCUIT_RESET_UNAVAILABLE", "emergency downgrade lacks authenticated durable review")
        return result

    async def paper_account_inputs(self, as_of: str) -> dict:
        """PIT durable ledger + shared marks + native D29 and D34 projections.

        Correction chains and purported OWNER reviews with no authenticated
        durable binding are refused, never silently interpreted as resets.
        """
        if self.environment != "PAPER":
            raise BridgeError("PAPER_ACCOUNT_NOT_LIVE", self.environment)
        if self.ledger is None:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "ledger not bound")
        end = _iso_to_ms(as_of)
        entries = [e for e in await self.ledger.read_ledger() if _iso_to_ms(e.timestamp) <= end]
        plans = []
        for plan in await self.ledger.trade_plans():
            if plan.get("environment") in ("LIVE","RESEARCH","BACKTEST"):
                continue
            if plan.get("environment") != "PAPER":
                raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "plan environment unavailable")
            try:
                stamp = max(_iso_to_ms(plan["as_of"]),_iso_to_ms(plan["created_utc"]))
            except (ValueError,TypeError,KeyError,AttributeError) as exc:
                raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "plan PIT timestamps unavailable") from exc
            if stamp <= end:
                plans.append(plan)
        class PITView:
            async def read_ledger(self): return entries
            async def trade_plans(self): return plans
        by_id = {e.event_id:e for e in entries}
        by_id.update({e.ledger_id:e for e in entries})
        environments, symbols, net = {}, set(), {}
        for entry in entries:
            p = entry.raw.get("payload",{})
            if entry.event_type == "FSM_TRANSITION":
                env = p.get("environment")
                if env not in ("PAPER","LIVE","RESEARCH","BACKTEST") or (
                        entry.intent_id in environments and environments[entry.intent_id] != env):
                    raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "FSM environment unavailable/conflicting")
                environments[entry.intent_id] = env
                if env == "PAPER" and p.get("trigger") == "SUBMIT_ORDER":
                    symbol = p.get("evidence",{}).get("symbol")
                    if not symbol:
                        raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "submission symbol unavailable")
                    symbols.add(symbol)
        outcomes = []
        for entry in entries:
            p = entry.raw.get("payload",{})
            if entry.event_type == "CORRECTION_EVENT":
                target = by_id.get(p.get("supersedes"))
                target_payload = target.raw.get("payload",{}) if target is not None else {}
                target_env = target_payload.get("outcome",{}).get("context",{}).get("environment")
                if target_env is None and target is not None:
                    target_env = environments.get(target.intent_id)
                if target_env not in ("LIVE","RESEARCH","BACKTEST"):
                    raise BridgeError("PAPER_CORRECTION_UNAVAILABLE", "canonical correction resolution required")
            if (entry.event_type in ("OWNER_REVIEW","CIRCUIT_RESET","RISK_REVIEW")
                    and p.get("environment") not in ("LIVE","RESEARCH","BACKTEST")):
                raise BridgeError("CIRCUIT_RESET_UNAVAILABLE", "no authenticated durable review binding")
            if entry.event_type == "FILL":
                env = environments.get(entry.intent_id)
                if env is None:
                    raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "unidentified fill environment")
                if env == "PAPER":
                    side, symbol = p.get("side"), p.get("symbol")
                    if side not in ("BUY_OPEN","SELL_OPEN","BUY_CLOSE","SELL_CLOSE") or not symbol:
                        raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "fill symbol/side unavailable")
                    qty = _paper_decimal(entry.quantity,"fill quantity",positive=True)
                    symbols.add(symbol)
                    net[symbol] = net.get(symbol,Decimal(0)) + (qty if side.startswith("BUY") else -qty)
            if entry.event_type == "OUTCOME":
                outcome = p.get("outcome",{})
                env = outcome.get("context",{}).get("environment")
                if env not in ("PAPER","LIVE","RESEARCH","BACKTEST"):
                    raise BridgeError("PAPER_LOSS_UNAVAILABLE", "outcome environment unavailable")
                if env != "PAPER": continue
                identity = outcome.get("outcome_id")
                if not identity or not outcome.get("exit_reason"):
                    raise BridgeError("PAPER_LOSS_UNAVAILABLE", "canonical completed outcome identity/reason unavailable")
                stored = await (await self.store.db.execute(
                    "SELECT pnl,setup_id,exit_reason,context FROM outcome WHERE outcome_id=?",(identity,))).fetchone()
                import json
                if (stored is None or stored[1] != outcome.get("setup_id")
                        or stored[2] != outcome["exit_reason"] or json.loads(stored[3]) != outcome["context"]
                        or _paper_decimal(stored[0],"stored net pnl") != _paper_decimal(entry.raw.get("pnl"),"ledger net pnl")
                        or _paper_decimal(outcome.get("pnl"),"outcome net pnl") != _paper_decimal(stored[0],"stored net pnl")):
                    raise BridgeError("PAPER_LOSS_UNAVAILABLE", "canonical outcome/ledger mismatch")
                outcomes.append({"outcome_id":identity,"environment":env,"completed":True,
                    "timestamp_ms":_iso_to_ms(entry.timestamp),"pnl":entry.raw["pnl"]})
        marks = await self.paper_marks([s for s,q in net.items() if q],as_of)
        specs = {}
        for symbol in sorted(symbols):
            fact = await read_public_venue_facts(self.store,symbol,as_of)
            specs[symbol] = {"contract_multiplier":fact["contract_multiplier"]}
        account = await paper_account_state(PITView(), marks=marks["marks"], contract_specs=specs,environment="PAPER")
        losses = realized_loss_projection(outcomes,capital=account["capital"],as_of_ms=end)
        return {**account, **losses, "mark_set":marks, "as_of":as_of,
                "ledger_event_ids":[e.event_id for e in entries]}

    async def prepare_engine_bundle(self, symbol: str, timeframe: str, as_of: str,
                                    *, rtm_context: Mapping[str, Any] | None = None) -> dict:
        """Compute and persist a complete native bundle before plan admission.

        Final bridge/risk projection is separate; this method never presents
        an engine-only bundle as all REQUIRED_CONTEXT_KEYS/REQUIRED_RISK_KEYS.
        """
        from dataclasses import replace
        artifact = load_classifier(self.classifier_path)
        measured = mtf = None
        if rtm_context is None:
            measured = await self.quality_window(symbol, timeframe, as_of)
            mtf = await self.mtf_inputs(symbol, timeframe, as_of)
            rtm_context = {"derive_avg_quality": True, "mtf_align": mtf["mtf_align"]}
        rows = await (await self.store.db.execute(
            "SELECT COUNT(*) FROM market_observation WHERE symbol=? AND timeframe=? "
            "AND candle_status IN ('CLOSED','CORRECTED') AND open_time<=?",
            (symbol, timeframe, as_of))).fetchone()
        window = await self.window(symbol, timeframe, as_of, int(rows[0]))
        if not window:
            raise BridgeError("NO_MARKET_DATA", f"{symbol}:{timeframe}")
        last = None
        async for item in self.feature_timeline(symbol, timeframe, window, incremental=True):
            last = item
        if last is None or "vector" not in last:
            raise BridgeError("E11_CONTEXT_UNAVAILABLE", str((last or {}).get("reason", "empty timeline")))
        if measured is not None:
            expected = [(o.timestamp, o.content_hash()) for o in last["frame"]["raw_window"]]
            actual = [(o.timestamp, o.content_hash()) for o in measured["window"]]
            if actual != expected:
                raise BridgeError("QUALITY_PROVENANCE_UNAVAILABLE", "engine/quality window mismatch")
            last["frame"]["raw_window"] = measured["window"]
            history_candles = [E12.observation_to_candle(o) for o in closed_engine_window(window[:-1],timeframe)]
            last["temporal_profile"] = E12.compute_temporal_profile(
                E12.returns_by_tod_from_candles(history_candles),as_of=int(history_candles[-1]["ts"]))
        bundle = complete_engine_bundle(last, symbol, timeframe, artifact, rtm_context=rtm_context)
        bundle["volatility_history"] = [e.state for e in last["volatility_stream"]["evidence"]]
        if measured is not None:
            bundle["measured_quality"] = measured
            bundle["measured_mtf"] = {k: v for k, v in mtf.items() if k != "frames"}
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

    def _raw_content_hash(self, observation: Any) -> str:
        """Memo only the frozen content_hash payload, with exact typed values.

        repr preserves Decimal precision (numeric equality alone would alias
        100.0 and 100.00). Every miss calls the native method on the actual
        observation; this never constructs or modifies a raw record.
        """
        key = (type(observation), tuple((type(value),repr(value)) for value in
            (observation.symbol,observation.timeframe,observation.timestamp,
             observation.open,observation.close,observation.volume)))
        if key not in self._content_hashes:
            digest = observation.content_hash()
            if len(self._content_hashes) >= 4096:
                del self._content_hashes[next(iter(self._content_hashes))]
            self._content_hashes[key] = digest
        return self._content_hashes[key]

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
            content_hash = self._raw_content_hash(obs)
            if row is None or row[3] != content_hash or row[2] != hashlib.sha256(row[3].encode()).hexdigest():
                raise BridgeError("RAW_LINEAGE_INVALID", "observation/raw content binding missing")
            if row[4] is None:
                raise BridgeError("RAW_LINEAGE_INVALID", "raw availability unavailable")
            if _iso_to_ms(row[4]) > end:
                continue  # never expose not-yet-available observations
            oi_lag = (max(0., (end - _iso_to_ms(row[5])) / 1000.) if row[5] is not None else None)
            result.append(replace(obs, availability_time=row[4], oi_timestamp=row[5], oi_lag_seconds=oi_lag))
            self._raw_lineage[(symbol, timeframe, obs.timestamp, content_hash)] = {
                "observation_id": row[1], "oi_state": row[6], "availability_time": row[4]}
        return result

    async def training_dep_window(self, symbol: str, timeframe: str, *,
                                  close_to_ms: int, count: int) -> list[Any]:
        """D35 training-only HTF prefetch: one verified read per cell.

        Replaces thousands of identical per-bar window() re-reads over one
        training cell. Every dependency row closed at or before the cell end
        is returned (no lower cut: gapped history can reach arbitrarily far
        back for a 301-bar slice); each per-bar slice re-applies the gates
        via slice_training_window, so served slices equal live window()
        calls exactly (parity-tested). Runtime (G1) never uses this path.
        """
        return await self.window(symbol, timeframe, _ms_to_iso(close_to_ms), count) if count else []

    async def _frame_at(self, symbol: str, timeframe: str, as_of: str, *,
                        rows: list[Any] | None = None,
                        engine_profile: dict | None = None) -> dict[str, Any]:
        if rows is None:
            window = await self.window(symbol, timeframe, as_of, 301)
        else:
            window = slice_training_window(rows, _iso_to_ms(as_of), timeframe, 301)
        if len(window) < 51:
            raise BridgeError("INSUFFICIENT_HISTORY", f"{symbol}:{timeframe}")
        window = window[-300:]
        # Native engines consume the actual OI timestamp, not the wiring-only
        # query-clock lag. Keep that timestamp and every other input in the
        # identity; refresh both observation views on return. Otherwise an
        # unchanged HTF replays all native engines at every finer close.
        native_input = [{k:v for k,v in o.to_dict().items() if k != "oi_lag_seconds"} for o in window]
        key = (symbol, timeframe, hashlib.sha256(canonical_json(native_input).encode()).hexdigest())
        if key not in self._frames:
            self._frames[key] = upstream_frame(window, symbol, timeframe, engine_profile=engine_profile)
            if len(self._frames) > 32:
                del self._frames[next(iter(self._frames))]
        return {**self._frames[key], "raw_window":window,
                "window":closed_engine_window(window,timeframe)}

    async def feature_timeline(self, symbol: str, timeframe: str, window: list[Any], *,
                               incremental: bool = False,
                               dep_rows: dict[str, list[Any]] | None = None,
                               engine_profile: dict | None = None):
        """Shared PIT training/runtime X_t stream; explicit warmup refusals.

        HTF bias observations are strictly last-closed as of each historical
        close, never current bias projected backward into a training sample.
        Training may serve HTF slices from prefetched rows (parity-tested);
        runtime always passes nothing and keeps live reads.
        """
        history = {key: [] for key in HISTORY_KEYS}
        atr14_history: list[float] | None = None
        seed_state = E11.RegimeEngine()
        mu, sigma, previous_momentum = seed_state.mu, seed_state.Sigma, seed_state.prev_mom
        volatility_stream = {"engine": E04.VolatilityEngineV4(timeframe=timeframe), "pending": [], "evidence": []}
        from dataclasses import replace
        signatures = [canonical_json({k:v for k,v in o.to_dict().items() if k != "oi_lag_seconds"}) for o in window]
        cached = self._timelines.get((symbol,timeframe)) if incremental else None
        start, last_item = 0, None
        if cached and signatures[:len(cached["signatures"])] == cached["signatures"]:
            start = len(cached["signatures"])
            history, atr14_history = cached["history"], cached["atr14_history"]
            mu, sigma, previous_momentum = cached["mu"], cached["sigma"], cached["previous_momentum"]
            volatility_stream, last_item = cached["volatility_stream"], cached["last_item"]
            if start == len(window):
                yield last_item
                return
        for index in range(start,len(window)):
            obs = window[index]
            as_of = _ms_to_iso(close_time_ms(_iso_to_ms(obs.timestamp), timeframe))
            volatility_stream["pending"].append(E04.observation_to_bar(closed_engine_window([obs], timeframe)[0], timeframe))
            if index < 50:
                yield {"index": index, "as_of": as_of, "reason": "UPSTREAM_WARMUP", "confirmation": False}
                continue
            # Each historical feature uses its own PIT lag, not the final
            # request's clock. This also makes exact-prefix continuation safe.
            source_window = [replace(o,oi_lag_seconds=(max(0.,(_iso_to_ms(as_of)-_iso_to_ms(o.oi_timestamp))/1000)
                if o.oi_timestamp is not None else None)) for o in window[max(0,index-299):index+1]]
            if any(o.availability_time is None or _iso_to_ms(o.availability_time) > _iso_to_ms(as_of) for o in source_window):
                yield {"index": index, "as_of": as_of, "confirmation": None, "reason": "PIT_VIOLATION"}
                continue
            structure = structure_projection(source_window, symbol, timeframe,
                                               engine_profile=engine_profile)
            confirmation = structural_confirmation(source_window, symbol, timeframe, result=structure)
            try:
                frame = upstream_frame(source_window, symbol, timeframe, atr14_history=atr14_history,
                                       structure_result=structure, volatility_stream=volatility_stream,
                                       engine_profile=engine_profile)
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
                    htf = (frame if tf == timeframe else await self._frame_at(
                        symbol, tf, as_of, rows=(dep_rows or {}).get(tf),
                        engine_profile=engine_profile))
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
            mark = time.monotonic() if engine_profile is not None else 0.0
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
            if engine_profile is not None:
                engine_profile["E11"] += time.monotonic() - mark
            last_item = item
            yield item
            # Normalization history can contain finite observations even when
            # its old window was degenerate. No invalid X_t updates the EWMA.
            for key, source in HISTORY_KEYS.items():
                history[key].append(float(ic[source]))
                history[key] = history[key][-E11.W_180D_H1:]

        if incremental and last_item is not None and last_item.get("index") == len(window)-1 and "vector" in last_item:
            self._timelines[(symbol,timeframe)] = {"signatures":signatures,"history":history,"atr14_history":atr14_history,
                "mu":mu,"sigma":sigma,"previous_momentum":previous_momentum,"volatility_stream":volatility_stream,"last_item":last_item}
        elif incremental:
            self._timelines.pop((symbol,timeframe),None)


class DegenerateTraining(BridgeError):
    def __init__(self, histogram: dict[str, int], excluded: dict[str, int], window: dict):
        self.histogram, self.excluded, self.training_window = histogram, excluded, window
        # D36: refuse only when one of the eight rule-tree classes is empty;
        # TRANSITION, a derived state, may be zero. First such name in
        # E11.REGIMES order.
        self.refusing_class = next(name for name in E11.REGIMES
                                   if name != "TRANSITION" and histogram[name] == 0)
        super().__init__(f"EMPTY_CLASS:{self.refusing_class}",
                         f"zero delayed-label members: {self.refusing_class}")


class TrainingTimeout(BridgeError):
    """D35: --max-minutes bounds ONE invocation; completed cells stay cached."""

    def __init__(self, completed: list[str], remaining: list[str], next_cell: str | None):
        self.cells_completed, self.cells_remaining, self.next_cell = completed, remaining, next_cell
        super().__init__("TRAINING_TIME_LIMIT",
                         "D35 one-invocation bound reached; completed cells are cached")


# D36 (ISSUE-CP14-061 / ADR-CP14-023): TRANSITION is a derived state
# (E11 Section 1.4 and Section 3.2 branch 2: H >= theta_H implies
# TRANSITION by construction), never a learned class. The fit requires
# every E11.REGIMES member except TRANSITION; an empty TRANSITION
# histogram is accepted.
FIT_REQUIRED_CLASSES = tuple(name for name in E11.REGIMES if name != "TRANSITION")


def _fit_core(
    x: Any,
    y: Any,
    seed: int,
    iterations: int,
    learning_rate: float,
    l2: float,
    class_weights: bool,
    design: Any,
) -> tuple[Any, Any]:
    """Shared gradient-descent core for fit_multinomial and fit_multinomial_study.

    D47: iterations, learning_rate, l2, class_weights come from protocol.
    Bit-identical to pre-D47 for legacy {2000,0.2,0.0,False}.
    """
    rng = np.random.default_rng(seed % (2 ** 128))
    W = rng.normal(0.0, 0.01, (9, 8))
    b = np.zeros(9)
    weights = None
    if class_weights:
        counts = np.bincount(y, minlength=9).astype(float)
        present = counts > 0
        w = np.zeros(9)
        w[present] = 1.0 / counts[present]
        w[present] /= w[present].mean()
        weights = w
    for _ in range(int(iterations)):
        z = design @ W.T + b
        z -= np.max(z, axis=1, keepdims=True)
        probabilities = np.exp(z)
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        probabilities[np.arange(len(y)), y] -= 1.0
        if class_weights:
            assert weights is not None
            probabilities = probabilities * weights[y][:, None]
        gradient_W = probabilities.T @ design / len(y)
        gradient_b = probabilities.mean(axis=0)
        if l2:
            gradient_W = gradient_W + float(l2) * W
        W -= float(learning_rate) * gradient_W
        b -= float(learning_rate) * gradient_b
    return W, b


def fit_multinomial(
    X: list[list[float]],
    labels: list[str],
    seed: int,
    protocol: Mapping[str, Any],
) -> tuple[list, list]:
    """D47 governed fit: fixed-order full-batch multinomial log-loss descent.

    protocol is mandatory per D47: {iterations, learning_rate, l2, class_weights}.
    CP-14.5 C2: there is no default — a missing protocol is a TypeError from the
    signature and an explicit ``None`` is refused CONFIGURATION_INVALID. The
    legacy {2000,0.2,0.0,False} mapping must be passed explicitly, and is then
    bit-identical to the pre-D47 body.
    The optimizer's seeded initialization and K=9 rows are unchanged.
    P2 {100000,0.2,0.0,False} identity to fit_multinomial_study non-standardised.
    """
    if protocol is None:
        raise BridgeError("CONFIGURATION_INVALID",
                          "fit protocol required: protocol is mandatory per D47")
    try:
        if not isinstance(protocol, Mapping) or set(protocol) != {"iterations", "learning_rate", "l2", "class_weights"}:
            raise ValueError("protocol schema")
        iterations = protocol["iterations"]
        learning_rate = protocol["learning_rate"]
        l2 = protocol["l2"]
        class_weights = protocol["class_weights"]
        if type(iterations) is not int or iterations <= 0:
            raise ValueError("iterations")
        if type(learning_rate) not in (int, float) or not math.isfinite(float(learning_rate)) or float(learning_rate) <= 0:
            raise ValueError("learning_rate")
        if type(l2) not in (int, float) or not math.isfinite(float(l2)) or float(l2) < 0:
            raise ValueError("l2")
        if type(class_weights) is not bool:
            raise ValueError("class_weights")
    except (ValueError, TypeError, KeyError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", f"fit protocol invalid: {exc}") from exc

    x = np.asarray(X, dtype=float)
    y = np.array([E11.REGIMES.index(label) for label in labels])
    if x.shape != (len(labels), 8) or not np.isfinite(x).all() or not len(labels):
        raise BridgeError("CONFIGURATION_INVALID", "invalid training matrix")
    if any(name not in set(labels) for name in FIT_REQUIRED_CLASSES):
        raise BridgeError("CONFIGURATION_INVALID", "eight rule-tree classes required for fitting")
    W, b = _fit_core(x, y, seed, int(iterations), float(learning_rate), float(l2), bool(class_weights), x)
    if not np.isfinite(W).all() or not np.isfinite(b).all():
        raise BridgeError("CONFIGURATION_INVALID", "non-finite fitted parameters")
    return W.tolist(), b.tolist()


# CP-14.3 (ADR-CP14-025): the extended validation surface. The bucket edges
# are the documented p_max ranges [0,.3) [.3,.5) [.5,.7) [.7,1]; the last one
# is closed at 1.0 because a saturated fit reaches p_max = 1.0 exactly and no
# sample may fall outside every bucket. An empty bucket is reported as None,
# never as a fabricated median.
ENTROPY_PMAX_BUCKETS = ((0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 1.0))
GATE7_ENTROPY_NORM_MAX = 0.85


def training_metrics(
    labels: list[str],
    entropies: list[float],
    pmaxes: list[float],
    probabilities: list[list[float]],
    theta: float,
) -> dict:
    """D47 governed metric core.

    theta is passed from get_params().entropy_threshold (governed YAML per D49).
    Verdict D47: PASS iff train_accuracy>=0.70 AND share_pmax_ge_0_50>=0.75 AND
    min over eight FIT_REQUIRED_CLASSES of per_class share_pmax_ge_0_50 >=0.40
    else WARN. share_H_ge_theta is informational only. WARN never blocks.
    Adds min_class_share_pmax_ge_0_50, verdict_rule, H percentiles p20/p30/p70/p80.
    theta_recommendation is the D49 triple mapping (CP-14.5 C1): {"theta_H": H p80,
    "quality_H_Q2": H p90, "quality_H_Q5": H p30} — exactly the values D49 says are
    to be set later from the H distribution. Informational only: nothing in the
    decision path consumes it, and params/e11_params_v4.yaml is never written here.
    """
    if type(theta) not in (int, float) or not math.isfinite(float(theta)):
        raise BridgeError("CONFIGURATION_INVALID", "theta_H unavailable")
    theta_f = float(theta)
    n = len(labels)
    if n == 0:
        raise BridgeError("CONFIGURATION_INVALID", "empty metrics")
    per_class: dict[str, dict[str, Any]] = {
        name: {"n": 0, "share_H_ge_theta": 0.0, "share_pmax_ge_0_50": 0.0}
        for name in E11.REGIMES}
    correct, log_losses = 0, []
    for index, label in enumerate(labels):
        H, p_max = entropies[index], pmaxes[index]
        row = probabilities[index]
        stats = per_class[label]
        stats["n"] += 1
        if H >= theta_f:
            stats["share_H_ge_theta"] += 1.0
        if p_max >= 0.50:
            stats["share_pmax_ge_0_50"] += 1.0
        label_index = E11.REGIMES.index(label)
        if int(np.argmax(row)) == label_index:
            correct += 1
        log_losses.append(-math.log(max(float(row[label_index]), float(E11.EPS))))
    share_h_ge_theta = sum(1.0 for H in entropies if H >= theta_f) / n
    share_pmax_ge_0_50 = sum(1.0 for p in pmaxes if p >= 0.50) / n
    for stats in per_class.values():
        if stats["n"]:
            stats["share_H_ge_theta"] /= stats["n"]
            stats["share_pmax_ge_0_50"] /= stats["n"]
    percentiles = np.percentile(
        np.asarray(entropies, dtype=float),
        [10.0, 20.0, 25.0, 30.0, 50.0, 70.0, 75.0, 80.0, 90.0],
    )
    by_bucket = {}
    for index, (lower, upper) in enumerate(ENTROPY_PMAX_BUCKETS):
        closed = index == len(ENTROPY_PMAX_BUCKETS) - 1
        inside = [H for H, p in zip(entropies, pmaxes)
                  if lower <= p < upper or (closed and p == upper)]
        by_bucket[f"[{lower:.1f},{upper:.1f}{']' if closed else ')'}"] = (
            float(np.median(inside)) if inside else None)
    train_accuracy = correct / n
    # min over eight rule-tree classes of per_class share_pmax_ge_0_50
    min_class_share = min(
        per_class[name]["share_pmax_ge_0_50"] for name in FIT_REQUIRED_CLASSES
    )
    verdict = (
        "PASS"
        if train_accuracy >= 0.70
        and share_pmax_ge_0_50 >= 0.75
        and min_class_share >= 0.40
        else "WARN"
    )
    return {
        "share_H_ge_theta": share_h_ge_theta,
        "share_H_ge_0_80": sum(1.0 for H in entropies if H >= 0.80) / n,
        "share_H_lt_0_40": sum(1.0 for H in entropies if H < 0.40) / n,
        "share_pmax_ge_0_50": share_pmax_ge_0_50,
        "min_class_share_pmax_ge_0_50": float(min_class_share),
        "share_h_norm_gt_0_85": sum(
            1.0 for H in entropies if E11.entropy_normalized(H) > GATE7_ENTROPY_NORM_MAX
        ) / n,
        "train_accuracy": train_accuracy,
        "train_log_loss": float(sum(log_losses) / n),
        "H_min": float(min(entropies)),
        "H_median": float(np.median(entropies)),
        "H_max": float(max(entropies)),
        "pmax_median": float(np.median(pmaxes)),
        "H_percentiles": {
            "p10": float(percentiles[0]),
            "p20": float(percentiles[1]),
            "p25": float(percentiles[2]),
            "p30": float(percentiles[3]),
            "p50": float(percentiles[4]),
            "p70": float(percentiles[5]),
            "p75": float(percentiles[6]),
            "p80": float(percentiles[7]),
            "p90": float(percentiles[8]),
        },
        # CP-14.5 C1: the D49 triple, not a single float. p80 -> theta_H,
        # p90 -> quality_H_Q2, p30 -> quality_H_Q5 (percentiles above are
        # [10, 20, 25, 30, 50, 70, 75, 80, 90]).
        "theta_recommendation": {
            "theta_H": float(percentiles[7]),
            "quality_H_Q2": float(percentiles[8]),
            "quality_H_Q5": float(percentiles[3]),
        },
        "entropy_by_pmax_bucket": by_bucket,
        "per_class": per_class,
        "verdict": verdict,
        "verdict_rule": "D47",
    }


def training_validation(
    X: list[list[float]],
    labels: list[str],
    W: list,
    b: list,
    theta: float | None = None,
) -> dict:
    """Mandatory post-fit entropy/confidence report (D47 governed).

    theta_H is taken from get_params().entropy_threshold (governed YAML per D49),
    not from E11.THETA_H constant. Verdict D47 per training_metrics.
    WARN never blocks. Every sample's H and probabilities come from the runtime
    function itself (E11.compute_logits_softmax), never a reimplementation.
    """
    if not X or len(X) != len(labels) or any(label not in E11.REGIMES for label in labels):
        raise BridgeError("CONFIGURATION_INVALID", "training validation needs matched regime samples")
    if theta is None:
        try:
            theta = float(E11.get_params().entropy_threshold)
        except Exception as exc:
            raise BridgeError("CONFIGURATION_INVALID", "governed theta_H unavailable") from exc
    entropies, pmaxes, probabilities = [], [], []
    for row, _label in zip(X, labels):
        _, probs, H = E11.compute_logits_softmax(dict(zip(E11.VECTOR_KEYS, row)), W, b)
        entropies.append(H)
        pmaxes.append(max(probs))
        probabilities.append(probs)
    n = len(X)
    return {"samples": n, "theta_H": float(theta),
            **training_metrics(labels, entropies, pmaxes, probabilities, float(theta))}


# CP-14.4 D47/D49: fixed named fit-protocol grid, RESEARCH-ONLY train-e11 --fit-study.
# P0 legacy {2000,0.2,0.0,False}, P2 is D47 governed {100000,0.2,0.0,False}.
# Added P10 {100000,0.2,0.0,True}, P11 {300000,0.2,0.0,False}, P12 {300000,0.2,0.0,True}
# per C7. No variant is a protocol change and none is ever written to params/.
FIT_STUDY_VARIANTS: tuple[dict[str, Any], ...] = (
    {"variant": "P0", "iterations": 2000, "learning_rate": 0.2, "l2": 0.0,
     "class_weights": False, "standardise": False},
    {"variant": "P1", "iterations": 20000, "learning_rate": 0.2, "l2": 0.0,
     "class_weights": False, "standardise": False},
    {"variant": "P2", "iterations": 100000, "learning_rate": 0.2, "l2": 0.0,
     "class_weights": False, "standardise": False},
    {"variant": "P3", "iterations": 20000, "learning_rate": 0.2, "l2": 1e-3,
     "class_weights": False, "standardise": False},
    {"variant": "P4", "iterations": 20000, "learning_rate": 0.2, "l2": 1e-2,
     "class_weights": False, "standardise": False},
    {"variant": "P5", "iterations": 20000, "learning_rate": 0.2, "l2": 0.0,
     "class_weights": True, "standardise": False},
    {"variant": "P6", "iterations": 20000, "learning_rate": 0.2, "l2": 1e-3,
     "class_weights": True, "standardise": False},
    {"variant": "P7", "iterations": 20000, "learning_rate": 0.2, "l2": 1e-2,
     "class_weights": True, "standardise": False},
    {"variant": "P8", "iterations": 20000, "learning_rate": 0.2, "l2": 0.0,
     "class_weights": False, "standardise": True},
    {"variant": "P9", "iterations": 20000, "learning_rate": 0.2, "l2": 0.0,
     "class_weights": True, "standardise": True},
    {"variant": "P10", "iterations": 100000, "learning_rate": 0.2, "l2": 0.0,
     "class_weights": True, "standardise": False},
    {"variant": "P11", "iterations": 300000, "learning_rate": 0.2, "l2": 0.0,
     "class_weights": False, "standardise": False},
    {"variant": "P12", "iterations": 300000, "learning_rate": 0.2, "l2": 0.0,
     "class_weights": True, "standardise": False},
)
FIT_STUDY_PER_CLASS_ROW = ("CHOP", "TREND", "TREND_EXPANSION", "RANGE")


def fit_multinomial_study(X: list[list[float]], labels: list[str], seed: int, *,
                          iterations: int = 2000, learning_rate: float = 0.2, l2: float = 0.0,
                          class_weights: bool = False,
                          standardise: bool = False) -> tuple[list, list, dict]:
    """Research-only fit protocol for ``train-e11 --fit-study`` (ADR-CP14-025, CP-14.4 fix).

    Same seeded initialization and full-batch gradient-descent shape as
    ``fit_multinomial`` (shared core), with optional L2 on W only,
    inverse-frequency class weights normalised to mean 1, and z-score
    standardisation computed on training set and folded back into W/b so
    runtime contract (raw 8 features -> logits) is unchanged.

    C7 fix: fold-back is W_raw=W/scale row-wise, b_raw=b-W_raw@mean, proven
    with random X probs equal 1e-9 (not W/scale then b-W@(mean/scale) which
    double-divides).
    Returns ``(W, b, info)``.
    """
    x = np.asarray(X, dtype=float)
    y = np.array([E11.REGIMES.index(label) for label in labels])
    if x.shape != (len(labels), 8) or not np.isfinite(x).all() or not len(labels):
        raise BridgeError("CONFIGURATION_INVALID", "invalid training matrix")
    if any(name not in set(labels) for name in FIT_REQUIRED_CLASSES):
        raise BridgeError("CONFIGURATION_INVALID", "eight rule-tree classes required for fitting")
    started = time.monotonic()
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale = np.where(scale > 0.0, scale, 1.0)
    design = (x - mean) / scale if standardise else x
    W, b = _fit_core(x, y, seed, int(iterations), float(learning_rate), float(l2), bool(class_weights), design)
    if not np.isfinite(W).all() or not np.isfinite(b).all():
        raise BridgeError("CONFIGURATION_INVALID", "non-finite fitted parameters")
    if standardise:
        # C7 fixed fold-back: W_raw = W / scale row-wise, b_raw = b - W_raw @ mean
        W_raw = W / scale
        b_raw = b - W_raw @ mean
        W, b = W_raw, b_raw
    entropies = [E11.compute_logits_softmax(dict(zip(E11.VECTOR_KEYS, row)), W, b)[2]
                 for row in X]
    info = {"iterations": int(iterations), "learning_rate": float(learning_rate),
            "l2": float(l2), "weights": bool(class_weights),
            "standardised": bool(standardise), "seconds": time.monotonic() - started,
            "standardisation": ({"mean": [float(v) for v in mean],
                                 "std": [float(v) for v in scale]} if standardise else None),
            "entropies": entropies}
    return W.tolist(), b.tolist(), info


def run_fit_study(X: list[list[float]], labels: list[str], *,
                  seed: int = DEFAULT_TRAINING_SEED,
                  variants: tuple[dict[str, Any], ...] = FIT_STUDY_VARIANTS) -> dict:
    """D47/D49: evaluate named grid, returns report body.

    Research-only: fits in memory, returns diagnostics. Writes no artifact.
    Every variant records theta_for_10/20/30 pct (H p90/80/70) and
    min_class_share_pmax_ge_0_50 (from D47 metrics). theta_H is governed
    entropy_threshold from get_params().
    """
    try:
        governed_theta = float(E11.get_params().entropy_threshold)
    except Exception:
        governed_theta = float(E11.THETA_H)
    records = []
    for spec in variants:
        W, b, info = fit_multinomial_study(
            X, labels, seed, iterations=spec["iterations"],
            learning_rate=spec["learning_rate"], l2=spec["l2"],
            class_weights=spec["class_weights"], standardise=spec["standardise"])
        entropies = info.pop("entropies")
        metrics = training_validation(X, labels, W, b, theta=governed_theta)
        record = {"variant": spec["variant"], **info, **metrics}
        # Empirical H cut-offs: 90th/80th/70th percentiles classify exactly
        # 10%/20%/30% as H >= theta — for every variant per C7.
        theta_cuts = np.percentile(np.asarray(entropies, dtype=float), [90.0, 80.0, 70.0])
        record["theta_for_10pct"] = float(theta_cuts[0])
        record["theta_for_20pct"] = float(theta_cuts[1])
        record["theta_for_30pct"] = float(theta_cuts[2])
        records.append(record)
    return {"samples": len(X), "seed": int(seed),
            "variants": records, "theta_H": governed_theta}


def load_fit_study_cache(*, timeframes: Any = DEFAULT_TRAINING_TIMEFRAMES,
                         symbols: Any = CORE10_SYMBOLS,
                         max_bars_per_cell: int | None = DEFAULT_MAX_BARS_PER_CELL,
                         cache_dir: str | Path | None = None) -> dict:
    """Load every scoped cell from the D35 cache only (ADR-CP14-025).

    The study never recomputes a feature and never reads the store: a cell is
    a hit only when its cache payload matches the same protocol hash, cell
    identity, vector keys and sample schema that training enforces
    (``read_cell_cache``). Any missing or invalid cell refuses with
    ``FIT_STUDY_REQUIRES_CACHE`` and names every cell it needs.
    """
    timeframes, symbols = training_scope(timeframes, symbols)
    max_bars = training_bar_cap(max_bars_per_cell)
    protocol_hash = training_protocol_hash(timeframes, symbols, max_bars)
    cell_dir = (Path(cache_dir) if cache_dir is not None else E11_TRAIN_CACHE_ROOT) / protocol_hash
    X, labels, stamps, cells, missing = [], [], [], [], []
    for symbol in symbols:
        for timeframe in timeframes:
            cell = symbol + ":" + timeframe
            payload = read_cell_cache(cell_dir / f"{symbol}_{timeframe}.json", cell=cell,
                                      protocol_hash=protocol_hash, input_hash=None)
            if payload is None:
                missing.append(cell)
                continue
            for sample in payload["samples"]:
                labels.append(sample["label"])
                X.append([float(value) for value in sample["vector"]])
                stamps.append(sample["as_of"])
            cells.append({"cell": cell, "samples": len(payload["samples"]),
                          "closed_bars": payload["closed_bars"],
                          "input_hash": payload.get("input_hash")})
    if missing:
        raise BridgeError("FIT_STUDY_REQUIRES_CACHE",
                          "cache-only study; missing or invalid cells: " + ",".join(missing))
    if not X:
        raise BridgeError("FIT_STUDY_REQUIRES_CACHE", "cache holds no samples for the scope")
    return {"protocol_hash": protocol_hash, "cache_dir": str(cell_dir), "cells": cells,
            "X": X, "labels": labels, "as_of": stamps, "samples": len(X)}


def training_scope(timeframes=DEFAULT_TRAINING_TIMEFRAMES, symbols=CORE10_SYMBOLS) -> tuple[tuple, tuple]:
    """D30 defaults unchanged; explicit closeout fallback scope is opt-in."""
    def selected(value, allowed):
        values = [v.strip() for v in value.split(",")] if isinstance(value, str) else list(value)
        if not values or len(values) != len(set(values)) or any(v not in allowed for v in values):
            raise BridgeError("TRAINING_SCOPE_INVALID", "use authorized timeframes 15m,30m,1h,2h,4h and Core-10 symbols only")
        return tuple(v for v in allowed if v in values)
    return selected(timeframes, AUTHORIZED_TRAINING_TIMEFRAMES), selected(symbols, CORE10_SYMBOLS)


def training_time_limit(minutes: float) -> float:
    value = float(minutes)
    if not math.isfinite(value) or value < 0:
        raise BridgeError("TRAINING_LIMIT_INVALID", "max-minutes must be finite and nonnegative")
    return value * 60.0


def training_bar_cap(value: int | None) -> int | None:
    """D35 --max-bars-per-cell: None keeps D30 unlimited; else a positive int."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise BridgeError("TRAINING_BARS_INVALID", "max-bars-per-cell must be a positive integer")
    return value


def training_protocol_hash(timeframes: tuple, symbols: tuple, max_bars: int | None) -> str:
    """D35 cache namespace; the identical value is stored in the artifact."""
    return hashlib.sha256(canonical_json(
        {"protocol": TRAINING_QUERY, "timeframes": timeframes, "symbols": symbols,
         "max_bars_per_cell": max_bars}).encode()).hexdigest()


def cell_input_hash(window: list[Any], dep_rows: Mapping[str, list[Any]],
                    max_bars: int | None) -> str:
    """D35 per-cell input identity over exactly the consumed CLOSED rows.

    Full observation payloads (including high/low, which the native
    duplicate-detection hash does not cover) identify the cell's consumed
    bars and every prefetched HTF dependency row; only the clock-derived
    wiring lag is excluded. Any consumed-row change (new bars, wick-only
    corrections, availability gating under a new clock) changes the digest
    and forces recomputation; nothing else invalidates a completed cell.
    """
    def identity(obs):
        return {k: v for k, v in obs.to_dict().items() if k != "oi_lag_seconds"}
    return hashlib.sha256(canonical_json(
        {"cell": [identity(o) for o in window],
         "deps": {tf: [identity(o) for o in rows] for tf, rows in sorted(dep_rows.items())},
         "max_bars_per_cell": max_bars}).encode()).hexdigest()


def read_cell_cache(path: Path, *, cell: str, protocol_hash: str,
                    input_hash: str | None) -> dict | None:
    """Load a completed cell's finalized samples, or None to recompute.

    Missing files, malformed JSON, schema drift, protocol/input mismatch or
    any non-finite value all mean recompute — never a partial or foreign
    sample set. Python/JSON float repr round-trips exactly, so a validated
    payload reproduces the original X/labels bit-for-bit.

    ``input_hash=None`` is the cache-only research mode (ADR-CP14-025): the
    caller has no store-derived input identity, so the recorded one is
    accepted as-is; every other guard still applies. Training always passes
    the recomputed hash.
    """
    import json
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        if not isinstance(payload, dict) or payload.get("format") != E11_TRAIN_CACHE_FORMAT:
            return None
        if payload.get("cell") != cell or payload.get("training_query_sha256") != protocol_hash:
            return None
        if input_hash is not None and payload.get("input_hash") != input_hash:
            return None
        if list(payload.get("vector_keys", [])) != list(E11.VECTOR_KEYS):
            return None
        samples = payload.get("samples")
        excluded = payload.get("excluded")
        if not isinstance(samples, list) or not isinstance(excluded, dict):
            return None
        for sample in samples:
            if not isinstance(sample, dict) or sample.get("label") not in E11.REGIMES:
                return None
            if not isinstance(sample.get("as_of"), str):
                return None
            vector = sample.get("vector")
            if (not isinstance(vector, list) or len(vector) != 8
                    or any(type(v) is not float or not math.isfinite(v) for v in vector)):
                return None
        for reason, count in excluded.items():
            if not isinstance(reason, str) or type(count) is not int or count < 0:
                return None
        if type(payload.get("closed_bars")) is not int:
            return None
    except (AttributeError, TypeError):
        return None
    return payload


def write_cell_cache(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomically persist one completed cell; failures refuse loudly.

    A torn or silently missing cache would trap a phone campaign in an
    endless TRAINING_TIME_LIMIT loop, so OSError here is fatal to the run.
    """
    import json
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".cell-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(payload, separators=(",", ":"), sort_keys=True))
            stream.write("\n")
        os.replace(temporary, path)
    except OSError as exc:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise BridgeError("TRAINING_CACHE_UNAVAILABLE", f"cell cache write failed: {path.name}") from exc


async def train_classifier(store: Any, *, seed: int = DEFAULT_TRAINING_SEED,
                           now: Callable[[], float] = time.time,
                           timeframes: Any = DEFAULT_TRAINING_TIMEFRAMES,
                           symbols: Any = CORE10_SYMBOLS,
                           max_minutes: float = DEFAULT_TRAINING_MAX_MINUTES,
                           max_bars_per_cell: int | None = DEFAULT_MAX_BARS_PER_CELL,
                           cache_dir: str | Path | None = None,
                           profile: bool = False,
                           optimize: bool = True,
                           progress: Callable[[dict], None] | None = None,
                           monotonic: Callable[[], float] = time.monotonic) -> tuple[dict, dict]:
    """Train from actual store windows only. No file or fixture fallback.

    D35: each completed cell's finalized samples persist under
    data/e11_train_cache/<protocol>/ and reload on reruns with the same
    protocol hash; --max-minutes bounds one invocation. D21 labels and D30
    defaults are unchanged. D36: the refusal is the eight rule-tree classes
    (TRANSITION, a derived state, may be empty) and the report carries a
    mandatory "validation" entropy/confidence section (never part of the
    artifact). `optimize=False` is the unoptimized reference path for
    exact-parity tests only.
    """
    timeframes, symbols = training_scope(timeframes, symbols)
    max_bars = training_bar_cap(max_bars_per_cell)
    limit = training_time_limit(max_minutes)
    started = monotonic()
    def check_deadline():
        if monotonic() - started >= limit:
            raise BridgeError("TRAINING_TIME_LIMIT", "D35 maximum elapsed training time reached")
    check_deadline()
    protocol_hash = training_protocol_hash(timeframes, symbols, max_bars)
    cell_dir = (Path(cache_dir) if cache_dir is not None else E11_TRAIN_CACHE_ROOT) / protocol_hash
    try:
        cell_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BridgeError("TRAINING_CACHE_UNAVAILABLE", "cell cache directory unwritable") from exc
    counts = {(r[0], r[1]): r[3] for r in await (await store.db.execute(CELL_QUERY)).fetchall()}
    producer = EngineContextProducer(store, now=now)
    histogram = {name: 0 for name in E11.REGIMES}
    excluded: dict[str, int] = {}
    X, labels, stamps = [], [], []
    end_ms = int(now() * 1000)
    for symbol, timeframe in [(symbol, tf) for symbol in symbols for tf in timeframes]:
        check_deadline()
        cell = symbol + ":" + timeframe
        cell_start, eligible_before = monotonic(), len(labels)
        count = counts.get((symbol, timeframe), 0)
        read_start = time.monotonic()
        window = await producer.window(symbol, timeframe, _ms_to_iso(end_ms), int(count)) if count else []
        window_read = time.monotonic() - read_start
        if max_bars is not None:
            window = window[-max_bars:]
        label_seconds = 0.0
        engines = {name: 0.0 for name in PROFILE_ENGINE_ORDER} if profile else None
        cell_excluded: dict[str, int] = {}
        def exclude(reason):
            excluded[reason] = excluded.get(reason, 0) + 1
            cell_excluded[reason] = cell_excluded.get(reason, 0) + 1
        def report_cell(kind="cell", cache="miss", bars_done=None):
            if progress:
                message = {"kind": kind, "cell": cell,
                           "closed_bars": len(window), "eligible_samples": len(labels) - eligible_before,
                           "elapsed_seconds": monotonic() - cell_start}
                if kind == "tick":
                    message["bars_done"], message["bars_total"] = bars_done, len(window)
                else:
                    message["cache"] = cache
                    message["excluded"] = dict(cell_excluded)
                    message["profile"] = {"engines": dict(engines or {}),
                                          "window_read_seconds": window_read,
                                          "label_confirmation_seconds": label_seconds}
                progress(message)
        report_cell("started")
        if not window:
            exclude("EMPTY_CLOSED_WINDOW")
            report_cell()
            continue
        dep_rows: dict[str, list[Any]] = {}
        close_to = close_time_ms(_iso_to_ms(window[-1].timestamp), timeframe)
        for dep_tf in [tf for tf in ("4h", "1h", "15m") if tf != timeframe]:
            read_start = time.monotonic()
            dep_rows[dep_tf] = await producer.training_dep_window(
                symbol, dep_tf, close_to_ms=close_to,
                count=int(counts.get((symbol, dep_tf), 0)))
            window_read += time.monotonic() - read_start
        input_hash = cell_input_hash(window, dep_rows, max_bars)
        cached = read_cell_cache(cell_dir / f"{symbol}_{timeframe}.json", cell=cell,
                                 protocol_hash=protocol_hash, input_hash=input_hash)
        if cached is not None:
            for sample in cached["samples"]:
                histogram[sample["label"]] += 1
                labels.append(sample["label"])
                X.append([float(value) for value in sample["vector"]])
                stamps.append(sample["as_of"])
            for reason, number in cached["excluded"].items():
                excluded[reason] = excluded.get(reason, 0) + number
                cell_excluded[reason] = number
            report_cell(cache="hit")
            continue
        serving = dep_rows if optimize else None
        pending = []
        async for item in producer.feature_timeline(symbol, timeframe, window, dep_rows=serving,
                                                   engine_profile=engines):
            check_deadline()
            if (item["index"] + 1) % TRAIN_PROGRESS_EVERY_BARS == 0:
                report_cell("tick", bars_done=item["index"] + 1)
            # Keep just the 48 delayed candidates, not full engine states.
            pending.append({key: item[key] for key in ("index", "as_of", "confirmation", "vector", "rule0", "reason") if key in item})
            if len(pending) <= 48:
                continue
            mark = time.monotonic()
            candidate = pending.pop(0)
            if "vector" not in candidate:
                exclude(candidate.get("reason", "INVALID_FEATURE"))
            elif not contiguous_label_horizon(window, candidate["index"], timeframe):
                exclude("NONCONTIGUOUS_LABEL_HORIZON")
            elif any(type(f.get("confirmation")) is not bool for f in pending):
                exclude("LABEL_CONFIRMATION_UNAVAILABLE")
            else:
                label = candidate["rule0"] if any(f["confirmation"] for f in pending) else "TRANSITION"
                histogram[label] += 1
                labels.append(label)
                X.append([candidate["vector"][key] for key in E11.VECTOR_KEYS])
                stamps.append(candidate["as_of"])
            label_seconds += time.monotonic() - mark
        excluded["UNFINALIZED_TAIL"] = excluded.get("UNFINALIZED_TAIL", 0) + len(pending)
        cell_excluded["UNFINALIZED_TAIL"] = cell_excluded.get("UNFINALIZED_TAIL", 0) + len(pending)
        write_cell_cache(cell_dir / f"{symbol}_{timeframe}.json", {
            "format": E11_TRAIN_CACHE_FORMAT, "cell": cell,
            "training_query_sha256": protocol_hash, "input_hash": input_hash,
            "closed_bars": len(window), "max_bars_per_cell": max_bars,
            "vector_keys": list(E11.VECTOR_KEYS),
            "samples": [{"as_of": stamp, "label": label,
                         "vector": [float(value) for value in row]}
                        for stamp, label, row in zip(stamps[eligible_before:], labels[eligible_before:],
                                                    X[eligible_before:])],
            "excluded": dict(cell_excluded),
            "window_start": window[0].timestamp, "window_end": window[-1].timestamp})
        report_cell()
    check_deadline()
    training_window = {"start": min(stamps) if stamps else None, "end": max(stamps) if stamps else None,
                       "timeframes": list(timeframes), "symbols": list(symbols),
                       "default_timeframes": list(DEFAULT_TRAINING_TIMEFRAMES), "default_symbols": list(CORE10_SYMBOLS),
                       "max_bars_per_cell": max_bars}
    # D36: TRANSITION is a derived state (E11 Section 1.4 / Section 3.2
    # branch 2), so it may be empty. Only the eight rule-tree classes must
    # have delayed-label members; an empty required class still refuses.
    if any(histogram[name] == 0 for name in FIT_REQUIRED_CLASSES):
        raise DegenerateTraining(histogram, excluded, training_window)
    # D47: load governed fit protocol once per training invocation
    fit_protocol = load_e11_training_protocol()
    fit_start = time.monotonic()
    W, b = fit_multinomial(X, labels, seed, protocol=fit_protocol)
    fit_seconds = time.monotonic() - fit_start
    check_deadline()
    artifact = {"W": W, "b": b, "K": 9, "label_delay_candles": 48,
                "seed": seed, "fit_protocol": dict(fit_protocol),
                "training_window": training_window, "sample_count": len(X),
                "training_query_sha256": protocol_hash,
                "artifact_sha256": classifier_hash(W, b, seed, fit_protocol)}
    validate_classifier(artifact)
    validation = training_validation(X, labels, W, b)
    report = {"per_class_counts": histogram, "excluded": excluded,
              "fit_seconds": fit_seconds,
              "fit_protocol": dict(fit_protocol),
              "validation": validation,
              "verdict_rule": "D47"}
    return artifact, report


def _training_worker(connection, sqlite: str, seed: int, timeframes: tuple, symbols: tuple, max_minutes: float,
                     max_bars: int | None, cache_dir: str | None, profile: bool):
    """Isolated CPU worker. It never knows the artifact output path.

    D35: the worker owns the per-cell resume cache (fixed conventional
    layout, never the artifact path); only the parent returns a verified
    artifact to the atomic writer after successful training.
    """
    import asyncio
    from apex.data_catalog.store.sqlite_store import SQLiteStore
    async def run():
        store = await SQLiteStore(sqlite).open()
        try:
            artifact, report = await train_classifier(store, seed=seed, timeframes=timeframes,
                symbols=symbols, max_minutes=max_minutes, max_bars_per_cell=max_bars,
                cache_dir=cache_dir, profile=profile, progress=connection.send)
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
        max_minutes=DEFAULT_TRAINING_MAX_MINUTES, max_bars_per_cell=None,
        cache_dir=None, profile=False, progress=None) -> tuple[dict, dict]:
    """Hard wall-time supervisor, including CPU-bound native engine calls.

    asyncio.wait_for alone cannot interrupt those calls. Only the parent may
    return a verified artifact to the atomic writer after successful training.
    D35: ticks stream through for liveness; a timeout reports the completed,
    remaining and next cells so the next invocation resumes from the cache.
    """
    import asyncio
    import multiprocessing
    scope = training_scope(timeframes, symbols)
    ordered = [symbol + ":" + tf for symbol in scope[1] for tf in scope[0]]
    cache_arg = str(cache_dir) if cache_dir is not None else None
    deadline = time.monotonic() + training_time_limit(max_minutes)
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_training_worker,
                              args=(sender, sqlite, seed, *scope, max_minutes,
                                    training_bar_cap(max_bars_per_cell), cache_arg, profile))
    completed: list[str] = []
    current = None
    def partial():
        remaining = [cell for cell in ordered if cell not in completed]
        if current is not None and current.get("cell") in remaining:
            return list(completed), remaining, current["cell"]
        return list(completed), remaining, remaining[0] if remaining else None
    try:
        process.start()
        sender.close()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if current is not None and progress:
                    progress({**current, "kind": "cell", "status": "ABORTED"})
                raise TrainingTimeout(*partial())
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
                raise TrainingTimeout(*partial())
            kind = message["kind"]
            if kind in ("started", "tick"):
                current = message
                if kind == "tick" and progress:
                    progress(message)
            elif kind == "cell":
                if progress:
                    progress(message)
                if message.get("cell") not in completed:
                    completed.append(message["cell"])
                current = None
            elif kind == "degenerate":
                raise DegenerateTraining(message["histogram"], message["excluded"], message["training_window"])
            elif kind == "error":
                if message["reason"] == "TRAINING_TIME_LIMIT":
                    raise TrainingTimeout(*partial())
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
    # D47: fixed key order after seed — fit_protocol then training_window etc.
    text += "fit_protocol:\n"
    for key in ("iterations", "learning_rate", "l2", "class_weights"):
        text += "  " + key + ": " + json.dumps(artifact["fit_protocol"][key]) + "\n"
    text += "training_window:\n"
    for key in ("start", "end", "timeframes", "symbols", "default_timeframes", "default_symbols",
                "max_bars_per_cell"):
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


async def append_context_fact(store: Any, kind: str, symbol: str, timeframe: str,
                              as_of: str, data: Mapping) -> str:
    """Append an identity-bound producer input/result via public snapshot API.

    No UPDATE/DELETE, schema change or replacement of raw availability. The
    input owner supplies measurement time, not the candle's convenient time.
    """
    as_of = _ms_to_iso(_iso_to_ms(as_of))
    body = {"kind": kind, "symbol": symbol, "timeframe": timeframe,
            "as_of": as_of, "data": dict(data)}
    identity = hashlib.sha256(canonical_json(body).encode()).hexdigest()
    found = await (await store.db.execute("SELECT snapshot_id FROM snapshot_pit WHERE snapshot_id=?", (identity,))).fetchone()
    if not found:
        await store.insert_snapshot({"snapshot_id": identity, "as_of": as_of,
            "symbol_scope": [symbol], "timeframe_scope": [timeframe],
            "source_state": "CP14_"+kind, "parameter_package_id": "CP14_PRODUCER_V1",
            "code_version": "CP14_PRODUCER_V1", "quality_state": body})
    return identity


async def read_context_fact(store: Any, kind: str, symbol: str, timeframe: str,
                            as_of: str, *, exact: bool = False) -> dict | None:
    import json
    rows = await (await store.db.execute(
        "SELECT snapshot_id,vector_quality_state,as_of FROM snapshot_pit "
        "WHERE source_state=? AND symbol_scope=? AND timeframe_scope=? AND as_of"+
        ("=?" if exact else "<=?")+" ORDER BY as_of DESC,rowid DESC LIMIT 1",
        ("CP14_"+kind, symbol, timeframe, as_of))).fetchall()
    if not rows:
        return None
    try:
        identity, raw, stamp = rows[0]
        body = json.loads(raw)
        if (hashlib.sha256(canonical_json(body).encode()).hexdigest() != identity
                or (body["kind"], body["symbol"], body["timeframe"], body["as_of"]) != (kind,symbol,timeframe,stamp)):
            raise ValueError("fact identity mismatch")
        return {**body["data"], "fact_snapshot_id": identity, "fact_as_of": stamp}
    except (ValueError, KeyError, TypeError) as exc:
        raise BridgeError("CONTEXT_FACT_INVALID", kind) from exc


async def publish_quality_observation(store: Any, observation: Any, *, flags: Any,
                                      measurements: Mapping, receipt_time_ms: int, measured_at: str,
                                      measurement_source: str) -> str:
    """Quality-plane public seam: explicit observations/flags, native scoring.

    This is not called to backfill unknown historical metadata. A source must
    supply its actual completeness/source-health/sequence measurements and
    their provenance; the raw-only runtime never invokes it with defaults.
    """
    from dataclasses import asdict, replace
    from apex.quality.vector import calc_quality_vector, QualityFlags
    if not isinstance(flags, QualityFlags) or not measurement_source:
        raise BridgeError("QUALITY_PROVENANCE_UNAVAILABLE", "explicit flags and source required")
    if (type(receipt_time_ms) is not int or receipt_time_ms > _iso_to_ms(measured_at)
            or receipt_time_ms < close_time_ms(_iso_to_ms(observation.timestamp), observation.timeframe)):
        raise BridgeError("QUALITY_PROVENANCE_UNAVAILABLE", "future receipt")
    rows = await (await store.db.execute(
        "SELECT observation_id FROM market_observation WHERE symbol=? AND timeframe=? AND open_time=? "
        "AND candle_status IN ('CLOSED','CORRECTED')",
        (observation.symbol, observation.timeframe, observation.timestamp))).fetchall()
    if len(rows) != 1:
        raise BridgeError("QUALITY_PROVENANCE_UNAVAILABLE", "unique raw identity required")
    delay = freshness([observation], observation.timeframe, receipt_time=receipt_time_ms/1000)["staleness_seconds"]
    if set(measurements) != {"source_health", "gap_count", "expected_count", "completeness_pct"}:
        raise BridgeError("QUALITY_PROVENANCE_UNAVAILABLE", "explicit measured metadata required")
    lag = (max(0., (receipt_time_ms-_iso_to_ms(observation.oi_timestamp))/1000)
           if observation.oi_timestamp is not None else None)
    obs = replace(observation, **measurements, delay_seconds=delay, oi_lag_seconds=lag)
    q, state, tier = calc_quality_vector(obs, flags)
    payload = {"observation_id": rows[0][0], "content_hash": obs.content_hash(),
               "measurement_source": measurement_source, "receipt_time_ms": receipt_time_ms,
               "flags": asdict(flags), "measurements": {k: getattr(obs,k) for k in
                   ("source_health","gap_count","expected_count","completeness_pct","delay_seconds")},
               "quality_state": state, "quality_class": tier}
    if q is not None:
        payload["q_raw"] = q
    else:
        payload["refusal"] = state
    return await append_context_fact(store, "QUALITY_"+rows[0][0], obs.symbol, obs.timeframe, measured_at, payload)


def governed_holding_end(start_ms: int, timeframe: str) -> int:
    """D25 SL-12's known H_max entries; strictest known bound elsewhere."""
    import re
    from apex.research.governance import GOVERNED_DEFAULTS
    text = next(p.l1_default for p in GOVERNED_DEFAULTS if p.name == "H_max(tf)")
    documented = {tf:int(n) for n,tf in re.findall(r"(\d+) \((\w+)\)", text)}
    if not documented or timeframe not in E04.TF_SECONDS:
        raise BridgeError("HOLDING_HORIZON_UNAVAILABLE", timeframe)
    cap = documented.get(timeframe, min(documented.values()))
    end = start_ms
    for _ in range(cap):
        end = close_time_ms(end, timeframe)
    return end


async def persist_public_funding_schedule(store: Any, symbol: str, *, client: Any = None,
                                         now: Callable[[],float] = time.time) -> dict:
    refusal = None
    try:
        value = await collect_public_funding_schedule(symbol,client=client,now=now)
        stamp = _ms_to_iso(value["observed_at_ms"])
    except BridgeError as exc:
        refusal = exc
        stamp = _ms_to_iso(int(now()*1000))
        value = {"refusal":exc.reason,"detail":exc.detail}
    await append_context_fact(store,"PUBLIC_FUNDING_SCHEDULE",symbol,"",stamp,value)
    if refusal is not None: raise refusal
    return value


async def read_public_funding_schedule(store: Any, symbol: str, as_of: str) -> dict:
    value = await read_context_fact(store,"PUBLIC_FUNDING_SCHEDULE",symbol,"",as_of)
    if value is None or "refusal" in value:
        raise BridgeError("FUNDING_UNAVAILABLE",symbol)
    try:
        value["rate"] = Decimal(str(value["rate"]))
        if (not value["rate"].is_finite() or type(value["interval_ms"]) is not int or value["interval_ms"] <= 0
                or type(value["next_settlement_ms"]) is not int or value["next_settlement_ms"] <= 0
                or value["observed_at_ms"] != _iso_to_ms(value["fact_as_of"]) or not value["source"]):
            raise ValueError("invalid stored public funding schedule")
    except (KeyError,ValueError,TypeError,ArithmeticError) as exc:
        raise BridgeError("FUNDING_UNAVAILABLE",symbol) from exc
    return value


def validate_produced_context(context: Mapping) -> None:
    """Producer shape/range check in addition to unchanged native validators."""
    from apex.ops.plan_bridge import REQUIRED_CONTEXT_KEYS, REQUIRED_RISK_KEYS, _validate_e11_context
    from apex.risk.kernel import RISK_LADDER_STATES, EMERGENCY_LADDER
    from apex.fabric.context import COMPONENT_ENGINE
    allowed = set(REQUIRED_CONTEXT_KEYS) | set(PRODUCER_CONTEXT_ALLOWLIST)
    if set(context) != allowed or not isinstance(context.get("risk"),Mapping) or set(context["risk"]) != set(REQUIRED_RISK_KEYS):
        raise BridgeError("PRODUCER_SCHEMA_INVALID","exact 38 context + provenance + 23 risk fields required")
    if any(context[k] is None for k in allowed):
        raise BridgeError("PRODUCER_SCHEMA_INVALID","missing context value")
    _validate_e11_context(context["e11_context"])
    for key in ("data_trust","q_raw","regime_confidence","regime_uncertainty","divergence_magnitude",
                "temporal_window_validity","forecast_quality","p_min_tf","c_min","h_norm"):
        measured_number(context[key],"PRODUCER_RANGE_INVALID",lower=0,upper=1)
    for key in ("atr","forecast_rr","forecast_cost_r"):
        if measured_number(context[key],"PRODUCER_RANGE_INVALID",lower=0) <= 0:
            raise BridgeError("PRODUCER_RANGE_INVALID",key)
    for key in ("market_regime","mtf_state","utc_window_state","volatility_state","structure_state",
                "pattern_id","risk_state","family_status","temporal_quality","volatility_quality"):
        if not isinstance(context[key],str) or not context[key]:
            raise BridgeError("PRODUCER_TYPE_INVALID",key)
    # D46 (ADR-CP14-024): the allowlisted provenance key is a closed enum.
    if context["p_min_source"] not in P_MIN_SOURCES:
        raise BridgeError("PRODUCER_RANGE_INVALID","p_min_source")
    for key in ("is_overlap","freshness_ok"):
        if type(context[key]) is not bool: raise BridgeError("PRODUCER_TYPE_INVALID",key)
    if type(context["direction"]) is not int or context["direction"] not in (-1,1):
        raise BridgeError("PRODUCER_RANGE_INVALID","direction")
    for key in ("bos","regime_state","x","package","arbitration"):
        if not isinstance(context[key],Mapping) or not context[key]: raise BridgeError("PRODUCER_TYPE_INVALID",key)
    for key in ("s_i","q_i"):
        if not isinstance(context[key],Mapping) or set(context[key])-set(COMPONENT_ENGINE):
            raise BridgeError("PRODUCER_TYPE_INVALID",key)
        for value in context[key].values():
            measured_number(value,"PRODUCER_RANGE_INVALID",lower=0,upper=1)
            if key == "s_i" and value not in (0.,1.): raise BridgeError("PRODUCER_RANGE_INVALID",key)
    for value in context["x"].values(): measured_number(value,"PRODUCER_RANGE_INVALID")
    if not isinstance(context["events"],list) or not context["events"] or not isinstance(context["fvg_zones"],list):
        raise BridgeError("PRODUCER_TYPE_INVALID","events/fvg_zones")
    for event in context["events"]: event.validate_24_fields()
    if not isinstance(context["window_qualities"],(list,tuple)) or not context["window_qualities"]:
        raise BridgeError("PRODUCER_TYPE_INVALID","window_qualities")
    window_quality_projection(context["window_qualities"])
    risk = context["risk"]
    for key in ("circuit_breaker_engaged","is_risk_increase","uncertainty_is_rising"):
        if type(risk[key]) is not bool: raise BridgeError("PRODUCER_TYPE_INVALID",key)
    if risk["risk_state"] != context["risk_state"] or risk["risk_state"] not in RISK_LADDER_STATES or risk["emergency_state"] not in EMERGENCY_LADDER:
        raise BridgeError("PRODUCER_RANGE_INVALID","risk revision")
    for key in REQUIRED_RISK_KEYS:
        if key in ("risk_state","emergency_state","circuit_breaker_engaged","is_risk_increase","uncertainty_is_rising","time_to_expiry_days"): continue
        measured_number(risk[key],"PRODUCER_RANGE_INVALID",lower=0)
    for key in ("capital","min_quantity","contract_multiplier"):
        if risk[key] <= 0: raise BridgeError("PRODUCER_RANGE_INVALID",key)
    for key in ("margin_health_fraction","realized_daily_loss_fraction","realized_weekly_loss_fraction"):
        measured_number(risk[key],"PRODUCER_RANGE_INVALID",lower=0,upper=1 if key == "margin_health_fraction" else None)
    if type(risk["consecutive_losses"]) is not int: raise BridgeError("PRODUCER_TYPE_INVALID","consecutive_losses")
    expiry = risk["time_to_expiry_days"]
    if isinstance(expiry,Mapping):
        if (set(expiry) != {"applicable","contract_type"} or expiry.get("applicable") is not False
                or expiry.get("contract_type") != "PERPETUAL"):
            raise BridgeError("PRODUCER_RANGE_INVALID","expiry applicability")
    else: measured_number(expiry,"PRODUCER_RANGE_INVALID")


def decision_evidence_age(event_time: str, timeframe: str, as_of_ms: int) -> float:
    """SL-14 age of the emitted fact, not an engine's history sample count.

    Preserve all 24 native fields in storage; the decision view measures
    elapsed closed bars from the fact's actual timestamp. No future clipping.
    """
    from apex.ops.bootstrap_service import latest_close_boundary
    start = _iso_to_ms(event_time)
    if start > as_of_ms:
        raise BridgeError("BRIDGE_PIT_VIOLATION", "future evidence event time")
    end = latest_close_boundary(as_of_ms,timeframe)
    if timeframe != "1mo":
        return float((end-start)//(close_time_ms(start,timeframe)-start))
    a,b = parse_utc_ms(event_time),parse_utc_ms(_ms_to_iso(end))
    return float((b.year-a.year)*12+b.month-a.month)
