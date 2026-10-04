#!/usr/bin/env python3
"""
Unit Tests for Alert Correlation Engine (central/correlation.py)
Uses in-memory SQLite to avoid requiring a live PostgreSQL instance.
"""

import os
import sys
import time
import unittest
import logging

# Ensure imports resolve from central/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force SQLite for isolated testing
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from db import init_db, close_db, get_connection, _db_type
from correlation import (
    process_new_alert,
    close_stale_incidents,
    get_severity,
    get_incidents,
    get_incident_stats,
    CORRELATION_WINDOW_SECONDS,
)

# Enable logging to capture warnings for unknown SID test
logging.basicConfig(level=logging.DEBUG)


def _create_tables():
    """Create the required tables in SQLite for testing."""
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


class TestGetSeverity(unittest.TestCase):
    """Test severity mapping from SID."""

    def test_ssh_brute_force_is_critical(self):
        self.assertEqual(get_severity(1000003), "critical")

    def test_syn_scan_is_high(self):
        self.assertEqual(get_severity(1000002), "high")

    def test_icmp_flood_is_medium(self):
        self.assertEqual(get_severity(1000001), "medium")

    def test_unknown_sid_is_low_with_warning(self):
        with self.assertLogs("IngestionAPI.Correlation", level="WARNING") as cm:
            severity = get_severity(9999999)
        self.assertEqual(severity, "low")
        self.assertTrue(any("Unknown SID 9999999" in msg for msg in cm.output))


