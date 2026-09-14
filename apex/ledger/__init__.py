"""APEX_GEN5 ledger package (Ch.16 L16757-16760, L16918-16930; AI.7 "Single
ledger writer" L18715; AI.8 ledger-write idempotency L18754).

Normative tree file (S9.5-10): ``apex/ledger/store.py`` -- the append-only,
hash-chained ledger with EXACTLY ONE writer; every execution-FSM state
mutation passes through that one writer queue (Ch.23 L18253-18260).
"""
