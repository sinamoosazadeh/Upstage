"""Ch.17 — Parameter Governance (SL-12) as an executable service.

Blueprint law implemented here
------------------------------
§17.1  four parameter classes (static/architecture, static/owner,
       dynamic/governed, research-only); three resolution tiers (L1 default /
       L2 profile / L3 symbol override); the constrained update
       ``θ′ = Π_[L,U](θ + Δ)``; the normative change-proposal protocol
       (reason + 180-day PIT backtest + 30-day forward observation + OOS
       evaluation + parameter-board approval); the sensitivity-removal
       criterion (Sobol ``S1/ST < 0.05`` ⇒ removal *candidate*, never
       automatic); the Empirical Closure (EC) register (a quantity without an
       APPROVED closure has **no active value** and every dependent path stays
       conservative); and the governed-default table (34 rows) that governs
       *changes* without altering any frozen §6 value.
W.5    RED LINE: no optimizer output may touch the 14 hard vetoes
       (SL-5 registry names only), margin-health thresholds, capital caps,
       circuit breakers or owner-set ceilings (leverage TF cap, max loss per
       trade/day). A package that touches them is rejected *before* paper
       trial.
W.5/§17.1  a governed value's runtime home is ``params/*.yaml`` (§9.5-10):
       this module never writes a live parameter file — suggestions land in
       ``apex/research/params_suggestions/`` only (Wave-Out item "optimizer
       writing live yaml"; G6).

The registry records the blueprint's own number *and* the frozen YAML value
where one exists; the two are compared and divergences are reported as
``doc_inconsistency`` notes — never silently reconciled (G13).
``[ISSUE-CP8-001]`` records the one divergence found (``budget_per_trade``).

CONTRACT_VERSION 4.0.0.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from apex.config import load_params
from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex
from apex.research.proxies import REPO_ROOT
from apex.risk.kernel import veto_definition

CONTRACT_VERSION = "4.0.0"

SUGGESTIONS_DIR = REPO_ROOT / "apex" / "research" / "params_suggestions"
LIVE_PARAMS_DIR = REPO_ROOT / "params"
INJECTION_LOG_NAME = "injection_log.json"


class GovernanceError(ValueError):
    """A governance rule refused the operation (fail-closed)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class ResearchRedLineError(GovernanceError):
    """W.5 RED LINE: the package (or the write target) is forbidden."""


# --------------------------------------------------------------------------
# §17.1 — classes and tiers
# --------------------------------------------------------------------------

PARAM_CLASSES: Tuple[str, ...] = (
    "static/architecture", "static/owner", "dynamic/governed", "research-only")

RESOLUTION_TIERS: Tuple[str, ...] = ("L1", "L2", "L3")
PROFILE_NAMES: Tuple[str, ...] = ("Aggressive", "Balanced", "Conservative")


@dataclass(frozen=True)
class GovernedParameter:
    """One row of the §17.1 governed-default layer."""

    name: str
    l1_default: Any
    unit: str
    param_class: str
    low: Optional[float] = None
    high: Optional[float] = None
    yaml_ref: str = ""            # "params/<file>.yaml#<key>" when one exists
    owner_module: str = ""        # runtime home when no YAML row exists (CP-7 §003)
    cite: str = "APEX_GEN5.md L16972-17006"

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "l1_default": self.l1_default,
                "unit": self.unit, "class": self.param_class,
                "bounds": [self.low, self.high], "yaml_ref": self.yaml_ref,
                "owner_module": self.owner_module, "cite": self.cite,
                "contract_version": CONTRACT_VERSION}


def _g(name: str, l1: Any, unit: str, cls: str, low: Optional[float] = None,
       high: Optional[float] = None, yaml_ref: str = "",
       owner: str = "") -> GovernedParameter:
    return GovernedParameter(name, l1, unit, cls, low, high, yaml_ref, owner)


