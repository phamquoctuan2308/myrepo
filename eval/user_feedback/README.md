# User feedback protocol

Đây là biểu mẫu thu thập phản hồi thật; file CSV mặc định chỉ có header để không biến dữ liệu mẫu
thành bằng chứng giả.

## Cách thu thập

1. Mời tối thiểu 5 người dùng thử các scenario chính: chat/tóm tắt, task, calendar/reminder,
   memory và quyền riêng tư.
2. Dùng mã ẩn danh cho `participant_id`; không ghi email, số điện thoại hoặc nội dung chat riêng tư.
3. Mỗi participant/scenario là một dòng trong `responses.csv`.
4. Rating phải từ 1 đến 5. Boolean dùng `true` hoặc `false`.
5. Chỉ sử dụng trích dẫn khi `consent_to_use_anonymized_quote=true`.

## Tổng hợp

```powershell
python scripts/summarize_user_feedback.py
```

Runner kiểm tra schema, tính completion rate, rating/helpfulness/trust trung bình và tỷ lệ sẵn sàng
dùng lại. Khi chưa đủ 5 participant, báo cáo có trạng thái `INSUFFICIENT_DATA` thay vì PASS giả.
