# Roadmap — hoàn thiện "AI Agent Trợ lý cá nhân trong Chat" theo đề bài

Đề bài gốc: [Frontend/detai.md](Frontend/detai.md). Kiến trúc/quyết định công nghệ chi tiết:
[ARCHITECTURE.md](ARCHITECTURE.md). Nhật ký chi tiết từng thay đổi: [WORKLOG.md](WORKLOG.md). Tài
liệu này chỉ theo dõi **tiến độ theo yêu cầu đề bài** — cập nhật trạng thái mỗi khi một mục hoàn
thành.

## Bảng hiện trạng (gap analysis)

| Yêu cầu | Trạng thái | Ghi chú |
| --- | --- | --- |
| Deploy online, đăng nhập, ≥2 role | 🟡 Một phần | Auth (JWT+bcrypt) + role user/admin đã chạy thật; `Dockerfile`/`docker-compose.yml` có sẵn nhưng **chưa deploy lên domain public**, chưa có CD |
| Tóm tắt hội thoại theo yêu cầu | 🟢 Xong | Nút Summarize trong `AIPanel.jsx` gọi `/api/v1/chat` thật |
| Trích xuất task + tạo nhắc việc có xác nhận | 🟢 Xong | Tool `extract_tasks` + `create_reminder` (human-in-the-loop), `/tasks` và `/reminders` nối API thật |
| Hiển thị lịch cá nhân | 🟢 Xong | `/calendar` gọi Google Calendar API thật (CRUD đầy đủ) |
| Memory hội thoại | 🟢 Xong | `AsyncPostgresSaver` giữ agent thread qua restart. Consent-scoped rolling summary/STM cho chat 1-1/nhóm: `conversation_summary_service.py` (heartbeat 15 phút, `conversation_rolling_summaries` table) gộp dần tin nhắn của người đã `contribution_allowed`/`ai_enabled` thành 1 bản tóm tắt tích luỹ, bơm vào system prompt qua `context_node`/`planner_node` — trả lời được câu hỏi tự do xuyên nhiều tháng dù cửa sổ context mỗi request chỉ ≤50 tin nhắn. Thu hồi consent giữa chừng (`contribution_allowed=False` hoặc rời group đang bật AI) đặt cờ `needs_reset` để lần chạy kế tiếp xây lại từ đầu, không tiếp tục phát tán nội dung đã thu hồi. Riêng trang `/assistant` độc lập đã có cơ chế tương đương từ trước (`memory_maintenance_service.py` + `AssistantThread`/`MemoryEpisode`), không đổi. |
| Xử lý lỗi cơ bản | 🟢 Xong | `ChatResponse` có `status: "error"` trả lỗi thật; agent không gọi LLM lần 2 gây lỗi 400 |
| Agent chủ động phát hiện cam kết | 🟢 P0 an toàn | `proactive_service.py` — pre-filter + yêu cầu sender bật cả Assistant/contribution consent + prompt chỉ nhận cam kết của chính sender, không coi assignment cho người khác là task của sender. Candidate có provenance và bị invalidate khi nguồn revoke. **Accept task chỉ thêm task**; Calendar/Reminder cần confirmation riêng, không còn side effect ẩn. |
| Đồng bộ Google Calendar 2 chiều | 🟢 Xong | Ghi (app→Google) qua REST/agent tool; đọc thay đổi từ Google qua polling `syncToken` (`poll_calendar_changes`, mỗi 20s) — xem ghi chú bên dưới về giới hạn |
| Dashboard "inbox nhiệm vụ" ưu tiên | 🟢 Xong | `/tasks/inbox` (`TaskInboxPage.jsx`, nav "Inbox" trong Sidebar) — view tách riêng khỏi `/tasks`, nhóm theo 4 mức ưu tiên (cần quyết định / quá hạn / sắp đến hạn trong 48h / priority cao), realtime qua cùng kênh WebSocket đã có |
| Cảnh báo vượt hạn mức token/chi phí | 🟢 Xong | `usage_service._maybe_alert_budget` đẩy WebSocket `usage_budget_alert` tới mọi admin đang online ngay khi vượt 80%/100% (edge-triggered, không lặp lại nếu không có ngưỡng mới vượt) — hiện ở bất kỳ trang nào admin đang mở (`BudgetAlertToast`), không chỉ khi mở Admin dashboard; **và** `usage_service.is_over_budget()` chặn hẳn cuộc gọi LLM mới (`/chat`, proactive detection) một khi đã chạm ngân sách — `/chat/resume` cố tình được miễn trừ để không làm treo một hành động con người đã xác nhận rồi. Verify thật qua UI (không phải chỉ unit test): xem WORKLOG.md |
| Rate limiting | 🟢 Xong | `src/api/rate_limit.py` — in-memory sliding-window, khoá theo user (JWT)/IP, áp cho mọi `/api/v1/*` theo tier (`register` 5/phút, `auth` 10/phút, `chat` POST 15/phút, `crud` 60/phút mặc định), loại trừ `/health` và `/chat/resume`+`/chat/status` để không chặn HITL resume dở dang. Cấu hình qua `.env` (`RATE_LIMIT_*`, xem `.env.example`); test `tests/test_api/test_rate_limiting.py`. Giới hạn đã biết: in-memory nên không chia sẻ giữa nhiều worker/instance — đủ cho triển khai single-instance hiện tại, cần chuyển sang Redis nếu scale ngang. |
| Đánh giá độ chính xác trích xuất task | 🟢 Xong (mẫu nhỏ) | `scripts/eval_extract_tasks.py` — chấm riêng title (P/R/F1) và **date accuracy** (`due_at` có resolve đúng "ngày mai"/"thứ Sáu này" theo ngày chạy thật không — 2 thứ lệch pha, title đúng không đảm bảo ngày đúng). Hiện tại: Title F1 = 100%, Date accuracy = 100% trên 8 case tay (VI+EN, 7/8 case có ngày); nên coi là bằng chứng ban đầu, chưa phải benchmark quy mô lớn |
| Ràng buộc: quyền riêng tư tin nhắn / strict participant consent | 🟢 P0 xong | Tách `granted` (quyền dùng Assistant) và `contribution_allowed` (quyền xử lý message do user gửi). `AuthorizedMessageView` được build ở backend, không tin raw messages từ client khi có `conversation_id`; content của non-consenting author không tới model. Có coverage UI, consent hash, stale-HITL revalidation và invalidation cho candidate chưa xác nhận. |
| Ràng buộc: tối ưu độ trễ/chi phí (cache embedding, batch LLM call) | ⚪ Không áp dụng được | App không dùng vector store/embedding ở đâu cả nên không có gì để cache; pre-filter regex trước khi gọi LLM (proactive detection) là tối ưu duy nhất thực sự áp dụng được |
| Ràng buộc: human-in-the-loop trước khi tạo/gửi lịch, nhắc việc | 🟢 Xong | `interrupt()` bắt buộc cho mọi tool có tác dụng phụ (calendar CRUD, `create_reminder`) |

