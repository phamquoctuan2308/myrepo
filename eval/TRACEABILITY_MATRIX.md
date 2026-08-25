# Requirement Traceability Matrix

Ma trận này nối yêu cầu quan trọng với test tự động, code thực thi và bằng chứng thủ công. Trạng thái
`Covered` nghĩa là đã có test; không tự động có nghĩa toàn bộ release gate đã PASS.

| ID | Requirement | Automated test | Implementation | Evidence | Status |
|---|---|---|---|---|---|
| AUTH-01 | Đăng ký, đăng nhập và duy trì phiên | `tests/test_auth.py` | `src/api/auth_routes.py` | `MANUAL_TEST_CASES.md` TC-AUTH-01 | Covered |
| AUTH-02 | User thường không truy cập admin | `tests/test_admin.py`, `tests/test_authorization.py` | `src/api/admin_routes.py`, `src/api/platform_routes.py` | TC-AUTH-02 | Covered |
| CHAT-01 | Tin nhắn 1-1 và unread chính xác | `tests/test_chat.py` | `src/api/chat_routes.py`, `src/services/chat_service.py` | TC-CHAT-01 | Covered |
| CHAT-02 | WebSocket chỉ broadcast đúng participant | `tests/test_websocket.py` | `src/websocket/routes.py`, `src/websocket/manager.py` | TC-CHAT-01/02 | Covered |
| PRIV-01 | Context AI loại message chưa consent | `tests/test_ai_permissions.py`, `tests/test_group_ai_event_extraction.py` | `src/services/consent_service.py` | AI context scope UI | Covered |
| AGENT-01 | Agent chọn đúng tool/route | `tests/test_agents/test_graph.py`, `tests/test_agents/test_planner_node.py` | `src/agents/graph.py`, `src/agents/nodes/planner_node.py` | Acceptance dataset ROUTE cases | Covered; formal gate failing |
| AGENT-02 | Tóm tắt có grounding, không bịa | `tests/test_agents/test_tools/test_summarize_tool.py` | `src/agents/tools/summarize_tool.py` | RAGAS + acceptance SUM cases | Covered; RAGAS pending |
| TASK-01 | Trích xuất task/deadline chính xác | `tests/test_agents/test_tools/test_task_tool.py`, `tests/test_agent_eval_runner.py` | `src/agents/tools/task_tool.py` | `task-extraction-latest.json` | Covered |
| HITL-01 | Side effect chỉ chạy sau xác nhận | `tests/test_agents/test_graph.py`, calendar/reminder tool tests | `src/agents/graph.py`, `src/agents/tools/` | TC-CAL-01 | Covered |
| HITL-02 | Retry/double-click không tạo side effect trùng | `tests/test_golden_dataset.py`, `tests/test_agent_dataset.py` | Agent proposal/resume flow | Golden HITL cases | Dataset covered; formal rerun required |
| MEMORY-01 | Memory đúng owner, không cross-user | `tests/test_memory_harness.py`, `tests/test_memories.py` | `src/services/memory_service.py` | Memory harness | Covered; formal gate failing |
| SAFE-01 | Chống prompt injection và secret leakage | `tests/test_guardrails.py`, `tests/test_agent_quality_harness.py` | `src/services/guardrail_service.py` | Golden injection cases | Covered |
| CAL-01 | Calendar đúng owner và token mã hóa | `tests/test_calendar.py` | `src/services/calendar_service.py` | TC-CAL-01/02 | Covered |
| OPS-01 | Health/readiness phản ánh DB/schema | `tests/test_api/test_routes.py` | `src/main.py`, `src/db/schema_health.py` | Latency benchmark | Covered; latency pending |
| OPS-02 | API có rate limit đúng tier | `tests/test_api/test_rate_limiting.py` | `src/api/rate_limit.py` | Automated test | Covered |
| EVAL-01 | Test suite đạt source coverage >=60% | `scripts/run_coverage.py` | `pyproject.toml` coverage config | `coverage-latest.json` | Runner ready; result pending |
| UX-01 | Luồng chính được người dùng đánh giá | Manual scenarios + feedback protocol | User/Admin frontend | `eval/user_feedback/` | Data pending |

## Quy tắc cập nhật

- Khi thêm requirement P0/P1, thêm ít nhất một dòng và link test tương ứng.
- Nếu một test bị xóa hoặc đổi tên, cập nhật ma trận trong cùng commit.
- `Covered` không thay thế kết quả chạy; báo cáo chính vẫn phải link artifact có timestamp.
