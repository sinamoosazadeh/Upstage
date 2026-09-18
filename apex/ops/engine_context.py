"""CP-14 store-context boundary helpers (Section 9.5 P1/P2/P7).

Artifact validation is lazy: missing classifier parameters never prevent boot,
status, bootstrap, or repair. PAPER accounting reads environment-tagged ledger
outcomes only. Freshness is a wiring measurement, not a reinterpretation of
raw availability_time. D22 catch-up admission is a separate concern.
"""
from __future__ import annotations

import hashlib
import math
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

from apex.config import Config, PARAMS_DIR, PARAMS_FILES, _YamlSubsetParser, load_params
from apex.data_catalog.contracts import parse_utc_ms
from apex.engines.e11_regime import engine as E11
from apex.identity.canonical_json import canonical_json
from apex.ops.bootstrap_service import close_time_ms
from apex.ops.plan_bridge import BridgeError

ENGINE_ORDER = ("E01", "E02", "E12", "E04", "E03", "E10", "E09", "E05",
                "E06", "E11", "E07", "E08")
DEFAULT_TRAINING_SEED = 20260917


def classifier_hash(W: Any, b: Any, seed: int) -> str:
    return hashlib.sha256(canonical_json(
        {"W": W, "b": b, "seed": seed}).encode("utf-8")).hexdigest()


def validate_classifier(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """P2: validate the complete artifact before any E11 computation."""
    required = {"W", "b", "K", "label_delay_candles", "seed", "training_window",
                "sample_count", "training_query_sha256", "artifact_sha256"}
    try:
        if not isinstance(artifact, Mapping) or set(artifact) != required:
            raise ValueError("artifact schema")
        if artifact["K"] != 9 or artifact["label_delay_candles"] != 48:
            raise ValueError("K or label delay")
        if type(artifact["seed"]) is not int:
            raise ValueError("seed")
        if type(artifact["sample_count"]) is not int or artifact["sample_count"] <= 0:
            raise ValueError("sample_count")
        W = np.asarray(artifact["W"], dtype=float)
        b = np.asarray(artifact["b"], dtype=float)
        if W.shape != (9, 8) or b.shape != (9,):
            raise ValueError("W/b shape")
        if not np.isfinite(W).all() or not np.isfinite(b).all():
            raise ValueError("non-finite W/b")
        window = artifact["training_window"]
        if set(window) != {"start", "end"}:
            raise ValueError("training_window")
        if parse_utc_ms(window["start"]) > parse_utc_ms(window["end"]):
            raise ValueError("reversed training_window")
        query_hash = artifact["training_query_sha256"]
        if not isinstance(query_hash, str) or len(query_hash) != 64 or any(
                c not in "0123456789abcdef" for c in query_hash):
            raise ValueError("training_query_sha256")
        if classifier_hash(artifact["W"], artifact["b"], artifact["seed"]) != artifact["artifact_sha256"]:
            raise ValueError("artifact_sha256 mismatch")
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", f"E11 {exc}") from exc
    return dict(artifact)


def load_classifier(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path is not None else PARAMS_DIR / "e11_classifier_v1.yaml"
    try:
        artifact = _YamlSubsetParser(path.read_text(encoding="utf-8")).parse()
    except (OSError, ValueError) as exc:
        # Do not print paths, file contents, or untrusted YAML in a refusal.
        raise BridgeError("CONFIGURATION_INVALID", "E11 artifact missing or unreadable") from exc
    return validate_classifier(artifact)


def freshness(window: Any, timeframe: str, *,
              receipt_time: float | None = None) -> dict[str, Any]:
    """D14 exact seconds and iff; never mutate a MarketObservation."""
    if window is None or len(window) == 0:
        raise BridgeError("NO_MARKET_DATA", "empty CLOSED candle window")
    receipt = time.time() if receipt_time is None else float(receipt_time)
    if not math.isfinite(receipt):
        raise BridgeError("CONFIGURATION_INVALID", "non-finite receipt time")
    open_ms = int(parse_utc_ms(window[-1].timestamp).timestamp() * 1000)
    closed = close_time_ms(open_ms, timeframe)
    staleness = max(0.0, receipt - closed / 1000.0)
    sla = float(load_params()["quality_weights"]["freshness_threshold_seconds"][timeframe])
    return {"staleness_seconds": staleness, "freshness_sla_seconds": sla,
            "freshness_ok": staleness <= sla,
            "receipt_time_ms": int(receipt * 1000), "close_time_ms": closed}


def load_paper_account() -> dict[str, Any]:
    account = load_params()["paper_account"]
    try:
        if set(account) != {"capital_usdt", "simulated_margin"}:
            raise ValueError("paper account schema")
        capital = Decimal(str(account["capital_usdt"]))
        if not capital.is_finite() or capital <= 0:
            raise ValueError("paper capital")
        margin = account["simulated_margin"]
        if set(margin) != {"warning_fraction", "action_fraction",
                           "liquidation_approach_fraction"}:
            raise ValueError("simulated margin schema")
        values = [float(margin[k]) for k in ("warning_fraction", "action_fraction",
                                            "liquidation_approach_fraction")]
        if not 1 >= values[0] > values[1] > values[2] >= 0:
            raise ValueError("simulated margin ordering")
    except (ValueError, TypeError, KeyError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", "invalid PAPER account") from exc
    return account


async def paper_balance(ledger: Any) -> Decimal:
    """D4: YAML capital plus realized PAPER P/L, never LIVE outcomes.

    OUTCOME is the existing LedgerWriter.append_outcome envelope. No ledger
    schema or execution-stage change is needed for this read-only projection.
    """
    total = Decimal(str(load_paper_account()["capital_usdt"]))
    for entry in await ledger.read_ledger():
        if entry.event_type != "OUTCOME":
            continue
        outcome = entry.raw.get("payload", {}).get("outcome", {})
        environment = outcome.get("context", {}).get("environment")
        if environment not in ("PAPER", "LIVE", "RESEARCH", "BACKTEST"):
            raise BridgeError("CONFIGURATION_INVALID", "outcome environment unavailable")
        if environment != "PAPER":
            continue
        amount = entry.raw.get("pnl")
        if amount in (None, ""):
            raise BridgeError("CONFIGURATION_INVALID", "PAPER realized P/L unavailable")
        delta = Decimal(str(amount))
        if not delta.is_finite():
            raise BridgeError("CONFIGURATION_INVALID", "non-finite PAPER realized P/L")
        total += delta
    return total


def _paper_decimal(value: Any, name: str, *, positive: bool = False) -> Decimal:
    try:
        if value is None or isinstance(value, bool):
            raise ValueError("missing number")
        number = Decimal(str(value))
        if not number.is_finite() or (positive and number <= 0):
            raise ValueError("invalid number")
        return number
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise BridgeError("PAPER_MARGIN_INPUT_INVALID", name) from exc


def paper_reservation_proxy(*, capital: Any, positions: list[dict], orders: list[dict],
                            environment: str) -> dict:
    """D29, also binding on CP-15's durable-state adapter. No leverage input.

    Positions carry signed quantity, mark_price and contract_multiplier.
    Orders carry known state, reduce_only/is_risk_increase, submitted and
    filled quantities, reference_price and contract_multiplier. All are facts,
    not permissions or synthetic defaults. Exposure caps are evaluated elsewhere.
    """
    from apex.risk.kernel import margin_health_state
    if environment != "PAPER":
        raise BridgeError("PAPER_ACCOUNT_NOT_LIVE", "reservation proxy is PAPER-only")
    C = _paper_decimal(capital, "capital", positive=True)
    open_notional = Decimal(0)
    for position in positions:
        quantity = _paper_decimal(position.get("quantity"), "position quantity")
        if quantity == 0:
            continue
        price = _paper_decimal(position.get("mark_price"), "position mark", positive=True)
        multiplier = _paper_decimal(position.get("contract_multiplier"), "contract multiplier", positive=True)
        open_notional += abs(quantity) * price * multiplier
    pending = Decimal(0)
    active = {"SUBMITTING", "ACKNOWLEDGED", "PARTIAL"}
    filled = {"FILLED", "PROTECTED", "MANAGED", "CLOSED"}
    cancelled = {"CANCELLED", "REJECTED"}
    for order in orders:
        state = order.get("state")
        if state not in active | filled | cancelled:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", str(state))
        if type(order.get("reduce_only")) is not bool or type(order.get("is_risk_increase")) is not bool:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "order risk classification missing")
        if order["reduce_only"] or not order["is_risk_increase"] or state in cancelled:
            continue
        quantity = _paper_decimal(order.get("quantity"), "order quantity", positive=True)
        done = _paper_decimal(order.get("filled_quantity"), "filled quantity")
        if not 0 <= done <= quantity:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "inconsistent filled quantity")
        remaining = quantity - done
        if state in filled and remaining != 0:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "full-fill state lacks complete fill records")
        if remaining:
            price = _paper_decimal(order.get("reference_price"), "pending order price", positive=True)
            multiplier = _paper_decimal(order.get("contract_multiplier"), "contract multiplier", positive=True)
            pending += remaining * price * multiplier
    N = open_notional + pending
    health = (C - N) / C
    if not Decimal(0) <= health <= Decimal(1):
        raise BridgeError("PAPER_MARGIN_OUT_OF_RANGE", "reservation exceeds capital; no clipping")
    return {"capital": C, "open_notional": open_notional, "pending_notional": pending,
            "reserved_notional": N, "margin_health_fraction": health,
            "margin_model": "PAPER_RESERVATION_PROXY_D29", "environment": "PAPER",
            "margin_status": margin_health_state(float(health), environment="PAPER")}


