#!/usr/bin/env python3
"""
Database operations for Notifications table in Mini-SOC Central API.
Records dispatch logs for Telegram Bot / webhook channels.
Supports both PostgreSQL and in-memory SQLite for tests.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import db as _db_module
from db import get_connection

logger = logging.getLogger("IngestionAPI.NotificationsDB")


def init_notifications_table() -> None:
    """Ensure notifications table exists (helpful for isolated SQLite unit tests)."""
    with get_connection() as cur:
        if _db_module._db_type == "sqlite":
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id INTEGER,
                    channel TEXT NOT NULL,
                    sent_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending'
                );
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id BIGSERIAL PRIMARY KEY,
                    incident_id BIGINT REFERENCES incidents(id),
                    channel TEXT NOT NULL,
                    sent_at TIMESTAMPTZ,
                    status TEXT NOT NULL DEFAULT 'pending'
                );
            """)


def insert_notification(
    incident_id: Optional[int],
    channel: str = "telegram",
    status: str = "sent"
) -> Optional[int]:
    """
    Insert a dispatch log into the notifications table.
    
    Args:
        incident_id: ID of the correlated incident.
        channel: Notification channel (default: "telegram").
        status: Dispatch status, either "sent" or "failed".
        
    Returns:
        The notification row ID or None on failure.
    """
    # Ensure notifications table exists in test environments
    init_notifications_table()

    # sent_at is set to current timestamp if status == "sent", otherwise None
    sent_at = datetime.now(timezone.utc) if status == "sent" else None

    try:
        with get_connection() as cur:
            if _db_module._db_type == "sqlite":
                sent_at_str = sent_at.isoformat() if sent_at else None
                cur.execute("""
                    INSERT INTO notifications (incident_id, channel, sent_at, status)
                    VALUES (?, ?, ?, ?);
                """, (incident_id, channel, sent_at_str, status))
                notification_id = cur.lastrowid
            else:
                cur.execute("""
                    INSERT INTO notifications (incident_id, channel, sent_at, status)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                """, (incident_id, channel, sent_at, status))
                row = cur.fetchone()
                notification_id = row[0] if row else None

            logger.info(
                f"Recorded notification #{notification_id} for incident #{incident_id} "
                f"[{channel}] status={status}"
            )
            return notification_id

    except Exception as e:
        logger.error(f"Failed to insert notification for incident #{incident_id}: {e}")
        return None


def get_notifications(
    incident_id: Optional[int] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Retrieve recorded notifications, optionally filtered by incident_id."""
    init_notifications_table()
    conditions = []
    params: list = []

    if incident_id is not None:
        placeholder = "?" if _db_module._db_type == "sqlite" else "%s"
        conditions.append(f"incident_id = {placeholder}")
        params.append(incident_id)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    limit_ph = "?" if _db_module._db_type == "sqlite" else "%s"
    params.append(limit)

    query = f"""
        SELECT id, incident_id, channel, sent_at, status
        FROM notifications
        {where_clause}
        ORDER BY id DESC
        LIMIT {limit_ph};
    """

    results = []
    with get_connection() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        for row in rows:
            if _db_module._db_type == "sqlite":
                results.append({
                    "id": row["id"],
                    "incident_id": row["incident_id"],
                    "channel": row["channel"],
                    "sent_at": row["sent_at"],
                    "status": row["status"]
                })
            else:
                results.append({
                    "id": row[0],
                    "incident_id": row[1],
                    "channel": row[2],
                    "sent_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]) if row[3] else None,
                    "status": row[4]
                })

    return results
