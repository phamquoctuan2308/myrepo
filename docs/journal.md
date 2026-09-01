# Nhật ký cải tiến dự án Orbit

> Tóm tắt ngắn theo lịch sử commit của repository, từ 27/07/2026 đến 01/09/2026. Ngày không có commit được ghi rõ để nhật ký không suy đoán tiến độ.

## Tháng 07/2026

- **27/07/2026:** Cải thiện bộ ghi log Antigravity để đọc thêm nguồn `overview.txt`.
- **28/07/2026:** Không ghi nhận thay đổi mã nguồn trên nhánh chính.
- **29/07/2026:** Không ghi nhận thay đổi mã nguồn trên nhánh chính.
- **30/07/2026:** Bổ sung kiểm thử thử nghiệm và bản frontend demo ban đầu.
- **31/07/2026:** Hoàn thiện nền tảng chat realtime.

## Tháng 08/2026

- **01/08/2026:** Chỉnh lại README và cấu trúc hướng dẫn dự án.
- **02/08/2026:** Thêm phân quyền Admin, cải thiện prompt tóm tắt, luồng tìm kiếm/khôi phục tài khoản và tài liệu tổng quan hệ thống.
- **03/08/2026:** Chuyển LLM sang Gemini, sửa tool-call, kết nối Task/Calendar/Reminder thật và xây nền tảng workspace authorization/migration.
- **04/08/2026:** Mở rộng PostgreSQL, hoàn thiện Task/Calendar/Reminder/Memory/Profile, proactive agent và đồng bộ Calendar hai chiều.
- **05/08/2026:** Ổn định context/search của agent, HITL, Task Inbox, cảnh báo ngân sách, timezone và nền tảng metric.
- **06/08/2026:** Bổ sung bộ metric, đăng nhập Google, Calendar theo từng người dùng với token mã hóa và hardening Workspace.
- **07/08/2026:** Bổ sung kiểm thử nhiều tài khoản và blueprint triển khai Docker trên Render.
- **08/08/2026:** Sửa lỗi PKCE trong Google OAuth và viết hướng dẫn kiểm thử Calendar cho nhóm.
- **09/08/2026:** Không ghi nhận thay đổi mã nguồn trên nhánh chính.
- **10/08/2026:** Hoàn thiện scope filter phía backend, timestamp context, Calendar OAuth theo người dùng và tool `search_messages` có xử lý mơ hồ.
- **11/08/2026:** Thiết lập Render/Supabase/Vercel, sửa ngày tương đối và nâng proactive notification với xác minh danh tính.
- **12/08/2026:** Thêm rate limit, eval harness, quản trị AI/audit, tách luồng Admin và sửa lỗi Calendar, proactive cùng hợp đồng frontend–backend.
- **13/08/2026:** Tách ứng dụng User/Admin, siết consent, bổ sung thông báo nền, trang quản trị AI và giới hạn Calendar theo người dùng.
- **14/08/2026:** Tách Admin thành Vite app riêng, bắt buộc PostgreSQL cho agent runtime và thêm acceptance test cô lập.
- **15/08/2026:** Thêm kiểm tra xung đột lịch, dữ liệu Assistant thật, toast/confirm, jump-to-unread, Markdown AI và bộ tài liệu/test agent.
- **16/08/2026:** Chuẩn hóa manual test, sửa điều hướng Calendar và logging nền; hoàn tất 10/10 test case với bằng chứng UI.
- **17/08/2026:** Tăng bảo vệ Calendar/logging/consent, bổ sung CI migration và hai frontend build, đồng thời tạo golden conversation dataset.
- **18/08/2026:** Xây nền tảng Workspace Multi-Agent.
- **19/08/2026:** Hoàn thiện các pha routing, policy, Delivery/Quality/Executive Agent, shared HITL, governance, dataset và UI Workspace.
- **20/08/2026:** Bổ sung QA tools, cross-workspace dependency, security/eval harness, kill switch, consent revoke và HITL cho specialist agents.
- **21/08/2026:** Tích hợp Product Delivery, Executive Agent và tăng guardrail/evaluation cho memory.
- **22/08/2026:** Thêm migration cho memory guardrail/episode và sửa các regression phát hiện bởi pytest.
- **23/08/2026:** Khôi phục UI overhaul, sửa regression/độ tương phản/lọc Workspace, đồng bộ dark theme Admin và mở rộng consent cho chat 1-1.
- **24/08/2026:** Thêm rolling summary, QA Agent trong chat, Workspace Briefs, pitch deck, đồng bộ Task–Calendar và episodic memory/guardrail.
- **25/08/2026:** Thu gọn phạm vi phát hành, harden deployment/realtime/Admin, khôi phục CI và bổ sung bộ bằng chứng chất lượng tái lập.
- **26/08/2026:** Hoàn thiện usage widget, cấu hình production, hiệu năng Calendar, guardrail tiếng Việt, Reminder khi nhận task và tối ưu connection pool.
- **27/08/2026:** Ổn định deploy Vercel/PostgreSQL, yêu cầu xác nhận thời gian còn thiếu, hiển thị nguồn task, scope Workspace, readiness và Admin SSO/budget.
- **28/08/2026:** Cải thiện trải nghiệm mobile cho Chat/Assistant, keyboard composer, AI panel, file attachment, emoji, profile và trạng thái usage.
- **29/08/2026:** Hợp nhất codebase, giữ bộ Deliverables/eval và bổ sung tài liệu SOLUTION cùng cập nhật Chat/Assistant.
- **30/08/2026:** Không ghi nhận thay đổi mã nguồn trên nhánh chính.
- **31/08/2026:** Phát hành báo cáo đánh giá kỹ thuật và đánh giá giá trị nghiệp vụ.

## Tháng 09/2026

- **01/09/2026:** Chốt bản release, đồng bộ evidence, sắp xếp tài liệu bàn giao và bổ sung metric, pitch deck, video demo cùng các báo cáo evaluation trong `docs/`.
