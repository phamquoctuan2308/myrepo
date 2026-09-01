# Evaluation suite

Orbit tách đánh giá deterministic khỏi những bộ gọi model thật để test thường nhanh và không tốn
quota.

| Suite | API key | Command | Output |
|---|---|---|---|
| Unit/integration + coverage | Không | `python scripts/run_coverage.py` | coverage JSON/XML/HTML + JUnit |
| Agent quality harness | Không | `pytest tests/test_agent_quality_harness.py -v` | pytest/JUnit |
| Formal user-agent acceptance | Có | `python scripts/eval_user_agent.py` | acceptance JSON/Markdown |
| Task extraction | Có | `python scripts/eval_extract_tasks.py` | task metrics JSON |
| API latency | Không với `/health`; bearer token với `/chat` | `python scripts/benchmark_api_latency.py` | latency JSON/Markdown |
| User feedback | Không | `python scripts/summarize_user_feedback.py` | aggregate JSON/Markdown |
| Consolidated evidence | Không | `python scripts/generate_evaluation_evidence.py` | `EVALUATION_EVIDENCE.md` |

## Thứ tự tạo evidence trước release

1. Chạy coverage và lưu toàn bộ artifact trong `eval/results/`.
2. Chạy benchmark `/health`, `/ready` và `/api/v1/chat` trên môi trường cần đánh giá.
3. Chạy task extraction và formal acceptance với model/version được khóa.
4. Thu thập feedback thật, tối thiểu 5 participant ẩn danh.
5. Chạy generator tổng hợp và kiểm tra mọi mục P0 không còn `PENDING`/`FAIL`.

Các file chứa key, raw chat hoặc dữ liệu cá nhân không được đưa vào dataset/evidence.
