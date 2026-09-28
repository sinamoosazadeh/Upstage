from __future__ import annotations

import ast
import sqlite3
from decimal import Decimal
from pathlib import Path

from apex.data_catalog.contracts import (
    MarketObservation,
    ValidationError,
    validate_market_observation,
)
from apex.data_catalog.store.sqlite_store import CH4_DDL
from apex.engines.e05_fvg.engine import detect_fvg_at
from apex.ops.bootstrap_service import _ohlc_violation

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    "tests/unit/test_e04_volatility.py",
    "tests/unit/test_e05_fvg.py",
    "tests/unit/test_e06_orderblock.py",
    "tests/integration/test_cp3_engines.py",
]


def scan_literals() -> list[tuple[str, int, str, float, float, float, float, str]]:
    found = []
    for relative in FILES:
        tree = ast.parse((ROOT / relative).read_text())
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            keys, values = [], []
            for key, value in zip(node.keys, node.values):
                keys.append(key.value if isinstance(key, ast.Constant) else None)
                try:
                    values.append(ast.literal_eval(value))
                except (ValueError, TypeError):
                    values.append(None)
            data = dict(zip(keys, values))
            aliases = (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close"))
            if not all(any(k in data for k in group) for group in aliases):
                continue
            o, h, low, close = (data.get(short, data.get(long)) for short, long in aliases)
            if not all(isinstance(x, (int, float)) for x in (o, h, low, close)):
                continue
            problems = []
            if h < max(o, close):
                problems.append("high<max(open,close)")
            if low > min(o, close):
                problems.append("low>min(open,close)")
            if h < low:
                problems.append("high<low")
            if not problems:
                continue
            owner = node
            while owner in parents and not isinstance(
                owner, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                owner = parents[owner]
            context = getattr(owner, "name", "<module>")
            # Include the enclosing class when the nearest owner is a method.
            parent = parents.get(owner)
            if isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)) and isinstance(parent, ast.ClassDef):
                context = f"{parent.name}.{context}"
            found.append((relative, node.lineno, context, o, h, low, close, ",".join(problems)))
    return found


print("CP-3 literal OHLC geometry scan; tests are not executed by this static pass")
violations = scan_literals()
for path, line, context, o, h, low, close, problem in violations:
    print(f"{path}:{line} {context}: O={o} H={h} L={low} C={close}: {problem}")
print(f"invalid numeric OHLC dict literals={len(violations)} across {len(FILES)} test files")

# Gate-D fixture represented in test_e05_fvg.py::TestFormulas::test_gate_d_min_width_0_2_rule.
# Its second sample changes L only from 101.19 to 101.21; both remain above O=100.5.
bars = [
    {"o": 100, "h": 101, "l": 99, "c": 100, "v": 1000, "ts_close": 1000},
    {"o": 100, "h": 101, "l": 99.9, "c": 100.5, "v": 1000, "ts_close": 2000},
    {"o": 100.5, "h": 102, "l": 101.21, "c": 101.8, "v": 1000, "ts_close": 3000},
]
detection = detect_fvg_at(bars, 2, 0.2, 3, 0.01, atr_override=1.0)
print("direct E05 detect_fvg_at on asserted-positive Gate-D bar:",
      "invalid_reason=" + str(detection.get("invalid_reason")),
      "width=" + str(detection.get("width")))
assert detection and "invalid_reason" not in detection

# Demonstrate the same geometries are excluded by the production source gate,
# canonical MarketObservation validator, and repository DDL (all in-memory).
representatives = {
    "E05_GateD_low_above_open": (100.5, 102, 101.21, 101.8),
    "E05_case_study_low_above_open": (523.3, 527.5, 523.5, 526.8),
    "E05_case_study_high_below_open": (531.0, 528.5, 525.0, 526.0),
    "E06_scenario_high_below_open": (107.0, 100.5, 98.9, 100.2),
    "E06_scenario_low_above_open": (97.5, 100.2, 99.0, 99.9),
}
for label, (o, h, low, close) in representatives.items():
    raw = {"open": str(o), "high": str(h), "low": str(low), "close": str(close)}
    print(f"production _ohlc_violation {label}:", _ohlc_violation(raw))
    obs = MarketObservation(
        symbol="BTCUSDT", timeframe="1h", open=Decimal(str(o)),
        high=Decimal(str(h)), low=Decimal(str(low)), close=Decimal(str(close)),
        volume=Decimal("1000"), oi=None, timestamp="2026-01-01T00:00:00.000Z",
        sequence=1, status="CLOSED",
    )
    try:
        validate_market_observation(obs)
    except ValidationError as exc:
        print(f"validate_market_observation {label}: {exc}")
    else:
        raise AssertionError(f"canonical validator accepted {label}")

# Repository DDL check: no data/ access; disposable in-memory DB only.
db = sqlite3.connect(":memory:")
db.executescript(CH4_DDL)
invalid = representatives["E05_GateD_low_above_open"]
try:
    db.execute(
        "INSERT INTO market_observation "
        "(observation_id,symbol,timeframe,open_price,high_price,low_price,close_price,volume,"
        "open_interest,open_time,close_time,retrieved_at,candle_status,quality_state,source,"
        "schema_version,raw_payload_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("bad", "BTCUSDT", "1h", *(str(v) for v in invalid), "1000", "MISSING",
         "2026-01-01T00:00:00.000Z", "2026-01-01T01:00:00.000Z",
         "2026-01-01T01:00:00.000Z", "CLOSED", "Q0", "TEST", "v1", "hash"),
    )
except sqlite3.IntegrityError as exc:
    print("repository CH4_DDL malformed-row insert:", type(exc).__name__, str(exc))
else:
    raise AssertionError("CH4_DDL accepted malformed Gate-D fixture")
print("probe=PASS; in-memory SQLite only; no venue/network or data/ access")
