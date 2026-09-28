# BÁO CÁO TIẾN ĐỘ DỰ ÁN MINI-SOC LAB (TUẦN 8)

---

## BÁO CÁO CHỐT 1: Viết xong agent/ và central/
**Giờ hệ thống:** 2026-09-28 09:58:30 +07:00

### A. Trạng thái từng việc (Việc 1 đến 4 trong yêu cầu Tuần 8)
* **Việc 1: Topology Selection (Mô hình Asynchronous push-based)**: `DONE_UNVERIFIED`  
  *Ghi chú:* Đã thiết kế và lập trình hoàn tất `agent/agent.py` và `central/main.py`. Test hiện chỉ phủ parser, chưa kiểm chứng gửi nhận telemetry qua mạng thật (chờ kiểm chứng tại Chốt 3).
* **Việc 2: Sensor Containers (Tích hợp Python forwarding agent bên cạnh Snort 2.9)**: `IN_PROGRESS`  
  *Minh chứng:* Đã viết xong mã nguồn `agent/agent.py` và `agent/Dockerfile`. Chưa sửa `docker-compose.yml` và chưa gắn vào container theo đúng nguyên tắc Chốt 1.
* **Việc 3: End-to-End Telemetry Pipeline**: `IN_PROGRESS`  
  *Minh chứng:* Đã hoàn thiện 2 khối Shipper Agent và Central Ingestion API. Chuỗi truyền dẫn tổng thể sẽ được kiểm thử tích hợp tại Chốt 3 sau khi build & deploy tại Chốt 2.
* **Việc 4: Shipper Pipeline (Tailing alert log, convert JSON, forward POST /api/v1/telemetry)**: `DONE_UNVERIFIED`  
  *Ghi chú:* Đã viết thuật toán tailing file liên tục, chống mất log khi file bị truncate/rotate, cơ chế exponential backoff retry khi mất kết nối mạng. Test hiện chỉ phủ parser, chưa kiểm chứng đẩy dữ liệu thật.

---

### B. File đã tạo hoặc sửa
| Đường dẫn | Tạo mới hay sửa | Số dòng |
|---|---|---|
| `agent/agent.py` | Tạo mới | 173 |
| `agent/requirements.txt` | Tạo mới | 1 |
| `agent/Dockerfile` | Tạo mới | 6 |
| `agent/test_agent.py` | Tạo mới | 59 |
| `central/schemas.py` | Tạo mới | 33 |
| `central/main.py` | Tạo mới | 137 |
| `central/requirements.txt` | Tạo mới | 3 |
| `central/Dockerfile` | Tạo mới | 7 |
| `evidence/T8/test_agent_parser.txt` | Tạo mới | 9 |
| `evidence/T8/test_central_compile.txt` | Tạo mới | 7 |
| `PROGRESS.md` | Tạo mới | 115 |

---

### C. Lệnh đã chạy và output thật

#### 1. Kiểm thử unit test Parser của Shipper Agent
```powershell
docker cp C:\Users\taiph\mini-soc-lab-v2\agent victim-hq:/tmp/agent; docker exec victim-hq python3 /tmp/agent/test_agent.py
```
**Output thật:**
```text
2026-09-28 02:53:26 [WARNING] [ShipperAgent] Could not parse alert line: random unformatted log text
.....
----------------------------------------------------------------------
Ran 5 tests in 0.002s

OK
```

#### 2. Kiểm tra biên dịch cú pháp mã nguồn Central API
```powershell
docker cp C:\Users\taiph\mini-soc-lab-v2\central victim-hq:/tmp/central; docker exec victim-hq python3 -m py_compile /tmp/central/schemas.py /tmp/central/main.py
```
**Output thật:**
```text
Exit code: 0 (Không phát hiện bất kỳ lỗi cú pháp nào)
```

#### 3. Kiểm tra trạng thái Git
```powershell
git status --short
git log --oneline -5
git remote -v
```
**Output thật:**
```text
?? agent/
?? central/
?? evidence/
24bfc46 Initial commit: Mini-SOC Docker lab with 3 sensors
origin  https://github.com/soobinzinzin/mini-soc-dashboard.git (fetch)
origin  https://github.com/soobinzinzin/mini-soc-dashboard.git (push)
```

---

### D. Kết quả kiểm thử
| Bước kiểm thử | Trạng thái | Bằng chứng |
|---|---|---|
| Kiểm tra Parser ICMP Flood, SYN Scan, SSH Brute Force, Classification (`test_agent.py`) | **PASS** | 5/5 test case OK (`evidence/T8/test_agent_parser.txt`) |
| Kiểm tra biên dịch cú pháp Python `central/schemas.py` và `central/main.py` | **PASS** | `py_compile` mã trả về 0 (`evidence/T8/test_central_compile.txt`) |

---

