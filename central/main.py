#!/usr/bin/env python3
"""
Central Ingestion REST API for Mini-SOC
Receives, validates, and buffers telemetry logs forwarded from remote sensor agents.
"""

import os
import uuid
import logging
from datetime import datetime
from typing import List, Optional
from collections import deque

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from schemas import TelemetryPayload, TelemetryResponse, TelemetryStats

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
    description="Central ingestion point for distributed Snort sensor telemetry",
    version="1.0.0"
)

# Enable CORS for dashboard integration (React)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory circular buffer for telemetry records (max 2000 items)
# (In Week 9-10, this connects to PostgreSQL & Triage Engine)
MAX_BUFFER_SIZE = int(os.getenv("TELEMETRY_BUFFER_SIZE", "2000"))
telemetry_store: deque = deque(maxlen=MAX_BUFFER_SIZE)


@app.get("/", tags=["Info"])
def get_root():
    return {
        "service": "Mini-SOC Central Ingestion API",
        "version": "1.0.0",
        "status": "operational",
        "docs_url": "/docs",
        "telemetry_endpoint": "/api/v1/telemetry"
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "ingestion-api",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "buffered_records": len(telemetry_store)
    }


@app.post(
    "/api/v1/telemetry",
    response_model=TelemetryResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Telemetry"]
)
def ingest_telemetry(payload: TelemetryPayload):
    """
    Ingest a telemetry event from a sensor agent.
    Validates payload, logs event, and stores in circular buffer.
    """
    telemetry_id = str(uuid.uuid4())
    received_at = datetime.utcnow().isoformat() + "Z"

    record = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    record["telemetry_id"] = telemetry_id
    record["received_at"] = received_at

    telemetry_store.append(record)

    logger.info(
        f"INCOMING TELEMETRY [{record['site'].upper()}] - SID:{record['sid']} "
        f"'{record['signature']}' | {record['protocol']} {record['src_ip']}:"
        f"{record.get('src_port') or '*'} -> {record['dst_ip']}:{record.get('dst_port') or '*'}"
    )

    return TelemetryResponse(
        status="success",
        message="Telemetry ingested successfully",
        received_at=received_at,
        telemetry_id=telemetry_id
    )


@app.get("/api/v1/telemetry", response_model=List[dict], tags=["Telemetry"])
def list_telemetry(
    site: Optional[str] = Query(None, description="Filter by site (hq, serverfarm, dmz)"),
    protocol: Optional[str] = Query(None, description="Filter by protocol (TCP, ICMP, UDP)"),
    sid: Optional[int] = Query(None, description="Filter by Snort SID"),
    limit: int = Query(50, ge=1, le=500, description="Max number of items to return")
):
    """
    Retrieve recent telemetry records with optional filtering.
    """
    records = list(telemetry_store)

    if site:
        records = [r for r in records if r.get("site", "").lower() == site.lower()]
    if protocol:
        records = [r for r in records if r.get("protocol", "").upper() == protocol.upper()]
    if sid:
        records = [r for r in records if r.get("sid") == sid]

    # Return newest first
    return list(reversed(records))[:limit]


@app.get("/api/v1/telemetry/stats", response_model=TelemetryStats, tags=["Telemetry"])
def get_telemetry_stats():
    """
    Calculate and return aggregate telemetry statistics.
    """
    by_site = {}
    by_signature = {}
    by_protocol = {}

    for r in telemetry_store:
        site = r.get("site", "unknown")
        sig = r.get("signature", "unknown")
        proto = r.get("protocol", "unknown")

        by_site[site] = by_site.get(site, 0) + 1
        by_signature[sig] = by_signature.get(sig, 0) + 1
        by_protocol[proto] = by_protocol.get(proto, 0) + 1

    return TelemetryStats(
        total_received=len(telemetry_store),
        by_site=by_site,
        by_signature=by_signature,
        by_protocol=by_protocol
    )


@app.delete("/api/v1/telemetry", tags=["Telemetry"])
def clear_telemetry():
    """
    Clear all telemetry buffer (for testing and reset).
    """
    count = len(telemetry_store)
    telemetry_store.clear()
    logger.info(f"Cleared {count} telemetry records from buffer.")
    return {"status": "success", "cleared_records": count}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
