# Worklog — Commit History

| Thuộc tính | Giá trị |
|---|---|
| Hạng mục | 9 |
| Tên | Worklog (commit history) |
| Trạng thái | Phần lớn hoàn thành |
| Mức độ | Dễ |
| Nguồn | Git log tự động |

## Phạm vi

- Nhánh theo dõi: `main`.
- Khoảng lịch sử: từ commit đầu tiên ngày 24/07/2026 đến 01/09/2026.
- Snapshot nguồn: `49ec0a1`, gồm 346 commit trước khi tạo file này.
- Nhật ký mô tả theo từng ngày: [journal.md](journal.md).

## Các mốc chính

| Giai đoạn | Cải tiến nổi bật | Commit minh chứng |
|---|---|---|
| 24–31/07 | Khởi tạo dự án, frontend demo và chat realtime | `05aa048`, `ab15d9c`, `7fa0432` |
| 01–08/08 | Personal Agent, Task/Reminder/Calendar/Memory, metric, Google OAuth và PostgreSQL | `0b6cb67`, `19cb507`, `943c4a0`, `5ca1f7c` |
| 10–14/08 | Scope phía backend, deploy cloud, rate limit, consent, Admin app và acceptance test | `956a9b5`, `1359c27`, `3f8ff59`, `68ffd5c` |
| 15–17/08 | Conflict check, UX/HITL, manual test, evidence UI, CI và golden dataset | `60d0434`, `48baa76`, `fcd91da`, `efb783d` |
| 18–24/08 | Workspace Multi-Agent, specialist agents, security/eval harness, memory guardrail và pitch deck | `60a7f90`, `884ab2b`, `b883955`, `c225913` |
| 25–29/08 | Hardening production, evaluation tái lập, tối ưu Calendar/DB và hoàn thiện mobile | `8871730`, `78bdd41`, `76d3c9f`, `c38c0bb` |
| 31/08–01/09 | Báo cáo evaluation, release cuối và chuẩn hóa bộ tài liệu bàn giao | `179b760`, `0488f24`, `6272917`, `49ec0a1` |

## Số commit theo ngày

<!-- Tự động tổng hợp từ git log tại snapshot 49ec0a1. -->

| Ngày | Số commit | Ngày | Số commit |
|---|---:|---|---:|
| 24/07/2026 | 1 | 25/07/2026 | 9 |
| 26/07/2026 | 1 | 27/07/2026 | 1 |
| 30/07/2026 | 3 | 31/07/2026 | 1 |
| 01/08/2026 | 2 | 02/08/2026 | 7 |
| 03/08/2026 | 14 | 04/08/2026 | 7 |
| 05/08/2026 | 18 | 06/08/2026 | 13 |
| 07/08/2026 | 3 | 08/08/2026 | 3 |
| 10/08/2026 | 5 | 11/08/2026 | 4 |
| 12/08/2026 | 16 | 13/08/2026 | 10 |
| 14/08/2026 | 3 | 15/08/2026 | 26 |
| 16/08/2026 | 16 | 17/08/2026 | 7 |
| 18/08/2026 | 1 | 19/08/2026 | 22 |
| 20/08/2026 | 7 | 21/08/2026 | 2 |
| 22/08/2026 | 3 | 23/08/2026 | 9 |
| 24/08/2026 | 16 | 25/08/2026 | 11 |
| 26/08/2026 | 29 | 27/08/2026 | 32 |
| 28/08/2026 | 27 | 29/08/2026 | 4 |
| 31/08/2026 | 1 | 01/09/2026 | 12 |

Ngày không xuất hiện trong bảng là ngày không có commit trên `main`.

## Cách tạo lại Git log

```bash
git log main --date=short --pretty=format:"%ad | %h | %s"
```

Để kiểm tra riêng một ngày:

```bash
git log main --since="2026-08-27 00:00" --until="2026-08-28 00:00" --oneline
```