### E. Chỗ làm khác so với yêu cầu và lý do
Không

---

### F. Giả định bạn tự đặt ra
1. **Giả định 1**: Định dạng Snort Fast Alert (`-A fast`) tương thích với mẫu thu thập thực tế từ Tuần 7:  
   `MM/DD-hh:mm:ss.uuuuuu [**] [gid:sid:rev] signature [**] [Priority: n] {PROTO} src_ip:src_port -> dst_ip:dst_port`.
2. **Giả định 2**: Central Ingestion API sử dụng cổng 8000 trong mạng nội bộ Docker `minisoc-net`, URL endpoint tiếp nhận là `http://soc-central:8000/api/v1/telemetry`.
3. **Giả định 3**: Shipper Agent dùng thư viện chuẩn `urllib` để tối ưu kích thước container, không phụ thuộc vào `pip` cài thêm bên trong sensor, nhưng vẫn chuẩn bị `requirements.txt` để hỗ trợ môi trường bên ngoài.

---

### G. Những gì chưa kiểm chứng hoặc chưa làm
* Chưa sửa `docker-compose.yml` (tuân thủ nghiêm ngặt nguyên tắc Chốt 1).
* Chưa build Docker images mới.
* Chưa kiểm thử gửi nhận telemetry trực tiếp giữa các container qua mạng Docker bridge (sẽ thực hiện ở Chốt 3).

---

### H. Lỗi hoặc rủi ro phát hiện thêm (chỉ báo cáo)
* **Rủi ro 1**: Toàn bộ container lab hiện đang ở trạng thái `Exited (137)` do máy trạm/server vừa được khởi động lại. Cần chạy `docker compose up -d` ở Chốt 2 để bật lại.
* **Rủi ro 2**: Do các container sensor phụ thuộc vào namespace mạng của victim (`network_mode: "service:victim-*"`), cần đảm bảo victim khởi động lành lặn trước sensor.

---

### I. Điều cần tôi quyết định
Để chuẩn bị bước sang Chốt 2 (sửa `docker-compose.yml` và build), xin ý kiến bạn chọn 1 trong 2 phương án kiến trúc sau:
* **Phương án A (Khuyến nghị theo đặc tả Tuần 8)**: Tích hợp Python Forwarding Agent chạy trực tiếp trong từng container sensor (`sensor-hq`, `sensor-serverfarm`, `sensor-dmz`) song song cùng tiến trình Snort bằng script `entrypoint.sh`.
* **Phương án B**: Tách Python Shipper thành 3 container riêng biệt (`shipper-hq`, `shipper-serverfarm`, `shipper-dmz`) mount chung volume logs với sensor.

---

### J. Git
* `git status --short`:
  ```text
  ?? agent/
  ?? central/
  ?? evidence/
  ?? PROGRESS.md
  ```
* `git log --oneline -5`:
  ```text
  24bfc46 Initial commit: Mini-SOC Docker lab with 3 sensors
  ```
* `git remote -v`:
  ```text
  origin	https://github.com/soobinzinzin/mini-soc-dashboard.git (fetch)
  origin	https://github.com/soobinzinzin/mini-soc-dashboard.git (push)
  ```

---

### K. Bước tiếp theo đề xuất (không tự làm)
Chờ bạn phê duyệt lựa chọn ở **Mục I** và phản hồi **"TIẾP TỤC"** để chuyển sang **Chốt 2**: Sửa `docker-compose.yml`, cấu hình service `soc-central` và các sensor, build image và khởi động toàn bộ lab (`docker compose up -d`).

---
---

## BÁO CÁO CHỐT 2: Sửa docker-compose.yml, build và up xong (Chưa chạy kiểm thử)
**Giờ hệ thống:** 2026-09-28 10:15:00 +07:00

### A. Trạng thái từng việc (Việc 1 đến 4 trong yêu cầu Tuần 8)
* **Việc 1: Topology Selection (Mô hình Asynchronous push-based)**: `DONE_UNVERIFIED`  
  *Ghi chú:* Kiến trúc Phương án B: 3 container agent độc lập trên mạng `minisoc-net` đọc volume log `:ro`, gửi JSON trực tiếp đến `http://soc-central:8000/api/v1/telemetry`. Toàn bộ container đã UP, chờ kiểm chứng với lưu lượng tấn công thật ở Chốt 3.
* **Việc 2: Sensor Containers (Tích hợp Python forwarding agent bên cạnh Snort 2.9)**: `DONE_UNVERIFIED`  
  *Ghi chú:* Cả 3 sensor giữ nguyên cấu hình sniffing (`network_mode: service:victim-*`). 3 agent độc lập (`agent-hq`, `agent-serverfarm`, `agent-dmz`) đã khởi động thành công và gắn kết vào alert file tương ứng. Đã có output `docker compose ps` chứng minh cả 11/11 container đều `Up`, nhưng cần chờ bằng chứng bắt alert thực tế ở Chốt 3 để verify.
