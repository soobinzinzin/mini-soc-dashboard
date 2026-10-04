#!/usr/bin/env python3
"""
Alert Correlation Engine for Mini-SOC
Groups raw_alerts into incidents using a 10-second sliding window
keyed on (site, sid, src_ip). Assigns severity based on SID mapping.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

import db as _db_module
from db import get_connection

logger = logging.getLogger("IngestionAPI.Correlation")

# ---------- Severity Mapping ----------
SEVERITY_MAP: Dict[int, str] = {
    1000003: "critical",   # SSH Brute Force
    1000002: "high",       # TCP SYN Port Scan
    1000001: "medium",     # ICMP Flood
}

# Correlation window in seconds
CORRELATION_WINDOW_SECONDS = 10


def get_severity(sid: int) -> str:
    """
    Map Snort SID to severity level.
    Unknown SIDs default to 'low' with a warning log.
    """
    severity = SEVERITY_MAP.get(sid)
    if severity is None:
        logger.warning(
            f"Unknown SID {sid} not in severity map. Defaulting to 'low'. "
            f"Consider adding this SID to SEVERITY_MAP in correlation.py."
        )
        return "low"
    return severity


def process_new_alert(raw_alert: Dict[str, Any]) -> Optional[int]:
    """
    Process a newly inserted raw_alert and correlate it into an incident.

    Logic:
    - Find an 'open' incident with same (site, sid, src_ip) where
      last_alert_at is within CORRELATION_WINDOW_SECONDS of this alert's timestamp.
    - If found: update that incident (increment alert_count, update last_alert_at).
    - If not found: create a new incident.

    Args:
        raw_alert: dict with keys: site, sid, src_ip, alert_timestamp, signature

    Returns:
        The incident ID that was created or updated, or None on error.
    """
    site = raw_alert.get("site")
    sid = raw_alert.get("sid")
    src_ip = raw_alert.get("src_ip") or ""
    alert_ts = raw_alert.get("alert_timestamp")
    severity = get_severity(sid)

    # Parse alert_timestamp to datetime if it's a string
    if isinstance(alert_ts, str):
        try:
            alert_dt = datetime.fromisoformat(alert_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            alert_dt = datetime.now(timezone.utc)
    elif isinstance(alert_ts, datetime):
        alert_dt = alert_ts
    else:
        alert_dt = datetime.now(timezone.utc)

    window_start = alert_dt - timedelta(seconds=CORRELATION_WINDOW_SECONDS)

    try:
        with get_connection() as cur:
            # Find matching open incident within the time window
            if _db_module._db_type == "sqlite":
                cur.execute("""
                    SELECT id, alert_count, last_alert_at
                    FROM incidents
                    WHERE site = ? AND sid = ? AND src_ip = ?
                      AND status = 'open'
                      AND last_alert_at >= ?
                    ORDER BY last_alert_at DESC
                    LIMIT 1;
                """, (site, sid, src_ip, window_start.isoformat()))
            else:
                cur.execute("""
                    SELECT id, alert_count, last_alert_at
                    FROM incidents
                    WHERE site = %s AND sid = %s AND src_ip = %s
                      AND status = 'open'
                      AND last_alert_at >= %s
                    ORDER BY last_alert_at DESC
                    LIMIT 1;
                """, (site, sid, src_ip, window_start))

            row = cur.fetchone()

            if row:
                # Update existing incident
                incident_id = row[0]
                new_count = row[1] + 1

                if _db_module._db_type == "sqlite":
                    cur.execute("""
                        UPDATE incidents
                        SET alert_count = ?,
                            last_alert_at = ?
                        WHERE id = ?;
                    """, (new_count, alert_dt.isoformat(), incident_id))
                else:
                    cur.execute("""
                        UPDATE incidents
                        SET alert_count = %s,
                            last_alert_at = %s
                        WHERE id = %s;
                    """, (new_count, alert_dt, incident_id))

                logger.info(
                    f"CORRELATED alert into incident #{incident_id} "
                    f"[{site}/{sid}] alert_count={new_count}"
                )
                return incident_id
            else:
                # Create new incident
                if _db_module._db_type == "sqlite":
                    cur.execute("""
                        INSERT INTO incidents
                            (site, sid, src_ip, severity, alert_count,
                             first_alert_at, last_alert_at, status)
                        VALUES (?, ?, ?, ?, 1, ?, ?, 'open');
                    """, (site, sid, src_ip, severity,
                          alert_dt.isoformat(), alert_dt.isoformat()))
                    incident_id = cur.lastrowid
                else:
                    cur.execute("""
                        INSERT INTO incidents
                            (site, sid, src_ip, severity, alert_count,
                             first_alert_at, last_alert_at, status)
                        VALUES (%s, %s, %s, %s, 1, %s, %s, 'open')
                        RETURNING id;
                    """, (site, sid, src_ip, severity, alert_dt, alert_dt))
                    result = cur.fetchone()
                    incident_id = result[0] if result else None

                logger.info(
                    f"NEW incident #{incident_id} created "
                    f"[{site}/{sid}/{src_ip}] severity={severity}"
                )
                return incident_id

    except Exception as e:
        logger.error(f"Correlation error for alert [{site}/{sid}]: {e}")
        return None


def close_stale_incidents() -> int:
    """
    Close all 'open' incidents whose last_alert_at is older than
    CORRELATION_WINDOW_SECONDS from now.

    Returns:
        Number of incidents closed.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=CORRELATION_WINDOW_SECONDS)

    try:
        with get_connection() as cur:
            if _db_module._db_type == "sqlite":
                cur.execute("""
                    UPDATE incidents
                    SET status = 'closed'
                    WHERE status = 'open' AND last_alert_at < ?;
                """, (cutoff.isoformat(),))
            else:
                cur.execute("""
                    UPDATE incidents
                    SET status = 'closed'
                    WHERE status = 'open' AND last_alert_at < %s;
                """, (cutoff,))

            closed_count = cur.rowcount
            if closed_count > 0:
                logger.info(f"Closed {closed_count} stale incident(s).")
            return closed_count

    except Exception as e:
        logger.error(f"Error closing stale incidents: {e}")
        return 0


