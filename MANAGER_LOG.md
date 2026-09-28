# MANAGER_LOG — Nhật ký review của người quản lý

Quy ước: mỗi mục ghi những gì đã tự kiểm chứng, những gì phát hiện, và quyết định. Claude nào review tiếp thì thêm mục mới ở cuối, không sửa mục cũ.

## Chốt 1 (Tuần 8): viết xong agent/ và central/

Đã tự kiểm chứng:
- Parser của agent đọc đúng 399/399 dòng alert thật từ 3 file log.
- central trả HTTP 201 và agent chấp nhận 200 hoặc 201. Các trường agent gửi khớp schema của central.
- Không file nào đã commit bị sửa.

Phát hiện:
1. Antigravity khuyến nghị đặt agent chung container sensor (Phương án A). Sai, vì Snort sẽ bắt luôn gói tin agent gửi đi. Chọn Phương án B, agent là container riêng.
2. Báo cáo ghi DONE_VERIFIED cho Việc 1 và Việc 4 nhưng 5 test chỉ phủ parser. Phần đọc file liên tục, retry chưa được test.
3. forward_with_retry retry vô hạn kể cả với lỗi 4xx, có thể làm agent kẹt trên một alert hỏng.
4. Timestamp thiếu xử lý chuyển năm.
5. central: DELETE không xác thực, CORS mở "*", timestamp là chuỗi.
6. requests nằm trong requirements.txt nhưng code dùng urllib.

Quyết định: cho sang Chốt 2 kèm 6 điều chỉnh bắt buộc.

## Chốt 2 (Tuần 8): sửa compose, build, chạy

Đã tự kiểm chứng:
- Chạy lại bộ test trong môi trường khác (Python 3.12): 10/10 OK. Các test có thật: bỏ alert khi 4xx, retry khi 500 rồi 201, lùi năm timestamp, đọc dòng mới, file bị cắt ngắn.
- docker-compose.yml đúng đặc tả: 3 agent riêng, không dùng network_mode, volume :ro, biến môi trường khớp code, có depends_on và restart.
- sensor/, victim/, attacker/, central/ giống hệt bản trước.
- Số dòng khớp báo cáo (PowerShell đếm dòng không rỗng), trừ PROGRESS.md ghi 230 là số chưa đo, thực tế 263 dòng không rỗng.

Phát hiện:
1. Việc 2 ghi DONE_VERIFIED nhưng bằng chứng chỉ là container Up và log của agent-hq.
2. Mục H ghi không có lỗi, nhưng log tool có lỗi 503 của dịch vụ Antigravity giữa lúc tạo file.
3. Cổng 8000 mở ra mọi card mạng trong khi API không xác thực. Đổi thành 127.0.0.1:8000:8000.
4. Giới hạn: agent restart lúc API chết thì mất alert chưa gửi.
5. Rủi ro: inode và kích thước file có thể không ổn định trên mount Windows, gây gửi trùng.

Quyết định: cho sang Chốt 3 kèm điều chỉnh.

## Chốt 3 (Tuần 8): kiểm thử tấn công đầu-cuối

Kết luận: ĐẠT ở quy mô nhỏ. Cho commit và push code Tuần 8. Chưa được khẳng định "không mất, không trùng alert" ở quy mô lớn.

Đã tự kiểm chứng:
- Các điều chỉnh của Chốt 2 đã được làm: Việc 2 hạ về DONE_UNVERIFIED trong mục Chốt 2, lỗi 503 đã được ghi vào mục H, số dòng PROGRESS.md đã đo lại (475 dòng không rỗng, khớp), cổng 8000 đã đổi thành 127.0.0.1:8000 (thấy trong docker-compose.yml).
- Số dòng của 8 file evidence khớp bảng B trong báo cáo.
- Độ trễ tính lại từ output thô: 0.4071, 0.5440, 0.9359 giây, trung bình 0.6290. Khớp.
- Đối chiếu Bước 4: dmz 4 sang 5, hq 391 sang 392, serverfarm 4 sang 5. Mỗi site tăng 1 dòng và API nhận đúng 1 bản ghi mỗi site. Khớp.
- Bước 6: agent retry sau 2, 4, 8 giây, gửi thành công lúc API bật lại. Bước 7: restart agent thì total_received không đổi.