class TestCorrelation(unittest.TestCase):
    """Test process_new_alert correlation logic."""

    @classmethod
    def setUpClass(cls):
        init_db("sqlite:///:memory:")
        _create_tables()

    @classmethod
    def tearDownClass(cls):
        close_db()

    def setUp(self):
        """Clear incidents table before each test."""
        with get_connection() as cur:
            cur.execute("DELETE FROM incidents;")

    def _make_alert(self, site="hq", sid=1000002, src_ip="10.0.0.1",
                    timestamp="2026-10-02T10:00:00+00:00"):
        """Helper to create a minimal alert dict."""
        return {
            "site": site,
            "sid": sid,
            "src_ip": src_ip,
            "alert_timestamp": timestamp,
            "signature": "Test Alert",
        }

    def test_three_alerts_within_10s_create_one_incident(self):
        """
        3 alerts with same (site, sid, src_ip) within 10 seconds
        should produce exactly 1 incident with alert_count=3.
        """
        a1 = self._make_alert(timestamp="2026-10-02T10:00:00+00:00")
        a2 = self._make_alert(timestamp="2026-10-02T10:00:03+00:00")
        a3 = self._make_alert(timestamp="2026-10-02T10:00:07+00:00")

        id1 = process_new_alert(a1)
        id2 = process_new_alert(a2)
        id3 = process_new_alert(a3)

        self.assertIsNotNone(id1)
        # All should map to the same incident
        self.assertEqual(id1, id2)
        self.assertEqual(id2, id3)

        # Verify incident details
        incidents = get_incidents()
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["alert_count"], 3)
        self.assertEqual(incidents[0]["status"], "open")
        self.assertEqual(incidents[0]["severity"], "high")  # sid 1000002

    def test_two_alerts_more_than_10s_apart_create_two_incidents(self):
        """
        2 alerts with same (site, sid, src_ip) but more than 10 seconds apart
        should produce 2 separate incidents.
        """
        a1 = self._make_alert(timestamp="2026-10-02T10:00:00+00:00")
        a2 = self._make_alert(timestamp="2026-10-02T10:00:15+00:00")

        id1 = process_new_alert(a1)
        id2 = process_new_alert(a2)

        self.assertIsNotNone(id1)
        self.assertIsNotNone(id2)
        self.assertNotEqual(id1, id2)

        incidents = get_incidents()
        self.assertEqual(len(incidents), 2)
        for inc in incidents:
            self.assertEqual(inc["alert_count"], 1)

    def test_different_src_ip_creates_separate_incidents(self):
        """
        Alerts with same (site, sid) but different src_ip within 10s
        should create separate incidents.
        """
        a1 = self._make_alert(src_ip="10.0.0.1", timestamp="2026-10-02T10:00:00+00:00")
        a2 = self._make_alert(src_ip="10.0.0.2", timestamp="2026-10-02T10:00:03+00:00")

        id1 = process_new_alert(a1)
        id2 = process_new_alert(a2)

        self.assertNotEqual(id1, id2)
        incidents = get_incidents()
        self.assertEqual(len(incidents), 2)

    def test_different_site_creates_separate_incidents(self):
        """
        Alerts with same (sid, src_ip) but different site within 10s
        should create separate incidents.
        """
        a1 = self._make_alert(site="hq", timestamp="2026-10-02T10:00:00+00:00")
        a2 = self._make_alert(site="dmz", timestamp="2026-10-02T10:00:03+00:00")

        id1 = process_new_alert(a1)
        id2 = process_new_alert(a2)

        self.assertNotEqual(id1, id2)

    def test_sliding_window_extends(self):
        """
        Sliding window: a1 at T+0, a2 at T+8, a3 at T+16.
        a2 is within 10s of a1 → same incident.
        a3 is within 10s of a2 (now last_alert_at=T+8) → still same incident.
        All 3 should be in 1 incident.
        """
        a1 = self._make_alert(timestamp="2026-10-02T10:00:00+00:00")
        a2 = self._make_alert(timestamp="2026-10-02T10:00:08+00:00")
        a3 = self._make_alert(timestamp="2026-10-02T10:00:16+00:00")

        id1 = process_new_alert(a1)
        id2 = process_new_alert(a2)
        id3 = process_new_alert(a3)

        self.assertEqual(id1, id2)
        self.assertEqual(id2, id3)

        incidents = get_incidents()
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["alert_count"], 3)

    def test_unknown_sid_gets_low_severity(self):
        """
        Alert with SID not in SEVERITY_MAP should create incident with severity='low'.
        """
        a1 = self._make_alert(sid=9999999, timestamp="2026-10-02T10:00:00+00:00")

        with self.assertLogs("IngestionAPI.Correlation", level="WARNING") as cm:
            inc_id = process_new_alert(a1)

        self.assertIsNotNone(inc_id)
        self.assertTrue(any("Unknown SID 9999999" in msg for msg in cm.output))

        incidents = get_incidents()
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["severity"], "low")

    def test_ssh_brute_force_severity(self):
        """SID 1000003 should map to 'critical'."""
        a1 = self._make_alert(sid=1000003, timestamp="2026-10-02T10:00:00+00:00")
        process_new_alert(a1)
        incidents = get_incidents()
        self.assertEqual(incidents[0]["severity"], "critical")

    def test_icmp_flood_severity(self):
        """SID 1000001 should map to 'medium'."""
        a1 = self._make_alert(sid=1000001, timestamp="2026-10-02T10:00:00+00:00")
        process_new_alert(a1)
        incidents = get_incidents()
        self.assertEqual(incidents[0]["severity"], "medium")


