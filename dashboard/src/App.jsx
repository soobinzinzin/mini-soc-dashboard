import React, { useState, useEffect, useMemo } from 'react';

import {
  API_BASE_URL,
  SID_NAME_MAP,
  SEVERITY_COLOR_MAP,
  getAlertName,
  getSeverityStyle,
  formatTimestamp,
} from './utils.js';

export {
  API_BASE_URL,
  SID_NAME_MAP,
  SEVERITY_COLOR_MAP,
  getAlertName,
  getSeverityStyle,
  formatTimestamp,
};

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [stats, setStats] = useState({
    total_incidents: 0,
    by_severity: {},
    by_status: {},
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Client-side filter states
  const [siteFilter, setSiteFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  // Fetch incidents & stats from Central API
  const fetchData = async () => {
    try {
      const [incidentsRes, statsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/v1/incidents?status=all&limit=50`),
        fetch(`${API_BASE_URL}/api/v1/incidents/stats`),
      ]);

      if (!incidentsRes.ok) {
        throw new Error(`Lỗi tải incidents: HTTP ${incidentsRes.status}`);
      }
      if (!statsRes.ok) {
        throw new Error(`Lỗi tải thống kê: HTTP ${statsRes.status}`);
      }

      const incidentsData = await incidentsRes.json();
      const statsData = await statsRes.json();

      setIncidents(incidentsData);
      setStats(statsData);
      setError(null);
      setLastUpdated(new Date().toLocaleTimeString('vi-VN'));
    } catch (err) {
      setError(err.message || 'Không thể kết nối tới máy chủ Central API');
    } finally {
      setLoading(false);
    }
  };

  // Auto-polling every 5 seconds with cleanup
  useEffect(() => {
    fetchData(); // Initial load
    const timer = setInterval(() => {
      fetchData();
    }, 5000);

    return () => clearInterval(timer);
  }, []);

  // Client-side filtering
  const filteredIncidents = useMemo(() => {
    return incidents.filter((item) => {
      const matchSite =
        siteFilter === 'all' ||
        String(item.site).toLowerCase() === siteFilter.toLowerCase();
      const matchStatus =
        statusFilter === 'all' ||
        String(item.status).toLowerCase() === statusFilter.toLowerCase();
      return matchSite && matchStatus;
    });
  }, [incidents, siteFilter, statusFilter]);

  // Derived stats
  const totalCount = stats.total_incidents || incidents.length || 0;
  const openCount = stats.by_status?.open || 0;
  const criticalHighCount =
    (stats.by_severity?.critical || 0) + (stats.by_severity?.high || 0);
  const mediumLowCount =
    (stats.by_severity?.medium || 0) + (stats.by_severity?.low || 0);

  return (
    <div className="soc-container">
      {/* Header */}
      <header className="soc-header">
        <div className="header-brand">
          <div className="logo-badge">🛡️</div>
          <div>
            <h1>Mini-SOC Incident Management</h1>
            <p className="subtitle">
              Nền tảng trực quan hoá cảnh báo Snort IDS thời gian thực
            </p>
          </div>
        </div>
        <div className="header-status">
          <span className="live-indicator">
            <span className="live-dot"></span> Real-time Polling (5s)
          </span>
          {lastUpdated && (
            <span className="last-sync">Cập nhật: {lastUpdated}</span>
          )}
        </div>
      </header>

      {/* Error Alert Banner */}
      {error && (
        <div className="error-banner" role="alert">
          <div className="error-icon">⚠️</div>
          <div className="error-content">
            <strong>Mất kết nối tới Central Ingestion API!</strong>
            <p>{error} (Đích gọi: {API_BASE_URL}). Hệ thống đang thử lại tự động mỗi 5s...</p>
          </div>
          <button className="retry-btn" onClick={fetchData}>
            Thử lại ngay
          </button>
        </div>
      )}

      {/* Metric Cards */}
      <div className="stats-grid">
        <div className="stat-card total-card">
          <div className="stat-header">
            <span className="stat-title">Tổng số Incidents</span>
            <span className="stat-icon">📊</span>
          </div>
          <div className="stat-value">{totalCount}</div>
          <div className="stat-hint">Gộp từ toàn bộ sensor các site</div>
        </div>

        <div className="stat-card open-card">
          <div className="stat-header">
            <span className="stat-title">Đang hoạt động (Open)</span>
            <span className="stat-icon">⚡</span>
          </div>
          <div className="stat-value text-red">{openCount}</div>
          <div className="stat-hint">Tự đóng sau 10s không có alert mới</div>
        </div>

        <div className="stat-card high-card">
          <div className="stat-header">
            <span className="stat-title">Critical & High</span>
            <span className="stat-icon">🔥</span>
          </div>
          <div className="stat-value text-orange">{criticalHighCount}</div>
          <div className="stat-hint">
            Critical: {stats.by_severity?.critical || 0} | High: {stats.by_severity?.high || 0}
          </div>
        </div>

        <div className="stat-card low-card">
          <div className="stat-header">
            <span className="stat-title">Medium & Low</span>
            <span className="stat-icon">ℹ️</span>
          </div>
          <div className="stat-value text-yellow">{mediumLowCount}</div>
          <div className="stat-hint">
            Medium: {stats.by_severity?.medium || 0} | Low: {stats.by_severity?.low || 0}
          </div>
        </div>
      </div>

      {/* Main Content Card: Filter & Table */}
      <div className="content-card">
        {/* Filter Toolbar */}
        <div className="filter-toolbar">
          <div className="filter-group">
            <label htmlFor="site-select">Chi nhánh (Site):</label>
            <select
              id="site-select"
              value={siteFilter}
              onChange={(e) => setSiteFilter(e.target.value)}
              className="soc-select"
            >
              <option value="all">Tất cả chi nhánh</option>
              <option value="hq">Trụ sở (HQ)</option>
              <option value="serverfarm">Server Farm</option>
              <option value="dmz">Vùng mạng DMZ</option>
            </select>
          </div>

          <div className="filter-group">
            <label htmlFor="status-select">Trạng thái:</label>
            <select
              id="status-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="soc-select"
            >
              <option value="all">Tất cả trạng thái</option>
              <option value="open">Đang mở (Open)</option>
              <option value="closed">Đã đóng (Closed)</option>
            </select>
          </div>

          <div className="filter-summary">
            Hiển thị <strong>{filteredIncidents.length}</strong> / {incidents.length} sự cố
          </div>
        </div>

        {/* Incidents Table */}
        <div className="table-responsive">
          <table className="soc-table">
            <thead>
              <tr>
                <th style={{ width: '60px' }}>ID</th>
                <th style={{ width: '130px' }}>Site</th>
                <th>Loại tấn công (SID)</th>
                <th style={{ width: '140px' }}>IP Nguồn (Attacker)</th>
                <th style={{ width: '120px' }}>Mức độ</th>
                <th style={{ width: '100px', textAlign: 'center' }}>Số Alert</th>
                <th style={{ width: '110px', textAlign: 'center' }}>Trạng thái</th>
                <th style={{ width: '180px' }}>Cảnh báo gần nhất</th>
              </tr>
            </thead>
            <tbody>
              {loading && incidents.length === 0 ? (
                <tr>
                  <td colSpan="8" className="empty-message">
                    Đang tải dữ liệu từ máy chủ Mini-SOC...
                  </td>
                </tr>
              ) : filteredIncidents.length === 0 ? (
                <tr>
                  <td colSpan="8" className="empty-message">
                    Không có sự cố nào khớp với điều kiện lọc hiện tại.
                  </td>
                </tr>
              ) : (
                filteredIncidents.map((inc) => {
                  const sevStyle = getSeverityStyle(inc.severity);
                  const isClosed = String(inc.status).toLowerCase() === 'closed';

                  return (
                    <tr key={inc.id} className={!isClosed ? 'row-active' : ''}>
                      <td className="font-mono">#{inc.id}</td>
                      <td>
                        <span className={`site-tag site-${String(inc.site).toLowerCase()}`}>
                          {String(inc.site).toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <div className="attack-name">{getAlertName(inc.sid)}</div>
                        <div className="attack-sid font-mono">SID: {inc.sid}</div>
                      </td>
                      <td className="font-mono">{inc.src_ip || 'N/A'}</td>
                      <td>
                        <span
                          className="severity-badge"
                          style={{
                            backgroundColor: sevStyle.bg,
                            color: sevStyle.text,
                            borderColor: sevStyle.border,
                          }}
                        >
                          {String(inc.severity).toUpperCase()}
                        </span>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span className="count-badge">{inc.alert_count}</span>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span className={`status-badge status-${inc.status}`}>
                          {inc.status === 'open' ? '● OPEN' : '✓ CLOSED'}
                        </span>
                      </td>
                      <td className="timestamp-cell">
                        {formatTimestamp(inc.last_alert_at)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
