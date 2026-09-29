"""V1e E-007 — the real adapter's duplicate cache and actual manager exit kind.
No Config/env lookup, network, data directory or operational endpoint."""
import asyncio
import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from fake_toobit_responder import FakeToobitResponder, TEST_API_KEY, TEST_API_SECRET
from apex.execution.toobit_adapter import ToobitAdapter
from apex.execution.toobit_map import ToobitMapError

CFG = SimpleNamespace(allow_signed=True, toobit_api_key=TEST_API_KEY,
                      toobit_api_secret=TEST_API_SECRET, apex_env="PAPER")
ISO = "2026-01-01T00:00:00.000Z"

async def main():
    responder = FakeToobitResponder(api_key=TEST_API_KEY, api_secret=TEST_API_SECRET)
    adapter = ToobitAdapter(config=CFG, transport=responder, utc_now=lambda: ISO,
                            clock=lambda: 1000.0)
    first = await adapter.submit_order(intent_id="i-e007", symbol="BTCUSDT", timeframe="1h",
                                       direction="LONG", quantity="0.2", price="100", leverage=4.0)
    cached = await adapter.submit_order(intent_id="i-e007", symbol="BTCUSDT", timeframe="1h",
                                        direction="LONG", quantity="0.2", price="100", leverage=4.0)
    print("cache", first.outcome, cached.outcome, cached.cached, cached.error_code,
          "posts", len([c for c in responder.calls if c.method == "POST"]))
    try:
        await adapter.submit_order(intent_id="i-e007-exit", symbol="BTCUSDT", timeframe="1h",
                                   direction="LONG", quantity="0.2", price="99",
                                   phase="flatten", kind="exit", reduce_only=True)
    except ToobitMapError as exc:
        print("manager_exit_kind", exc.reason,
              "transport_posts_after_exit_attempt", len([c for c in responder.calls if c.method == "POST"]))

asyncio.run(main())
