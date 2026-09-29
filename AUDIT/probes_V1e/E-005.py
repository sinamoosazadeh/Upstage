"""V1e E-005 — exercise the real adapter cache marker and the actual exit
submission seam. Temporary SQLite; repository fake venue only; no Config/env lookup."""
import asyncio
import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from fake_toobit_responder import FakeToobitResponder, TEST_API_KEY, TEST_API_SECRET
from apex.execution.fsm import ExecutionFSM
from apex.execution.toobit_adapter import ToobitAdapter
from apex.execution.toobit_map import ToobitMapError

CFG = SimpleNamespace(allow_signed=True, toobit_api_key=TEST_API_KEY,
                      toobit_api_secret=TEST_API_SECRET, apex_env="PAPER")
ISO = "2026-01-01T00:00:00.000Z"

async def main():
    responder = FakeToobitResponder(api_key=TEST_API_KEY, api_secret=TEST_API_SECRET)
    adapter = ToobitAdapter(config=CFG, transport=responder, utc_now=lambda: ISO,
                            clock=lambda: 1000.0)
    first = await adapter.submit_order(intent_id="i-e005-cache", symbol="BTCUSDT",
                                       timeframe="1h", direction="LONG", quantity="0.2",
                                       price="100", leverage=4.0, timestamp_utc=ISO)
    cached = await adapter.submit_order(intent_id="i-e005-cache", symbol="BTCUSDT",
                                        timeframe="1h", direction="LONG", quantity="0.2",
                                        price="100", leverage=4.0, timestamp_utc=ISO)
    machine = ExecutionFSM(intent_id="i-e005-cache", adapter=adapter,
                           utc_now=lambda: ISO, clock=lambda: 1000.0)
    await machine.advance("SUBMIT_ORDER")
    applied = await machine.apply_adapter_result(cached)
    print("first", first.outcome, first.cached, "cached", cached.outcome, cached.cached,
          cached.error_code, "post_count", len([c for c in responder.calls if c.method == "POST"]))
    print("cached_apply_state", machine.state, "duplicate_exposed", "duplicate" in applied,
          "reconcile_required", applied["reconcile_required"])
    try:
        await adapter.submit_order(intent_id="i-e005-exit", symbol="BTCUSDT",
                                   timeframe="1h", direction="LONG", quantity="0.1",
                                   price="99", phase="flatten", kind="exit",
                                   reduce_only=True, timestamp_utc=ISO)
    except ToobitMapError as exc:
        print("actual_exit_exception", exc.reason)

asyncio.run(main())
