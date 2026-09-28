"""Offline production boot/serve composition checks. No actual order operation.
Run: PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-002-root.py
The only runtime seams changed in the main experiment are public time (local
fixture) and the optional classifier diagnostic (deliberate refusal).
The production Runtime.adapter factory is NOT patched in that experiment.
"""
import runpy
from pathlib import Path
ns = runpy.run_path(str(Path(__file__).with_name('C-002.py')))
# Imports and safety hooks from the original probe; it does not run main here.
import asyncio
import json
from unittest.mock import patch
from scripts import run_apex as R
from apex.execution.toobit_adapter import ToobitAdapter

async def local_time():
    return {'serverTime': R.C.SystemClock().now_ms()}

def no_model(*args, **kwargs):
    raise R.EC.BridgeError('AUDIT_MODEL_NOT_LOADED', 'offline diagnostic seam')

async def forbidden_order(*args, **kwargs):
    raise AssertionError('AUDIT_ORDER_OPERATION_FORBIDDEN')

async def main():
    for present in (False, True):
        cfg = ns['config'](present)
        print('CASE synthetic_credentials=' + str(present))
        with patch.object(R, '_venue_server_time', local_time), \
             patch.object(R.EC, 'load_classifier', no_model), \
             patch.object(ToobitAdapter, 'submit_order', forbidden_order), \
             patch.object(ToobitAdapter, 'cancel_order', forbidden_order):
            boot_code = await R._boot(cfg, as_json=True)
            serve_code = await R._serve(cfg, as_json=True, cycles=0)
        print(json.dumps({'boot_exit': boot_code, 'serve_exit': serve_code}))
        assert boot_code == (3 if present else 2)
        assert serve_code == 2
    # Counterfactual control: same store/FSM, only transport gets an empty
    # offline responder. This is NOT a proposed PAPER simulator.
    cfg = ns['config'](True)
    runtime = await R.Runtime(cfg).start()
    called = []
    async def empty_query(method, url, query, headers):
        assert method == 'GET'
        path = url.split('toobit.com')[-1]
        assert path in ('/api/v1/futures/positions', '/api/v1/futures/openOrders', '/api/v1/futures/userTrades')
        called.append(path)
        return {'http_status': 200, 'body': {'code': 0, 'data': []}}
    try:
        adapter = ToobitAdapter(config=cfg, transport=empty_query)
        result = await R.F.StartupReconciliation(ledger=runtime.ledger, adapter=adapter,
                    environment='PAPER', drift_seconds=0).run()
        print(json.dumps({'control': 'ONLY_OFFLINE_TRANSPORT_INJECTED', 'boot_state': result['boot_state'], 'queries': called}))
        assert result['boot_state'] == 'READY'
    finally:
        await runtime.stop()
    print('guard_blocked_attempts=' + json.dumps(ns['blocked']))
    assert not ns['blocked']
    print('PASS: production boot + zero-cycle serve refuse, transport-only control READY; no device acceptance')

asyncio.run(main())
