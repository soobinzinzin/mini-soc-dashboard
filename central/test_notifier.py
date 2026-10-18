#!/usr/bin/env python3
"""
Unit Tests for Telegram Notification Dispatcher and Correlation Integration.
Tests all requirements for Chốt 1 using mock httpx responses.
No real network calls or real Telegram API calls are performed.
"""

import os
import sys
import asyncio
import threading
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

# Ensure imports resolve from central/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force SQLite in-memory for testing
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from db import init_db, close_db, get_connection
from notifier import (
    send_telegram_message,
    format_incident_message,
    get_attack_name,
    format_vietnam_time,
    SID_NAME_MAP
)
from notifications_db import (
    init_notifications_table,
    insert_notification,
    get_notifications
)
from correlation import process_new_alert


def _setup_test_db():
    """Create all needed tables in SQLite."""
    with get_connection() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sensors (
                sensor_id TEXT PRIMARY KEY,
                site TEXT NOT NULL,
                first_seen TEXT NOT NULL DEFAULT (datetime('now')),
                last_seen TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS raw_alerts (
                telemetry_id TEXT PRIMARY KEY,
                sensor_id TEXT NOT NULL,
                site TEXT NOT NULL,
                gid INT NOT NULL,
                sid INT NOT NULL,
                rev INT,
                signature TEXT NOT NULL,
                priority INT NOT NULL DEFAULT 0,
                protocol TEXT NOT NULL,
                src_ip TEXT,
                src_port INT,
                dst_ip TEXT,
                dst_port INT,
                raw_log TEXT NOT NULL,
                alert_timestamp TEXT NOT NULL,
                received_at TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site TEXT NOT NULL,
                sid INT NOT NULL,
                src_ip TEXT,
                severity TEXT NOT NULL,
                alert_count INT NOT NULL DEFAULT 1,
                first_alert_at TEXT NOT NULL,
                last_alert_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER,
                channel TEXT NOT NULL,
                sent_at TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
            );
        """)


class TestMessageFormatting(unittest.TestCase):
    """Test incident message formatting, attack name mapping, and timezone conversion."""

    def test_attack_name_mapping(self):
        self.assertEqual(get_attack_name(1000001), "ICMP Flood")
        self.assertEqual(get_attack_name(1000002), "SYN Port Scan")
        self.assertEqual(get_attack_name(1000003), "SSH Brute Force")
        self.assertEqual(get_attack_name("1000002"), "SYN Port Scan")
        self.assertEqual(get_attack_name(9999999), "SID 9999999")

    def test_vietnam_time_formatting(self):
        # 08:00 UTC = 15:00 GMT+7
        utc_str = "2026-10-07T08:30:00Z"
        formatted = format_vietnam_time(utc_str)
        self.assertIn("15:30:00", formatted)
        self.assertIn("07/10/2026", formatted)
        self.assertIn("GMT+7", formatted)

    def test_format_critical_incident_message(self):
        incident = {
            "id": 1,
            "site": "dmz",
            "sid": 1000003,
            "src_ip": "172.19.0.5",
            "severity": "critical",
            "alert_count": 3,
            "last_alert_at": "2026-10-07T08:00:00Z"
        }
        msg = format_incident_message(incident)
        self.assertIn("🔴", msg)
        self.assertIn("CRITICAL", msg)
        self.assertIn("Cảnh báo an ninh mạng", msg)
        self.assertIn("Site: DMZ", msg)
        self.assertIn("Loại tấn công: SSH Brute Force", msg)
        self.assertIn("IP nguồn: 172.19.0.5", msg)
        self.assertIn("Số lần lặp: 3", msg)
        self.assertIn("15:00:00", msg)

    def test_format_high_incident_message(self):
        incident = {
            "id": 2,
            "site": "hq",
            "sid": 1000002,
            "src_ip": "172.20.0.5",
            "severity": "high",
            "alert_count": 1,
            "last_alert_at": "2026-10-07T09:00:00Z"
        }
        msg = format_incident_message(incident)
        self.assertIn("🟠", msg)
        self.assertIn("HIGH", msg)
        self.assertIn("Loại tấn công: SYN Port Scan", msg)
        self.assertIn("Site: HQ", msg)


class TestTelegramNotifierUnit(unittest.TestCase):
    """Test send_telegram_message with mock httpx responses."""

    def test_missing_token_returns_false_and_no_httpx_call(self):
        """Thiếu TELEGRAM_BOT_TOKEN -> không gọi httpx, trả False."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "123456"}):
            with patch("httpx.AsyncClient") as mock_client:
                result = asyncio.run(send_telegram_message("test message"))
                self.assertFalse(result)
                mock_client.assert_not_called()

    def test_missing_chat_id_returns_false_and_no_httpx_call(self):
        """Thiếu TELEGRAM_CHAT_ID -> không gọi httpx, trả False."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "bot12345:token", "TELEGRAM_CHAT_ID": ""}):
            with patch("httpx.AsyncClient") as mock_client:
                result = asyncio.run(send_telegram_message("test message"))
                self.assertFalse(result)
                mock_client.assert_not_called()

    def test_send_success_returns_true(self):
        """Gửi thành công (mock trả 200) -> trả True."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"ok": true}'

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "mock_token", "TELEGRAM_CHAT_ID": "123456"}):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client_instance = AsyncMock()
                mock_client_instance.post.return_value = mock_response
                mock_client_cls.return_value.__aenter__.return_value = mock_client_instance

                result = asyncio.run(send_telegram_message("Hello SOC"))
                self.assertTrue(result)
                mock_client_instance.post.assert_called_once()
                call_args = mock_client_instance.post.call_args
                self.assertIn("https://api.telegram.org/botmock_token/sendMessage", call_args[0][0])
                self.assertEqual(call_args[1]["json"]["chat_id"], "123456")
                self.assertEqual(call_args[1]["json"]["parse_mode"], "HTML")

    def test_500_retry_then_200_returns_true(self):
        """Mock trả 500 rồi 200 ở lần retry thứ 2 -> cuối cùng trả True."""
        resp_500 = MagicMock()
        resp_500.status_code = 500
        resp_500.text = "Internal Server Error"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.text = '{"ok": true}'

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "mock_token", "TELEGRAM_CHAT_ID": "123456"}):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client_instance = AsyncMock()
                # 1st attempt: 500, 2nd attempt: 200
                mock_client_instance.post.side_effect = [resp_500, resp_200]
                mock_client_cls.return_value.__aenter__.return_value = mock_client_instance

                result = asyncio.run(send_telegram_message("Hello Retry", retry_delay=0.01))
                self.assertTrue(result)
                self.assertEqual(mock_client_instance.post.call_count, 2)

    def test_400_no_retry_returns_false(self):
        """Mock trả 400 -> không retry, trả False ngay."""
        resp_400 = MagicMock()
        resp_400.status_code = 400
        resp_400.text = '{"ok": false, "description": "Bad Request: chat not found"}'

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "mock_token", "TELEGRAM_CHAT_ID": "wrong_id"}):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client_instance = AsyncMock()
                mock_client_instance.post.return_value = resp_400
                mock_client_cls.return_value.__aenter__.return_value = mock_client_instance

                result = asyncio.run(send_telegram_message("Hello 400", retry_delay=0.01))
                self.assertFalse(result)
                # Must NOT retry on 4xx error
                self.assertEqual(mock_client_instance.post.call_count, 1)


