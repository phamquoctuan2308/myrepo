# Weekly Journal — Team DRIVER ENGINEER

> Tóm tắt theo `WORKLOG.md`; chỉ ghi các mốc đã có bằng chứng trong repository.

## Tuần 1 — Nền tảng ứng dụng

### Đã hoàn thành

- Xây dựng đăng ký/đăng nhập, JWT và phân quyền user/admin.
- Xây dựng chat 1-1/nhóm, lưu lịch sử và WebSocket realtime.
- Thiết lập test backend ban đầu và hai frontend User/Admin.

### Bài học

- Authorization phải kiểm tra ở backend, không dựa vào route guard của frontend.
- Realtime cần broadcast đúng participant và có dữ liệu bền vững trong PostgreSQL.

## Tuần 2 — Personal Agent và tích hợp

### Đã hoàn thành

- Tích hợp LangGraph, task, reminder, memory và Google Calendar per-user.
- Thêm consent cho AI, proactive detection, usage budget và multi-provider LLM.
- Chuẩn hóa PostgreSQL, migration và timezone Asia/Ho_Chi_Minh.

### Bài học

- Calendar/Reminder write phải có human-in-the-loop.
- Consent phải được áp dụng trước khi context tới model và kiểm tra lại khi resume.

## Tuần 3 — An toàn và bằng chứng

### Đã hoàn thành

- Hardening consent, provenance, stale approval và idempotency.
- Thực hiện manual test các luồng auth, chat, AI, task, reminder, Calendar và admin.
- Xây dựng metric, traceability và các evaluation harness.

### Bài học

- `PENDING` và `FAIL` phải được giữ nguyên trong báo cáo nếu chưa có evidence hợp lệ.
- Dữ liệu synthetic hữu ích cho regression nhưng không thay thế feedback người dùng thật.

## Tuần 4 — Phát triển Workspace Multi-Agent

### Đã hoàn thành

- Xây Company/Agent Workspace, membership, router, scope và resource guard.
- Phát triển Delivery, Quality và aggregate foundation cùng UI Workspace.
- Thêm dataset/test chuyên biệt cho routing, cross-workspace denial, brief và HITL.

### Bài học

- Cần tách rõ `Implemented`, `Tested` và `Released`.
- Workspace là phần phát triển mở rộng; không được làm mờ phạm vi Personal Agent của đề bài gốc.

## Tuần 5 — Tích hợp, đánh giá và bàn giao

### Đã hoàn thành

- Mở rộng control plane, delivery/quality workflows và operational evidence.
- Chạy các đợt đánh giá staging/local và ghi rõ các gate chưa đạt.
- Chuẩn hóa tài liệu thành sản phẩm nền tảng, phần phát triển Workspace, evaluation và deliverables.

### Kết luận

Personal Agent là sản phẩm nền tảng bàn giao. Workspace Multi-Agent đã được phát triển đáng kể nhưng feature flag còn tắt mặc định và cần acceptance riêng trước khi phát hành.
