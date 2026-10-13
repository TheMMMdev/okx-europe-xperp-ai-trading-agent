"""OKX 持仓模式判定与探测（第一百八十刀；补齐三所同尺）。

三所模式词汇**各不相同**，故各所有各所的判定函数（**绝不共用一个枚举**）：

| 所 | 字段 | 词表 |
|---|---|---|
| OKX | `data[0].posMode` | `long_short_mode` / `net_mode` |
| Gate | `position_mode` | `single` / `dual` / `dual_plus` |
| Binance | `dualSidePosition` | 布尔 |

纪律一致：**读不出 ⇒ `unknown`，而 `unknown` 在 `execution_router` 的模式闸里 ⇒ 禁新开仓
（fail-closed）** —— 「读不到」必须与「干净」区分开。
"""

import ast
import inspect
import unittest
from unittest.mock import patch

import astra_backend.exchanges.okx as okx_mod
from astra_backend.exchanges.okx import OKXAdapter, filter_xperp_instruments, interpret_position_mode


class InterpretPositionModeTest(unittest.TestCase):
    def test_both_modes_are_mapped(self):
        self.assertEqual(interpret_position_mode({"data": [{"posMode": "long_short_mode"}]}),
                         "long_short")
        self.assertEqual(interpret_position_mode({"data": [{"posMode": "net_mode"}]}), "net")
        self.assertEqual(interpret_position_mode([{"posMode": "NET_MODE"}]), "net",
                         "裸列表回包同样支持（大小写无关）")

    def test_unknown_values_and_missing_field_are_unknown(self):
        for payload in ({"data": [{"posMode": "weird_mode"}]},
                        {"data": [{"other": 1}]},
                        {"data": []},
                        {"data": "not-a-list"},
                        {},
                        None,
                        "text",
                        [None]):
            with self.subTest(payload=payload):
                self.assertEqual(interpret_position_mode(payload), "unknown",
                                 "读不出 ⇒ unknown（调用方据此禁新开仓）")


class DetectPositionModeTest(unittest.TestCase):
    def setUp(self):
        self.ad = OKXAdapter.__new__(OKXAdapter)
        self.ad.environment = "demo"
        self.ad.api_key = ""
        self.ad.secret_key = ""
        self.ad.passphrase = ""

    def test_read_failure_is_unknown_and_never_raises(self):
        with patch("scripts.okx_rest.request", side_effect=RuntimeError("读不动")):
            self.assertEqual(self.ad.detect_position_mode(), "unknown")

    def test_payload_is_delegated(self):
        with patch("scripts.okx_rest.request",
                   return_value={"data": [{"posMode": "long_short_mode"}]}):
            self.assertEqual(self.ad.detect_position_mode(), "long_short")

    def test_the_module_never_switches_the_account_mode(self):
        """★ 用 **AST 调用点**证明**从不**调用设置模式接口（字符串扫描会被注释误伤）。"""
        tree = ast.parse(inspect.getsource(okx_mod))
        guessed = {"set_position_mode", "set-position-mode", "set_position_mode_okx"}
        found = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and ((isinstance(n.func, ast.Attribute) and n.func.attr in guessed)
                      or (isinstance(n.func, ast.Name) and n.func.id in guessed))]
        self.assertEqual(found, [], "本系统绝不自动切换用户账户模式")