* **Việc 3: End-to-End Telemetry Pipeline**: `IN_PROGRESS`  
  *Minh chứng:* Các thành phần từ Attacker -> Victim/Sensor -> File log -> Shipper Agent -> Central Ingestion API đã sẵn sàng trên cùng mạng container. Sẽ kiểm thử kết nối toàn trình ở Chốt 3.
* **Việc 4: Shipper Pipeline (Tailing alert log, convert JSON, forward POST /api/v1/telemetry)**: `DONE_UNVERIFIED`  
  *Ghi chú:* Đã hoàn thiện logic: drop HTTP 4xx, retry HTTP 5xx/lỗi mạng, chuẩn hóa timestamp UTC lùi 1 năm nếu ở tương lai > 1 ngày, cơ chế truncate file. Bộ test 10/10 PASS. Đang chờ kiểm chứng chuyển phát lưu lượng thật ở Chốt 3.

---

### B. File đã tạo hoặc sửa
| Đường dẫn | Tạo mới hay sửa | Số dòng |
|---|---|---|
| `agent/agent.py` | Sửa | 234 |
| `agent/Dockerfile` | Sửa | 4 |
| `agent/requirements.txt` | Sửa | 1 |
| `agent/test_agent.py` | Sửa | 213 |
| `docker-compose.yml` | Sửa | 122 |
| `evidence/T8/test_agent_full.txt` | Tạo mới | 22 |
| `PROGRESS.md` | Sửa | 265 |

---

### C. Lệnh đã chạy và output thật

#### 1. Kiểm thử đầy đủ bộ test Shipper Agent (10 test cases)
```powershell
docker run --rm -v C:\Users\taiph\mini-soc-lab-v2\agent:/app -w /app python:3.11-slim python test_agent.py
```
**Output thật:**
```text
2026-09-28 03:11:57 [WARNING] [ShipperAgent] Could not parse alert line: random unformatted log text
.....2026-09-28 03:11:57 [INFO] [ShipperAgent] Starting Shipper Agent for [sensor-hq] (Site: hq)
2026-09-28 03:11:57 [INFO] [ShipperAgent] Monitoring file: /tmp/tmpej3uynip
2026-09-28 03:11:57 [INFO] [ShipperAgent] Target Ingestion URL: http://mock-api/telemetry
2026-09-28 03:11:57 [INFO] [ShipperAgent] Found alert file: /tmp/tmpej3uynip. Attaching tail stream.
2026-09-28 03:11:57 [INFO] [ShipperAgent] Alert file rotated or truncated. Re-opening...
.2026-09-28 03:11:57 [ERROR] [ShipperAgent] HTTP 422 Client Error (Unprocessable Entity). Dropping alert. Raw log: test raw log line
2026-09-28 03:11:57 [WARNING] [ShipperAgent] Alert dropped for SID 1000001 due to client error (HTTP 4xx).
.2026-09-28 03:11:57 [WARNING] [ShipperAgent] HTTP 500 Server Error (Internal Server Error). Will retry.
2026-09-28 03:11:57 [WARNING] [ShipperAgent] Delivery failed for SID 1000002. Retrying in 0.0s...
2026-09-28 03:11:58 [INFO] [ShipperAgent] Forwarded alert [SID:1000002] 'Test Scan' from 10.0.0.1 to 10.0.0.2
.2026-09-28 03:11:58 [INFO] [ShipperAgent] Starting Shipper Agent for [sensor-hq] (Site: hq)
2026-09-28 03:11:58 [INFO] [ShipperAgent] Monitoring file: /tmp/tmp_bmr_mrc
2026-09-28 03:11:58 [INFO] [ShipperAgent] Target Ingestion URL: http://mock-api/telemetry
2026-09-28 03:11:58 [INFO] [ShipperAgent] Found alert file: /tmp/tmp_bmr_mrc. Attaching tail stream.
..
----------------------------------------------------------------------
Ran 10 tests in 0.370s

OK
```

