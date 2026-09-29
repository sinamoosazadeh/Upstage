"""V1d new finding X-V1d-002 — ExecutionFSM.apply_adapter_result consumes a
CACHED duplicate receipt (cached=True, error_code=DUPLICATE_CLIENT_ORDER_ID)
exactly like a fresh venue acknowledgement: it advances SUBMITTING ->
ACKNOWLEDGED and reports classification OK. The idempotency markers the
adapter faithfully sets (T_ADAPTER_DUPLICATE / D50) are never consulted by
the only production consumer. (Related to E-022; this is the consumer-side
half, which the audit row does not cover.)
READ-ONLY verification with the real ExecutionFSM + real AdapterResult."""
import asyncio
import os
import sys

os.environ.setdefault("APEX_ENV", "PAPER")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apex.execution import fsm as F
from apex.execution.toobit_adapter import AdapterResult

UTC = lambda: "2026-01-01T00:00:00.000Z"  # noqa: E731


def duplicate_receipt() -> AdapterResult:
    """A byte-faithful D50/T_ADAPTER_DUPLICATE cached receipt (same fields
    ToobitAdapter._cached_result returns)."""
    return AdapterResult(
        operation="submit_order", endpoint="/api/v1/futures/order",
        ok=True, classification="OK", outcome="ACKNOWLEDGED",
        business_code=0, http_status=200, data={},
        client_order_id="i-x002", order_id="900001",
        idempotency_key="k" * 64, reconcile_required=False,
        resubmitted=False, cached=True, interval_disabled=None,
        attempts=(), error_code="DUPLICATE_CLIENT_ORDER_ID",
        rule="Ch.16 L16796–16798 DUPLICATE_CLIENT_ORDER_ID — a repeated key "
             "returns the recorded response and never resubmits")


async def main() -> None:
    machine = F.ExecutionFSM(intent_id="i-x002", environment="PAPER",
                             utc_now=UTC, clock=lambda: 1000.0)
    await machine.advance("SUBMIT_ORDER")
    result = await machine.apply_adapter_result(duplicate_receipt())
    print("apply_adapter_result(cached=True, error_code="
          "DUPLICATE_CLIENT_ORDER_ID):")
    print("  ->", result)
    print("  FSM state:", machine.state,
          "| reconcile_required:", result["reconcile_required"])
    print("  grep of apply_adapter_result (fsm.py:598-641): it branches ONLY"
          " on result.classification and result.outcome;")
    print("  result.cached and result.error_code are never read — a cached"
          " duplicate receipt is indistinguishable from a fresh ACK.")
    print("  (D50: a repeated client order id is 'rejected by name"
          " DUPLICATE_CLIENT_ORDER_ID'; the adapter's own comment says"
          " 'the named code is what a caller matches on' — yet no caller"
          " matches on it: grep over apex/ finds .cached /"
          " DUPLICATE_CLIENT_ORDER_ID only inside toobit_adapter.py.)")


if __name__ == "__main__":
    asyncio.run(main())
