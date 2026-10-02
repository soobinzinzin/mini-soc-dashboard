#!/usr/bin/env python3
"""
Pydantic Schemas for Central Ingestion API
Validates incoming telemetry payloads from sensor shipper agents.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class TelemetryPayload(BaseModel):
    timestamp: str = Field(..., description="Timestamp in ISO 8601 format (YYYY-MM-DDTHH:MM:SS.ffffffZ)")
    sensor_id: str = Field(..., description="Unique sensor ID (e.g., sensor-hq, sensor-serverfarm, sensor-dmz)")
    site: str = Field(..., description="Site location (e.g., hq, serverfarm, dmz)")
    sid: int = Field(..., description="Snort Signature ID (e.g., 1000001)")
    gid: int = Field(default=1, description="Snort Generator ID")
    rev: int = Field(default=1, description="Snort Rule Revision")
    signature: str = Field(..., description="Snort alert signature/message")
    classification: Optional[str] = Field(default=None, description="Classification category")
    priority: int = Field(default=0, description="Alert priority level (0-4)")
    protocol: str = Field(..., description="Transport/Network protocol (TCP, UDP, ICMP)")
    src_ip: str = Field(..., description="Source IP address")
    src_port: Optional[int] = Field(default=None, description="Source port number")
    dst_ip: str = Field(..., description="Destination IP address")
    dst_port: Optional[int] = Field(default=None, description="Destination port number")
    raw_log: Optional[str] = Field(default=None, description="Original raw alert line")
    telemetry_id: Optional[str] = Field(default=None, description="Deterministic telemetry ID from agent")


class TelemetryResponse(BaseModel):
    status: str = Field(default="success")
    message: str = Field(...)
    received_at: str = Field(...)
    telemetry_id: Optional[str] = Field(default=None)


class TelemetryStats(BaseModel):
    total_received: int
    by_site: dict
    by_signature: dict
    by_protocol: dict
