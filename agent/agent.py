#!/usr/bin/env python3
"""
Shipper Agent for Mini-SOC Sensor
Tails Snort fast alert log, converts each entry into structured JSON,
and forwards it via HTTP/HTTPS POST to the central Ingestion API.
"""

import os
import re
import sys
import time
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
import urllib.request
import urllib.error

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ShipperAgent] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ShipperAgent")

# Configuration from Environment
ALERT_FILE = os.getenv("ALERT_FILE", "/var/log/snort/alert")
INGESTION_URL = os.getenv("INGESTION_URL", "http://soc-central:8000/api/v1/telemetry")
SENSOR_ID = os.getenv("SENSOR_ID", "sensor-hq")
SENSOR_SITE = os.getenv("SENSOR_SITE", "hq")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "0.5"))
RETRY_DELAY = float(os.getenv("RETRY_DELAY", "2.0"))
MAX_RETRY_DELAY = float(os.getenv("MAX_RETRY_DELAY", "30.0"))
TIMEOUT_SECONDS = float(os.getenv("TIMEOUT_SECONDS", "5.0"))

# Regex pattern for Snort Fast Alert format
# Format: MM/DD-hh:mm:ss.uuuuuu [**] [gid:sid:rev] signature [**] [Classification: ...] [Priority: n] {PROTO} src_ip:src_port -> dst_ip:dst_port
SNORT_FAST_ALERT_REGEX = re.compile(
    r"^(?P<timestamp>\d{2}/\d{2}-\d{2}:\d{2}:\d{2}\.\d+)\s+"
    r"\[\*\*\]\s+\[(?P<gid>\d+):(?P<sid>\d+):(?P<rev>\d+)\]\s+"
    r"(?P<signature>.+?)\s+\[\*\*\]\s+"
    r"(?:\[Classification:\s*(?P<classification>[^\]]+)\]\s+)?"
    r"(?:\[Priority:\s*(?P<priority>\d+)\]\s+)?"
    r"\{(?P<protocol>\w+)\}\s+"
    r"(?P<src_ip>[^:\s]+)(?::(?P<src_port>\d+))?\s+->\s+"
    r"(?P<dst_ip>[^:\s]+)(?::(?P<dst_port>\d+))?"
)


