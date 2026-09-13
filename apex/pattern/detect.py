"""APEX_GEN5 — Pattern Intelligence: the operational detector layer (Ch.9).

Blueprint: APEX_GEN5.md Ch.9 §9.0 (L15012–15110), §9.1 detector catalogue +
operational tolerances + the E08 golden-fixture schema lock (L15110–15190)
and §9.2 AC.1–AC.5 (L15190–15210 range).

Laws implemented here
---------------------
* Ch.9 §9.0: "Patterns are detectors on engine evidence. They do not size risk
  and they do not send orders."
* The 20-pattern frozen catalogue is a **legacy/chart-pattern reference**; a
  row is not operationally admitted merely because it appears there. Every
  operational record is an AC.1 Pattern Entity with an explicit
  ``PAT-<family>-<seq>`` id, all ten mandatory fields, and materialization in
  the Data Plane ``pattern_evidence``.
* Round-2 freeze demotion (owner decision): **Three Drives, Gartley, Bat**
  are ``RESEARCH_ONLY`` — they produce no evidence that may contribute to
  setup scoring and participate in no trade permission.
* Operational detection tolerances (bootstrap, SL-12; §9.1 table): double
  top/bottom equality ≤ 0.15·ATR, H&S shoulder equality ≤ 0.25·ATR, triangles
  ≥ 4 touches, flag/pennant pole ≥ 1.5·ATR with a consolidation ≤ 0.5·pole,
  rectangle equal levels ≤ 0.15·ATR with ≥ 3 touches, quasimodo ATR depth
  ≥ θ_depth.
* Spring/Upthrust are **E08 events** (§9.1 row: "E08 event; 3-bar return"):
  this module consumes E08's ``EV_WYK_005``/``EV_WYK_008`` output and never
  re-derives Wyckoff detection (one authority, no parallel detector).
* Deterministic, PIT-only: every detector sees bars up to and including the
  evaluated close; a future bar can never change a past call (Ch.9
  ``T_PATTERN``: "each family on its fixture — deterministic detection, no
  look-ahead").

No network access anywhere in this package (``apex.pattern.fibonacci`` is an
in-repo module per §9.5-15, and nothing here imports a transport library).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from apex.errors import WaveOutError, wave_out

CONTRACT_VERSION = "4.0.0"

# ---------------------------------------------------------------------------
# Governed bootstrap parameters (engine-local frozen defaults, precedent
# ISSUE-CP2-006: in-code frozen defaults + get_params(), no 7th YAML).
# ---------------------------------------------------------------------------

DEFAULT_THETA_EQ_ATR = 0.15       # equality/symmetry tolerance (double top/
                                  # bottom, rectangle) — §9.1 table
DEFAULT_THETA_SHOULDER_ATR = 0.25  # H&S shoulder equality — §9.1 table
DEFAULT_POLE_MIN_ATR = 1.5        # flag/pennant pole floor — §9.1 table
DEFAULT_FLAG_MAX_RATIO = 0.5      # flag height ≤ 0.5·pole — §9.1 table
DEFAULT_TRIANGLE_MIN_TOUCHES = 4  # ≥ 4 touches — §9.1 table
DEFAULT_RECT_MIN_TOUCHES = 3      # ≥ 3 touches — §9.1 table
DEFAULT_THETA_DEPTH_ATR = 1.0     # quasimodo ATR depth ≥ θ_depth (governed)
DEFAULT_EGAL_EPS = 1e-8
DEFAULT_SWING_LOOKBACK = 2       # fractal k used when anchors are not supplied

PATTERN_PARAMS: Dict[str, float] = {
    "theta_eq_atr": DEFAULT_THETA_EQ_ATR,
    "theta_shoulder_atr": DEFAULT_THETA_SHOULDER_ATR,
    "pole_min_atr": DEFAULT_POLE_MIN_ATR,
    "flag_max_ratio": DEFAULT_FLAG_MAX_RATIO,
    "triangle_min_touches": DEFAULT_TRIANGLE_MIN_TOUCHES,
    "rect_min_touches": DEFAULT_RECT_MIN_TOUCHES,
    "theta_depth_atr": DEFAULT_THETA_DEPTH_ATR,
    "eps": DEFAULT_EGAL_EPS,
    "swing_lookback": DEFAULT_SWING_LOOKBACK,
}


def get_params(overrides: Optional[Mapping[str, float]] = None) -> Dict[str, float]:
    """In-code governed defaults; an unknown key fails closed."""
    ov = dict(overrides or {})
    unknown = sorted(set(ov) - set(PATTERN_PARAMS))
    if unknown:
        raise ValueError(f"UNKNOWN_PATTERN_PARAM_QX: {unknown}")
    return {**PATTERN_PARAMS, **ov}


# ---------------------------------------------------------------------------
# AC.1 — Pattern Entity (registry contract)
# ---------------------------------------------------------------------------

AC1_MANDATORY_FIELDS: Tuple[str, ...] = (
    "pattern_id", "family", "formation_sequence", "required_context",
    "evidence_dependencies", "invalidation_rules", "provenance_class",
    "lifecycle_status", "setup_score_contribution_class",
    "template_reconciliation",
)
AC1_FAMILIES: Tuple[str, ...] = (
    "Structural", "Liquidity", "Smart Money", "Wyckoff", "Order Flow",
    "Volume", "Volatility", "Futures-Derivatives", "Composite",
    "Price Action",
)
PROVENANCE_CLASSES: Tuple[str, ...] = (
    "RESEARCH_ONLY", "ACTIVE", "DEPRECATED", "harmonic_demotion_round_2",
)
LIFECYCLE_STATES: Tuple[str, ...] = ("ACTIVE", "RESEARCH_ONLY", "DEPRECATED")
CONTRIBUTION_CLASSES: Tuple[str, ...] = (
    "s_i_component", "q_i_component", "convergence_weight", "advisory",
)


@dataclass(frozen=True)
class PatternEntity:
    """One AC.1 Pattern Entity record (10 mandatory + 3 optional fields)."""

    pattern_id: str
    family: str
    formation_sequence: str
    required_context: Tuple[Tuple[str, str, str], ...]   # (condition, class, engine)
    evidence_dependencies: Tuple[str, ...]
    invalidation_rules: Tuple[str, ...]
    provenance_class: str
    lifecycle_status: str
    setup_score_contribution_class: str
    template_reconciliation: str
    reference_implementation: Optional[str] = None
    historical_statistics: Optional[Mapping[str, Any]] = None
    revision_history: Optional[Tuple[str, ...]] = None

    def __post_init__(self) -> None:
        if not _PAT_ID_RE.match(self.pattern_id):
            raise ValueError(
                f"PATTERN_ID_QX: {self.pattern_id!r} is not PAT-<FAM>-<seq>"
            )
        if self.family not in AC1_FAMILIES:
            raise ValueError(
                f"PATTERN_FAMILY_QX: {self.family!r} outside the admitted "
                f"families {AC1_FAMILIES}"
            )
        if not self.evidence_dependencies:
            # AC.1 #5: "An orphan pattern — one with no mapped evidence
            # source — is rejected."
            raise ValueError("PATTERN_ORPHAN_QX: no evidence dependency mapped")
        for e in self.evidence_dependencies:
            if e not in tuple(f"E{i:02d}" for i in range(1, 13)):
                raise ValueError(
                    f"PATTERN_DEPENDENCY_QX: {e!r} is not a frozen engine E01..E12"
                )
        if self.provenance_class not in PROVENANCE_CLASSES:
            raise ValueError(f"PATTERN_PROVENANCE_QX: {self.provenance_class!r}")
        if self.lifecycle_status not in LIFECYCLE_STATES:
            raise ValueError(f"PATTERN_LIFECYCLE_QX: {self.lifecycle_status!r}")
        if self.setup_score_contribution_class not in CONTRIBUTION_CLASSES:
            raise ValueError(
                f"PATTERN_CONTRIBUTION_QX: {self.setup_score_contribution_class!r}"
            )
        if not self.invalidation_rules:
            raise ValueError("PATTERN_INVALIDATION_QX: rules are mandatory")
        for cond, cls, _eng in self.required_context:
            if cls not in ("REQUIRED", "OPTIONAL"):
                raise ValueError(
                    f"PATTERN_CONTEXT_CLASS_QX: {cls!r} not REQUIRED/OPTIONAL"
                )
        if self.lifecycle_status == "RESEARCH_ONLY" and \
                self.setup_score_contribution_class in (
                    "s_i_component", "q_i_component", "convergence_weight"):
            raise ValueError(
                "PATTERN_RESEARCH_SCORING_QX: a RESEARCH_ONLY pattern must not "
                "carry a scoring contribution class (Ch.9 §9.1 demotion: no "
                "evidence that may contribute to setup scoring)"
            )

    def to_pattern_evidence_row(self) -> Dict[str, Any]:
        """The Data Plane ``pattern_evidence`` materialization (AC.5 #2)."""
        return {
            "pattern_id": self.pattern_id,
            "family": self.family,
            "pattern_type": self.formation_sequence[:120],
            "formation_sequence": self.formation_sequence,
            "required_context": ";".join(
                f"{c}:{k}@{e}" for c, k, e in self.required_context),
            "evidence_dependencies": ",".join(self.evidence_dependencies),
            "invalidation_rules": ";".join(self.invalidation_rules),
            "provenance_class": self.provenance_class,
            "lifecycle_status": self.lifecycle_status,
            "setup_score_contribution_class": self.setup_score_contribution_class,
            "template_reconciliation": self.template_reconciliation,
            "reference_implementation": self.reference_implementation,
            "historical_statistics": (
                None if self.historical_statistics is None
                else dict(self.historical_statistics)),
            "revision_history": (
                None if self.revision_history is None
                else list(self.revision_history)),
            "confidence": None,
        }


import re as _re
_PAT_ID_RE = _re.compile(r"^PAT-[A-Z]{3}-\d{3}$")


def assert_scoring_admissible(entity: PatternEntity) -> None:
    """Gate against the legacy catalogue and the research-only rows.

    Only ``ACTIVE`` lifecycle entities with a scoring contribution class may
    feed setup scoring; a RESEARCH_ONLY row (the three demoted harmonics) is a
    hard ``WaveOutError`` — the demotion is an exclusion, not a warning.
    """
    if entity.setup_score_contribution_class == "advisory":
        raise wave_out(
            "pattern_advisory_scoring",
            f"PATTERN_ADVISORY_NO_SCORING::{entity.pattern_id}")
    if entity.lifecycle_status != "ACTIVE":
        raise wave_out(
            "pattern_research_only_scoring",
            f"PATTERN_RESEARCH_ONLY_NO_SCORING::{entity.pattern_id}")


# ---------------------------------------------------------------------------
# The 20-row frozen catalogue (Ch.9 §9.1) — legacy reference with the AC.1
# identifiers assigned here (an explicit row-level record is still required
# for operational admission, and this module produces exactly that record for
# the 17 rows it can back with an engine-mapped detector).
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CatalogueRow:
    name: str
    pattern_id: str
    family: str
    sequence: str
    invalidation: str
    provenance: str
    lifecycle_status: str
    engines: Tuple[str, ...]
    detector: Optional[str]        # detector function name in this module


CATALOGUE: Tuple[CatalogueRow, ...] = (
    CatalogueRow("Double Top", "PAT-STR-001", "Price Action",
                 "High1 -> Low -> High2 ~ High1 -> Breakdown Low",
                 "Close above High2 invalidates", "Price Action", "ACTIVE",
                 ("E01", "E04"), "detect_double_top"),
    CatalogueRow("Double Bottom", "PAT-STR-002", "Price Action",
                 "Low1 -> High -> Low2 ~ Low1 -> Breakout High",
                 "Close below Low2 invalidates", "Price Action", "ACTIVE",
                 ("E01", "E04"), "detect_double_bottom"),
    CatalogueRow("Head & Shoulders", "PAT-STR-003", "Price Action",
                 "Left Shoulder -> Head -> Right Shoulder -> Breakdown Neckline",
                 "Close above Right Shoulder invalidates", "Price Action",
                 "ACTIVE", ("E01", "E04"), "detect_head_and_shoulders"),
    CatalogueRow("Inverse H&S", "PAT-STR-004", "Price Action",
                 "Inverted Left -> Head -> Right -> Breakout Neckline",
                 "Close below Right invalidates", "Price Action", "ACTIVE",
                 ("E01", "E04"), "detect_inverse_head_and_shoulders"),
    CatalogueRow("Triangle Ascending", "PAT-STR-005", "Price Action",
                 "Higher Lows + Equal Highs -> Breakout High",
                 "Close below last Higher Low invalidates", "Price Action",
                 "ACTIVE", ("E01", "E04"), "detect_triangle_ascending"),
    CatalogueRow("Triangle Descending", "PAT-STR-006", "Price Action",
                 "Lower Highs + Equal Lows -> Breakdown Low",
                 "Close above last Lower High invalidates", "Price Action",
                 "ACTIVE", ("E01", "E04"), "detect_triangle_descending"),
    CatalogueRow("Triangle Symmetrical", "PAT-STR-007", "Price Action",
                 "Lower Highs + Higher Lows -> Breakout",
                 "Close beyond opposite side invalidates", "Price Action",
                 "ACTIVE", ("E01", "E04"), "detect_triangle_symmetrical"),
    CatalogueRow("Flag", "PAT-STR-008", "Price Action",
                 "Impulse -> Consolidation flag -> Continuation",
                 "Close beyond flag opposite invalidates", "Price Action",
                 "ACTIVE", ("E01", "E04"), "detect_flag"),
    CatalogueRow("Pennant", "PAT-STR-009", "Price Action",
                 "Impulse -> Pennant consolidation -> Continuation",
                 "Close beyond pennant opposite invalidates", "Price Action",
                 "ACTIVE", ("E01", "E04"), "detect_flag"),
    CatalogueRow("Quasimodo", "PAT-STR-010", "Price Action",
                 "Higher High -> Lower Low -> Higher Low -> Lower High",
                 "Structure break invalidates", "Price Action", "ACTIVE",
                 ("E01", "E04"), "detect_quasimodo"),
    CatalogueRow("Wolfe Wave", "PAT-STR-011", "Price Action",
                 "1-2-3-4-5 waves -> Target line 1-4",
                 "Close beyond wave 5 invalidates", "Price Action",
                 "RESEARCH_ONLY", ("E01", "E04"), None),
    CatalogueRow("Rising Wedge", "PAT-STR-012", "Price Action",
                 "Higher Highs + Higher Lows converging -> Breakdown",
                 "Close above the last Higher High invalidates", "Price Action",
                 "ACTIVE", ("E01", "E04"), "detect_rising_wedge"),
    CatalogueRow("Falling Wedge", "PAT-STR-013", "Price Action",
                 "Lower Highs + Lower Lows converging -> Breakout",
                 "Close below the last Lower Low invalidates", "Price Action",
                 "ACTIVE", ("E01", "E04"), "detect_falling_wedge"),
    CatalogueRow("Rectangle", "PAT-STR-014", "Price Action",
                 "Equal Highs + Equal Lows range -> Breakout in breakout direction",
                 "Close back inside the range after breakout invalidates",
                 "Price Action", "ACTIVE", ("E01", "E04"), "detect_rectangle"),
    CatalogueRow("Broadening", "PAT-STR-015", "Price Action",
                 "Higher Highs + Lower Lows diverging -> Reversal at boundary",
                 "Close beyond the opposite boundary invalidates",
                 "Price Action", "ACTIVE", ("E01", "E04"), "detect_broadening"),
    CatalogueRow("Three Drives", "PAT-HAR-001", "Composite",
                 "Drive1 -> Correction1 -> Drive2 -> Correction2 -> Drive3 "
                 "(Fibonacci symmetry between drives)",
                 "Close beyond the Drive3 extreme invalidates",
                 "Harmonic (research-only)", "RESEARCH_ONLY", ("E01",), None),
    CatalogueRow("Gartley", "PAT-HAR-002", "Composite",
                 "XA -> AB (0.618 retracement of XA) -> BC -> CD completion "
                 "at the potential reversal zone",
                 "Close beyond X invalidates", "Harmonic (research-only)",
                 "RESEARCH_ONLY", ("E01",), None),
    CatalogueRow("Bat", "PAT-HAR-003", "Composite",
                 "XA -> AB (0.382-0.5 retracement of XA) -> BC -> CD "
                 "completion at the PRZ (0.886 of XA)",
                 "Close beyond X invalidates", "Harmonic (research-only)",
                 "RESEARCH_ONLY", ("E01",), None),
    CatalogueRow("Spring", "PAT-WYC-001", "Wyckoff",
                 "Penetration below the range low -> Close back above the "
                 "range low within 3 bars",
                 "Close below the Spring low invalidates", "Wyckoff", "ACTIVE",
                 ("E08",), "from_e08_spring"),
    CatalogueRow("Upthrust", "PAT-WYC-002", "Wyckoff",
                 "Penetration above the range high -> Close back below the "
                 "range high",
                 "Close above the Upthrust high invalidates", "Wyckoff",
                 "ACTIVE", ("E08",), "from_e08_upthrust"),
)

# Research-only catalogue rows (Three Drives / Gartley / Bat are demoted at the
# Round-2 freeze; Wolfe Wave carries no operational tolerance row in §9.1 and
# is therefore not admitted with a detector).
RESEARCH_ONLY_PATTERNS: Tuple[str, ...] = tuple(
    r.pattern_id for r in CATALOGUE if r.lifecycle_status == "RESEARCH_ONLY")

CATALOGUE_BY_NAME: Dict[str, CatalogueRow] = {r.name: r for r in CATALOGUE}

# Families outside the medium scope of AC.3 (never admitted as detectors here).
EXCLUDED_FAMILIES_AC3: Tuple[str, ...] = ("Smart Money", "Wyckoff-PHASE",
                                          "Composite-CMX")

# The AC.3 non-runnable PAT-DER rows (excluded from APEX runtime).
EXCLUDED_PAT_DER: Tuple[str, ...] = ("PAT-DER-002", "PAT-DER-007", "PAT-DER-008")


def entity_for(row: CatalogueRow) -> PatternEntity:
    """Materialize one catalogue row as an AC.1 Pattern Entity record.

    Legacy rows do NOT acquire operational admission by appearing in the
    catalogue (AC.5 #1); this function builds the record that the Setup layer
    checks, and a row without a detector is registered advisory-only.
    """
    contribution = ("advisory" if row.detector is None else "s_i_component")
    lifecycle = row.lifecycle_status if contribution == "advisory" \
        else row.lifecycle_status
    if lifecycle == "RESEARCH_ONLY":
        contribution = "advisory"
    return PatternEntity(
        pattern_id=row.pattern_id, family=row.family,
        formation_sequence=row.sequence,
        required_context=(("volatility_regime", "REQUIRED", "E04"),
                          ("structure_state", "REQUIRED", "E01")),
        evidence_dependencies=row.engines,
        invalidation_rules=(row.invalidation,),
        provenance_class=("harmonic_demotion_round_2"
                          if "Harmonic" in row.provenance else
                          ("RESEARCH_ONLY" if lifecycle == "RESEARCH_ONLY"
                           else "ACTIVE")),
        lifecycle_status=lifecycle,
        setup_score_contribution_class=contribution,
        template_reconciliation=("AB.3 content template; §9.1 tolerance row"),
        reference_implementation=(
            f"apex.pattern.detect.{row.detector}" if row.detector else None),
    )


# ---------------------------------------------------------------------------
# Deterministic detectors (pure functions of CLOSED bars, PIT-only)
# ---------------------------------------------------------------------------

def swings(highs: Sequence[float], lows: Sequence[float], k: int = 2
           ) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """Fractal swing points: index ``i`` is a swing high iff
    ``highs[i] == max(highs[i-k:i+k+1])`` (and symmetrically for lows).

    Strictly local — a swing is only asserted once its ``k`` right-side bars
    are CLOSED, which is the no-look-ahead rule of ``T_PATTERN``.
    """
    n = len(highs)
    sh: List[Tuple[int, float]] = []
    sl: List[Tuple[int, float]] = []
    for i in range(k, n - k):
        window = range(i - k, i + k + 1)
        if highs[i] == max(highs[j] for j in window):
            sh.append((i, highs[i]))
        if lows[i] == min(lows[j] for j in window):
            sl.append((i, lows[i]))
    return sh, sl


def _ohlcv(bars: Sequence[Mapping[str, float]]
           ) -> Tuple[List[float], List[float], List[float]]:
    """Extract the (highs, lows, closes) view of a bar series.

    A bar is ``{o,h,l,c}`` (the E08 fixture convention, Ch.13 §8); a bar with
    ``h < l`` fails closed — a malformed candle is never silently absorbed
    (§2.1 Q_ohlc semantics).
    """
    highs, lows, closes = [], [], []
    for i, b in enumerate(bars):
        h, l = float(b["h"]), float(b["l"])
        if h < l:
            raise ValueError(
                f"PATTERN_BAR_QX: bar {i} has High < Low (QX INVALID)"
            )
        highs.append(h)
        lows.append(l)
        closes.append(float(b["c"]))
    return highs, lows, closes


def _swings_or(highs: Sequence[float], lows: Sequence[float], k: int,
               swings_in: Optional[Tuple[Sequence[Tuple[int, float]],
                                         Sequence[Tuple[int, float]]]]
               ) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """Use the caller's swing anchors when supplied, else derive them locally.

    Both paths are PIT-only: the anchors a caller passes must have been CLOSED
    (the Setup layer sources them from E01 structure events, never from a
    future bar), and the derived ones only assert a swing once its ``k``
    right-side bars are closed.
    """
    if swings_in is not None:
        sh, sl = swings_in
        return sorted((int(i), float(v)) for i, v in sh), \
               sorted((int(i), float(v)) for i, v in sl)
    return swings(highs, lows, k)


def _atr_or_raise(atr: float) -> float:
    if atr is None or atr != atr or atr <= 0:
        raise ValueError(
            "PATTERN_ATR_QX: a governed ATR is mandatory (no substitute ATR "
            "is ever fabricated — Ch.9 ATR-normalized family contract)"
        )
    return float(atr)


def _close_beyond(close: float, level: float, side: str, eps: float) -> bool:
    return close > level + eps if side == "UP" else close < level - eps


@dataclass(frozen=True)
class PatternHit:
    """Detection result: the pattern, its invalidation level and the swing
    anchors it was derived from (row-level evidence, never a bare boolean)."""

    pattern_id: str
    name: str
    direction: int                 # -1 / 0 / +1 (Ch.10 conflict law)
    index: int                     # bar index of the confirming close
    invalidation_level: float
    invalidation_side: str         # UP | DOWN ("close above/below X")
    anchors: Mapping[str, float] = field(default_factory=dict)
    strength: float = 0.0

    def to_evidence(self, *, symbol: str, timeframe: str, as_of: int,
                    snapshot_id: str, lineage: Sequence[str]) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "as_of": as_of,
            "direction": self.direction,
            "strength": self.strength,
            "invalidation": {"level": self.invalidation_level,
                             "side": self.invalidation_side},
            "anchors": dict(self.anchors),
            "snapshot_id": snapshot_id,
            "lineage": tuple(lineage),
            "contract_version": CONTRACT_VERSION,
        }