#: §17.1 governed defaults (the blueprint's own table, row by row).
GOVERNED_DEFAULTS: Tuple[GovernedParameter, ...] = (
    _g("budget_per_trade", "1.0%", "% of capital", "dynamic/governed",
       0.0, 0.05, "params/risk_defaults_v1.yaml#budget_per_trade"),
    _g("risk_ladder_multiplier", "1.0/1.0/0.75/0.50/0.0",
       "No/Low/Medium/High/Critical", "dynamic/governed", 0.0, 1.0,
       owner="apex.risk.kernel.ladder_multiplier"),
    _g("correlation_cap", 0.70, "ρ", "dynamic/governed", 0.0, 1.0,
       "params/risk_defaults_v1.yaml#correlation_cap"),
    _g("symbol_exposure_cap", "20%", "% of capital", "static/owner", 0.0, 1.0,
       owner="apex.risk.kernel.adjudicate"),
    _g("portfolio_exposure_cap", "60%", "% of capital", "static/owner", 0.0, 1.0,
       owner="apex.risk.kernel.adjudicate"),
    _g("capital_hard_cap", "owner-set", "% of capital", "static/owner", 0.0, 1.0,
       owner="apex.risk.kernel.adjudicate"),
    _g("k_attn", 0.05, "× ATR-capped", "dynamic/governed", 0.0, 1.0,
       "params/risk_defaults_v1.yaml#k_attn"),
    _g("P_min(tf)", "0.52/0.55/0.50", "probability", "dynamic/governed",
       0.0, 1.0, owner="apex.setup.gates"),
    _g("C_min", 0.50, "process confidence", "dynamic/governed", 0.0, 1.0,
       owner="apex.setup.gates"),
    _g("lambda_forecast_decay", 0.1, "per bar", "dynamic/governed", 0.0, 1.0,
       owner="apex.forecast.logistic"),
    _g("alpha_spread", 0.25, "× (order_size / ADV)", "dynamic/governed",
       0.0, 5.0, owner="apex.decision.pipeline.slippage_model"),
    _g("fee", "0.02%", "per trade", "static/architecture", 0.0, 0.01,
       owner="apex.decision.pipeline"),
    _g("retry", 3, "attempts", "static/architecture", 1.0, 10.0,
       owner="apex.data_catalog.ingest.toobit_public"),
    _g("H_max(tf)", "12 (1m) / 24 (1h)", "candles", "dynamic/governed",
       1.0, 1000.0, owner="apex.playbook.pb_fvg_sweep_rev_a.max_hold_for"),
    _g("daily_loss_limit", "3%", "% of capital", "dynamic/governed", 0.0, 0.25,
       "params/risk_defaults_v1.yaml#daily_loss_cap"),
    _g("weekly_loss_limit", "6%", "% of capital", "dynamic/governed", 0.0, 0.5,
       "params/risk_defaults_v1.yaml#weekly_loss_cap"),
    _g("max_consecutive_losses", 4, "trades", "dynamic/governed", 1.0, 20.0,
       "params/risk_defaults_v1.yaml#consecutive_loss_halt"),
    _g("cvar_95_cap", "4%", "% of capital", "dynamic/governed", 0.0, 0.25,
       owner="apex.risk.kernel.cvar_advisory"),
    _g("rollover_threshold", 7, "days to expiry", "dynamic/governed", 0.0, 30.0,
       owner="apex.execution.toobit_map.rollover_entry_allowed"),
    _g("margin_warning", "60%", "of maintenance distance", "dynamic/governed",
       0.0, 1.0, owner="apex.risk.kernel.margin_health_state"),
    _g("margin_action", "40%", "of maintenance distance", "dynamic/governed",
       0.0, 1.0, owner="apex.risk.kernel.margin_health_state"),
    _g("margin_liquidation_approach", "20%", "of maintenance distance",
       "dynamic/governed", 0.0, 1.0,
       owner="apex.risk.kernel.margin_health_state"),
    _g("crisis_factor", 0.5, "× exposure caps", "dynamic/governed", 0.0, 1.0,
       owner="apex.risk.kernel.circuit_breaker_reset"),
    _g("heartbeat_interval", 60, "seconds", "static/architecture", 1.0, 3600.0,
       owner="apex.ops.watchdog.HEARTBEAT_INTERVAL_SECONDS"),
    _g("heartbeat_miss_limit", 3, "consecutive misses", "static/architecture",
       1.0, 100.0, owner="apex.ops.watchdog.HEARTBEAT_MISS_LIMIT"),
    _g("clock_drift_tolerance", 5, "seconds", "static/architecture", 0.0, 60.0,
       owner="apex.execution.fsm.StartupReconciliation"),
    _g("backup_interval", 15, "minutes", "static/architecture", 1.0, 1440.0,
       owner="apex.ops.backup.BACKUP_INTERVAL_MINUTES"),
    _g("restore_drill_period", 90, "days", "static/architecture", 1.0, 365.0,
       owner="apex.ops.backup.RESTORE_DRILL_PERIOD_DAYS"),
    _g("storage_floor", "15%", "free storage", "dynamic/governed", 0.0, 1.0,
       owner="apex.ops.backup.STORAGE_FLOOR_FRACTION"),
    _g("alert_dedup_window", 30, "minutes", "dynamic/governed", 0.0, 1440.0,
       owner="apex.telegram.signaling.ALERT_DEDUP_WINDOW_SECONDS"),
    _g("submission_timeout", 5, "seconds", "dynamic/governed", 0.0, 60.0,
       owner="apex.execution.fsm"),
    _g("fill_timeout", 5, "seconds", "dynamic/governed", 0.0, 60.0,
       owner="apex.execution.fsm"),
    _g("key_rotation_period", 90, "days", "static/architecture", 1.0, 365.0,
       owner="owner procedure (AI.13)"),
    _g("incident_contain_target", 15, "minutes", "static/architecture",
       1.0, 240.0, owner="owner procedure (AI.13)"),
)

