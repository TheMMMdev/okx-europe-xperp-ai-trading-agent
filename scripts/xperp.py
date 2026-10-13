from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any, Iterable


@dataclass(frozen=True)
class XPerpVerdict:
    ok: bool
    reason: str = ""


def execution_enabled() -> bool:
    return str(os.getenv("ASTRA_XPERP_EXECUTION", "0")).strip().lower() in {"1", "true", "yes", "on"}


def margin_mode() -> str:
    mode = str(os.getenv("ASTRA_XPERP_MARGIN_MODE", "isolated")).strip().lower()
    if mode not in {"isolated", "cross"}:
        raise ValueError("X-Perp margin mode must be isolated or cross")
    return mode


def product_for_instrument(inst_id: str) -> str:
    return "xperp" if "_XPERP-" in str(inst_id or "").upper() else "swap"


def state_identity(product: str, inst_id: str, side: str) -> str:
    return f"{str(product).strip().lower()}|{str(inst_id).strip().upper()}|{str(side).strip().lower()}"


def client_order_id(product: str, inst_id: str, side: str, intent_id: str) -> str:
    seed = "\0".join((str(product), str(inst_id), str(side), str(intent_id))).encode("utf-8")
    return "ax" + hashlib.sha256(seed).hexdigest()[:30]


def expiry_verdict(exp_time: Any, *, now_ms: int | None = None, guard_days: int | None = None) -> XPerpVerdict:
    try:
        expiry_ms = int(exp_time or 0)
    except (TypeError, ValueError):
        return XPerpVerdict(False, "X-Perp expiry is missing or invalid")
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    days = int(guard_days if guard_days is not None else os.getenv("ASTRA_XPERP_EXPIRY_GUARD_DAYS", "30"))
    if days < 1:
        return XPerpVerdict(False, "X-Perp expiry guard must be at least one day")
    if expiry_ms <= now:
        return XPerpVerdict(False, "X-Perp contract has expired")
    if expiry_ms - now <= days * 86_400_000:
        return XPerpVerdict(False, f"X-Perp expires within the {days}-day entry guard")
    return XPerpVerdict(True)


def instrument_verdict(row: dict[str, Any], settlement_currency: str, *, now_ms: int | None = None,
                       guard_days: int | None = None) -> XPerpVerdict:
    if str(row.get("instType") or "").upper() != "FUTURES":
        return XPerpVerdict(False, "instrument type is not FUTURES")
    if str(row.get("ruleType") or "").lower() != "xperp":
        return XPerpVerdict(False, "instrument is not an X-Perp")
    if str(row.get("state") or "").lower() not in {"live", "trading"}:
        return XPerpVerdict(False, "instrument is not live")
    if str(row.get("settleCcy") or "").upper() != str(settlement_currency).upper():
        return XPerpVerdict(False, "settlement currency mismatch")
    if not str(row.get("instId") or "").strip():
        return XPerpVerdict(False, "instrument ID is missing")
    return expiry_verdict(row.get("expTime"), now_ms=now_ms, guard_days=guard_days)


def pool_from_instruments(rows: Iterable[dict[str, Any]], settlement_currency: str, *,
                          allowed_bases: Iterable[str] = ("BTC", "ETH"), now_ms: int | None = None,
                          guard_days: int | None = None) -> list[dict[str, Any]]:
    allowed = {str(value).strip().upper() for value in allowed_bases}
    pool = []
    for row in rows:
        inst_id = str(row.get("instId") or "").strip().upper()
        base = inst_id.split("-", 1)[0]
        if base not in allowed or not instrument_verdict(
                row, settlement_currency, now_ms=now_ms, guard_days=guard_days).ok:
            continue
        tick_size = str(row.get("tickSz") or "")
        normalized_tick = tick_size.rstrip("0")
        precision = len(normalized_tick.split(".", 1)[1]) if "." in normalized_tick else 0
        pool.append({
            "instId": inst_id,
            "name": base,
            "type": "crypto",
            "ccy": base,
            "tier": "tier_1_bluechip",
            "max_leverage": 1,
            "sl_atr_mult": 1.8,
            "base_sz": 1,
            "precision": precision,
            "risk_per_trade_usd": 0.0,
            "product": "xperp",
            "instType": "FUTURES",
            "ruleType": "xperp",
            "settleCcy": str(row.get("settleCcy") or "").upper(),
            "expTime": str(row.get("expTime") or ""),
            "ctVal": float(row.get("ctVal") or 0),
            "tickSz": str(row.get("tickSz") or ""),
            "lotSz": str(row.get("lotSz") or "1"),
            "minSz": str(row.get("minSz") or "1"),
        })
    return sorted(pool, key=lambda item: item["name"])


def usd_equity(balance_rows: list[dict[str, Any]],
               collateral_currencies: tuple[str, ...] = ("USDC", "USDG", "USD")) -> tuple[Decimal, Decimal]:
    row = (balance_rows or [{}])[0]
    total = Decimal(str(row.get("totalEq") or 0))
    allowed = {ccy.upper() for ccy in collateral_currencies}
    available = Decimal("0")
    for detail in row.get("details") or []:
        if str(detail.get("ccy") or "").upper() not in allowed:
            continue
        equity = Decimal(str(detail.get("eq") or detail.get("cashBal") or 0))
        equity_usd = Decimal(str(detail.get("eqUsd") or 0))
        available_native = Decimal(str(detail.get("availEq") or detail.get("availBal") or 0))
        if equity > 0 and equity_usd > 0 and available_native > 0:
            available += available_native * equity_usd / equity
    return total, available


def contracts_from_margin(margin_usd: Any, leverage: Any, price: Any, ct_val: Any,
                          lot_size: Any, min_size: Any) -> Decimal:
    values = [Decimal(str(value)) for value in (margin_usd, leverage, price, ct_val, lot_size, min_size)]
    margin, lever, px, contract_value, lot, minimum = values
    if min(values) <= 0:
        return Decimal("0")
    wanted = margin * lever / (px * contract_value)
    contracts = (wanted / lot).to_integral_value(rounding=ROUND_DOWN) * lot
    return contracts if contracts >= minimum else Decimal("0")
