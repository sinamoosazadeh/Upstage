"""CP-8 — Ch.17 SL-12 governance service + the W.5 RED LINE / T-PKG-001 suite
(MATRIX Part III CP-8 rows C8-GOV|1..12)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apex.research import governance as gov


def _package(**overrides):
    base = dict(package_id="pkg-test-1", version="1.0.0",
                values={"correlation_cap": 0.65}, code_revision="a" * 40,
                feature_version="4.0.0", model_version="4.0.0", seed=7,
                reason="unit test")
    base.update(overrides)
    return gov.ParameterPackage(**base)


def _complete_proposal():
    return {"reason": "sharper gate", "pit_backtest_180d": 180,
            "forward_observation_30d": 30, "out_of_sample_evaluation": "OOS-1",
            "parameter_board_approval": "board-2026-09"}


# --------------------------------------------------------------------------
# §17.1 — classes, tiers, register
# --------------------------------------------------------------------------

class TestRegistry:
    def test_four_classes(self):
        assert gov.PARAM_CLASSES == ("static/architecture", "static/owner",
                                     "dynamic/governed", "research-only")

    def test_governed_default_table_is_34_rows(self):
        summary = gov.governance_summary()
        assert summary["governed_defaults"] == 34
        assert summary["expected_governed_defaults"] == 34

    def test_every_row_has_a_home(self):
        for row in gov.GOVERNED_DEFAULTS:
            assert row.yaml_ref or row.owner_module, row.name
            assert row.cite

    def test_classes_assigned_per_blueprint(self):
        assert gov.parameter_class("budget_per_trade") == "dynamic/governed"
        assert gov.parameter_class("symbol_exposure_cap") == "static/owner"
        assert gov.parameter_class("heartbeat_interval") == "static/architecture"
        assert gov.parameter_class("backup_interval") == "static/architecture"

    def test_unknown_parameter_fails_closed(self):
        with pytest.raises(gov.GovernanceError) as err:
            gov.governed_default("not_a_parameter")
        assert "UNKNOWN_GOVERNED_PARAM" in str(err.value)

    def test_resolution_tiers(self):
        assert gov.resolution_tier() == "L1"
        assert gov.resolution_tier(profile="Aggressive") == "L2"
        assert gov.resolution_tier(profile="Balanced", symbol="BTCUSDT") == "L3"
        with pytest.raises(gov.GovernanceError):
            gov.resolution_tier(profile="YOLO")

    def test_yaml_backed_values_match_or_are_recorded(self):
        divergences = gov.assert_yaml_consistency()
        # the loader always wins at runtime (§9.5-10); divergences are recorded
        for row in divergences:
            assert row["note"] == "doc_inconsistency"
            assert row["yaml_ref"].startswith("params/")
        # The two known ones are budge/projection-layer tensions, not silent
        # rewrites — CP-8 files them instead of touching a frozen YAML.
        names = {d["name"] for d in divergences}
        assert names <= {"budget_per_trade", "k_attn"}


# --------------------------------------------------------------------------
# §17.1 — constrained update
# --------------------------------------------------------------------------

class TestConstrainedUpdate:
    def test_projection_operator(self):
        assert gov.project(0.9, 0.0, 0.7) == 0.7
        assert gov.project(-0.1, 0.0, 0.7) == 0.0
        assert gov.project(0.5, 0.0, 0.7) == 0.5

    def test_inverted_bounds_refused(self):
        with pytest.raises(gov.GovernanceError):
            gov.project(0.5, 0.8, 0.2)

    def test_constrained_update_clamps_and_reports(self):
        """θ′ = Π_[L,U](θ + Δ): 0.5 + 2.0 projects onto U = 1.0."""
        result = gov.constrained_update(name="crisis_factor", current=0.5,
                                        delta=2.0)
        assert result["proposed"] == pytest.approx(2.5)
        assert result["projected"] == pytest.approx(1.0)
        assert result["clamped"] is True
        assert result["bounds"] == [0.0, 1.0]

    def test_constrained_update_within_bounds_is_exact(self):
        result = gov.constrained_update(name="correlation_cap", current=0.50,
                                        delta=0.10)
        assert result["projected"] == pytest.approx(0.60)
        assert result["clamped"] is False

    def test_owner_bounds_are_tighter(self):
        result = gov.constrained_update(name="correlation_cap", current=0.50,
                                        delta=0.40, low=0.2, high=0.6)
        assert result["projected"] == pytest.approx(0.6)

    def test_current_out_of_bounds_fails_closed(self):
        with pytest.raises(gov.GovernanceError) as err:
            gov.constrained_update(name="correlation_cap", current=5.0, delta=0.1)
        assert "CURRENT_OUT_OF_BOUNDS" in str(err.value)

    def test_non_finite_delta_refused(self):
        with pytest.raises(gov.GovernanceError):
            gov.constrained_update(name="correlation_cap", current=0.5,
                                   delta=float("nan"))


# --------------------------------------------------------------------------
# §17.1 — change-proposal protocol
# --------------------------------------------------------------------------

class TestChangeProposal:
    def test_complete_proposal_is_approved(self):
        verdict = gov.validate_change_proposal(_complete_proposal())
        assert verdict["decision"] == "APPROVED"
        assert verdict["missing"] == []

    @pytest.mark.parametrize("missing", gov.PROPOSAL_REQUIRED_ITEMS)
    def test_every_item_is_mandatory(self, missing):
        proposal = _complete_proposal()
        proposal.pop(missing)
        verdict = gov.validate_change_proposal(proposal)
        assert verdict["decision"] == "REJECTED"
        assert missing in verdict["missing"]
        assert verdict["conservative_value_kept"] is True

    def test_short_backtest_window_is_rejected(self):
        proposal = _complete_proposal()
        proposal["pit_backtest_180d"] = 179
        assert "pit_backtest_180d<180d" in gov.validate_change_proposal(
            proposal)["missing"]

    def test_short_forward_observation_is_rejected(self):
        proposal = _complete_proposal()
        proposal["forward_observation_30d"] = 29
        assert "forward_observation_30d<30d" in gov.validate_change_proposal(
            proposal)["missing"]


# --------------------------------------------------------------------------
# §17.1 — EC register + sensitivity
# --------------------------------------------------------------------------

class TestECRegister:
    def _semantics(self, **extra):
        base = {field: "x" for field in gov.EC_FIELDS if field != "status"}
        base.update(extra)
        return base

    def test_open_entry_has_no_active_value(self):
        register = gov.ECRegister()
        register.register(gov.ECEntry("alpha_decay_half_life",
                                      self._semantics(), status="OPEN"))
        assert register.active_value("alpha_decay_half_life") is None
        assert register.get("alpha_decay_half_life").conservative() is True
        assert "alpha_decay_half_life" in register.conservative_paths()

    def test_approved_entry_exposes_its_value(self):
        register = gov.ECRegister()
        register.register(gov.ECEntry("spread_scale",
                                      self._semantics(value=0.02),
                                      status="APPROVED"))
        assert register.active_value("spread_scale") == pytest.approx(0.02)
        assert register.conservative_paths() == []

    def test_missing_fields_fail_closed(self):
        with pytest.raises(gov.GovernanceError) as err:
            gov.ECEntry("bad", {"unit": "x"}, status="OPEN")
        assert "EC_FIELDS_MISSING" in str(err.value)

    def test_invalid_status_refused(self):
        with pytest.raises(gov.GovernanceError):
            gov.ECEntry("bad", self._semantics(), status="MAYBE")

    def test_absent_entry_refused(self):
        with pytest.raises(gov.GovernanceError):
            gov.ECRegister().get("nope")


class TestSensitivity:
    def test_removal_candidate_below_threshold(self):
        out = gov.sensitivity_removal_candidate(s1=0.001, st=0.5)
        assert out["removal_candidate"] is True
        assert out["automatic_removal"] is False

    def test_not_a_candidate_above_threshold(self):
        out = gov.sensitivity_removal_candidate(s1=0.4, st=0.5)
        assert out["removal_candidate"] is False

    def test_zero_total_refused(self):
        with pytest.raises(gov.GovernanceError):
            gov.sensitivity_removal_candidate(s1=0.1, st=0.0)


# --------------------------------------------------------------------------
# W.5 — RED LINE
# --------------------------------------------------------------------------

class TestRedLine:
    def test_clean_package_validates(self):
        verdict = gov.validate_package(_package())
        assert verdict["decision"] == "VALIDATED"
        assert verdict["red_line_clean"] is True

    def test_all_fourteen_veto_names_are_forbidden(self):
        assert len(gov.VETO_FIELD_NAMES) == 14
        for name in gov.VETO_FIELD_NAMES:
            verdict = gov.validate_package(_package(values={name: 1}))
            assert verdict["decision"] == "REJECTED"
            assert verdict["violations"][0]["kind"] == "RED_LINE_FIELD"

    def test_owner_static_fields_are_rejected(self):
        for field in ("capital_hard_cap", "leverage_cap_by_tf",
                      "max_loss_per_day", "circuit_breaker"):
            verdict = gov.validate_package(_package(values={field: 1}))
            assert verdict["decision"] == "REJECTED", field

    def test_margin_thresholds_are_immutable(self):
        verdict = gov.validate_package(_package(values={"margin_action": 0.9}))
        assert verdict["decision"] == "REJECTED"

    def test_out_of_bounds_value_is_rejected(self):
        verdict = gov.validate_package(_package(values={"k_attn": 5.0}))
        assert any(v["kind"] == "OUT_OF_BOUNDS" for v in verdict["violations"])

    def test_incomplete_proposal_blocks_the_package(self):
        verdict = gov.validate_package(
            _package(values={"correlation_cap": 0.65}),
            proposals={"correlation_cap": {"reason": "no evidence"}})
        assert verdict["decision"] == "REJECTED"
        assert verdict["violations"][0]["kind"] == "PROPOSAL_INCOMPLETE"

    def test_complete_proposal_unblocks(self):
        verdict = gov.validate_package(
            _package(values={"correlation_cap": 0.65}),
            proposals={"correlation_cap": _complete_proposal()})
        assert verdict["decision"] == "VALIDATED"

    def test_absent_proposal_for_a_changed_value_is_rejected(self):
        verdict = gov.validate_package(_package(), proposals={})
        assert any(v["kind"] == "PROPOSAL_ABSENT" for v in verdict["violations"])

    def test_code_revision_must_be_git40(self):
        with pytest.raises(gov.GovernanceError):
            _package(code_revision="abc")

    def test_version_format_enforced(self):
        with pytest.raises(gov.GovernanceError):
            _package(version="v1")

    def test_package_environment_cannot_be_live(self):
        with pytest.raises(gov.GovernanceError):
            _package(environment="LIVE")


# --------------------------------------------------------------------------
# W.5 / G6 — research may never write live parameters
# --------------------------------------------------------------------------

class TestLiveParamsWriteForbidden:
    def test_live_params_target_is_refused(self, tmp_path):
        target = gov.LIVE_PARAMS_DIR / "risk_defaults_v1.yaml"
        with pytest.raises(gov.ResearchRedLineError) as err:
            gov.assert_live_params_untouched(_package(), target,
                                             research_root=tmp_path)
        assert "LIVE_PARAMS_WRITE_FORBIDDEN" in str(err.value)

    def test_directory_traversal_into_params_is_refused(self):
        """A `..` traversal from the real suggestions dir lands in the live
        params dir — the guard resolves paths FIRST, so it still refuses."""
        sneaky = (gov.SUGGESTIONS_DIR / ".." / ".." / ".." / "params"
                  / "risk_defaults_v1.yaml")
        assert sneaky.resolve() == (gov.LIVE_PARAMS_DIR
                                   / "risk_defaults_v1.yaml").resolve()
        with pytest.raises(gov.ResearchRedLineError) as err:
            gov.assert_live_params_untouched(_package(), sneaky)
        assert "LIVE_PARAMS_WRITE_FORBIDDEN" in str(err.value)

    def test_default_research_root_is_the_suggestions_dir(self, tmp_path):
        with pytest.raises(gov.ResearchRedLineError) as err:
            gov.assert_live_params_untouched(
                _package(), tmp_path / "somewhere" / "s.json")
        assert "SUGGESTION_TARGET_OUTSIDE_RESEARCH" in str(err.value)

    def test_target_outside_research_is_refused(self, tmp_path):
        with pytest.raises(gov.ResearchRedLineError) as err:
            gov.assert_live_params_untouched(
                _package(), tmp_path / "elsewhere.json")
        assert "SUGGESTION_TARGET_OUTSIDE_RESEARCH" in str(err.value)

    def test_frozen_params_files_are_untouched_by_this_suite(self):
        """The six frozen YAMLs stay read-only except the two CP-14.6 mandated
        edits (D49 values, family_engines) and the new decision_v1.yaml."""
        import subprocess
        diff = subprocess.run(["git", "status", "--porcelain", "params"],
                              capture_output=True, text=True, check=True)
        changed = set()
        for line in diff.stdout.splitlines():
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1].strip()
            changed.add(path)
        allowed = {
            "params/e11_params_v4.yaml",
            "params/setup_weights_v1.yaml",
            "params/decision_v1.yaml",
        }
        assert changed <= allowed


class TestInjectionLedger:
    def test_first_injection_writes_a_suggestion(self, tmp_path):
        ledger = gov.InjectionLedger(path=tmp_path / "injection_log.json",
                                     research_root=tmp_path)
        result = ledger.inject(_package(), package_dir=tmp_path / "suggestions")
        assert result["cached"] is False
        assert Path(result["path"]).exists()
        payload = json.loads(Path(result["path"]).read_text())
        assert payload["package_id"] == "pkg-test-1"
        assert payload["contract_version"] == gov.CONTRACT_VERSION

    def test_reinjection_is_a_no_op_t_pkg_001(self, tmp_path):
        ledger = gov.InjectionLedger(path=tmp_path / "injection_log.json",
                                     research_root=tmp_path)
        first = ledger.inject(_package(), package_dir=tmp_path / "suggestions")
        second = ledger.inject(_package(), package_dir=tmp_path / "suggestions")
        assert second["cached"] is True and second["no_op"] is True
        assert second["identical"] is True
        assert second["path"] == first["path"]
        assert len(ledger) == 1

    def test_injection_into_params_is_refused(self, tmp_path):
        ledger = gov.InjectionLedger(path=tmp_path / "injection_log.json",
                                     research_root=tmp_path)
        with pytest.raises(gov.ResearchRedLineError):
            ledger.inject(_package(), package_dir=gov.LIVE_PARAMS_DIR)

    def test_idempotency_survives_a_process_restart(self, tmp_path):
        path = tmp_path / "injection_log.json"
        gov.InjectionLedger(path=path, research_root=tmp_path).inject(
            _package(), package_dir=tmp_path / "suggestions")
        reloaded = gov.InjectionLedger(path=path, research_root=tmp_path)
        again = reloaded.inject(_package(), package_dir=tmp_path / "suggestions")
        assert again["cached"] is True and len(reloaded) == 1
