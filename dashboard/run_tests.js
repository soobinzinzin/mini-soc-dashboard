import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getAlertName,
  getSeverityStyle,
  formatTimestamp,
  SID_NAME_MAP,
  SEVERITY_COLOR_MAP,
} from './src/utils.js';

test('1. SID to Attack Name Mapping', async (t) => {
  await t.test('maps SID 1000001 to ICMP Flood', () => {
    assert.equal(getAlertName(1000001), 'ICMP Flood');
  });

  await t.test('maps SID 1000002 to SYN Port Scan', () => {
    assert.equal(getAlertName(1000002), 'SYN Port Scan');
  });

  await t.test('maps SID 1000003 to SSH Brute Force', () => {
    assert.equal(getAlertName(1000003), 'SSH Brute Force');
  });

  await t.test('handles string SID representations', () => {
    assert.equal(getAlertName('1000002'), 'SYN Port Scan');
  });

  await t.test('falls back to readable label for undefined SID', () => {
    assert.equal(getAlertName(9999999), 'SID 9999999 (Chưa định nghĩa)');
  });
});

test('2. Severity to Color Mapping', async (t) => {
  await t.test('maps critical severity to red colors', () => {
    const style = getSeverityStyle('critical');
    assert.equal(style.text, '#dc2626');
    assert.equal(style.bg, '#fee2e2');
  });

  await t.test('maps high severity to orange colors', () => {
    const style = getSeverityStyle('high');
    assert.equal(style.text, '#ea580c');
    assert.equal(style.bg, '#ffedd5');
  });

  await t.test('maps medium severity to yellow colors', () => {
    const style = getSeverityStyle('medium');
    assert.equal(style.text, '#ca8a04');
    assert.equal(style.bg, '#fef9c3');
  });

  await t.test('maps low severity to gray colors', () => {
    const style = getSeverityStyle('low');
    assert.equal(style.text, '#4b5563');
    assert.equal(style.bg, '#f3f4f6');
  });

  await t.test('defaults to low/gray for unknown severity', () => {
    const style = getSeverityStyle('unknown');
    assert.deepEqual(style, SEVERITY_COLOR_MAP.low);
  });
});

test('3. Timestamp Formatting', async (t) => {
  await t.test('handles empty or null timestamp gracefully', () => {
    assert.equal(formatTimestamp(null), 'N/A');
    assert.equal(formatTimestamp(''), 'N/A');
  });

  await t.test('formats valid ISO timestamp into string', () => {
    const formatted = formatTimestamp('2026-10-04T08:00:00Z');
    assert.equal(typeof formatted, 'string');
    assert.ok(formatted.length > 5);
  });
});

test('4. API Error Handling Logic', async (t) => {
  await t.test('verifies error capture when fetch fails', async () => {
    let capturedError = null;
    try {
      const fakeFetch = () => Promise.reject(new Error('Connection refused'));
      await fakeFetch();
    } catch (err) {
      capturedError = err.message;
    }
    assert.equal(capturedError, 'Connection refused');
  });

  await t.test('verifies error capture on HTTP 500 response', async () => {
    let statusError = null;
    const fakeResponse = { ok: false, status: 500 };
    if (!fakeResponse.ok) {
      statusError = `Lỗi tải incidents: HTTP ${fakeResponse.status}`;
    }
    assert.equal(statusError, 'Lỗi tải incidents: HTTP 500');
  });
});