#### 2. Kiểm tra trạng thái 11 containers (`docker compose ps`)
```powershell
docker compose ps
```
**Output thật:**
```text
NAME                IMAGE                                                                     COMMAND                  SERVICE             CREATED          STATUS          PORTS
agent-dmz           mini-soc-lab-v2-agent-dmz                                                 "python agent.py"        agent-dmz           13 seconds ago   Up 11 seconds   
agent-hq            mini-soc-lab-v2-agent-hq                                                  "python agent.py"        agent-hq            13 seconds ago   Up 12 seconds   
agent-serverfarm    mini-soc-lab-v2-agent-serverfarm                                          "python agent.py"        agent-serverfarm    13 seconds ago   Up 11 seconds   
attacker            sha256:94f2454fab504bea4f0240fb4eb5bc461ad516b4c0dba32136f2b8c5007adc33   "sleep infinity"         attacker            12 hours ago     Up 12 seconds   
sensor-dmz          sha256:b267b3e65eacdb8bebb2dd23659850722a7180fb42004f774fff3bd4bd355e1c   "snort -q -k none -c…"   sensor-dmz          12 hours ago     Up 11 seconds   
sensor-hq           sha256:39ba4b72c2823023b63fae56343335eec226a195122eb88462e6dc1ab4be27a3   "snort -q -k none -c…"   sensor-hq           12 hours ago     Up 11 seconds   
sensor-serverfarm   sha256:34ce5c0f53e25bc98b096f63935370627ec18dfc2c20f49ba7bbf68c1eb90e92   "snort -q -k none -c…"   sensor-serverfarm   12 hours ago     Up 12 seconds   
soc-central         mini-soc-lab-v2-soc-central                                               "uvicorn main:app --…"   soc-central         13 seconds ago   Up 12 seconds   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
victim-dmz          sha256:520606af0aa7080b51c973fa3225c8df58f97a6ab661645aeaea632f88bedfb7   "/bin/sh -c 'service…"   victim-dmz          12 hours ago     Up 12 seconds   22/tcp, 80/tcp
victim-hq           sha256:edcadd6eb4bb580e6ee41cb9d24b2a7c3b76dea54318f819d396524cbb9862fb   "/bin/sh -c 'service…"   victim-hq           12 hours ago     Up 12 seconds   22/tcp, 80/tcp
victim-serverfarm   sha256:0c2b450870d2acac1bf489bc0935ca4d8cb83f1ff5e10504d0336b38c5d3aad4   "/bin/sh -c 'service…"   victim-serverfarm   12 hours ago     Up 13 seconds   22/tcp, 80/tcp
```

#### 3. Log của service `soc-central`
```powershell
docker logs soc-central
```
**Output thật:**
```text
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

#### 4. Log của service `agent-hq`
```powershell
docker logs agent-hq
```
**Output thật:**
```text
2026-09-28 03:13:47 [INFO] [ShipperAgent] Starting Shipper Agent for [sensor-hq] (Site: hq)
2026-09-28 03:13:47 [INFO] [ShipperAgent] Monitoring file: /var/log/snort/alert
2026-09-28 03:13:47 [INFO] [ShipperAgent] Target Ingestion URL: http://soc-central:8000/api/v1/telemetry
2026-09-28 03:13:47 [INFO] [ShipperAgent] Found alert file: /var/log/snort/alert. Attaching tail stream.
```

#### 5. Kiểm tra Endpoint Health của Central API
```powershell
curl.exe http://localhost:8000/health
```
**Output thật:**
```text
{"status":"healthy","service":"ingestion-api","timestamp":"2026-09-28T03:14:15.378927Z","buffered_records":0}
```

---

### D. Kết quả kiểm thử
| Bước kiểm thử | Trạng thái | Bằng chứng |
|---|---|---|
| Kiểm thử đầy đủ 10 test case `test_agent.py` (Parser, Timestamp rollback, 422 Drop, 500 Retry, Tail Stream, Truncate) | **PASS** | `Ran 10 tests in 0.370s - OK` (`evidence/T8/test_agent_full.txt`) |
| Khởi động 11 container qua `docker compose up -d --build` | **PASS** | Tất cả 11 service đều `Up` |
| Kiểm tra endpoint `/health` của `soc-central` | **PASS** | HTTP 200 `{"status":"healthy","service":"ingestion-api",...}` |
| Kết nối file log của `agent-hq` | **PASS** | Log ghi nhận `Found alert file... Attaching tail stream.` |

---

### E. Chỗ làm khác so với yêu cầu và lý do
Không

---

### F. Giả định bạn tự đặt ra
1. **Giả định 1**: Các volume log `./logs/<site>` được mount dạng read-only (`:ro`) cho agent để bảo đảm tính toàn vẹn dữ liệu, chỉ container sensor mới có quyền ghi vào thư mục log.
2. **Giả định 2**: Khi chưa phát sinh tấn công mới, số lượng bản ghi `buffered_records` tại central API khởi đầu bằng `0`.

---

### G. Những gì chưa kiểm chứng hoặc chưa làm
* CHƯA chạy bất kỳ lệnh tấn công nào (`nmap`, `ping flood`, `hydra`) từ container `attacker`.
* CHƯA chạy 6 bước kiểm thử của Chốt 3.

---

### H. Lỗi hoặc rủi ro phát hiện thêm (chỉ báo cáo)
* Không phát hiện lỗi phát sinh trong quá trình build và khởi chạy 11 container.
* Phát hiện lỗi 503 "failed to get load code assist response" xuất hiện từ phía dịch vụ AI/hệ thống giữa lúc tạo file (không ảnh hưởng tới mã nguồn cục bộ).

---

### I. Điều cần tôi quyết định
Xác nhận toàn bộ các service Chốt 2 đã khởi động đúng yêu cầu và cho phép chuyển sang **Chốt 3** (Tiến hành 6 bước kiểm thử tấn công và đối chiếu telemetry end-to-end).

---

### J. Git
* `git status --short`:
  ```text
   M docker-compose.yml
  ?? PROGRESS.md
  ?? agent/
  ?? central/
  ?? evidence/
  ```
* `git log --oneline -5`:
  ```text
  24bfc46 Initial commit: Mini-SOC Docker lab with 3 sensors
  ```
* `git remote -v`:
  ```text
  origin	https://github.com/soobinzinzin/mini-soc-dashboard.git (fetch)
  origin	https://github.com/soobinzinzin/mini-soc-dashboard.git (push)
  ```

---

### K. Bước tiếp theo đề xuất (không tự làm)
Chờ bạn phê duyệt lựa chọn ở **Mục I** và phản hồi **"TIẾP TỤC"** để chuyển sang **Chốt 3**: Thực hiện 6 bước kiểm thử tấn công (SYN scan, ICMP flood, SSH brute-force trên các site), xác minh telemetry được chuyển phát về Central Ingestion API, xuất báo cáo Chốt 3 và lưu raw evidence.

---
---

## BÁO CÁO CHỐT 3: Chạy xong các bước kiểm thử tấn công, đối chiếu, độ trễ và chịu lỗi
**Giờ hệ thống:** 2026-09-28 10:32:00 +07:00

### A. Trạng thái từng việc (Việc 1 đến 4 trong yêu cầu Tuần 8)
* **Việc 1: Topology Selection (Mô hình Asynchronous push-based)**: `DONE_VERIFIED`  
  *Minh chứng:* 3 shipper agent độc lập đã chuyển phát 3/3 alert sang `http://soc-central:8000/api/v1/telemetry` theo mô hình push-based bất đồng bộ. Đã đối chiếu số lượng alert sinh ra và bản ghi tại API khớp 3/3 alert (mỗi site 1 alert), không bị drop hoặc trùng lặp (chứng minh tại Bước 4, Bước 6, Bước 7).
