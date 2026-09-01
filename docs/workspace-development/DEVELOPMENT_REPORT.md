# Báo cáo phát triển Workspace Multi-Agent

> **Phạm vi:** phần phát triển mở rộng của Orbit, không thay thế phạm vi Personal Agent trong đề bài gốc.
>
> **Đối chiếu code:** `main` tại commit `1a23f82` trước khi tái cấu trúc tài liệu.
>
> **Trạng thái:** đã triển khai đáng kể trong code và test; chưa phát hành mặc định.

## 1. Kết luận điều hành

Workspace Multi-Agent không còn chỉ là ý tưởng hoặc bản thiết kế. Repository đã có control plane Workspace, route và runtime cho agent chuyên môn, UI Workspace, orchestration Delivery/Quality, policy/guardrail và các test liên quan.

Tuy vậy, phần này chưa được coi là release mặc định vì bốn feature flag vẫn tắt theo cấu hình mẫu, chưa có bộ acceptance live/staging riêng chứng minh toàn bộ luồng trên môi trường mục tiêu, và Personal Agent vẫn là trải nghiệm mặc định của sản phẩm bàn giao.

## 2. Phần đã có trong code

### Workspace control plane

- Company/organization Workspace và Agent Workspace.
- Membership, lead/member lifecycle và resource binding.
- Admin Workspace page và user discovery theo membership.
- Các route `workspace`, `agent_workspace`, relationship và action control plane.

### Agent runtime

- Workspace gateway/router, policy và runtime adapters.
- Product Delivery profiles, executor/runner, supervisor và specialist graph.
- Quality Assurance profiles, graph, tools, quality control và handoff.
- Delivery/Quality tools cho messages, people, task/work item, analysis và brief.
- Workspace agent memory, metrics, progress và outbox services.

### User interface

- `/workspaces` cho danh sách Workspace được cấp.
- `/workspace-agent` chọn agent theo profile được server trả về.
- Workspace channels và các trang Delivery/Quality chuyên biệt.
- Admin page quản lý Workspace.

## 3. Bằng chứng kiểm thử trong repository

Các nhóm test hiện có bao gồm:

- `tests/test_agent_workspaces.py`, `tests/test_workspaces.py`, `tests/test_workspace_migration.py`;
- `tests/test_agents/test_workspace_delivery_graph.py` và `test_workspace_quality_graph.py`;
- các test Delivery API, scope, tools, checkpoints, task review và multi-agent;
- các test Quality tools/workspace integration;
- test runtime isolation, LLM policy, prompt budget và Workspace memory;
- dataset `eval/datasets/multi_agent_workspace_v1.jsonl` gồm 150 case synthetic.

`WORKLOG.md` ghi nhận lần tích hợp QA/UI ngày 2026-08-23 đã chạy 68 test agent/multi-agent liên quan, Ruff và frontend build thành công. Đây là bằng chứng lịch sử tại thời điểm đó; việc tái cấu trúc tài liệu này không chạy lại toàn bộ suite và không nâng kết quả đó thành chứng nhận release mới.

## 4. Chưa được tuyên bố hoàn thành ở mức release

- `MULTI_AGENT_ENABLED`, `PRODUCT_DELIVERY_AGENT_ENABLED`, `QUALITY_ASSURANCE_AGENT_ENABLED` và `EXECUTIVE_AGENT_ENABLED` mặc định là `false`.
- Chưa có báo cáo live/staging acceptance riêng cho toàn bộ Workspace flow trên cùng một revision triển khai.
- Chưa có bằng chứng production cho rollout, observability, rollback và vận hành dài hạn của Workspace Agent.
- Dataset synthetic chứng minh contract/policy coverage, không thay thế pilot người dùng thật.

## 5. Trạng thái theo lớp

| Lớp | Implemented | Tested | Released |
|---|---:|---:|---:|
| Workspace control plane | Có | Có test repository | Chưa xác nhận release mặc định |
| Delivery Agent | Có | Có test chuyên biệt | Feature flag mặc định tắt |
| Quality Agent | Có | Có test chuyên biệt | Feature flag mặc định tắt |
| Executive/aggregate foundation | Có thành phần runtime và contract | Có test liên quan | Chưa có live acceptance riêng |
| Workspace UI | Có route và page | Có build/test lịch sử | Chưa xác nhận staging đầy đủ |
| Security boundary/HITL | Có policy, guard và action control plane | Có security/unit test | Chưa diễn tập release đầy đủ |

## 6. Quan hệ với bản bàn giao Personal Agent

Kết quả Workspace không được dùng để thay thế các gate của Personal Agent trong `docs/EVALUATION_EVIDENCE.md`. Ngược lại, việc Workspace chưa phát hành không làm mất các tính năng Personal Agent đã bàn giao.

Khi chuẩn bị một release Workspace riêng, cần tạo bộ evidence tại `eval/workspace/`, pin commit/model/schema/policy version và chạy lại API, UI, authorization, HITL, latency, accessibility và rollback trên cùng môi trường mục tiêu.
