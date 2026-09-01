# Đánh giá và bằng chứng — Orbit

## Phạm vi

Evaluation chính chấm **Personal Agent**, là sản phẩm nền tảng theo đề bài gốc. Workspace Multi-Agent là phần phát triển mở rộng; kết quả Workspace chỉ được công bố riêng khi có dataset, revision và môi trường tương ứng.

## Tài liệu canonical

| Tài liệu | Nội dung |
|---|---|
| [Business Evaluation](BUSINESS_EVALUATION_REPORT.md) | Tự đánh giá giá trị và readiness business của Personal Agent |
| [Evaluation Evidence](EVALUATION_EVIDENCE.md) | Báo cáo kỹ thuật tổng hợp theo artifact hiện có |
| [Traceability Matrix](TRACEABILITY_MATRIX.md) | Yêu cầu → test → code → evidence |
| [Metrics](METRICS.md) | Định nghĩa metric, gate và protocol |
| [Manual Test Report](manual/MANUAL_TEST_REPORT.md) | Kiểm thử UI thủ công và ảnh bằng chứng |
| [Memory Manual Test](manual/MEMORY_TEST_REPORT.md) | Kịch bản kiểm thử memory |

## Cấu trúc

- `datasets/`: dữ liệu đánh giá có version, gồm dataset Workspace synthetic.
- `golden_dataset/`: golden cases của Personal Agent.
- `manual/`: báo cáo và ảnh kiểm thử thủ công.
- `results/`: JSON, Markdown, JUnit, Lighthouse và artifact máy tạo.
- `memory_harness/`, `user_feedback/`: protocol/harness chuyên biệt.

## Lệnh còn tồn tại trong repository

```powershell
python -m pytest tests -q
python -m ruff check src tests scripts
python scripts\eval_user_agent.py
python scripts\eval_extract_tasks.py
python scripts\validate_multi_agent_dataset.py
python scripts\workspace_agent_load_harness.py --help
```

Các runner gọi model thật cần API key và phải ghi model, prompt/schema version, commit, thời gian và môi trường. Không diễn giải artifact `latest` là hiện trạng production nếu deployment đã đổi revision.

## Quy tắc evidence

- `PASS`: đã chạy và đạt gate.
- `FAIL`: đã chạy nhưng không đạt.
- `PENDING`: thiếu dữ liệu hợp lệ; không quy đổi thành pass.
- `SKIP`: chủ động ngoài phạm vi; không quy đổi thành pass.
- Không đưa secret, raw chat hoặc dữ liệu cá nhân vào artifact.
- Feedback synthetic chỉ kiểm tra pipeline, không thay thế người dùng thật.

Workspace release evidence trong tương lai phải đặt dưới `eval/workspace/`; không trộn với điểm Personal Agent hiện tại.
