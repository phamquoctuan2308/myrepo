# Manual Test Cases — Orbit AI Assistant

Tài liệu gồm 11 test case thủ công theo 5 nhóm chức năng chính của hệ thống. Các mốc thời gian hiển thị được kiểm tra theo múi giờ `Asia/Ho_Chi_Minh`.

## Chuẩn bị chung

- Backend chạy tại `http://localhost:8000`.
- User app chạy tại `http://localhost:5173`.
- Admin app chạy tại `http://localhost:5174`.
- PostgreSQL đã được cấu hình và backend kết nối thành công.
- Chuẩn bị hai tài khoản user khác nhau (`User A`, `User B`) và một tài khoản có role `admin`.
- Các case dùng AI cần cấu hình LLM provider hợp lệ và ngân sách token trong ngày chưa bị vượt.
- Các case dùng Google Calendar cần cấu hình OAuth và kết nối tài khoản Google Calendar cho user test.

---

## 1. Xác thực và phân quyền

### TC-AUTH-01 — Đăng ký và đăng nhập bằng email/mật khẩu

**Tiền điều kiện:** Email test chưa tồn tại trong hệ thống.

| Bước | Thao tác | Kết quả mong đợi |
| --- | --- | --- |
| 1 | Mở `/register`. | Form đăng ký hiển thị đầy đủ. |
| 2 | Nhập email hợp lệ, tên hiển thị và mật khẩu hợp lệ, sau đó gửi form. | Đăng ký thành công và người dùng được đưa vào ứng dụng. |
| 3 | Đăng xuất. | Phiên đăng nhập bị xoá và trình duyệt chuyển về `/login`. |
| 4 | Đăng nhập lại bằng email và mật khẩu vừa tạo. | Đăng nhập thành công và chuyển đến `/assistant`. |
| 5 | Tải lại trang. | Người dùng vẫn đăng nhập và thông tin tài khoản được hiển thị đúng. |

### TC-AUTH-02 — Chặn user thường truy cập chức năng admin

**Tiền điều kiện:** Đã đăng nhập bằng tài khoản có role `user`.

| Bước | Thao tác | Kết quả mong đợi |
| --- | --- | --- |
| 1 | Quan sát sidebar của user app. | Không xuất hiện mục quản trị dành riêng cho admin. |
| 2 | Nhập trực tiếp URL của một trang admin. | User không được xem dữ liệu admin và bị chuyển về trang hợp lệ hoặc nhận thông báo không có quyền. |
| 3 | Gửi request tới một API `/api/v1/admin/*` bằng access token của user. | Backend trả về `403 Forbidden`; không có dữ liệu quản trị bị lộ. |

---

## 2. Chat 1-1/nhóm và realtime

### TC-CHAT-01 — Gửi và nhận tin nhắn 1-1 theo thời gian thực

**Tiền điều kiện:** User A và User B đăng nhập trên hai trình duyệt hoặc hai cửa sổ độc lập; hai user có hội thoại 1-1.

| Bước | Thao tác | Kết quả mong đợi |
| --- | --- | --- |
| 1 | User A mở hội thoại với User B và gửi một tin nhắn duy nhất. | Tin nhắn xuất hiện ngay trong khung chat của User A, không bị gửi lặp. |
| 2 | Quan sát màn hình của User B mà không tải lại trang. | Tin nhắn mới tự xuất hiện qua WebSocket, đúng nội dung và đúng người gửi. |
| 3 | Khi User B chưa mở hội thoại, User A gửi thêm một tin khác. | Bộ đếm chưa đọc của User B tăng đúng số lượng. |
| 4 | User B mở hội thoại. | Tin nhắn được đánh dấu đã đọc và bộ đếm chưa đọc được cập nhật. |

### TC-CHAT-02 — Tạo hội thoại nhóm và chỉ gửi realtime cho thành viên

**Tiền điều kiện:** Có ít nhất ba tài khoản: User A, User B và User C.