async def paper_account_state(ledger: Any, *, marks: Mapping[str, Any],
                              contract_specs: Mapping[str, Mapping], environment: str) -> dict:
    """Read-only D29 projection of the real append-only PAPER ledger.

    No inference of an order's completion from its age, no leverage discount,
    no unidentified fill, no PAPER capital in LIVE. Marks are supplied by the
    governed fresh CLOSED data-plane reader, not entry-price fallbacks.
    """
    if environment != "PAPER":
        raise BridgeError("PAPER_ACCOUNT_NOT_LIVE", "ledger projection is PAPER-only")
    if ledger is None:
        raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "ledger not bound")
    entries = await ledger.read_ledger()
    plans = await ledger.trade_plans()
    identities = {}
    for plan in plans:
        for key in {plan["proposal_id"], "i-" + plan["proposal_id"][-12:]}:
            if key in identities and identities[key]["proposal_id"] != plan["proposal_id"]:
                raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "ambiguous execution identity")
            identities[key] = plan
    transitions, submissions, environments = {}, {}, {}
    for entry in entries:
        if entry.event_type != "FSM_TRANSITION":
            continue
        payload = entry.raw.get("payload", {})
        env = payload.get("environment")
        if env not in ("PAPER", "LIVE", "RESEARCH", "BACKTEST"):
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "FSM environment unavailable")
        if entry.intent_id in environments and environments[entry.intent_id] != env:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "FSM environment conflict")
        environments[entry.intent_id] = env
        history = transitions.setdefault(entry.intent_id, [])
        history.append(payload.get("to_state"))
        if payload.get("trigger") == "SUBMIT_ORDER":
            if entry.intent_id in submissions:
                raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "multiple submissions for one intent")
            submissions[entry.intent_id] = payload.get("evidence", {})
    for plan in plans:
        if plan["environment"] != "PAPER" or plan["decision"] == "REJECT":
            continue
        if not any(k in transitions for k in (plan["proposal_id"], "i-" + plan["proposal_id"][-12:])):
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "materialized plan lacks order state")
    net, filled_qty, pnl = {}, {}, []
    for entry in entries:
        payload = entry.raw.get("payload", {})
        if entry.event_type == "OUTCOME":
            env = payload.get("outcome", {}).get("context", {}).get("environment")
            if env not in ("PAPER", "LIVE", "RESEARCH", "BACKTEST"):
                raise BridgeError("PAPER_MARGIN_INPUT_INVALID", "outcome environment unavailable")
            if env == "PAPER":
                pnl.append((entry.timestamp, _paper_decimal(entry.raw.get("pnl"), "realized PAPER P/L")))
        if entry.event_type != "FILL":
            continue
        plan = identities.get(entry.intent_id)
        env = environments.get(entry.intent_id)
        if plan is not None and env != plan["environment"]:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "fill plan/FSM environment mismatch")
        if env is None:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "fill has no environment-tagged order state")
        if env != "PAPER":
            continue
        side, symbol = payload.get("side"), payload.get("symbol")
        if side not in ("BUY_OPEN", "SELL_OPEN", "BUY_CLOSE", "SELL_CLOSE") or not symbol:
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "fill symbol/side missing")
        qty = _paper_decimal(entry.quantity, "fill quantity", positive=True)
        net[symbol] = net.get(symbol, Decimal(0)) + (qty if side.startswith("BUY") else -qty)
        if side.endswith("_OPEN"):
            filled_qty[entry.intent_id] = filled_qty.get(entry.intent_id, Decimal(0)) + qty
    def multiplier(symbol):
        return _paper_decimal(contract_specs.get(symbol, {}).get("contract_multiplier"), "contract multiplier", positive=True)
    positions = [{"symbol": symbol, "quantity": qty, "mark_price": marks.get(symbol),
                  "contract_multiplier": multiplier(symbol)} for symbol, qty in net.items() if qty != 0]
    orders = []
    for intent, history in transitions.items():
        if environments[intent] != "PAPER":
            continue
        state = history[-1]
        if state == "RECONCILED":
            settled = [s for s in history[:-1] if s in ("CLOSED", "CANCELLED", "REJECTED")]
            if not settled:
                raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "reconciled order has no settled origin")
            state = settled[-1]
        submit = submissions.get(intent)
        if submit is None:
            if state in ("REJECTED", "CANCELLED"):
                continue  # explicit pre-submission refusal; no venue order
            raise BridgeError("PAPER_ORDER_STATE_UNAVAILABLE", "submission facts missing")
        symbol = submit.get("symbol")
        # Frozen FSM SUBMIT_ORDER submits phase=entry. Protective/exit orders
        # use the separate reduce-only path and never this entry transition.
        orders.append({"state": state, "symbol": symbol, "reduce_only": False,
                       "is_risk_increase": True, "quantity": submit.get("quantity"),
                       "filled_quantity": filled_qty.get(intent, Decimal(0)),
                       "reference_price": submit.get("price"),
                       "contract_multiplier": multiplier(symbol)})
    capital = Decimal(str(load_paper_account()["capital_usdt"])) + sum((v for _, v in pnl), Decimal(0))
    result = paper_reservation_proxy(capital=capital, positions=positions, orders=orders, environment=environment)
    return {**result, "positions": net, "realized_outcomes": pnl,
            "per_symbol_exposure": {p["symbol"]: abs(p["quantity"]) * _paper_decimal(p["mark_price"], "mark", positive=True)
                                     * p["contract_multiplier"] for p in positions}, "orders": orders}


def training_rule0(vector: Mapping[str, float], *, turbulence: float) -> str:
    """D21(b): the exact ordered training tree, with no entropy branch.

    The 15.5 training threshold is explicitly owner-governed by D21. Runtime
    keeps E11's full tree and its unchanged Section 6 parameters.
    """
    v = vector
    if turbulence >= 15.5 or v["volatility"] >= 0.85:
        return "CRISIS"
    if v["expansion"] >= 0.6 and v["participation"] >= 0.4:
        return "EXPANSION"
    if v["trendiness"] >= 0.6 and v["expansion"] >= 0.5:
        return "TREND_EXPANSION"
    if v["trendiness"] >= 0.6 and v["compression"] >= 0.6:
        return "TREND_CONTRACTION"
    if v["trendiness"] >= 0.6:
        return "TREND"
    if v["compression"] >= 0.6 and v["volatility"] <= 0.4:
        return "COMPRESSION"
    if v["participation"] <= 0.25 and v["liquidity_stability"] <= 0.3:
        return "CHOP"
    return "RANGE"


