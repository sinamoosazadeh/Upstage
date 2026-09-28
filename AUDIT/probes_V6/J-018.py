"""V6 probe J-018: two DIFFERENT intents with IDENTICAL content
(symbol/side/qty/price) both reach the venue — AI.8's content order_hash
(symbol||side||qty||price||timestamp, TTL 60 s) is NOT implemented; the
adapter's dedup cache is keyed by intent_id only (Ch.16/D50). Also: the
Ch.16 idempotency key appears only in the audit trail, not the HTTP query.
Uses the repo's own FakeToobitResponder (no network).
"""
import asyncio
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

from fake_toobit_responder import FakeToobitResponder
from apex.config import Config
from apex.execution.toobit_adapter import ToobitAdapter

async def main():
    import os
    os.environ["APEX_ENV"] = "PAPER"          # probe-only, in-process
    os.environ["APEX_ALLOW_SIGNED"] = "1"
    os.environ["TOOBIT_API_KEY"] = "TEST_KEY_CP7"
    os.environ["TOOBIT_API_SECRET"] = "TEST_SECRET_CP7"
    responder = FakeToobitResponder(api_key="TEST_KEY_CP7",
                                    api_secret="TEST_SECRET_CP7",
                                    balance="10000")
    adapter = ToobitAdapter(config=Config(), transport=responder)

    r1 = await adapter.submit_order(intent_id="i-aaaaaaaaaaaaaaaaaaaaaaaa",
                                    symbol="BTCUSDT", timeframe="15m",
                                    direction="LONG", quantity=1, price=60000,
                                    order_type="LIMIT")
    r2 = await adapter.submit_order(intent_id="i-bbbbbbbbbbbbbbbbbbbbbbbb",
                                    symbol="BTCUSDT", timeframe="15m",
                                    direction="LONG", quantity=1, price=60000,
                                    order_type="LIMIT")
    print("submit #1:", r1.outcome, r1.business_code,
          "| order_id:", r1.order_id)
    print("submit #2 (same content, different intent):", r2.outcome,
          r2.business_code, "| order_id:", r2.order_id)
    posts = [c for c in responder.calls if c.method == "POST"]
    print("venue POSTs recorded:", len(posts))
    for c in posts:
        print("   POST", c.path, "| clientOrderId:",
              c.params.get("clientOrderId"), "| signed:", c.signature_ok)
    print("distinct clientOrderIds:", len({c.params.get("clientOrderId")
                                           for c in posts}))
    print()
    print("AI.8 order_hash would be identical for both submits:",
          "same symbol/side/qty/price -> one hash")
    # where does the Ch.16 key live?
    for c in posts:
        has_key = any("idempoten" in k for k in c.params)
        print("idempotency key in HTTP query params:", has_key)
    print("Ch.16 key recorded in adapter attempt audit trail:",
          all(any(getattr(a, "idempotency_key", None)
                  for a in (r1.attempts, r2.attempts)[i]) for i in range(2)))
    # duplicate intent (control): same intent twice -> cached, no resubmit
    r3 = await adapter.submit_order(intent_id="i-aaaaaaaaaaaaaaaaaaaaaaaa",
                                    symbol="BTCUSDT", timeframe="15m",
                                    direction="LONG", quantity=1, price=60000,
                                    order_type="LIMIT")
    posts_after = [c for c in responder.calls if c.method == "POST"]
    print()
    print("control: repeat SAME intent -> outcome:", r3.outcome,
          "| venue POSTs still:", len(posts_after),
          "| result_source:", getattr(r3, "result_source", None))

asyncio.run(main())