Phát hiện:
1. Cỡ mẫu rất nhỏ. Rule dùng threshold "type both" nên mỗi lần tấn công chỉ sinh 1 alert. Kết luận "khớp 100%, không trùng, không mất" dựa trên 3 alert (Bước 4) và 1 alert (Bước 6). Chưa đủ để loại trừ rủi ro inode và kích thước file trên mount Windows.
2. Việc 4 ghi "không rớt alert khi API gặp sự cố" mà không nêu phạm vi. Chỉ đã test trường hợp API mất khoảng 30 giây và agent vẫn sống. Giới hạn đã biết (agent restart lúc API chết thì mất alert chưa gửi) không được ghi ở mục H.
3. Trong Bước 6, soc-central restart nên bộ nhớ bị xóa. Bước này chỉ chứng minh alert bị kẹt được gửi lại, không chứng minh gì về dữ liệu cũ.
4. Điều kiện tiên quyết số 3 (log của agent-serverfarm và agent-dmz có dòng "Attaching tail stream") không được báo cáo và mục E ghi "Không" về chỗ làm khác. Bằng chứng gián tiếp vẫn có: API nhận được bản ghi từ cả site serverfarm và dmz.
5. Độ trễ đo trên 3 mẫu, gồm cả chu kỳ đọc file 0.5 giây của agent và độ trễ của thư mục mount từ Windows. Chưa đủ để viết mục 3.5 của Outline.
6. Ngôn ngữ báo cáo phóng đại: "hoàn hảo", "xuất sắc 100%". Đã thêm quy tắc số 7 vào CONTEXT.md.

Quyết định: chấp nhận Chốt 3. Yêu cầu Antigravity sửa PROGRESS.md (nêu phạm vi và cỡ mẫu, bỏ lời phóng đại, ghi giới hạn vào mục H) rồi người dùng tự commit và push.

## Phản hồi của giảng viên (email 2026-09-28)

Nội dung (tóm tắt): đồng ý Docker thay VMware và demo trên laptop cá nhân. Lưu ý tạo mạng riêng cho từng site (bridge hoặc macvlan) và chuẩn bị traffic giả lập (hping3 hoặc scapy) để Snort thực sự bắt được gì đó khi demo. Đồng ý đổi Filebeat sang Fluent Bit hoặc agent Python, khuyên thử Fluent Bit trước khi viết Python riêng cho đỡ mất công.

Nhận xét của người quản lý:
1. Hai rủi ro lớn nhất (Docker và Filebeat) đã được gỡ. Cần cập nhật Outline: thay chữ Filebeat trong các mục 2.2, 3.1.2, 3.2, 3.3, bảng công nghệ, bảng lịch tuần 7 và tài liệu tham khảo [5].
2. Agent Python đã xong và test xong trước khi giảng viên khuyên thử Fluent Bit. Không nên bỏ đi. Nên thử Fluent Bit có giới hạn thời gian và so sánh hai bên trên cùng bài test 30 alert. Kết quả so sánh dùng được cho Chương 2.5 và 3.5.
3. Mạng riêng cho từng site: hiện cả 3 site và attacker dùng chung minisoc-net. Cần đổi compose thành 3 mạng riêng cho 3 site, victim nằm trong mạng site của nó, sensor tự theo victim, attacker nối được vào cả 3 mạng, agent và soc-central nối vào một mạng trung tâm. Việc này làm sơ đồ C2 trong Outline trung thực hơn.
4. Traffic giả lập cho demo: cần một script chạy tuần tự các kịch bản tấn công trên 3 site để demo không phụ thuộc gõ lệnh tay.

## Việc cho người review tiếp theo

1. Xác nhận người dùng đã commit và push code Tuần 8 (không có logs/, .env). Kiểm tra bằng git status và mở repo trên GitHub.
2. Việc kỹ thuật tiếp theo: PostgreSQL. Thêm service postgres:15 vào compose, tạo 5 bảng (sensors, raw_alerts, incidents, notifications, admin_users) bằng file SQL khởi tạo, sửa central lưu vào raw_alerts thay cho bộ nhớ, đổi timestamp thành kiểu thời gian, thêm kiểm tra dữ liệu chặt hơn.
3. Điều kiện nghiệm thu bắt buộc cho giai đoạn PostgreSQL: rải tối thiểu 30 alert đều 3 site (tấn công lặp, cách nhau hơn 5 giây để mỗi lần sinh 1 alert), sau đó số dòng mới trong file alert phải bằng số dòng trong bảng raw_alerts của từng site. Thêm 1 lần kiểm tra restart agent trong lúc API đang tắt để ghi lại giới hạn vào Chương 4.2.
4. Sau đó: Alert Engine gộp trùng trong cửa sổ 10 giây, gán mức độ theo sid, rồi Dashboard React và Telegram.
5. Nhắc người dùng: sửa Filebeat trong Outline (giảng viên đã đồng ý), thêm giới hạn agent vào Chương 4.2, khảo sát 5+ người, vẽ hình ERD.
6. Đưa hai yêu cầu của giảng viên (mạng riêng từng site, script traffic giả lập) vào kế hoạch. Đề xuất làm mạng riêng ngay trước hoặc cùng lúc với PostgreSQL vì chỉ sửa compose.
7. Khi viết prompt PostgreSQL, yêu cầu endpoint POST /api/v1/telemetry nhận được cả 1 object lẫn 1 danh sách object, để sau này có thể thử Fluent Bit mà không phải sửa lại central.
