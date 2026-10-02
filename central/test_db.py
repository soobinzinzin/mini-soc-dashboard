#!/usr/bin/env python3
"""
Unit and Functional Tests for Central Database Module (db.py) and Ingestion API (main.py)
Tests database operations using an isolated in-memory SQLite database without requiring
a running PostgreSQL instance or external HTTP client.
"""

import unittest
import uuid
import os
import sys

# Ensure central directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
from schemas import TelemetryPayload
from main import (
    ingest_telemetry,
    list_telemetry,
    get_telemetry_stats,
    health_check,
    clear_telemetry
)


class TestCentralDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure db module to use SQLite in-memory database
        db.init_db("sqlite:///:memory:")
        # Create schema for testing
        with db.get_connection() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sensors (
                    sensor_id TEXT PRIMARY KEY,
                    site TEXT NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS raw_alerts (
                    telemetry_id TEXT PRIMARY KEY,
                    sensor_id TEXT NOT NULL REFERENCES sensors(sensor_id),
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
                    alert_timestamp TIMESTAMP NOT NULL,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def setUp(self):
        # Clean tables before each test
        with db.get_connection() as cur:
            cur.execute("DELETE FROM raw_alerts;")
            cur.execute("DELETE FROM sensors;")

    def test_01_check_connection(self):
        """Verify check_connection returns True for healthy database."""
        self.assertTrue(db.check_connection())

    def test_02_upsert_sensor(self):
        """Verify upsert_sensor inserts new sensor and updates last_seen on conflict."""
        db.upsert_sensor("sensor-hq", "hq")
        with db.get_connection() as cur:
            cur.execute("SELECT sensor_id, site FROM sensors WHERE sensor_id = ?;", ("sensor-hq",))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "sensor-hq")
            self.assertEqual(row[1], "hq")

        # Upsert again (conflict update)
        db.upsert_sensor("sensor-hq", "hq")
        with db.get_connection() as cur:
            cur.execute("SELECT COUNT(*) FROM sensors WHERE sensor_id = ?;", ("sensor-hq",))
            count = cur.fetchone()[0]
            self.assertEqual(count, 1)

    def test_03_insert_raw_alert_and_query(self):
        """Verify inserting 1 alert and querying it back preserves all fields."""
        db.upsert_sensor("sensor-hq", "hq")

        t_id = str(uuid.uuid4())
        alert = {
            "telemetry_id": t_id,
            "sensor_id": "sensor-hq",
            "site": "hq",
            "gid": 1,
            "sid": 1000002,
            "rev": 2,
            "signature": "TCP SYN Port Scan Detected",
            "priority": 0,
            "protocol": "TCP",
            "src_ip": "172.22.0.2",
            "src_port": 44343,
            "dst_ip": "172.22.0.3",
            "dst_port": 11,
            "raw_log": "09/30-02:56:44.410124 [**] [1:1000002:2] TCP SYN Port Scan Detected [**] ...",
            "alert_timestamp": "2026-09-30T02:56:44.410124Z",
            "received_at": "2026-09-30T02:56:45.000000Z"
        }

        inserted = db.insert_raw_alert(alert)
        self.assertTrue(inserted)

        # Query back
        alerts = db.get_raw_alerts(limit=10)
        self.assertEqual(len(alerts), 1)
        record = alerts[0]
        self.assertEqual(record["telemetry_id"], t_id)
        self.assertEqual(record["sensor_id"], "sensor-hq")
        self.assertEqual(record["site"], "hq")
        self.assertEqual(record["sid"], 1000002)
        self.assertEqual(record["signature"], "TCP SYN Port Scan Detected")
        self.assertEqual(record["protocol"], "TCP")
        self.assertEqual(record["src_ip"], "172.22.0.2")
        self.assertEqual(record["dst_ip"], "172.22.0.3")

    def test_04_duplicate_telemetry_id_not_inserted(self):
        """Verify inserting duplicate telemetry_id does NOT increase row count (idempotence)."""
        db.upsert_sensor("sensor-dmz", "dmz")
        t_id = str(uuid.uuid4())

        alert = {
            "telemetry_id": t_id,
            "sensor_id": "sensor-dmz",
            "site": "dmz",
            "gid": 1,
            "sid": 1000003,
            "rev": 2,
            "signature": "SSH Brute Force Attempt",
            "priority": 0,
            "protocol": "TCP",
            "src_ip": "172.20.0.2",
            "src_port": 34370,
            "dst_ip": "172.20.0.3",
            "dst_port": 22,
            "raw_log": "raw log line",
            "alert_timestamp": "2026-09-30T02:57:02.162816Z",
            "received_at": "2026-09-30T02:57:03.000000Z"
        }

        # First insert -> True
        first_insert = db.insert_raw_alert(alert)
        self.assertTrue(first_insert)

        # Duplicate insert with same telemetry_id -> False (ON CONFLICT DO NOTHING)
        duplicate_insert = db.insert_raw_alert(alert)
        self.assertFalse(duplicate_insert)

        # Total count must remain exactly 1
        stats = db.get_stats()
        self.assertEqual(stats["total_received"], 1)

    def test_05_stats_aggregation(self):
        """Verify get_stats computes total_received, by_site, by_signature, and by_protocol."""
        db.upsert_sensor("sensor-hq", "hq")
        db.upsert_sensor("sensor-serverfarm", "serverfarm")

        alert1 = {
            "telemetry_id": str(uuid.uuid4()),
            "sensor_id": "sensor-hq",
            "site": "hq",
            "gid": 1,
            "sid": 1000001,
            "rev": 2,
            "signature": "ICMP Flood Attack Detected",
            "priority": 0,
            "protocol": "ICMP",
            "src_ip": "172.22.0.2",
            "src_port": None,
            "dst_ip": "172.22.0.3",
            "dst_port": None,
            "raw_log": "log 1",
            "alert_timestamp": "2026-09-30T02:00:00Z",
            "received_at": "2026-09-30T02:00:01Z"
        }
        alert2 = {
            "telemetry_id": str(uuid.uuid4()),
            "sensor_id": "sensor-serverfarm",
            "site": "serverfarm",
            "gid": 1,
            "sid": 1000003,
            "rev": 2,
            "signature": "SSH Brute Force Attempt",
            "priority": 0,
            "protocol": "TCP",
            "src_ip": "172.19.0.2",
            "src_port": 2222,
            "dst_ip": "172.19.0.3",
            "dst_port": 22,
            "raw_log": "log 2",
            "alert_timestamp": "2026-09-30T02:00:05Z",
            "received_at": "2026-09-30T02:00:06Z"
        }

        db.insert_raw_alert(alert1)
        db.insert_raw_alert(alert2)

        stats = db.get_stats()
        self.assertEqual(stats["total_received"], 2)
        self.assertEqual(stats["by_site"], {"hq": 1, "serverfarm": 1})
        self.assertEqual(stats["by_protocol"], {"ICMP": 1, "TCP": 1})
        self.assertEqual(stats["by_signature"], {
            "ICMP Flood Attack Detected": 1,
            "SSH Brute Force Attempt": 1
        })

    def test_06_truncate_raw_alerts(self):
        """Verify truncate_raw_alerts clears all alerts and returns count."""
        db.upsert_sensor("sensor-hq", "hq")
        db.insert_raw_alert({
            "telemetry_id": str(uuid.uuid4()),
            "sensor_id": "sensor-hq",
            "site": "hq",
            "gid": 1,
            "sid": 1000001,
            "rev": 2,
            "signature": "ICMP Flood Attack Detected",
            "priority": 0,
            "protocol": "ICMP",
            "src_ip": "172.22.0.2",
            "src_port": None,
            "dst_ip": "172.22.0.3",
            "dst_port": None,
            "raw_log": "log",
            "alert_timestamp": "2026-09-30T02:00:00Z",
            "received_at": "2026-09-30T02:00:01Z"
        })

        self.assertEqual(db.get_stats()["total_received"], 1)
        deleted = db.truncate_raw_alerts()
        self.assertEqual(deleted, 1)
        self.assertEqual(db.get_stats()["total_received"], 0)

    def test_07_main_api_flow(self):
        """Verify main.py endpoints: health_check, ingest_telemetry, list_telemetry, clear_telemetry."""
        # 1. Health check
        health = health_check()
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(health["database"], "ok")

        # 2. Ingest telemetry
        payload = TelemetryPayload(
            timestamp="2026-09-30T02:56:44.410124Z",
            sensor_id="sensor-hq",
            site="hq",
            sid=1000002,
            gid=1,
            rev=2,
            signature="TCP SYN Port Scan Detected",
            priority=0,
            protocol="TCP",
            src_ip="172.22.0.2",
            src_port=44343,
            dst_ip="172.22.0.3",
            dst_port=11,
            raw_log="09/30-02:56:44.410124 [**] [1:1000002:2] TCP SYN Port Scan Detected [**] ..."
        )
        res = ingest_telemetry(payload)
        self.assertEqual(res.status, "success")
        self.assertIsNotNone(res.telemetry_id)

        # 3. List telemetry
        items = list_telemetry(limit=10)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["site"], "hq")
        self.assertEqual(items[0]["sid"], 1000002)

        # 4. Telemetry stats
        stats = get_telemetry_stats()
        self.assertEqual(stats.total_received, 1)
        self.assertEqual(stats.by_site, {"hq": 1})

        # 5. Clear telemetry
        clear_res = clear_telemetry()
        self.assertEqual(clear_res["status"], "success")
        self.assertEqual(clear_res["cleared_records"], 1)
        self.assertEqual(get_telemetry_stats().total_received, 0)

    def test_08_ingest_telemetry_deduplication_same_telemetry_id(self):
        """Verify calling ingest_telemetry twice with identical telemetry_id results in exactly 1 row in raw_alerts."""
        fixed_id = "test-dedup-uuid-12345"
        payload = TelemetryPayload(
            timestamp="2026-09-30T03:00:00.000000Z",
            sensor_id="sensor-hq",
            site="hq",
            sid=1000001,
            gid=1,
            rev=2,
            signature="ICMP Flood Attack Detected",
            priority=0,
            protocol="ICMP",
            src_ip="172.22.0.2",
            dst_ip="172.22.0.3",
            raw_log="09/30-03:00:00.000000 [**] [1:1000001:2] ICMP Flood Attack Detected",
            telemetry_id=fixed_id
        )

        # First call -> success, inserted
        res1 = ingest_telemetry(payload)
        self.assertEqual(res1.status, "success")
        self.assertEqual(res1.telemetry_id, fixed_id)

        # Second call with identical telemetry_id (simulating retry)
        res2 = ingest_telemetry(payload)
        self.assertEqual(res2.status, "success")
        self.assertEqual(res2.telemetry_id, fixed_id)

        # Check database: exactly 1 row in raw_alerts, count does NOT increase
        stats = get_telemetry_stats()
        self.assertEqual(stats.total_received, 1)

        alerts = db.get_raw_alerts(limit=10)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["telemetry_id"], fixed_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
