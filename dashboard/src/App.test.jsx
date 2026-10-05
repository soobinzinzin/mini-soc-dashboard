import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import App, {
  getAlertName,
  getSeverityStyle,
  formatTimestamp,
  SID_NAME_MAP,
  SEVERITY_COLOR_MAP,
} from './App.jsx';

describe('1. SID to Attack Name Mapping (getAlertName)', () => {
  it('maps SID 1000001 to ICMP Flood', () => {
    expect(getAlertName(1000001)).toBe('ICMP Flood');
  });

  it('maps SID 1000002 to SYN Port Scan', () => {
    expect(getAlertName(1000002)).toBe('SYN Port Scan');
  });

  it('maps SID 1000003 to SSH Brute Force', () => {
    expect(getAlertName(1000003)).toBe('SSH Brute Force');
  });

  it('handles string SID representations correctly', () => {
    expect(getAlertName('1000002')).toBe('SYN Port Scan');
  });

  it('falls back to readable label for undefined SID', () => {
    expect(getAlertName(9999999)).toBe('SID 9999999 (Chưa định nghĩa)');
  });
});

describe('2. Severity to Color Mapping (getSeverityStyle)', () => {
  it('maps critical severity to red colors', () => {
    const style = getSeverityStyle('critical');
    expect(style.text).toBe('#dc2626');
    expect(style.bg).toBe('#fee2e2');
  });

  it('maps high severity to orange colors', () => {
    const style = getSeverityStyle('high');
    expect(style.text).toBe('#ea580c');
    expect(style.bg).toBe('#ffedd5');
  });

  it('maps medium severity to yellow colors', () => {
    const style = getSeverityStyle('medium');
    expect(style.text).toBe('#ca8a04');
    expect(style.bg).toBe('#fef9c3');
  });

  it('maps low severity to gray colors', () => {
    const style = getSeverityStyle('low');
    expect(style.text).toBe('#4b5563');
    expect(style.bg).toBe('#f3f4f6');
  });

  it('defaults to low/gray for unknown severity', () => {
    const style = getSeverityStyle('unknown');
    expect(style).toEqual(SEVERITY_COLOR_MAP.low);
  });
});

describe('3. Timestamp Formatting (formatTimestamp)', () => {
  it('handles empty or null timestamp gracefully', () => {
    expect(formatTimestamp(null)).toBe('N/A');
    expect(formatTimestamp('')).toBe('N/A');
  });

  it('formats valid ISO timestamp into string', () => {
    const formatted = formatTimestamp('2026-10-04T08:00:00Z');
    expect(typeof formatted).toBe('string');
    expect(formatted.length).toBeGreaterThan(5);
  });
});

describe('4. Error Handling UI (Mock Fetch Failure)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('displays error banner when Central API connection fails', async () => {
    // Mock global fetch to simulate network error
    global.fetch = vi.fn().mockRejectedValue(new Error('Network connection refused'));

    render(<App />);

    // Check that error banner appears and contains informative message
    await waitFor(() => {
      const banner = screen.getByRole('alert');
      expect(banner).toBeDefined();
      expect(banner.textContent).toContain('Mất kết nối tới Central Ingestion API');
      expect(banner.textContent).toContain('Network connection refused');
    });
  });

  it('displays error banner when Central API returns HTTP 500 error', async () => {
    // Mock global fetch returning HTTP 500
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    });

    render(<App />);

    await waitFor(() => {
      const banner = screen.getByRole('alert');
      expect(banner).toBeDefined();
      expect(banner.textContent).toContain('Lỗi tải incidents: HTTP 500');
    });
  });
});