🟢 Xong · 🟡 Một phần · ⚪ Không áp dụng · 🔴 Chưa có

## Còn lại — theo độ ưu tiên

1. **Deploy online thật** — hạng mục lớn nhất còn thiếu. Stack đã chốt: backend lên Render, Postgres
   quản lý trên Supabase, frontend lên Vercel; CD qua `.github/workflows/deploy.yml`, gate sau khi CI
   pass trên `main`. Code (Dockerfile, `render.yaml`, workflows, `Frontend/vercel.json`) đã sẵn sàng —
   còn lại là các bước thao tác dashboard, xem hướng dẫn đầy đủ ở [docs/deploy.md](docs/deploy.md).
   Đây cũng là điều kiện để nâng cấp đồng bộ Calendar từ polling lên webhook `events.watch` thật của
   Google (cần domain public HTTPS).
2. **Mở rộng eval harness** — bộ 8 case tay hiện tại chỉ đủ làm bằng chứng ban đầu; nên thêm case
   thật từ hội thoại người dùng (ẩn danh) để đo chính xác hơn trước khi báo cáo con số cuối.
3. **Batch LLM call** (ưu tiên thấp) — bấm liên tiếp nhiều Quick Action (vd Summarize rồi Extract
   tasks) trên cùng hội thoại hiện tốn nhiều lần gọi LLM riêng dù cùng 1 context; có thể gộp lại.
   Lợi ích khiêm tốn.

## Ngoài phạm vi (quyết định có chủ đích)

- Không đổi frontend sang Next.js, không đổi backend sang NestJS.
- Không tự implement mã hoá E2E thật cho tin nhắn — thay vào đó dự định thực thi đúng tinh thần
  "chỉ đọc hội thoại được cấp quyền" qua bảng `ai_permissions` (mục 2 ở trên), panel AI đã có dòng
  minh bạch báo người dùng nội dung sẽ được gửi sang Gemini/Groq.
- Không dùng BullMQ/Redis/Socket.IO — giữ nguyên APScheduler + WebSocket thuần đã có.
- Không xây vector store dài hạn (Qdrant/pgvector/ChromaDB) — yêu cầu "Cơ bản" về memory đã đạt qua
  `AsyncPostgresSaver`, yêu cầu memory cá nhân đã đạt qua tính năng Memory (ghi chú người dùng tự
  thêm); không có nhu cầu semantic search rõ ràng để biện minh thêm 1 service. Xem
  [ARCHITECTURE.md](ARCHITECTURE.md) mục Vector Store.
- Không xây chức năng "Quên mật khẩu" — cần SMTP/email service thật để gửi link đặt lại, dự án chưa
  có và quyết định bỏ qua thay vì làm bản giả (2026-08-03). Nút "Forgot password?" trên `LoginPage`
  hiện vẫn là nút chưa nối gì cả.

---
Mỗi mục ở trên đủ lớn để cần một phiên plan + review riêng trước khi code — không gộp chung nhiều
mục vào 1 lần triển khai.

## Cập nhật 2026-08-10 — group AI và bộ nhớ lịch

- Group chat không còn lọc rời từng tác giả. Conversation manager quản lý một policy AI chung;
  khi bật, toàn bộ message của các participant hiện hành là context liên tục và mọi thành viên đều
  thấy trạng thái AI.
- Direct chat vẫn giữ `granted` và `contribution_allowed` độc lập.
- Đã có `EventCandidate` cho create/update/cancel, provenance theo message, confidence/missing fields,
  revalidation trước confirm và manager-only confirmation trước khi ghi Google Calendar.
- Đã có incremental extraction cho message mới và historical backfill theo batch/cursor. Vì vậy lịch
  cũ không cần được tìm bằng cách gửi toàn bộ lịch sử chat vào mỗi request.
- Chưa có general semantic retrieval/rolling summary cho câu hỏi tự do xuyên nhiều tháng; phần đã
  hoàn thành là memory chuyên biệt cho calendar facts.
