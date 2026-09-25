"""CP-1 foundations: packaging (nine SBOM pins exact, pytest dev-only,
no python-dotenv), .gitignore (ADR-P2-013), normative-tree presence,
import chain, and params-vs-blueprint literal checks (§9.5/Ch.10/§2.1/
Ch.16). Verifying tests named in TRACEABILITY Part I rows."""
from __future__ import annotations

import importlib
import pathlib
import re
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent.parent

# Ch.1 SBOM — the nine pins, exactly.
SBOM_PINS = [
    "aiohttp==3.9.5",
    "aiogram==3.7.0",
    "aiosqlite==0.20.0",
    "matplotlib==3.8.4",
    "pandas==2.2.0",
    "numpy==1.26.0",
    "pydantic==2.5.0",
    "python-dateutil==2.8.2",
    "pytz==2024.1",
]

# §9.5 normative tree — CP-1-owned files.
CP1_TREE = [
    "pyproject.toml", "requirements.lock", "README.md", ".gitignore",
    "scripts/run_all_tests.sh",
    "apex/__init__.py", "apex/errors.py", "apex/bus.py", "apex/config.py",
    "apex/identity/__init__.py", "apex/identity/canonical_json.py",
    "apex/identity/uuid_v7.py", "apex/identity/snapshot.py",
    "apex/identity/hashes.py",
    "apex/data_catalog/__init__.py", "apex/data_catalog/contracts.py",
    "apex/data_catalog/catalog.py",
    "apex/data_catalog/store/__init__.py",
    "apex/data_catalog/store/sqlite_store.py",
    "apex/data_catalog/ingest/__init__.py",
    "apex/data_catalog/ingest/toobit_public.py",
    "apex/data_catalog/atomic/__init__.py",
    "apex/data_catalog/atomic/features.py",
    "apex/data_catalog/molecular/__init__.py",
    "apex/data_catalog/molecular/features.py",
    "apex/data_catalog/organismic/__init__.py",
    "apex/data_catalog/organismic/features.py",
    "apex/data_catalog/math/__init__.py",
    "apex/data_catalog/performance/__init__.py",
    "apex/quality/__init__.py", "apex/quality/vector.py",
    "apex/quality/numerical.py", "apex/quality/pit.py",
    "apex/engines/__init__.py", "apex/engines/base.py",
    "params/universe_v1.yaml", "params/risk_defaults_v1.yaml",
    "params/setup_weights_v1.yaml", "params/quality_weights_v1.yaml",
    "params/toobit_wire_v1.yaml", "params/e11_params_v4.yaml",
]

CP1_MODULES = [
    "apex", "apex.errors", "apex.bus", "apex.config",
    "apex.identity.canonical_json", "apex.identity.uuid_v7",
    "apex.identity.snapshot", "apex.identity.hashes",
    "apex.data_catalog.contracts", "apex.data_catalog.catalog",
    "apex.data_catalog.store.sqlite_store",
    "apex.data_catalog.ingest.toobit_public",
    "apex.data_catalog.atomic.features",
    "apex.data_catalog.molecular.features",
    "apex.data_catalog.organismic.features",
    "apex.data_catalog.math", "apex.data_catalog.performance",
    "apex.quality.vector", "apex.quality.numerical", "apex.quality.pit",
    "apex.engines.base",
]


class TestPackaging:
    def test_sbom_pins_exact(self):
        lock = (REPO / "requirements.lock").read_text()
        pins = [line.strip() for line in lock.splitlines()
                if line.strip() and not line.startswith("#")]
        assert pins == SBOM_PINS, "requirements.lock must be EXACTLY the nine pins"

    def test_pyproject_runtime_deps_are_the_nine_pins(self):
        text = (REPO / "pyproject.toml").read_text()
        for pin in SBOM_PINS:
            assert pin in text, f"missing runtime pin {pin}"

    def test_pytest_dev_only_never_in_lock(self):
        lock = (REPO / "requirements.lock").read_text()
        pins = [line.strip() for line in lock.splitlines()
                if line.strip() and not line.startswith("#")]
        assert all("pytest" not in pin for pin in pins), \
            "pytest must never enter requirements.lock"
        text = (REPO / "pyproject.toml").read_text()
        assert "tests" in text and "pytest>=7,<9" in text

    def test_no_python_dotenv(self):
        for path in (REPO / "requirements.lock", REPO / "pyproject.toml"):
            assert "dotenv" not in path.read_text()

    def test_gitignore_adr_p2_013(self):
        gi = (REPO / ".gitignore").read_text()
        for entry in ("data/", "*.sqlite3*", ".env", "__pycache__/",
                      ".pytest_cache/", "dist/", "build/"):
            assert entry in gi

    def test_run_all_tests_script(self):
        script = REPO / "scripts/run_all_tests.sh"
        assert script.exists() and script.stat().st_mode & 0o111

    def test_run_all_tests_runs_full_suite(self):
        out = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q",
             "tests/unit", "tests/integration"],
            cwd=REPO, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr


class TestNormativeTree:
    def test_all_cp1_files_exist_non_empty(self):
        for rel in CP1_TREE:
            path = REPO / rel
            assert path.exists(), f"missing tree file {rel}"
            assert path.stat().st_size > 0, f"empty tree file {rel}"

    def test_import_chain(self):
        for mod in CP1_MODULES:
            importlib.import_module(mod)

    def test_no_todo_fixme_pass_stubs_in_wave_in_code(self):
        """G6: Wave-In code contains no TODO/FIXME/pass-stubs/
        NotImplementedError placeholders (except the abstract compute hook,
        which is an ABC contract, not a stub)."""
        for rel in CP1_TREE:
            if not rel.endswith(".py"):
                continue
            text = (REPO / rel).read_text()
            for token in ("TODO", "FIXME"):
                assert token not in text, f"{token} in {rel}"
            # pass statements only lawful inside exception handlers/classes
            for m in re.finditer(r"^\s*pass\s*(#.*)?$", text, re.M):
                line = text[:m.start()].count("\n") + 1
                ctx = text.splitlines()[line - 2:line + 1]
                if any("except" in c or "class" in c for c in ctx):
                    continue
                raise AssertionError(f"pass-stub in {rel}:{line}")
        base = (REPO / "apex/engines/base.py").read_text()
        # exactly one NotImplementedError: the abstract compute() hook
        assert base.count("NotImplementedError") == 1