* **Việc 2: Sensor Containers (Sites A, B, C)**: `DONE_VERIFIED`  
  *Minh chứng:* Cả 3 sensor (`sensor-hq`, `sensor-serverfarm`, `sensor-dmz`) đều phát hiện các cuộc tấn công (`nmap`, `ping flood`, `hydra`), ghi log vào `/var/log/snort/alert` và được các agent tương ứng gắn kết stream đẩy đi (n=1 alert mỗi site).
* **Việc 3: End-to-End Telemetry Pipeline**: `DONE_VERIFIED`  
  *Minh chứng:* Toàn trình từ Gói tin tấn công (Attacker) -> Snort Engine (Sensor) -> Alert log -> Python Shipper Agent (parse JSON) -> Ingestion API (`soc-central`) đã chuyển phát khớp 3/3 alert, mỗi site 1 alert. Độ trễ toàn trình đo được từ 0.4071s đến 0.9359s (n=3 mẫu, toàn bộ dưới 1 giây, chứng minh tại Bước 5).
* **Việc 4: Shipper Pipeline (Tailing alert log, convert JSON, forward POST /api/v1/telemetry)**: `DONE_VERIFIED`  
  *Minh chứng:* Tailing log khớp số lượng (Bước 4, n=3 alert). Retry thành công khi API mất khoảng 30 giây, n=1 alert, agent không bị restart (Bước 6). Khởi động lại agent không bị gửi trùng lặp (Bước 7, n=1 alert).

---

### B. File đã tạo hoặc sửa
| Đường dẫn | Tạo mới hay sửa | Số dòng |
|---|---|---|
| `docker-compose.yml` | Sửa | 122 |
| `evidence/T8/chot3-buoc0.txt` | Tạo mới | 18 |
| `evidence/T8/chot3-buoc1.txt` | Tạo mới | 14 |
| `evidence/T8/chot3-buoc2.txt` | Tạo mới | 9 |
| `evidence/T8/chot3-buoc3.txt` | Tạo mới | 10 |
| `evidence/T8/chot3-buoc4.txt` | Tạo mới | 18 |
| `evidence/T8/chot3-buoc5.txt` | Tạo mới | 22 |
| `evidence/T8/chot3-buoc6.txt` | Tạo mới | 36 |
| `evidence/T8/chot3-buoc7.txt` | Tạo mới | 23 |
| `PROGRESS.md` | Sửa | 477 |

---

### C. Lệnh đã chạy và output thật