| Bước | Thao tác | Kết quả mong đợi |
| --- | --- | --- |
| 1 | User A tạo nhóm và chỉ thêm User B. | Nhóm được tạo, danh sách thành viên chỉ gồm A và B. |
| 2 | User A gửi tin nhắn vào nhóm. | User B nhận tin realtime và thấy đúng tên nhóm/nội dung. |
| 3 | Kiểm tra màn hình và API bằng phiên của User C. | User C không thấy nhóm, không nhận WebSocket event của nhóm và không đọc được lịch sử nhóm. |

### TC-CHAT-03 — Đính kèm file, emoji và ô soạn tin tự giãn

**Tiền điều kiện:** User A và User B có hội thoại 1-1; cả hai đang mở hội thoại đó.

| Bước | Thao tác | Kết quả mong đợi |
| --- | --- | --- |
| 1 | User A bấm icon kẹp giấy ở ô soạn tin, chọn 1 ảnh (< 3 MB) và 1 file không phải ảnh. | Hai chip đính kèm hiện phía trên ô soạn tin; chip ảnh có thumbnail, mỗi chip có nút xoá. |
| 2 | User A thử chọn thêm để vượt quá 5 file, và chọn một file > 3 MB. | File > 3 MB bị bỏ qua; tổng số đính kèm không vượt quá 5. |
| 3 | User A bấm icon mặt cười và chọn một emoji. | Emoji được chèn vào cuối nội dung đang soạn. |
| 4 | User A gửi tin nhắn. | Ảnh hiển thị inline trong bong bóng của A; file khác hiển thị dạng link tải. Ô soạn tin trở về rỗng và cao 1 dòng. |
| 5 | Quan sát màn hình User B (không tải lại trang). | B nhận tin realtime với cùng ảnh inline và link tải, không phải chuỗi `[[orbit-attachment]]` thô. |
| 6 | User A dán/gõ một đoạn văn bản dài nhiều dòng vào ô soạn tin. | Ô soạn tin tự cao dần theo nội dung tới trần ~120px rồi mới xuất hiện thanh cuộn; nút gửi vẫn nhìn thấy. |
| 7 | (Tuỳ chọn) Thu nhỏ cửa sổ xuống cỡ điện thoại rồi lặp lại bước 1–6. | Bố cục `/chat` không vỡ: bong bóng không tràn mép phải, panel AI mở dạng tấm phủ toàn màn hình, ô soạn tin không bị bàn phím ảo che. |

---

## 3. AI và quản lý Task

### TC-AI-01 — Tóm tắt hội thoại theo phạm vi đã chọn

**Tiền điều kiện:** Hội thoại có nhiều tin nhắn; user đã cấp quyền AI cho hội thoại; LLM hoạt động.

| Bước | Thao tác | Kết quả mong đợi |
| --- | --- | --- |
| 1 | Mở hội thoại, mở AI Panel và chọn phạm vi 20 tin gần nhất. | Phạm vi 20 tin được ghi nhận trên giao diện. |
| 2 | Bấm **Summarize**. | Hiển thị trạng thái đang xử lý; người dùng không phải rời trang chat. |
| 3 | Chờ kết quả. | Chỉ có một bản tóm tắt, phản ánh nội dung trong phạm vi đã chọn và không lặp lại nhiều định dạng. |
| 4 | Kiểm tra hội thoại gốc. | Không có tin nhắn, task, reminder hoặc calendar event nào bị tạo ngoài ý muốn. |

### TC-AI-02 — Trích xuất task và Accept/Dismiss gợi ý

**Tiền điều kiện:** Hội thoại có nội dung như “Lan gửi báo giá trước 15:00 ngày mai”; user đã cấp quyền AI.

| Bước | Thao tác | Kết quả mong đợi |
| --- | --- | --- |
| 1 | Trong AI Panel, bấm **Extract tasks**. | AI nhận diện được công việc, deadline và trả kết quả thành công. |
| 2 | Mở `/tasks`. | Task mới nằm trong **AI suggestions**, có trạng thái `suggested`, chưa nằm trong danh sách task chính thức. |
| 3 | Bấm **Accept** trên gợi ý. | Task chuyển sang trạng thái chính thức và deadline hiển thị theo giờ Việt Nam. |
| 4 | Tạo lại một gợi ý khác và bấm **Dismiss**. | Gợi ý bị loại khỏi khu vực cần quyết định và không trở thành task chính thức. |

---

