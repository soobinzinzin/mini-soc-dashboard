#!/usr/bin/env python3
"""
Central Ingestion REST API for Mini-SOC
Receives, validates, and stores telemetry logs forwarded from remote sensor agents
into PostgreSQL persistent database.
"""

import os
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Union

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from schemas import TelemetryPayload, TelemetryResponse, TelemetryStats
from db import (
    init_db,
    close_db,
    check_connection,
    upsert_sensor,
    insert_raw_alert,
    get_raw_alerts,
    get_stats,
    truncate_raw_alerts
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [IngestionAPI] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("IngestionAPI")

# Initialize FastAPI App
app = FastAPI(
    title="Mini-SOC Central Ingestion API",
    description="Central ingestion point for distributed Snort sensor telemetry backed by PostgreSQL",
    version="2.0.0"
)

# Enable CORS for dashboard integration (React)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    """
    Initialize database connection on application startup.
    Logs error clearly without crashing if DB is temporarily unreachable.
    """
    db_url = os.getenv("DATABASE_URL")
    logger.info("Initializing Central Ingestion API service...")
    if not db_url:
        logger.warning("DATABASE_URL environment variable is not defined.")
    else:
        connected = init_db(db_url)
        if connected:
            logger.info("PostgreSQL database connection established successfully.")
        else:
            logger.error("Could not connect to database on startup. Endpoints will report 500 until DB is ready.")


@app.on_event("shutdown")
def shutdown_event():
    """Close database pool on shutdown."""
    logger.info("Shutting down Ingestion API service, closing database connections...")
    close_db()


@app.get("/", tags=["Info"])
def get_root():
    return {
        "service": "Mini-SOC Central Ingestion API",
        "version": "2.0.0",
        "storage": "PostgreSQL",
        "status": "operational",
        "docs_url": "/docs",
        "telemetry_endpoint": "/api/v1/telemetry"
    }


@app.get("/health", tags=["Health"])
def health_check():
    """
    Health check endpoint.
    Performs SELECT 1 to verify database connectivity.
    """
    db_ok = check_connection()
    db_status = "ok" if db_ok else "error"
    overall_status = "healthy" if db_ok else "degraded"

    return {
        "status": overall_status,
        "service": "ingestion-api",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@app.post(
    "/api/v1/telemetry",
    response_model=TelemetryResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Telemetry"]
)
def ingest_telemetry(payload: Union[TelemetryPayload, List[TelemetryPayload]]):
    """
    Ingest telemetry events from sensor agents.
    Supports single event object or list of events (Fluent Bit compatibility).
    Upserts sensor info and persists raw alerts to PostgreSQL.
    Returns HTTP 500 on database errors to allow agent retries.
    """
    items = payload if isinstance(payload, list) else [payload]
    received_at = datetime.utcnow().isoformat() + "Z"
    last_id = None

    for item in items:
        record = item.model_dump() if hasattr(item, "model_dump") else item.dict()
        telemetry_id = record.get("telemetry_id")
        if not telemetry_id:
            telemetry_id = str(uuid.uuid4())
        last_id = telemetry_id

        alert_data = {
            "telemetry_id": telemetry_id,
            "sensor_id": record["sensor_id"],
            "site": record["site"],
            "gid": record.get("gid", 1),
            "sid": record["sid"],
            "rev": record.get("rev", 1),
            "signature": record["signature"],
            "priority": record.get("priority", 0),
            "protocol": record["protocol"],
            "src_ip": record.get("src_ip"),
            "src_port": record.get("src_port"),
            "dst_ip": record.get("dst_ip"),
            "dst_port": record.get("dst_port"),
            "raw_log": record.get("raw_log") or "",
            "alert_timestamp": record["timestamp"],
            "received_at": received_at
        }

        try:
            # 1. Upsert sensor metadata
            upsert_sensor(sensor_id=record["sensor_id"], site=record["site"])

            # 2. Insert raw alert into PostgreSQL
            inserted = insert_raw_alert(alert_data)
            if inserted:
                logger.info(
                    f"INGESTED TELEMETRY [{record['site'].upper()}] - SID:{record['sid']} "
                    f"'{record['signature']}' | {record['protocol']} {record['src_ip']}:"
                    f"{record.get('src_port') or '*'} -> {record['dst_ip']}:{record.get('dst_port') or '*'}"
                )
            else:
                logger.warning(f"Duplicate alert skipped: telemetry_id={telemetry_id}")

        except Exception as e:
            logger.error(f"Database error during telemetry ingestion: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database write error: {str(e)}"
            )

    return TelemetryResponse(
        status="success",
        message=f"Telemetry ingested successfully ({len(items)} record(s))",
        received_at=received_at,
        telemetry_id=last_id
    )


@app.get("/api/v1/telemetry", response_model=List[dict], tags=["Telemetry"])
def list_telemetry(
    site: Optional[str] = Query(None, description="Filter by site (hq, serverfarm, dmz)"),
    protocol: Optional[str] = Query(None, description="Filter by protocol (TCP, ICMP, UDP)"),
    sid: Optional[int] = Query(None, description="Filter by Snort SID"),
    limit: int = Query(50, ge=1, le=500, description="Max number of items to return")
):
    """
    Retrieve recent telemetry records from raw_alerts with optional filtering.
    """
    # Sanitize default values when called directly in unit tests without FastAPI DI
    effective_site = site if isinstance(site, str) else None
    effective_proto = protocol if isinstance(protocol, str) else None
    effective_sid = sid if isinstance(sid, int) else None
    effective_limit = limit if isinstance(limit, int) else 50

    try:
        return get_raw_alerts(
            limit=effective_limit,
            site=effective_site,
            protocol=effective_proto,
            sid=effective_sid
        )
    except Exception as e:
        logger.error(f"Failed to query telemetry records: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query error: {str(e)}"
        )


@app.get("/api/v1/telemetry/stats", response_model=TelemetryStats, tags=["Telemetry"])
def get_telemetry_stats():
    """
    Calculate and return aggregate telemetry statistics directly from PostgreSQL.
    """
    try:
        stats_data = get_stats()
        return TelemetryStats(**stats_data)
    except Exception as e:
        logger.error(f"Failed to compute telemetry stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database stats query error: {str(e)}"
        )


@app.delete("/api/v1/telemetry", tags=["Telemetry"])
def clear_telemetry():
    """
    Clear all telemetry from raw_alerts (for testing and reset).
    Logs a warning as this is an administrative/testing operation.
    """
    logger.warning("DANGEROUS OPERATION: Truncating raw_alerts table via DELETE /api/v1/telemetry")
    try:
        count = truncate_raw_alerts()
        logger.info(f"Cleared {count} telemetry records from PostgreSQL.")
        return {"status": "success", "cleared_records": count}
    except Exception as e:
        logger.error(f"Failed to clear telemetry table: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to truncate raw_alerts: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
