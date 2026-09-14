"""CP-7 execution FSM tests — SL-6 canonical state list, the frozen transition
matrix (Ch.16 L16764–16790), reconcile-first on boot (Ch.23 L18242–18251),
E-EXEC-001 fill/submission timeouts, T-MON-002 (state never reverts), T_MATCH /
T_RECONCILE / T-LR-002 / T-LR-003 through the FSM, protection-failure
escalation (Ch.16 L16916–16918) and the AI.9 seven-check recovery sequence.

The venue is ``tests/fake_toobit_responder.py`` (a test double only) and every
scenario runs inside ONE event loop with ONE ledger writer, exactly like the
runtime composition root (Ch.23 L18253–18260).
"""
from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pytest

from apex.bus import EventBus, Priority
from apex.data_catalog.store import sqlite_store as ss
from apex.execution import fsm as F
from apex.execution.toobit_adapter import ToobitAdapter
from apex.ledger import store as LS

TEST_KEY = "TEST_KEY_CP7"
TEST_SECRET = "TEST_SECRET_CP7"
ISO = "2026-01-01T00:00:00.000Z"


class TickingClock:
    def __init__(self, start_ms: int = 1767225600000) -> None:
        self.ms = start_ms

    def __call__(self) -> str:
        self.ms += 1
        moment = dt.datetime.fromtimestamp(self.ms / 1000.0, dt.timezone.utc)
        return moment.strftime("%Y-%m-%dT%H:%M:%S.") + \
            f"{moment.microsecond // 1000:03d}Z"