def delayed_training_labels(rule0: list[str], structural_confirmation: list[bool]
                            ) -> list[str]:
    """D21(c/d): only t whose t+48 is present; no label for the tail."""
    if len(rule0) != len(structural_confirmation):
        raise ValueError("training label/confirmation lengths differ")
    if any(label not in E11.REGIMES or label == "TRANSITION" for label in rule0):
        raise ValueError("rule0 must contain only the eight non-entropy labels")
    return [rule0[t] if any(structural_confirmation[t + 1:t + 49])
            else "TRANSITION" for t in range(max(0, len(rule0) - 48))]


def load_decision_runtime(*, environment: str | None = None) -> dict[str, Any]:
    """D25 governed policy, shared by PAPER/LIVE, never an account source."""
    from apex.data_catalog.contracts import TIMEFRAMES_14
    environment = Config().apex_env if environment is None else environment
    try:
        p = load_params()["decision_runtime"]
        if set(p) - {"paper_bootstrap"} != {"capital_hard_cap_fraction", "p_min_tf", "c_min"}:
            raise ValueError("schema")
        if set(p["p_min_tf"]) != set(TIMEFRAMES_14):
            raise ValueError("timeframes")
        expected = {tf: 0.55 for tf in TIMEFRAMES_14}
        expected.update({"1m": 0.52, "1d": 0.50})
        if p["p_min_tf"] != expected or p["capital_hard_cap_fraction"] != 0.60 or p["c_min"] != 0.50:
            raise ValueError("SL-12/D25 twin mismatch")
        core = {k: v for k, v in p.items() if k != "paper_bootstrap"}
        if environment == "PAPER":
            core["paper_bootstrap"] = validate_paper_bootstrap(p["paper_bootstrap"])
        return core
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", "decision-runtime policy unavailable or invalid") from exc


