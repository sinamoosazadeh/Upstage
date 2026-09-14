"""CP-8 integration — the AI.10 adapter-conformance harness against REAL CP-7
objects: the ``ToobitAdapter`` submit seam and the in-repo fake responder.

T-AD-002 (idempotency) is exercised here end-to-end because the research plane
must not own an exchange seam: the harness supplies the retry key, the CP-7
adapter answers duplicates from its own cache and the fake responder counts the
actual venue submissions. T-AD-001 (legacy export translation) runs the
synthetic legacy cases through the real E05/E06 adapters.
"""
from __future__ import annotations

import asyncio

import pytest

from apex.config import Config
from apex.execution.toobit_adapter import ToobitAdapter
from apex.research import adapter_conformance as ac

TEST_KEY = "TEST_KEY_CP8"
TEST_SECRET = "TEST_SECRET_CP8"
CLIENT_ORDER_ID = "intent-cp8-tad002"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def signed_env(monkeypatch):
    monkeypatch.setenv("APEX_ENV", "PAPER")
    monkeypatch.setenv("APEX_ALLOW_SIGNED", "1")
    monkeypatch.setenv("TOOBIT_API_KEY", TEST_KEY)
    monkeypatch.setenv("TOOBIT_API_SECRET", TEST_SECRET)


@pytest.fixture()
def venue():
    from fake_toobit_responder import FakeToobitResponder

    responder = FakeToobitResponder(api_key=TEST_KEY, api_secret=TEST_SECRET,
                                    balance="10000")
    adapter = ToobitAdapter(config=Config(), transport=responder)
    return responder, adapter


# --------------------------------------------------------------------------
# T-AD-002 — the retry key against the real adapter seam
# --------------------------------------------------------------------------

class TestTAd002AdapterSeam:
    def _submit_factory(self, adapter, seen):
        def submit(intent_id: str):
            result = run(adapter.submit_order(
                intent_id=intent_id, symbol="BTCUSDT", timeframe="15m",
                direction="LONG", quantity=1, price=60000,
                order_type="LIMIT"))
            seen.append(result)
            return result.to_dict()

        return submit

    def test_one_hundred_retries_produce_one_venue_order(self, venue):
        responder, adapter = venue
        seen = []
        verdict = ac.t_ad_002(retries=100,
                              submit=self._submit_factory(adapter, seen))
        assert verdict["unique_keys"] == 1
        assert verdict["key_stable"] is True
        assert verdict["new_submissions"] == 1
        assert verdict["cached_hits"] == 99
        assert verdict["no_double_execution"] is True
        assert verdict["passed"] is True

        # the venue itself saw exactly one POST /api/v1/futures/order
        posts = responder.calls_to("/api/v1/futures/order", "POST")
        assert len(posts) == 1
        assert responder.open_order_count() == 1
        # no signature violation anywhere in the retry storm
        assert responder.signature_violations() == []

    def test_duplicate_result_is_flagged_cached_and_not_resubmitted(self, venue):
        responder, adapter = venue
        seen = []
        submit = self._submit_factory(adapter, seen)
        submit(CLIENT_ORDER_ID)
        submit(CLIENT_ORDER_ID)
        assert seen[-1].cached is True
        assert seen[-1].resubmitted is False
        assert seen[-1].order_id == seen[0].order_id
        assert seen[-1].idempotency_key == seen[0].idempotency_key
        assert len(responder.calls_to("/api/v1/futures/order", "POST")) == 1

    def test_the_retry_key_is_a_replay_key_not_the_attempt_index(self):
        common = dict(engine_version="4.0.0", contract_version="4.0.0",
                      symbol="BTCUSDT", timeframe="15m",
                      as_of="2026-08-30T14:00:00Z", input_hash="a" * 64,
                      parameter_package_id="pkg-cp8-0.1.0",
                      code_revision="0" * 40)
        payload = {"intent_id": CLIENT_ORDER_ID, "quantity": 1.0}
        first = ac.stable_retry_key(payload=payload, **common)
        again = ac.stable_retry_key(payload=payload, **common)
        assert first == again
        # any real change of the intent changes the key
        changed = ac.stable_retry_key(payload={**payload, "quantity": 2.0},
                                      **common)
        assert changed != first

    def test_a_lost_ack_is_recorded_on_the_venue_side(self, venue):
        responder, adapter = venue
        responder.lose_next_ack(1)
        seen = []
        submit = self._submit_factory(adapter, seen)
        verdict = ac.t_ad_002(retries=3, submit=submit)
        # the ACK was lost but the order WAS recorded: the retry answers from
        # the adapter cache, so the venue never sees a second order
        assert verdict["unique_keys"] == 1
        posts = responder.calls_to("/api/v1/futures/order", "POST")
        assert len(posts) == 1