GOVERNED_DEFAULT_COUNT = 34

_PARAM_BY_NAME: Dict[str, GovernedParameter] = {p.name: p for p in GOVERNED_DEFAULTS}


def governed_default(name: str) -> GovernedParameter:
    if name not in _PARAM_BY_NAME:
        raise GovernanceError("UNKNOWN_GOVERNED_PARAM", name)
    return _PARAM_BY_NAME[name]


def parameter_class(name: str) -> str:
    return governed_default(name).param_class


def _percent(text: Any) -> Optional[float]:
    if isinstance(text, str) and text.strip().endswith("%"):
        return float(text.strip().rstrip("%")) / 100.0
    return None


def yaml_values() -> Dict[str, Any]:
    """Flatten the frozen YAML values referenced by ``yaml_ref``."""
    params = load_params()
    flat: Dict[str, Any] = {}
    for row in GOVERNED_DEFAULTS:
        if not row.yaml_ref:
            continue
        file_part, _, key = row.yaml_ref.partition("#")
        name = file_part.split("/")[1].replace("_v1.yaml", "").replace("_v4.yaml", "")
        data = params.get(name) or {}
        if key in data:
            flat[row.name] = data[key]
    return flat


def assert_yaml_consistency() -> List[Dict[str, Any]]:
    """Compare the §17.1 blueprint numbers with the frozen YAML values.

    Divergences are reported, never resolved here (G13): the YAML is the
    runtime source of record (§9.5-10) and CP-8 may not edit it.
    """
    flat = yaml_values()
    divergences: List[Dict[str, Any]] = []
    for row in GOVERNED_DEFAULTS:
        if row.name not in flat:
            continue
        yaml_value = flat[row.name]
        blueprint_value = _percent(row.l1_default)
        if blueprint_value is None and isinstance(row.l1_default, (int, float)):
            blueprint_value = float(row.l1_default)
        if blueprint_value is None:
            continue
        if not math.isclose(float(yaml_value), blueprint_value,
                            rel_tol=0.0, abs_tol=1e-12):
            divergences.append({
                "name": row.name, "blueprint": row.l1_default,
                "blueprint_numeric": blueprint_value, "yaml": yaml_value,
                "yaml_ref": row.yaml_ref, "note": "doc_inconsistency",
                "resolution": "YAML loads at runtime (§9.5-10); row recorded, "
                              "never rewritten (ISSUE-CP8-001)",
            })
    return divergences


