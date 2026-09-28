"""Probe the fake transport's auth rejection and shared HMAC oracle; no network."""
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlencode

root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root), str(root / "tests")]
import fake_toobit_responder as fake_module
from apex.execution import toobit_adapter as adapter_module
from apex.execution import toobit_map as wire

print(f"fake_uses_same_sign_query={fake_module.sign_query is wire.sign_query}")
print(f"sut_uses_same_signed_request={adapter_module.signed_request is wire.signed_request}")

params = {
    "symbol": "BTC-SWAP-USDT", "side": "BUY_OPEN", "positionSide": "BOTH",
    "type": "LIMIT", "timeInForce": "IOC", "price": "100",
    "quantity": "0.1", "reduceOnly": "false", "clientOrderId": "i-unsigned",
    "timestamp": "1767225600000", "recvWindow": str(wire.RECV_WINDOW_MS),
}

async def invoke(*, signature=None, client_id):
    responder = fake_module.FakeToobitResponder()
    request = dict(params)
    request["clientOrderId"] = client_id
    if signature is not None:
        request["signature"] = signature
    query = urlencode(request)
    response = await responder(
        "POST", f"{wire.BASE_URL}/api/v1/futures/order", query,
        {wire.HEADER_API_KEY: fake_module.TEST_API_KEY},
    )
    call = responder.calls[-1]
    return response, call, responder

unsigned, unsigned_call, unsigned_fake = asyncio.run(invoke(client_id="i-unsigned"))
print(f"unsigned_private_http={unsigned['http_status']}")
print(f"unsigned_private_order_status={unsigned['body']['data']['status']}")
print(f"unsigned_private_signature_flag={unsigned_call.signature_ok}")
print(f"unsigned_private_api_key_present={unsigned_call.api_key_present}")
print(f"unsigned_private_violations={len(unsigned_fake.signature_violations())}")
print(f"unsigned_private_order_created={'i-unsigned' in unsigned_fake.orders}")

invalid, invalid_call, invalid_fake = asyncio.run(
    invoke(signature="not-a-valid-hmac", client_id="i-invalid-signature"))
print(f"invalid_signature_http={invalid['http_status']}")
print(f"invalid_signature_order_status={invalid['body']['data']['status']}")
print(f"invalid_signature_flag={invalid_call.signature_ok}")
print(f"invalid_signature_violations={len(invalid_fake.signature_violations())}")
print(f"invalid_signature_order_created={'i-invalid-signature' in invalid_fake.orders}")