def validate_paper_bootstrap(section: Any) -> dict[str, Any]:
    """D28: governed YAML values, never a runtime constant-weight fallback."""
    try:
        if not isinstance(section, Mapping) or set(section) != {"arbitration_weights"}:
            raise ValueError("bootstrap schema")
        weights = section["arbitration_weights"]
        if not isinstance(weights, Mapping) or set(weights) != {"quality", "alignment", "recency"}:
            raise ValueError("weights schema")
        if any(type(w) not in (int, float) or not math.isfinite(w) or w < 0 for w in weights.values()):
            raise ValueError("weights must be finite and nonnegative")
        if sum(weights.values()) <= 0:
            raise ValueError("empty weights")
        return {"arbitration_weights": dict(weights)}
    except (ValueError, TypeError, KeyError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", "invalid PAPER bootstrap policy") from exc


def regime_uncertainty_input(state: Mapping[str, Any]) -> float:
    """D27: Ch.8 confidence complement; never raw or normalized entropy."""
    try:
        probs = [float(v) for v in state["probs"]]
        if len(probs) != 9 or not all(math.isfinite(p) and 0 <= p <= 1 for p in probs):
            raise ValueError("invalid probabilities")
        if not math.isclose(sum(probs), 1.0, rel_tol=0.0, abs_tol=E11.EPS):
            raise ValueError("invalid simplex")
        return 1.0 - max(probs)
    except (KeyError, TypeError, ValueError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", "E11 probabilities unavailable or invalid") from exc


def paper_package_binding(*, environment: str, params_dir: str | Path | None = None) -> dict | None:
    """D28 filename-bound canonical YAML values; LIVE never reads bootstrap.

    Canonical bytes = canonical_json({filename: parsed_yaml, ...}).encode('utf-8').
    The optional classifier is included once; no random/time/process inputs.
    """
    if environment != "PAPER":
        return None
    directory = Path(params_dir) if params_dir is not None else PARAMS_DIR
    documents = {}
    try:
        for filename in sorted(set(PARAMS_FILES.values())):
            path = directory / filename
            if filename == "e11_classifier_v1.yaml" and not path.exists():
                continue
            documents[filename] = _YamlSubsetParser(path.read_text(encoding="utf-8")).parse()
        policy = validate_paper_bootstrap(documents["decision_runtime_v1.yaml"]["paper_bootstrap"])
        if "e11_classifier_v1.yaml" in documents:
            validate_classifier(documents["e11_classifier_v1.yaml"])
        digest = hashlib.sha256(canonical_json(documents).encode("utf-8")).hexdigest()
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise BridgeError("CONFIGURATION_INVALID", "governed PAPER package unreadable") from exc
    return {"parameter_package_id": "cp14_paper_bootstrap-v1.0.0-" + digest[:12],
            "package_version": "v1.0.0", "parameter_sha256": digest,
            "parameter_files": sorted(documents), "environment": "PAPER",
            "paper_bootstrap": policy}


def paper_bootstrap_inputs(*, environment: str, family_record: Mapping | None,
                           params_dir: str | Path | None = None) -> dict | None:
    """D28: a verified absent registry row is distinct from a read failure."""
    package = paper_package_binding(environment=environment, params_dir=params_dir)
    if package is None:
        return None
    if family_record is None:
        status, origin = "ACCUMULATING", "NO_REGISTRY_RECORD"
    else:
        status, origin = family_record.get("status"), "SETUP_FAMILY_REGISTRY"
        if status not in ("ACCUMULATING", "PROMOTED", "DEGRADING", "DEMOTED"):
            raise BridgeError("FAMILY_REGISTRY_INVALID", "existing family status is invalid")
    return {"package": package, "family_status": status, "family_status_source": origin,
            "arbitration": {"composite_weights": dict(package["paper_bootstrap"]["arbitration_weights"]),
                            "alignment": "UNAVAILABLE", "recency": "UNAVAILABLE"}}


async def read_family_record(store: Any, family_id: str, as_of: str) -> dict | None:
    """Read owner registry snapshots; never write an ACCUMULATING fallback.

    Existing snapshot quality_state.family_registry maps family_id to a
    record with status. Later snapshots omitting a family do not erase it.
    """
    import json
    parse_utc_ms(as_of)
    rows = await (await store.db.execute(
        "SELECT snapshot_id,vector_quality_state FROM snapshot_pit WHERE "
        "source_state='SETUP_FAMILY_REGISTRY' AND as_of<=? ORDER BY as_of DESC,rowid DESC",
        (as_of,))).fetchall()
    for snapshot_id, payload in rows:
        try:
            registry = json.loads(payload)["family_registry"]
            if not isinstance(registry, dict):
                raise ValueError("registry schema")
            if family_id in registry:
                record = registry[family_id]
                if not isinstance(record, dict) or record.get("status") not in (
                        "ACCUMULATING", "PROMOTED", "DEGRADING", "DEMOTED"):
                    raise ValueError("family schema")
                return {**record, "registry_snapshot_id": snapshot_id}
        except (ValueError, KeyError, TypeError) as exc:
            raise BridgeError("FAMILY_REGISTRY_INVALID", "cannot establish family lifecycle") from exc
    return None


async def collect_public_venue_facts(symbol: str, *, client: Any = None,
                                   now: Callable[[], float] = time.time) -> dict:
    """D28 public exchangeInfo/funding reads only; no signing fallback.

    Only explicit exchangeInfo fields are admitted. In particular, lack of
    commissionRate/takerCommissionRate never authorizes a fixture/default fee.
    """
    if client is None:
        import aiohttp
        from apex.data_catalog.ingest.toobit_public import ToobitPublicClient
        async with aiohttp.ClientSession() as session:
            return await collect_public_venue_facts(symbol, client=ToobitPublicClient(session=session), now=now)
    from apex.execution.toobit_map import to_wire_symbol
    try:
        info = await client.get_exchange_info()
    except Exception as exc:
        raise BridgeError("VENUE_EXCHANGE_INFO_UNAVAILABLE", symbol) from exc
    rows = info.get("symbols") if isinstance(info, Mapping) else None
    if not isinstance(rows, list):
        raise BridgeError("VENUE_CONTRACT_UNAVAILABLE", symbol)
    matches = [r for r in rows if isinstance(r, dict) and r.get("symbol") in (symbol, to_wire_symbol(symbol))]
    if len(matches) != 1:
        raise BridgeError("VENUE_CONTRACT_UNAVAILABLE", symbol)
    record = matches[0]
    def number(value, name, *, positive=False):
        try:
            if isinstance(value, bool) or value is None:
                raise ValueError("missing numeric fact")
            parsed = Decimal(str(value))
            if not parsed.is_finite() or (positive and parsed <= 0):
                raise ValueError("invalid numeric fact")
            return parsed
        except (ValueError, TypeError, ArithmeticError) as exc:
            raise BridgeError("VENUE_" + name + "_UNAVAILABLE", symbol) from exc
    # Do not interpret maker-only commission as the liquidity-taking fee.
    if "takerCommissionRate" in record:
        fee_key, commission = "takerCommissionRate", record["takerCommissionRate"]
    else:
        fee_key, commission = "commissionRate", record.get("commissionRate")
        if isinstance(commission, Mapping):
            fee_key, commission = "commissionRate.takerCommissionRate", commission.get("takerCommissionRate")
    commission = number(commission, "COMMISSION_RATE")
    multiplier = number(record.get("contractMultiplier"), "CONTRACT_MULTIPLIER", positive=True)
    contract_type = record.get("contractType")
    if contract_type not in ("PERPETUAL", "CURRENT_QUARTER", "NEXT_QUARTER", "DELIVERY"):
        raise BridgeError("VENUE_CONTRACT_TYPE_UNAVAILABLE", symbol)
    expiry = record.get("deliveryDate")
    if contract_type == "PERPETUAL":
        if expiry not in (None, 0, "0"):
            raise BridgeError("VENUE_EXPIRY_UNAVAILABLE", "conflicting perpetual expiry")
        expiry_time = None  # explicit PERPETUAL semantics, not absent contract type
    else:
        expiry_ms = number(expiry, "EXPIRY", positive=True)
        if expiry_ms != int(expiry_ms):
            raise BridgeError("VENUE_EXPIRY_UNAVAILABLE", symbol)
        try:
            expiry_time = _ms_to_iso(int(expiry_ms))
        except (ValueError, OverflowError, OSError) as exc:
            raise BridgeError("VENUE_EXPIRY_UNAVAILABLE", symbol) from exc
    try:
        funding, _ = await client.get_funding_rate(symbol)
    except Exception as exc:
        raise BridgeError("VENUE_FUNDING_RATE_UNAVAILABLE", symbol) from exc
    funding = number(funding, "FUNDING_RATE")
    observed_at = _ms_to_iso(int(now() * 1000))
    sources = {"exchange_info": {"endpoint": "/api/v1/exchangeInfo", "record": record},
               "funding": {"endpoint": "/api/v1/futures/fundingRate", "rate": funding}}
    return {"symbol": symbol, "observed_at": observed_at, "commission_rate": commission,
            "funding_rate": funding, "contract_multiplier": multiplier,
            "contract_type": contract_type, "expiry_time": expiry_time,
            "commission_field": fee_key, "sources": sources,
            "source_sha256": hashlib.sha256(canonical_json(sources).encode("utf-8")).hexdigest()}


async def persist_public_venue_facts(store: Any, symbol: str, *, environment: str,
                                    client: Any = None,
                                    now: Callable[[], float] = time.time) -> dict:
    package = paper_package_binding(environment=environment)
    if package is None:
        raise BridgeError("LIVE_GOVERNANCE_UNAVAILABLE", "PAPER publisher is not a LIVE package source")
    refusal = None
    try:
        facts = await collect_public_venue_facts(symbol, client=client, now=now)
        payload, observed_at = {"venue_facts": facts}, facts["observed_at"]
    except BridgeError as exc:
        # Append failure too: a later missing fact must not resurrect an old
        # successful measurement. This never affects another symbol's row.
        refusal = exc
        observed_at = _ms_to_iso(int(now() * 1000))
        payload = {"venue_fact_refusal": {"symbol": symbol, "observed_at": observed_at,
                                          "reason": exc.reason}}
    bound = {"source_state": "PUBLIC_VENUE_FACTS", **payload,
             "parameter_package_id": package["parameter_package_id"]}
    identity = hashlib.sha256(canonical_json(bound).encode("utf-8")).hexdigest()
    exists = await (await store.db.execute("SELECT snapshot_id FROM snapshot_pit WHERE snapshot_id=?", (identity,))).fetchone()
    if exists is None:
        await store.insert_snapshot({"snapshot_id": identity, "as_of": observed_at,
            "symbol_scope": [symbol], "source_state": "PUBLIC_VENUE_FACTS",
            "parameter_package_id": package["parameter_package_id"], "code_version": "CP14-D28-v1",
            "quality_state": payload})
    if refusal is not None:
        raise refusal
    return facts


async def read_public_venue_facts(store: Any, symbol: str, as_of: str) -> dict:
    import json
    parse_utc_ms(as_of)
    rows = await (await store.db.execute(
        "SELECT snapshot_id,vector_quality_state,as_of,parameter_package_id FROM snapshot_pit WHERE source_state='PUBLIC_VENUE_FACTS' "
        "AND symbol_scope=? AND as_of<=? ORDER BY as_of DESC,rowid DESC LIMIT 1", (symbol, as_of))).fetchall()
    try:
        payload = json.loads(rows[0][1])
        bound = {"source_state": "PUBLIC_VENUE_FACTS", **payload, "parameter_package_id": rows[0][3]}
        expected = hashlib.sha256(canonical_json(bound).encode("utf-8")).hexdigest()
        if expected != rows[0][0]:
            raise ValueError("venue facts payload binding mismatch")
        failed = "venue_fact_refusal" in payload
        facts = payload["venue_fact_refusal" if failed else "venue_facts"]
        if facts["observed_at"] != rows[0][2] or facts["symbol"] != symbol or parse_utc_ms(facts["observed_at"]) > parse_utc_ms(as_of):
            raise ValueError("venue facts identity/PIT mismatch")
        if failed:
            raise BridgeError(facts["reason"], symbol)
        if facts["source_sha256"] != hashlib.sha256(canonical_json(facts["sources"]).encode("utf-8")).hexdigest():
            raise ValueError("venue facts source hash mismatch")
        return facts
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise BridgeError("VENUE_FACTS_UNAVAILABLE", symbol) from exc


def participation_input(volume_z: float, oi_z: float | None, oi_state: str) -> dict[str, Any]:
    """Owner D23, shared by training and serve; no imputed OI series."""
    if oi_state not in ("AVAILABLE", "MISSING", "STALE", "INVALID", "DEGRADED"):
        raise BridgeError("CONFIGURATION_INVALID", "unknown OI state")
    if volume_z is None or not math.isfinite(float(volume_z)):
        raise BridgeError("CONFIGURATION_INVALID", "VolumeZ unavailable")
    partial = oi_state != "AVAILABLE"
    if not partial and (oi_z is None or not math.isfinite(float(oi_z))):
        raise BridgeError("CONFIGURATION_INVALID", "AVAILABLE OI lacks OI_z")
    raw = float(volume_z) if partial else 0.6 * float(volume_z) + 0.4 * float(oi_z)
    return {"participation_raw": raw, "oi_state": oi_state,
            "contributing_features": {"participation": "PARTIAL" if partial else "COMPLETE"}}


# Engine namespaces are the authorities; this module only maps their contracts.
from apex.engines.e01_structure import engine as E01
from apex.engines.e02_liquidity import engine as E02
from apex.engines.e03_volume import engine as E03
from apex.engines.e04_volatility import engine as E04
from apex.engines.e05_fvg import engine as E05
from apex.engines.e06_orderblock import engine as E06
from apex.engines.e07_rtm import engine as E07
from apex.engines.e08_wyckoff import engine as E08
from apex.engines.e09_trend import engine as E09
from apex.engines.e10_momentum import engine as E10
from apex.engines.e12_temporal import engine as E12
from apex.ops.bootstrap_service import _iso_to_ms, _ms_to_iso


def closed_engine_window(window: Any, timeframe: str) -> list[Any]:
    """Open-time store observations -> close-boundary engine observations.

    This is an in-memory projection only. CORRECTED current market rows are
    final observations, while their persisted lifecycle remains CORRECTED.
    """
    from dataclasses import replace
    result = []
    for index, obs in enumerate(window):
        if obs.status not in ("CLOSED", "CORRECTED"):
            raise BridgeError("DATA_QUALITY_QX", "non-final candle")
        result.append(replace(obs, timestamp=_ms_to_iso(close_time_ms(
            _iso_to_ms(obs.timestamp), timeframe)), status="CLOSED", sequence=index))
    return result


def _trend_swings(structure: Mapping[str, Any], window: list[Any]) -> list[dict[str, Any]]:
    """E01 HIGH/LOW -> E09 HH/HL/LH/LL, confirmed through t-1 only."""
    indices = {obs.timestamp: i for i, obs in enumerate(window)}
    previous: dict[str, float] = {}
    result = []
    for swing in sorted(structure["swings"], key=lambda s: s["index"]):
        side, price = swing["type"], float(swing["price"])
        old = previous.get(side)
        previous[side] = price
        confirmation = indices[swing["confirmed_at"]]
        if old is None or confirmation >= len(window) - 1:
            continue  # no comparison predecessor / E09's explicit t-1 boundary
        label = ("EQ" if price == old else
                 ("HH" if price > old else "LH") if side == "HIGH" else
                 ("HL" if price > old else "LL"))
        result.append({"idx": swing["index"], "price": price, "type": label,
                       "confirmed_at_idx": confirmation})
    return result


def atr_z_input(state: Any, prior_atr14: list[float]) -> float:
    """D26-A: E04's published ATR14, E11's Method-B lag-one reference.

    No new ATR, lookback/minimum constant, clipping or sigmoid. The caller
    supplies only prior observations of this same symbol/timeframe cell.
    """
    current = float(state.atr14_wilder)
    reference = prior_atr14[-E11.W_180D_H1:]
    mu, sigma = E11.rolling_method_b_reference(current, reference)
    return (current - mu) / (sigma + E11.EPS)



CONFIRMED_SWEEP_EVENT_TYPES = frozenset({"EV_LIQ_005", "EV_LIQ_006"})
SWEEP_PREREQUISITES = frozenset({"P1_valid_level", "P2_penetration", "P3_rejection",
                                "P4_temporal", "P5_data_quality"})


def structure_projection(raw_window: list[Any], symbol: str, timeframe: str) -> dict:
    window = closed_engine_window(raw_window, timeframe)
    if not window:
        raise BridgeError("NO_MARKET_DATA", "empty confirmation window")
    duration = (close_time_ms(_iso_to_ms(raw_window[-1].timestamp), timeframe)
                - _iso_to_ms(raw_window[-1].timestamp)) // 1000
    params = E01.get_params()
    params["tick_size"] = E01.resolve_tick_size(symbol)
    return E01.run_pipeline([E01.observation_to_candle(o, timeframe, duration) for o in window], params)


def structural_confirmation(raw_window: list[Any], symbol: str, timeframe: str, *, result: dict | None = None) -> bool:
    result = structure_projection(raw_window, symbol, timeframe) if result is None else result
    return any(event["candle_index"] == len(raw_window) - 1 and event["event_type"].startswith(
        ("EV_STR_007", "EV_STR_008", "EV_STR_009", "EV_STR_010")) for event in result["events"])


def contiguous_label_horizon(window: list[Any], index: int, timeframe: str) -> bool:
    """Exactly t+48 calendar-aware closes; a retained-row offset is not time."""
    horizon = window[index:index + 49]
    return len(horizon) == 49 and all(
        close_time_ms(_iso_to_ms(a.timestamp), timeframe) == _iso_to_ms(b.timestamp)
        for a, b in zip(horizon, horizon[1:]))


def liquidity_inputs(liquidity: Any) -> dict:
    """D26-B: actual E02 live levels and confirmed retained-window sweeps.

    The native retained-window constant is shared via volume_profile_bars;
    WickOnly and incomplete prerequisite sets never count as sweeps.
    """
    retained = [bar for bar in liquidity.candles[-liquidity.volume_profile_bars:] if bar.is_closed]
    if not retained:
        raise BridgeError("INVALID_E11_HISTORY", "empty CLOSED E02 retained window")
    current = retained[-1].bar_index
    live = [level for level in liquidity.levels.values() if level.fate in ("ACTIVE", "STRENGTHENED")]
    density = age = 0.0
    if len(live) >= 2:
        span = max(level.price for level in live) - min(level.price for level in live)
        if not math.isfinite(span) or span <= 0:
            raise BridgeError("INVALID_E11_FEATURE", "nonpositive live-level price span")
        density = len(live) / span
        age = float(max(current - level.last_touch for level in live))
        if age < 0:
            raise BridgeError("INVALID_E11_FEATURE", "future level touch")
    indices = {bar.bar_index for bar in retained}
    sweeps = [event for event in liquidity.events
              if event.get("event_type") in CONFIRMED_SWEEP_EVENT_TYPES and event.get("at_bar") in indices
              and SWEEP_PREREQUISITES.issubset(event.get("payload", {}).get("prereq", {}))
              and all(event["payload"]["prereq"][key] is True for key in SWEEP_PREREQUISITES)]
    rate = len(sweeps) / len(retained)
    return {"level_density": density, "age_score": age, "sweep_rate": rate,
            "liquidity_raw": density * age / (1.0 + rate)}

def upstream_frame(raw_window: list[Any], symbol: str, timeframe: str,
                   *, emit: bool = False,
                   atr14_history: list[float] | None = None,
                   structure_result: dict | None = None,
                   volatility_stream: dict | None = None) -> dict[str, Any]:
    """P1's first seven engines, in order, with explicit producer projections.

    A 300-bar engine window is the existing paper runtime window. The E11
    normalization history is assembled separately, over all prior frames.
    """
    if not raw_window:
        raise BridgeError("NO_MARKET_DATA", "empty engine window")
    window = closed_engine_window(raw_window, timeframe)
    end = window[-1].timestamp
    duration = (close_time_ms(_iso_to_ms(raw_window[-1].timestamp), timeframe)
                - _iso_to_ms(raw_window[-1].timestamp)) // 1000
    base = {"window": window}
    events = []
    order = []
    def collect(code, cls, context):
        order.append(code)
        if emit:
            events.extend(cls().compute(symbol, timeframe, end, context))

    params = E01.get_params()
    params["tick_size"] = E01.resolve_tick_size(symbol)
    collect("E01", E01.E01StructureEngine, base)
    candles = [E01.observation_to_candle(o, timeframe, duration) for o in window]
    structure = E01.run_pipeline(candles, params) if structure_result is None else structure_result
    bos_events = [ev for ev in structure["events"] if ev["event_type"].startswith(
        ("EV_STR_007", "EV_STR_008"))]
    structural_events = [ev for ev in structure["events"] if ev["event_type"].startswith(
        ("EV_STR_007", "EV_STR_008", "EV_STR_009", "EV_STR_010"))]
    bos = bos_events[-1] if bos_events else None
    collect("E02", E02.E02LiquidityEngine, base)
    liquidity = E02.run_engine([E02.observation_to_candle(o) for o in window])
    collect("E12", E12.E12TemporalEngine, base)
    temporal = E12.run_engine([E12.observation_to_candle(o) for o in window])["temporal_state"]
    order.append("E04")
    bars = [E04.observation_to_bar(o, timeframe) for o in window]
    if volatility_stream is None:
        volatility = E04.run_engine(bars, timeframe=timeframe)
    else:
        # Native chronological E04, never a partial/reimplemented indicator.
        # Drain only observations already reached by this feature timeline.
        for bar in volatility_stream["pending"]:
            evidence = volatility_stream["engine"].ingest_bar(bar)
            if evidence is not None:
                volatility_stream["evidence"].append(evidence)
        volatility_stream["pending"].clear()
        retained = [e for e in volatility_stream["evidence"] if bars[0]["ts"] <= e.state.as_of <= bars[-1]["ts"]]
        volatility = {"engine": volatility_stream["engine"], "states": [e.state for e in retained],
                      "events": [event for e in retained for event in e.events], "atr_series": [e.atr_scalar for e in retained]}
    if emit:
        emitter = E04.E04VolatilityEngine()
        quality = emitter._window_quality(window)
        events.extend(emitter._to_evidence(state, symbol, timeframe, quality) for state in volatility["states"] if state.snapshot_id)
    # D26-A supersedes the provisional ATR20 addition. Consume the actual
    # published E04 schema and align by as_of, not emitted-list position.
    atr_by_close = {state.as_of: state.atr14_wilder for state in volatility["states"]}
    atr14 = [atr_by_close.get(_iso_to_ms(o.timestamp)) for o in window]
    atr_prev = [None] + atr14[:-1]
    volume_context = {**base, "atr_prev": atr_prev,
                      "atr_availability_time_ms": [_iso_to_ms(o.timestamp) for o in window]}
    collect("E03", E03.E03VolumeEngine, volume_context)
    volume_bars = [E03.observation_to_bar(o, timeframe, atr_prev[i], None, _iso_to_ms(o.timestamp))
                   for i, o in enumerate(window)]
    volume = E03.run_engine(volume_bars)
    if not volume.emitted or not volatility["states"]:
        raise BridgeError("INSUFFICIENT_HISTORY", "E03/E04 warmup")
    vol = volume.emitted[-1]
    if volume.history_bars[-1]["ts"] != _iso_to_ms(end):
        raise BridgeError("ENGINE_CONTEXT_UNAVAILABLE", "E03 latest candle unavailable")
    vlt = volatility["states"][-1]
    collect("E10", E10.E10MomentumEngine, {**base, "volatility_context": vars(vlt)})
    momentum = E10.run_engine(bars, symbol=symbol, interval=timeframe,
                             volatility_context=vars(vlt))["state"]
    swings = _trend_swings(structure, window)
    trend_context = {**base, "swings": swings, "atr": vlt.atr14_wilder,
                     "tf_seconds": duration, "bos_event": bos, "oi_state": vol.oi_state}
    collect("E09", E09.E09TrendEngine, trend_context)
    trend = E09.run_engine(bars, swings=swings, atr=vlt.atr14_wilder,
                          tf_seconds=duration, bos_event=bos, oi_state=vol.oi_state)
    # ISSUE-CP14-011 projections are resolved by owner D26-A/B.
    # An explicit empty history is unavailable, never replaced by a fallback.
    prior = ([state.atr14_wilder for state in volatility["states"]
              if state.as_of < _iso_to_ms(end)]
             if atr14_history is None else atr14_history)
    projection_refusals = []
    try:
        atr_z = atr_z_input(vlt, prior)
    except ValueError as exc:
        if not str(exc).startswith("INVALID_E11_HISTORY:"):
            raise
        atr_z = None
        projection_refusals.append("INVALID_E11_HISTORY")
    part = participation_input(vol.volume_z, vol.oi_z, vol.oi_state)
    macro = trend["stack"]["MACRO"]
    raw_trend = sum(weight * (trend["stack"][scale] * macro > 0)
                    for scale, weight in E09.W_STACK_CORRECTED.items())
    is_bos = bool(bos and bos["candle_index"] == len(window) - 1)
    ic = {"trendiness_raw": raw_trend, "vol_ratio": vlt.vol_ratio,
          "expansion_raw": vlt.vol_ratio * is_bos, **liquidity_inputs(liquidity),
          "structure_score": float(bos["strength"]["S"]) if bos else 0.0,
          "momentum_state_raw": E10.momentum_state_projection(momentum)["momentum_state_raw"],
          "atr_z": atr_z, **part}
    return {"window": window, "raw_window": raw_window, "bars": bars, "ic": ic,
            "structure": structure, "structural_events": structural_events,
            "confirmation": any(e["candle_index"] == len(window) - 1 for e in structural_events),
            "liquidity": liquidity, "volume": volume, "volume_bars": volume_bars,
            "volatility": volatility, "vlt": vlt, "atr14": atr14,
            "momentum": momentum, "trend": trend, "temporal": temporal,
            "events": events, "engine_order": order,
            "projection_refusals": projection_refusals}


CELL_QUERY = ("SELECT symbol,timeframe,MAX(open_time),COUNT(*) FROM market_observation "
              "WHERE candle_status IN ('CLOSED','CORRECTED') GROUP BY symbol,timeframe "
              "ORDER BY symbol,timeframe")
TRAINING_QUERY = canonical_json({
    "cell_discovery": CELL_QUERY,
    "window_reader": "SQLiteStore.get_window(symbol,timeframe,as_of,bars)",
    "window_predicate": "candle_status IN (CLOSED,CORRECTED) AND open_time <= as_of",
    "window_order": "last bars by open_time DESC, returned open_time ASC",
    "closed_filter": "close_time_ms(open_time,timeframe) <= as_of",
    "label_boundary": "49 consecutive CLOSED candles t..t+48 with independent E01 confirmation; D21 unchanged",
    "raw_metadata": "immutable observation_id/content hash binding restores availability_time and OI timestamp; availability<=as_of",
    "E04_replay": "native chronological VolatilityEngineV4, each CLOSED observation once; no future-state reuse",
})
HISTORY_KEYS = {"trend": "trendiness_raw", "vol": "vol_ratio", "exp": "expansion_raw",
                "liq": "liquidity_raw", "part": "participation_raw", "sq": "structure_score"}


class EngineContextProducer:
    """Public store-to-bridge seam, with no fixture or network dependency."""
    def __init__(self, store: Any, *, ledger: Any = None,
                 classifier_path: str | Path | None = None, environment: str | None = None,
                 now: Callable[[], float] = time.time) -> None:
        self.store, self.ledger = store, ledger
        self.classifier_path, self.now = classifier_path, now
        self.environment = Config().apex_env if environment is None else environment
        self.diagnostics: dict[str, Any] = {}
        self._frames: dict[tuple, dict] = {}
        self._raw_lineage: dict[tuple, dict] = {}

    async def decision_inputs(self, symbol: str, timeframe: str, as_of: str) -> dict:
        """D28 stored governance/venue inputs; not a fabricated complete context."""
        if self.environment != "PAPER":
            raise BridgeError("LIVE_GOVERNANCE_UNAVAILABLE", "PAPER bootstrap is not a LIVE source")
        from apex.setup.family_sf_fvg_sweep_rev import FAMILY_ID
        record = await read_family_record(self.store, FAMILY_ID, as_of)
        governance = paper_bootstrap_inputs(environment=self.environment, family_record=record)
        venue = await read_public_venue_facts(self.store, symbol, as_of)
        return {**governance, "environment": "PAPER", "commission_rate": venue["commission_rate"],
                "funding_rate": venue["funding_rate"], "venue_provenance": venue,
                "contract_specs": {symbol: {k: venue[k] for k in (
                    "contract_multiplier", "contract_type", "expiry_time")}}}

    async def window(self, symbol: str, timeframe: str, as_of: str, bars: int) -> list[Any]:
        end = _iso_to_ms(as_of)
        window = await self.store.get_window(symbol, timeframe, as_of, bars)
        if window is None:
            raise BridgeError("NO_MARKET_DATA", "store returned no window")
        from dataclasses import replace
        window = [o for o in window if close_time_ms(_iso_to_ms(o.timestamp), timeframe) <= end]
        if not window:
            return []
        # get_window is the authoritative bar reader. Its legacy projection
        # substitutes retrieved_at for raw availability and loses OI lineage.
        # Recover ONLY metadata through the immutable identity, never rewrite
        # a market/raw row or substitute the derived close for raw availability.
        rows = await (await self.store.db.execute(
            "SELECT m.open_time,m.observation_id,m.raw_payload_hash,r.content_hash,"
            "r.availability_time,r.oi_timestamp,r.oi_state FROM market_observation m "
            "JOIN raw_observation r ON m.observation_id='obs-'||r.event_id "
            "WHERE m.symbol=? AND m.timeframe=? AND m.candle_status IN ('CLOSED','CORRECTED') "
            "AND m.open_time>=? AND m.open_time<=? ORDER BY m.open_time",
            (symbol, timeframe, window[0].timestamp, window[-1].timestamp))).fetchall()
        metadata = {}
        for row in rows:
            if row[0] in metadata:
                raise BridgeError("RAW_LINEAGE_INVALID", "ambiguous active observation")
            metadata[row[0]] = row
        result = []
        for obs in window:
            row = metadata.get(obs.timestamp)
            if row is None or row[3] != obs.content_hash() or row[2] != hashlib.sha256(row[3].encode()).hexdigest():
                raise BridgeError("RAW_LINEAGE_INVALID", "observation/raw content binding missing")
            if row[4] is None:
                raise BridgeError("RAW_LINEAGE_INVALID", "raw availability unavailable")
            if _iso_to_ms(row[4]) > end:
                continue  # never expose not-yet-available observations
            oi_lag = (max(0., (end - _iso_to_ms(row[5])) / 1000.) if row[5] is not None else None)
            result.append(replace(obs, availability_time=row[4], oi_timestamp=row[5], oi_lag_seconds=oi_lag))
            self._raw_lineage[(symbol, timeframe, obs.timestamp, obs.content_hash())] = {
                "observation_id": row[1], "oi_state": row[6], "availability_time": row[4]}
        return result

    async def _frame_at(self, symbol: str, timeframe: str, as_of: str) -> dict[str, Any]:
        window = await self.window(symbol, timeframe, as_of, 301)
        if len(window) < 51:
            raise BridgeError("INSUFFICIENT_HISTORY", f"{symbol}:{timeframe}")
        window = window[-300:]
        key = (symbol, timeframe, hashlib.sha256(canonical_json(window).encode()).hexdigest())
        if key not in self._frames:
            self._frames[key] = upstream_frame(window, symbol, timeframe)
            if len(self._frames) > 32:
                del self._frames[next(iter(self._frames))]
        return self._frames[key]

    async def feature_timeline(self, symbol: str, timeframe: str, window: list[Any]):
        """Shared PIT training/runtime X_t stream; explicit warmup refusals.

        HTF bias observations are strictly last-closed as of each historical
        close, never current bias projected backward into a training sample.
        """
        history = {key: [] for key in HISTORY_KEYS}
        atr14_history: list[float] | None = None
        seed_state = E11.RegimeEngine()
        mu, sigma, previous_momentum = seed_state.mu, seed_state.Sigma, seed_state.prev_mom
        volatility_stream = {"engine": E04.VolatilityEngineV4(timeframe=timeframe), "pending": [], "evidence": []}
        for index, obs in enumerate(window):
            as_of = _ms_to_iso(close_time_ms(_iso_to_ms(obs.timestamp), timeframe))
            volatility_stream["pending"].append(E04.observation_to_bar(closed_engine_window([obs], timeframe)[0], timeframe))
            if index < 50:
                yield {"index": index, "as_of": as_of, "reason": "UPSTREAM_WARMUP", "confirmation": False}
                continue
            source_window = window[max(0, index - 299):index + 1]
            if any(o.availability_time is None or _iso_to_ms(o.availability_time) > _iso_to_ms(as_of) for o in source_window):
                yield {"index": index, "as_of": as_of, "confirmation": None, "reason": "PIT_VIOLATION"}
                continue
            structure = structure_projection(source_window, symbol, timeframe)
            confirmation = structural_confirmation(source_window, symbol, timeframe, result=structure)
            try:
                frame = upstream_frame(source_window, symbol, timeframe, atr14_history=atr14_history,
                                       structure_result=structure, volatility_stream=volatility_stream)
                # Advance the independent same-cell ATR reference AFTER its
                # lag-one projection, even while another feature is refused.
                if atr14_history is None:
                    atr14_history = [state.atr14_wilder for state in frame["volatility"]["states"]]
                else:
                    atr14_history.append(frame["vlt"].atr14_wilder)
                atr14_history = atr14_history[-E11.W_180D_H1:]
                if frame.get("projection_refusals"):
                    yield {"index": index, "as_of": as_of, "confirmation": confirmation,
                           "reason": ("INVALID_E11_HISTORY" if "INVALID_E11_HISTORY" in frame["projection_refusals"]
                                      else "E11_PROJECTION_UNCONFIGURED"),
                           "projection_refusals": list(frame["projection_refusals"])}
                    continue
                ic = dict(frame["ic"])
                biases = {}
                for label, tf in (("H4", "4h"), ("H1", "1h"), ("M15", "15m")):
                    htf = frame if tf == timeframe else await self._frame_at(symbol, tf, as_of)
                    biases[label] = float(htf["trend"]["bias"])
                ic["bias_per_TF"] = biases
                ic["trendiness_raw"] = sum(w * (frame["trend"]["stack"][scale] * biases["H4"] > 0)
                                             for scale, w in E09.W_STACK_CORRECTED.items())
            except (BridgeError, ValueError) as exc:
                yield {"index": index, "as_of": as_of,
                       "reason": getattr(exc, "reason", str(exc).split(":")[0]), "confirmation": confirmation}
                continue
            item = {"index": index, "as_of": as_of, "ic": ic, "frame": frame,
                    "volatility_stream": volatility_stream,
                    "confirmation": confirmation, "history": {k: list(v) for k, v in history.items()},
                    "mu": mu.copy(), "Sigma": sigma.copy(), "prev_mom": previous_momentum}
            try:
                vector, bias = E11.compute_state_vector(ic, history, previous_momentum)
                x = E11.vector_to_array(vector)
                turbulence = E11.mahalanobis_turbulence(x, mu, sigma)
                item.update(vector=vector, bias=bias, turbulence=turbulence,
                            rule0=training_rule0(vector, turbulence=turbulence))
                mu, sigma = E11.ewma_update(mu, sigma, x)
                previous_momentum = vector["momentum_state"]
            except ValueError as exc:
                item["reason"] = str(exc).split(":")[0]
            yield item
            # Normalization history can contain finite observations even when
            # its old window was degenerate. No invalid X_t updates the EWMA.
            for key, source in HISTORY_KEYS.items():
                history[key].append(float(ic[source]))
                history[key] = history[key][-E11.W_180D_H1:]


class DegenerateTraining(BridgeError):
    def __init__(self, histogram: dict[str, int], excluded: dict[str, int], window: dict):
        self.histogram, self.excluded, self.training_window = histogram, excluded, window
        self.refusing_class = next(name for name in E11.REGIMES if histogram[name] == 0)
        super().__init__("CONFIGURATION_INVALID", f"zero delayed-label members: {self.refusing_class}")


def fit_multinomial(X: list[list[float]], labels: list[str], seed: int) -> tuple[list, list]:
    """Fixed-order full-batch multinomial log-loss descent, nine classes.

    No class reweighting, synthetic members, dropped classes or runtime random
    weights. The optimizer's seeded initialization exists only during training.
    """
    x = np.asarray(X, dtype=float)
    y = np.array([E11.REGIMES.index(label) for label in labels])
    if x.shape != (len(labels), 8) or not np.isfinite(x).all() or not len(labels):
        raise BridgeError("CONFIGURATION_INVALID", "invalid training matrix")
    if len(set(y.tolist())) != 9:
        raise BridgeError("CONFIGURATION_INVALID", "all nine classes required for fitting")
    rng = np.random.default_rng(seed % (2 ** 128))
    W = rng.normal(0.0, 0.01, (9, 8))
    b = np.zeros(9)
    # Deterministic optimization protocol, recorded in ADR-CP14-004.
    for _ in range(2000):
        z = x @ W.T + b
        z -= np.max(z, axis=1, keepdims=True)
        probabilities = np.exp(z)
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        probabilities[np.arange(len(y)), y] -= 1.0
        gradient_W = probabilities.T @ x / len(y)
        gradient_b = probabilities.mean(axis=0)
        W -= 0.2 * gradient_W
        b -= 0.2 * gradient_b
    if not np.isfinite(W).all() or not np.isfinite(b).all():
        raise BridgeError("CONFIGURATION_INVALID", "non-finite fitted parameters")
    return W.tolist(), b.tolist()


async def train_classifier(store: Any, *, seed: int = DEFAULT_TRAINING_SEED,
                           now: Callable[[], float] = time.time) -> tuple[dict, dict]:
    """Train from actual store windows only. No file or fixture fallback."""
    cells = await (await store.db.execute(CELL_QUERY)).fetchall()
    producer = EngineContextProducer(store, now=now)
    histogram = {name: 0 for name in E11.REGIMES}
    excluded: dict[str, int] = {}
    X, labels, stamps = [], [], []
    end_ms = int(now() * 1000)
    for symbol, timeframe, _, count in cells:
        window = await producer.window(symbol, timeframe, _ms_to_iso(end_ms), int(count))
        if not window:
            excluded["EMPTY_CLOSED_WINDOW"] = excluded.get("EMPTY_CLOSED_WINDOW", 0) + 1
            continue
        pending = []
        async for item in producer.feature_timeline(symbol, timeframe, window):
            # Keep just the 48 delayed candidates, not full engine states.
            pending.append({key: item[key] for key in ("index", "as_of", "confirmation", "vector", "rule0", "reason") if key in item})
            if len(pending) <= 48:
                continue
            candidate = pending.pop(0)
            if "vector" not in candidate:
                reason = candidate.get("reason", "INVALID_FEATURE")
                excluded[reason] = excluded.get(reason, 0) + 1
                continue
            if not contiguous_label_horizon(window, candidate["index"], timeframe):
                excluded["NONCONTIGUOUS_LABEL_HORIZON"] = excluded.get("NONCONTIGUOUS_LABEL_HORIZON", 0) + 1
                continue
            if any(type(f.get("confirmation")) is not bool for f in pending):
                excluded["LABEL_CONFIRMATION_UNAVAILABLE"] = excluded.get("LABEL_CONFIRMATION_UNAVAILABLE", 0) + 1
                continue
            label = candidate["rule0"] if any(f["confirmation"] for f in pending) else "TRANSITION"
            histogram[label] += 1
            labels.append(label)
            X.append([candidate["vector"][key] for key in E11.VECTOR_KEYS])
            stamps.append(candidate["as_of"])
        excluded["UNFINALIZED_TAIL"] = excluded.get("UNFINALIZED_TAIL", 0) + len(pending)
    training_window = {"start": min(stamps) if stamps else None, "end": max(stamps) if stamps else None}
    if any(count == 0 for count in histogram.values()):
        raise DegenerateTraining(histogram, excluded, training_window)
    W, b = fit_multinomial(X, labels, seed)
    artifact = {"W": W, "b": b, "K": 9, "label_delay_candles": 48,
                "seed": seed, "training_window": training_window, "sample_count": len(X),
                "training_query_sha256": hashlib.sha256(TRAINING_QUERY.encode()).hexdigest(),
                "artifact_sha256": classifier_hash(W, b, seed)}
    validate_classifier(artifact)
    return artifact, {"per_class_counts": histogram, "excluded": excluded}


def write_classifier(artifact: dict[str, Any], path: str | Path) -> None:
    """Deterministic supported YAML; atomic replacement only after validation."""
    import json
    import os
    import tempfile
    validate_classifier(artifact)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = "W:\n" + "".join("  - " + json.dumps(row, separators=(",", ":")) + "\n" for row in artifact["W"])
    for key in ("b", "K", "label_delay_candles", "seed"):
        text += key + ": " + json.dumps(artifact[key], separators=(",", ":")) + "\n"
    text += "training_window:\n"
    for key in ("start", "end"):
        text += "  " + key + ": " + json.dumps(artifact["training_window"][key]) + "\n"
    for key in ("sample_count", "training_query_sha256", "artifact_sha256"):
        text += key + ": " + json.dumps(artifact[key]) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".e11-", suffix=".yaml", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


EVIDENCE_ENVELOPE = "APEX.CP14.EvidenceEvent.v1"


def evidence_storage_copy(event: Any) -> Any:
    """Full contract in the existing raw TEXT column, no frozen-store edit.

    insert_evidence maps explanation to raw. Only the storage copy carries
    the envelope; the original explanation is preserved inside its payload.
    """
    from dataclasses import asdict, replace
    event.validate_24_fields()
    payload = asdict(event)
    digest = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
    return replace(event, explanation=canonical_json({
        "schema": EVIDENCE_ENVELOPE, "payload_sha256": digest, "event": payload}))


def evidence_from_raw(raw: str) -> Any:
    import json
    from dataclasses import fields
    from apex.data_catalog.contracts import EvidenceEvent, LifecycleState
    try:
        envelope = json.loads(raw)
        if set(envelope) != {"schema", "payload_sha256", "event"} or envelope["schema"] != EVIDENCE_ENVELOPE:
            raise ValueError("complete-event envelope required")
        payload = envelope["event"]
        if set(payload) != {f.name for f in fields(EvidenceEvent)}:
            raise ValueError("complete 24-field payload required")
        if hashlib.sha256(canonical_json(payload).encode()).hexdigest() != envelope["payload_sha256"]:
            raise ValueError("event hash mismatch")
        payload["fate_state"] = LifecycleState(payload["fate_state"])
        payload["feature_dependencies"] = tuple(payload["feature_dependencies"])
        payload["lineage"] = tuple(payload["lineage"])
        event = EvidenceEvent(**payload)
        event.validate_24_fields()
        return event
    except (ValueError, TypeError, KeyError) as exc:
        raise BridgeError("EVIDENCE_CONTEXT_INVALID", "missing or corrupt complete event") from exc


async def read_complete_evidence(store: Any, evidence_ids: list[str]) -> list[Any]:
    """Read in requested order; never reconstruct missing fields from SQL."""
    events = []
    for identity in evidence_ids:
        row = await (await store.db.execute(
            "SELECT raw,engine_id,snapshot_id FROM evidence_event WHERE evidence_id=?",
            (identity,))).fetchone()
        if row is None:
            raise BridgeError("EVIDENCE_CONTEXT_INVALID", "persisted event missing")
        event = evidence_from_raw(row[0])
        if (event.evidence_id, event.engine_id, event.snapshot_id) != (identity, row[1], row[2]):
            raise BridgeError("EVIDENCE_CONTEXT_INVALID", "event envelope/projection mismatch")
        events.append(event)
    return events


async def persist_complete_evidence(store: Any, events: list[Any]) -> list[Any]:
    """Use the canonical public insert, then verify full readback equality."""
    for event in events:
        row = await (await store.db.execute(
            "SELECT raw FROM evidence_event WHERE evidence_id=?",
            (event.evidence_id,))).fetchone()
        if row is not None:
            if canonical_json(evidence_from_raw(row[0])) != canonical_json(event):
                raise BridgeError("EVIDENCE_CONTEXT_INVALID", "evidence identity collision")
        else:
            await store.insert_evidence(evidence_storage_copy(event))
    result = await read_complete_evidence(store, [e.evidence_id for e in events])
    if canonical_json(result) != canonical_json(events):
        raise BridgeError("EVIDENCE_CONTEXT_INVALID", "complete-event round trip mismatch")
    return result
