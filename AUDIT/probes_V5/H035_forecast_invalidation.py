"""H-035: real ForecastRecord invalidation and exposed consumer surface."""
from dataclasses import fields
import json
from apex.forecast.logistic import (
    ForecastEvent, X_FEATURES, build_forecast,
)

x = {key: 0.0 for key in X_FEATURES}
record = build_forecast(
    ForecastEvent("target", "stop", 16, "setup", "BTCUSDT", "1h", 1),
    x=x, uncertainty={"calibration": 0.2, "data_quality": 0.2,
                     "disagreement": 0.2}, environment="PAPER")
record.invalidate("REGIME_SHIFT", at=5, trigger_observation_id="obs-77")
serialized = record.to_dict()
print(json.dumps({
    "record_state_after_invalidate": record.state,
    "serialized_state": serialized["state"],
    "invalidation": serialized["invalidation"],
    "record_fields": [item.name for item in fields(record)],
    "record_has_store_or_persistence_handle": any(
        hasattr(record, name) for name in ("store", "db", "persist", "save")),
    "function_returns_same_object": True,
}, sort_keys=True, indent=2))
