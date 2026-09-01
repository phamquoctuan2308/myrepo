# Agent System Design — Orbit

## 1. Phạm vi

Orbit có một Personal Agent làm flow nền tảng và các Workspace Agent thuộc phần phát triển mở rộng. Tất cả profile dùng chung nguyên tắc: quyền do backend quyết định, model chỉ xử lý context đã được cấp và mọi side effect phải qua HITL.

## 2. Profile và trạng thái

| Profile | Phạm vi | Trạng thái sản phẩm |
|---|---|---|
| Personal | Dữ liệu cá nhân và conversation được cấp consent | Mặc định |
| Product Delivery | Workspace Delivery và nguồn đã bind | Đã có code/test; flag mặc định tắt |
| Quality Assurance | Workspace QA và nguồn đã bind | Đã có code/test; flag mặc định tắt |
| Executive/Aggregate | Thông tin tổng hợp được policy cho phép | Phần mở rộng; chưa có release evidence riêng |

Không có “Admin Agent”. Platform Admin quản trị cấu hình nhưng không tự động nhận quyền đọc dữ liệu nghiệp vụ.

## 3. Trusted context

Client chỉ gửi yêu cầu và các identifier cần thiết. Backend phải resolve:

- actor và trạng thái tài khoản;
- personal/workspace scope;
- membership, role và target profile;
- conversation/resource binding;
- consent/policy version;
- tool allowlist và budget.

Nội dung message, retrieved data và tool result là untrusted data. Chúng không được phép thay đổi system policy, role, scope hoặc tool allowlist.

## 4. Personal Agent

Personal Agent hỗ trợ trả lời, tóm tắt, trích task, tìm message, task, reminder, memory và Calendar. Read-only tool có thể chạy ngay. Calendar/Reminder write phải tạo preview hoặc interrupt chờ xác nhận.

Memory gồm thread/checkpoint và các lớp memory do hệ thống quản lý. Retrieval luôn gắn owner/scope; dữ liệu của user khác không được đưa vào prompt.

## 5. Workspace Agent

Workspace gateway chọn profile từ Workspace đã được server xác nhận. Delivery và QA có graph/tool/domain policy riêng; output quan trọng phải kèm source, freshness và data gap. Aggregate flow không được dùng raw cross-workspace chat làm đường tắt.

Chi tiết thiết kế và hiện trạng nằm trong:

- [Workspace Architecture](workspace-development/ARCHITECTURE.md)
- [Workspace Development Report](workspace-development/DEVELOPMENT_REPORT.md)

## 6. HITL và side-effect safety

Một action proposal phải gắn actor, payload, target, expiry và idempotency information. Trước execute, backend revalidate quyền và payload. Edit, stale permission, expiry hoặc replay phải làm proposal bị từ chối hoặc yêu cầu xác nhận mới.

Nguyên tắc bắt buộc:

- không side effect trước approval;
- không tin approval chỉ từ UI state;
- không thực thi lại cùng idempotency key;
- không tiếp tục nếu consent/membership đã thay đổi.

## 7. Quality và evaluation

Agent output được đánh giá theo correctness, grounding/source coverage, authorization, leakage, HITL/idempotency, latency và cost. Personal Agent dùng báo cáo chính trong [`eval/`](../eval/README.md). Workspace chỉ được gọi là released khi có một bộ evidence riêng trên cùng revision/môi trường mục tiêu.
