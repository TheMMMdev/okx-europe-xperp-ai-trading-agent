from __future__ import annotations

import argparse
import json
import sys
import time
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from scripts import okx_rest
from scripts.okx_runtime import current_environment
from astra_backend.exchanges.okx import OKXPublicAdapter
from scripts.xperp import margin_mode, usd_equity


CONFIRMATION = "LIVE-ETH-1-CONTRACT-BOTH"


def _position(inst_id: str, env):
    rows = okx_rest.positions(inst_type="FUTURES", inst_id=inst_id, env=env)
    return next((row for row in rows if Decimal(str(row.get("pos") or 0)) != 0), None)


def _flat(inst_id: str, env) -> bool:
    return _position(inst_id, env) is None


def _wait_position(inst_id: str, env, *, present: bool, timeout: float = 12.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = _position(inst_id, env)
        if bool(row) == present:
            return row
        time.sleep(0.5)
    return _position(inst_id, env)


def _algo_rows(inst_id: str, env):
    return okx_rest.pending_algo_orders(inst_id, inst_type="FUTURES", ord_type="conditional,oco", env=env)


def _cancel_algos(inst_id: str, env):
    rows = _algo_rows(inst_id, env)
    payload = [{"instId": inst_id, "algoId": row.get("algoId")}
               for row in rows if row.get("algoId")]
    for index in range(0, len(payload), 10):
        okx_rest.cancel_algo_orders(payload[index:index + 10], env=env)
    return len(payload)


def _force_flat(inst_id: str, env):
    row = _position(inst_id, env)
    if not row:
        return
    try:
        okx_rest.close_position(inst_id, "net", td_mode="isolated", auto_cxl=True, env=env)
    except Exception:
        size = abs(Decimal(str(row.get("pos") or 0)))
        side = "sell" if Decimal(str(row.get("pos") or 0)) > 0 else "buy"
        okx_rest.place_order(inst_id, side, str(size), td_mode="isolated", ord_type="market",
                            reduce_only=True, env=env)
    if _wait_position(inst_id, env, present=False, timeout=12.0):
        raise RuntimeError("Emergency flatten did not reach zero position")


def _price(value: Decimal, tick: Decimal) -> str:
    return str((value / tick).to_integral_value(rounding=ROUND_DOWN) * tick)


def _run_leg(inst_id: str, direction: str, last: Decimal, tick: Decimal, env):
    side = "buy" if direction == "long" else "sell"
    if direction == "long":
        tp, sl = last * Decimal("1.04"), last * Decimal("0.98")
    else:
        tp, sl = last * Decimal("0.96"), last * Decimal("1.02")
    client_id = f"axlife{direction}{int(time.time() * 1000)}"[:32]
    placed = okx_rest.place_order(
        inst_id, side, "1", td_mode="isolated", ord_type="market", cl_ord_id=client_id,
        attach_tp=_price(tp, tick), attach_sl=_price(sl, tick), attach_trigger_px_type="mark", env=env)
    order_id = str((placed or [{}])[0].get("ordId") or "")
    row = _wait_position(inst_id, env, present=True)
    if not row:
        raise RuntimeError(f"{direction} entry was accepted but no position appeared")
    signed = Decimal(str(row.get("pos") or 0))
    if (direction == "long" and signed <= 0) or (direction == "short" and signed >= 0):
        raise RuntimeError(f"{direction} entry produced the wrong signed net position")
    deadline = time.time() + 12.0
    protection = []
    while time.time() < deadline:
        protection = _algo_rows(inst_id, env)
        if protection:
            break
        time.sleep(0.5)
    if not protection:
        raise RuntimeError(f"{direction} position has no readable exchange-side protection")
    canceled = _cancel_algos(inst_id, env)
    _force_flat(inst_id, env)
    if not _flat(inst_id, env):
        raise RuntimeError(f"{direction} lifecycle did not finish flat")
    return {"direction": direction, "order_id": order_id, "protection_rows": len(protection),
            "canceled_algos": canceled, "closed": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    if args.confirm != CONFIRMATION:
        raise SystemExit("Exact lifecycle confirmation phrase required")
    env = current_environment()
    if env.mode != "live" or env.product_profile.product != "xperp":
        raise SystemExit("Lifecycle check requires LIVE X-Perp profile")
    if env.base_url != "https://eea.okx.com":
        raise SystemExit("Lifecycle check requires EEA private API routing")
    if margin_mode() != "isolated":
        raise SystemExit("Lifecycle check requires isolated margin mode")
    account_config = okx_rest.request("GET", "/api/v5/account/config", env=env)
    if str((account_config or [{}])[0].get("posMode") or "").lower() != "net_mode":
        raise SystemExit("Lifecycle check requires one-way net position mode")
    _, available_collateral = usd_equity(okx_rest.balances(env=env))
    if available_collateral < Decimal("3"):
        raise SystemExit("At least 3 USD of available USDC/USDG/USD X-Perp collateral is required")
    settlement = env.product_profile.settlement_currency
    adapter = OKXPublicAdapter(environment=env.mode, product="xperp", settlement_currency=settlement)
    if not hasattr(adapter, "fetch_xperp_instruments"):
        raise SystemExit("Selected public adapter does not support X-Perp discovery")
    instruments = adapter.fetch_xperp_instruments(settlement)
    instrument = next((row for row in instruments if str(row.get("instId") or "").startswith("ETH-")), None)
    if not instrument:
        raise SystemExit("No active ETH X-Perp found")
    inst_id = str(instrument["instId"])
    if not _flat(inst_id, env) or okx_rest.pending_orders(inst_id, inst_type="FUTURES", env=env):
        raise SystemExit("Refusing lifecycle check because ETH is not initially flat and order-free")
    if _algo_rows(inst_id, env):
        raise SystemExit("Refusing lifecycle check because ETH has pending algo orders")
    ticker = adapter.fetch_ticker(inst_id) or {}
    last = Decimal(str(ticker.get("last") or 0))
    tick = Decimal(str(instrument.get("tickSz") or 0))
    if last <= 0 or tick <= 0:
        raise SystemExit("ETH ticker or tick size is unavailable")
    okx_rest.set_leverage(inst_id, 1, mgn_mode="isolated", env=env)
    results = []
    try:
        results.append(_run_leg(inst_id, "long", last, tick, env))
        ticker = adapter.fetch_ticker(inst_id) or {}
        results.append(_run_leg(inst_id, "short", Decimal(str(ticker.get("last") or last)), tick, env))
    finally:
        try:
            _cancel_algos(inst_id, env)
        finally:
            _force_flat(inst_id, env)
    print(json.dumps({"instId": inst_id, "contracts_per_leg": 1, "leverage": 1,
                      "margin_mode": "isolated", "flat": _flat(inst_id, env), "results": results}, indent=2))


if __name__ == "__main__":
    main()
