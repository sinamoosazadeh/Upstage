"""K-027 probe — event time in the fabric adapters.

READ-ONLY. Real frozen `EvidenceEvent`, real `apex.fabric.evidence`
(`fabric_from_events`, `EvidenceFabric.assemble`) and the real bridge adapter
`apex.ops.plan_bridge._fabric_ref`. Writes only this probe's .out file.

A. `fabric_from_events` with an ACTIVE event whose availability_time is in 2099,
   `age=None` and `lineage=()`, assembled at as_of=1000.
B. The bridge adapter `_fabric_ref` with a 1h event whose `event_time` is 14 days
   (336 bars) before as_of but which claims `age=0`, then the same ref with the
   measured age; both assembled by the real fabric.
C. Does the bridge re-measure the age without a `context["evidence_age_bars"]`
   mapping?  (plan_bridge.py:640-647)
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = pathlib.Path(__file__).with_suffix(".out")
_buf = []


def say(line=""):
    _buf.append(str(line))
    OUT.write_text("\n".join(_buf) + "\n")


def event(**over):
    from apex.data_catalog.contracts import EvidenceEvent
    base = dict(
        evidence_id="ev-1", engine_id="E09", analyst_version="v4.0.0+" + "a" * 40,
        symbol="BTCUSDT", timeframe="1h", snapshot_id="snap-1",
        event_time="2026-09-01T00:00:00.000Z",
        availability_time="2026-09-01T00:00:00.000Z",
        observation_window={"bars": 300}, feature_snapshot_id="feat-1",
        feature_dependencies=(), condition_state="TREND_UP", direction=1,
        strength=1.0, confidence=0.9, quality=0.9, validity="VALID",
        fate_state="ACTIVE", age=0.0, decay=0.0, explanation="probe",
        parameter_version="p-1", lineage=("obs-1",), resolution_class="Q3")
    base.update(over)
    ev = EvidenceEvent(**base)
    ev.validate_24_fields()
    return ev


def main():
    from apex.fabric.evidence import (EvidenceFabric, fabric_from_events,
                                      expiry_age_bars)
    from apex.ops import plan_bridge as PB

    say("# K-027 — event time in the fabric adapters")
    say()
    say("A. fabric_from_events: availability 2099, age=None, lineage=()")
    ev = event(availability_time="2099-01-01T00:00:00.000Z",
               event_time="2099-01-01T00:00:00.000Z", age=None, lineage=())
    fabric = fabric_from_events([ev], symbol="BTCUSDT", timeframe="1h",
                                as_of=1000, data_trust=1.0)
    say("   members  = %d   excluded = %r" % (len(fabric.members),
                                              list(fabric.excluded)))
    for m in fabric.members:
        say("   ref.as_of=%r  ref.age_bars=%r  ref.lineage=%r"
            % (m.as_of, m.age_bars, m.lineage))
    say("   (the event's own availability_time is never parsed: "
        "apex/fabric/evidence.py:465 writes as_of=as_of)")

    say()
    say("B. bridge adapter with a claimed age of 0 on a 14-day-old 1h event")
    HOUR_MS = 3_600_000
    as_of_ms = 1_790_000_000_000
    stale_iso = "2026-09-01T00:00:00.000Z"
    from apex.ops.engine_context import decision_evidence_age
    measured = decision_evidence_age(stale_iso, "1h", as_of_ms)
    ev2 = event(event_time=stale_iso, availability_time=stale_iso, age=0.0)
    ref = PB._fabric_ref(ev2, symbol="BTCUSDT", timeframe="1h",
                         as_of_ms=as_of_ms)
    say("   measured age (decision_evidence_age) = %r bars" % measured)
    say("   ref.age_bars accepted by _fabric_ref = %r" % ref.age_bars)
    say("   expiry_age_bars('1h')                = %r seconds"
        % expiry_age_bars("1h"))
    f_claim = EvidenceFabric.assemble(symbol="BTCUSDT", timeframe="1h",
                                      as_of=as_of_ms, evidence=[ref],
                                      data_trust=1.0)
    import dataclasses
    ref_true = dataclasses.replace(ref, age_bars=measured)
    f_true = EvidenceFabric.assemble(symbol="BTCUSDT", timeframe="1h",
                                     as_of=as_of_ms, evidence=[ref_true],
                                     data_trust=1.0)
    say("   claimed age 0   -> members=%d excluded=%r"
        % (len(f_claim.members), list(f_claim.excluded)))
    say("   measured age    -> members=%d excluded=%r"
        % (len(f_true.members), list(f_true.excluded)))

    say()
    say("C. bridge refusals that DO fire in _fabric_ref (plan_bridge.py:324-332)")
    for label, kwargs in (("availability_time missing", {"availability_time": ""}),
                          ("age None", {"age": None}),
                          ("lineage empty", {"lineage": ()})):
        try:
            bad = event(**kwargs)
        except ValueError as exc:
            say("   %-26s -> EvidenceEvent refused: %s" % (label, exc))
            continue
        try:
            PB._fabric_ref(bad, symbol="BTCUSDT", timeframe="1h",
                           as_of_ms=as_of_ms)
            say("   %-26s -> ACCEPTED" % label)
        except Exception as exc:                        # noqa: BLE001
            say("   %-26s -> %s(%r)" % (label, type(exc).__name__,
                                        getattr(exc, "reason", str(exc))))
    say("   the age is re-measured ONLY when context['evidence_age_bars'] is "
        "supplied (plan_bridge.py:640-647)")


if __name__ == "__main__":
    main()
    sys.stdout.write(OUT.read_text())
