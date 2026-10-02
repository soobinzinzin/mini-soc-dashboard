#!/usr/bin/env python3
"""
Database Management Module for Mini-SOC Central Ingestion API
Handles connection pooling, upsert operations, and telemetry queries for PostgreSQL.
Supports SQLite compatibility mode for isolated unit testing.
"""

import os
import logging
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager

logger = logging.getLogger("IngestionAPI.DB")

# Connection pool holder
_pool = None
_db_type = "postgres"  # "postgres" or "sqlite"
_sqlite_conn = None


def init_db(database_url: Optional[str] = None) -> bool:
    """
    Initialize database connection pool or test connection.
    Returns True if connection successful, False otherwise.
    """
    global _pool, _db_type, _sqlite_conn

    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        logger.warning("DATABASE_URL is not set. Database operations will fail.")
        return False

    if url.startswith("sqlite"):
        import sqlite3
        _db_type = "sqlite"
        db_path = url.replace("sqlite:///", "").replace("sqlite://", "") or ":memory:"
        _sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
        _sqlite_conn.row_factory = sqlite3.Row
        logger.info(f"Initialized SQLite database at {db_path}")
        return True

    # PostgreSQL configuration
    try:
        import psycopg2
        from psycopg2.pool import ThreadedConnectionPool

        _db_type = "postgres"
        # Create threaded connection pool (min 1, max 10)
        _pool = ThreadedConnectionPool(minconn=1, maxconn=10, dsn=url)
        logger.info("Successfully connected to PostgreSQL connection pool.")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        _pool = None
        return False


def close_db():
    """Close connection pool and connections."""
    global _pool, _sqlite_conn
    if _pool:
        try:
            _pool.closeall()
        except Exception:
            pass
        _pool = None
    if _sqlite_conn:
        try:
            _sqlite_conn.close()
        except Exception:
            pass
        _sqlite_conn = None


@contextmanager
def get_connection():
    """
    Context manager to acquire and return a connection.
    Ensures commits on success, rollbacks on error, and releases connection.
    """
    global _pool, _db_type, _sqlite_conn

    if _db_type == "sqlite":
        if _sqlite_conn is None:
            raise RuntimeError("Database is not connected.")
        cursor = _sqlite_conn.cursor()
        try:
            yield cursor
            _sqlite_conn.commit()
        except Exception:
            _sqlite_conn.rollback()
            raise
        finally:
            cursor.close()
        return

    if _pool is None:
        raise RuntimeError("PostgreSQL connection pool is not initialized.")

    conn = _pool.getconn()
    try:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def check_connection() -> bool:
    """
    Check if the database connection is healthy (SELECT 1).
    """
    try:
        with get_connection() as cur:
            cur.execute("SELECT 1;")
            result = cur.fetchone()
            return result is not None
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


def upsert_sensor(sensor_id: str, site: str) -> None:
    """
    Upsert sensor metadata: insert new sensor or update last_seen on conflict.
    """
    with get_connection() as cur:
        if _db_type == "sqlite":
            query = """
                INSERT INTO sensors (sensor_id, site, first_seen, last_seen)
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (sensor_id) DO UPDATE SET
                    site = excluded.site,
                    last_seen = CURRENT_TIMESTAMP;
            """
            cur.execute(query, (sensor_id, site))
        else:
            query = """
                INSERT INTO sensors (sensor_id, site, first_seen, last_seen)
                VALUES (%s, %s, NOW(), NOW())
                ON CONFLICT (sensor_id) DO UPDATE SET
                    site = EXCLUDED.site,
                    last_seen = NOW();
            """
            cur.execute(query, (sensor_id, site))


def insert_raw_alert(alert: Dict[str, Any]) -> bool:
    """
    Insert a raw alert record. On conflict (telemetry_id), do nothing.
    Returns True if a new row was inserted, False if skipped due to conflict.
    """
    with get_connection() as cur:
        if _db_type == "sqlite":
            query = """
                INSERT INTO raw_alerts (
                    telemetry_id, sensor_id, site, gid, sid, rev,
                    signature, priority, protocol, src_ip, src_port,
                    dst_ip, dst_port, raw_log, alert_timestamp, received_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
                ON CONFLICT (telemetry_id) DO NOTHING;
            """
            params = (
                str(alert["telemetry_id"]),
                alert["sensor_id"],
                alert["site"],
                alert["gid"],
                alert["sid"],
                alert.get("rev"),
                alert["signature"],
                alert.get("priority", 0),
                alert["protocol"],
                alert.get("src_ip"),
                alert.get("src_port"),
                alert.get("dst_ip"),
                alert.get("dst_port"),
                alert["raw_log"],
                alert["alert_timestamp"],
                alert.get("received_at")
            )
            cur.execute(query, params)
        else:
            query = """
                INSERT INTO raw_alerts (
                    telemetry_id, sensor_id, site, gid, sid, rev,
                    signature, priority, protocol, src_ip, src_port,
                    dst_ip, dst_port, raw_log, alert_timestamp, received_at
                ) VALUES (
                    %(telemetry_id)s, %(sensor_id)s, %(site)s, %(gid)s, %(sid)s, %(rev)s,
                    %(signature)s, %(priority)s, %(protocol)s, %(src_ip)s, %(src_port)s,
                    %(dst_ip)s, %(dst_port)s, %(raw_log)s, %(alert_timestamp)s, %(received_at)s
                )
                ON CONFLICT (telemetry_id) DO NOTHING;
            """
            cur.execute(query, alert)

        return cur.rowcount > 0