## 4. Calendar và Reminder

### TC-CAL-01 — Tạo sự kiện qua AI chỉ sau khi xác nhận

**Tiền điều kiện:** User đã kết nối Google Calendar và mở `/assistant`; LLM hoạt động.

| Bước | Thao tác | Kết quả mong đợi |
| --- | --- | --- |
| 1 | Gửi “Đặt lịch họp team lúc 15:00 ngày mai trong 1 giờ”. | AI dừng ở trạng thái chờ xác nhận và hiển thị thẻ có tiêu đề, ngày, giờ. |
| 2 | Kiểm tra Google Calendar trước khi xác nhận. | Chưa có sự kiện mới được tạo. |
| 3 | Bấm **Xác nhận**. | AI báo tạo thành công; sự kiện xuất hiện trong Orbit và đúng Google Calendar của user. |
| 4 | Lặp lại yêu cầu khác nhưng bấm **Huỷ**. | AI báo đã huỷ và không tạo thêm sự kiện nào. |

### TC-REM-01 — Reminder được đẩy realtime khi đến hạn

**Tiền điều kiện:** User đã đăng nhập; backend scheduler và WebSocket hoạt động.

| Bước | Thao tác | Kết quả mong đợi |
| --- | --- | --- |
| 1 | Mở `/reminders` và tạo reminder có thời điểm kích hoạt sau hiện tại 2–3 phút. | Reminder được lưu và hiển thị với trạng thái chờ. |
| 2 | Chuyển sang một trang khác trong user app, không tải lại trình duyệt. | Kết nối WebSocket chung của ứng dụng vẫn hoạt động. |
| 3 | Chờ đến thời điểm kích hoạt. | Toast reminder xuất hiện realtime, đúng tiêu đề/nội dung và chỉ hiển thị cho chủ sở hữu. |
| 4 | Mở lại `/reminders`. | Reminder có trạng thái đã kích hoạt phù hợp, không bị tạo bản ghi trùng. |

---

## 5. Admin và giám sát hệ thống

### TC-ADMIN-01 — Admin khoá và mở khoá tài khoản user

**Tiền điều kiện:** Admin đăng nhập tại app admin; User A đang hoạt động.

| Bước | Thao tác | Kết quả mong đợi |
| --- | --- | --- |
| 1 | Admin mở trang quản lý Users và khoá User A. | Trạng thái User A đổi sang bị khoá và thao tác được ghi nhận. |
| 2 | Đăng xuất User A rồi thử đăng nhập lại. | Hệ thống từ chối đăng nhập bằng tài khoản bị khoá với thông báo phù hợp. |
| 3 | Admin mở khoá User A. | Trạng thái tài khoản trở lại hoạt động. |
| 4 | User A đăng nhập lại. | Đăng nhập thành công và dữ liệu cũ vẫn còn nguyên. |

### TC-ADMIN-02 — Hiển thị cảnh báo và chặn AI khi hết ngân sách token

**Tiền điều kiện:** Có thể cấu hình ngân sách test thấp hoặc chuẩn bị usage gần ngưỡng; admin và user đang online.

| Bước | Thao tác | Kết quả mong đợi |
| --- | --- | --- |
| 1 | Thực hiện các yêu cầu AI cho đến khi usage đạt ít nhất 80% ngân sách ngày. | Admin nhận toast/banner cảnh báo realtime; dashboard hiển thị đúng tổng token, request và phần trăm ngân sách. |
| 2 | Tiếp tục đến khi usage đạt 100%. | Admin nhận cảnh báo mức 100%. |
| 3 | User gửi một yêu cầu AI mới. | Yêu cầu mới bị chặn với thông báo rõ ràng; hệ thống không gọi thêm LLM. |
| 4 | Nếu đang có hành động AI đã chờ xác nhận từ trước, bấm xác nhận. | Luồng `/chat/resume` vẫn hoàn tất, không bị treo vì giới hạn ngân sách. |

---

## Ghi nhận kết quả chạy test

Khi thực thi, tester ghi thêm cho từng test case: ngày test, môi trường/build, người test, trạng thái `Pass/Fail/Blocked`, bằng chứng (ảnh hoặc log) và mã lỗi nếu có.
