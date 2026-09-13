"""APEX_GEN5 Statistical Forecast package (Ch.13 §13.1; CP-6).

P/U/C only: the forecast grants no permission and issues no order. The
bootstrap prior (p = 0.5) runs in RESEARCH/PAPER and is refused for LIVE
capital until a calibrated walk-forward package exists.
"""

from apex.forecast.logistic import (  # noqa: F401
    BOOTSTRAP_P,
    BOOTSTRAP_Q_FORECAST,
    CALIBRATION_THRESHOLDS,
    COMPOSITE_WEIGHTS,
    DECAY_LAMBDA_PER_BAR,
    HORIZON_MULTIPLE,
    INVALIDATION_REASONS,
    MIN_OBS_DEFAULT,
    UNCERTAINTY_COMPONENTS,
    X_FEATURES,
    X_FEATURE_COUNT,
    ForecastError,
    ForecastEvent,
    ForecastRecord,
    build_forecast,
    composite_estimate,
    cost_r_floor,
    decay,
    economic_utility,
    h_max_tf,
    horizon_bars,
    logistic_bootstrap_p,
    platt_or_isotonic_oos,
    require_calibrated_package,
    r_penalty_for,
    uncertainty_from,
)
from apex.forecast.registry import AG_MODEL_REGISTRY, ag_models_bound_to_q_i  # noqa: F401