# --------------------------------------------------------------------------
# T-AD-001 — legacy export translation through the real adapters
# --------------------------------------------------------------------------

class TestTAd001Synthetic:
    def test_synthetic_cases_pass(self):
        verdict = ac.t_ad_001()
        assert verdict["test"] == "T-AD-001"
        assert verdict["passed"] is True
        assert verdict["failures"] == []
        assert verdict["synthetic_cases"] == len(ac.synthetic_legacy_cases())
        assert all(row["read_only"] is True for row in verdict["results"])

    def test_every_case_is_translated_and_none_invented(self):
        cases = ac.synthetic_legacy_cases()
        report = ac.run_legacy_export(cases)
        assert len(cases) >= 2
        assert report["translated"] == len(cases)
        assert report["data_loss"] == 0
        assert report["failures"] == []

    def test_the_real_data_gate_stays_open_without_an_export(self):
        gate = ac.t_ad_001()["real_data_gate"]
        assert gate["gate"] == "G-ADAPTER-001"
        assert gate["status"] == "OPEN/UNVERIFIED"
        assert gate["samples_supplied"] == 0
        assert gate["required_samples"] == ac.G_ADAPTER_SAMPLE_REQUIREMENT == 100

    def test_a_short_owner_export_is_processed_but_the_gate_stays_open(
            self, tmp_path):
        import json
        path = tmp_path / "legacy_export.json"
        path.write_text(json.dumps(ac.synthetic_legacy_cases()))
        gate = ac.t_ad_001(export_path=str(path))["real_data_gate"]
        # every supplied record translated without loss, yet < 100 samples
        assert gate["samples_supplied"] == len(ac.synthetic_legacy_cases())
        assert gate["translated"] == gate["samples_supplied"]
        assert gate["status"] == "OPEN/UNVERIFIED"

    def test_a_corrupt_export_record_is_reported_not_hidden(self, tmp_path):
        import json
        path = tmp_path / "legacy_export.json"
        path.write_text(json.dumps([
            {"engine_id": "E05", "version": "v3", "ftype": "NOPE"},
            {"engine_id": "E99", "version": "v2", "ftype": "BULLISH_FVG"}]))
        gate = ac.t_ad_001(export_path=str(path))["real_data_gate"]
        assert gate["translated"] == 0
        assert len(gate["failures"]) == 2
        assert gate["status"] == "OPEN/UNVERIFIED"

    def test_absent_export_path_is_refused(self, tmp_path):
        with pytest.raises(ac.AdapterConformanceError) as err:
            ac.t_ad_001(export_path=str(tmp_path / "missing.json"))
        assert err.value.reason == "EXPORT_PATH_ABSENT"

    def test_summary_names_the_engines_and_the_rename(self):
        summary = ac.conformance_summary()
        assert set(summary["engine_adapters"]) == {"E05", "E06"}
        assert ac.rename_registry_entry("order_book_imbalance") == "obi_proxy"
        assert ac.rename_registry_entry("atr_zscore") == "atr_zscore"
        assert summary["real_data_requirement"] == 100
