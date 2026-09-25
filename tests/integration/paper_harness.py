"""Shared PAPER runtime builder.

Not a pytest plugin and not a conftest. Nothing here is autouse, and nothing
here sets ``APEX_ENV``. Unit tests that need the builder define their own
fixture and call ``build_harness``.
"""

from __future__ import annotations

from typing import Any


async def build_harness(tmp_path: Any, **runtime_kwargs: Any) -> Any:
    from apex.bus import EventBus
    from apex.config import Config
    from apex.data_catalog.store import sqlite_store as ss
    from apex.ledger import store as LS
    from apex.ops import paper_loop as PL
    from apex.scheduler import clock as C
    from tests.integration.test_ops_paper_loop import (
        START, SYMBOL, TF, FakeAdapter, Harness, LedgerClock, seed_setup,
    )

    store = ss.SQLiteStore(str(tmp_path / "apex.sqlite3"))
    await store.open()
    ledger = LS.LedgerWriter(store, clock=LedgerClock())
    await ledger.initialize()
    await ledger.start()
    clock = C.FixtureClock(START)
    adapter = FakeAdapter()
    bus = EventBus()
    bus.start()
    notifications: list = []

    async def notifier(text: str) -> dict:
        notifications.append(text)
        return {"sent": True}

    await seed_setup(store, "setup-0001")
    runtime_kwargs.setdefault("cells", [C.BundleCell(SYMBOL, TF)])
    runtime_kwargs["notifier"] = notifier
    runtime = PL.PaperRuntime(
        config=Config(), store=store, ledger=ledger, bus=bus,
        adapter=adapter, clock=clock, environment="PAPER",
        **runtime_kwargs)
    await runtime.boot(drift_seconds=0.0)
    return Harness(store, ledger, bus, clock, adapter, runtime, notifications)
