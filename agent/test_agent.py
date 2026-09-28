#!/usr/bin/env python3
"""
Unit and integration tests for Snort alert parsing and forwarding in Shipper Agent.
Tested with actual alert samples produced by the mini-soc lab, plus mock HTTP & file streaming tests.
"""

import os
import io
import time
import tempfile
import threading
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
from datetime import datetime, timezone

from agent import (
    parse_snort_alert,
    parse_timestamp_to_iso,
    send_telemetry,
    forward_with_retry,
    tail_and_forward
)


class TestSnortAlertParser(unittest.TestCase):
    """5 Original Parser Tests"""

    def test_parse_icmp_flood(self):
        line = "09/27-15:32:10.613847  [**] [1:1000001:2] ICMP Flood Attack Detected [**] [Priority: 0] {ICMP} 172.19.0.2 -> 172.19.0.3"
        result = parse_snort_alert(line, sensor_id="sensor-serverfarm", site="serverfarm")
        self.assertIsNotNone(result)
        self.assertEqual(result["gid"], 1)
        self.assertEqual(result["sid"], 1000001)
        self.assertEqual(result["rev"], 2)
        self.assertEqual(result["signature"], "ICMP Flood Attack Detected")
        self.assertEqual(result["priority"], 0)
        self.assertEqual(result["protocol"], "ICMP")
        self.assertEqual(result["src_ip"], "172.19.0.2")
        self.assertIsNone(result["src_port"])
        self.assertEqual(result["dst_ip"], "172.19.0.3")
        self.assertIsNone(result["dst_port"])
        self.assertEqual(result["sensor_id"], "sensor-serverfarm")
        self.assertEqual(result["site"], "serverfarm")

    def test_parse_tcp_syn_scan(self):
        line = "09/27-15:32:10.551967  [**] [1:1000002:2] TCP SYN Port Scan Detected [**] [Priority: 0] {TCP} 172.19.0.2:33561 -> 172.19.0.3:66"
        result = parse_snort_alert(line, sensor_id="sensor-serverfarm", site="serverfarm")
        self.assertIsNotNone(result)
        self.assertEqual(result["gid"], 1)
        self.assertEqual(result["sid"], 1000002)
        self.assertEqual(result["signature"], "TCP SYN Port Scan Detected")
        self.assertEqual(result["protocol"], "TCP")
        self.assertEqual(result["src_ip"], "172.19.0.2")
        self.assertEqual(result["src_port"], 33561)
        self.assertEqual(result["dst_ip"], "172.19.0.3")
        self.assertEqual(result["dst_port"], 66)

    def test_parse_ssh_brute_force(self):
        line = "09/27-15:31:29.210201  [**] [1:1000003:2] SSH Brute Force Attempt [**] [Priority: 0] {TCP} 172.19.0.2:44098 -> 172.19.0.4:22"
        result = parse_snort_alert(line, sensor_id="sensor-hq", site="hq")
        self.assertIsNotNone(result)
        self.assertEqual(result["sid"], 1000003)
        self.assertEqual(result["signature"], "SSH Brute Force Attempt")
        self.assertEqual(result["protocol"], "TCP")
        self.assertEqual(result["src_ip"], "172.19.0.2")
        self.assertEqual(result["src_port"], 44098)
        self.assertEqual(result["dst_ip"], "172.19.0.4")
        self.assertEqual(result["dst_port"], 22)
        self.assertEqual(result["site"], "hq")

    def test_parse_alert_with_classification(self):
        line = "05/24-10:15:30.123456  [**] [1:1000001:1] ICMP Flood Attack Detected [**] [Classification: Misc Attack] [Priority: 2] {ICMP} 10.0.0.1 -> 10.0.0.2"
        result = parse_snort_alert(line, sensor_id="sensor-dmz", site="dmz")
        self.assertIsNotNone(result)
        self.assertEqual(result["classification"], "Misc Attack")
        self.assertEqual(result["priority"], 2)

    def test_invalid_lines(self):
        self.assertIsNone(parse_snort_alert(""))
        self.assertIsNone(parse_snort_alert("random unformatted log text"))


