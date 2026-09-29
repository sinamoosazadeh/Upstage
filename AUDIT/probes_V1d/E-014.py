"""V1d probe E-014 — is the duplicate-submission guarantee atomic?
Two coroutines submit the SAME intent_id concurrently against the REAL
ToobitAdapter. The transport is an in-memory gate: it blocks until both
coroutines are inside _execute (i.e. both have PASSED the _duplicates check),
then answers both. No network, no repo file modified."""
import asyncio
import os
import sys

os.environ.setdefault("APEX_ENV", "PAPER")
os.environ.setdefault("APEX_ALLOW_SIGNED", "1")
os.environ.setdefault("TOOBIT_API_KEY", "TEST_KEY_CP7")
os.environ.setdefault("TOOBIT_API_SECRET", "TEST_SECRET_CP7")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apex.config import Config
from apex.execution.toobit_adapter import ToobitAdapter

UTC = lambda: "2026-01-01T00:00:00.000Z"  # noqa: E731

calls = []
entered = asyncio.Event()


class GatedTransport:
    """Blocks the FIRST call until the second coroutine has also entered the
    transport — i.e. both passed the _duplicates check."""

    def __init__(self) -> None:
        self.first = True

    async def __call__(self, method, url, query, headers):
        calls.append(query)
        if self.first:
            self.first = False
            # yield control until the other submit is also inside the transport
            await asyncio.sleep(0.05)
        return {"http_status": 200,
                "body": {"code": 0, "msg": "success",
                         "data": {"orderId": f"90000{len(calls)}",
                                  "clientOrderId": "i-race",
                                  "status": "NEW"}}}


async def main() -> None:
    adapter = ToobitAdapter(config=Config(), transport=GatedTransport(),
                            utc_now=UTC, clock=lambda: 1000.0)
    common = dict(symbol="BTCUSDT", timeframe="1h", direction="LONG",
                  quantity="0.1", price="100")
    r1, r2 = await asyncio.gather(
        adapter.submit_order(intent_id="i-race", **common),
        adapter.submit_order(intent_id="i-race", **common))
    print("transport invocations for intent i-race:", len(calls))
    print("result1: ok=%s outcome=%s order_id=%s cached=%s attempts=%d" %
          (r1.ok, r1.outcome, r1.order_id, r1.cached, len(r1.attempts)))
    print("result2: ok=%s outcome=%s order_id=%s cached=%s attempts=%d" %
          (r2.ok, r2.outcome, r2.order_id, r2.cached, len(r2.attempts)))
    print("distinct venue order ids issued:",
          sorted({r1.order_id, r2.order_id}))
    # a THIRD submit after both completed hits the cache (this part works):
    r3 = await adapter.submit_order(intent_id="i-race", **common)
    print("third submit (sequential): cached=%s new_transport_calls=%d" %
          (r3.cached, len(calls) - 2))
    print("audit entries result_source:",
          [a.result_source for a in adapter.audit_trail()])

    # --- venue-side view: same race against the repository's real fake
    # --- responder (which books orders and flags duplicate submissions).
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tests"))
    from fake_toobit_responder import FakeToobitResponder

    class SlowFake(FakeToobitResponder):
        async def __call__(self, method, url, query, headers):
            await asyncio.sleep(0.05)      # widen the window deterministically
            return await super().__call__(method, url, query, headers)

    responder = SlowFake()
    adapter2 = ToobitAdapter(config=Config(), transport=responder,
                             utc_now=UTC, clock=lambda: 1000.0)
    a, b = await asyncio.gather(
        adapter2.submit_order(intent_id="i-race-2", **common),
        adapter2.submit_order(intent_id="i-race-2", **common))
    posts = responder.calls_to("/api/v1/futures/order", "POST")
    booked = responder.orders.get("i-race-2", {})
    print("venue POSTs for i-race-2:", len(posts),
          "| venue flagged duplicate_submission:",
          booked.get("duplicate_submission"),
          "| cached flags:", a.cached, b.cached)


if __name__ == "__main__":
    asyncio.run(main())