def detect_double_top(bars: Sequence[Mapping[str, float]], atr: float, *,
                      swing_anchor: Optional[Tuple[Sequence[Tuple[int, float]],
                                                   Sequence[Tuple[int, float]]]] = None,
                      params: Optional[Mapping[str, float]] = None) -> Optional[PatternHit]:
    """High1 → Low → High2 ≈ High1 → breakdown below the intervening low
    (§9.1 row 1; equality tolerance ``|H1−H2| ≤ 0.15·ATR``)."""
    p = get_params(params)
    a = _atr_or_raise(atr)
    highs, lows, closes = _ohlcv(bars)
    sh, sl = _swings_or(highs, lows, p["swing_lookback"], swing_anchor)
    for i in range(1, len(sh)):
        (i1, h1), (i2, h2) = sh[i - 1], sh[i]
        if abs(h1 - h2) > p["theta_eq_atr"] * a:
            continue
        between = [lows[j] for j in range(i1 + 1, i2)]
        if not between:
            continue
        pivot_low = min(between)
        for j in range(i2 + 1, len(closes)):
            if closes[j] < pivot_low - p["eps"]:
                return PatternHit(
                    "PAT-STR-001", "Double Top", -1, j, h2, "UP",
                    {"h1": h1, "h2": h2, "pivot_low": pivot_low},
                    strength=min(1.0, abs(h2 - pivot_low) / (2 * a)))
    return None