def resolution_tier(*, profile: Optional[str] = None,
                    symbol: Optional[str] = None) -> str:
    """L1 default < L2 profile < L3 symbol override (§17.1 resolution tiers)."""
    if symbol:
        return "L3"
    if profile:
        if profile not in PROFILE_NAMES:
            raise GovernanceError("UNKNOWN_PROFILE", profile)
        return "L2"
    return "L1"


# --------------------------------------------------------------------------
# §17.1 — constrained update θ′ = Π_[L,U](θ + Δ)
# --------------------------------------------------------------------------

def project(value: float, low: float, high: float) -> float:
    """``Π_[L,U]`` — the projection operator of the constrained update."""
    if low > high:
        raise GovernanceError("BOUNDS_INVERTED", f"[{low},{high}]")
    if not (math.isfinite(low) and math.isfinite(high)):
        raise GovernanceError("BOUNDS_NON_FINITE")
    return min(max(float(value), float(low)), float(high))


def constrained_update(*, name: str, current: float, delta: float,
                       low: Optional[float] = None,
                       high: Optional[float] = None) -> Dict[str, Any]:
    """One governed step: ``θ′ = Π_[L,U](θ + Δ)``, bounds from the register
    unless the caller supplies tighter owner bounds."""
    row = governed_default(name)
    lo = row.low if low is None else float(low)
    hi = row.high if high is None else float(high)
    if lo is None or hi is None:
        raise GovernanceError("BOUNDS_UNDEFINED", name)
    if not math.isfinite(float(delta)):
        raise GovernanceError("DELTA_NON_FINITE", str(delta))
    if not (lo <= float(current) <= hi):
        raise GovernanceError("CURRENT_OUT_OF_BOUNDS",
                             f"{name}={current} ∉ [{lo},{hi}]")
    proposed = float(current) + float(delta)
    projected = project(proposed, lo, hi)
    return {"name": name, "current": float(current), "delta": float(delta),
            "proposed": proposed, "projected": projected,
            "clamped": not math.isclose(proposed, projected, rel_tol=0.0,
                                        abs_tol=1e-15),
            "bounds": [lo, hi], "class": row.param_class}


# --------------------------------------------------------------------------
# §17.1 — change-proposal protocol (normative)
# --------------------------------------------------------------------------

PROPOSAL_REQUIRED_ITEMS: Tuple[str, ...] = (
    "reason", "pit_backtest_180d", "forward_observation_30d",
    "out_of_sample_evaluation", "parameter_board_approval")


def validate_change_proposal(proposal: Mapping[str, Any]) -> Dict[str, Any]:
    """The five mandatory items of a change proposal, checked item by item.

    A missing/empty item fails the proposal closed: it may not be promoted and
    its dependents keep the current value.
    """
    missing: List[str] = []
    for item in PROPOSAL_REQUIRED_ITEMS:
        value = proposal.get(item)
        if value is None or value == "" or value == {} or value == []:
            missing.append(item)
    if "pit_backtest_180d" in proposal and proposal.get("pit_backtest_180d"):
        window = proposal["pit_backtest_180d"]
        if isinstance(window, (int, float)) and float(window) < 180.0:
            missing.append("pit_backtest_180d<180d")
    if "forward_observation_30d" in proposal and \
            proposal.get("forward_observation_30d"):
        window = proposal["forward_observation_30d"]
        if isinstance(window, (int, float)) and float(window) < 30.0:
            missing.append("forward_observation_30d<30d")
    decision = "APPROVED" if not missing else "REJECTED"
    return {"decision": decision, "missing": missing,
            "required": list(PROPOSAL_REQUIRED_ITEMS),
            "conservative_value_kept": bool(missing)}


