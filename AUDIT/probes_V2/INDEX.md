# V2 probe manifest

Each numbered `.py` file is an executable probe using repository code. The matching `.out` file is its captured raw stdout/stderr. Temporary SQLite files are created under `/tmp` by the probes and removed before exit.

- D-001 through D-031: row probes and raw outputs.
- D-008-EQP.py / D-008-EQP.out: `EXPLAIN QUERY PLAN` comparison with and without `idx_mo_sym_tf_open` and `idx_pit_scope_asof`.
- `probe_impl.py`: shared implementation imported by the numbered wrappers.
- `pytest-focused.out`: raw focused pytest result used as regression evidence.

No probe reads `data/`, `.env`, secrets, real venue credentials, Telegram, or a device.