#### Bước 0: Ghi mốc số dòng ban đầu và reset buffer API
```powershell
(Get-Content logs\hq\alert | Measure-Object -Line).Lines
(Get-Content logs\serverfarm\alert | Measure-Object -Line).Lines
(Get-Content logs\dmz\alert | Measure-Object -Line).Lines
curl.exe -s -X DELETE http://localhost:8000/api/v1/telemetry
curl.exe -s http://localhost:8000/api/v1/telemetry/stats
```
**Output thật:**
```text
391
4
4
{"status":"success","cleared_records":0}
{"total_received":0,"by_site":{},"by_signature":{},"by_protocol":{}}
```

#### Bước 1: Nmap SYN scan vào victim-dmz
```powershell
docker exec attacker nmap -sS -p 1-100 victim-dmz; Start-Sleep -Seconds 10
```
**Output thật:**
```text
Starting Nmap 7.99 ( https://nmap.org ) at 2026-09-28 03:26 +0000
Nmap scan report for victim-dmz (172.19.0.3)
Host is up (0.0000070s latency).
rDNS record for 172.19.0.3: victim-dmz.mini-soc-lab-v2_minisoc-net
Not shown: 98 closed tcp ports (reset)
PORT   STATE SERVICE
22/tcp open  ssh
80/tcp open  http
MAC Address: 66:15:A9:96:EE:8F (Unknown)

Nmap done: 1 IP address (1 host up) scanned in 0.17 seconds
```

#### Bước 2: ICMP Flood vào victim-hq
```powershell
docker exec attacker ping -f -c 200 victim-hq; Start-Sleep -Seconds 10
```
**Output thật:**
```text
PING victim-hq (172.19.0.4) 56(84) bytes of data.
.   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   
--- victim-hq ping statistics ---
200 packets transmitted, 200 received, 0% packet loss, time 1ms
rtt min/avg/max/mdev = 0.005/0.006/0.097/0.006 ms, ipg/ewma 0.007/0.006 ms
```

#### Bước 3: SSH Brute Force vào victim-serverfarm
```powershell
docker exec attacker timeout 60 hydra -l demo -P /usr/share/wordlists/rockyou.txt ssh://victim-serverfarm -t 4; Start-Sleep -Seconds 10
```
**Output thật:**
```text
Hydra v9.7 (c) 2023 by van Hauser/THC & David Maciejak - Please do not use in military or secret service organizations, or for illegal purposes (this is non-binding, these *** ignore laws and ethics anyway).

Hydra (https://github.com/vanhauser-thc/thc-hydra) starting at 2026-09-28 03:27:13
[WARNING] Restorefile (you have 10 seconds to abort... (use option -I to skip waiting)) from a previous session found, to prevent overwriting, ./hydra.restore
[DATA] max 4 tasks per 1 server, overall 4 tasks, 14344399 login tries (l:1/p:14344399), ~3586100 tries per task
[DATA] attacking ssh://victim-serverfarm:22/
The session file ./hydra.restore was written. Type "hydra -R" to resume session.
```

#### Bước 4: Đối chiếu số lượng alert giữa File và API
```powershell
(Get-Content logs\hq\alert | Measure-Object -Line).Lines
(Get-Content logs\serverfarm\alert | Measure-Object -Line).Lines
(Get-Content logs\dmz\alert | Measure-Object -Line).Lines
curl.exe -s http://localhost:8000/api/v1/telemetry/stats
```
**Output thật:**
```text
392
5
5
{"total_received":3,"by_site":{"dmz":1,"hq":1,"serverfarm":1},"by_signature":{"TCP SYN Port Scan Detected":1,"ICMP Flood Attack Detected":1,"SSH Brute Force Attempt":1},"by_protocol":{"TCP":2,"ICMP":1}}
```