def detect_double_bottom(bars: Sequence[Mapping[str, float]], atr: float, *,
                         swing_anchor: Optional[Tuple[Sequence[Tuple[int, float]],
                                                      Sequence[Tuple[int, float]]]] = None,
                         params: Optional[Mapping[str, float]] = None) -> Optional[PatternHit]:
    p = get_params(params)
    a = _atr_or_raise(atr)
    highs, lows, closes = _ohlcv(bars)
    _sh, sl = _swings_or(highs, lows, p["swing_lookback"], swing_anchor)
    for i in range(1, len(sl)):
        (i1, l1), (i2, l2) = sl[i - 1], sl[i]
        if abs(l1 - l2) > p["theta_eq_atr"] * a:
            continue
        between = [highs[j] for j in range(i1 + 1, i2)]
        if not between:
            continue
        pivot_high = max(between)
        for j in range(i2 + 1, len(closes)):
            if closes[j] > pivot_high + p["eps"]:
                return PatternHit(
                    "PAT-STR-002", "Double Bottom", +1, j, l2, "DOWN",
                    {"l1": l1, "l2": l2, "pivot_high": pivot_high},
                    strength=min(1.0, abs(pivot_high - l2) / (2 * a)))
    return None


def _hsh_variant(bars, atr, *, inverse: bool, params=None, swing_anchor=None):
    p = get_params(params)
    a = _atr_or_raise(atr)
    highs, lows, closes = _ohlcv(bars)
    sh, sl = _swings_or(highs, lows, p["swing_lookback"], swing_anchor)
    pts = sh if not inverse else sl
    if len(pts) < 3:
        return None
    for i in range(len(pts) - 2):
        (i1, v1), (i2, v2), (i3, v3) = pts[i], pts[i + 1], pts[i + 2]
        head_is_extreme = (v2 > v1 and v2 > v3) if not inverse else (v2 < v1 and v2 < v3)
        if not head_is_extreme:
            continue
        if abs(v1 - v3) > p["theta_shoulder_atr"] * a:
            continue
        # Neckline = the troughs (H&S) / peaks (inverse) between the shoulders,
        # taken from the swing anchors that define the pattern (E01 structure
        # events on the Setup path; the locally derived swings otherwise).
        anchor_pts = sl if not inverse else sh
        between = [v for idx_, v in anchor_pts if i1 < idx_ < i3]
        if not between:
            between = ([min(lows[j] for j in range(i1, i2 + 1)),
                        min(lows[j] for j in range(i2, i3 + 1))]
                       if not inverse else
                       [max(highs[j] for j in range(i1, i2 + 1)),
                        max(highs[j] for j in range(i2, i3 + 1))])
        neck_vals = between
        neckline = sum(neck_vals) / 2.0
        for j in range(i3 + 1, len(closes)):
            broke = (closes[j] < neckline - p["eps"]) if not inverse \
                else (closes[j] > neckline + p["eps"])
            if broke:
                return PatternHit(
                    "PAT-STR-003" if not inverse else "PAT-STR-004",
                    "Head & Shoulders" if not inverse else "Inverse H&S",
                    -1 if not inverse else +1, j,
                    v3, "UP" if not inverse else "DOWN",
                    {"left": v1, "head": v2, "right": v3, "neckline": neckline},
                    strength=min(1.0, abs(v2 - neckline) / (3 * a)))
    return None


