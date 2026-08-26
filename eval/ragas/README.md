# RAGAS evaluation

Bộ này đánh giá luồng tóm tắt dựa trên context thật của Orbit bằng bốn metric:

| Metric | Gate |
|---|---:|
| Faithfulness | >= 0.70 |
| Answer relevancy | >= 0.70 |
| Context precision | >= 0.60 |
| Context recall | >= 0.60 |

Dataset trong `conversation_summary_cases.jsonl` chỉ chứa hội thoại tổng hợp, không có dữ liệu cá
nhân hoặc dữ liệu production. Khi chạy, prompt tóm tắt thật của Orbit sinh câu trả lời qua
OpenRouter `openai/gpt-5.6-luna`; RAGAS dùng cùng gateway và model để chấm. Kết quả được ghi vào
`eval/results/ragas-latest.json` và `eval/results/ragas-latest.md`.

## Cài đặt và chạy

```powershell
pip install -e ".[eval]"
python scripts/eval_ragas.py
```

Cấu hình được tự động nạp từ `.env`; cũng có thể truyền biến môi trường trực tiếp. LangSmith tracing
mặc định bị tắt cho runner độc lập này; chỉ bật khi chủ động đặt `RAGAS_ENABLE_LANGSMITH=true`.

Có thể đặt `RAGAS_APPLICATION_MODEL`, `RAGAS_EVALUATOR_MODEL` và `RAGAS_EMBEDDING_MODEL` để khóa
model. Mặc định lần lượt là `openai/gpt-5.6-luna`, `openai/gpt-5.6-luna` và
`openai/text-embedding-3-small`. Bộ này gọi model thật, tốn quota và không nằm trong test/CI mặc định.

Nếu dataset đã chứa trường `response` lấy từ một lần chạy Orbit trước đó, dùng `--use-stored-responses`
để chỉ chấm lại mà không gọi application LLM.
