"""CP-13 — governed repair of partial bars (`apex.ops.partial_bar_repair`).

Every venue interaction goes through an injected stub (G9): the LIVE path is
exercised with parsed observations, never the network. CLI exit-mapping tests
call `run_apex._repair_partial` with `APEX_SQLITE_PATH` pointed at tmp and
`REPO_ROOT` redirected at tmp, so the repo's `data/` is never touched.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_apex

from apex.config import Config
from apex.data_catalog.ingest.toobit_public import parse_kline_to_observation
from apex.data_catalog.store import sqlite_store as ss
from apex.identity.hashes import sha256_hex
from apex.ops import bootstrap_service as BS
from apex.ops import partial_bar_repair as PR

HOUR = 3_600_000
T0 = 1_672_531_200_000                      # 2023-01-01T00:00:00.000Z


def run(coro):
    return asyncio.run(coro)


def wire(open_ms, o="100", h="101", l="99", c="100.5", v="10", step=HOUR):
    return [int(open_ms), o, h, l, c, v, int(open_ms) + step - 1]


async def open_store(path):
    store = ss.SQLiteStore(str(path))
    await store.open()
    return store


async def seed(store, open_ms, *, created_iso, symbol="BTCUSDT", tf="1h",
               **ohlcv):
    """Seed one bar with a chosen `created_at` (INSERT-only).

    `raw_observation` is immutable (the frozen UPDATE trigger), so the
    fixture performs the same two INSERTs `ingest_raw` does — same columns,
    same hashes — with the caller's `created_at` instead of `now`.
    """
    obs = parse_kline_to_observation(symbol, tf, wire(open_ms, **ohlcv), 0)
    event_id = store._new_event_id()
    content_hash = obs.content_hash()
    await store.db.execute(
        "INSERT INTO raw_observation "
        "(event_id, as_of, symbol, timeframe, open, high, low, close, "
        " volume, oi, oi_timestamp, oi_state, status, content_hash, "
        " source, availability_time, quality_vector, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (event_id, obs.timestamp, obs.symbol, obs.timeframe,
         str(obs.open), str(obs.high), str(obs.low), str(obs.close),
         str(obs.volume), None, obs.oi_timestamp, "MISSING", obs.status,
         content_hash, obs.source, obs.availability_time, None,
         created_iso))
    await store.db.execute(
        "INSERT INTO market_observation "
        "(observation_id, symbol, timeframe, open_price, high_price, "
        " low_price, close_price, volume, open_interest, open_time, "
        " close_time, retrieved_at, candle_status, quality_state, "
        " source, schema_version, raw_payload_hash) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (f"obs-{event_id}", obs.symbol, obs.timeframe, str(obs.open),
         str(obs.high), str(obs.low), str(obs.close), str(obs.volume),
         "MISSING", obs.timestamp, obs.timestamp, created_iso,
         "CLOSED" if obs.status == "CLOSED" else "PARTIAL",
         "Q0", obs.source, "v1", sha256_hex(content_hash)))
    await store.db.commit()
    return event_id


async def raw_count(store, as_of=None):
    if as_of is None:
        cur = await store.db.execute("SELECT COUNT(*) FROM raw_observation")
    else:
        cur = await store.db.execute(
            "SELECT COUNT(*) FROM raw_observation WHERE as_of=?", (as_of,))
    return (await cur.fetchone())[0]


def live_obs(symbol, tf, open_ms, **ohlcv):
    return parse_kline_to_observation(symbol, tf, wire(open_ms, **ohlcv), 0)


class StubLiveClient:
    """Frozen-parse observations out, recorded calls (never the network)."""

    def __init__(self, rows=None, exc=None):
        self.rows = list(rows or [])
        self.exc = exc
        self.calls = []

    async def get_klines(self, symbol, interval, start_ms, end_ms, limit=None):
        self.calls.append((symbol, interval, int(start_ms), int(end_ms),
                           limit))
        if self.exc is not None:
            raise self.exc
        return list(self.rows)


def write_evidence_f6a(path, symbol, tf, open_ms, store_ohlcv, venue_row):
    payload = {"differs": [{
        "symbol": symbol, "timeframe": tf,
        "open_time": BS._ms_to_iso(open_ms),
        "store": dict(store_ohlcv), "venue": {"raw": list(venue_row)}}]}
    Path(path).write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def write_evidence_f6b(path, symbol, tf, open_ms, store_ohlcv, venue_row,
                       verdict="DIFFERS"):
    payload = {"rows": [{
        "symbol": symbol, "timeframe": tf,
        "open_time": BS._ms_to_iso(open_ms), "verdict": verdict,
        "store": dict(store_ohlcv), "venue": {"raw": list(venue_row)}}]}
    Path(path).write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


STORE_OHLCV = {"open": "100", "high": "101", "low": "99", "close": "100.5",
               "volume": "10"}


# ---------------------------------------------------------------------------
# B1 — candidates (store only)
# ---------------------------------------------------------------------------

class TestFindCandidates:
    def test_finds_only_partial_closed_rows(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                close0 = BS.close_time_ms(T0, "1h")
                e_partial = await seed(store, T0, o="100", h="101", l="99",
                                       c="100.5", v="10",
                                       created_iso=BS._ms_to_iso(T0 + 1_800_000))
                e_closed = await seed(store, T0 + HOUR, o="100", h="101",
                                      l="99", c="100.5", v="10",
                                      created_iso=BS._ms_to_iso(T0 + 2 * HOUR + 3_600_000))
                # Exactly close+5s: strict `<` excludes the boundary itself.
                e_edge = await seed(store, T0 + 2 * HOUR, o="100", h="101",
                                    l="99", c="100.5", v="10",
                                    created_iso=BS._ms_to_iso(close0 + 2 * HOUR + 5_000))
                # close+4s: inside the skew margin, still checked.
                e_skew = await seed(store, T0 + 3 * HOUR, o="100", h="101",
                                    l="99", c="100.5", v="10",
                                    created_iso=BS._ms_to_iso(close0 + 3 * HOUR + 4_000))
                found = await PR.find_candidates(store)
                assert {c["event_id"] for c in found} == {e_partial, e_skew}
                assert e_closed not in {c["event_id"] for c in found}
                assert e_edge not in {c["event_id"] for c in found}
                by_id = {c["event_id"]: c for c in found}
                assert by_id[e_partial]["close_ms"] == close0
            finally:
                await store.close()
        run(scenario())

    def test_cells_filter_restricts_candidates(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                await seed(store, T0, created_iso=BS._ms_to_iso(T0 + 1_000))
                await seed(store, T0, symbol="ETHUSDT",
                           created_iso=BS._ms_to_iso(T0 + 1_000))
                found = await PR.find_candidates(store,
                                                 cells=[("BTCUSDT", "1h")])
                assert [(c["symbol"], c["timeframe"]) for c in found] == [
                    ("BTCUSDT", "1h")]
            finally:
                await store.close()
        run(scenario())


# ---------------------------------------------------------------------------
# B2 — LIVE first, evidence fallback (dry-run)
# ---------------------------------------------------------------------------

class TestLiveAndEvidence:
    def test_live_match_verifies_without_writing(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                await seed(store, T0, created_iso=BS._ms_to_iso(T0 + 1_000))
                client = StubLiveClient([live_obs("BTCUSDT", "1h", T0)])
                report = await PR.run_repair(store, client=client, apply=False)
                assert report["counts"] == {"candidates": 1, "verified": 1,
                                            "corrected": 0, "unrepairable": 0,
                                            "refused": 0}
                row = report["candidates"][0]
                assert row["verdict"] == PR.VERIFIED_CLOSED
                assert row["replacement"] == "VENUE_LIVE"
                # endTime = close - 1, limit small.
                assert client.calls == [
                    ("BTCUSDT", "1h", T0, T0 + HOUR - 1, PR.LIVE_FETCH_LIMIT)]
                assert await raw_count(store) == 1
            finally:
                await store.close()
        run(scenario())

    def test_live_mismatch_corrects_in_dry_run_without_writing(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                await seed(store, T0, created_iso=BS._ms_to_iso(T0 + 1_000))
                client = StubLiveClient([live_obs("BTCUSDT", "1h", T0,
                                                  c="100.9", v="11")])
                report = await PR.run_repair(store, client=client, apply=False)
                row = report["candidates"][0]
                assert row["verdict"] == PR.CORRECTED
                assert row["dry_run"] is True
                assert row["replacement"] == "VENUE_LIVE"
                assert row["store_close"] == "100.5"
                assert row["repl_close"] == "100.9"
                assert await raw_count(store) == 1
                cur = await store.db.execute(
                    "SELECT close FROM raw_observation")
                assert (await cur.fetchone())[0] == "100.5"
            finally:
                await store.close()
        run(scenario())

    def test_live_open_mismatch_is_treated_as_absent(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                await seed(store, T0, created_iso=BS._ms_to_iso(T0 + 1_000))
                # Venue returns the NEXT bar at the bound — not our open.
                client = StubLiveClient(
                    [live_obs("BTCUSDT", "1h", T0 + HOUR)])
                report = await PR.run_repair(store, client=client, apply=False)
                assert report["candidates"][0]["verdict"] == \
                    PR.UNREPAIRABLE_VENUE_WINDOW_PASSED
                assert await raw_count(store) == 1
            finally:
                await store.close()
        run(scenario())

    def test_evidence_f6a_verifies_when_live_absent(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                await seed(store, T0, created_iso=BS._ms_to_iso(T0 + 1_000))
                path = write_evidence_f6a(
                    tmp_path / "store_vs_venue.json", "BTCUSDT", "1h", T0,
                    STORE_OHLCV, wire(T0))
                report = await PR.run_repair(store, client=StubLiveClient([]),
                                             evidence_paths=[path],
                                             apply=False)
                row = report["candidates"][0]
                assert row["verdict"] == PR.VERIFIED_CLOSED
                assert row["replacement"] == \
                    "EVIDENCE_FILE:store_vs_venue.json"
                assert await raw_count(store) == 1
            finally:
                await store.close()
        run(scenario())

    def test_evidence_f6b_differs_reports_correction_dry_run(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                await seed(store, T0, created_iso=BS._ms_to_iso(T0 + 1_000))
                path = write_evidence_f6b(
                    tmp_path / "partial_bar_evidence.json", "BTCUSDT", "1h",
                    T0, STORE_OHLCV, wire(T0, c="100.9", v="11"))
                report = await PR.run_repair(store, client=StubLiveClient([]),
                                             evidence_paths=[path],
                                             apply=False)
                row = report["candidates"][0]
                assert row["verdict"] == PR.CORRECTED
                assert row["dry_run"] is True
                assert row["replacement"] == \
                    "EVIDENCE_FILE:partial_bar_evidence.json"
                assert await raw_count(store) == 1
            finally:
                await store.close()
        run(scenario())

    def test_evidence_store_mismatch_is_refused(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                await seed(store, T0, created_iso=BS._ms_to_iso(T0 + 1_000))
                drifted = dict(STORE_OHLCV, close="999.9")
                path = write_evidence_f6a(
                    tmp_path / "store_vs_venue.json", "BTCUSDT", "1h", T0,
                    drifted, wire(T0, c="100.9"))
                report = await PR.run_repair(store, client=StubLiveClient([]),
                                             evidence_paths=[path],
                                             apply=False)
                row = report["candidates"][0]
                assert row["verdict"] == PR.REFUSED_EVIDENCE_MISMATCH
                assert await raw_count(store) == 1
            finally:
                await store.close()
        run(scenario())


# ---------------------------------------------------------------------------
# B3 — apply (frozen correct_raw) + idempotence
# ---------------------------------------------------------------------------

class TestApply:
    def test_apply_corrects_and_second_apply_is_noop(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                as_of = BS._ms_to_iso(T0)
                event_id = await seed(store, T0,
                                      created_iso=BS._ms_to_iso(T0 + 1_000))
                path = write_evidence_f6a(
                    tmp_path / "store_vs_venue.json", "BTCUSDT", "1h", T0,
                    STORE_OHLCV, wire(T0, c="100.9", v="11"))
                report = await PR.run_repair(store, client=StubLiveClient([]),
                                             evidence_paths=[path], apply=True)
                assert report["candidates"][0]["verdict"] == PR.CORRECTED
                assert "dry_run" not in report["candidates"][0]
                # Original immutable + correction: two raw rows, one as_of.
                assert await raw_count(store, as_of) == 2
                cur = await store.db.execute(
                    "SELECT candle_status FROM market_observation "
                    "WHERE observation_id=?", (f"obs-{event_id}",))
                assert (await cur.fetchone())[0] == "SUPERSEDED"
                cur = await store.db.execute(
                    "SELECT candle_status, close_price FROM market_observation "
                    "WHERE observation_id!=? AND open_time=? "
                    "ORDER BY retrieved_at DESC",
                    (f"obs-{event_id}", as_of))
                status, close = await cur.fetchone()
                assert (status, close) == ("CORRECTED", "100.9")
                cur = await store.db.execute(
                    "SELECT actor, correction_reason FROM raw_revision")
                actor, reason = await cur.fetchone()
                assert actor == PR.REPAIR_ACTOR == "OPS_REPAIR_CP13"
                assert "PARTIAL_BAR_STORED_BEFORE_CLOSE" in reason
                assert BS._ms_to_iso(T0 + 1_000) in reason
                assert BS._ms_to_iso(T0 + HOUR) in reason
                assert "EVIDENCE_FILE:store_vs_venue.json" in reason
                # Engines see exactly the corrected bar (B4 visibility).
                window = await store.get_window("BTCUSDT", "1h", as_of, 5)
                assert len(window) == 1
                assert str(window[0].close) == "100.9"
                # Second --apply: nothing left to repair (idempotent).
                again = await PR.run_repair(store, client=StubLiveClient([]),
                                            evidence_paths=[path], apply=True)
                assert again["counts"]["candidates"] == 0
                assert await raw_count(store, as_of) == 2
            finally:
                await store.close()
        run(scenario())

    def test_apply_verified_writes_nothing(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                await seed(store, T0, created_iso=BS._ms_to_iso(T0 + 1_000))
                client = StubLiveClient([live_obs("BTCUSDT", "1h", T0)])
                report = await PR.run_repair(store, client=client, apply=True)
                assert report["candidates"][0]["verdict"] == PR.VERIFIED_CLOSED
                assert await raw_count(store) == 1
                cur = await store.db.execute(
                    "SELECT COUNT(*) FROM raw_revision")
                assert (await cur.fetchone())[0] == 0
            finally:
                await store.close()
        run(scenario())

    def test_report_filename_shape(self):
        import datetime as dt
        moment = dt.datetime(2026, 9, 16, 12, 0, 0,
                             tzinfo=dt.timezone.utc)
        assert PR.report_filename(moment) == \
            "repair_partial_report_20260916T120000Z.json"


# ---------------------------------------------------------------------------
# B4 — unrepairable (row untouched, listed)
# ---------------------------------------------------------------------------

class TestUnrepairable:
    def test_no_source_leaves_the_row_untouched(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                await seed(store, T0, created_iso=BS._ms_to_iso(T0 + 1_000))
                report = await PR.run_repair(store, client=StubLiveClient([]),
                                             apply=True)
                assert report["counts"] == {"candidates": 1, "verified": 0,
                                            "corrected": 0, "unrepairable": 1,
                                            "refused": 0}
                row = report["candidates"][0]
                assert row["verdict"] == PR.UNREPAIRABLE_VENUE_WINDOW_PASSED
                assert row["replacement"] is None
                assert await raw_count(store) == 1
            finally:
                await store.close()
        run(scenario())


# ---------------------------------------------------------------------------
# B5 — refusals fail closed
# ---------------------------------------------------------------------------

class TestRefusals:
    def test_ohlc_violating_replacement_refused_by_name(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                await seed(store, T0, created_iso=BS._ms_to_iso(T0 + 1_000))
                bad = wire(T0, o="100", h="99", l="98", c="100", v="10")
                path = write_evidence_f6a(
                    tmp_path / "store_vs_venue.json", "BTCUSDT", "1h", T0,
                    STORE_OHLCV, bad)
                report = await PR.run_repair(store, client=StubLiveClient([]),
                                             evidence_paths=[path], apply=True)
                verdict = report["candidates"][0]["verdict"]
                assert verdict == ("REFUSED_OHLC_"
                                   "HIGH_BELOW_MAX_OPEN_CLOSE")
                assert report["counts"]["refused"] == 1
                assert await raw_count(store) == 1
            finally:
                await store.close()
        run(scenario())

    def test_missing_evidence_file_fails_closed(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                await seed(store, T0, created_iso=BS._ms_to_iso(T0 + 1_000))
                with pytest.raises(FileNotFoundError):
                    await PR.run_repair(
                        store, client=StubLiveClient([]),
                        evidence_paths=[str(tmp_path / "absent.json")])
            finally:
                await store.close()
        run(scenario())

    def test_malformed_evidence_json_fails_closed(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                bad = tmp_path / "broken.json"
                bad.write_text("{not json", encoding="utf-8")
                with pytest.raises(ValueError):
                    await PR.run_repair(store, client=StubLiveClient([]),
                                        evidence_paths=[str(bad)])
            finally:
                await store.close()
        run(scenario())


# ---------------------------------------------------------------------------
# CLI — repair-partial exit mapping (hermetic: stubbed LIVE, tmp data dir)
# ---------------------------------------------------------------------------

class TestRepairPartialCli:
    async def _seed_db(self, db_path):
        store = await open_store(db_path)
        try:
            await seed(store, T0, created_iso=BS._ms_to_iso(T0 + 1_000))
        finally:
            await store.close()

    def _patch_cli(self, monkeypatch, tmp_path):
        async def no_live(*args, **kwargs):
            return None
        monkeypatch.setattr(PR, "fetch_live_bar", no_live)
        monkeypatch.setattr(run_apex, "REPO_ROOT", tmp_path)
        monkeypatch.setenv("APEX_SQLITE_PATH", str(tmp_path / "apex.sqlite3"))

    def test_cli_verified_exits_zero_and_writes_report(self, tmp_path,
                                                       monkeypatch, capsys):
        async def scenario():
            await self._seed_db(tmp_path / "apex.sqlite3")
            path = write_evidence_f6a(
                tmp_path / "store_vs_venue.json", "BTCUSDT", "1h", T0,
                STORE_OHLCV, wire(T0))
            code = await run_apex._repair_partial(
                Config(), as_json=False, evidence=[path], apply=False,
                cells=None)
            assert code == run_apex.EXIT_READY == 0
            out = capsys.readouterr().out
            assert "VERIFIED_CLOSED" in out
            assert "verified=1" in out
            reports = list((tmp_path / "data").glob(
                "repair_partial_report_*.json"))
            assert len(reports) == 1
            saved = json.loads(reports[0].read_text(encoding="utf-8"))
            assert saved["counts"]["verified"] == 1
        self._patch_cli(monkeypatch, tmp_path)
        run(scenario())

    def test_cli_apply_corrects_and_exits_zero(self, tmp_path, monkeypatch,
                                               capsys):
        async def scenario():
            await self._seed_db(tmp_path / "apex.sqlite3")
            path = write_evidence_f6a(
                tmp_path / "store_vs_venue.json", "BTCUSDT", "1h", T0,
                STORE_OHLCV, wire(T0, c="100.9", v="11"))
            code = await run_apex._repair_partial(
                Config(), as_json=False, evidence=[path], apply=True,
                cells=None)
            assert code == 0
            assert "corrected=1" in capsys.readouterr().out
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                assert await raw_count(store, BS._ms_to_iso(T0)) == 2
            finally:
                await store.close()
        self._patch_cli(monkeypatch, tmp_path)
        run(scenario())

    def test_cli_unrepairable_exits_degraded(self, tmp_path, monkeypatch,
                                             capsys):
        async def scenario():
            await self._seed_db(tmp_path / "apex.sqlite3")
            code = await run_apex._repair_partial(
                Config(), as_json=False, evidence=None, apply=True,
                cells=None)
            assert code == run_apex.EXIT_DEGRADED == 2
            out = capsys.readouterr().out
            assert "UNREPAIRABLE_VENUE_WINDOW_PASSED" in out
            assert "unrepairable=1" in out
        self._patch_cli(monkeypatch, tmp_path)
        run(scenario())

    def test_cli_refused_exits_degraded(self, tmp_path, monkeypatch, capsys):
        async def scenario():
            await self._seed_db(tmp_path / "apex.sqlite3")
            bad = wire(T0, o="100", h="99", l="98", c="100", v="10")
            path = write_evidence_f6a(
                tmp_path / "store_vs_venue.json", "BTCUSDT", "1h", T0,
                STORE_OHLCV, bad)
            code = await run_apex._repair_partial(
                Config(), as_json=False, evidence=[path], apply=True,
                cells=None)
            assert code == 2
            assert "REFUSED_OHLC_HIGH_BELOW_MAX_OPEN_CLOSE" in \
                capsys.readouterr().out
        self._patch_cli(monkeypatch, tmp_path)
        run(scenario())

    def test_cli_missing_evidence_exits_error(self, tmp_path, monkeypatch,
                                              capsys):
        async def scenario():
            await self._seed_db(tmp_path / "apex.sqlite3")
            code = await run_apex._repair_partial(
                Config(), as_json=False,
                evidence=[str(tmp_path / "absent.json")], apply=False,
                cells=None)
            assert code == run_apex.EXIT_ERROR == 1
            assert "REFUSED" in capsys.readouterr().out
        self._patch_cli(monkeypatch, tmp_path)
        run(scenario())


# ---------------------------------------------------------------------------
# CP-13.1 (ISSUE-CP13-004) — SKIPPED_STILL_OPEN guard on still-open bars
# ---------------------------------------------------------------------------


class TestSkippedStillOpen:
    """The close-time-vs-now guard: a bar that has not closed by
    ``now_ms - SKEW_MARGIN_SECONDS*1000`` is never fetched and never
    repaired, never counts as unrepairable/refused, and is listed with
    ``closes_at`` so the owner sees when it becomes repairable."""

    def test_a_still_open_weekly_bar_skipped_no_live_fetch(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                assert PR.CONTRACT_VERSION == "4.1.0"
                assert PR.VERDICT_SKIPPED_STILL_OPEN == "SKIPPED_STILL_OPEN"
                close0 = BS.close_time_ms(T0, "1w")
                await seed(store, T0, tf="1w",
                           created_iso=BS._ms_to_iso(T0 + 1_000))
                client = StubLiveClient([])
                report = await PR.run_repair(store, client=client,
                                             apply=False,
                                             now_ms=T0 + 1_000)
                row = report["candidates"][0]
                assert row["verdict"] == PR.VERDICT_SKIPPED_STILL_OPEN
                assert row["closes_at"] == BS._ms_to_iso(close0)
                assert row["replacement"] is None
                counts = report["counts"]
                assert counts["candidates"] == 1
                assert counts["skipped_still_open"] == 1
                assert counts["unrepairable"] == 0
                assert counts["refused"] == 0
                assert counts["verified"] == 0
                assert counts["corrected"] == 0
                assert client.calls == []
            finally:
                await store.close()
        run(scenario())

    def test_b_after_close_plus_skew_processed_normally(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                close0 = BS.close_time_ms(T0, "1w")
                await seed(store, T0, tf="1w",
                           created_iso=BS._ms_to_iso(T0 + 1_000))
                client = StubLiveClient([live_obs("BTCUSDT", "1w", T0)])
                report = await PR.run_repair(store, client=client,
                                             apply=False,
                                             now_ms=close0 + 5_000)
                row = report["candidates"][0]
                assert row["verdict"] == PR.VERIFIED_CLOSED
                assert row["replacement"] == "VENUE_LIVE"
                assert "closes_at" not in row
                counts = report["counts"]
                assert counts["verified"] == 1
                assert "skipped_still_open" not in counts
                assert client.calls == [
                    ("BTCUSDT", "1w", T0, close0 - 1, PR.LIVE_FETCH_LIMIT)]
            finally:
                await store.close()
        run(scenario())

    def test_c_close_within_skew_window_before_now_is_still_open(
            self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                close0 = BS.close_time_ms(T0, "1h")
                await seed(store, T0, created_iso=BS._ms_to_iso(T0 + 1_000))
                client = StubLiveClient([live_obs("BTCUSDT", "1h", T0)])
                # Close inside the 5 s skew window before now (and 4 s in
                # the future) is treated as still open — no fetch at all.
                for now_ms in (close0 - 4_000, close0 + 3_000, close0 + 4_999):
                    report = await PR.run_repair(store, client=client,
                                                 apply=False, now_ms=now_ms)
                    assert report["candidates"][0]["verdict"] == \
                        PR.VERDICT_SKIPPED_STILL_OPEN
                    assert report["counts"]["skipped_still_open"] == 1
                assert client.calls == []
                # The exact boundary is NOT skipped (strict >).
                report = await PR.run_repair(store, client=client,
                                             apply=False,
                                             now_ms=close0 + 5_000)
                assert report["candidates"][0]["verdict"] == \
                    PR.VERIFIED_CLOSED
                assert report["counts"]["verified"] == 1
                assert client.calls == [
                    ("BTCUSDT", "1h", T0, close0 - 1, PR.LIVE_FETCH_LIMIT)]
            finally:
                await store.close()
        run(scenario())

    def test_d_apply_skipped_row_writes_nothing(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                await seed(store, T0, tf="1w",
                           created_iso=BS._ms_to_iso(T0 + 1_000))
                client = StubLiveClient([])
                report = await PR.run_repair(store, client=client, apply=True,
                                             now_ms=T0 + 1_000)
                assert report["candidates"][0]["verdict"] == \
                    PR.VERDICT_SKIPPED_STILL_OPEN
                assert report["counts"]["skipped_still_open"] == 1
                # --apply semantics: no correct_raw, content byte-identical.
                assert await raw_count(store) == 1
                cur = await store.db.execute(
                    "SELECT close FROM raw_observation")
                assert (await cur.fetchone())[0] == "100.5"
                cur = await store.db.execute(
                    "SELECT candle_status FROM market_observation")
                assert (await cur.fetchone())[0] == "CLOSED"
                cur = await store.db.execute(
                    "SELECT COUNT(*) FROM raw_revision")
                assert (await cur.fetchone())[0] == 0
                assert client.calls == []
            finally:
                await store.close()
        run(scenario())

    def test_e_mixed_run_counts_and_json_round_trip(self, tmp_path):
        async def scenario():
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                close_h2 = BS.close_time_ms(T0 + HOUR, "1h")
                now_ms = close_h2 + 6_000       # past close+skew for both 1h
                await seed(store, T0, symbol="SOLUSDT", tf="1w",
                           created_iso=BS._ms_to_iso(T0 + 1_000))
                await seed(store, T0, symbol="BTCUSDT", tf="1h",
                           created_iso=BS._ms_to_iso(T0 + 1_000))
                await seed(store, T0 + HOUR, symbol="ETHUSDT", tf="1h",
                           created_iso=BS._ms_to_iso(T0 + HOUR + 1_000))
                client = StubLiveClient([
                    live_obs("BTCUSDT", "1h", T0, c="100.9", v="11"),
                    live_obs("ETHUSDT", "1h", T0 + HOUR)])
                report = await PR.run_repair(store, client=client,
                                             apply=False, now_ms=now_ms)
                assert report["counts"] == {
                    "candidates": 3, "verified": 1, "corrected": 1,
                    "unrepairable": 0, "refused": 0, "skipped_still_open": 1}
                by_symbol = {row["symbol"]: row
                             for row in report["candidates"]}
                assert by_symbol["SOLUSDT"]["verdict"] == \
                    PR.VERDICT_SKIPPED_STILL_OPEN
                assert by_symbol["SOLUSDT"]["replacement"] is None
                assert by_symbol["SOLUSDT"]["closes_at"] == \
                    BS._ms_to_iso(BS.close_time_ms(T0, "1w"))
                assert by_symbol["BTCUSDT"]["verdict"] == PR.CORRECTED
                assert by_symbol["BTCUSDT"]["dry_run"] is True
                assert by_symbol["ETHUSDT"]["verdict"] == PR.VERIFIED_CLOSED
                assert len(client.calls) == 2
                assert {call[0] for call in client.calls} == {
                    "BTCUSDT", "ETHUSDT"}
                assert json.loads(json.dumps(report, default=str)) == report
            finally:
                await store.close()
        run(scenario())

    def test_f_cli_summary_skipped_and_exit_ready_when_only_skipped(
            self, tmp_path, monkeypatch, capsys):
        async def scenario():
            import time as _time
            # A 1w bar opened one day ago at wall clock: it is the CURRENT
            # still-open bar for ~6 more days, whatever the sandbox date is.
            open_ms = int(_time.time() * 1000) - 86_400_000
            store = await open_store(tmp_path / "apex.sqlite3")
            try:
                await seed(store, open_ms, tf="1w",
                           created_iso=BS._ms_to_iso(open_ms + 1_000))
            finally:
                await store.close()

            async def live_must_not_be_called(*args, **kwargs):
                raise AssertionError(
                    "live fetch must not run for still-open bars")

            monkeypatch.setattr(PR, "fetch_live_bar", live_must_not_be_called)
            code = await run_apex._repair_partial(
                Config(), as_json=False, evidence=None, apply=True,
                cells=None)
            assert code == run_apex.EXIT_READY == 0
            out = capsys.readouterr().out
            assert "verdict=SKIPPED_STILL_OPEN" in out
            assert "closes_at=" in out
            assert "skipped_still_open=1" in out
            assert "corrected=0" in out
            reports = list((tmp_path / "data").glob(
                "repair_partial_report_*.json"))
            assert len(reports) == 1
            saved = json.loads(reports[0].read_text(encoding="utf-8"))
            assert saved["counts"]["skipped_still_open"] == 1
            assert saved["counts"]["corrected"] == 0
            row = saved["candidates"][0]
            assert row["verdict"] == "SKIPPED_STILL_OPEN"
            assert row["replacement"] is None
            assert row["closes_at"] == BS._ms_to_iso(open_ms + 604_800_000)
        monkeypatch.setattr(run_apex, "REPO_ROOT", tmp_path)
        monkeypatch.setenv("APEX_SQLITE_PATH", str(tmp_path / "apex.sqlite3"))
        run(scenario())
