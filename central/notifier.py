#!/usr/bin/env python3
"""
Telegram Notification Dispatcher for Mini-SOC
Sends alerts to Telegram Bot API when critical or high severity incidents are created.
Includes retry logic, network fault-tolerance, and message formatting.
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger("IngestionAPI.Notifier")

# SID to Attack Name Mapping (consistent with React Dashboard)
SID_NAME_MAP: Dict[int, str] = {
    1000001: "ICMP Flood",
    1000002: "SYN Port Scan",
    1000003: "SSH Brute Force",
}

# Vietnam Timezone (GMT+7)
VN_TZ = timezone(timedelta(hours=7))


def get_attack_name(sid: Any) -> str:
    """Return human-readable attack name from Snort SID."""
    try:
        sid_int = int(sid)
        return SID_NAME_MAP.get(sid_int, f"SID {sid}")
    except (ValueError, TypeError):
        return f"SID {sid}"


def format_vietnam_time(dt_val: Any) -> str:
    """
    Format timestamp to readable Vietnam Time (GMT+7).
    Accepts datetime object, ISO timestamp string, or returns raw fallback.
    """
    if not dt_val:
        return "N/A"

    if isinstance(dt_val, str):
        try:
            # Handle ISO string with Z or offset
            dt = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        except Exception:
            return dt_val
    elif isinstance(dt_val, datetime):
        dt = dt_val
    else:
        return str(dt_val)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    vn_dt = dt.astimezone(VN_TZ)
    return vn_dt.strftime("%d/%m/%Y %H:%M:%S (GMT+7)")


def format_incident_message(incident: Dict[str, Any]) -> str:
    """
    Format incident data into HTML Telegram message.
    Format:
      🚨 🔴 <b>[CRITICAL]</b> Cảnh báo an ninh mạng
      Site: {site}
      Loại tấn công: {attack_name}
      IP nguồn: {src_ip}
      Số lần lặp: {alert_count}
      Thời gian: {last_alert_at (VN Time)}
    """
    severity = str(incident.get("severity") or "unknown").lower()
    icon = "🔴" if severity == "critical" else "🟠" if severity == "high" else "🟡"
    severity_upper = severity.upper()

    site = str(incident.get("site") or "Unknown").upper()
    sid = incident.get("sid")
    attack_name = get_attack_name(sid)
    src_ip = incident.get("src_ip") or "N/A"
    alert_count = incident.get("alert_count", 1)
    last_alert_at = incident.get("last_alert_at")
    time_str = format_vietnam_time(last_alert_at)

    message = (
        f"🚨 {icon} <b>[{severity_upper}]</b> Cảnh báo an ninh mạng\n"
        f"Site: {site}\n"
        f"Loại tấn công: {attack_name}\n"
        f"IP nguồn: {src_ip}\n"
        f"Số lần lặp: {alert_count}\n"
        f"Thời gian: {time_str}"
    )
    return message


async def send_telegram_message(
    text: str,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    max_retries: int = 3,
    retry_delay: float = 2.0
) -> bool:
    """
    Send HTML-formatted text message to Telegram Bot API.
    
    Retry logic:
      - Max 3 attempts for network errors or HTTP 5xx, with 2-second sleep between retries.
      - Never retry on 4xx client errors (invalid token, bad chat_id, malformed request).
      - Returns True if HTTP 200, False if failed or missing credentials.
    """
    token = bot_token if bot_token is not None else os.getenv("TELEGRAM_BOT_TOKEN")
    cid = chat_id if chat_id is not None else os.getenv("TELEGRAM_CHAT_ID")

    if not token or not cid:
        logger.warning(
            "Telegram notification skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing."
        )
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": cid,
        "text": text,
        "parse_mode": "HTML"
    }

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    logger.info(f"Telegram notification sent successfully on attempt {attempt}.")
                    return True

                # 4xx Client Error: do not retry
                if 400 <= response.status_code < 500:
                    logger.error(
                        f"Telegram API 4xx error (HTTP {response.status_code}): {response.text}. Not retrying."
                    )
                    return False

                # 5xx Server Error: eligible for retry
                logger.warning(
                    f"Telegram API 5xx server error (HTTP {response.status_code}) on attempt {attempt}/{max_retries}."
                )

        except (httpx.RequestError, Exception) as exc:
            logger.warning(
                f"Telegram request exception on attempt {attempt}/{max_retries}: {exc}"
            )

        if attempt < max_retries:
            await asyncio.sleep(retry_delay)

    logger.error(f"Failed to send Telegram message after {max_retries} attempts.")
    return False