def detect_head_and_shoulders(bars, atr, *, params=None,
                              swing_anchor=None) -> Optional[PatternHit]:
    """LS → Head → RS → neckline break; shoulder equality ≤ 0.25·ATR."""
    return _hsh_variant(bars, atr, inverse=False, params=params,
                        swing_anchor=swing_anchor)


def detect_inverse_head_and_shoulders(bars, atr, *, params=None,
                                      swing_anchor=None) -> Optional[PatternHit]:
    return _hsh_variant(bars, atr, inverse=True, params=params,
                        swing_anchor=swing_anchor)


def _touch_count(vals: Sequence[float], level: float, atr: float, eps: float) -> int:
    return sum(1 for v in vals if abs(v - level) <= 0.15 * atr + eps)


def _triangle(bars, atr, *, kind: str, params=None, swing_anchor=None):
    """Ascending / descending / symmetrical: ≥ 4 touches of the boundary
    extrema, converging slopes, then a close beyond the flat side (§9.1)."""
    p = get_params(params)
    a = _atr_or_raise(atr)
    highs, lows, closes = _ohlcv(bars)
    sh, sl = _swings_or(highs, lows, p["swing_lookback"], swing_anchor)
    if len(sh) < 2 or len(sl) < 2:
        return None
    flat_level, flat_vals, other, side = (
        (max(v for _, v in sh), [v for _, v in sh], sl, "DOWN")
        if kind == "ASCENDING" else
        (min(v for _, v in sl), [v for _, v in sl], sh, "UP")
        if kind == "DESCENDING" else (None, [], [], "NONE"))
    if kind != "SYMMETRICAL":
        if _touch_count(flat_vals, flat_level, a, p["eps"]) < p["triangle_min_touches"]:
            return None
        other_level = other[-1][1]
        # ASCENDING = "Higher Lows + Equal Highs" → the sloping side rises;
        # DESCENDING = "Lower Highs + Equal Lows" → the sloping side falls.
        ovals = [v for _, v in other]
        converging = (all(x < y for x, y in zip(ovals, ovals[1:]))
                      if kind == "ASCENDING" else
                      all(x > y for x, y in zip(ovals, ovals[1:])))
        if not converging:
            return None
        for j in range(max(flat_vals and 1, 1), len(closes)):
            if _close_beyond(closes[j], flat_level,
                             "UP" if kind == "ASCENDING" else "DOWN", p["eps"]):
                return PatternHit(
                    "PAT-STR-005" if kind == "ASCENDING" else "PAT-STR-006",
                    f"Triangle {kind.title()}",
                    +1 if kind == "ASCENDING" else -1, j,
                    other_level, side,
                    {"boundary": flat_level, "last_other_swing": other_level},
                    strength=min(1.0, abs(flat_level - other_level) / (2 * a)))
        return None
    # symmetrical: lower highs + higher lows, close beyond either side
    hs = [v for _, v in sh]
    ls = [v for _, v in sl]
    if len(hs) < 2 or len(ls) < 2:
        return None
    if not (hs[-1] < hs[-2] and ls[-1] > ls[-2]):
        return None
    for j in range(len(closes) - 1, -1, -1):
        if closes[j] > hs[-1] + p["eps"]:
            return PatternHit("PAT-STR-007", "Triangle Symmetrical", +1, j,
                              ls[-1], "DOWN", {"last_high": hs[-1],
                                               "last_low": ls[-1]},
                              strength=min(1.0, (hs[-1] - ls[-1]) / (2 * a)))
        if closes[j] < ls[-1] - p["eps"]:
            return PatternHit("PAT-STR-007", "Triangle Symmetrical", -1, j,
                              hs[-1], "UP", {"last_high": hs[-1],
                                             "last_low": ls[-1]},
                              strength=min(1.0, (hs[-1] - ls[-1]) / (2 * a)))
    return None


