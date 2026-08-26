# Bộ tài liệu chuẩn — Orbit

Thư mục này giữ tài liệu sản phẩm/kỹ thuật đang được dùng. Team đọc theo thứ tự sau:

| Thứ tự | Tài liệu | Câu hỏi được trả lời |
|---|---|---|
| 1 | [Product Brief](BRIEF.md) | Sản phẩm là gì, giải quyết vấn đề nào và phạm vi MVP ra sao? |
| 2 | [PRD](PRD.md) | Nghiệp vụ, yêu cầu và acceptance criteria là gì? |
| 3 | [Architecture](ARCHITECTURE.md) | Component, data flow, authorization và trạng thái hiện tại được thiết kế thế nào? |
| 4 | [Deployment Guide](deploy.md) | Chạy và triển khai hệ thống thế nào? |

Trạng thái triển khai thật theo từng yêu cầu đề bài (khác với phạm vi/mục tiêu mô tả trong
BRIEF.md/PRD.md) nằm ở [ROADMAP.md](../ROADMAP.md) tại root repo — luôn đối chiếu ROADMAP.md khi
cần biết một tính năng đã chạy thật hay còn là kế hoạch.

## Quy tắc single source of truth

- `BRIEF.md` khóa ý tưởng và ranh giới sản phẩm.
- `PRD.md` khóa hành vi và acceptance.
- `ARCHITECTURE.md` khóa giải pháp kỹ thuật và security boundary hiện tại.
- `ROADMAP.md` (root) là nguồn sự thật cho "đã chạy thật" vs "chưa xong" theo từng yêu cầu đề bài.
- Mọi tài liệu phải phân biệt rõ **đã có trong code** và **mục tiêu cần triển khai**.
- Khi đổi kiến trúc hoặc data boundary, PR phải cập nhật tài liệu canonical tương ứng cùng lúc.

## Lịch sử

Subsystem "Multi-Agent theo Workspace" (Company Root, Agent Workspace phòng ban, Product
Delivery/Quality Assurance/Executive Agent, WorkspaceBrief) từng được xây trên nhánh này nhưng luôn
tắt bằng feature flag và chưa từng có UI thật cho người dùng — đã được gỡ bỏ hoàn toàn khỏi code,
migration, test và tài liệu (2026-08-25). Tài liệu mô tả subsystem đó (kế hoạch triển khai, dataset
test, thiết kế Enterprise Workspace Foundation) vẫn có thể khôi phục từ lịch sử Git nếu cần tra cứu,
nhưng không còn phản ánh code hiện tại.
