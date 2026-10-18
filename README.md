# Mini-SOC Dashboard

## Giới thiệu và Kiến trúc Tổng quan

Mini-SOC Dashboard là nền tảng quản lý và trực quan hóa cảnh báo an ninh mạng tập trung cho doanh nghiệp nhiều chi nhánh. Hệ thống thu thập nhật ký từ 3 cảm biến Snort IDS phân tán, gộp các cảnh báo trùng lặp theo cửa sổ thời gian 10 giây và phân loại mức độ nghiêm trọng. Dữ liệu được lưu trữ tập trung vào cơ sở dữ liệu PostgreSQL 15, hiển thị trực quan theo thời gian thực trên React Dashboard và phát cảnh báo khẩn cấp tới Telegram Bot.

### Sơ đồ kiến trúc luồng dữ liệu

```text
[Attacker / Mạng ngoài]
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  Các chi nhánh được giám sát (HQ, Server Farm, DMZ)   │
│  [Victim Hosts] <── (Traffic) ──> [Snort Sensors]      │
│                                           │ (Log fast) │
│                                           ▼            │
│                                    [Shipper Agents]    │
└───────────────────────────────────────────┬────────────┘
                                            │ HTTP POST (JSON)
                                            ▼
┌────────────────────────────────────────────────────────┐
│  soc-central (FastAPI Ingestion API :8000)             │
│  - Tiếp nhận telemetry, kiểm tra schema, chống trùng   │
│  - Alert Correlation Engine (cửa sổ trượt 10s)        │
│  - Async Telegram Notifier (daemon thread non-blocking)│
└───────────────┬───────────────────────────┬────────────┘
                │                           │
                ▼                           ▼
┌───────────────────────────────┐   ┌────────────────────────────┐
│ soc-postgres (PostgreSQL 15)  │   │ Telegram Bot API           │
│ - Lưu raw_alerts, incidents,  │   │ - Cảnh báo khẩn cấp        │
│   sensors, notifications      │   │   (critical, high)         │
└───────────────▲───────────────┘   └────────────────────────────┘
                │
                │ Query API (:8000)
                │
┌───────────────────────────────┐
│ soc-dashboard (React + Nginx) │
│ - Cổng 5173 ra host           │
│ - Polling tự động mỗi 5 giây  │
└───────────────────────────────┘
```

---

## Yêu cầu hệ thống

- Hệ điều hành: Windows 10/11 kèm WSL2 (Ubuntu 22.04 LTS hoặc mới hơn).
- Docker Desktop: Phiên bản hỗ trợ WSL2 engine và Docker Compose v2.
- Git: Bản 2.30 trở lên.

---

## Cấu trúc thư mục

```text
mini-soc-lab-v2/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── README.md
├── agent/
│   ├── Dockerfile
│   ├── agent.py
│   ├── requirements.txt
│   └── test_agent.py
├── attacker/
│   ├── Dockerfile
│   └── demo_traffic.sh
├── central/
│   ├── Dockerfile
│   ├── correlation.py
│   ├── db.py
│   ├── main.py
│   ├── notifications_db.py
│   ├── notifier.py
│   ├── requirements.txt
│   ├── schemas.py
│   ├── test_correlation.py
│   ├── test_db.py
│   └── test_notifier.py
├── dashboard/
│   ├── .dockerignore
│   ├── .gitignore
│   ├── Dockerfile
│   ├── index.html
│   ├── nginx.conf
│   ├── package-lock.json
│   ├── package.json
│   ├── run_tests.js
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── App.test.jsx
│       ├── index.css
│       ├── main.jsx
│       └── utils.js
├── db/
│   └── init.sql
├── sensor/
│   ├── Dockerfile
│   ├── local.rules
│   └── snort.conf
└── victim/
    └── Dockerfile
```

---

## Hướng dẫn triển khai và vận hành

### 1. Tải mã nguồn và tạo cấu hình môi trường

```bash
git clone https://github.com/soobinzinzin/mini-soc-dashboard.git
cd mini-soc-dashboard

# Tạo file .env từ template
cp .env.example .env
```

Thiết lập các biến bắt buộc trong file `.env`:
- `POSTGRES_PASSWORD`: Mật khẩu cho tài khoản PostgreSQL `minisoc`.
- `TELEGRAM_BOT_TOKEN`: Token bot từ @BotFather (tùy chọn, để trống nếu chưa tích hợp).
- `TELEGRAM_CHAT_ID`: Chat ID nhận tin nhắn cảnh báo (tùy chọn).

### 2. Khởi chạy toàn bộ hệ sinh thái dịch vụ

```bash
docker compose up -d --build
```

### 3. Kiểm tra trạng thái hệ thống và endpoints

Danh sách cổng và URL dịch vụ đang xuất bản ra máy chủ host:
- Web Dashboard: `http://localhost:5173`
- Central Ingestion & Query API: `http://127.0.0.1:8000`
- PostgreSQL Database: Port nội bộ `5432` trong mạng `net-central`.

Kiểm tra trạng thái các container:
```bash
docker compose ps
```
Xác nhận toàn bộ 13 container đều hiển thị trạng thái `Up` (riêng `soc-postgres` có trạng thái `healthy`).

Kiểm tra sức khỏe dịch vụ API trung tâm:
```bash
curl -i http://127.0.0.1:8000/health
```
Phản hồi mẫu thành công:
```json
HTTP/1.1 200 OK
{"status":"healthy","service":"ingestion-api","database":"ok","timestamp":"2026-10-18T13:18:26.443622Z"}
```

### 4. Dừng hệ thống

```bash
docker compose down
```

---

## Ghi chú an toàn thông tin

Tệp `.env` chứa mật khẩu cơ sở dữ liệu và mã khóa bí mật Telegram bot. File này đã được thêm vào `.gitignore` và tuyệt đối không bao giờ được đưa vào các bản ghi Git (commit) hoặc đẩy lên kho lưu trữ từ xa.