def detect_triangle_ascending(bars, atr, *, params=None, swing_anchor=None):
    return _triangle(bars, atr, kind="ASCENDING", params=params,
                     swing_anchor=swing_anchor)


def detect_triangle_descending(bars, atr, *, params=None, swing_anchor=None):
    return _triangle(bars, atr, kind="DESCENDING", params=params,
                     swing_anchor=swing_anchor)


def detect_triangle_symmetrical(bars, atr, *, params=None, swing_anchor=None):
    return _triangle(bars, atr, kind="SYMMETRICAL", params=params,
                     swing_anchor=swing_anchor)


def detect_flag(bars, atr, *, direction: int, flag_bars: int = 6, params=None,
                pole_end_idx: Optional[int] = None) -> Optional[PatternHit]:
    """Pole ≥ 1.5·ATR; consolidation height ≤ 0.5·pole; continuation close
    beyond the flag's opposite edge (§9.1 row 8/9).

    The consolidation window is the ``flag_bars`` bars that end the series:
    ``pole_end_idx`` (default ``len − 1 − flag_bars``) marks the pole's last
    bar. A "close beyond flag opposite" is the continuation break on the
    *opposite* side of the consolidation (the flag slopes against the pole).
    """
    p = get_params(params)
    a = _atr_or_raise(atr)
    highs, lows, closes = _ohlcv(bars)
    if direction not in (-1, 0, 1) or direction == 0:
        raise ValueError("PATTERN_DIRECTION_QX: direction must be ±1")
    if len(closes) < flag_bars + 2:
        return None
    pole_end = (len(closes) - 1 - flag_bars) if pole_end_idx is None         else int(pole_end_idx)
    if pole_end < 1 or pole_end >= len(closes) - 1:
        return None
    pole_start = closes[0]
    pole = (closes[pole_end] - pole_start) if direction > 0 \
        else (pole_start - closes[pole_end])
    if pole < p["pole_min_atr"] * a - p["eps"]:
        return None
    start = pole_end + 1
    end = start + flag_bars            # the consolidation is flag_bars bars
    cons_hi = max(highs[start:end])
    cons_lo = min(lows[start:end])
    height = cons_hi - cons_lo
    if height > p["flag_max_ratio"] * pole + p["eps"]:
        return None
    opposite = cons_lo if direction > 0 else cons_hi
    side = "UP" if direction > 0 else "DOWN"
    for j in range(start, len(closes)):
        if _close_beyond(closes[j], opposite, side, p["eps"]):
            return PatternHit("PAT-STR-008", "Flag", direction, j,
                              cons_hi if direction > 0 else cons_lo,
                              "DOWN" if direction > 0 else "UP",
                              {"pole": pole, "cons_hi": cons_hi,
                               "cons_lo": cons_lo},
                              strength=min(1.0, pole / (4 * a)))
    return None