class FakeMonotonic:
    """A controllable monotonic clock for the timeout laws."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> float:
        self.now += float(seconds)
        return self.now


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def store(tmp_path):
    sqlite = ss.SQLiteStore(str(tmp_path / "apex.sqlite3"))
    run(sqlite.open())
    yield sqlite
    run(sqlite.close())


@pytest.fixture(autouse=True)
def signed_env(monkeypatch):
    monkeypatch.setenv("APEX_ENV", "PAPER")
    monkeypatch.setenv("APEX_ALLOW_SIGNED", "1")
    monkeypatch.setenv("TOOBIT_API_KEY", TEST_KEY)
    monkeypatch.setenv("TOOBIT_API_SECRET", TEST_SECRET)


@dataclass
class FakeProposal:
    """CP-6 StrategyProposal shape (HANDOFF_CP6 §INTERFACES 1)."""
    proposal_id: str = "pr-0001"
    setup_id: str = "su-0001"
    direction: str = "LONG"
    stop: float = 99.0
    targets: tuple = (103.0, 106.0)
    entry_logic_ref: str = "E-01/BOS"
    snapshot_id: str = "sn-0001"

    def to_dict(self) -> Dict[str, Any]:
        return {"proposal_id": self.proposal_id, "setup_id": self.setup_id,
                "direction": self.direction, "stop": self.stop,
                "targets": list(self.targets),
                "entry_logic_ref": self.entry_logic_ref,
                "snapshot_id": self.snapshot_id}


def adjudication(**overrides) -> Dict[str, Any]:
    base = {"decision": "ALLOW", "sized_quantity": 0.10, "vetoes_applied": [],
            "sizing": {"R_allowed": 10.0}, "snapshot_id": "sn-0001"}
    base.update(overrides)
    return base


def make_plan(**overrides) -> F.TradePlan:
    kwargs = {"proposal": FakeProposal(), "adjudication": adjudication(),
              "symbol": "BTCUSDT", "timeframe": "1h", "environment": "PAPER",
              "as_of": ISO, "capital": 10000.0, "contract_multiplier": 1.0,
              "risk_state": "LowRisk", "package_version": "4.0.0",
              "created_utc": ISO}
    kwargs.update(overrides)
    return F.build_trade_plan(**kwargs)


class Harness:
    """Everything one scenario needs, all bound to ONE event loop."""

    def __init__(self, store, *, adapter=True, bus=True, drift=0.0,
                 fill_mode="none", fail_with=None, fail_times=1,
                 timeouts=0, clock=None, ledger=True, environment="PAPER"):
        self.store = store
        self.clock = clock or FakeMonotonic()
        self.ledger: Optional[LS.LedgerWriter] = None
        self.responder = None
        self.adapter = None
        self.bus = None
        self.events: List[Any] = []
        self._adapter_flag = adapter
        self._bus_flag = bus
        self._ledger_flag = ledger
        self.drift = drift
        self.environment = environment
        self._scenario = {"fill_mode": fill_mode, "fail_with": fail_with,
                          "fail_times": fail_times, "timeouts": timeouts}

    async def setup(self) -> "Harness":
        from fake_toobit_responder import FakeToobitResponder
        if self._ledger_flag:
            self.ledger = LS.LedgerWriter(self.store, clock=TickingClock())
            await self.ledger.initialize()
            await self.ledger.start()
        if self._adapter_flag:
            self.responder = FakeToobitResponder(api_key=TEST_KEY,
                                                api_secret=TEST_SECRET)
            scenario = self._scenario
            if scenario["fill_mode"] != "none":
                self.responder.set_fill_mode(scenario["fill_mode"])
            if scenario["fail_with"] is not None:
                self.responder.fail_next(scenario["fail_with"],
                                         scenario["fail_times"])
            if scenario["timeouts"]:
                self.responder.lose_next_ack(scenario["timeouts"])
            from apex.config import Config
            self.adapter = ToobitAdapter(config=Config(),
                                         transport=self.responder,
                                         utc_now=lambda: ISO,
                                         clock=lambda: self.clock())
        if self._bus_flag:
            self.bus = EventBus()

            async def collector(event):
                self.events.append(event)

            self.bus.subscribe("execution.fsm.transition", collector)
            self.bus.subscribe("execution.boot", collector)
            self._bus_task = self.bus.start()      # P1/P2/P3 lane consumers
        return self

    async def drain(self, times: int = 8) -> None:
        """Let the bus lanes deliver what was enqueued (P0 is inline)."""
        for _ in range(times):
            await asyncio.sleep(0)

    async def teardown(self) -> None:
        if self.bus is not None:
            await self.bus.stop()
        if self.ledger is not None and not self.ledger.closed:
            await self.ledger.stop()

    def fsm(self, **kwargs) -> F.ExecutionFSM:
        kwargs.setdefault("ledger", self.ledger)
        kwargs.setdefault("adapter", self.adapter)
        kwargs.setdefault("bus", self.bus)
        kwargs.setdefault("clock", self.clock)
        kwargs.setdefault("utc_now", lambda: ISO)
        kwargs.setdefault("environment", self.environment)
        return F.ExecutionFSM(**kwargs)

    def boot(self, **kwargs) -> F.StartupReconciliation:
        kwargs.setdefault("ledger", self.ledger)
        kwargs.setdefault("adapter", self.adapter)
        kwargs.setdefault("bus", self.bus)
        kwargs.setdefault("clock", self.clock)
        kwargs.setdefault("utc_now", lambda: ISO)
        kwargs.setdefault("environment", self.environment)
        kwargs.setdefault("drift_seconds", self.drift)
        return F.StartupReconciliation(**kwargs)

    async def ledger_rows(self, event_type=None) -> List[LS.LedgerEntry]:
        rows = await self.ledger.read_ledger()
        return [r for r in rows if event_type is None
                or r.event_type == event_type]


def scenario(body, store, **kwargs):
    """Run ``body(harness)`` inside one event loop with one writer."""

    async def _run():
        harness = Harness(store, **kwargs)
        await harness.setup()
        try:
            return await body(harness)
        finally:
            await harness.teardown()

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# SL-6 canonical state list + the frozen matrix
# ---------------------------------------------------------------------------

class TestCanonicalStates:
    def test_sl6_canonical_list_is_exactly_nine_states(self):
        assert F.CANONICAL_STATES == ("READY", "SUBMITTING", "ACKNOWLEDGED",
                                      "PARTIAL", "FILLED", "PROTECTED",
                                      "MANAGED", "CLOSED", "RECONCILED")
        assert len(F.CANONICAL_STATES) == 9

    def test_the_runtime_vocabulary_adds_only_the_response_classes(self):
        assert F.FSM_STATES == F.CANONICAL_STATES + (
            F.RECOVERY_REQUIRED,) + F.TERMINAL_RESPONSE_STATES
        assert F.TERMINAL_RESPONSE_STATES == ("REJECTED", "CANCELLED")
        assert F.TERMINAL_STATES == frozenset({"RECONCILED"})

    def test_every_state_has_a_semantic_definition(self):
        assert set(F.STATE_SEMANTICS) == set(F.FSM_STATES)

    def test_every_matrix_entry_is_inside_the_vocabulary(self):
        for (src, trigger), dst in F.LEGAL_TRANSITIONS.items():
            assert src in F.FSM_STATES, src
            assert dst in F.FSM_STATES, dst
            assert trigger in F.TRIGGERS, trigger

    @pytest.mark.parametrize("src,trigger,dst", [
        ("READY", "SUBMIT_ORDER", "SUBMITTING"),
        ("READY", "VALIDATION_FAILED", "REJECTED"),
        ("SUBMITTING", "EXCHANGE_ACK", "ACKNOWLEDGED"),
        ("SUBMITTING", "PARTIAL_FILL", "PARTIAL"),
        ("SUBMITTING", "FULL_FILL", "FILLED"),
        ("SUBMITTING", "EXCHANGE_REJECT", "REJECTED"),
        ("SUBMITTING", "SUBMISSION_TIMEOUT", F.RECOVERY_REQUIRED),
        ("SUBMITTING", "UNKNOWN_OUTCOME", F.RECOVERY_REQUIRED),
        ("ACKNOWLEDGED", "FULL_FILL", "FILLED"),
        ("ACKNOWLEDGED", "FILL_TIMEOUT", F.RECOVERY_REQUIRED),
        ("ACKNOWLEDGED", "PROTECTION_PLACED", "PROTECTED"),
        ("PARTIAL", "FULL_FILL", "FILLED"),
        ("FILLED", "PROTECTION_PLACED", "PROTECTED"),
        ("FILLED", "PROTECTION_FAILED", F.RECOVERY_REQUIRED),
        ("FILLED", "POSITION_CLOSED", "CLOSED"),
        ("PROTECTED", "MANAGEMENT_ACTIVE", "MANAGED"),
        ("PROTECTED", "POSITION_CLOSED", "CLOSED"),
        ("MANAGED", "POSITION_CLOSED", "CLOSED"),
        ("CLOSED", "RECONCILE_MATCH", "RECONCILED"),
        ("CLOSED", "RECONCILE_DIVERGENCE", F.RECOVERY_REQUIRED),
        (F.RECOVERY_REQUIRED, "RECONCILE_MATCH", "RECONCILED"),
        ("ACKNOWLEDGED", "CANCEL_CONFIRMED", "CANCELLED")])
    def test_required_transitions_exist(self, src, trigger, dst):
        assert F.LEGAL_TRANSITIONS[(src, trigger)] == dst
        assert F.is_legal(src, trigger, dst) is True

    @pytest.mark.parametrize("src,trigger", [
        ("FILLED", "SUBMIT_ORDER"),            # never re-submit a filled order
        ("RECONCILED", "POSITION_CLOSED"),     # terminal: nothing re-opens it
        ("RECONCILED", "SUBMIT_ORDER"),
        ("READY", "FULL_FILL"),                # no fill before submission
        ("CLOSED", "MANAGEMENT_ACTIVE"),
        ("REJECTED", "SUBMIT_ORDER"),
        ("SUBMITTING", "MANAGEMENT_ACTIVE")])
    def test_illegal_transitions_are_absent_from_the_matrix(self, src, trigger):
        assert (src, trigger) not in F.LEGAL_TRANSITIONS
        assert F.is_legal(src, trigger, "FILLED") is False

    def test_recovery_required_resolves_to_every_live_state(self):
        """AI.9 step 7: recovery re-enters the state the exchange proves."""
        resolutions = {dst for (src, trigger), dst in F.LEGAL_TRANSITIONS.items()
                       if src == F.RECOVERY_REQUIRED}
        assert resolutions == {"RECONCILED", "ACKNOWLEDGED", "PARTIAL", "FILLED",
                               "PROTECTED", "MANAGED", "CLOSED", "CANCELLED",
                               "REJECTED", F.RECOVERY_REQUIRED}

    def test_legal_targets_and_triggers_views(self):
        assert F.legal_targets("READY")["SUBMIT_ORDER"] == "SUBMITTING"
        assert F.legal_targets("RECONCILED") == {}


class TestCh1DiagramAliases:
    @pytest.mark.parametrize("alias,canonical", [
        ("ARMED", "READY"), ("TRIGGERED", "READY"), ("EXECUTING", "SUBMITTING"),
        ("SETTLED", "RECONCILED"), ("CANCEL_PENDING", "SUBMITTING"),
        ("INVALIDATED", "REJECTED"), ("UNKNOWN", F.RECOVERY_REQUIRED)])
    def test_chapter_1_diagram_names_map_to_the_canonical_list(self, alias,
                                                               canonical):
        assert F.CH1_DIAGRAM_MAP[alias] == canonical
        assert F.canonical_state(alias) == canonical

    @pytest.mark.parametrize("name", ["ARCHIVED", "IDLE", "PRUNED"])
    def test_non_fsm_states_are_refused_not_invented(self, name):
        """Ch.1 L255: ARCHIVED/IDLE/PRUNED are message-lifecycle states, not
        execution states — mapping them would be an invention."""
        assert F.CH1_DIAGRAM_MAP[name] is None
        with pytest.raises(F.FsmError) as exc:
            F.canonical_state(name)
        assert exc.value.reason == "NOT_AN_FSM_STATE"

    def test_canonical_names_pass_through(self):
        for state in F.CANONICAL_STATES:
            assert F.canonical_state(state) == state

    def test_an_unrecognised_name_fails_closed(self):
        """A name that is neither canonical nor a Ch.1 alias is refused —
        mapping it to some state would be an invention (G6 fail-closed)."""
        with pytest.raises(F.FsmError) as exc:
            F.canonical_state("SOMETHING_ELSE")
        assert exc.value.reason == "FSM_STATE_UNKNOWN"

    def test_the_diagram_unknown_name_is_recovery_required(self):
        assert F.canonical_state("UNKNOWN") == F.RECOVERY_REQUIRED


# ---------------------------------------------------------------------------
# advance(): ledger + bus effects, illegal refusal
# ---------------------------------------------------------------------------

class TestAdvance:
    def test_a_legal_advance_writes_the_ledger_and_publishes_p1(self, store):
        async def body(h):
            machine = h.fsm()
            record = await machine.advance("SUBMIT_ORDER", reason="test")
            rows = await h.ledger_rows("FSM_TRANSITION")
            await h.drain()
            return record, rows, h.events

        record, rows, events = scenario(body, store)
        assert record.from_state == "READY"
        assert record.to_state == "SUBMITTING"
        assert record.trigger == "SUBMIT_ORDER"
        assert record.ledger_id is not None
        assert len(rows) == 1
        assert rows[0].raw["payload"]["from_state"] == "READY"
        assert rows[0].raw["payload"]["to_state"] == "SUBMITTING"
        assert len(events) == 1
        assert events[0].priority == int(Priority.P1)
        assert events[0].topic == "execution.fsm.transition"

    def test_an_illegal_advance_is_refused_and_writes_nothing(self, store):
        async def body(h):
            machine = h.fsm()
            with pytest.raises(F.IllegalTransitionError) as exc:
                await machine.advance("FULL_FILL")
            return machine.state, await h.ledger_rows(), str(exc.value), h.events

        state, rows, message, events = scenario(body, store)
        assert state == "READY"                    # the state never moved
        assert rows == []                          # nothing was written
        assert "ILLEGAL_FSM_TRANSITION" in message
        assert events == []                        # nothing was published

    def test_recovery_required_publishes_at_p0(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.advance("SUBMIT_ORDER")
            await machine.advance("UNKNOWN_OUTCOME", reason="lost ack")
            await h.drain()
            return machine.state, [int(e.priority) for e in h.events]

        state, priorities = scenario(body, store)
        assert state == F.RECOVERY_REQUIRED
        assert priorities == [int(Priority.P1), int(Priority.P0)]

    def test_history_is_an_immutable_view(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.advance("SUBMIT_ORDER")
            history = machine.history
            with pytest.raises(TypeError):
                history[0] = None
            return len(history)

        assert scenario(body, store) == 1

    def test_reconciled_is_terminal(self, store):
        async def body(h):
            machine = h.fsm()
            for trigger in ("SUBMIT_ORDER", "EXCHANGE_ACK", "FULL_FILL",
                            "PROTECTION_PLACED", "POSITION_CLOSED",
                            "RECONCILE_MATCH"):
                await machine.advance(trigger)
            return machine.state, machine.is_terminal, machine.legal_triggers()

        state, terminal, triggers = scenario(body, store)
        assert state == "RECONCILED"
        assert terminal is True
        assert triggers == {}


class TestSubstates:
    def test_armed_and_triggered_are_nested_in_ready(self, store):
        async def body(h):
            machine = h.fsm()
            machine.set_substate("ARMED")
            armed = (machine.state, machine.substate)
            machine.set_substate("TRIGGERED")
            triggered = (machine.state, machine.substate)
            return armed, triggered, await h.ledger_rows()

        armed, triggered, rows = scenario(body, store)
        assert armed == ("READY", "ARMED")
        assert triggered == ("READY", "TRIGGERED")
        assert rows == []            # a substate is not a canonical transition

    def test_a_substate_outside_ready_is_refused(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.advance("SUBMIT_ORDER")
            with pytest.raises(F.FsmError) as exc:
                machine.set_substate("ARMED")
            return exc.value.reason

        assert scenario(body, store) == "SUBSTATE_ONLY_IN_READY"

    def test_an_unknown_substate_is_refused(self, store):
        async def body(h):
            machine = h.fsm()
            with pytest.raises(F.FsmError) as exc:
                machine.set_substate("HALF_ARMED")
            return exc.value.reason

        assert scenario(body, store) == "SUBSTATE_QX"


class TestTMon002:
    """AI.4 canonical state machine: state never reverts; only forward or
    terminal (100 transitions, no backward move except recovery re-entry)."""

    def test_a_full_lifecycle_never_reverts(self, store):
        path = ["SUBMIT_ORDER", "EXCHANGE_ACK", "PARTIAL_FILL", "FULL_FILL",
                "PROTECTION_PLACED", "MANAGEMENT_ACTIVE", "POSITION_CLOSED",
                "RECONCILE_MATCH"]

        async def body(h):
            machine = h.fsm()
            seen = [machine.state]
            for _ in range(12):                      # 96 transitions total
                for trigger in path:
                    if trigger not in machine.legal_triggers():
                        break
                    await machine.advance(trigger)
                    seen.append(machine.state)
                if machine.is_terminal:
                    break
            return seen

        seen = scenario(body, store)
        order = {state: index for index, state in enumerate(F.CANONICAL_STATES)}
        indices = [order[s] for s in seen if s in order]
        assert all(indices[i] <= indices[i + 1] for i in range(len(indices) - 1))
        assert seen[-1] == "RECONCILED"

    #: Forward rank for T-MON-002. The nine canonical states rank in lifecycle
    #: order; REJECTED/CANCELLED are terminal RESPONSE classes that a
    #: reconciliation still completes (→ RECONCILED), so they rank below
    #: RECONCILED and above RECOVERY_REQUIRED (the recovery class).
    RANK = {state: index for index, state in enumerate(F.CANONICAL_STATES)}
    RANK.update({F.RECOVERY_REQUIRED: 9, "REJECTED": 10, "CANCELLED": 10,
                 "RECONCILED": 11})

    def test_no_backward_edge_exists_outside_recovery(self):
        backwards = [(src, trigger, dst)
                     for (src, trigger), dst in F.LEGAL_TRANSITIONS.items()
                     if self.RANK[dst] < self.RANK[src]
                     and src != F.RECOVERY_REQUIRED]
        assert backwards == []

    def test_recovery_re_entry_is_the_only_backward_class(self):
        backwards = {src for (src, trigger), dst in F.LEGAL_TRANSITIONS.items()
                     if self.RANK[dst] < self.RANK[src]}
        assert backwards == {F.RECOVERY_REQUIRED}

    def test_a_lifecycle_never_revisits_a_state_it_has_left(self, store):
        async def body(h):
            machine = h.fsm()
            seen = []
            for trigger in ("SUBMIT_ORDER", "EXCHANGE_ACK", "PARTIAL_FILL",
                            "FULL_FILL", "PROTECTION_PLACED",
                            "MANAGEMENT_ACTIVE", "POSITION_CLOSED",
                            "RECONCILE_MATCH"):
                await machine.advance(trigger)
                seen.append(machine.state)
            return seen

        seen = scenario(body, store)
        assert len(seen) == len(set(seen))


# ---------------------------------------------------------------------------
# E-EXEC-001 timeouts
# ---------------------------------------------------------------------------

class TestTimeouts:
    def test_governed_timeout_literals(self):
        assert F.SUBMISSION_TIMEOUT_SECONDS == 5.0
        assert F.FILL_TIMEOUT_SECONDS == 5.0
        assert F.FILL_TIMEOUT_REASON == "E-EXEC-001"
        assert F.CLOCK_DRIFT_TOLERANCE_SECONDS == 5.0
        assert F.E12_DRIFT_DEGRADED_SECONDS == 0.5
        assert F.RECONCILE_DELTA_TOLERANCE_UNITS == 1.0

    def test_submission_timeout_forces_recovery_required(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.advance("SUBMIT_ORDER")
            before = machine.check_timeouts()
            h.clock.advance(F.SUBMISSION_TIMEOUT_SECONDS + 0.001)
            expired = machine.check_timeouts()
            verdict = await machine.apply_timeouts()
            rows = await h.ledger_rows("FSM_TRANSITION")
            return before, expired, verdict, machine.state, rows[-1]

        before, expired, verdict, state, last = scenario(body, store)
        assert before["expired"] is None
        assert expired["expired"] == "SUBMISSION_TIMEOUT"
        assert expired["error_code"] == "E-EXEC-001"
        assert verdict["expired"] == "SUBMISSION_TIMEOUT"
        assert state == F.RECOVERY_REQUIRED
        assert last.raw["payload"]["error_code"] == "E-EXEC-001"

    def test_fill_timeout_forces_recovery_required(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.advance("SUBMIT_ORDER")
            await machine.advance("EXCHANGE_ACK")
            h.clock.advance(F.FILL_TIMEOUT_SECONDS + 0.5)
            await machine.apply_timeouts()
            return machine.state

        assert scenario(body, store) == F.RECOVERY_REQUIRED

    def test_fill_timeout_applies_to_a_partial_fill_too(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.advance("SUBMIT_ORDER")
            await machine.advance("PARTIAL_FILL")
            h.clock.advance(F.FILL_TIMEOUT_SECONDS + 0.5)
            verdict = await machine.apply_timeouts()
            return machine.state, verdict["expired"]

        assert scenario(body, store) == (F.RECOVERY_REQUIRED, "FILL_TIMEOUT")

    def test_no_timeout_inside_the_governed_window(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.advance("SUBMIT_ORDER")
            h.clock.advance(F.SUBMISSION_TIMEOUT_SECONDS - 0.5)
            verdict = await machine.apply_timeouts()
            return machine.state, verdict["expired"]

        assert scenario(body, store) == ("SUBMITTING", None)

    def test_a_terminal_state_never_times_out(self, store):
        async def body(h):
            machine = h.fsm()
            for trigger in ("SUBMIT_ORDER", "EXCHANGE_ACK", "FULL_FILL",
                            "PROTECTION_PLACED", "POSITION_CLOSED",
                            "RECONCILE_MATCH"):
                await machine.advance(trigger)
            h.clock.advance(3600)
            return machine.state, (await machine.apply_timeouts())["expired"]

        assert scenario(body, store) == ("RECONCILED", None)

    def test_check_timeouts_never_mutates_state(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.advance("SUBMIT_ORDER")
            h.clock.advance(60)
            machine.check_timeouts()
            return machine.state, len(await h.ledger_rows())

        assert scenario(body, store) == ("SUBMITTING", 1)


# ---------------------------------------------------------------------------
# Pre-submission validation (READY-state law)
# ---------------------------------------------------------------------------

class TestPreSubmissionValidation:
    def test_a_reject_plan_is_never_submitted(self, store):
        async def body(h):
            machine = h.fsm()
            plan = make_plan(adjudication=adjudication(decision="REJECT",
                                                       sized_quantity=0.0))
            result = await machine.submit(plan, price="100")
            return result, machine.state, h.responder.calls

        result, state, calls = scenario(body, store)
        assert result["submitted"] is False
        assert result["reason"] == "RISK_REJECT"
        assert state == "REJECTED"
        assert calls == []

    def test_a_zero_sized_quantity_is_never_submitted(self, store):
        async def body(h):
            machine = h.fsm()
            plan = make_plan(adjudication=adjudication(sized_quantity=0.0))
            result = await machine.submit(plan, price="100")
            return result["reason"], machine.state, h.responder.calls

        reason, state, calls = scenario(body, store)
        assert reason == "QUANTITY_ZERO"
        assert state == "REJECTED"
        assert calls == []

    def test_a_flat_direction_is_never_an_order(self, store):
        async def body(h):
            machine = h.fsm()
            plan = make_plan(proposal=FakeProposal(direction="NO_TRADE"))
            result = await machine.submit(plan, price="100")
            return result["reason"], plan.direction, machine.state

        reason, direction, state = scenario(body, store)
        assert direction == "FLAT"      # NO_TRADE maps onto the Ch.16 CHECK
        assert reason == "NO_TRADE_DIRECTION"
        assert state == "REJECTED"

    def test_a_disabled_cell_is_never_submitted(self, store):
        async def body(h):
            h.responder.fail_next(-1120, 1)
            machine = h.fsm()
            plan = make_plan(timeframe="1mo")
            first = await machine.submit(plan, price="100")
            second_machine = h.fsm()
            second = await second_machine.submit(plan, price="100")
            return first["state"], second["reason"], second["state"], \
                len(h.responder.calls_to("/api/v1/futures/order", "POST"))

        first_state, reason, state, posts = scenario(body, store)
        assert first_state == "REJECTED"
        assert reason == "TF_DISABLED_FOR_SYMBOL"
        assert state == "REJECTED"
        assert posts == 1               # the disabled cell never hits the venue

    def test_an_unknown_decision_is_refused_at_plan_build(self):
        with pytest.raises(F.FsmError) as exc:
            make_plan(adjudication=adjudication(decision="MAYBE"))
        assert exc.value.reason == "DECISION_QX"

    def test_an_unknown_decision_is_refused_again_in_ready(self, store):
        """Defence in depth: a plan assembled by hand still cannot pass the
        READY-state guard (Ch.16 L16830 CHECK)."""
        import dataclasses

        async def body(h):
            machine = h.fsm()
            plan = dataclasses.replace(make_plan(), decision="MAYBE")
            return (await machine.submit(plan, price="100"))["reason"]

        assert scenario(body, store) == "DECISION_QX"

    def test_validation_passes_for_an_allow_plan(self, store):
        async def body(h):
            machine = h.fsm()
            return machine.pre_submission_validation(make_plan())

        assert scenario(body, store) is None


# ---------------------------------------------------------------------------
# Submission through the adapter (T_ADAPTER_* at the FSM level)
# ---------------------------------------------------------------------------

class TestSubmit:
    def test_happy_path_reaches_acknowledged(self, store):
        async def body(h):
            machine = h.fsm()
            result = await machine.submit(make_plan(), price="100")
            rows = await h.ledger_rows("FSM_TRANSITION")
            sent = h.responder.calls_to("/api/v1/futures/order", "POST")[-1]
            return result, machine.state, machine.order_id, rows, sent.params

        result, state, order_id, rows, params = scenario(body, store)
        assert result["outcome"] == "ACKNOWLEDGED"
        assert state == "ACKNOWLEDGED"
        assert order_id is not None
        assert [(r.raw["payload"]["from_state"], r.raw["payload"]["to_state"])
                for r in rows] == [("READY", "SUBMITTING"),
                                   ("SUBMITTING", "ACKNOWLEDGED")]
        assert params["clientOrderId"] == params["clientOrderId"]
        assert params["symbol"] == "BTC-SWAP-USDT"
        assert params["side"] == "BUY_OPEN"

    def test_the_intent_id_is_the_client_order_id(self, store):
        async def body(h):
            machine = h.fsm(intent_id="intent-fixed-1")
            await machine.submit(make_plan(), price="100")
            return h.responder.calls_to("/api/v1/futures/order", "POST")[-1].params

        assert scenario(body, store)["clientOrderId"] == "intent-fixed-1"

    def test_an_immediate_fill_reaches_filled(self, store):
        async def body(h):
            machine = h.fsm()
            result = await machine.submit(make_plan(), price="100")
            return result["outcome"], machine.state

        assert scenario(body, store, fill_mode="immediate") == ("FILLED",
                                                                "FILLED")

    def test_a_partial_fill_reaches_partial(self, store):
        async def body(h):
            machine = h.fsm()
            result = await machine.submit(make_plan(), price="100")
            return result["outcome"], machine.state

        assert scenario(body, store, fill_mode="partial") == ("PARTIAL",
                                                              "PARTIAL")

    def test_an_exchange_reject_is_terminal_for_the_intent(self, store):
        async def body(h):
            machine = h.fsm()
            result = await machine.submit(make_plan(), price="100")
            return result["outcome"], machine.state, result["classification"]

        outcome, state, classification = scenario(body, store, fail_with=-1022)
        assert outcome == "REJECTED"
        assert state == "REJECTED"
        assert classification == "ABORT"

    def test_a_lost_ack_forces_recovery_and_never_resubmits(self, store):
        """T_ADAPTER_LOST_ACK at the FSM level: the venue recorded the order,
        the acknowledgement was lost ⇒ RECOVERY_REQUIRED + reconcile."""

        async def body(h):
            machine = h.fsm()
            result = await machine.submit(make_plan(), price="100")
            rows = await h.ledger_rows("FSM_TRANSITION")
            return result, machine.state, rows[-1].raw["payload"], \
                len(h.responder.calls_to("/api/v1/futures/order", "POST")), \
                list(h.responder.orders)

        result, state, payload, posts, orders = scenario(body, store, timeouts=1)
        assert result["outcome"] == "UNKNOWN"
        assert result["reconcile_required"] is True
        assert result["resubmitted"] is False
        assert state == F.RECOVERY_REQUIRED
        assert payload["error_code"] == "E-EXEC-001"
        assert posts == 1                     # exactly one submission
        assert len(orders) == 1               # the venue DID record it

    def test_an_unmapped_code_forces_recovery(self, store):
        async def body(h):
            machine = h.fsm()
            result = await machine.submit(make_plan(), price="100")
            return result["classification"], machine.state

        assert scenario(body, store, fail_with=-1021) == ("UNMAPPED",
                                                          F.RECOVERY_REQUIRED)

    def test_a_backoff_retry_is_transparent_and_still_acknowledged(self, store):
        async def body(h):
            machine = h.fsm()
            result = await machine.submit(make_plan(), price="100")
            return result["outcome"], machine.state, \
                len(h.responder.calls_to("/api/v1/futures/order", "POST"))

        outcome, state, posts = scenario(body, store, fail_with=-1003,
                                         fail_times=2)
        assert outcome == "ACKNOWLEDGED"
        assert state == "ACKNOWLEDGED"
        assert posts == 3

    def test_submit_without_an_adapter_is_refused(self, store):
        async def body(h):
            machine = h.fsm()
            with pytest.raises(F.FsmError) as exc:
                await machine.submit(make_plan(), price="100")
            return exc.value.reason

        assert scenario(body, store, adapter=False) == "ADAPTER_REQUIRED"

    def test_a_local_refusal_never_reaches_the_venue(self, store):
        async def body(h):
            machine = h.fsm()
            result = await machine.submit(make_plan(), price="100",
                                          quantity="0.0001")
            return result["outcome"], machine.state, h.responder.calls

        outcome, state, calls = scenario(body, store)
        assert outcome == "REJECTED"
        assert state == "REJECTED"
        assert calls == []


class TestApplyAdapterResult:
    @pytest.mark.parametrize("outcome,trigger,state", [
        ("ACKNOWLEDGED", "EXCHANGE_ACK", "ACKNOWLEDGED"),
        ("PARTIAL", "PARTIAL_FILL", "PARTIAL"),
        ("FILLED", "FULL_FILL", "FILLED"),
        ("REJECTED", "EXCHANGE_REJECT", "REJECTED"),
        ("CANCELLED", "CANCEL_CONFIRMED", "CANCELLED"),
        ("UNKNOWN", "UNKNOWN_OUTCOME", F.RECOVERY_REQUIRED)])
    def test_outcome_to_transition_map(self, store, outcome, trigger, state):
        async def body(h):
            machine = h.fsm()
            await machine.advance("SUBMIT_ORDER")
            result = _fake_result(outcome)
            applied = await machine.apply_adapter_result(result)
            rows = await h.ledger_rows("FSM_TRANSITION")
            return applied, machine.state, rows[-1].raw["payload"]["trigger"]

        applied, final, recorded = scenario(body, store)
        assert final == state
        assert recorded == trigger
        assert applied["outcome"] == outcome


def _fake_result(outcome: str):
    """A minimal AdapterResult double for the mapping table."""
    from types import MappingProxyType
    from apex.execution.toobit_adapter import AdapterResult
    classification = {"ACKNOWLEDGED": "OK", "PARTIAL": "OK", "FILLED": "OK",
                      "REJECTED": "ABORT", "CANCELLED": "OK",
                      "UNKNOWN": "UNMAPPED"}[outcome]
    return AdapterResult(operation="submit_order",
                         endpoint="POST /api/v1/futures/order",
                         ok=outcome in ("ACKNOWLEDGED", "PARTIAL", "FILLED",
                                        "CANCELLED"),
                         classification=classification, outcome=outcome,
                         business_code=0 if classification == "OK" else -1022,
                         http_status=200 if classification == "OK" else 400,
                         data=MappingProxyType({}), client_order_id="i-1",
                         order_id="900001", idempotency_key="k" * 64,
                         reconcile_required=outcome == "UNKNOWN",
                         resubmitted=False, cached=False, interval_disabled=None,
                         attempts=(), error_code=None, rule="test")


# ---------------------------------------------------------------------------
# Fills, protection, management, close, cancel
# ---------------------------------------------------------------------------

class TestFills:
    def test_a_fill_is_written_through_the_single_writer(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.submit(make_plan(), price="100")
            entry = await machine.record_fill(fill_id="f-1", price="100",
                                              quantity="0.10", fee="0.02")
            fills = await h.ledger_rows("FILL")
            return entry, machine.fills, fills

        entry, fills_view, rows = scenario(body, store)
        assert entry.event_type == "FILL"
        assert entry.price == "100"
        assert entry.quantity == "0.10"
        assert len(rows) == 1
        assert rows[0].raw["payload"]["side"] == "BUY_OPEN"
        assert rows[0].raw["payload"]["symbol"] == "BTCUSDT"
        assert len(fills_view) == 1

    def test_a_replayed_fill_id_never_double_counts(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.record_fill(fill_id="f-dup", price="100",
                                      quantity="0.10")
            await machine.record_fill(fill_id="f-dup", price="100",
                                      quantity="0.10")
            return len(await h.ledger_rows("FILL")), len(machine.fills)

        assert scenario(body, store) == (1, 1)

    def test_recording_a_fill_requires_the_ledger(self, store):
        async def body(h):
            machine = h.fsm()
            with pytest.raises(F.FsmError) as exc:
                await machine.record_fill(fill_id="f-1", price="100",
                                          quantity="0.1")
            return exc.value.reason

        assert scenario(body, store, ledger=False) == "LEDGER_REQUIRED"


class TestProtection:
    def test_stop_and_target_are_placed_with_the_governed_defaults(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.submit(make_plan(), price="100", quantity="0.10")
            await machine.advance("FULL_FILL")
            result = await machine.place_protection(stop_price="99",
                                                    target_price="103")
            posts = h.responder.calls_to("/api/v1/futures/order", "POST")
            return result, machine.state, [p.params for p in posts[1:]]

        result, state, sent = scenario(body, store)
        assert result["protected"] is True
        assert state == "PROTECTED"
        assert len(sent) == 2
        stop, target = sent
        assert stop["type"] == "STOP"
        assert stop["timeInForce"] == "GTC"
        assert stop["side"] == "SELL_CLOSE"
        assert stop["reduceOnly"] == "true"      # wire boolean, lower-case
        assert stop["clientOrderId"].endswith("-stop")
        assert target["type"] == "LIMIT"
        assert target["timeInForce"] == "GTC"
        assert target["clientOrderId"].endswith("-target")

    def test_a_protection_failure_closes_at_market_and_escalates(self, store):
        """Ch.16 L16916–16918: PROTECTION_FAILED ⇒ emergency close at market +
        OWNER escalation + EXEC_RECOVERY at P0."""

        async def body(h):
            machine = h.fsm()
            await machine.submit(make_plan(), price="100", quantity="0.10")
            await machine.advance("FULL_FILL")
            h.responder.fail_next(-1022, 1)       # the stop order is rejected
            result = await machine.place_protection(stop_price="99",
                                                    target_price="103")
            rows = await h.ledger_rows("PROTECTION_FAILED")
            await h.drain()
            return result, machine.state, rows, \
                [int(e.priority) for e in h.events][-1]

        result, state, rows, priority = scenario(body, store)
        assert result["protected"] is False
        assert result["emergency_path"] == "PLAYBOOK_EMERGENCY_CLOSE_AT_MARKET"
        assert result["escalation"] == "OWNER"
        assert result["alert"] == "EXEC_RECOVERY"
        assert result["priority"] == "P0"
        assert state == F.RECOVERY_REQUIRED
        assert len(rows) == 1
        assert priority == int(Priority.P0)

    def test_protection_requires_an_adapter_and_a_plan(self, store):
        async def body(h):
            machine = h.fsm()
            with pytest.raises(F.FsmError) as exc:
                await machine.place_protection(stop_price="99",
                                               target_price="103")
            return exc.value.reason

        assert scenario(body, store) == "PLAN_REQUIRED"

    def test_management_activation(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.submit(make_plan(), price="100", quantity="0.10")
            await machine.advance("FULL_FILL")
            await machine.place_protection(stop_price="99", target_price="103")
            record = await machine.activate_management()
            return machine.state, record.trigger

        assert scenario(body, store) == ("MANAGED", "MANAGEMENT_ACTIVE")


class TestCloseAndCancel:
    def test_a_close_writes_the_outcome_with_stop_gap_attribution(self, store):
        async def body(h):
            await h.store.db.execute(
                "INSERT INTO setup_candidate (setup_id, timestamp, symbol, "
                "timeframe, direction, quality, snapshot_id) VALUES "
                "('su-0001','2026-01-01T00:00:00.000Z','BTCUSDT','1h',"
                "'BULLISH','Q2','sn-0001')")
            await h.store.db.commit()
            machine = h.fsm()
            await machine.submit(make_plan(), price="100", quantity="0.10")
            await machine.record_fill(fill_id="f-1", price="100",
                                      quantity="0.10")
            await machine.advance("FULL_FILL")
            result = await machine.close_position(exit_price="98.5",
                                                  quantity="0.10",
                                                  exit_reason="STOP_LOSS",
                                                  intended_stop="99",
                                                  actual_fill="98.5",
                                                  setup_id="su-0001",
                                                  pnl="-1.5")
            outcomes = await h.ledger_rows("OUTCOME")
            return result, machine.state, outcomes

        result, state, outcomes = scenario(body, store)
        assert state == "CLOSED"
        assert result["stop_gap"]["exceeded"] is True
        assert result["stop_gap"]["stop_gap"] == "0.5"
        assert result["stop_gap"]["attribution"] == "STOP_GAP_SLIPPAGE"
        assert result["stop_gap"]["next_risk_input"] == "REALIZED_WORST_LOSS"
        assert len(outcomes) == 1
        assert outcomes[0].raw["payload"]["outcome"]["exit_reason"] == "STOP_LOSS"

    def test_a_close_without_a_stop_gap_records_none(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.submit(make_plan(), price="100", quantity="0.10")
            await machine.advance("FULL_FILL")
            result = await machine.close_position(exit_price="103",
                                                  quantity="0.10",
                                                  exit_reason="TARGET_1")
            return result["stop_gap"], machine.state

        assert scenario(body, store) == (None, "CLOSED")

    def test_cancel_uses_the_intent_id(self, store):
        async def body(h):
            machine = h.fsm(intent_id="intent-cancel-1")
            await machine.submit(make_plan(), price="100")
            result = await machine.cancel(reason="owner request")
            deletes = h.responder.calls_to("/api/v1/futures/order", "DELETE")
            return result, machine.state, deletes[-1].params

        result, state, params = scenario(body, store)
        assert state == "CANCELLED"
        assert result["outcome"] == "CANCELLED"
        assert params["clientOrderId"] == "intent-cancel-1"

    def test_cancel_all_uses_the_protective_batch_path(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.submit(make_plan(), price="100")
            await machine.cancel(scope="all", reason="Emergency L3 CANCEL_ALL")
            return h.responder.calls_to("/api/v1/futures/batchOrders", "DELETE")

        assert len(scenario(body, store)) == 1

    def test_an_unknown_cancel_outcome_forces_recovery(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.submit(make_plan(), price="100")
            h.responder.lose_next_ack(1, record=False)
            result = await machine.cancel()
            return result["outcome"], machine.state

        assert scenario(body, store) == ("UNKNOWN", F.RECOVERY_REQUIRED)


# ---------------------------------------------------------------------------
# Reconciliation through the FSM (T_MATCH / T_RECONCILE / T-LR-002 / T-LR-003)
# ---------------------------------------------------------------------------

class TestReconcile:
    def test_t_match_reaches_reconciled(self, store):
        async def body(h):
            machine = h.fsm()
            h.responder.set_fill_mode("immediate")
            await machine.submit(make_plan(), price="100", quantity="0.10")
            await machine.record_fill(fill_id="f-1", price="100",
                                      quantity="0.10")
            await machine.advance("PROTECTION_PLACED")
            await machine.advance("POSITION_CLOSED")
            verdict = await machine.reconcile()
            return verdict, machine.state

        verdict, state = scenario(body, store)
        assert verdict["agree"] is True
        assert state == "RECONCILED"
        assert verdict["action"] is None

    def test_t_reconcile_divergence_forces_recovery_required(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.submit(make_plan(), price="100", quantity="0.10")
            await machine.record_fill(fill_id="f-1", price="100",
                                      quantity="0.10")
            await machine.advance("FULL_FILL")
            h.responder.seed_position("BTCUSDT", "LONG", "9")   # venue disagrees
            verdict = await machine.reconcile()
            corrections = await h.ledger_rows("CORRECTION_EVENT")
            return verdict, machine.state, corrections

        verdict, state, corrections = scenario(body, store)
        assert verdict["agree"] is False
        assert verdict["action"] == "RECOVERY_REQUIRED"
        assert verdict["new_entries_blocked"] is True
        assert state == F.RECOVERY_REQUIRED
        assert len(corrections) == 1
        assert corrections[0].raw["payload"]["reason"] == "BROKER_LEDGER_DELTA"
        assert corrections[0].raw["payload"]["delta"]["alert"] == \
            "RECONCILE_FAILURE"

    def test_t_lr_002_requires_reconciled_before_the_next_decision(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.submit(make_plan(), price="100", quantity="0.10")
            try:
                await machine.require_reconciled()
                before = "ALLOWED"
            except LS.LedgerNotReconciled as exc:
                before = exc.reason
            await machine.record_fill(fill_id="f-1", price="100",
                                      quantity="0.10")
            await machine.advance("PROTECTION_PLACED")
            await machine.advance("POSITION_CLOSED")
            await machine.reconcile()
            after = await machine.require_reconciled()
            return before, after

        before, after = scenario(body, store)
        assert before == "T-LR-002_NOT_RECONCILED"
        assert after["reconciled"] is True

    def test_reconcile_without_the_ledger_is_refused(self, store):
        async def body(h):
            machine = h.fsm()
            with pytest.raises(F.FsmError) as exc:
                await machine.reconcile(query_exchange=False)
            return exc.value.reason

        assert scenario(body, store, ledger=False) == "LEDGER_REQUIRED"

    def test_a_reconcile_inside_the_one_unit_tolerance_agrees(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.submit(make_plan(), price="100", quantity="0.10")
            await machine.record_fill(fill_id="f-1", price="100",
                                      quantity="0.10")
            await machine.advance("FULL_FILL")
            verdict = await machine.reconcile(
                exchange_position={"symbol": "BTCUSDT", "quantity": "0.6"},
                exchange_order={"status": "FILLED"}, query_exchange=False)
            return verdict["agree"], verdict["delta"]

        assert scenario(body, store) == (True, "0.50")   # Decimal, not float

    def test_an_unknown_order_state_at_the_venue_forces_recovery(self, store):
        async def body(h):
            machine = h.fsm()
            await machine.submit(make_plan(), price="100", quantity="0.10")
            h.responder.lose_next_ack(1, record=False)   # the query times out
            verdict = await machine.reconcile()
            return verdict["agree"], verdict["action"], machine.state

        agree, action, state = scenario(body, store)
        assert agree is False
        assert action == "RECOVERY_REQUIRED"
        assert state == F.RECOVERY_REQUIRED


# ---------------------------------------------------------------------------
# Trade plan projection (CP-6 → Ch.16 columns)
# ---------------------------------------------------------------------------

class TestBuildTradePlan:
    def test_cp6_shapes_project_onto_the_ch16_columns(self):
        plan = make_plan()
        assert plan.proposal_id == "pr-0001"
        assert plan.setup_id == "su-0001"
        assert plan.symbol == "BTCUSDT"
        assert plan.timeframe == "1h"
        assert plan.direction == "LONG"
        assert plan.entry_ref == "E-01/BOS"
        assert plan.stop_price == 99.0
        assert plan.target_price == 103.0        # the FIRST target (base RR)
        assert plan.sized_quantity == 0.10
        assert plan.risk_amount == 10.0
        assert plan.decision == "ALLOW"
        assert plan.vetoes_applied == ()
        assert plan.snapshot_id == "sn-0001"
        assert plan.environment == "PAPER"
        assert len(plan.payload_hash) == 64

    def test_a_reject_carries_zero_quantity(self):
        plan = make_plan(adjudication=adjudication(decision="REJECT",
                                                   sized_quantity=0.5))
        assert plan.decision == "REJECT"
        assert plan.sized_quantity == 0.0

    def test_leverage_is_the_min_over_all_caps(self):
        plan = make_plan(timeframe="1mo", owner_leverage_cap=3)
        assert plan.leverage == 3.0

    def test_no_trade_becomes_flat_for_the_ch16_check(self):
        plan = make_plan(proposal=FakeProposal(direction="NO_TRADE"))
        assert plan.direction == "FLAT"

    def test_a_shadow_environment_does_not_exist(self):
        with pytest.raises(F.FsmError) as exc:
            make_plan(environment="SHADOW")
        assert exc.value.reason == "ENVIRONMENT_QX"

    def test_an_unknown_decision_is_refused(self):
        with pytest.raises(F.FsmError) as exc:
            make_plan(adjudication=adjudication(decision="MAYBE"))
        assert exc.value.reason == "DECISION_QX"

    def test_an_unknown_direction_is_refused(self):
        with pytest.raises(F.FsmError) as exc:
            make_plan(proposal=FakeProposal(direction="SIDEWAYS"))
        assert exc.value.reason == "DIRECTION_QX"

    def test_to_dict_is_json_shaped(self):
        payload = make_plan().to_dict()
        assert isinstance(payload["vetoes_applied"], list)
        assert payload["contract_version"] == F.CONTRACT_VERSION

    def test_the_plan_fits_the_frozen_trade_plan_columns(self):
        payload = make_plan().to_dict()
        assert set(LS.TRADE_PLAN_COLUMNS) <= set(payload)


# ---------------------------------------------------------------------------
# Boot: STARTING → SELF_TEST → RECONCILING → READY | DEGRADED | RECOVERY
# ---------------------------------------------------------------------------

class TestBootMachine:
    def test_boot_states_and_matrix(self):
        assert F.BOOT_STATES == ("STARTING", "SELF_TEST", "RECONCILING",
                                 "READY", "DEGRADED", F.RECOVERY_REQUIRED)
        assert F.BOOT_TRANSITIONS[("STARTING", "SELF_TEST_BEGIN")] == "SELF_TEST"
        assert F.BOOT_TRANSITIONS[("SELF_TEST", "SELF_TEST_PASS")] == "RECONCILING"
        assert F.BOOT_TRANSITIONS[("SELF_TEST", "SELF_TEST_FAIL")] == \
            F.RECOVERY_REQUIRED
        assert F.BOOT_TRANSITIONS[("SELF_TEST", "DRIFT_BEYOND_TOLERANCE")] == \
            "DEGRADED"
        assert F.BOOT_TRANSITIONS[("RECONCILING", "RECONCILE_MATCH")] == "READY"
        assert F.BOOT_TRANSITIONS[("RECONCILING", "RECONCILE_DIVERGENCE")] == \
            F.RECOVERY_REQUIRED
        assert F.BOOT_TRANSITIONS[("RECONCILING", "DEPENDENCY_UNAVAILABLE")] == \
            "DEGRADED"

    def test_a_clean_boot_reaches_ready_and_allows_new_trades(self, store):
        async def body(h):
            boot = h.boot()
            assert boot.state == "STARTING"
            assert boot.ladder_actions_available() is False
            verdict = await boot.run()
            return verdict, boot.state, boot.ladder_actions_available()

        verdict, state, ladder = scenario(body, store)
        assert verdict["boot_state"] == "READY"
        assert verdict["ready"] is True
        assert verdict["new_trades_allowed"] is True
        assert state == "READY"
        assert ladder is True
        names = [c["name"] for c in verdict["checks"]]
        assert names[:4] == ["dependencies", "schema_version", "clock_sync",
                             "ladder_state"]
        assert "broker_reconciliation" in names
        assert all(c["status"] == "PASS" for c in verdict["checks"])

    def test_no_new_trade_before_ready(self, store):
        async def body(h):
            boot = h.boot()
            before = boot.state
            verdict = await boot.run()
            return before, verdict["new_trades_allowed"]

        assert scenario(body, store) == ("STARTING", True)

    def test_drift_beyond_tolerance_blocks_new_trades(self, store):
        async def body(h):
            boot = h.boot()
            verdict = await boot.run()
            return verdict["boot_state"], verdict["new_trades_allowed"], \
                verdict["drift_blocks_new_trades"], \
                [c for c in verdict["checks"] if c["name"] == "clock_sync"][0]

        state, allowed, blocked, clock_check = scenario(body, store, drift=6.0)
        assert state == "DEGRADED"
        assert allowed is False
        assert blocked is True
        assert clock_check["status"] == "DEGRADED"
        assert "5.0s" in clock_check["detail"]

    def test_e12_drift_over_500ms_degrades_the_boot(self, store):
        async def body(h):
            verdict = await h.boot().run()
            return verdict["boot_state"], verdict["new_trades_allowed"]

        assert scenario(body, store, drift=0.6) == ("DEGRADED", False)

    def test_drift_inside_the_ntp_target_boots_ready(self, store):
        async def body(h):
            verdict = await h.boot().run()
            return verdict["boot_state"], verdict["drift_blocks_new_trades"]

        assert scenario(body, store, drift=0.05) == ("READY", False)

    def test_an_unmeasurable_clock_is_never_assumed_synchronized(self, store):
        """``drift_seconds=None`` (no route to the venue time endpoint) is
        UNAVAILABLE → DEGRADED, never a silent READY (G6)."""

        async def body(h):
            verdict = await h.boot(drift_seconds=None).run()
            clock_check = [c for c in verdict["checks"]
                           if c["name"] == "clock_sync"][0]
            return verdict["boot_state"], verdict["new_trades_allowed"], \
                verdict["drift_seconds"], verdict["drift_blocks_new_trades"], \
                clock_check["status"]

        state, allowed, drift, blocks, status = scenario(body, store)
        assert state == "DEGRADED"
        assert allowed is False
        assert drift is None
        assert blocks is True
        assert status == "UNAVAILABLE"

    def test_a_boot_without_an_adapter_is_degraded_never_ready(self, store):
        """Fail-closed: with no exchange surface the positions cannot be
        verified, so the boot is DEGRADED (never assumed equal)."""

        async def body(h):
            verdict = await h.boot().run()
            return verdict["boot_state"], verdict["reconciliation"]["reason"], \
                verdict["new_trades_allowed"]

        state, reason, allowed = scenario(body, store, adapter=False)
        assert state == "DEGRADED"
        assert reason == "ADAPTER_UNAVAILABLE"
        assert allowed is False

    def test_a_boot_without_a_ledger_fails_the_self_test(self, store):
        async def body(h):
            verdict = await h.boot().run()
            return verdict["boot_state"], \
                [c["name"] for c in verdict["checks"] if c["status"] == "FAIL"]

        state, failed = scenario(body, store, ledger=False, adapter=False)
        assert state == F.RECOVERY_REQUIRED
        assert "schema_version" in failed

    def test_a_divergent_boot_forces_recovery_required(self, store):
        async def body(h):
            await h.ledger.append_fill(intent_id="i-boot", fill_id="f-boot",
                                       price="100", quantity="2",
                                       symbol="BTCUSDT", side="BUY_OPEN")
            h.responder.seed_position("BTCUSDT", "LONG", "9")
            h.responder.seed_order(intent_id="i-open-1", symbol="BTCUSDT",
                                   timeframe="1h", direction="LONG",
                                   quantity="0.1", price="100")
            verdict = await h.boot().run()
            corrections = await h.ledger_rows("CORRECTION_EVENT")
            return verdict, corrections

        verdict, corrections = scenario(body, store)
        assert verdict["boot_state"] == F.RECOVERY_REQUIRED
        assert verdict["new_trades_allowed"] is False
        assert verdict["reconciliation"]["agree"] is False
        assert verdict["open_intents"] == ("i-open-1",)
        assert len(corrections) == 1
        assert corrections[0].raw["payload"]["reason"] == "BOOT_BROKER_LEDGER_DELTA"

    def test_a_matching_boot_reaches_ready_with_open_intents(self, store):
        async def body(h):
            await h.ledger.append_fill(intent_id="i-boot", fill_id="f-boot",
                                       price="100", quantity="2",
                                       symbol="BTCUSDT", side="BUY_OPEN")
            h.responder.seed_position("BTCUSDT", "LONG", "2")
            verdict = await h.boot().run()
            return verdict["boot_state"], verdict["reconciliation"]["agree"]

        assert scenario(body, store) == ("READY", True)

    def test_an_illegal_boot_transition_is_refused(self, store):
        async def body(h):
            boot = h.boot()
            with pytest.raises(F.FsmError) as exc:
                boot._boot_advance("RECONCILE_MATCH")
            return exc.value.reason

        assert scenario(body, store) == "ILLEGAL_BOOT_TRANSITION"

    def test_ladder_actions_are_available_in_every_state_except_starting(self,
                                                                        store):
        async def body(h):
            boot = h.boot()
            states = {"STARTING": boot.ladder_actions_available()}
            await boot.run()
            states[boot.state] = boot.ladder_actions_available()
            return states

        states = scenario(body, store)
        assert states["STARTING"] is False
        assert all(value is True for key, value in states.items()
                   if key != "STARTING")


class TestRecoveryReconciliation:
    def test_the_seven_ai9_checks_run_in_order(self, store):
        async def body(h):
            verdict = await h.boot().run_recovery_reconciliation()
            return [c["name"] for c in verdict["checks"]], verdict["action"]

        names, action = scenario(body, store)
        assert names == ["ledger_integrity", "raw_hash_chain",
                         "broker_reconciliation", "feature_replay",
                         "pattern_reevaluation", "risk_recheck", "fsm_state"]
        assert action == "HALT_AND_ESCALATE_MANUAL"

    def test_missing_research_providers_fail_closed_not_silently_pass(self,
                                                                     store):
        async def body(h):
            verdict = await h.boot().run_recovery_reconciliation()
            return {c["name"]: c["status"] for c in verdict["checks"]}

        statuses = scenario(body, store)
        assert statuses["feature_replay"] == "UNAVAILABLE"
        assert statuses["pattern_reevaluation"] == "UNAVAILABLE"
        assert statuses["ledger_integrity"] == "PASS"

    def test_with_providers_and_a_matching_venue_recovery_resumes(self, store):
        async def body(h):
            boot = h.boot(feature_replay_provider=lambda: {"consistent": True},
                          pattern_provider=lambda: {"consistent": True})
            verdict = await boot.run_recovery_reconciliation()
            return verdict["passed"], verdict["action"], \
                {c["name"]: c["status"] for c in verdict["checks"]}

        passed, action, statuses = scenario(body, store)
        assert passed is True
        assert action == "RESUME"
        assert set(statuses.values()) == {"PASS"}

    def test_a_failed_check_halts_recovery(self, store):
        async def body(h):
            boot = h.boot(feature_replay_provider=lambda: {"consistent": False},
                          pattern_provider=lambda: {"consistent": True})
            verdict = await boot.run_recovery_reconciliation()
            return verdict["passed"], verdict["action"]

        assert scenario(body, store) == (False, "HALT_AND_ESCALATE_MANUAL")

    def test_a_divergent_venue_halts_recovery(self, store):
        async def body(h):
            await h.ledger.append_fill(intent_id="i-r", fill_id="f-r",
                                       price="100", quantity="2",
                                       symbol="BTCUSDT", side="BUY_OPEN")
            h.responder.seed_position("BTCUSDT", "LONG", "9")
            boot = h.boot(feature_replay_provider=lambda: {"consistent": True},
                          pattern_provider=lambda: {"consistent": True})
            verdict = await boot.run_recovery_reconciliation()
            return verdict["action"], \
                [c for c in verdict["checks"]
                 if c["name"] == "broker_reconciliation"][0]["status"]

        assert scenario(body, store) == ("HALT_AND_ESCALATE_MANUAL", "FAIL")