class XPerpProductTest(unittest.TestCase):
    def test_product_profile_isolated_from_swap(self):
        from scripts.okx_runtime import selected_environment
        swap = selected_environment({"ASTRA_OKX_ENV": "demo"})
        xperp = selected_environment({
            "ASTRA_OKX_ENV": "live",
            "ASTRA_OKX_PRODUCT": "xperp",
            "ASTRA_XPERP_SETTLEMENT_CCY": "USDC",
        })
        self.assertEqual((swap.product_profile.inst_type, swap.product_profile.settlement_currency),
                         ("SWAP", "USDT"))
        self.assertEqual((xperp.product_profile.inst_type, xperp.product_profile.rule_type,
                          xperp.product_profile.settlement_currency),
                         ("FUTURES", "xperp", "USDC"))
        self.assertEqual(swap.base_url, "https://www.okx.com")
        self.assertEqual(xperp.base_url, "https://eea.okx.com")
        self.assertNotEqual(swap.identity, xperp.identity)

    def test_xperp_filter_rejects_normal_futures_wrong_currency_and_expiryless_rows(self):
        rows = [
            {"instType": "FUTURES", "ruleType": "xperp", "state": "live", "settleCcy": "USDC",
             "instId": "BTC-USD_UM_XPERP-040431", "expTime": "1901232000000"},
            {"instType": "FUTURES", "ruleType": "normal", "state": "live", "settleCcy": "USDC",
             "instId": "BTC-USDC-260101", "expTime": "1767225600000"},
            {"instType": "FUTURES", "ruleType": "xperp", "state": "live", "settleCcy": "USDG",
             "instId": "ETH-USD_UM_XPERP-040431", "expTime": "1901232000000"},
            {"instType": "FUTURES", "ruleType": "xperp", "state": "live", "settleCcy": "USDC",
             "instId": "SOL-USD_UM_XPERP-040431", "expTime": ""},
        ]
        found = filter_xperp_instruments(rows, "USDC")
        self.assertEqual([row["instId"] for row in found], ["BTC-USD_UM_XPERP-040431"])

    def test_invalid_settlement_currency_is_rejected(self):
        from scripts.okx_runtime import selected_environment
        with self.assertRaises(ValueError):
            selected_environment({"ASTRA_OKX_PRODUCT": "xperp", "ASTRA_XPERP_SETTLEMENT_CCY": "USDT"})

    def test_unknown_product_is_rejected_instead_of_falling_back_to_swap(self):
        from scripts.okx_runtime import selected_environment
        with self.assertRaises(ValueError):
            selected_environment({"ASTRA_OKX_PRODUCT": "spot"})

    def test_product_specific_api_hosts_are_enforced(self):
        from scripts.okx_runtime import selected_environment
        with self.assertRaises(ValueError):
            selected_environment({"ASTRA_OKX_PRODUCT": "xperp",
                                  "OKX_BASE_URL": "https://www.okx.com"})
        with self.assertRaises(ValueError):
            selected_environment({"ASTRA_OKX_PRODUCT": "swap",
                                  "OKX_BASE_URL": "https://eea.okx.com"})


class OkxEnvTest(unittest.TestCase):
    """审计 D4：`OKXEnvironment` 是 **frozen dataclass**，`simulated`/`configured` 是**派生 property**
    ⇒ 旧写法把它们当构造参数传 = **一调用即 TypeError（接线即炸）**。"""

    def setUp(self):
        self.ad = OKXAdapter.__new__(OKXAdapter)
        self.ad.environment = "Demo"
        self.ad.api_key = ""
        self.ad.secret_key = ""
        self.ad.passphrase = ""

    def _fill(self, key="K", secret="S", phrase="P"):
        self.ad.api_key, self.ad.secret_key, self.ad.passphrase = key, secret, phrase

    def test_full_credentials_build_a_frozen_env_from_fields_not_properties(self):
        from scripts.okx_runtime import OKXEnvironment
        self._fill()
        env = self.ad._get_okx_env()
        self.assertIsInstance(env, OKXEnvironment)
        self.assertEqual(env.mode, "demo", "档位小写归一")
        self.assertEqual(env.api_key, "K")
        self.assertEqual(env.passphrase, "P")
        self.assertEqual(env.simulated, True, "派生属性由 mode 推出（不是构造参数）")

    def test_half_credentials_fall_back_to_current_environment(self):
        sentinel = object()
        self.ad.api_key = "K"          # 只有 key ⇒ 视为未配置
        with patch("scripts.okx_runtime.current_environment", return_value=sentinel):
            self.assertIs(self.ad._get_okx_env(), sentinel)
        self._fill()
        with patch("scripts.okx_runtime.current_environment", return_value=sentinel):
            self._fill("", "S", "P")
            self.assertIs(self.ad._get_okx_env(), sentinel, "缺 secret ⇒ 同样回退")


if __name__ == "__main__":
    unittest.main()