def detect_quasimodo(bars, atr, *, params=None, swing_anchor=None):
    """HH → LL → HL → LH (Q60-style stop hunt); depth ≥ θ_depth·ATR; a
    structure break (close below the HL) invalidates (§9.1)."""
    p = get_params(params)
    a = _atr_or_raise(atr)
    highs, lows, closes = _ohlcv(bars)
    sh, sl = _swings_or(highs, lows, p["swing_lookback"], swing_anchor)
    if len(sh) < 2 or len(sl) < 2:
        return None
    # find HH then a break of structure down with an HL that holds
    hh_candidates = [i for i in range(1, len(sh)) if sh[i][1] > sh[i - 1][1]]
    for i in hh_candidates:
        hh_idx, hh = sh[i]
        later_lows = [(j, v) for j, v in sl if j > hh_idx]
        if not later_lows:
            continue
        ll_idx, ll = min(later_lows, key=lambda t: t[1])
        if hh - ll < p["theta_depth_atr"] * a:
            continue
        after = [(j, v) for j, v in sl if j > ll_idx]
        higher_lows = [(j, v) for j, v in after if v > ll + p["eps"]]
        if not higher_lows:
            continue
        hl_idx, hl = higher_lows[0]
        later_highs = [(j, v) for j, v in sh if j > hl_idx]
        if not later_highs:
            continue
        lh_idx, lh = min(later_highs, key=lambda t: t[1])
        if lh >= hh:
            continue
        for j in range(lh_idx + 1, len(closes)):
            if closes[j] < hl - p["eps"]:
                return PatternHit("PAT-STR-010", "Quasimodo", -1, j, hl,
                                  "DOWN", {"hh": hh, "ll": ll, "hl": hl,
                                            "lh": lh},
                                  strength=min(1.0, (hh - ll) / (4 * a)))
    return None


