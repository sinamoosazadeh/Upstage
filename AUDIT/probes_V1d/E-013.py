"""V1d probe E-013 — does `extra_params` override validated wire fields?
READ-ONLY verification of the REAL ToobitAdapter with the repository's
FakeToobitResponder transport (in-memory, no network)."""
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

    # 1) The only production caller shape: fsm.place_protection sends ONLY a
    #    TIF extra (apex/execution/fsm.py:722) — this must keep working.
    ok_tif = await adapter.submit_order(
        intent_id="i-stop-tif", symbol="BTCUSDT", timeframe="1h",
        direction="LONG", quantity="0.1", price="99", phase="flatten",
        kind="stop", reduce_only=True, extra_params={"timeInForce": "GTC"})
    sent_tif = responder.calls_to("/api/v1/futures/order", "POST")[-1].params
    print("1) production TIF extra  -> ok=%s classification=%s" %
          (ok_tif.ok, ok_tif.classification))
    print("   sent:", {k: sent_tif[k] for k in
                       ("type", "quantity", "price", "reduceOnly", "timeInForce")})

    # 2) A validated LIMIT/GTC reduce-only target order, then the SAME call
    #    with extra_params overriding protected fields. Validation runs BEFORE
    #    `params.update(extra_params)` (toobit_adapter.py:430-470), so the
    #    overrides reach the wire unvalidated.
    good = await adapter.submit_order(
        intent_id="i-target-good", symbol="BTCUSDT", timeframe="1h",
        direction="LONG", quantity="0.1", price="103", phase="flatten",
        kind="target", reduce_only=True)
    sent_good = responder.calls_to("/api/v1/futures/order", "POST")[-1].params
    print("2) valid target          -> ok=%s outcome=%s" % (good.ok, good.outcome))
    print("   sent:", {k: sent_good[k] for k in
                       ("type", "quantity", "price", "reduceOnly", "timeInForce")})

    bad = await adapter.submit_order(
        intent_id="i-target-bad", symbol="BTCUSDT", timeframe="1h",
        direction="LONG", quantity="0.1", price="103", phase="flatten",
        kind="target", reduce_only=True,
        extra_params={"type": "MARKET",          # forbidden order type (Ch.16 L16895)
                      "quantity": "999",          # bypasses quantize/min-notional
                      "reduceOnly": "false",      # strips the reduce-only flag
                      "side": "BUY_OPEN",         # flips SELL_CLOSE -> BUY_OPEN
                      "clientOrderId": "i-evil",  # replaces the intent identity
                      "leverage": "125"})         # bypasses the min-over-caps law
    sent_bad = responder.calls_to("/api/v1/futures/order", "POST")[-1].params
    print("3) same call + extras   -> ok=%s outcome=%s" % (bad.ok, bad.outcome))
    print("   sent:", dict(sorted(sent_bad.items())))

    print("4) venue recorded clientOrderId:", "i-evil" in responder.orders,
          "| adapter-visible intent was i-target-bad")

    # 3) order_type="MARKET" passed directly IS refused — proving the bypass
    #    is specific to the extra_params path.
    try:
        await adapter.submit_order(
            intent_id="i-mkt", symbol="BTCUSDT", timeframe="1h",
            direction="LONG", quantity="0.1", price="100", order_type="MARKET")
        print("5) direct order_type=MARKET: ACCEPTED (unexpected)")
    except Exception as exc:
        print("5) direct order_type=MARKET refused:", type(exc).__name__, exc)


if __name__ == "__main__":
    asyncio.run(main())
