"""APEX_GEN5 — Phase 2 · CP-8 OPS hardening (Ch.17 §17.1 ops rows, Ch.23
safeguards, AI.9 fail-closed/fallback, AI.13 G-RESTORE-001).

Modules
-------
- :mod:`apex.ops.watchdog` — heartbeat monitoring with the 3-miss escalation,
  the AI.9 fail-closed entry/drive logic and the **send-only Gmail channel**:
  CRITICAL-only, structurally isolated from Telegram, and the only place that
  ever holds an independent-channel credential.
- :mod:`apex.ops.backup`  — SQLite backup + restore drill (T-RESTORE-001),
  RTO ≤ 30 min / RPO ≤ 5 min, hash-chain validation before resumption, the
  storage floor/alert checks and the refusal to claim encryption the SBOM
  cannot provide.

CONTRACT_VERSION 4.0.0.
"""

from __future__ import annotations

CONTRACT_VERSION = "4.0.0"

__all__ = ["CONTRACT_VERSION"]