def _wedge(bars, atr, *, rising: bool, params=None, swing_anchor=None):
    """Rising wedge: HH + HL converging → breakdown. Falling wedge: LH + LL
    converging → breakout (§9.1 rows 12/13)."""
    p = get_params(params)
    a = _atr_or_raise(atr)
    highs, lows, closes = _ohlcv(bars)
    sh, sl = _swings_or(highs, lows, p["swing_lookback"], swing_anchor)
    if len(sh) < 2 or len(sl) < 2:
        return None
    hs, ls = [v for _, v in sh], [v for _, v in sl]
    if rising:
        if not (hs[-1] > hs[-2] and ls[-1] > ls[-2]):
            return None
        if not (hs[-1] - ls[-1] < hs[-2] - ls[-2]):   # converging
            return None
        # "Higher Highs + Higher Lows converging -> Breakdown" (§9.1 row 12)
        level, direction = ls[-1], -1
        for j in range(len(closes) - 1, -1, -1):
            if closes[j] < level - p["eps"]:
                return PatternHit("PAT-STR-012", "Rising Wedge", direction, j,
                                  hs[-1], "UP",          # invalidation side
                                  {"last_high": hs[-1], "last_low": ls[-1]},
                                  strength=min(1.0, (hs[-1] - ls[-1]) / (2 * a)))
        return None
    if not (hs[-1] < hs[-2] and ls[-1] < ls[-2]):
        return None
    if not (hs[-1] - ls[-1] < hs[-2] - ls[-2]):
        return None
    # "Lower Highs + Lower Lows converging -> Breakout" (§9.1 row 13)
    level, direction = hs[-1], +1
    for j in range(len(closes) - 1, -1, -1):
        if closes[j] > level + p["eps"]:
            return PatternHit("PAT-STR-013", "Falling Wedge", direction, j,
                              ls[-1], "DOWN",           # invalidation side
                              {"last_high": hs[-1], "last_low": ls[-1]},
                              strength=min(1.0, (hs[-1] - ls[-1]) / (2 * a)))
    return None


def detect_rising_wedge(bars, atr, *, params=None, swing_anchor=None):
    return _wedge(bars, atr, rising=True, params=params,
                  swing_anchor=swing_anchor)


def detect_falling_wedge(bars, atr, *, params=None, swing_anchor=None):
    return _wedge(bars, atr, rising=False, params=params,
                  swing_anchor=swing_anchor)


def detect_rectangle(bars, atr, *, params=None, swing_anchor=None):
    """Equal highs + equal lows (≤0.15·ATR each), ≥3 touches, then a close
    outside; a close back inside invalidates (§9.1 rows 14 and tolerance)."""
    p = get_params(params)
    a = _atr_or_raise(atr)
    highs, lows, closes = _ohlcv(bars)
    sh, sl = _swings_or(highs, lows, p["swing_lookback"], swing_anchor)
    if len(sh) < 3 or len(sl) < 3:
        return None
    hi_level = sum(v for _, v in sh) / len(sh)
    lo_level = sum(v for _, v in sl) / len(sl)
    if _touch_count([v for _, v in sh], hi_level, a, p["eps"]) < p["rect_min_touches"]:
        return None
    if _touch_count([v for _, v in sl], lo_level, a, p["eps"]) < p["rect_min_touches"]:
        return None
    for j in range(len(closes) - 1, -1, -1):
        if closes[j] > hi_level + p["eps"]:
            return PatternHit("PAT-STR-014", "Rectangle", +1, j, lo_level,
                              "UP", {"hi": hi_level, "lo": lo_level},
                              strength=min(1.0, (hi_level - lo_level) / (3 * a)))
        if closes[j] < lo_level - p["eps"]:
            return PatternHit("PAT-STR-014", "Rectangle", -1, j, hi_level,
                              "DOWN", {"hi": hi_level, "lo": lo_level},
                              strength=min(1.0, (hi_level - lo_level) / (3 * a)))
    return None


def detect_broadening(bars, atr, *, params=None, swing_anchor=None):
    """HH + LL diverging → reversal at the boundary; a close beyond the
    opposite boundary invalidates (§9.1 row 15)."""
    p = get_params(params)
    a = _atr_or_raise(atr)
    highs, lows, closes = _ohlcv(bars)
    sh, sl = _swings_or(highs, lows, p["swing_lookback"], swing_anchor)
    if len(sh) < 2 or len(sl) < 2:
        return None
    hs, ls = [v for _, v in sh], [v for _, v in sl]
    if not (hs[-1] > hs[-2] and ls[-1] < ls[-2]):
        return None
    for j in range(len(closes) - 1, -1, -1):
        if closes[j] < hs[-1] - p["eps"]:
            return PatternHit("PAT-STR-015", "Broadening", -1, j, ls[-1], "UP",
                              {"last_high": hs[-1], "last_low": ls[-1]},
                              strength=min(1.0, (hs[-1] - ls[-1]) / (4 * a)))
    return None