class TestCloseStaleIncidents(unittest.TestCase):
    """Test close_stale_incidents function."""

    @classmethod
    def setUpClass(cls):
        init_db("sqlite:///:memory:")
        _create_tables()

    @classmethod
    def tearDownClass(cls):
        close_db()

    def setUp(self):
        with get_connection() as cur:
            cur.execute("DELETE FROM incidents;")

    def test_close_stale_after_window(self):
        """
        Create an incident with last_alert_at in the past (> 10 seconds ago).
        Calling close_stale_incidents() should set its status to 'closed'.
        """
        from datetime import datetime, timedelta, timezone

        # Insert an incident with last_alert_at 20 seconds ago
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()

        with get_connection() as cur:
            cur.execute("""
                INSERT INTO incidents (site, sid, src_ip, severity, alert_count,
                                       first_alert_at, last_alert_at, status)
                VALUES ('hq', 1000002, '10.0.0.1', 'high', 5, ?, ?, 'open');
            """, (old_time, old_time))

        # Close stale incidents
        closed = close_stale_incidents()
        self.assertEqual(closed, 1)

        # Verify status is now 'closed'
        incidents = get_incidents(status_filter="closed")
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["status"], "closed")

    def test_recent_incident_stays_open(self):
        """
        An incident with last_alert_at within the last 10 seconds
        should NOT be closed.
        """
        from datetime import datetime, timezone

        now_iso = datetime.now(timezone.utc).isoformat()

        with get_connection() as cur:
            cur.execute("""
                INSERT INTO incidents (site, sid, src_ip, severity, alert_count,
                                       first_alert_at, last_alert_at, status)
                VALUES ('dmz', 1000003, '10.0.0.5', 'critical', 2, ?, ?, 'open');
            """, (now_iso, now_iso))

        closed = close_stale_incidents()
        self.assertEqual(closed, 0)

        incidents = get_incidents(status_filter="open")
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["status"], "open")

    def test_already_closed_not_affected(self):
        """
        An already-closed incident should not be re-closed or affected.
        """
        from datetime import datetime, timedelta, timezone

        old_time = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()

        with get_connection() as cur:
            cur.execute("""
                INSERT INTO incidents (site, sid, src_ip, severity, alert_count,
                                       first_alert_at, last_alert_at, status)
                VALUES ('hq', 1000001, '10.0.0.1', 'medium', 3, ?, ?, 'closed');
            """, (old_time, old_time))

        closed = close_stale_incidents()
        self.assertEqual(closed, 0)  # Already closed, nothing to update


class TestIncidentStats(unittest.TestCase):
    """Test get_incident_stats function."""

    @classmethod
    def setUpClass(cls):
        init_db("sqlite:///:memory:")
        _create_tables()

    @classmethod
    def tearDownClass(cls):
        close_db()

    def setUp(self):
        with get_connection() as cur:
            cur.execute("DELETE FROM incidents;")

    def test_stats_counts_correctly(self):
        """Verify stats counts by severity and status."""
        from datetime import datetime, timezone

        now_iso = datetime.now(timezone.utc).isoformat()

        with get_connection() as cur:
            # 2 open critical, 1 closed high, 1 open medium
            for _ in range(2):
                cur.execute("""
                    INSERT INTO incidents (site, sid, src_ip, severity, alert_count,
                                           first_alert_at, last_alert_at, status)
                    VALUES ('dmz', 1000003, '10.0.0.1', 'critical', 1, ?, ?, 'open');
                """, (now_iso, now_iso))

            cur.execute("""
                INSERT INTO incidents (site, sid, src_ip, severity, alert_count,
                                       first_alert_at, last_alert_at, status)
                VALUES ('hq', 1000002, '10.0.0.2', 'high', 3, ?, ?, 'closed');
            """, (now_iso, now_iso))

            cur.execute("""
                INSERT INTO incidents (site, sid, src_ip, severity, alert_count,
                                       first_alert_at, last_alert_at, status)
                VALUES ('serverfarm', 1000001, '10.0.0.3', 'medium', 2, ?, ?, 'open');
            """, (now_iso, now_iso))

        stats = get_incident_stats()
        self.assertEqual(stats["total_incidents"], 4)
        self.assertEqual(stats["by_severity"]["critical"], 2)
        self.assertEqual(stats["by_severity"]["high"], 1)
        self.assertEqual(stats["by_severity"]["medium"], 1)
        self.assertEqual(stats["by_status"]["open"], 3)
        self.assertEqual(stats["by_status"]["closed"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
