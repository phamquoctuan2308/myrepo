# Tài liệu dự án Orbit

Tài liệu được chia theo đúng phạm vi bàn giao:

- **Personal Agent** là sản phẩm nền tảng đáp ứng đề bài gốc và là phạm vi đánh giá chính.
- **Multi-Agent theo Workspace** là phần phát triển mở rộng. Repo đã có nhiều thành phần code, UI và test, nhưng các feature flag mặc định vẫn tắt và phần này chưa được tuyên bố là trải nghiệm phát hành mặc định.

## Sản phẩm nền tảng

| Tài liệu | Nội dung |
|---|---|
| [Đề bài gốc](PROJECT_REQUIREMENTS.md) | Bài toán, ràng buộc và yêu cầu đầu ra |
| [Giải pháp](SOLUTION.md) | Cách tiếp cận, quyết định phạm vi và kết quả |
| [Kiến trúc](ARCHITECTURE.md) | Kiến trúc hiện hành, boundary dữ liệu và runtime |
| [Agent System Design](AGENT_SYSTEM_DESIGN.md) | Prompt, tool, memory, guardrail và HITL |
| [Architecture Diagram](architecture_diagram.md) | Sơ đồ rút gọn phục vụ trình bày |
| [Deployment](DEPLOYMENT.md) | Cách chạy và triển khai |
| [Nhật ký cải tiến](journal.md) | Tóm tắt thay đổi hằng ngày từ 27/07/2026 đến 01/09/2026 |

## Phần phát triển Workspace

Đọc từ [Workspace Development](workspace-development/README.md). Bộ này mô tả thiết kế, phần đã triển khai và điều kiện còn thiếu trước khi có thể bật làm trải nghiệm mặc định.

## Đánh giá và bằng chứng

Các báo cáo dành cho người đọc nằm tại [Evaluation Evidence](EVALUATION_EVIDENCE.md) và [Business Evaluation](BUSINESS_EVALUATION_REPORT.md). Dataset, test thủ công và kết quả máy vẫn nằm trong [`eval/`](../eval/README.md).

## Quy tắc nguồn chính thức

- Mỗi nội dung chỉ có một file canonical; file khác chỉ liên kết tới nó.
- Tài liệu phải phân biệt **có trong code**, **đã kiểm thử** và **đã phát hành**.
- Không diễn giải Workspace là sản phẩm mặc định chỉ vì code hoặc route đã tồn tại.
- Báo cáo đánh giá Personal Agent không dùng kết quả Workspace để nâng điểm nếu chưa có eval riêng.
- Kế hoạch và snapshot lịch sử được lưu trong Git history, không dùng làm tài liệu hiện trạng.