# ---------------------------------------------------------------------------
# Spring / Upthrust — consumed from E08, never re-derived (Ch.9 §9.1)
# ---------------------------------------------------------------------------

def from_e08_spring(bars: Sequence[Mapping[str, float]], range_lo: float,
                    idx: int, atr: float, vol_ratio: float,
                    evr_value: float = 0.0, *,
                    sp_bars: int = 3) -> Optional[PatternHit]:
    """Spring: E08's ``detect_spring`` plus the 3-bar return clause, then the
    E08 invalidation ("Close below the Spring low invalidates")."""
    from apex.engines.e08_wyckoff import detect_spring, spring_recovered
    bar = bars[idx]
    if not detect_spring(bar["l"], range_lo, bar["c"], atr, vol_ratio,
                         evr_value):
        return None
    if not spring_recovered(list(bars), range_lo, idx, sp_bars):
        return None
    return PatternHit("PAT-WYC-001", "Spring", +1, idx, bar["l"], "DOWN",
                      {"range_lo": range_lo, "spring_low": bar["l"],
                       "penetration": range_lo - bar["l"]},
                      strength=min(1.0, max(0.0, vol_ratio - 1.0) / 2.0 + 0.3))


def from_e08_upthrust(bars: Sequence[Mapping[str, float]], range_hi: float,
                      idx: int, atr: float, vol_ratio: float,
                      evr_value: float = 0.0, **_kw) -> Optional[PatternHit]:
    """Upthrust: E08's ``detect_ut`` + close back inside; invalidation "Close
    above the Upthrust high". """
    from apex.engines.e08_wyckoff import detect_ut
    bar = bars[idx]
    if not detect_ut(bar["h"], range_hi, bar["c"], atr, vol_ratio):
        return None
    return PatternHit("PAT-WYC-002", "Upthrust", -1, idx, bar["h"], "UP",
                      {"range_hi": range_hi, "ut_high": bar["h"],
                       "penetration": bar["h"] - range_hi},
                      strength=min(1.0, max(0.0, vol_ratio - 1.0) / 2.0 + 0.3))


DETECTORS: Dict[str, Callable[..., Optional[PatternHit]]] = {
    "detect_double_top": detect_double_top,
    "detect_double_bottom": detect_double_bottom,
    "detect_head_and_shoulders": detect_head_and_shoulders,
    "detect_inverse_head_and_shoulders": detect_inverse_head_and_shoulders,
    "detect_triangle_ascending": detect_triangle_ascending,
    "detect_triangle_descending": detect_triangle_descending,
    "detect_triangle_symmetrical": detect_triangle_symmetrical,
    "detect_flag": detect_flag,
    "detect_quasimodo": detect_quasimodo,
    "detect_rising_wedge": detect_rising_wedge,
    "detect_falling_wedge": detect_falling_wedge,
    "detect_rectangle": detect_rectangle,
    "detect_broadening": detect_broadening,
    "from_e08_spring": from_e08_spring,
    "from_e08_upthrust": from_e08_upthrust,
}


def is_invalidated(hit: PatternHit, close: float) -> bool:
    """The §9.1 invalidation rule of the hit's own row, evaluated on a later
    close. Invalidation never re-permits: it is a removal, not a reversal."""
    return _close_beyond(close, hit.invalidation_level, hit.invalidation_side,
                         get_params()["eps"])


def detect_all(bars: Sequence[Mapping[str, float]], atr: float, *,
               params: Optional[Mapping[str, float]] = None) -> Dict[str, Any]:
    """Run every admitted detector on the series and return the hits keyed by
    pattern id (T_PATTERN battery entry point). Research-only rows are never
    run — they have no detector and must produce nothing."""
    out: Dict[str, PatternHit] = {}
    _ohlcv(bars)                      # validate every bar once, up front
    for row in CATALOGUE:
        if row.lifecycle_status != "ACTIVE" or row.detector is None:
            continue
        if row.engines != ("E01", "E04"):
            continue                     # E08-backed rows run via their own API
        fn = DETECTORS[row.detector]
        if row.detector in ("detect_flag",):
            for d in (+1, -1):
                hit = fn(bars, atr, direction=d, params=params)
                if hit is not None:
                    out[hit.pattern_id] = hit
                    break
            continue
        hit = fn(bars, atr, params=params)
        if hit is not None:
            out[hit.pattern_id] = hit
    return {"hits": out,
            "n_admitted_rows": sum(
                1 for r in CATALOGUE if r.lifecycle_status == "ACTIVE"
                and r.detector is not None),
            "n_run_here": sum(1 for r in CATALOGUE if r.lifecycle_status ==
                             "ACTIVE" and r.detector is not None
                             and r.engines == ("E01", "E04")),
            "contract_version": CONTRACT_VERSION}


__all__ = [
    "AC1_FAMILIES", "AC1_MANDATORY_FIELDS", "CATALOGUE", "CATALOGUE_BY_NAME",
    "CONTRACT_VERSION", "CONTRIBUTION_CLASSES", "DETECTORS",
    "EXCLUDED_PAT_DER", "LIFECYCLE_STATES", "PROVENANCE_CLASSES",
    "PatternEntity", "PatternHit", "RESEARCH_ONLY_PATTERNS",
    "assert_scoring_admissible", "detect_all", "detect_broadening",
    "detect_double_bottom", "detect_double_top", "detect_falling_wedge",
    "detect_flag", "detect_head_and_shoulders",
    "detect_inverse_head_and_shoulders", "detect_quasimodo",
    "detect_rectangle", "detect_rising_wedge", "detect_triangle_ascending",
    "detect_triangle_descending", "detect_triangle_symmetrical",
    "entity_for", "from_e08_spring", "from_e08_upthrust", "get_params",
    "is_invalidated", "swings",
]