def parse_timestamp_to_iso(ts_str: str, now: Optional[datetime] = None) -> str:
    """
    Converts Snort timestamp 'MM/DD-hh:mm:ss.uuuuuu' to ISO 8601 UTC string.
    Uses datetime.now(timezone.utc). If parsed date is > 1 day in the future
    relative to UTC now, roll back 1 year.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    try:
        parts = ts_str.split("-")
        month_day = parts[0].split("/")
        month = int(month_day[0])
        day = int(month_day[1])

        time_parts = parts[1].split(":")
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        sec_parts = time_parts[2].split(".")
        second = int(sec_parts[0])
        microsecond = int(sec_parts[1]) if len(sec_parts) > 1 else 0

        year = now.year
        try:
            dt = datetime(year, month, day, hour, minute, second, microsecond, tzinfo=timezone.utc)
        except ValueError:
            # Handle leap year edge cases
            dt = datetime(year, month, day - 1, hour, minute, second, microsecond, tzinfo=timezone.utc)

        # If date is more than 1 day in the future, roll back 1 year
        if dt > now + timedelta(days=1):
            try:
                dt = datetime(year - 1, month, day, hour, minute, second, microsecond, tzinfo=timezone.utc)
            except ValueError:
                dt = datetime(year - 1, month, day - 1, hour, minute, second, microsecond, tzinfo=timezone.utc)

        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    except Exception as e:
        logger.warning(f"Error parsing timestamp '{ts_str}': {e}")
        return ts_str


def parse_snort_alert(line: str, sensor_id: str = SENSOR_ID, site: str = SENSOR_SITE, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """
    Parses a single line of Snort fast alert into a structured dictionary.
    Returns None if line does not match.
    """
    line = line.strip()
    if not line:
        return None

    match = SNORT_FAST_ALERT_REGEX.match(line)
    if not match:
        logger.warning(f"Could not parse alert line: {line}")
        return None

    data = match.groupdict()
    timestamp_iso = parse_timestamp_to_iso(data["timestamp"], now=now)

    # Deterministic telemetry_id based on sensor_id and raw_log (stable across retries)
    telemetry_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{sensor_id}|{line}"))

    payload = {
        "telemetry_id": telemetry_id,
        "timestamp": timestamp_iso,
        "sensor_id": sensor_id,
        "site": site,
        "gid": int(data["gid"]),
        "sid": int(data["sid"]),
        "rev": int(data["rev"]),
        "signature": data["signature"].strip(),
        "classification": data["classification"].strip() if data["classification"] else None,
        "priority": int(data["priority"]) if data["priority"] is not None else 0,
        "protocol": data["protocol"].upper(),
        "src_ip": data["src_ip"],
        "src_port": int(data["src_port"]) if data["src_port"] else None,
        "dst_ip": data["dst_ip"],
        "dst_port": int(data["dst_port"]) if data["dst_port"] else None,
        "raw_log": line
    }
    return payload


def send_telemetry(payload: Dict[str, Any], url: str = INGESTION_URL, timeout: float = TIMEOUT_SECONDS) -> Tuple[bool, str]:
    """
    Sends JSON telemetry payload to the central Ingestion API using standard library urllib.
    Returns (success: bool, action: str) where action is:
      - 'ok': HTTP 200 or 201 (Success)
      - 'drop': HTTP 4xx (Client Error, malformed, invalid - drop and do not retry)
      - 'retry': HTTP 5xx or Network/Connection Error (Server Error - retry)
    """
    json_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=json_bytes,
        headers={"Content-Type": "application/json", "User-Agent": "Mini-SOC-Shipper/1.0"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status in (200, 201):
                return True, "ok"
            elif 400 <= response.status < 500:
                logger.error(f"HTTP {response.status} Client Error. Dropping alert. Raw log: {payload.get('raw_log')}")
                return False, "drop"
            else:
                logger.warning(f"HTTP {response.status} Server Error. Will retry.")
                return False, "retry"
    except urllib.error.HTTPError as e:
        if 400 <= e.code < 500:
            logger.error(f"HTTP {e.code} Client Error ({e.reason}). Dropping alert. Raw log: {payload.get('raw_log')}")
            return False, "drop"
        else:
            logger.warning(f"HTTP {e.code} Server Error ({e.reason}). Will retry.")
            return False, "retry"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        logger.warning(f"Network error reaching {url}: {e}. Will retry.")
        return False, "retry"
    except Exception as e:
        logger.error(f"Unexpected error sending telemetry: {e}. Will retry.")
        return False, "retry"


def forward_with_retry(
    payload: Dict[str, Any],
    url: str = INGESTION_URL,
    retry_delay: float = RETRY_DELAY,
    max_retry_delay: float = MAX_RETRY_DELAY
) -> bool:
    """
    Attempts to forward payload to Ingestion API with exponential backoff on retryable failures.
    - If HTTP 200/201: returns True.
    - If HTTP 4xx: logs error with raw_log and drops alert immediately (returns False, no retry).
    - If HTTP 5xx or Network Error: retries with exponential backoff until success.
    """
    delay = retry_delay
    while True:
        success, action = send_telemetry(payload, url=url)
        if success:
            logger.info(f"Forwarded alert [SID:{payload['sid']}] '{payload['signature']}' from {payload['src_ip']} to {payload['dst_ip']}")
            return True
        if action == "drop":
            logger.warning(f"Alert dropped for SID {payload['sid']} due to client error (HTTP 4xx).")
            return False
        # Action is 'retry'
        logger.warning(f"Delivery failed for SID {payload['sid']}. Retrying in {delay:.1f}s...")
        time.sleep(delay)
        delay = min(delay * 2, max_retry_delay)


def tail_and_forward(
    file_path: str = ALERT_FILE,
    url: str = INGESTION_URL,
    sensor_id: str = SENSOR_ID,
    site: str = SENSOR_SITE,
    poll_interval: float = POLL_INTERVAL,
    stop_event=None,
    max_records: Optional[int] = None
):
    """
    Tails the specified Snort alert file and forwards alerts continuously.
    """
    logger.info(f"Starting Shipper Agent for [{sensor_id}] (Site: {site})")
    logger.info(f"Monitoring file: {file_path}")
    logger.info(f"Target Ingestion URL: {url}")

    # Wait for file to exist
    while not os.path.exists(file_path):
        if stop_event and stop_event.is_set():
            return
        logger.info(f"Waiting for alert file to appear: {file_path}...")
        time.sleep(poll_interval)

    logger.info(f"Found alert file: {file_path}. Attaching tail stream.")

    records_processed = 0
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        # Seek to the end of the file on startup so we only ship new alerts
        f.seek(0, os.SEEK_END)
        cur_inode = os.stat(file_path).st_ino
        cur_size = os.stat(file_path).st_size

        while True:
            if stop_event and stop_event.is_set():
                break

            # Check for file rotation / truncation
            try:
                stat = os.stat(file_path)
                if stat.st_ino != cur_inode or stat.st_size < cur_size:
                    logger.info("Alert file rotated or truncated. Re-opening...")
                    f.close()
                    f = open(file_path, "r", encoding="utf-8", errors="replace")
                    cur_inode = stat.st_ino
                    cur_size = stat.st_size
                else:
                    cur_size = stat.st_size
            except Exception as e:
                logger.warning(f"Error checking file stat: {e}")

            line = f.readline()
            if line:
                payload = parse_snort_alert(line, sensor_id=sensor_id, site=site)
                if payload:
                    forward_with_retry(payload, url=url)
                    records_processed += 1
                    if max_records and records_processed >= max_records:
                        break
            else:
                time.sleep(poll_interval)


if __name__ == "__main__":
    try:
        tail_and_forward()
    except KeyboardInterrupt:
        logger.info("Shipper Agent stopped by user.")
        sys.exit(0)
