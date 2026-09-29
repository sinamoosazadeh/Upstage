"""V1d probe E-022 — the order-response cache is keyed ONLY by intent_id
(client_order_id): no input_hash, no TTL, no code_version. A SECOND submit
with the SAME id but a DIFFERENT economic payload returns the FIRST order's
receipt (ok=True, cached=True) without any transport call. READ-ONLY
verification with the REAL ToobitAdapter + repository FakeToobitResponder."""
import asyncio
import os
import sys

os.environ.setdefault("APEX_ENV", "PAPER")
os.environ.setdefault("APEX_ALLOW_SIGNED", "1")
os.environ.setdefault("TOOBIT_API_KEY", "TEST_KEY_CP7")
os.environ.setdefault("TOOBIT_API_SECRET", "TEST_SECRET_CP7")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tests"))

from apex.config import Config
from apex.execution.toobit_adapter import ToobitAdapter
from fake_toobit_responder import FakeToobitResponder

UTC = lambda: "2026-01-01T00:00:00.000Z"  # noqa: E731


async def main() -> None:
    responder = FakeToobitResponder()
    adapter = ToobitAdapter(config=Config(), transport=responder,
                            utc_now=UTC, clock=lambda: 1000.0)

    first = await adapter.submit_order(
        intent_id="i-collision", symbol="BTCUSDT", timeframe="1h",
        direction="LONG", quantity="0.1", price="100")
    posts_after_first = len(responder.calls_to("/api/v1/futures/order", "POST"))
    print("1) LONG 0.1 @100  -> ok=%s outcome=%s order_id=%s cached=%s "
          "error_code=%s" % (first.ok, first.outcome, first.order_id,
                             first.cached, first.error_code))

    # SAME intent id, COMPLETELY different economic payload
    second = await adapter.submit_order(
        intent_id="i-collision", symbol="BTCUSDT", timeframe="1h",
        direction="SHORT", quantity="1", price="200")
    posts_after_second = len(responder.calls_to("/api/v1/futures/order", "POST"))
    print("2) SHORT 1 @200 (same id) -> ok=%s outcome=%s order_id=%s "
          "cached=%s error_code=%s" % (second.ok, second.outcome,
                                       second.order_id, second.cached,
                                       second.error_code))
    print("   new POSTs for the changed request:", posts_after_second -
          posts_after_first)
    print("   side recorded by the venue for i-collision:",
          responder.orders["i-collision"]["side"],
          responder.orders["i-collision"]["origQty"],
          responder.orders["i-collision"]["price"])
    print("   the changed request's side (SHORT) was NEVER sent; the receipt "
          "says ok=True")

    # what the cache actually stores (key + AdapterResult fields)
    state = adapter.state
    print("3) registry keys:", state.known_client_order_ids,
          "| duplicate entry fields (input_hash? ttl? code_version?):",
          sorted(f for f in ("input_hash", "ttl", "code_version",
                             "created_at")
                 if hasattr(adapter._duplicates["i-collision"], f)) or
          "NONE of them — only the AdapterResult")

    # a genuinely identical retry also returns the cached receipt (lawful)
    third = await adapter.submit_order(
        intent_id="i-collision", symbol="BTCUSDT", timeframe="1h",
        direction="LONG", quantity="0.1", price="100")
    print("4) identical retry -> ok=%s cached=%s error_code=%s new_POSTs=%d" %
          (third.ok, third.cached, third.error_code,
           len(responder.calls_to("/api/v1/futures/order", "POST")) -
           posts_after_second))

    # what the FSM would do with the cached ACKNOWLEDGED outcome
    from apex.execution import fsm as F
    from types import MappingProxyType
    machine = F.ExecutionFSM(environment="PAPER")
    await machine.advance("SUBMIT_ORDER")
    applied = await machine.apply_adapter_result(second)
    print("5) FSM applying the cached result of the CHANGED request:",
          applied)


if __name__ == "__main__":
    asyncio.run(main())
