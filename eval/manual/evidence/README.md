# Evidence — Ảnh chụp màn hình kiểm thử thủ công

Thư mục này chứa ảnh chụp màn hình làm bằng chứng cho từng test case trong [`MANUAL_TEST_REPORT.md`](../MANUAL_TEST_REPORT.md).

## Cấu trúc thư mục

```
eval/manual/evidence/
├── TC-01/   # Đăng ký tài khoản mới
├── TC-02/   # Từ chối đăng nhập khi sai mật khẩu
├── TC-03/   # Chặn truy cập khi chưa đăng nhập
├── TC-04/   # Gửi và nhận tin nhắn theo thời gian thực
├── TC-05/   # Tạo hội thoại nhóm
├── TC-06/   # AI tóm tắt hội thoại
├── TC-07/   # Tạo và hoàn thành task
├── TC-08/   # Reminder được kích hoạt đúng thời điểm
├── TC-09/   # Kết nối và tạo sự kiện Google Calendar
└── TC-10/   # Admin khóa và mở khóa người dùng
```

## Quy ước đặt tên file

```
TC-XX-stepNN-mo-ta-ngan.png
```

Ví dụ: `TC-01-step04-dang-ky-thanh-cong.png`

- Không dấu, không khoảng trắng (dùng `-` để nối từ).
- `stepNN` tương ứng đúng số thứ tự bước trong bảng thao tác của test case đó.
- Nếu một bước cần nhiều ảnh, thêm hậu tố `-a`, `-b`, ví dụ `TC-04-step03-a.png`, `TC-04-step03-b.png`.
- Chụp toàn bộ cửa sổ trình duyệt (bao gồm thanh địa chỉ) để thấy rõ URL/trạng thái đăng nhập tại thời điểm chụp.

## Cách gắn ảnh vào tài liệu test case

1. Đặt ảnh vào đúng thư mục `TC-XX/` theo tên file gợi ý sẵn trong bảng **Bằng chứng hình ảnh** của test case tương ứng trong `MANUAL_TEST_REPORT.md`.
2. Không cần sửa gì thêm — placeholder Markdown `![...](evidence/TC-XX/...)` đã trỏ sẵn đúng đường dẫn, ảnh sẽ tự hiển thị khi mở file Markdown bằng trình xem hỗ trợ ảnh cục bộ (VD: VS Code preview, GitHub).
3. Nếu tên file thực tế khác với gợi ý, cập nhật lại đường dẫn trong placeholder cho khớp.
4. Case `FAIL`/`BLOCKED`: bổ sung thêm ảnh chụp đúng tại bước phát sinh lỗi (kèm mã lỗi nếu có), thêm dòng mới vào bảng nếu bước đó chưa có placeholder sẵn.
