"""APEX_GEN5 — Phase 2 · CP-8 RESEARCH PLANE (Ch.17 §17.1, Ch.18, Ch.20).

This package is the research plane of the frozen blueprint. It is the ONLY
place where governed parameters may be *proposed*; it never places orders,
never edits the 14 hard vetoes, and never writes a live ``params/*.yaml``
(Ch.18 W.5 RED LINE + GC-D7 / G6 Wave-Out item "optimizer writing live yaml").

Modules
-------
- :mod:`apex.research.proxies`    — Ch.20 liquidity proxy layer: the 38-concept
  registry (AA.2/AA.3/AA.4), the six formal rejections (AA.5) and the
  formula-bearing proxies (B01, B02, B03, B04, B06, B07, B08, B10, D01, D02,
  A21, A22).
- :mod:`apex.research.governance` — Ch.17 SL-12 parameter governance service:
  the four parameter classes, the three resolution tiers, the governed-default
  register, the constrained-update projection ``θ′ = Π_[L,U](θ + Δ)``, the
  change-proposal protocol, the EC register, the sensitivity-removal criterion
  and the RED LINE package validator.
- :mod:`apex.research.backtest`   — Ch.18 §18.1/§18.4 deterministic replay
  engine: metrics, walk-forward split, Monte-Carlo, stress battery.
- :mod:`apex.research.optimizer`  — Ch.18 W.1–W.4/W.8 dual optimizer with
  exhaustive grids, checkpointing, the 03:00–05:00 UTC window and continuous
  run mode; suggestions land in ``apex/research/params_suggestions/`` only.
- :mod:`apex.research.promotion`  — Ch.18 W.5 + Z.1–Z.9 promotion gate:
  WFO criteria, family-pool Wilson gate, absolute floor, Bayesian shrinkage,
  SPRT live monitor, deflated Sharpe and PBO.
- :mod:`apex.research.adapter_conformance` — T-AD-001/T-AD-002 harness for the
  read-only v2/v3 → v4.0.0 adapters (ADR-P2-009: no fabricated legacy data).
- :mod:`apex.research.bootstrap`  — Ch.18 W.6 first-run bootstrap runner
  (three phases, persistent checkpoints, pause/resume, hardware preflight).

Contract version: 4.0.0 (matches every runtime module of Phase 2).
"""

from __future__ import annotations

CONTRACT_VERSION = "4.0.0"

__all__ = ["CONTRACT_VERSION"]