def get_incidents(
    status_filter: str = "all",
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Retrieve incidents sorted by last_alert_at descending.
    status_filter: 'open', 'closed', or 'all' (default).
    """
    conditions = []
    params: list = []

    if status_filter in ("open", "closed"):
        placeholder = "?" if _db_module._db_type == "sqlite" else "%s"
        conditions.append(f"status = {placeholder}")
        params.append(status_filter)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    limit_ph = "?" if _db_module._db_type == "sqlite" else "%s"
    params.append(limit)

    query = f"""
        SELECT id, site, sid, src_ip, severity, alert_count,
               first_alert_at, last_alert_at, status, created_at
        FROM incidents
        {where_clause}
        ORDER BY last_alert_at DESC
        LIMIT {limit_ph};
    """

    results = []
    with get_connection() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        for row in rows:
            if _db_module._db_type == "sqlite":
                record = {
                    "id": row["id"],
                    "site": row["site"],
                    "sid": row["sid"],
                    "src_ip": row["src_ip"],
                    "severity": row["severity"],
                    "alert_count": row["alert_count"],
                    "first_alert_at": str(row["first_alert_at"]),
                    "last_alert_at": str(row["last_alert_at"]),
                    "status": row["status"],
                    "created_at": str(row["created_at"]),
                }
            else:
                record = {
                    "id": row[0],
                    "site": row[1],
                    "sid": row[2],
                    "src_ip": str(row[3]) if row[3] else None,
                    "severity": row[4],
                    "alert_count": row[5],
                    "first_alert_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
                    "last_alert_at": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7]),
                    "status": row[8],
                    "created_at": row[9].isoformat() if hasattr(row[9], "isoformat") else str(row[9]),
                }
            results.append(record)

    return results


def get_incident_stats() -> Dict[str, Any]:
    """
    Return aggregate incident statistics: count by severity and by status.
    """
    by_severity: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    total = 0

    with get_connection() as cur:
        cur.execute("SELECT COUNT(*) FROM incidents;")
        row = cur.fetchone()
        total = row[0] if row else 0

        cur.execute("SELECT severity, COUNT(*) FROM incidents GROUP BY severity;")
        for r in cur.fetchall():
            by_severity[r[0]] = r[1]

        cur.execute("SELECT status, COUNT(*) FROM incidents GROUP BY status;")
        for r in cur.fetchall():
            by_status[r[0]] = r[1]

    return {
        "total_incidents": total,
        "by_severity": by_severity,
        "by_status": by_status,
    }
