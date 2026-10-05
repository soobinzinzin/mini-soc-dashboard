// Mini-SOC Dashboard Utilities & Mappings

// API Base URL from Vite environment variable (default: http://localhost:8000)
export const API_BASE_URL =
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL) ||
  'http://localhost:8000';

// Mapping Snort SID to human-readable attack names
export const SID_NAME_MAP = {
  1000001: 'ICMP Flood',
  1000002: 'SYN Port Scan',
  1000003: 'SSH Brute Force',
};

export function getAlertName(sid) {
  const numericSid = Number(sid);
  return SID_NAME_MAP[numericSid] || `SID ${sid} (Chưa định nghĩa)`;
}

// Severity color definition
export const SEVERITY_COLOR_MAP = {
  critical: { bg: '#fee2e2', text: '#dc2626', border: '#f87171' }, // Red
  high:     { bg: '#ffedd5', text: '#ea580c', border: '#fb923c' }, // Orange
  medium:   { bg: '#fef9c3', text: '#ca8a04', border: '#facc15' }, // Yellow
  low:      { bg: '#f3f4f6', text: '#4b5563', border: '#9ca3af' }, // Gray
};

export function getSeverityStyle(severity) {
  const key = String(severity || '').toLowerCase();
  return SEVERITY_COLOR_MAP[key] || SEVERITY_COLOR_MAP.low;
}

export function formatTimestamp(ts) {
  if (!ts) return 'N/A';
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return ts;
    return d.toLocaleString('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return ts;
  }
}