# --------------------------------------------------------------------------
# §17.1 — Empirical Closure (EC) register
# --------------------------------------------------------------------------

EC_FIELDS: Tuple[str, ...] = (
    "semantic_question", "unit", "scope", "allowed_bounds",
    "measurement_method", "dataset", "sample", "uncertainty", "required_test",
    "fallback", "behavior_if_unresolved", "status")

EC_STATUSES: Tuple[str, ...] = ("OPEN", "APPROVED", "REJECTED")


@dataclass
class ECEntry:
    """One empirical-closure record; until ``status == "APPROVED"`` the
    quantity has **no active value** (§17.1)."""

    name: str
    semantics: Mapping[str, Any]
    status: str = "OPEN"

    def __post_init__(self) -> None:
        if self.status not in EC_STATUSES:
            raise GovernanceError("EC_STATUS_QX", self.status)
        missing = [f for f in EC_FIELDS if f not in self.semantics
                   and f not in ("status",)]
        if missing:
            raise GovernanceError("EC_FIELDS_MISSING", ",".join(missing))

    @property
    def has_active_value(self) -> bool:
        return self.status == "APPROVED"

    def conservative(self) -> bool:
        """True whenever a dependent path must behave conservatively."""
        return not self.has_active_value

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "status": self.status,
                "has_active_value": self.has_active_value,
                "semantics": dict(self.semantics)}


class ECRegister:
    """The EC register of the research plane."""

    def __init__(self, entries: Optional[Iterable[ECEntry]] = None) -> None:
        self._entries: Dict[str, ECEntry] = {}
        for entry in entries or ():
            self.register(entry)

    def register(self, entry: ECEntry) -> ECEntry:
        self._entries[entry.name] = entry
        return entry

    def get(self, name: str) -> ECEntry:
        if name not in self._entries:
            raise GovernanceError("EC_ENTRY_ABSENT", name)
        return self._entries[name]

    def active_value(self, name: str) -> Optional[float]:
        """``None`` unless APPROVED — the dependent path then stays
        conservative instead of using an unapproved value."""
        entry = self.get(name)
        return float(entry.semantics["value"]) if (entry.has_active_value
                                                  and "value" in entry.semantics) else None

    def conservative_paths(self) -> List[str]:
        return sorted(n for n, e in self._entries.items() if e.conservative())

    def __len__(self) -> int:
        return len(self._entries)


# --------------------------------------------------------------------------
# §17.1 — sensitivity-removal criterion
# --------------------------------------------------------------------------

SENSITIVITY_REMOVAL_THRESHOLD = 0.05


def sensitivity_removal_candidate(*, s1: float, st: float,
                                  threshold: float = SENSITIVITY_REMOVAL_THRESHOLD
                                  ) -> Dict[str, Any]:
    """``S1/ST < 0.05`` marks a parameter a removal *candidate*; removal stays
    a governance decision and is never automatic."""
    if st <= 0.0:
        raise GovernanceError("SOBOL_ST_NON_POSITIVE")
    ratio = float(s1) / float(st)
    return {"s1": float(s1), "st": float(st), "ratio": ratio,
            "threshold": float(threshold), "removal_candidate": ratio < float(threshold),
            "automatic_removal": False,
            "note": "candidate only — removal is a governance decision (§17.1)"}


# --------------------------------------------------------------------------
# W.5 — RED LINE package validation
# --------------------------------------------------------------------------

VETO_FIELD_NAMES: Tuple[str, ...] = tuple(
    veto_definition(n)["name"] for n in range(1, 15))

