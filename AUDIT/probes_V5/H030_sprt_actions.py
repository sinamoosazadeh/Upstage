"""H-030: exercise SPRT action path and distinguish state from operations."""
import json
from apex.research.promotion import LiveFamilyMonitor, SPRTState, sprt_monitor

monitor = LiveFamilyMonitor("fixture-family", SPRTState(p0=0.58, p_min=0.53))
last = None
for i in range(40):
    last = monitor.on_trade(win=False, timestamp=f"2026-09-01T00:{i:02d}:00Z")
    if monitor.halted:
        break
summary = sprt_monitor("fixture-family", p0=0.58, outcomes=[False] * 40)
print(json.dumps({
    "monitor_halted_in_memory": monitor.halted,
    "monitor_log_rows_in_memory": len(monitor.log),
    "monitor_fields": list(monitor.__dict__),
    "last_action": last["action"],
    "standalone_action": summary["action"],
    "rollback_action_strings": summary["rollback_actions"],
    "durable_store_or_executor_attached": False,
}, sort_keys=True, indent=2))
