"""CP-6 fabric battery — Evidence Fabric + SL-14 lifecycle crosswalk.

Blueprint: Ch.8 §8.0 (L14672–14768) + the L4681 crosswalk record
(SL-1 per ADR-P2-011 = Ch.8; SL-14 = Ch.8 §8.0 + Ch.2 §2.1).
Every clause of §8.0 that can be executed is executed here.
"""

from __future__ import annotations

import dataclasses
import math

import pytest

from apex.data_catalog.contracts import LifecycleState
from apex.fabric.evidence import (
    EVIDENCE_LIFECYCLE_STATES,
    ENGINE_LIFECYCLE_STATES,
    EXPIRY_TF_MULTIPLE,
    FABRIC_ADMIT_STATE,
    SL14_CROSSWALK,
    EvidenceFabric,
    FabricEvidenceRef,
    advance_lifecycle,
    engine_group_of,
    evidence_freshness,
    expiry_age_bars,
    fabric_from_events,
    is_forward,
    lifecycle_of,
    make_fabric_id,
    make_hash,
)
from apex.identity.hashes import sha256_hex
from apex.identity.canonical_json import canonical_json
from apex.quality.pit import TF_DURATION_SECONDS


def mkref(eid="ev_1", engine="E01", state="ACTIVE", direction=1, quality=0.9,
          age=1.0, as_of=1000, symbol="BTCUSDT", tf="1h", lineage=("obs-1",)):
    return FabricEvidenceRef(
        evidence_id=eid, engine_id=engine, symbol=symbol, timeframe=tf,
        state=state, direction=direction, quality=quality,
        resolution_class="Q3", age_bars=age, as_of=as_of,
        snapshot_id="a" * 64, lineage=tuple(lineage), parent_ids=())


# ---------------------------------------------------------------------------
# SL-14 lifecycle + crosswalk (L4681)
# ---------------------------------------------------------------------------

class TestSL14Crosswalk:
    def test_crosswalk_verbatim_equivalences(self):
        assert SL14_CROSSWALK["emitted"] == "ACTIVE"          # L4681 verbatim
        assert SL14_CROSSWALK["expired"] == "EXPIRED"         # L4681 verbatim
        assert SL14_CROSSWALK["superseded"] == "SUPERSEDED"   # L4681 verbatim

    def test_crosswalk_covers_every_engine_state(self):
        assert tuple(SL14_CROSSWALK) == ENGINE_LIFECYCLE_STATES
        assert set(SL14_CROSSWALK.values()) <= set(EVIDENCE_LIFECYCLE_STATES)

    def test_crosswalk_targets_exist_in_the_frozen_lifecycle_enum(self):
        # The frozen CP-1 contract enum is the single source of lifecycle
        # names — the fabric must not invent an eighth state (G6).
        for state in EVIDENCE_LIFECYCLE_STATES:
            assert getattr(LifecycleState, state) is not None
        assert len(EVIDENCE_LIFECYCLE_STATES) == len(LifecycleState)

    def test_unknown_engine_state_fails_closed(self):
        with pytest.raises(ValueError, match="UNRECOGNISED_EVIDENCE_LIFECYCLE_QX"):
            lifecycle_of("archived_but_not_really")

    def test_ladder_reaches_the_terminal_states_only(self):
        # L4681: "archived, never deleted" — no DELETED state exists.
        assert "DELETED" not in EVIDENCE_LIFECYCLE_STATES
        assert "ARCHIVED" not in EVIDENCE_LIFECYCLE_STATES


class TestLifecycleMachine:
    @pytest.mark.parametrize("src,dst", [
        ("CANDIDATE", "CONFIRMED"),
        ("CONFIRMED", "ACTIVE"),
        ("ACTIVE", "MITIGATED"), ("ACTIVE", "INVALIDATED"),
        ("ACTIVE", "EXPIRED"), ("ACTIVE", "SUPERSEDED"),
        ("MITIGATED", "INVALIDATED"), ("MITIGATED", "EXPIRED"),
        ("MITIGATED", "SUPERSEDED"),
    ])
    def test_forward_transitions_are_lawful(self, src, dst):
        assert is_forward(src, dst)
        assert advance_lifecycle(src, dst) == dst

    @pytest.mark.parametrize("src,dst", [
        ("ACTIVE", "CANDIDATE"),        # never reverts
        ("ACTIVE", "CONFIRMED"),         # skips a state
        ("CANDIDATE", "ACTIVE"),         # admission is not a shortcut
        ("CONFIRMED", "SUPERSEDED"),     # only from ACTIVE
        ("INVALIDATED", "ACTIVE"),       # terminal
        ("EXPIRED", "ACTIVE"),           # terminal
        ("SUPERSEDED", "CONFIRMED"),     # terminal
    ])
    def test_illegal_transitions_fail_closed(self, src, dst):
        assert not is_forward(src, dst)
        with pytest.raises(ValueError, match="ILLEGAL_SL14_TRANSITION_QX"):
            advance_lifecycle(src, dst)

    def test_unknown_state_is_rejected_not_invented(self):
        with pytest.raises(ValueError, match="UNKNOWN_SL14_STATE_QX"):
            advance_lifecycle("ACTIVE", "QUARANTINED")

    def test_fabric_admission_state_is_active_only(self):
        assert FABRIC_ADMIT_STATE == "ACTIVE"