#: W.5 — fields no package may ever carry (owner-static, X.7).
FORBIDDEN_FIELDS: Tuple[str, ...] = (
    "veto_registry", "veto_thresholds", "veto_count",
    "margin_warning", "margin_action", "margin_liquidation_approach",
    "capital_hard_cap", "symbol_exposure_cap", "portfolio_exposure_cap",
    "circuit_breaker", "circuit_breakers",
    "leverage_cap_by_tf", "system_leverage_cap_by_tf", "max_leverage",
    "max_loss_per_trade", "max_loss_per_day", "daily_loss_limit",
    "weekly_loss_limit", "risk_ladder_multiplier", "crisis_factor",
) + VETO_FIELD_NAMES

_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.]+)?$")


@dataclass
class ParameterPackage:
    """A versioned, immutable candidate parameter package (SL-12)."""

    package_id: str
    version: str
    values: Mapping[str, Any]
    code_revision: str           # git40 (§18.1 CodeRevision)
    feature_version: str
    model_version: str
    seed: int
    created_at: str = ""
    reason: str = ""
    environment: str = "RESEARCH"

    def __post_init__(self) -> None:
        if not _VERSION_RE.match(self.version):
            raise GovernanceError("VERSION_FORMAT_QX", self.version)
        if len(self.code_revision) != 40 or not re.match(r"^[0-9a-f]{40}$",
                                                        self.code_revision):
            raise GovernanceError("CODE_REVISION_QX", self.code_revision)
        if self.environment not in ("RESEARCH", "BACKTEST", "PAPER"):
            raise GovernanceError("PACKAGE_ENVIRONMENT_QX", self.environment)
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def content_hash(self) -> str:
        return sha256_hex(canonical_json({
            "package_id": self.package_id, "version": self.version,
            "values": dict(self.values), "code_revision": self.code_revision,
            "feature_version": self.feature_version,
            "model_version": self.model_version, "seed": int(self.seed)}))

    def to_dict(self) -> Dict[str, Any]:
        return {"package_id": self.package_id, "version": self.version,
                "values": dict(self.values), "code_revision": self.code_revision,
                "feature_version": self.feature_version,
                "model_version": self.model_version, "seed": int(self.seed),
                "created_at": self.created_at, "reason": self.reason,
                "environment": self.environment,
                "content_hash": self.content_hash(),
                "contract_version": CONTRACT_VERSION}


def validate_package(package: ParameterPackage, *,
                     proposals: Optional[Mapping[str, Mapping[str, Any]]] = None
                     ) -> Dict[str, Any]:
    """W.5 RED LINE + §17.1 bounds + EC/closure check, before paper trial."""
    violations: List[Dict[str, Any]] = []
    for key, value in package.values.items():
        if key in FORBIDDEN_FIELDS:
            violations.append({"kind": "RED_LINE_FIELD", "field": key,
                               "value": value,
                               "rule": "W.5 — vetoes / margin thresholds / "
                                       "capital caps / circuit breakers / "
                                       "owner ceilings are immutable"})
            continue
        if key in _PARAM_BY_NAME:
            row = _PARAM_BY_NAME[key]
            if row.low is None or row.high is None:
                continue
            if not (row.low <= float(value) <= row.high):
                violations.append({"kind": "OUT_OF_BOUNDS", "field": key,
                                   "value": value,
                                   "bounds": [row.low, row.high]})
            if row.param_class == "static/owner":
                violations.append({"kind": "OWNER_STATIC_FIELD", "field": key,
                                   "rule": "static/owner — owner-only change"})
    if proposals is not None:
        for name in package.values:
            proposal = proposals.get(name)
            if proposal is None:
                violations.append({"kind": "PROPOSAL_ABSENT", "field": name})
                continue
            verdict = validate_change_proposal(proposal)
            if verdict["decision"] != "APPROVED":
                violations.append({"kind": "PROPOSAL_INCOMPLETE",
                                   "field": name, "missing": verdict["missing"]})
    return {"package_id": package.package_id, "decision":
            "REJECTED" if violations else "VALIDATED",
            "violations": violations, "values_checked": len(package.values),
            "red_line_clean": not any(v["kind"] in (
                "RED_LINE_FIELD", "OWNER_STATIC_FIELD") for v in violations)}


