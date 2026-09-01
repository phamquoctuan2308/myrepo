# Orbit — Pitch Deck

## Slide 1 — Orbit AI Assistant

Trợ lý AI cá nhân trong ứng dụng chat: tóm tắt hội thoại, phát hiện công việc, nhắc việc và quản lý lịch có xác nhận.

## Slide 2 — Vấn đề

Task, deadline và lời hứa bị chôn trong lượng lớn tin nhắn. Người dùng phải tự tổng hợp, dễ quên việc và mất thời gian chuyển dữ liệu sang task/calendar.

## Slide 3 — Giải pháp

Orbit đọc đúng hội thoại được cấp quyền, tóm tắt theo yêu cầu, trích task, chủ động phát hiện cam kết và tạo Calendar/Reminder sau bước human-in-the-loop.

## Slide 4 — Trải nghiệm chính

Chat realtime → AI summary/task extraction → Accept/Dismiss → Calendar/Reminder → Task Inbox → Memory cá nhân.

Video: [`Deliverables/orbit_demo_3min.mp4`](../Deliverables/orbit_demo_3min.mp4).

## Slide 5 — Kiến trúc

React/Vite User + Admin SPA, FastAPI modular monolith, LangGraph, PostgreSQL, WebSocket, APScheduler, Google Calendar và model gateway nhiều provider.

Chi tiết: [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

## Slide 6 — Safety và privacy

- Backend dựng context theo participant/consent.
- Platform Admin không mặc định đọc chat.
- Side effect phải xác nhận và revalidate.
- Secret ở environment; Calendar credential được mã hóa.

## Slide 7 — Bằng chứng

Repo có automated tests, manual UI evidence, task/agent evaluation, latency/load, Lighthouse và traceability matrix. Báo cáo giữ nguyên `FAIL/PENDING`, không đổi thiếu dữ liệu thành pass.

## Slide 8 — Phần phát triển Workspace

Personal Agent là nền tảng bàn giao. Workspace Multi-Agent là phần phát triển mở rộng với Delivery/QA/aggregate foundation, control plane, UI và test; feature flag còn tắt mặc định và chưa có release evidence riêng.

## Slide 9 — Giá trị và giới hạn

Giá trị: giảm bỏ sót cam kết và thao tác chuyển đổi từ chat sang hành động. Giới hạn: chưa có feedback người dùng thật đủ lớn, một số gate staging chưa đạt và hệ thống chưa sẵn sàng scale ngang.

## Slide 10 — Bước tiếp theo

Pilot có kiểm soát, hoàn thành release P0, thu thập feedback/ROI thật và chạy Workspace acceptance riêng trước khi bật phần mở rộng.