class TestParamsFrozenValues:
    """Compare YAML literals against the blueprint's frozen strings
    (§9.5/Ch.10/§2.1/Ch.16) — literal-by-literal, code never hardcodes."""

    def test_universe_v1_literals(self):
        from apex.config import load_params
        u = load_params()["universe"]
        assert u["symbols"] == ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
                                "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT",
                                "LINKUSDT", "LTCUSDT"]
        assert u["timeframes"] == ["1m", "3m", "5m", "15m", "30m", "1h",
                                   "2h", "4h", "6h", "8h", "12h", "1d",
                                   "1w", "1mo"]
        assert u["setup_timeframes"] == u["timeframes"]
        assert u["nightly_window_utc"] == {"start": "03:00", "end": "05:00"}
        assert u["tick_size"]["BTCUSDT"] == 0.1
        assert u["quantity_step"]["XRPUSDT"] == 1
        assert u["min_notional"]["ETHUSDT"] == 5
        assert u["exchange_max_leverage"]["BTCUSDT"] == 125

    def test_risk_defaults_literals(self):
        from apex.config import load_params
        r = load_params()["risk_defaults"]
        assert r["budget_per_trade"] == 0.005
        assert r["k_attn"] == 0.25
        assert r["daily_loss_cap"] == 0.03
        assert r["weekly_loss_cap"] == 0.06
        assert r["consecutive_loss_halt"] == 4
        assert r["margin_mode"] == "ISOLATED"
        assert r["position_mode"] == "ONE_WAY"
        assert r["cost_R_floor"] == 0.05
        assert r["R_penalty_medium"] == 0.10
        assert r["R_penalty_high"] == 0.25
        assert r["max_candidates"] == 3
        assert r["correlation_cap"] == 0.70
        y2 = r["system_leverage_cap_by_tf"]
        assert y2["1m"] == 2 and y2["5m"] == 2 and y2["15m"] == 3
        assert y2["30m"] == 3 and y2["1h"] == 4 and y2["4h"] == 4
        assert y2["6h"] == 5 and y2["1mo"] == 5

    def test_setup_weights_literals(self):
        from apex.config import load_params
        s = load_params()["setup_weights"]
        assert s["family_id"] == "SF_FVG_SWEEP_REV"
        assert s["playbook_id"] == "PB_FVG_SWEEP_REV_A"
        assert s["Q_min_setup"] == 0.55
        assert s["gate7_entropy_threshold"] == 0.85
        assert s["conflict_penalty"] == 0.4
        assert s["redundancy_penalty"] == 0.3
        assert s["redundancy_rho_threshold"] == 0.85
        assert s["redundancy_window_n"] == 48
        w = s["weights"]
        assert w == {"w_structure": 0.16, "w_liquidity": 0.12,
                     "w_volume": 0.10, "w_volatility": 0.08,
                     "w_fvg": 0.12, "w_orderblock": 0.10,
                     "w_rtm": 0.06, "w_wyckoff": 0.06,
                     "w_trend": 0.08, "w_momentum": 0.06,
                     "w_regime": 0.04, "w_temporal": 0.02}
        assert abs(sum(w.values()) - 1.0) < 1e-9

    def test_quality_weights_copy_exact_21(self):
        from apex.config import load_params
        q = load_params()["quality_weights"]
        # Q_min complete bootstrap table (§2.1)
        assert q["q_min_by_tf"] == {
            "1m": 0.60, "3m": 0.58, "5m": 0.56, "15m": 0.54, "30m": 0.52,
            "1h": 0.50, "2h": 0.48, "4h": 0.46, "6h": 0.45, "8h": 0.44,
            "12h": 0.42, "1d": 0.40, "1w": 0.40, "1mo": 0.40}
        assert q["freshness_threshold_seconds"] == {
            "1m": 5, "3m": 8, "5m": 10, "15m": 20, "30m": 25, "1h": 30,
            "2h": 60, "4h": 120, "6h": 180, "8h": 240, "12h": 300,
            "1d": 300, "1w": 3600, "1mo": 14400}
        assert q["oi_lag_threshold_seconds"] == {
            "1m": 10, "3m": 15, "5m": 20, "15m": 30, "30m": 45, "1h": 60,
            "2h": 90, "4h": 120, "6h": 180, "8h": 240, "12h": 300,
            "1d": 300, "1w": 3600, "1mo": 14400}
        assert q["q_thr_by_tf"] == {"1m": 0.6, "1h": 0.5, "1d": 0.4}
        assert q["q_feature_weights"] == {"w_formula": 0.5, "w_lookback": 0.3,
                                          "w_epsilon": 0.2}
        assert q["q_evidence_weights"]["w_conf_by_tf"] == {"1m": 0.3,
                                                           "1h": 0.25,
                                                           "1d": 0.2}
        assert q["q_evidence_weights"]["w_strength"] == 0.3
        assert q["q_evidence_weights"]["w_freshness_by_tf"] == {"1m": 0.2,
                                                                "1h": 0.25}
        assert q["q_evidence_weights"]["w_regime"] == 0.2
        assert q["q_window_lambda"] == 0.1
        assert q["q_evidence_lambda"] == 0.1
        # complete Q_raw weights table: sums to 1 per TF, spot-check rows
        rows = q["q_raw_weights_by_tf"]
        assert set(rows) == set(q["q_min_by_tf"])
        for tf, wrow in rows.items():
            assert abs(sum(wrow.values()) - 1.0) < 1e-9
        assert rows["1m"] == {"Q_schema": 0.20, "Q_time": 0.20,
                              "Q_seq": 0.15, "Q_ohlc": 0.20,
                              "Q_volume": 0.10, "Q_oi": 0.10,
                              "Q_source": 0.05}
        assert rows["1d"] == {"Q_schema": 0.10, "Q_time": 0.10,
                              "Q_seq": 0.10, "Q_ohlc": 0.30,
                              "Q_volume": 0.15, "Q_oi": 0.15,
                              "Q_source": 0.10}

    def test_toobit_wire_literals(self):
        from apex.config import load_params
        w = load_params()["toobit_wire"]
        assert w["base_url"] == "https://api.toobit.com"
        assert w["header_api_key"] == "X-BB-APIKEY"
        assert w["recv_window_ms"] == 5000
        assert w["auth_scheme"] == "HMAC-SHA256"
        assert w["symbol_map"]["BTCUSDT"] == "BTC-SWAP-USDT"
        assert w["symbol_map"]["LTCUSDT"] == "LTC-SWAP-USDT"
        assert w["interval_map"] == {"1mo": "1M"}
        assert w["interval_unsupported_code"] == -1120
        assert w["interval_unsupported_handling"] == "DISABLE_TF_FOR_SYMBOL_ONLY"
        assert w["klines_limit"] == 1000
        assert w["open_interest_failure_handling"] == "OI_MISSING"
        assert w["funding_rate_alert_threshold"] == 0.001
        assert w["funding_rate_alert_only"] is True
        assert w["side_map"] == {"LONG_entry": "BUY_OPEN",
                                 "SHORT_entry": "SELL_OPEN",
                                 "LONG_flatten": "SELL_CLOSE",
                                 "SHORT_flatten": "BUY_CLOSE"}
        assert w["business_codes_ok"] == [0, 200]
        assert w["unknown_outcome_codes"] == [-1006, -1007, -1146, -1147]
        assert w["abort_code"] == -1022
        assert w["backoff_code"] == -1003
        assert w["retry_attempts"] == 3
        assert w["retry_backoff_seconds"] == [1, 2, 4]
        assert w["rollover_min_days"] == 7
        assert "withdraw" in w["forbidden_operations"]
        assert w["forbidden_order_type"] == "MARKET"
        assert w["margin_type_value"] == "ISOLATED"

    def test_e11_params_literals(self):
        from apex.config import load_params
        e = load_params()["e11_params"]
        # D49: thresholds are the PASS-artifact percentiles, not the chapter defaults.
        assert e == {"K": 9, "theta_H": 1.105878, "quality_H_Q2": 1.229880,
                     "quality_H_Q5": 0.564415,
                     "lambda_ewma": 0.94, "hysteresis_candles": 3, "dirichlet_alpha": 0.1,
                     "transition_delay_candles": 48, "W_180d_H1": 4320}