def assert_live_params_untouched(package: ParameterPackage, target: Path,
                                 *, research_root: Optional[Path] = None) -> None:
    """The write target must live under ``apex/research/params_suggestions/``.

    Any attempt to write a live ``params/*.yaml`` raises
    :class:`ResearchRedLineError` — the Wave-Out item "optimizer writing live
    yaml" made executable (G6). ``research_root`` only relocates the *allowed*
    research directory (tests, alternate sandboxes); the live-params refusal is
    absolute and can never be relocated.
    """
    resolved = Path(target).resolve()
    allowed = Path(research_root).resolve() if research_root is not None \
        else SUGGESTIONS_DIR.resolve()
    live = LIVE_PARAMS_DIR.resolve()
    if live == resolved or live in resolved.parents:
        raise ResearchRedLineError(
            "LIVE_PARAMS_WRITE_FORBIDDEN",
            f"{resolved} is inside {live} — research may never write live "
            f"parameters (W.5 RED LINE / G6)")
    if allowed != resolved and allowed not in resolved.parents:
        raise ResearchRedLineError(
            "SUGGESTION_TARGET_OUTSIDE_RESEARCH",
            f"{resolved} is outside {allowed}")


class InjectionLedger:
    """Version-locked injection record: re-injecting a package is a no-op
    (T-PKG-001, AI.8 package-injection idempotency)."""

    def __init__(self, path: Optional[Path] = None, *,
                 research_root: Optional[Path] = None) -> None:
        self.path = Path(path) if path else SUGGESTIONS_DIR / INJECTION_LOG_NAME
        self.research_root = (Path(research_root) if research_root is not None
                              else SUGGESTIONS_DIR)
        self._records: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            self._records = json.loads(self.path.read_text(encoding="utf-8"))

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._records, sort_keys=True, indent=2),
                       encoding="utf-8")
        os.replace(tmp, self.path)

    def inject(self, package: ParameterPackage, *, package_dir: Path) -> Dict[str, Any]:
        """Write the package file (suggestion only) and record the injection."""
        assert_live_params_untouched(package, package_dir,
                                     research_root=self.research_root)
        if package.package_id in self._records:
            existing = self._records[package.package_id]
            same_hash = existing["content_hash"] == package.content_hash()
            return {"package_id": package.package_id, "cached": True,
                    "no_op": True, "identical": same_hash,
                    "path": existing["path"],
                    "reason": "PACKAGE_ALREADY_INJECTED"}
        package_dir.mkdir(parents=True, exist_ok=True)
        target = package_dir / f"{package.package_id}-{package.version}.json"
        assert_live_params_untouched(package, target,
                                     research_root=self.research_root)
        target.write_text(json.dumps(package.to_dict(), sort_keys=True,
                                     indent=2), encoding="utf-8")
        self._records[package.package_id] = {
            "package_id": package.package_id, "version": package.version,
            "content_hash": package.content_hash(), "path": str(target),
            "created_at": package.created_at}
        self._flush()
        return {"package_id": package.package_id, "cached": False,
                "no_op": False, "path": str(target)}

    def records(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._records)

    def __len__(self) -> int:
        return len(self._records)


def governance_summary() -> Dict[str, Any]:
    """Audit surface for the closeout sweep / FINAL_REPORT."""
    return {
        "governed_defaults": len(GOVERNED_DEFAULTS),
        "expected_governed_defaults": GOVERNED_DEFAULT_COUNT,
        "classes": list(PARAM_CLASSES),
        "tiers": list(RESOLUTION_TIERS),
        "red_line_forbidden_fields": len(FORBIDDEN_FIELDS),
        "veto_names_registered": len(VETO_FIELD_NAMES),
        "yaml_backed_rows": sum(1 for r in GOVERNED_DEFAULTS if r.yaml_ref),
        "module_backed_rows": sum(1 for r in GOVERNED_DEFAULTS if r.owner_module),
        "contract_version": CONTRACT_VERSION,
    }