class TestTimestampAndMockHttp(unittest.TestCase):
    """New Required Tests for Chot 2"""

    def test_timestamp_future_rollback(self):
        # Current time: Jan 15, 2026. Log timestamp: Dec 20 (future by 11 months) -> Year must roll back to 2025
        mock_now = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        iso_str = parse_timestamp_to_iso("12/20-14:30:00.123456", now=mock_now)
        self.assertTrue(iso_str.startswith("2025-12-20T14:30:00.123456Z"))

    @patch("urllib.request.urlopen")
    def test_http_422_dropped(self, mock_urlopen):
        """HTTP 422: alert bi bo qua (dropped), khong retry, agent tiep tuc chay"""
        mock_error = urllib.error.HTTPError(
            url="http://mock-api/telemetry",
            code=422,
            msg="Unprocessable Entity",
            hdrs={},
            fp=io.BytesIO(b'{"detail":"Validation error"}')
        )
        mock_urlopen.side_effect = mock_error

        payload = {
            "timestamp": "2026-09-28T10:00:00.000000Z",
            "sensor_id": "sensor-hq",
            "site": "hq",
            "gid": 1,
            "sid": 1000001,
            "rev": 1,
            "signature": "Test Alert",
            "protocol": "ICMP",
            "src_ip": "1.1.1.1",
            "dst_ip": "2.2.2.2",
            "raw_log": "test raw log line"
        }

        # forward_with_retry must drop and return False immediately without infinite loop
        result = forward_with_retry(payload, url="http://mock-api/telemetry", retry_delay=0.01)
        self.assertFalse(result)
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("urllib.request.urlopen")
    def test_http_500_then_201_retry_success(self, mock_urlopen):
        """HTTP 500 roi 201: thu lai thanh cong"""
        mock_500 = urllib.error.HTTPError(
            url="http://mock-api/telemetry",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=io.BytesIO(b'{"error":"Server busy"}')
        )
        mock_201 = MagicMock()
        mock_201.status = 201
        mock_201.__enter__.return_value = mock_201

        mock_urlopen.side_effect = [mock_500, mock_201]

        payload = {
            "timestamp": "2026-09-28T10:00:00.000000Z",
            "sensor_id": "sensor-hq",
            "site": "hq",
            "gid": 1,
            "sid": 1000002,
            "rev": 1,
            "signature": "Test Scan",
            "protocol": "TCP",
            "src_ip": "10.0.0.1",
            "src_port": 1234,
            "dst_ip": "10.0.0.2",
            "dst_port": 80,
            "raw_log": "raw log"
        }

        result = forward_with_retry(payload, url="http://mock-api/telemetry", retry_delay=0.01)
        self.assertTrue(result)
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("agent.forward_with_retry")
    def test_tail_and_forward_new_line_called_once(self, mock_forward):
        """Ghi them 1 dong alert vao file tam khi tail_and_forward dang chay thi ham gui duoc goi dung 1 lan"""
        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as tf:
            tf.write("09/27-15:00:00.000000  [**] [1:1000001:1] Existing Alert [**] [Priority: 0] {ICMP} 1.1.1.1 -> 2.2.2.2\n")
            tf.flush()
            temp_path = tf.name

        stop_ev = threading.Event()
        try:
            # Start tailing in a background thread
            t = threading.Thread(
                target=tail_and_forward,
                kwargs={
                    "file_path": temp_path,
                    "url": "http://mock-api/telemetry",
                    "poll_interval": 0.05,
                    "stop_event": stop_ev,
                    "max_records": 1
                }
            )
            t.daemon = True
            t.start()
            time.sleep(0.15)  # Wait for tailer to seek to end

            # Write 1 new alert line
            with open(temp_path, "a", encoding="utf-8") as tf:
                tf.write("09/28-10:10:10.123456  [**] [1:1000001:2] ICMP Flood Attack Detected [**] [Priority: 0] {ICMP} 172.19.0.2 -> 172.19.0.4\n")
                tf.flush()

            t.join(timeout=2.0)
            self.assertEqual(mock_forward.call_count, 1)
            sent_payload = mock_forward.call_args[0][0]
            self.assertEqual(sent_payload["sid"], 1000001)
            self.assertEqual(sent_payload["signature"], "ICMP Flood Attack Detected")
        finally:
            stop_ev.set()
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @patch("agent.forward_with_retry")
    def test_file_truncation_no_crash(self, mock_forward):
        """File bi cat ngan (truncate) thi agent mo lai va khong crash"""
        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as tf:
            tf.write("09/27-15:00:00.000000  [**] [1:1000001:1] Old line 1 [**] {ICMP} 1.1.1.1 -> 2.2.2.2\n")
            tf.write("09/27-15:00:01.000000  [**] [1:1000001:1] Old line 2 [**] {ICMP} 1.1.1.1 -> 2.2.2.2\n")
            tf.flush()
            temp_path = tf.name

        stop_ev = threading.Event()
        try:
            t = threading.Thread(
                target=tail_and_forward,
                kwargs={
                    "file_path": temp_path,
                    "url": "http://mock-api/telemetry",
                    "poll_interval": 0.05,
                    "stop_event": stop_ev,
                    "max_records": 1
                }
            )
            t.daemon = True
            t.start()
            time.sleep(0.15)

            # Truncate the file to 0 bytes and write a new alert
            with open(temp_path, "w", encoding="utf-8") as tf:
                tf.write("09/28-10:20:20.999999  [**] [1:1000003:2] SSH Brute Force Attempt [**] [Priority: 0] {TCP} 172.19.0.2:50000 -> 172.19.0.4:22\n")
                tf.flush()

            t.join(timeout=2.0)
            self.assertEqual(mock_forward.call_count, 1)
            sent_payload = mock_forward.call_args[0][0]
            self.assertEqual(sent_payload["sid"], 1000003)
            self.assertEqual(sent_payload["signature"], "SSH Brute Force Attempt")
        finally:
            stop_ev.set()
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
