"""APEX_GEN5 Decision Engine package (Ch.12 + Ch.14; CP-6).

Ranking and proposal only: it proposes, it does not veto, and it never issues
an order (Ch.14 heading; AF.1 authority chain).
"""

from apex.decision.pipeline import (  # noqa: F401
    ARBITRATION_REASON_FIELDS,
    INELIGIBLE_FAMILIES,
    MIN_RR,
    NO_TRADE,
    PORTFOLIO_PROPOSAL_FIELDS,
    StrategyProposal,
    TRADE,
    DecisionError,
    arbitrate,
    build_proposal,
    composite_rank_score,
    economic_utility,
    eligibility,
    eu_dollar,
    family_status_ok,
    governed_limits,
    generate_candidates,
    rank,
    regime_window_ok,
    select,
    slippage_model,
    units_of_r,
)