class TestExpiryLaw:
    def test_expiry_is_five_tf_for_every_cell(self):
        # §9.5-8 universality: the rule applies to all 14 TFs.
        for tf, dur in TF_DURATION_SECONDS.items():
            assert expiry_age_bars(tf) == EXPIRY_TF_MULTIPLE * dur == 5 * dur

    def test_unknown_timeframe_fails_closed(self):
        with pytest.raises(ValueError, match="E-VAL-022"):
            expiry_age_bars("2d")


class TestFreshnessDecay:
    def test_decay_is_exp_minus_lambda_age(self):
        assert evidence_freshness(0.0, 0.02) == 1.0
        assert math.isclose(evidence_freshness(10.0, 0.02), math.exp(-0.2))
        assert math.isclose(evidence_freshness(4.0, 0.05), math.exp(-0.2))

    def test_decay_is_monotone_downward(self):
        vals = [evidence_freshness(a, 0.02) for a in range(0, 25)]
        assert all(x >= y for x, y in zip(vals, vals[1:]))

    def test_negative_inputs_fail_closed(self):
        with pytest.raises(ValueError, match="NEGATIVE_DECAY_INPUT_QX"):
            evidence_freshness(-1.0, 0.02)
        with pytest.raises(ValueError, match="NEGATIVE_DECAY_INPUT_QX"):
            evidence_freshness(1.0, -0.02)


# ---------------------------------------------------------------------------
# Fabric assembly (Ch.8 §8.0)
# ---------------------------------------------------------------------------

class TestEvidenceFabric:
    def test_shape_matches_the_frozen_json(self):
        fab = EvidenceFabric.assemble(symbol="BTCUSDT", timeframe="1h",
                                       as_of=1000, evidence=[mkref()],
                                       data_trust=0.98)
        d = fab.to_dict()
        assert set(d) == {"fabric_id", "as_of", "symbol", "timeframe",
                          "evidence", "data_trust", "conflict_state",
                          "redundancy_state", "hash"}
        assert d["fabric_id"].startswith("fab_")
        assert d["evidence"] == ["ev_1"]

    def test_only_active_evidence_enters(self):
        fab = EvidenceFabric.assemble(
            symbol="BTCUSDT", timeframe="1h", as_of=1000,
            evidence=[mkref("ev_1"), mkref("ev_2", state="CONFIRMED")],
            data_trust=0.98)
        assert [m.evidence_id for m in fab.members] == ["ev_1"]
        assert fab.excluded == (("ev_2", "NOT_ACTIVE_SL14"),)

    def test_lineage_down_to_raw_is_mandatory(self):
        with pytest.raises(ValueError, match="FABRIC_LINEAGE_QX"):
            mkref(lineage=())

    def test_lineage_must_resolve_when_raw_set_given(self):
        fab = EvidenceFabric.assemble(
            symbol="BTCUSDT", timeframe="1h", as_of=1000,
            evidence=[mkref("ev_1", lineage=("obs-999",))],
            data_trust=0.98, raw_observation_ids=["obs-1", "obs-2"])
        assert fab.is_empty()
        assert fab.excluded == (("ev_1", "LINEAGE_UNRESOLVED_QX"),)

    def test_pit_invariant_i1_excludes_future_evidence(self):
        fab = EvidenceFabric.assemble(
            symbol="BTCUSDT", timeframe="1h", as_of=1000,
            evidence=[mkref("ev_1", as_of=1001)], data_trust=0.98)
        assert fab.excluded == (("ev_1", "E-PIT-001"),)

    def test_scope_key_is_enforced(self):
        fab = EvidenceFabric.assemble(
            symbol="BTCUSDT", timeframe="1h", as_of=1000,
            evidence=[mkref("ev_1", symbol="ETHUSDT"),
                      mkref("ev_2", tf="4h")], data_trust=0.98)
        assert fab.is_empty()
        assert {r for _i, r in fab.excluded} == {"FABRIC_SCOPE_MISMATCH_QX"}

    def test_expired_members_leave_the_fabric(self):
        # age beyond 5×TF ⇒ EXPIRED_5TF (1h ⇒ 5·3600 s ⇒ 5 bars of age).
        fab = EvidenceFabric.assemble(
            symbol="BTCUSDT", timeframe="1h", as_of=1000,
            evidence=[mkref("ev_1", age=5.0), mkref("ev_2", age=4.99)],
            data_trust=0.98)
        assert [m.evidence_id for m in fab.members] == ["ev_2"]
        assert fab.excluded == (("ev_1", "EXPIRED_5TF"),)

    def test_data_trust_out_of_range_fails_closed(self):
        with pytest.raises(ValueError, match="FABRIC_DATA_TRUST_QX"):
            EvidenceFabric.assemble(symbol="BTCUSDT", timeframe="1h",
                                    as_of=1000, evidence=[], data_trust=1.2)

    def test_hash_is_sha256_of_canonical_serialization_and_stable(self):
        members = [mkref("ev_2"), mkref("ev_1")]
        a = EvidenceFabric.assemble(symbol="BTCUSDT", timeframe="1h",
                                    as_of=1000, evidence=members,
                                    data_trust=0.98)
        b = EvidenceFabric.assemble(symbol="BTCUSDT", timeframe="1h",
                                    as_of=1000, evidence=list(reversed(members)),
                                    data_trust=0.98)
        assert a.hash == b.hash          # member order is normalized
        assert len(a.hash) == 64
        expected = sha256_hex(canonical_json({
            "as_of": 1000, "symbol": "BTCUSDT", "timeframe": "1h",
            "evidence": ["ev_1", "ev_2"], "data_trust": 0.98,
            "conflict_state": "NONE", "redundancy_state": {}}))
        assert a.hash == expected

    def test_fabric_is_read_only_for_engines(self):
        fab = EvidenceFabric.assemble(symbol="BTCUSDT", timeframe="1h",
                                      as_of=1000, evidence=[mkref()],
                                      data_trust=0.98)
        with pytest.raises(dataclasses.FrozenInstanceError):
            fab.members = ()            # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            fab.conflict_state = "NONE"  # type: ignore[misc]

    def test_ref_validation_is_fail_closed(self):
        with pytest.raises(ValueError, match="FABRIC_DIRECTION_QX"):
            mkref(direction=2)
        with pytest.raises(ValueError, match="FABRIC_QUALITY_QX"):
            mkref(quality=float("nan"))
        with pytest.raises(ValueError, match="FABRIC_STATE_QX"):
            mkref(state="EMITTED")      # engine-local label is not an SL-14 state
        with pytest.raises(ValueError, match="FABRIC_SNAPSHOT_QX"):
            FabricEvidenceRef(evidence_id="e", engine_id="E01", symbol="S",
                              timeframe="1h", state="ACTIVE", direction=0,
                              quality=0.5, resolution_class="Q1", age_bars=0,
                              as_of=1, snapshot_id="", lineage=("obs",))

    def test_group_partition_is_total_and_disjoint(self):
        from apex.fabric.evidence import ENGINE_GROUPS
        seen = []
        for engines in ENGINE_GROUPS.values():
            seen.extend(engines)
        assert sorted(seen) == [f"E{i:02d}" for i in range(1, 13)]
        assert engine_group_of("E05") == "zones"
        with pytest.raises(ValueError, match="UNKNOWN_ENGINE_ID_QX"):
            engine_group_of("E13")


