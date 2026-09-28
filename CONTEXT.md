# CONTEXT — Mini-SOC Dashboard (CMP436 ĐACN)

Cập nhật lần cuối: 2026-09-28, sau review Chốt 3 của Tuần 8.
File này là ngữ cảnh ổn định. Lịch sử review nằm ở MANAGER_LOG.md. PROGRESS.md là báo cáo tự khai của Antigravity, chỉ là lời khai, không phải bằng chứng.

## 1. Đề tài

Nền tảng quản lý và trực quan hoá cảnh báo Snort IDS tập trung cho doanh nghiệp nhỏ nhiều chi nhánh.
Đồ án chuyên ngành CMP436, HUTECH, học kỳ 1 năm học 2026-2027. Sinh viên: Phan Hữu Tài.
Kế thừa đồ án trước: 1 Snort sensor, Isolation Forest, Flask dashboard, chạy trên VMware.
Giá trị cốt lõi của đồ án này: gom alert từ nhiều sensor về một nơi, gộp alert trùng, phân loại mức độ, hiển thị dashboard, cảnh báo qua Telegram.

## 2. Kiến trúc hiện tại (11 container, Docker Compose, mạng minisoc-net)

Luồng dữ liệu, với X là một trong hq, serverfarm, dmz:

attacker -> victim-X <- sensor-X (Snort, dùng chung network namespace với victim-X)
sensor-X ghi alert dạng Snort fast vào /var/log/snort/alert, bind-mount ra ./logs/X
agent-X (Python thư viện chuẩn, mount :ro) đọc file, tách thành JSON, HTTP POST
soc-central (FastAPI, POST /api/v1/telemetry, lưu trong bộ nhớ)
Kế hoạch tiếp: PostgreSQL 15, Alert Engine, React dashboard, Telegram bot.

Snort có 3 rule tự viết: sid 1000001 ICMP flood (itype:8), 1000002 TCP SYN scan, 1000003 SSH brute force.
Cả 3 rule đều Priority 0, nên mức độ nghiêm trọng phải được gán theo sid, không dùng Priority.

## 3. Các quyết định và lý do

| Quyết định | Lý do | Trạng thái |
|---|---|---|
| Docker thay VMware | Nhân bản site bằng cấu hình, nhẹ hơn nhiều so với 6 đến 9 máy ảo | Giảng viên đã đồng ý (email 2026-09-28), cho demo trên laptop cá nhân |
| Bỏ Filebeat, dùng agent Python hoặc Fluent Bit | Filebeat không có output HTTP nên không gửi thẳng tới FastAPI được | Giảng viên đồng ý cả hai và khuyên thử Fluent Bit trước để đỡ tốn công. Agent Python đã viết và test xong trước khi có trả lời. Chưa quyết giữ Python hay thử Fluent Bit. Outline v4 còn ghi Filebeat, cần sửa |
| Agent là container riêng (Phương án B), không nhét vào container sensor | Sensor dùng chung mạng với victim. Nếu agent nằm trong đó, Snort sẽ bắt luôn gói tin agent gửi đi, và rule SYN scan đang có HOME_NET any | Đã chốt |
| Agent bắt đầu đọc từ cuối file | Log lưu bền qua volume, đọc từ đầu sẽ gửi lại toàn bộ alert cũ mỗi lần restart | Đã chốt, kèm giới hạn ở mục 5 |
| Lưu tạm trong bộ nhớ trước, gắn PostgreSQL sau | Kiểm chứng luồng dữ liệu trước khi thêm database | Đã chốt |

## 4. Trạng thái

| Hạng mục | Trạng thái |
|---|---|
| Outline chi tiết v4 | Xong, chưa đổi Filebeat |
| Docker lab 3 site, 3 rule đã test | Xong (đã thấy alert từ cả 3 sensor) |
| Repo GitHub soobinzinzin/mini-soc-dashboard | Đã push commit đầu. Code T8 đã qua review, chờ commit và push |
| Tuần 8: code agent và central | Xong, 10/10 test đơn vị |
| Tuần 8: compose, 11 container chạy, cổng 8000 chỉ bind 127.0.0.1 | Xong (đã kiểm tra trong file) |
| Tuần 8: kiểm thử tấn công đầu-cuối (Chốt 3) | Đạt ở quy mô nhỏ: mỗi site 1 alert, khớp file và API 3/3, độ trễ 0.41 đến 0.94 giây (n=3) |
| PostgreSQL, Alert Engine, Dashboard, Telegram | Chưa bắt đầu. PostgreSQL là việc tiếp theo |
| Khảo sát 5+ quản trị viên IT, hình ERD | Chưa làm |
| Email hỏi giảng viên về Docker và Filebeat | Đã có trả lời ngày 2026-09-28, đồng ý cả hai |
| Yêu cầu của giảng viên: mạng riêng cho từng site, script traffic giả lập cho demo | Chưa làm. Hiện cả 3 site và attacker dùng chung 1 mạng minisoc-net |