#### Bước 5: Đo độ trễ chuyển phát (Latency)
```powershell
curl.exe -s http://localhost:8000/api/v1/telemetry?limit=5
```
**Output thật:**
```text
[{"timestamp":"2026-09-28T03:27:24.354797Z","sensor_id":"sensor-serverfarm","site":"serverfarm","sid":1000003,"gid":1,"rev":2,"signature":"SSH Brute Force Attempt","classification":null,"priority":0,"protocol":"TCP","src_ip":"172.19.0.5","src_port":59764,"dst_ip":"172.19.0.2","dst_port":22,"raw_log":"09/28-03:27:24.354797  [**] [1:1000003:2] SSH Brute Force Attempt [**] [Priority: 0] {TCP} 172.19.0.5:59764 -> 172.19.0.2:22","telemetry_id":"c2775260-628c-449e-bd1a-96ff1f21b5ad","received_at":"2026-09-28T03:27:24.761878Z"},{"timestamp":"2026-09-28T03:26:37.071322Z","sensor_id":"sensor-hq","site":"hq","sid":1000001,"gid":1,"rev":2,"signature":"ICMP Flood Attack Detected","classification":null,"priority":0,"protocol":"ICMP","src_ip":"172.19.0.5","src_port":null,"dst_ip":"172.19.0.4","dst_port":null,"raw_log":"09/28-03:26:37.071322  [**] [1:1000001:2] ICMP Flood Attack Detected [**] [Priority: 0] {ICMP} 172.19.0.5 -> 172.19.0.4","telemetry_id":"e932059c-2e44-4006-bd10-579073f46e18","received_at":"2026-09-28T03:26:38.007178Z"},{"timestamp":"2026-09-28T03:26:09.513372Z","sensor_id":"sensor-dmz","site":"dmz","sid":1000002,"gid":1,"rev":2,"signature":"TCP SYN Port Scan Detected","classification":null,"priority":0,"protocol":"TCP","src_ip":"172.19.0.5","src_port":46207,"dst_ip":"172.19.0.3","dst_port":5,"raw_log":"09/28-03:26:09.513372  [**] [1:1000002:2] TCP SYN Port Scan Detected [**] [Priority: 0] {TCP} 172.19.0.5:46207 -> 172.19.0.3:5","telemetry_id":"3c870368-8ac2-4f1a-a3a6-6d6d7c7c3bc5","received_at":"2026-09-28T03:26:10.057378Z"}]
```

#### Bước 6: Kiểm thử chịu lỗi (Fault Tolerance khi Ingestion API tắt)
```powershell
docker compose stop soc-central
docker exec attacker ping -f -c 200 victim-hq
Start-Sleep -Seconds 15
docker logs agent-hq --tail 5
docker compose start soc-central
Start-Sleep -Seconds 45
(Get-Content logs\hq\alert | Measure-Object -Line).Lines
curl.exe -s http://localhost:8000/api/v1/telemetry/stats
docker logs agent-hq --tail 5
```
**Output thật:**
```text
Container soc-central Stopping
Container soc-central Stopped
PING victim-hq (172.19.0.4) 56(84) bytes of data.
--- victim-hq ping statistics ---
200 packets transmitted, 200 received, 0% packet loss, time 4ms

[Log Agent Retry]:
2026-09-28 03:30:14 [WARNING] [ShipperAgent] Network error reaching http://soc-central:8000/api/v1/telemetry: <urlopen error [Errno -3] Temporary failure in name resolution>. Will retry.
2026-09-28 03:30:14 [WARNING] [ShipperAgent] Delivery failed for SID 1000001. Retrying in 4.0s...
2026-09-28 03:30:26 [WARNING] [ShipperAgent] Network error reaching http://soc-central:8000/api/v1/telemetry: <urlopen error [Errno -3] Temporary failure in name resolution>. Will retry.
2026-09-28 03:30:26 [WARNING] [ShipperAgent] Delivery failed for SID 1000001. Retrying in 8.0s...

[Sau khi API start lại]:
Container soc-central Starting
Container soc-central Started
393
{"total_received":1,"by_site":{"hq":1},"by_signature":{"ICMP Flood Attack Detected":1},"by_protocol":{"ICMP":1}}
2026-09-28 03:30:34 [INFO] [ShipperAgent] Forwarded alert [SID:1000001] 'ICMP Flood Attack Detected' from 172.19.0.5 to 172.19.0.4
```

#### Bước 7: Kiểm thử không gửi trùng khi Restart Agent
```powershell
curl.exe -s http://localhost:8000/api/v1/telemetry/stats
docker restart agent-hq
Start-Sleep -Seconds 10
curl.exe -s http://localhost:8000/api/v1/telemetry/stats
docker logs agent-hq
```
**Output thật:**
```text
{"total_received":1,"by_site":{"hq":1},"by_signature":{"ICMP Flood Attack Detected":1},"by_protocol":{"ICMP":1}}
agent-hq
{"total_received":1,"by_site":{"hq":1},"by_signature":{"ICMP Flood Attack Detected":1},"by_protocol":{"ICMP":1}}
2026-09-28 03:31:24 [INFO] [ShipperAgent] Starting Shipper Agent for [sensor-hq] (Site: hq)
2026-09-28 03:31:24 [INFO] [ShipperAgent] Monitoring file: /var/log/snort/alert
2026-09-28 03:31:24 [INFO] [ShipperAgent] Target Ingestion URL: http://soc-central:8000/api/v1/telemetry
2026-09-28 03:31:24 [INFO] [ShipperAgent] Found alert file: /var/log/snort/alert. Attaching tail stream.
```

---

