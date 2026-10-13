from __future__ import annotations

import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from scripts.xperp import (
    client_order_id,
    contracts_from_margin,
    execution_enabled,
    expiry_verdict,
    instrument_verdict,
    margin_mode,
    pool_from_instruments,
    product_for_instrument,
    state_identity,
    usd_equity,
)


NOW = 1_800_000_000_000
DAY = 86_400_000


def instrument(base="BTC", *, expiry=NOW + 365 * DAY, state="live", rule="xperp", settlement="USD"):
    return {
        "instId": f"{base}-USD_UM_XPERP-310404",
        "instType": "FUTURES",
        "ruleType": rule,
        "state": state,
        "settleCcy": settlement,
        "expTime": str(expiry),
        "ctVal": "0.0001" if base == "BTC" else "0.1",
        "tickSz": "0.1" if base == "BTC" else "0.01",
        "lotSz": "1",
        "minSz": "1",
    }


class XPerpExpiryTests(unittest.TestCase):
    def test_expiry_guard_accepts_distant_contract(self):
        self.assertTrue(expiry_verdict(NOW + 31 * DAY, now_ms=NOW, guard_days=30).ok)

    def test_expiry_guard_rejects_boundary_expired_and_invalid(self):
        for value, text in ((NOW + 30 * DAY, "within"), (NOW, "expired"), ("bad", "invalid")):
            with self.subTest(value=value):
                verdict = expiry_verdict(value, now_ms=NOW, guard_days=30)
                self.assertFalse(verdict.ok)
                self.assertIn(text, verdict.reason)

    def test_instrument_contract_is_fail_closed(self):
        self.assertTrue(instrument_verdict(instrument(), "USD", now_ms=NOW).ok)
        for row in (
            instrument(rule="normal"), instrument(state="suspended"),
            instrument(settlement="USDC"), instrument(expiry=NOW + DAY),
        ):
            self.assertFalse(instrument_verdict(row, "USD", now_ms=NOW).ok)


class XPerpPoolTests(unittest.TestCase):
    def test_pool_is_crypto_allowlisted_and_preserves_contract_metadata(self):
        rows = [instrument("BTC"), instrument("ETH"), instrument("AAPL"), instrument("SOL")]
        pool = pool_from_instruments(rows, "USD", allowed_bases=("BTC", "ETH"), now_ms=NOW)
        self.assertEqual([item["name"] for item in pool], ["BTC", "ETH"])
        self.assertEqual(pool[0]["product"], "xperp")
        self.assertEqual(pool[0]["instType"], "FUTURES")
        self.assertEqual(pool[0]["expTime"], str(NOW + 365 * DAY))


class XPerpSizingTests(unittest.TestCase):
    def test_eur_equity_is_not_treated_as_xperp_collateral(self):
        total, available = usd_equity([{
            "totalEq": "23.50",
            "details": [{"ccy": "EUR", "eq": "20", "eqUsd": "23.50", "availEq": "18"}],
        }])
        self.assertEqual(total, Decimal("23.50"))
        self.assertEqual(available, Decimal("0"))

    def test_usdc_collateral_is_converted_to_available_usd(self):
        total, available = usd_equity([{
            "totalEq": "20",
            "details": [{"ccy": "USDC", "eq": "20", "eqUsd": "19.98", "availEq": "18"}],
        }])
        self.assertEqual(total, Decimal("20"))
        self.assertEqual(available, Decimal("17.982"))

    def test_unpriced_collateral_fails_closed_for_available_equity(self):
        total, available = usd_equity([{
            "totalEq": "20", "details": [{"ccy": "EUR", "eq": "20", "availEq": "20"}],
        }])
        self.assertEqual(total, Decimal("20"))
        self.assertEqual(available, Decimal("0"))

    def test_contracts_floor_to_lot_without_exceeding_margin(self):
        contracts = contracts_from_margin("20", "2", "60000", "0.0001", "1", "1")
        self.assertEqual(contracts, Decimal("6"))
        self.assertLessEqual(contracts * Decimal("0.0001") * Decimal("60000") / Decimal("2"), Decimal("20"))

    def test_below_minimum_and_invalid_inputs_return_zero(self):
        self.assertEqual(contracts_from_margin("1", "1", "60000", "0.0001", "1", "1"), Decimal("0"))
        self.assertEqual(contracts_from_margin("0", "2", "60000", "0.0001", "1", "1"), Decimal("0"))


class XPerpIdentityTests(unittest.TestCase):
    def test_state_identity_separates_products_and_expiries(self):
        first = state_identity("xperp", "BTC-USD_UM_XPERP-310404", "long")
        second = state_identity("xperp", "BTC-USD_UM_XPERP-320404", "long")
        swap = state_identity("swap", "BTC-USDT-SWAP", "long")
        self.assertEqual(len({first, second, swap}), 3)
        self.assertEqual(product_for_instrument("BTC-USD_UM_XPERP-310404"), "xperp")
        self.assertEqual(product_for_instrument("BTC-USDT-SWAP"), "swap")

    def test_client_order_id_is_stable_distinct_and_okx_shaped(self):
        first = client_order_id("xperp", "BTC-USD_UM_XPERP-310404", "buy", "intent-1")
        repeat = client_order_id("xperp", "BTC-USD_UM_XPERP-310404", "buy", "intent-1")
        other = client_order_id("xperp", "BTC-USD_UM_XPERP-310404", "buy", "intent-2")
        self.assertEqual(first, repeat)
        self.assertNotEqual(first, other)
        self.assertEqual(len(first), 32)
        self.assertTrue(first.isalnum())

    def test_execution_gate_defaults_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(execution_enabled())
        with patch.dict(os.environ, {"ASTRA_XPERP_EXECUTION": "1"}, clear=True):
            self.assertTrue(execution_enabled())

    def test_margin_mode_defaults_isolated_and_rejects_unknown(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(margin_mode(), "isolated")
        with patch.dict(os.environ, {"ASTRA_XPERP_MARGIN_MODE": "cross"}, clear=True):
            self.assertEqual(margin_mode(), "cross")
        with patch.dict(os.environ, {"ASTRA_XPERP_MARGIN_MODE": "bad"}, clear=True):
            with self.assertRaises(ValueError):
                margin_mode()


if __name__ == "__main__":
    unittest.main()
