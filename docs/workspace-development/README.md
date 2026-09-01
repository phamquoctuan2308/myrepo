# Workspace Multi-Agent — phần phát triển mở rộng

## Vị trí trong dự án

Personal Agent là sản phẩm nền tảng đáp ứng đề bài gốc. Multi-Agent theo Workspace là phần phát triển mở rộng của Orbit nhằm hỗ trợ cộng tác theo phòng ban và tổng hợp liên phòng ban.

Phần Workspace đã có nhiều thành phần trong code và test, nhưng không đồng nghĩa đã phát hành:

- các feature flag Multi-Agent mặc định là `false`;
- Personal Agent vẫn là flow mặc định;
- chưa có một bộ live/staging acceptance riêng đủ để tuyên bố Workspace production-ready.

## Bộ tài liệu

| Tài liệu | Vai trò |
|---|---|
| [Product Brief](BRIEF.md) | Giá trị, persona và ranh giới phần mở rộng |
| [PRD](PRD.md) | Yêu cầu và acceptance cho một release Workspace tương lai |
| [Architecture](ARCHITECTURE.md) | Thiết kế kỹ thuật, security boundary và current/target state |
| [Enterprise Workspace Foundation](ENTERPRISE_WORKSPACE_FOUNDATION.md) | Company Root, role, membership và lifecycle |
| [Development Report](DEVELOPMENT_REPORT.md) | Báo cáo hiện trạng phát triển thống nhất |
| [Dataset](../../eval/datasets/MULTI_AGENT_DATASET.md) | Taxonomy và 150 case synthetic |

## Cách đọc trạng thái

- **Implemented:** có code trong repository.
- **Tested:** có test hoặc evidence được chỉ rõ.
- **Released:** đã bật, deploy và qua acceptance trên môi trường mục tiêu.

Workspace hiện ở trạng thái **developed extension, not default release**: đã triển khai đáng kể và có test, nhưng chưa đạt điều kiện `Released`.
