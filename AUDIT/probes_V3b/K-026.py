"""K-026 probe — the D52 PAPER backfill writes quality facts whose receipt is the
historical insert time, so the reader quarantines every one of them.

READ-ONLY. Real SQLiteStore, real publish_quality_backfill, real
EngineContextProducer.quality_window, real freshness()/calc_quality_vector.
Writes only this probe's .out file.

Seeded: 300 consecutive CLOSED 1h bars, each inserted (created_at) one day
after its own close — the shape of a historical backfill: the receipt is
legitimate (never before the close) but far later than the bar.
"""
import asyncio
import importlib.util
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = pathlib.Path(__file__).with_suffix(".out")
_buf = []


def say(line=""):
    _buf.append(str(line))
    OUT.write_text("\n".join(_buf) + "\n")


def load_helpers():
    spec = importlib.util.spec_from_file_location(
        "t_repair", ROOT / "tests" / "unit" / "test_ops_partial_bar_repair.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


async def main(tmp):
    h = load_helpers()
    from apex.ops import bootstrap_service as BS
    from apex.ops import engine_context as EC
    from apex.quality.vector import calc_quality_vector, QualityFlags

    HOUR = h.HOUR
    T0 = h.T0
    N = 8                                  # 8 bars is enough to show the rule
    store = await h.open_store(pathlib.Path(tmp) / "apex.sqlite3")
    for i in range(N):
        open_ms = T0 + i * HOUR
        close_ms = open_ms + HOUR
        await h.seed(store, open_ms,
                     created_iso=BS._ms_to_iso(close_ms + 86_400_000),
                     c="100.%d" % (i + 1))

    say("# K-026 — historical backfill freshness vs the PAPER window gate")
    say()
    say("seeded %d CLOSED 1h bars, each created_at = its close + 24 h" % N)

    report = await EC.publish_quality_backfill(store, environment="PAPER")
    say()
    say("publish_quality_backfill(environment='PAPER'):")
    for key in ("written", "already_present", "skipped",
                "skipped_receipt_before_close"):
        say("   %-28s = %r" % (key, report[key]))

    # What the reader recomputes for the newest bar (engine_context.py:2073-2081)
    cur = await store.db.execute(
        "SELECT observation_id FROM market_observation ORDER BY open_time DESC "
        "LIMIT 1")
    obs_id = (await cur.fetchone())[0]
    await cur.close()
    fact = await EC.read_context_fact(
        store, "QUALITY_" + obs_id, "BTCUSDT", "1h",
        BS._ms_to_iso(T0 + (N + 48) * HOUR))
    say()
    say("durable fact for the newest bar:")
    say("   measurement_source = %r" % fact.get("measurement_source"))
    say("   provenance         = %r" % fact.get("provenance"))
    say("   receipt_time_ms    = %r (%s)"
        % (fact.get("receipt_time_ms"), BS._ms_to_iso(fact["receipt_time_ms"])))
    say("   q_raw / state      = %r / %r"
        % (fact.get("q_raw"), fact.get("quality_state")))
    say("   delay_seconds      = %r"
        % (fact.get("measurements", {}).get("delay_seconds"),))

    say()
    say("reader path (EngineContextProducer.quality_window):")
    producer = EC.EngineContextProducer(store, environment="PAPER")
    try:
        await producer.quality_window("BTCUSDT", "1h",
                                      BS._ms_to_iso(T0 + (N + 48) * HOUR), N)
        say("   quality_window SUCCEEDED")
    except Exception as exc:                        # noqa: BLE001
        say("   quality_window raised %s(%r, %r)"
            % (type(exc).__name__, getattr(exc, "reason", None),
               str(getattr(exc, "detail", exc))[:120]))

    await store.close()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        asyncio.run(main(tmp))
    sys.stdout.write(OUT.read_text())