### D. Kết quả kiểm thử
| Bước kiểm thử | Trạng thái | Bằng chứng |
|---|---|---|
| Bước 0: Reset API buffer và lấy baseline file alert | **PASS** | `total_received = 0`, file hq: 391, serverfarm: 4, dmz: 4 (`evidence/T8/chot3-buoc0.txt`) |
| Bước 1: SYN Scan vào `victim-dmz` | **PASS** | Snort dmz bắt alert, API nhận 1 bản ghi `dmz` (`evidence/T8/chot3-buoc1.txt`) |
| Bước 2: ICMP Flood vào `victim-hq` | **PASS** | Snort hq bắt alert, API nhận 1 bản ghi `hq` (`evidence/T8/chot3-buoc2.txt`) |
| Bước 3: SSH Brute Force vào `victim-serverfarm` | **PASS** | Snort serverfarm bắt alert, API nhận 1 bản ghi `serverfarm` (`evidence/T8/chot3-buoc3.txt`) |
| Bước 4: Đối chiếu số lượng giữa file log và API stats | **PASS** | Khớp 3/3 alert: 3 dòng mới = 3 bản ghi API (hq:1, sf:1, dmz:1) (`evidence/T8/chot3-buoc4.txt`) |
| Bước 5: Đo độ trễ chuyển phát telemetry (Latency) | **PASS** | Min: 0.4071s, Max: 0.9359s (n=3 mẫu, đều < 1 giây) (`evidence/T8/chot3-buoc5.txt`) |
| Bước 6: Khả năng chịu lỗi khi API tắt (Fault Tolerance) | **PASS** | Agent retry 2s -> 4s -> 8s; API mở lại nhận đúng 1 bản ghi, n=1 alert (`evidence/T8/chot3-buoc6.txt`) |
| Bước 7: Không gửi trùng khi Restart Agent | **PASS** | `total_received` giữ nguyên 1, không có cảnh báo rotated/truncated (`evidence/T8/chot3-buoc7.txt`) |

---

### E. Chỗ làm khác so với yêu cầu và lý do
Điều kiện tiên quyết số 3 (log agent-serverfarm và agent-dmz có dòng Attaching tail stream) không được báo cáo. Bằng chứng gián tiếp: API đã nhận bản ghi từ cả hai site này ở Bước 1 và Bước 3.

---

### F. Giả định bạn tự đặt ra
1. **Giả định 1**: Cấu trúc fast alert của Snort phù hợp với regex chuẩn hóa trong `agent.py`.
2. **Giả định 2**: Khi `soc-central` bị restart ở Bước 6, buffer in-memory bị xóa và tiếp nhận bản ghi retry từ `agent-hq` sau khi service chạy lại.

---

### G. Những gì chưa kiểm chứng hoặc chưa làm
* Chưa lưu trữ telemetry vào cơ sở dữ liệu quan hệ PostgreSQL (thuộc phạm vi Tuần 9).
* Chưa xử lý luật tương quan (Correlation Rules / Triage Engine) và giao diện React Dashboard (thuộc phạm vi Tuần 9 - 10).

---

### H. Lỗi hoặc rủi ro phát hiện thêm (chỉ báo cáo)
* Cảnh báo `WARNING: Restorefile found` trong Hydra do phiên tấn công trước tạo file cache session (không gây ảnh hưởng đến tấn công).
* Các giới hạn đã biết:
  - Agent bắt đầu đọc từ cuối file, nên nếu agent restart lúc API đang chết thì alert chưa gửi bị mất. Chưa được test.
  - Bước 6 restart soc-central làm bộ nhớ bị xóa nên không chứng minh gì về dữ liệu cũ.
  - Mẫu nhỏ (mỗi lần tấn công chỉ sinh 1 alert do threshold type both) nên chưa loại trừ được rủi ro inode hoặc size không ổn định trên mount Windows.

---

### I. Điều cần tôi quyết định
Chốt 3 đạt ở quy mô nhỏ, cần test khối lượng lớn hơn (tối thiểu 30 alert rải đều 3 site) ở giai đoạn PostgreSQL trước khi kết luận không mất và không trùng.

---

### J. Git
* `git status --short`:
  ```text
   M docker-compose.yml
  ?? PROGRESS.md
  ?? agent/
  ?? central/
  ?? evidence/
  ```
* `git log --oneline -5`:
  ```text
  24bfc46 Initial commit: Mini-SOC Docker lab with 3 sensors
  ```
* `git remote -v`:
  ```text
  origin	https://github.com/soobinzinzin/mini-soc-dashboard.git (fetch)
  origin	https://github.com/soobinzinzin/mini-soc-dashboard.git (push)
  ```

---

### K. Bước tiếp theo đề xuất (không tự làm)
Chờ bạn phê duyệt báo cáo Chốt 3, sau đó cho phép commit/push code Tuần 8 lên GitHub và chuyển sang **Tuần 9: Database PostgreSQL + Triage Engine (Correlation Rules)**.