## 5. Rủi ro và việc treo

1. Yêu cầu của giảng viên chưa thực hiện: (a) tách mạng riêng cho từng site (bridge hoặc macvlan) thay cho 1 mạng minisoc-net chung, (b) chuẩn bị script traffic giả lập cho buổi demo (attacker đã có nmap, hydra, hping3; scapy chưa cài). Việc này chỉ sửa compose và thêm script, nên làm sớm.
2. Agent chỉ đọc từ cuối file khi khởi động, nên nếu agent bị restart lúc API đang chết thì alert chưa gửi bị mất. Cần ghi vào Chương 4.2. Cách sửa sau này: lưu vị trí đã đọc.
3. Agent phát hiện file bị xoay bằng inode và kích thước. Trên thư mục mount từ Windows, hai thông số này có thể không ổn định, dẫn tới gửi trùng alert. Chốt 3 không thấy dấu hiệu này (khớp 3/3, không có dòng "rotated or truncated"), nhưng mẫu quá nhỏ. Cần test lớn hơn: tối thiểu 30 alert rải đều 3 site, số dòng file phải bằng số bản ghi trong database.
4. central: có DELETE /api/v1/telemetry không cần xác thực, CORS mở "*", timestamp khai báo là chuỗi. Xử lý ở Tuần 11 và khi gắn PostgreSQL.
5. Repo đang Public. Không commit thư mục logs/, file .env, token Telegram.
6. Fluent Bit thay agent Python cần thử có giới hạn thời gian. Lý do đáng thử: tail của Fluent Bit có thể lưu vị trí đã đọc, và có thể đệm xuống đĩa, nên có khả năng sửa giới hạn ở mục 2. Cần kiểm chứng bằng cùng bài test 30 alert. Fluent Bit gửi HTTP theo dạng danh sách bản ghi, nên central nên nhận được cả 1 object lẫn 1 danh sách object. Quyết định giữ Python hay chuyển sang Fluent Bit cần dựa trên kết quả test, không dựa trên cảm tính.

## 6. Giao thức quản lý Antigravity

Antigravity là tác nhân viết code. Các Claude là người quản lý và review.
1. Antigravity làm theo 3 chốt, dừng sau mỗi chốt và chờ người dùng nói TIẾP TỤC.
2. Báo cáo theo mẫu A đến K: trạng thái từng việc, file đã sửa, lệnh và output thật, kết quả kiểm thử, chỗ làm khác yêu cầu, giả định, việc chưa kiểm chứng, rủi ro, điều cần quyết định, git, bước tiếp.
3. Trạng thái hợp lệ: NOT_STARTED, IN_PROGRESS, DONE_VERIFIED (có output chứng minh), DONE_UNVERIFIED, FAILED, BLOCKED.
4. Antigravity không tự git commit hay push, không docker compose down -v, không sửa file ngoài phạm vi được giao.
5. Người review không tin lời khai. Phải đọc code thật, chạy lại test nếu được, đối chiếu số dòng và số lượng.
6. Chỉ một Claude gửi prompt điều khiển Antigravity. Các Claude khác chỉ nêu phát hiện. Hai Claude bất đồng thì chạy lệnh kiểm chứng, không biểu quyết.
7. Báo cáo phải ghi cỡ mẫu (n) cho mọi kết luận và nêu phạm vi đã test. Không dùng các từ như "hoàn hảo" hay "xuất sắc 100%".

## 7. Vai trò các Claude

- Quản lý chính: đọc báo cáo, đối chiếu code, viết prompt cho chốt tiếp theo, cập nhật MANAGER_LOG.md.
- Reviewer độc lập: chỉ đọc code trên GitHub, không đọc PROGRESS.md trước, tìm lỗi và lỗ hổng rồi so với báo cáo sau.
- Phản biện hội đồng: đọc Outline và code, đặt câu hỏi khó để người dùng tập bảo vệ.

## 8. Cấu trúc repo và lệnh kiểm chứng

Thư mục: attacker/, victim/, sensor/ (không sửa), agent/ (agent.py, test_agent.py), central/ (main.py, schemas.py), evidence/T8/, docker-compose.yml, PROGRESS.md, CONTEXT.md, MANAGER_LOG.md.

Kiểm chứng trong PowerShell, tại thư mục dự án:
- docker compose ps
- docker run --rm -v ${PWD}/agent:/app -w /app python:3.11-slim python test_agent.py
- curl.exe http://localhost:8000/health
