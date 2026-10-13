"""Unit tests for the public full ledger API endpoint."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from astra_backend.app import app


class TestPublicLedgerApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self._tmp = tempfile.TemporaryDirectory(prefix="astra-public-ledger-")
        self.addCleanup(self._tmp.cleanup)
        data_dir = Path(self._tmp.name)
        trades = [{
            "inst": f"ETH-USDT-SWAP",
            "side": "long",
            "status": "closed",
            "open_time": f"2026-01-01 {i // 60:02d}:{i % 60:02d}:00",
            "close_time": f"2026-01-01 {i // 60 + 1:02d}:{i % 60:02d}:00",
        } for i in range(61)]
        (data_dir / "trading_ledger.json").write_text(
            json.dumps(trades), encoding="utf-8")
        self._env = patch.dict("os.environ", {"ASTRA_DATA_DIR": str(data_dir)})
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_public_ledger_returns_trades_and_counts(self):
        resp = self.client.get("/api/v1/public/ledger")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("trades", data)
        self.assertIn("total", data)
        self.assertIn("closed_count", data)
        self.assertIn("holding_count", data)
        self.assertIn("db_total", data)
        self.assertIsInstance(data["trades"], list)
        self.assertEqual(data["total"], len(data["trades"]))
        # 不应受常规仪表盘 60 笔硬截断限制
        self.assertEqual(data["total"], 61)
        self.assertEqual(data["closed_count"], 61)
        self.assertGreaterEqual(data["db_total"], 0)

    def test_public_ledger_all_time_parameter(self):
        resp_cycle = self.client.get("/api/v1/public/ledger?all_time=0")
        resp_all = self.client.get("/api/v1/public/ledger?all_time=1")
        self.assertEqual(resp_cycle.status_code, 200)
        self.assertEqual(resp_all.status_code, 200)
        data_cycle = resp_cycle.json()
        data_all = resp_all.json()
        # 全量历史数量应大于或等于当前周期
        self.assertGreaterEqual(data_all["total"], data_cycle["total"])
        self.assertGreaterEqual(data_all["closed_count"], data_cycle["closed_count"])