class TestNotificationsDB(unittest.TestCase):
    """Test insert_notification and retrieval in SQLite."""

    def setUp(self):
        init_db("sqlite:///:memory:")
        _setup_test_db()

    def tearDown(self):
        close_db()

    def test_insert_notification_sent_has_sent_at(self):
        notif_id = insert_notification(incident_id=10, channel="telegram", status="sent")
        self.assertIsNotNone(notif_id)

        rows = get_notifications(incident_id=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["channel"], "telegram")
        self.assertEqual(rows[0]["status"], "sent")
        self.assertIsNotNone(rows[0]["sent_at"])

    def test_insert_notification_failed_has_null_sent_at(self):
        notif_id = insert_notification(incident_id=11, channel="telegram", status="failed")
        self.assertIsNotNone(notif_id)

        rows = get_notifications(incident_id=11)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["channel"], "telegram")
        self.assertEqual(rows[0]["status"], "failed")
        self.assertIsNone(rows[0]["sent_at"])


class TestCorrelationNotifierIntegration(unittest.TestCase):
    """
    Test correlation engine integration with Telegram notifier:
    - New critical incident -> notifier called, notification recorded with 'sent'.
    - New high incident -> notifier called.
    - New medium incident -> notifier NOT called.
    - Existing incident updated -> notifier NOT called.
    - 400 failure -> notifier returns False, notification recorded with 'failed'.
    """

    def setUp(self):
        init_db("sqlite:///:memory:")
        _setup_test_db()

    def tearDown(self):
        close_db()

    def _wait_for_condition(self, cond_fn, timeout=2.0, interval=0.02):
        import time
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            if cond_fn():
                time.sleep(0.05)
                return True
            time.sleep(interval)
        return False

    @patch("notifier.send_telegram_message", new_callable=AsyncMock)
    def test_new_critical_incident_triggers_notification_and_records_sent(self, mock_send):
        """Incident mới severity='critical' -> notifier được gọi. Mock trả 200 -> insert_notification 'sent'."""
        mock_send.return_value = True

        raw_alert = {
            "site": "dmz",
            "sid": 1000003,  # SSH Brute Force -> critical
            "src_ip": "172.19.0.99",
            "alert_timestamp": datetime.now(timezone.utc).isoformat(),
            "signature": "SSH Brute Force Attempt"
        }

        inc_id = process_new_alert(raw_alert)
        self.assertIsNotNone(inc_id)

        # Wait for background thread to execute
        self.assertTrue(self._wait_for_condition(lambda: mock_send.call_count == 1))
        mock_send.assert_called_once()
        sent_message = mock_send.call_args[0][0]
        self.assertIn("CRITICAL", sent_message)
        self.assertIn("SSH Brute Force", sent_message)

        # Verify notification table has status='sent'
        records = get_notifications(incident_id=inc_id)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "sent")
        self.assertEqual(records[0]["channel"], "telegram")
        self.assertIsNotNone(records[0]["sent_at"])

    @patch("notifier.send_telegram_message", new_callable=AsyncMock)
    def test_new_high_incident_triggers_notification(self, mock_send):
        """Incident mới severity='high' -> notifier được gọi."""
        mock_send.return_value = True

        raw_alert = {
            "site": "hq",
            "sid": 1000002,  # TCP SYN Port Scan -> high
            "src_ip": "172.20.0.88",
            "alert_timestamp": datetime.now(timezone.utc).isoformat(),
            "signature": "TCP SYN Port Scan Detected"
        }

        inc_id = process_new_alert(raw_alert)
        self.assertIsNotNone(inc_id)

        self.assertTrue(self._wait_for_condition(lambda: mock_send.call_count == 1))
        mock_send.assert_called_once()
        self.assertIn("HIGH", mock_send.call_args[0][0])

    @patch("notifier.send_telegram_message", new_callable=AsyncMock)
    def test_new_medium_incident_does_not_trigger_notification(self, mock_send):
        """Incident severity='medium' -> notifier KHÔNG được gọi (tránh spam)."""
        import time
        raw_alert = {
            "site": "serverfarm",
            "sid": 1000001,  # ICMP Flood -> medium
            "src_ip": "172.22.0.77",
            "alert_timestamp": datetime.now(timezone.utc).isoformat(),
            "signature": "ICMP Flood Attack Detected"
        }

        inc_id = process_new_alert(raw_alert)
        self.assertIsNotNone(inc_id)

        # Wait small moment to be certain no background thread was started
        time.sleep(0.1)
        mock_send.assert_not_called()

        # No notification records should exist
        records = get_notifications(incident_id=inc_id)
        self.assertEqual(len(records), 0)

    @patch("notifier.send_telegram_message", new_callable=AsyncMock)
    def test_existing_critical_incident_update_does_not_trigger_notification(self, mock_send):
        """
        Incident CŨ tăng alert_count (không phải mới tạo) dù severity critical
        -> notifier KHÔNG được gọi lại (tránh spam nhiều lần cho 1 incident).
        """
        import time
        mock_send.return_value = True

        now = datetime.now(timezone.utc)
        raw_alert_1 = {
            "site": "dmz",
            "sid": 1000003,  # critical
            "src_ip": "172.19.0.66",
            "alert_timestamp": now.isoformat(),
            "signature": "SSH Brute Force Attempt"
        }

        # First alert creates incident #1 -> notifier CALLED ONCE
        inc_id_1 = process_new_alert(raw_alert_1)
        self.assertTrue(self._wait_for_condition(lambda: mock_send.call_count == 1))
        self.assertEqual(mock_send.call_count, 1)

        # Second alert arrives 2 seconds later (within 10s correlation window)
        raw_alert_2 = {
            "site": "dmz",
            "sid": 1000003,
            "src_ip": "172.19.0.66",
            "alert_timestamp": (now + timedelta(seconds=2)).isoformat(),
            "signature": "SSH Brute Force Attempt"
        }
        inc_id_2 = process_new_alert(raw_alert_2)

        # Correlated into the same incident
        self.assertEqual(inc_id_1, inc_id_2)

        # Crucial check: mock_send must STILL be 1 (NOT called again!)
        time.sleep(0.1)
        self.assertEqual(mock_send.call_count, 1)

        # Notification table should still have exactly 1 record
        records = get_notifications(incident_id=inc_id_1)
        self.assertEqual(len(records), 1)

    @patch("notifier.send_telegram_message", new_callable=AsyncMock)
    def test_send_failure_records_failed_status(self, mock_send):
        """Mock gửi thất bại (ví dụ 400 hoặc lỗi mạng) -> insert_notification với status='failed'."""
        mock_send.return_value = False

        raw_alert = {
            "site": "dmz",
            "sid": 1000003,
            "src_ip": "172.19.0.55",
            "alert_timestamp": datetime.now(timezone.utc).isoformat(),
            "signature": "SSH Brute Force Attempt"
        }

        inc_id = process_new_alert(raw_alert)
        self.assertIsNotNone(inc_id)

        self.assertTrue(self._wait_for_condition(lambda: mock_send.call_count == 1))
        mock_send.assert_called_once()

        # Notification recorded with status='failed' and sent_at=None
        records = get_notifications(incident_id=inc_id)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "failed")
        self.assertIsNone(records[0]["sent_at"])