def get_raw_alerts(
    limit: int = 50,
    site: Optional[str] = None,
    protocol: Optional[str] = None,
    sid: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve raw telemetry records sorted by received_at descending.
    Supports optional filtering by site, protocol, and sid.
    """
    conditions = []
    params: List[Any] = []

    if site:
        conditions.append("LOWER(site) = LOWER(%s)" if _db_type != "sqlite" else "LOWER(site) = LOWER(?)")
        params.append(site)
    if protocol:
        conditions.append("UPPER(protocol) = UPPER(%s)" if _db_type != "sqlite" else "UPPER(protocol) = UPPER(?)")
        params.append(protocol)
    if sid is not None:
        conditions.append("sid = %s" if _db_type != "sqlite" else "sid = ?")
        params.append(sid)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    limit_placeholder = "%s" if _db_type != "sqlite" else "?"
    params.append(limit)

    query = f"""
        SELECT 
            telemetry_id, sensor_id, site, gid, sid, rev,
            signature, priority, protocol, src_ip, src_port,
            dst_ip, dst_port, raw_log, alert_timestamp, received_at
        FROM raw_alerts
        {where_clause}
        ORDER BY received_at DESC
        LIMIT {limit_placeholder};
    """

    results = []
    with get_connection() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        for row in rows:
            if _db_type == "sqlite":
                record = {
                    "telemetry_id": str(row["telemetry_id"]),
                    "sensor_id": row["sensor_id"],
                    "site": row["site"],
                    "gid": row["gid"],
                    "sid": row["sid"],
                    "rev": row["rev"],
                    "signature": row["signature"],
                    "classification": None,
                    "priority": row["priority"],
                    "protocol": row["protocol"],
                    "src_ip": row["src_ip"],
                    "src_port": row["src_port"],
                    "dst_ip": row["dst_ip"],
                    "dst_port": row["dst_port"],
                    "raw_log": row["raw_log"],
                    "timestamp": str(row["alert_timestamp"]),
                    "received_at": str(row["received_at"])
                }
            else:
                # Postgres cursor tuple or DictCursor
                # columns: 0: telemetry_id, 1: sensor_id, 2: site, 3: gid, 4: sid, 5: rev,
                # 6: signature, 7: priority, 8: protocol, 9: src_ip, 10: src_port,
                # 11: dst_ip, 12: dst_port, 13: raw_log, 14: alert_timestamp, 15: received_at
                record = {
                    "telemetry_id": str(row[0]),
                    "sensor_id": row[1],
                    "site": row[2],
                    "gid": row[3],
                    "sid": row[4],
                    "rev": row[5],
                    "signature": row[6],
                    "classification": None,
                    "priority": row[7],
                    "protocol": row[8],
                    "src_ip": str(row[9]) if row[9] is not None else None,
                    "src_port": row[10],
                    "dst_ip": str(row[11]) if row[11] is not None else None,
                    "dst_port": row[12],
                    "raw_log": row[13],
                    "timestamp": row[14].isoformat() if hasattr(row[14], "isoformat") else str(row[14]),
                    "received_at": row[15].isoformat() if hasattr(row[15], "isoformat") else str(row[15])
                }
            results.append(record)

    return results


def get_stats() -> Dict[str, Any]:
    """
    Calculate aggregate telemetry statistics using SQL COUNT and GROUP BY.
    """
    by_site = {}
    by_signature = {}
    by_protocol = {}
    total_received = 0

    with get_connection() as cur:
        # Total count
        cur.execute("SELECT COUNT(*) FROM raw_alerts;")
        row = cur.fetchone()
        total_received = row[0] if row else 0

        # By site
        cur.execute("SELECT site, COUNT(*) FROM raw_alerts GROUP BY site;")
        for r in cur.fetchall():
            by_site[r[0]] = r[1]

        # By signature
        cur.execute("SELECT signature, COUNT(*) FROM raw_alerts GROUP BY signature;")
        for r in cur.fetchall():
            by_signature[r[0]] = r[1]

        # By protocol
        cur.execute("SELECT protocol, COUNT(*) FROM raw_alerts GROUP BY protocol;")
        for r in cur.fetchall():
            by_protocol[r[0]] = r[1]

    return {
        "total_received": total_received,
        "by_site": by_site,
        "by_signature": by_signature,
        "by_protocol": by_protocol
    }


def truncate_raw_alerts() -> int:
    """
    Clear all records from raw_alerts for testing and resets.
    Returns count of rows before deletion.
    """
    with get_connection() as cur:
        cur.execute("SELECT COUNT(*) FROM raw_alerts;")
        row = cur.fetchone()
        count = row[0] if row else 0

        if _db_type == "sqlite":
            cur.execute("DELETE FROM raw_alerts;")
        else:
            cur.execute("TRUNCATE TABLE raw_alerts;")

        return count