class TestFabricFromEvents:
    def test_adapter_crosswalks_engine_local_states(self):
        class Ev:
            evidence_id = "ev_x"
            engine_id = "E05"
            symbol = "BTCUSDT"
            timeframe = "1h"
            direction = -1
            quality = 0.8
            resolution_class = "Q2"
            age = 2.0
            snapshot_id = "b" * 64
            lineage = ("obs-7",)
            feature_dependencies = ("f1",)
            fate_state = "emitted"        # engine-local (L4681)

        fab = fabric_from_events([Ev()], symbol="BTCUSDT", timeframe="1h",
                                 as_of=10_000, data_trust=0.9)
        assert [m.state for m in fab.members] == ["ACTIVE"]   # emitted ≡ ACTIVE
        assert fab.members[0].direction == -1

    def test_missing_lifecycle_field_fails_closed(self):
        class Ev:
            evidence_id = "ev_y"
            engine_id = "E01"
            symbol = "BTCUSDT"
            timeframe = "1h"
            direction = 0
            quality = 0.5
            resolution_class = "Q1"
            age = 0.0
            snapshot_id = "c" * 64
            lineage = ("obs",)
            feature_dependencies = ()
            fate_state = None

        with pytest.raises(ValueError, match="FABRIC_STATE_QX"):
            fabric_from_events([Ev()], symbol="BTCUSDT", timeframe="1h",
                              as_of=10, data_trust=0.9)


class TestIdentityRules:
    def test_fabric_id_is_operational_only(self):
        i1, i2 = make_fabric_id(), make_fabric_id()
        assert i1.startswith("fab_") and i1 != i2
        # UUIDv7 must never enter the canonical payload (P8): the hash is
        # computed over a payload that excludes fabric_id.
        body = {"as_of": 1, "symbol": "S", "timeframe": "1h", "evidence": [],
                "data_trust": 1.0, "conflict_state": "NONE",
                "redundancy_state": {}}
        assert make_hash(body) == sha256_hex(canonical_json(body))
        assert i1 not in canonical_json(body)