class TestNonBlockingTrigger(unittest.TestCase):
    """
    Verify _trigger_telegram_notification is truly non-blocking.
    These tests run the trigger from a plain thread (no event loop),
    simulating how FastAPI calls a sync `def` route in a threadpool worker.
    The mock send_telegram_message sleeps 2s; trigger must return in < 0.5s.
    """

    def setUp(self):
        init_db("sqlite:///:memory:")
        _setup_test_db()

    def tearDown(self):
        close_db()

    @patch("notifier.send_telegram_message")
    def test_trigger_returns_immediately_on_success(self, mock_send):
        """
        Mock gửi thành công sau 2 giây. _trigger_telegram_notification phải trả về
        trong dưới 0.5 giây (không chặn). Sau 2.5 giây, insert_notification được gọi
        đúng 1 lần với status='sent'.
        """
        import time
        from correlation import _trigger_telegram_notification

        async def _slow_send(text):
            await asyncio.sleep(2)
            return True

        mock_send.side_effect = _slow_send

        incident_data = {
            "id": 9901,
            "site": "hq",
            "sid": 1000003,
            "src_ip": "10.0.0.1",
            "severity": "critical",
            "alert_count": 1,
            "last_alert_at": datetime.now(timezone.utc).isoformat(),
        }

        # Run _trigger from a thread with no event loop (like FastAPI sync route)
        elapsed = None
        def _run():
            nonlocal elapsed
            t0 = time.monotonic()
            _trigger_telegram_notification(incident_data)
            elapsed = time.monotonic() - t0

        t = threading.Thread(target=_run)
        t.start()
        t.join(timeout=5)

        # trigger must return in under 0.5 seconds
        self.assertIsNotNone(elapsed, "Thread did not finish")
        self.assertLess(elapsed, 0.5,
            f"_trigger_telegram_notification blocked for {elapsed:.2f}s (must be < 0.5s)")

        # Wait for background daemon thread to complete the 2s sleep + notification
        time.sleep(3.0)

        # Verify notification was recorded as 'sent'
        records = get_notifications(incident_id=9901)
        self.assertEqual(len(records), 1,
            f"Expected exactly 1 notification record, got {len(records)}")
        self.assertEqual(records[0]["status"], "sent")
        self.assertIsNotNone(records[0]["sent_at"])

    @patch("notifier.send_telegram_message")
    def test_trigger_returns_immediately_on_failure(self, mock_send):
        """
        Mock gửi thất bại sau 2 giây (retry timeout). _trigger_telegram_notification
        phải trả về trong dưới 0.5 giây (không chặn). Sau 2.5 giây,
        insert_notification được gọi với status='failed'.
        """
        import time
        from correlation import _trigger_telegram_notification

        async def _slow_fail(text):
            await asyncio.sleep(2)
            return False

        mock_send.side_effect = _slow_fail

        incident_data = {
            "id": 9902,
            "site": "dmz",
            "sid": 1000002,
            "src_ip": "10.0.0.2",
            "severity": "high",
            "alert_count": 1,
            "last_alert_at": datetime.now(timezone.utc).isoformat(),
        }

        elapsed = None
        def _run():
            nonlocal elapsed
            t0 = time.monotonic()
            _trigger_telegram_notification(incident_data)
            elapsed = time.monotonic() - t0

        t = threading.Thread(target=_run)
        t.start()
        t.join(timeout=5)

        self.assertIsNotNone(elapsed, "Thread did not finish")
        self.assertLess(elapsed, 0.5,
            f"_trigger_telegram_notification blocked for {elapsed:.2f}s (must be < 0.5s)")

        # Wait for background daemon thread to complete
        time.sleep(3.0)

        # Verify notification was recorded as 'failed'
        records = get_notifications(incident_id=9902)
        self.assertEqual(len(records), 1,
            f"Expected exactly 1 notification record, got {len(records)}")
        self.assertEqual(records[0]["status"], "failed")
        self.assertIsNone(records[0]["sent_at"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
