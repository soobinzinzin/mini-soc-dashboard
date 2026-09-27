# Mini-SOC Lab — 3 Snort sensor mô phỏng 3 site

## Kiến trúc
- `victim-hq`, `victim-serverfarm`, `victim-dmz`: 3 máy chủ giả lập (SSH + web server), mỗi cái đại diện 1 site.
- `sensor-hq`, `sensor-serverfarm`, `sensor-dmz`: mỗi sensor share network với đúng victim của site đó (giống mô hình 1 IDS theo dõi 1 máy trong ĐACS trước đây).
- `attacker`: container Kali dùng để tấn công thử (thay cho VM Kali cũ).

## Cách chạy

```bash
cd mini-soc-lab

# Build tất cả image (lần đầu sẽ hơi lâu vì tải base image)
docker compose build

# Chạy toàn bộ 7 container (1 attacker + 3 victims + 3 sensors)
docker compose up -d

# Kiểm tra tất cả đang chạy (thấy đủ 7 container trạng thái Up)
docker compose ps
```

## Test thử tấn công

```bash
# Vào container attacker
docker exec -it attacker bash

# Trong container attacker, lấy IP của victim-hq (dùng chính tên container vì cùng network)
ping victim-hq

# Test 1: SYN Port Scan -> phải trigger sid 1000002
nmap -sS victim-hq

# Test 2: ICMP Flood -> phải trigger sid 1000001
ping -f -c 500 victim-hq

# Test 3: SSH Brute Force -> phải trigger sid 1000003
hydra -l demo -P /usr/share/wordlists/rockyou.txt ssh://victim-hq -t 4
```

## Xem alert của từng sensor

Mở terminal MỚI (ngoài container attacker), chạy:

```bash
docker exec -it sensor-hq tail -f /var/log/snort/alert
docker exec -it sensor-serverfarm tail -f /var/log/snort/alert
docker exec -it sensor-dmz tail -f /var/log/snort/alert
```

Nếu thấy dòng alert hiện ra khi bạn chạy lệnh tấn công ở trên -> sensor hoạt động đúng.

## Dừng lab

```bash
docker compose down
```

## Bước tiếp theo (sau khi lab này chạy ổn)
1. Sửa sensor để xuất alert dạng JSON thay vì text (dùng `output alert_json` hoặc barnyard2/unified2).
2. Thêm Filebeat container đọc file alert.json và đẩy qua Ingestion API (FastAPI).
3. Viết Ingestion API + PostgreSQL để lưu alert tập trung.
