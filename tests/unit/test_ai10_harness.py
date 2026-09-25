"""CP-8 — AI.10 conformance harness runner (``scripts/run_adapter_conformance.py``):
the hash seal is checked before any case runs, all 19 golden cases execute
against the real CP-7 adapter over the fake responder, and T-AD-001/T-AD-002
are reported inside the same verdict (MATRIX Part III CP-8 rows C8-AI10|1..5)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "run_adapter_conformance.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("cp8_conformance_runner", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner():
    module = _load_runner()
    import os
    saved = {name: os.environ.get(name) for name in module.HARNESS_ENV}
    for name, value in module.HARNESS_ENV.items():
        os.environ.setdefault(name, value)
    yield module
    for name, previous in saved.items():
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


@pytest.fixture(scope="module")
def report(runner):
    return runner.run_harness()


class TestHarnessSeal:
    def test_fixture_hash_seal_verifies(self, runner):
        payload = json.loads(runner.FIXTURE.read_text(encoding="utf-8"))
        seal = runner.verify_fixture(payload)
        assert seal["ok"] is True
        assert seal["count_ok"] is True
        assert seal["case_count"] == 19

    def test_seal_hash_is_the_recorded_one(self, runner):
        payload = json.loads(runner.FIXTURE.read_text(encoding="utf-8"))
        assert runner.verify_fixture(payload)["cases_sha256"] == \
            payload["_meta"]["cases_sha256"]

    def test_tampered_fixture_aborts_before_any_case(self, runner, tmp_path,
                                                      monkeypatch):
        payload = json.loads(runner.FIXTURE.read_text(encoding="utf-8"))
        payload["cases"][0]["call"]["quantity"] = "999"
        tampered = tmp_path / "tampered.json"
        tampered.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(runner, "FIXTURE", tampered)
        verdict = runner.run_harness()
        assert verdict["status"] == "FIXTURE_INTEGRITY_FAILURE"
        assert verdict["passed"] is False
        assert verdict["cases"] == []          # nothing ran
        assert verdict["fixture_seal"]["reason"] == "FIXTURE_HASH_MISMATCH"

    def test_missing_cases_array_is_refused(self, runner):
        seal = runner.verify_fixture({"_meta": {}})
        assert seal["ok"] is False
        assert seal["reason"] == "FIXTURE_CASES_ABSENT"


class TestHarnessRun:
    def test_every_golden_case_passes(self, report):
        assert report["status"] == "PASS"
        assert report["passed"] is True
        assert report["cases_total"] == 19
        assert report["cases_passed"] == 19
        assert [c["id"] for c in report["cases"]] == \
            [f"C-{i:02d}" for i in range(1, 20)]
        assert all(case["failures"] == [] for case in report["cases"])

    def test_t_ad_001_and_t_ad_002_are_part_of_the_verdict(self, report):
        assert report["t_ad_001"]["test"] == "T-AD-001"
        assert report["t_ad_001"]["passed"] is True
        assert report["t_ad_002"]["test"] == "T-AD-002"
        assert report["t_ad_002"]["passed"] is True
        assert report["t_ad_002"]["unique_keys"] == 1
        assert report["t_ad_002"]["new_submissions"] == 1

    def test_the_real_data_gate_is_reported_open(self, report):
        gate = report["t_ad_001"]["real_data_gate"]
        assert gate["gate"] == "G-ADAPTER-001"
        assert gate["status"] == "OPEN/UNVERIFIED"

    def test_main_exits_zero_on_a_green_run(self, runner, monkeypatch, capsys):
        monkeypatch.setattr(runner, "run_harness",
                            lambda **kwargs: {"fixture_seal": {"ok": True},
                                              "fixture": "x", "cases": [],
                                              "t_ad_001": {"passed": True},
                                              "t_ad_002": {"passed": True},
                                              "status": "PASS", "passed": True,
                                              "cases_passed": 0,
                                              "cases_total": 0})
        assert runner.main([]) == 0
        assert "status: PASS" in capsys.readouterr().out

    def test_main_exits_two_on_a_tampered_fixture(self, runner, monkeypatch):
        monkeypatch.setattr(runner, "run_harness",
                            lambda **kwargs: {"fixture_seal": {"ok": False},
                                              "fixture": "x", "cases": [],
                                              "status":
                                                  "FIXTURE_INTEGRITY_FAILURE",
                                              "passed": False})
        assert runner.main([]) == 2
