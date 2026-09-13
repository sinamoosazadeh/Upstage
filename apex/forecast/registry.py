"""APEX_GEN5 — Engine quality-model registry (Ch.13 §13.2 AG.0–AG.5).

Layer-2 **design obligations**, recorded at schema/obligation level exactly as
the frozen text registers them: "Obligations bind; instantiations do not appear
in this frozen document." This module therefore fixes, per model, the seven AG.2
fields (definition / formula sketch / input features / output binding /
parameter governance / status / verification battery) and NOTHING more.

Additivity discipline (AG.0, enforced by the registry shape itself):
* no frozen engine body (E01–E12) is modified, extended or reinterpreted;
* **no new hard gate, veto or rejection path is created** — the 13 Setup gates
  and the 14 Risk vetoes stay exactly as specified;
* every AG output binds to ``q_i`` (evidence quality) of the frozen
  ``raw_setup_score = Σ(w_i·s_i·q_i·f_i)`` — never to ``s_i`` (presence stays a
  deterministic engine output), never as a veto, gate or exit;
* there is no parallel scoring authority (the Signal Optimizer's
  parameterization is the sole source of truth).

The honesty rule (AG.1) is carried explicitly: for E08 no model is designed at
all, because the audit claim against it was re-verified FALSE — the capability
already exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Mapping, Optional, Tuple

CONTRACT_VERSION = "4.0.0"

AG2_FIELDS: Tuple[str, ...] = (
    "definition", "formula_sketch", "input_features", "output_binding",
    "parameter_governance", "status", "verification_battery",
)
AG_STATUSES: FrozenSet[str] = frozenset({"OBLIGATION", "RESEARCH",
                                        "VERIFIED-EXISTING"})
PERMITTED_BINDINGS: FrozenSet[str] = frozenset({"q_i", "none"})


@dataclass(frozen=True)
class AGModel:
    """One AG.2 model contract — exactly seven fields, no authority."""

    key: str
    engine: str
    definition: str
    formula_sketch: str
    input_features: Tuple[str, ...]
    output_binding: str
    parameter_governance: str
    status: str
    verification_battery: str
    gate_enrichment: Optional[Tuple[int, ...]] = None   # existing gates only

    def __post_init__(self) -> None:
        missing = [f for f in AG2_FIELDS if getattr(self, f, None) in (None, "")]
        if missing:
            raise ValueError(f"AG_MODEL_INCOMPLETE_QX: {missing} (AG.2 fixes "
                             f"exactly these seven fields)")
        if self.status not in AG_STATUSES:
            raise ValueError(f"AG_STATUS_QX: {self.status!r} not in "
                             f"{sorted(AG_STATUSES)}")
        if self.output_binding not in PERMITTED_BINDINGS:
            raise ValueError(
                f"AG_BINDING_QX: {self.output_binding!r} — AG models bind to "
                f"q_i (or nothing). s_i stays deterministic engine output and "
                f"no AG output may act as veto, gate or exit (AG.2 field 4)")
        if self.gate_enrichment:
            bad = [g for g in self.gate_enrichment if g not in (7, 8, 9, 10)]
            if bad:
                raise ValueError(
                    f"AG_GATE_QX: {bad} — gates 7–10 may receive governed "
                    f"enrichment only; no gate is added, removed or altered")

    def to_dict(self) -> Dict[str, object]:
        return {f: getattr(self, f) for f in AG2_FIELDS} | {
            "engine": self.engine, "key": self.key,
            "gate_enrichment": list(self.gate_enrichment or ()),
            "contract_version": CONTRACT_VERSION}


_GOV = "SL-12 bounded governed ranges inside the Signal Optimizer domain " \
        "(W.1); W.5 RED LINE in full (no package may touch the 14 hard vetoes, " \
        "margin-health thresholds, capital caps, circuit breakers, exit " \
        "precedence or owner-set ceilings); calibration-drift auto-rollback " \
        "at >10%"
_BATT = "shared SL-13 validation batteries (walk-forward + stress, Research " \
        "Plane subsystems) plus the calibration battery (Brier / log-loss / " \
        "rolling calibration error); no live injection outside the single " \
        "promotion pipeline (the Promotion Protocol)"

AG_MODEL_REGISTRY: Mapping[str, AGModel] = {
    "E01-AG": AGModel(
        key="E01-AG", engine="E01",
        definition="Structural quality score over confirmations (volume "
                   "participation, liquidity context, order-flow agreement, "
                   "HTF alignment, volatility-regime compatibility) plus the "
                   "birth/age/decay lifecycle of a structural level.",
        formula_sketch="Q_struct = Σ_k w_k·c_k over c_k ∈ [0,1], Σw_k = 1; "
                       "age-decay modifier d(age) ∈ [0,1] with governed shape.",
        input_features=("E01 BOS/CHoCH/MSS/DISPLACEMENT", "F01/F02 body-class "
                        "features", "E03 VR/EVR", "E02 levels",
                        "SL-8 MTF state (read-only)", "E04 volatility regime"),
        output_binding="q_i", parameter_governance=_GOV, status="OBLIGATION",
        verification_battery=_BATT),
    "E02-AG": AGModel(
        key="E02-AG", engine="E02",
        definition="Liquidity participant model (retail-stop cluster vs "
                   "institutional resting interest vs liquidation density) and "
                   "the L0–L4 liquidity hierarchy — a soft attribution only.",
        formula_sketch="p(class | sweep signature, volume signature, OI "
                       "response, funding context) with governed priors; "
                       "hierarchy rank = governed weighted score.",
        input_features=("E02 SWEEP/EQUAL_HIGHS/EQUAL_LOWS", "feature 74 "
                        "APEX.L00.MOLE.LIQ.SWEEP.STRENGTH.V1", "proxies "
                        "B04/B06/B07 (Q3), D01 (Q3), D02, D03"),
        output_binding="q_i", parameter_governance=_GOV, status="OBLIGATION",
        verification_battery=_BATT),
    "E03-AG": AGModel(
        key="E03-AG", engine="E03",
        definition="Volume-intent classification over {accumulation, "
                   "distribution, panic-exit}, consuming — never replacing — "
                   "the frozen E03 probabilistic layer.",
        formula_sketch="intent posterior from volume-cluster signature, price "
                       "location, delta-proxy asymmetry and regime context; "
                       "entropy-gated emission.",
        input_features=("E03 VolumeZ/VolRatio/EVR/VR/BVC/VPIN", "B09 value "
                        "area", "D01 delta proxy (Q3)", "E11 regime snapshot",
                        "E12 temporal_window"),
        output_binding="q_i", parameter_governance=_GOV, status="OBLIGATION",
        verification_battery=_BATT),
    "E04-AG": AGModel(
        key="E04-AG", engine="E04",
        definition="Compression→expansion transition quality for the "
                   "volatility evidence.",
        formula_sketch="governed bounded score over HV percentile bands and "
                       "transition evidence (no invented coefficients).",
        input_features=("E04 HV bands q15/q35/q75/q95", "ATR (governed)",
                        "cluster persistence"),
        output_binding="q_i", parameter_governance=_GOV, status="OBLIGATION",
        verification_battery=_BATT, gate_enrichment=(9,)),
    "E05-AG": AGModel(
        key="E05-AG", engine="E05",
        definition="FVG quality score over the already-frozen FVG lifecycle "
                   "(Created/Fresh/Touched/Mitigated/Invalidated/Expired) — "
                   "quality only, not lifecycle invention.",
        formula_sketch="governed weighted quality of width, freshness, "
                       "mitigation state and context strength.",
        input_features=("E05 FVG records", "ATR", "volume context (E03)"),
        output_binding="q_i", parameter_governance=_GOV, status="OBLIGATION",
        verification_battery=_BATT),
    "E06-AG": AGModel(
        key="E06-AG", engine="E06",
        definition="Order-block qualification and failure classification "
                   "(research-plane labels), additive to the frozen Origin/"
                   "Displacement/Structural Consequence/Persistence/Mitigation "
                   "structure.",
        formula_sketch="governed qualification score + failure label; no "
                       "numeric scalar is hardcoded.",
        input_features=("E06 OB records", "E01 structure events", "ATR"),
        output_binding="q_i", parameter_governance=_GOV, status="OBLIGATION",
        verification_battery=_BATT),
    "E07-AG": AGModel(
        key="E07-AG", engine="E07",
        definition="Smart-money event score with the E02 boundary defined (no "
                   "parallel liquidity claim).",
        formula_sketch="governed composition of bundle integrity, weight "
                       "coverage and context agreement (E07 owns the math).",
        input_features=("E07 RTM bundles", "E02 sweeps", "E12 temporal "
                        "provider"),
        output_binding="q_i", parameter_governance=_GOV, status="OBLIGATION",
        verification_battery=_BATT),
    "E08": AGModel(
        key="E08", engine="E08",
        definition="No model: the audit claim that E08 lacks a state machine "
                   "was re-verified FALSE — E08 IS a calibrated probabilistic "
                   "phase machine (AG.1 row 1). The optional time-context note "
                   "is research-only and never an obligation.",
        formula_sketch="none — 'Capabilities that already exist receive no fix "
                       "design' (AG.0 honesty rule).",
        input_features=("n/a — verified-existing"), output_binding="none",
        parameter_governance="n/a (no parameter is introduced)",
        status="VERIFIED-EXISTING", verification_battery=_BATT),
    "E09-AG": AGModel(
        key="E09-AG", engine="E09",
        definition="Trend health score: direction, strength, participation and "
                   "sustainability of the multi-scale stack.",
        formula_sketch="governed weighted composition over the per-scale "
                       "quality record (ADX/Hurst/R²/MK-z already exist).",
        input_features=("E09 scale records", "E01 swings", "E10 momentum "
                        "series", "E04 ATR"),
        output_binding="q_i", parameter_governance=_GOV, status="OBLIGATION",
        verification_battery=_BATT),
    "E10-AG": AGModel(
        key="E10-AG", engine="E10",
        definition="Divergence quality and exhaustion probability (advisory); "
                   "detection itself already exists and is not re-designed.",
        formula_sketch="governed quality over the four normative divergence "
                       "kinds + CONVERGENCE/NONE, plus an advisory exhaustion "
                       "probability.",
        input_features=("E10 divergence records", "mom_series", "price "
                        "swings"),
        output_binding="q_i", parameter_governance=_GOV, status="OBLIGATION",
        verification_battery=_BATT),
    "E11-AG": AGModel(
        key="E11-AG", engine="E11",
        definition="Regime forecasting — RESEARCH (Q6-style) with a "
                   "NO-CONSUMER declaration: it never binds to setup scoring "
                   "and never becomes a trade permission until promoted by "
                   "owner decree through the Promotion Protocol.",
        formula_sketch="registered at obligation level only (no formula is "
                       "invented here).",
        input_features=("E11 regime probability vector (read-only)"),
        output_binding="none", parameter_governance=_GOV, status="RESEARCH",
        verification_battery=_BATT),
    "E12-AG": AGModel(
        key="E12-AG", engine="E12",
        definition="Temporal-window intelligence enrichment (volume migration, "
                   "funding reset, exchange behavior) — additive to the frozen "
                   "UTC windows, never replacing them.",
        formula_sketch="governed enrichment flags/scores carried beside the "
                       "canonical UTC_W0..W3 windows.",
        input_features=("E12 temporal_window records", "exchange calendar "
                        "metadata"),
        output_binding="q_i", parameter_governance=_GOV, status="OBLIGATION",
        verification_battery=_BATT, gate_enrichment=(8,)),
}

AG_REGISTRY_SUMMARY: Tuple[Tuple[str, str, str], ...] = (
    ("E01-AG", "q_i", "OBLIGATION"), ("E02-AG", "q_i", "OBLIGATION"),
    ("E03-AG", "q_i", "OBLIGATION"), ("E04-AG", "q_i (+ gate-9 evidence)",
                                      "OBLIGATION"),
    ("E05-AG", "q_i", "OBLIGATION"), ("E06-AG", "q_i (+ research-plane failure "
                                       "labels)", "OBLIGATION"),
    ("E07-AG", "q_i", "OBLIGATION"),
    ("E08", "n/a", "VERIFIED-EXISTING (optional note: RESEARCH, Q6)"),
    ("E09-AG", "q_i", "OBLIGATION"), ("E10-AG", "q_i (advisory)", "OBLIGATION"),
    ("E11-AG", "none (research-only; NO-CONSUMER)", "RESEARCH (Q6-style)"),
    ("E12-AG", "q_i (+ gate-8 evidence)", "OBLIGATION (additive only)"),
)

RED_LINE = ("No element of Engine Quality Models touches the 14 hard vetoes, "
            "capital caps, exit precedence, the authority hierarchy (Owner > "
            "Risk > Decision > Forecast > Evidence), fail-closed behavior, the "
            "single-file document rule, the four environments, or the single "
            "promotion pipeline.")


def ag_models_bound_to_q_i() -> Tuple[str, ...]:
    return tuple(k for k, m in AG_MODEL_REGISTRY.items()
                 if m.output_binding == "q_i")


def research_only_models() -> Tuple[str, ...]:
    return tuple(k for k, m in AG_MODEL_REGISTRY.items()
                 if m.status == "RESEARCH")


__all__ = ["AG2_FIELDS", "AG_MODEL_REGISTRY", "AG_REGISTRY_SUMMARY",
           "AG_STATUSES", "CONTRACT_VERSION", "PERMITTED_BINDINGS", "RED_LINE",
           "AGModel", "ag_models_bound_to_q_i", "research_only_models"]
