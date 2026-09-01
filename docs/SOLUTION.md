# Giải pháp & cách tiếp cận — Orbit

> Tài liệu này kể lại **cách nhóm đọc đề, cách nhóm nghĩ, giải pháp đã dựng và các metric dùng để
> chứng minh giải pháp hoạt động**. Nó nối [đề bài](PROJECT_REQUIREMENTS.md),
> [kiến trúc](ARCHITECTURE.md), [metric](../eval/METRICS.md) và
> [bằng chứng đánh giá](../eval/README.md) thành một mạch đọc từ vấn đề → giải pháp → số đo → kết quả.
>
> **Phạm vi:** Personal Agent là sản phẩm nền tảng theo đúng [đề bài gốc](PROJECT_REQUIREMENTS.md).
> Multi-Agent theo Workspace là **phần phát triển mở rộng**: đã có code/test đáng kể nhưng chưa
> phát hành mặc định; xem [§8](#8-phần-phát-triển-mở-rộng-và-các-hướng-tiếp-theo).
>
> **Nguồn sự thật:** khi tài liệu này lệch với code / migration Alembic / artifact trong `../eval/`,
> code và artifact có timestamp là đúng.

---

## 1. Bài toán và cách nhóm đọc đề

### 1.1 Đề yêu cầu gì

Người dùng nền tảng chat của Tập đoàn X nhận hàng trăm tin nhắn/ngày; việc cần làm, lịch hẹn, lời hứa
bị chôn trong luồng tin. Cần một **AI Agent cá nhân gắn trong app chat** biết:

- đọc hội thoại **được người dùng cho phép**, tóm tắt hội thoại dài;
- trích xuất việc cần làm / lịch hẹn, chủ động phát hiện cam kết ngay khi tin tới;
- lập kế hoạch nhiều bước, gọi tool (calendar, reminder, tìm tin cũ), lưu memory ngữ cảnh;
- hỏi lại khi thông tin mơ hồ.

Yêu cầu đầu ra chia **Cơ bản** (deploy online, đăng nhập, ≥2 role, tóm tắt/trích task/nhắc việc có
xác nhận, hiển thị lịch, memory, xử lý lỗi) và **Nâng cao** (proactive, đồng bộ Calendar 2 chiều,
dashboard inbox ưu tiên, cảnh báo vượt hạn mức token, bộ eval độ chính xác trích task).

### 1.2 Bốn ràng buộc — và cách nhóm diễn giải chúng

| Ràng buộc trong đề | Nhóm hiểu và làm thế nào |
|---|---|
| **Human-in-the-loop bắt buộc** trước khi tạo/gửi lịch, nhắc cho người khác | Không có ngoại lệ. Mọi tool có tác dụng phụ đi qua `interrupt()` của LangGraph; không có "cờ tắt xác nhận" kể cả để test nhanh. Đây là bất biến thiết kế, không phải tính năng có thể lược. |
| **Bảo mật & quyền riêng tư tin nhắn** — chỉ đọc hội thoại được cấp quyền, tôn trọng E2E, không lưu nội dung thô ra ngoài | E2E mã hoá đầu-cuối *thật* không khả thi trong khung thời gian (cần đổi toàn bộ mô hình lưu tin nhắn). Nhóm chọn thực thi **đúng tinh thần**: (a) bảng `ai_permissions` — AI chỉ đọc hội thoại người dùng bấm Grant; (b) tách quyền *dùng* Assistant khỏi quyền *xử lý message của một tác giả* (`granted` vs `contribution_allowed`); (c) cửa sổ context được **dựng ở server** từ message đã có consent, không tin danh sách `messages` client gửi lên; (d) minh bạch: panel AI ghi rõ "nội dung sẽ được gửi sang Gemini/Groq/OpenAI để xử lý". Cái *không* làm được nói thẳng ở [§7](#7-hạn-chế-đã-biết). |
| **Độ chính xác trích task cao (giảm false reminder)** | Đây là chỗ đánh đổi rõ nhất: **precision > recall**. Một false reminder làm mất niềm tin nhanh hơn một task bị bỏ sót. Prompt chỉ nhận cam kết của *chính người gửi*, không coi "assignment cho người khác" là task của người gửi; task mơ hồ gắn `needs_clarification` thay vì đoán. Có bộ eval riêng chấm **title F1** và **độ chính xác ngày** tách nhau (title đúng ≠ ngày đúng). |
| **Tối ưu độ trễ & chi phí** (chỉ tóm tắt khi cần, cache embedding, batch LLM call) | "Chỉ tóm tắt khi cần" → có. "Cache embedding / batch LLM call" → **không áp dụng được và nói thẳng là không**, vì app không dùng vector store / embedding ở đâu để mà cache, và không có luồng LLM nào tự nhiên gộp được. Tối ưu *thật sự* áp dụng: pre-filter regex trước khi gọi LLM ở proactive detection, agent dừng sau tool cuối (không gọi LLM lần 2), đa provider để không chết vì quota, chọn model theo cost benchmark. |

### 1.3 Quyết định phạm vi có chủ đích

- **Không** đổi frontend sang Next.js hay backend sang NestJS — React + Vite và FastAPI đủ và đã chạy.
- **Không** dùng Qdrant/pgvector/Redis/BullMQ/Socket.IO — xem lý do ở [§4.4](#44-vì-sao-lệch-tech-stack-gợi-ý).
- **Không** làm bản giả cho tính năng chưa xong. Phần chưa hoàn tất phải ghi rõ trong [§7](#7-hạn-chế-đã-biết)
  hoặc báo cáo phát triển Workspace, không trình bày mock/prototype như release.
- **Không** làm "Quên mật khẩu" bản giả — cần SMTP thật, quyết định bỏ qua thay vì dựng nút không nối gì.

---

## 2. Mindset — tám nguyên tắc thiết kế

Đây là phần mentor muốn thấy: *cách nhóm nghĩ*. Mỗi nguyên tắc kèm nơi nó hiện ra trong code.

### 2.1 Human-in-the-loop là bất biến, không phải bước có thể bỏ

Mọi tool tạo/sửa/xoá sự kiện Calendar và `create_reminder` **bắt buộc** đi qua `interrupt()` trong
`src/agents/graph.py`. Agent trả `status: "interrupted"` + payload để UI dựng thẻ Xác nhận/Huỷ; chỉ
sau `POST /chat/resume` graph mới thực thi. Không có đường tắt trong code, kể cả cho test — test HITL
đi đúng luồng `interrupt → resume`.

### 2.2 Consent trước context, không tin client

Cửa sổ tin nhắn đưa vào model được **server dựng** (`consent_service.build_authorized_message_view`),
không lấy từ `messages` client gửi. Ba lớp:

- `ai_permissions (conversation_id, user_id, granted)` — mặc định **chưa** cấp; `POST /chat` trả 403
  nếu chưa Grant.
- Tách `granted` (được gọi Assistant) khỏi `contribution_allowed` (message của tác giả này được AI xử
  lý) — nội dung của tác giả chưa đồng ý **không tới model**.
- `consent_scope_hash` được re-check trước *và* sau lời gọi LLM ở các luồng nền (event extraction,
  rolling summary) để không commit kết quả suy ra từ consent đã lỗi thời; thu hồi consent đặt cờ
  `needs_reset` buộc xây lại từ đầu.

### 2.3 Không làm tính năng giả

Nếu chưa nối được API thật thì nói chưa xong, không dựng UI mock trông như thật. `mockData.js` còn tồn
tại nhưng **không được import ở đâu**. E2E và deploy online chưa làm — ghi rõ, không che.

### 2.4 Đo trước khi tuyên bố; `PENDING` không quy đổi thành pass

Mọi con số chất lượng đều có **script tái lập** và **artifact có timestamp + commit SHA** trong
`../eval/`. [EVALUATION_EVIDENCE.md](../eval/EVALUATION_EVIDENCE.md) ghi rõ: *"This report never
converts missing evidence into a passing score"*. Latency P95 trên môi trường target và user feedback
hiện là `PENDING` — và được để nguyên là `PENDING`, không đoán.

### 2.5 Rẻ nhất mà vẫn qua mọi safety gate

- Proactive detection: **regex pre-filter (EN+VI)** rồi mới hỏi LLM — phần lớn tin nhắn không chạm LLM.
- Chỉ tóm tắt/trích xuất khi người dùng bấm; không tóm tắt ngầm.
- Đa provider LLM (`LLM_PROVIDER` = google | groq | openai) — đổi khi một bên hết quota, không phải sửa code.
- [METRICS.md §7](../eval/METRICS.md) định nghĩa cost benchmark: chọn cấu hình model **rẻ nhất vượt toàn bộ
  safety/release gate**, không chọn theo điểm chất lượng trung bình.

### 2.6 Fail an toàn, không chặn hot path

Proactive detection chạy `asyncio.create_task` / `BackgroundTasks`, **không bao giờ raise ra ngoài**,
không chặn việc gửi tin nhắn. Khi vượt `DAILY_TOKEN_BUDGET`, `is_over_budget()` chặn **lời gọi LLM
mới** (`/chat`, proactive) nhưng **chừa `/chat/resume`** — để không treo lơ lửng một hành động người
dùng đã xác nhận.

### 2.7 Determinism ở đúng chỗ cần

- Agent **dừng sau tool cuối** (`summarize_conversation`, `extract_tasks`) — không gọi LLM lần 2 (từng
  gây lỗi 400 "tool call validation failed" khi model tự sinh cú pháp gọi tool giả).
- **Ground ngày hiện tại** vào system prompt theo `calendar_timezone` — "ngày mai" / "thứ Sáu này"
  resolve đúng năm thật, không để model đoán theo dữ liệu huấn luyện.
- **Múi giờ cố định `Asia/Ho_Chi_Minh`** ở cả frontend (Intl), scheduler và mốc "hôm nay" của thống kê
  token — không phụ thuộc giờ máy server.

### 2.8 Bền vững qua restart

`AsyncPostgresSaver` giữ agent thread + interrupt qua restart; APScheduler dùng `SQLAlchemyJobStore`
nên reminder sống sót; refresh token Google Calendar mã hoá Fernet trước khi vào DB. Trên Windows,
`scripts/run_dev.py` ép `SelectorEventLoop` vì `AsyncPostgresSaver` (psycopg async) không chạy trên
`ProactorEventLoop` mà `uvicorn` CLI luôn chọn.

---

## 3. Giải pháp — tổng quan

```
┌── Frontend/user  :5173 ──┐      ┌── Frontend/admin :5174 ──┐
│  React + Vite            │      │  React + Vite (app riêng) │
│  /chat /assistant /tasks │      │  users, AI config,       │
│  /tasks/inbox /calendar  │      │  usage, audit log        │
│  /reminders /memory      │      └────────────┬─────────────┘
│  /profile                │                   │ JWT
└───────────┬──────────────┘                   │
            │ JWT + REST + WebSocket           │
            ▼                                  ▼
┌─────────────────── FastAPI (src/) :8000 ───────────────────┐
│  api/         route mỏng: auth, chat người-người, /chat    │
│  services/    chat, proactive, calendar, reminder, usage,  │
│               consent, conversation_summary, scheduler     │
│  agents/      LangGraph: planner + tools + interrupt()     │
│  websocket/   1 kênh realtime dùng chung                   │
└───────┬───────────────┬───────────────┬───────────────────┘
        │               │               │
        ▼               ▼               ▼
  PostgreSQL      LLM provider     Google Calendar API
  (app data +    (Gemini/Groq/     (OAuth per-user,
   AsyncPostgres  OpenAI)          refresh token Fernet)
   Saver + APS
   jobstore)
```

### 3.1 Các khối chính

| Khối | Vai trò | Điểm đáng chú ý |
|---|---|---|
| **Auth** | Đăng ký/đăng nhập bcrypt + JWT, role `user`/`admin`, đăng nhập Google (ID token, bảng `google_identities` riêng) | 2 app Vite tách hẳn; app admin có bootstrap key riêng, mọi route admin qua `require_admin` |
| **Chat người–người** | 1-1 và nhóm realtime qua WebSocket, lịch sử, đếm chưa đọc, đính kèm file + emoji, layout điện thoại | Đính kèm nhúng data URL vào `messages.content` (chưa có kho file riêng) |
| **AI Agent** (`POST /chat` + `/chat/resume`) | LangGraph planner + 11 tool; 4 tool có tác dụng phụ đi qua `interrupt()` | Tool đọc-only: `summarize_conversation`, `extract_tasks`, `search_messages`, `list_tasks`, `list_memories`, `list_calendar_events` |
| **Proactive detection** | Mỗi tin nhắn mới: regex pre-filter → LLM xác nhận → tạo `Task` gợi ý cho *người gửi* → đẩy WebSocket | Chạy nền, không chặn gửi tin, không raise; chỉ nhận cam kết của chính sender |
| **Tasks + Inbox ưu tiên** | CRUD task thật; `/tasks/inbox` gom 4 nhóm: cần quyết định / quá hạn / sắp đến hạn 48h / priority cao | Tính phía client từ `/tasks`, không thêm endpoint |
| **Calendar** | Google Calendar per-user, đồng bộ 2 chiều, realtime | Ghi: REST + agent tool. Đọc thay đổi từ Google: polling `syncToken` (chưa webhook vì chưa có domain public) |
| **Reminders** | Tạo/huỷ, bền vững qua restart (`SQLAlchemyJobStore`), đẩy `reminder_fired` realtime | |
| **Memory** | CRUD "điều Orbit nên nhớ về bạn"; agent chỉ tìm memory/task của đúng user lượt chat | + rolling summary consent-scoped cho hội thoại 1-1/nhóm |
| **Usage & budget** | Ghi token mỗi lần gọi LLM; cảnh báo edge-triggered 80%/100% qua WebSocket tới mọi admin online; chặn cứng khi hết ngân sách | `/chat/resume` được miễn trừ |
| **Rate limiting** | `src/api/rate_limit.py` — in-memory sliding-window theo user/IP, theo tier | Loại trừ `/health`, `/chat/resume`, `/chat/status` |

### 3.2 Luồng "hỏi trợ lý AI" (có HITL)

1. Frontend gọi `POST /api/v1/chat` kèm câu hỏi, `thread_id` tuỳ chọn, `conversation_id` tuỳ chọn.
2. Nếu gắn hội thoại thật: server kiểm tra **participant** *và* **consent** (`ai_permissions`).
3. LangGraph planner: trả lời trực tiếp, hoặc gọi tool.
4. Tool đọc-only chạy ngay và **kết thúc lượt**. Tool có tác dụng phụ → `interrupt()`, trả
   `status: "interrupted"` + payload.
5. Người dùng bấm Xác nhận/Huỷ → `POST /chat/resume` → graph tiếp tục từ checkpoint PostgreSQL.

### 3.3 Luồng proactive (không cần người dùng yêu cầu)

```
tin nhắn mới ──► regex pre-filter (EN+VI) ──match?──► hỏi LLM: có phải cam kết/lịch hẹn?
                        │ no                                   │ yes
                        ▼                                       ▼
                   bỏ qua (không tốn LLM)          tạo Task source="proactive" status="suggested"
                                                   cho người gửi  ──►  WebSocket task_suggested + toast
                                                   (Accept vẫn là bước HITL: chỉ thêm task,
                                                    Calendar/Reminder cần confirm riêng)
```

### 3.4 Vì sao lệch tech stack gợi ý

| Đề gợi ý | Nhóm dùng | Lý do |
|---|---|---|
| Vector DB (Qdrant / pgvector) lưu memory & lịch sử | `AsyncPostgresSaver` (agent thread) + tính năng **Memory** người dùng tự ghi + `search_messages` bằng `ILIKE` | Yêu cầu "memory hội thoại" (Cơ bản) đạt qua checkpointer; memory cá nhân đạt qua ghi chú người dùng. Chưa có nhu cầu semantic search đủ rõ để biện minh thêm một service + chi phí vận hành. Chỉ thêm khi có nhu cầu thật ([§8](#8-phần-phát-triển-mở-rộng-và-các-hướng-tiếp-theo)). |
| Redis + BullMQ / cron | APScheduler + `SQLAlchemyJobStore` | Job sống qua restart mà không cần thêm hạ tầng; đủ cho triển khai single-instance. |
| Socket.IO | WebSocket thuần (`src/websocket/`) | Một kênh realtime dùng chung cho chat / reminder / task / calendar / budget alert; không cần lớp trừu tượng của Socket.IO. |
| 1 tài khoản Google Calendar dùng chung | OAuth **per-user**, mỗi người tự Connect | Đúng ngữ nghĩa "lịch cá nhân"; sự kiện WebSocket chỉ tới đúng chủ lịch; refresh token mã hoá Fernet. |
| GPT-4o-mini / Claude Haiku cố định | `LLM_PROVIDER` chuyển được (Gemini / Groq / OpenAI) | Chống chết vì quota một nhà cung cấp; cho phép chạy cost benchmark chọn cấu hình rẻ nhất qua gate. |

---

## 4. Metric cho bài toán

Khung đầy đủ: [METRICS.md](../eval/METRICS.md). Kết quả đo mới nhất: [EVALUATION_EVIDENCE.md](../eval/EVALUATION_EVIDENCE.md),
[`eval/results/`](../eval/results/). Ánh xạ yêu cầu ↔ test ↔ code: [TRACEABILITY_MATRIX.md](../eval/TRACEABILITY_MATRIX.md).

### 4.1 North-star và release gate

**North-star:** *tỷ lệ action suggestion đúng, có ích, được người dùng chấp nhận mà không vi phạm
quyền hoặc gây side effect ngoài ý muốn.*

Nếu **privacy / authorization / HITL / duplicate side effect** fail → **không release** dù điểm trung
bình cao.

### 4.2 Mỗi ràng buộc đề bài → metric → kết quả đo gần nhất

| Ràng buộc | Metric | Gate | Kết quả đo | Nguồn |
|---|---|---:|---|---|
| Độ chính xác trích task (giảm false reminder) | Task title precision / recall / F1 | F1 ≥ 0.85 | **F1 91.9%** (P 85.0% / R 100%) trên 37 case VI+EN có case bẫy | `eval/results/report.md`, `task-extraction-latest.json` |
| " | Độ chính xác ngày/deadline | ≥ 0.90 (mục tiêu); ≥ 0.70 (gate hiện tại) | **82.1%** (23/28 case có ngày) | `eval/results/report.md` |
| " | Formal acceptance (task P/R/F1, due, priority) trên bộ 18 case xác định | 100% case pass | **100%** case pass; task P/R/F1 = 100%; due 100% | `eval/results/agent_acceptance_latest.md` |
| Human-in-the-loop | Side effect qua HITL | 100% | `hitl_preconfirmation_side_effect_rate` = **0%** | `eval/results/agent_acceptance_latest.md`, `HITL-01` |
| " | Duplicate side effect khi retry / double-click | 0 | Golden HITL cases **PASS**, `HITL-02` Covered | `eval/TRACEABILITY_MATRIX.md` |
| Quyền riêng tư | Rò rỉ raw content trái phép trong bộ red-team quyền | 0 | `forbidden_claim_rate` = **0%**, `unsupported_claim_rate` = **0%** | `agent_acceptance_latest.md` |
| " | Grounding — claim quan trọng có nguồn hợp lệ | ≥ 0.95 | RAGAS faithfulness **100%** | `eval/results/ragas-latest.md` |
| " | Memory isolation giữa user, loại memory hết hạn/thu hồi | 100% | `memory_isolation_pass_rate` **100%**, `expired_memory_rejection_rate` **100%** | `agent_acceptance_latest.md` |
| " | Chống prompt injection / lộ secret | pass | `SEC-01` **PASS**; `tests/test_guardrails.py` Covered | `agent_acceptance_latest.md`, `SAFE-01` |
| Routing đúng tool | `tool_routing_accuracy` | ≥ 0.95 | **100%** trên bộ acceptance | `agent_acceptance_latest.md` |
| Độ trễ & chi phí | Latency P95 interactive (summarize/search) trên môi trường target | < 5 s | **PENDING** — runner có, chưa đo trên target env | `eval/EVALUATION_EVIDENCE.md` |
| " | Latency quan sát trong bộ acceptance (không phải môi trường target) | tham khảo | p50 **3.25 s**, p95 **12.7 s**, mean 4.28 s | `agent_acceptance_latest.md` |
| " | Overhead thêm vào lúc gửi tin nhắn (proactive async) | P95 < 300 ms | inference chạy async, ngoài critical path | `eval/METRICS.md §2.6` |
| " | Token / run, cost / successful run | trong budget profile | run acceptance: ~80k token / 18 case / 28 lời gọi LLM | `agent_acceptance_latest.md` |
| Chất lượng kỹ thuật | Regression suite | 100% pass | **416/417 passed, 1 skipped** | `eval/EVALUATION_EVIDENCE.md` |
| " | Source coverage | ≥ 60% | **67.9%** | `eval/results/coverage-latest.json` |
| Proactive hữu ích | Suggestion precision | ≥ 0.90 | gate định nghĩa; acceptance rate lấy baseline ngày demo, mục tiêu pilot ≥ 30% | `eval/METRICS.md §2.6` |

### 4.3 Cách chấm (tóm tắt — chi tiết ở `eval/METRICS.md`)

- **Trích task:** đơn vị là *task fact* `(action, assignee, due_at, source)`, không so chuỗi title.
  TP = đúng ý định + assignee hợp lý + source hỗ trợ. Task mơ hồ gắn `needs_clarification` không tính
  FP nếu câu hỏi làm rõ phù hợp và chưa tạo side effect.
- **Tóm tắt:** rubric 0–2 cho Coverage / Faithfulness / Attribution / Concision / Privacy. Pass khi
  faithfulness và privacy tuyệt đối; normalized ≥ 0.85. ROUGE/BLEU chỉ tham khảo.
- **An toàn:** permission matrix ≥ 30 case (đoán ID người khác, đọc chat riêng, cross-workspace, consent
  thu hồi…), prompt-injection ≥ 20 case, HITL/idempotency ≥ 20 case. Kỳ vọng: `DENY`/`MASK` đúng policy,
  không lộ cả việc resource có tồn tại; 100% side effect có confirm hợp lệ; không duplicate.
- **Nguyên tắc báo cáo:** mỗi report có commit SHA, environment, dataset/prompt/model version, slice
  theo intent, ví dụ lỗi đã khử nội dung, quyết định pass/fail từng gate — **không chỉ một con số
  accuracy tổng**.

### 4.4 Chưa đủ / cần người/thiết bị ngoài chạy

- RAGAS và formal acceptance cần API key model thật + tốn quota.
- User satisfaction cần người thật (ẩn danh), ≥ 5 người — **không chấp nhận rating tổng hợp giả**. Hiện `PENDING`.
- Latency phải đo trên đúng môi trường target, ghi kèm URL/model — hiện `PENDING`.
- Bộ eval trích task hiện ~37 case: đủ làm bằng chứng ban đầu, **chưa** phải benchmark quy mô lớn.

---

## 5. Kết quả so với yêu cầu đề bài

Đối chiếu yêu cầu và bằng chứng hiện hành: [TRACEABILITY_MATRIX.md](../eval/TRACEABILITY_MATRIX.md).

### Cơ bản

| Yêu cầu | Trạng thái |
|---|---|
| App deploy online, đăng nhập, ≥ 2 role | 🟡 Auth (JWT+bcrypt) + role user/admin **chạy thật**; `Dockerfile`/`render.yaml`/CD workflow sẵn sàng; **chưa deploy lên domain public** |
| Tóm tắt hội thoại theo yêu cầu | 🟢 nút Summarize → `/chat` thật, có grounding (RAGAS 100%) |
| Trích xuất task + nhắc việc có xác nhận | 🟢 `extract_tasks` + `create_reminder` (HITL), `/tasks` và `/reminders` nối API thật |
| Hiển thị lịch cá nhân | 🟢 `/calendar` gọi Google Calendar API thật, CRUD đầy đủ, per-user |
| Memory hội thoại | 🟢 `AsyncPostgresSaver` + rolling summary consent-scoped + tính năng Memory |
| Xử lý lỗi cơ bản | 🟢 `ChatResponse.status="error"` trả lỗi thật; không gọi LLM lần 2 gây 400 |

### Nâng cao

| Yêu cầu | Trạng thái |
|---|---|
| Agent chủ động phát hiện cam kết | 🟢 `proactive_service` — pre-filter + consent + chỉ cam kết của sender + provenance + invalidate khi revoke |
| Đồng bộ Google Calendar 2 chiều | 🟢 ghi qua REST/agent tool; đọc thay đổi từ Google qua polling `syncToken` (webhook thật là future work — cần domain public) |
| Dashboard "inbox nhiệm vụ" ưu tiên | 🟢 `/tasks/inbox`, 4 nhóm ưu tiên, realtime |
| Cảnh báo vượt hạn mức token/chi phí | 🟢 edge-triggered 80/100% qua WebSocket tới mọi admin + chặn cứng LLM mới khi hết ngân sách |
| Đánh giá độ chính xác trích task | 🟢 (mẫu nhỏ) `scripts/eval_extract_tasks.py` chấm title F1 + date accuracy tách nhau; kết quả ở `eval/results/` |
| *(thêm)* Rate limiting | 🟢 `src/api/rate_limit.py`, in-memory sliding-window theo tier |

---

## 6. Bằng chứng & cách tái lập

```powershell
# Test + coverage
pytest tests/ -v
python scripts/run_coverage.py

# Eval chất lượng AI (cần API key model thật)
python scripts/eval_user_agent.py          # formal acceptance -> eval/results/agent_acceptance_latest.md
python scripts/eval_extract_tasks.py       # task title F1 + date accuracy -> eval/results/
python scripts/validate_multi_agent_dataset.py  # dataset phần Workspace mở rộng
python scripts/workspace_agent_load_harness.py --help
```

Bằng chứng thủ công: [Manual Test Report](../eval/manual/MANUAL_TEST_REPORT.md) (10/10 PASS có ảnh,
commit `1990341`, 2026-08-16); video demo trong [`Deliverables/`](../Deliverables/).

---

## 7. Hạn chế đã biết

| Hạn chế | Chi tiết |
|---|---|
| **Chưa deploy online** | Code hạ tầng (Dockerfile, `render.yaml`, `Frontend/vercel.json`, CD workflow) đã có; còn lại là thao tác dashboard. Đây cũng là điều kiện để nâng Calendar sync từ polling lên webhook `events.watch` thật. |
| **Không có E2E mã hoá đầu-cuối thật** | Thay bằng consent-scoped reading + minh bạch (xem [§1.2](#12-bốn-ràng-buộc--và-cách-nhóm-diễn-giải-chúng), [§2.2](#22-consent-trước-context-không-tin-client)). Nội dung tin nhắn *có* được gửi sang API LLM ngoài khi dùng tính năng AI — panel AI báo rõ điều này. |
| **Latency P95 trên môi trường target: PENDING** | Runner có; số p50 3.25 s / p95 12.7 s hiện lấy từ bộ acceptance, không phải môi trường triển khai thật. |
| **User feedback: PENDING** | Cần ≥ 5 người thật đánh giá luồng task/calendar/memory; không dùng rating giả. |
| **Bộ eval còn nhỏ ở vài slice** | ~37 case trích task; permission red-team và proactive acceptance mới ở mức baseline. |
| **Single-instance** | WebSocket registry + ownership map của agent thread nằm trong RAM process; APScheduler chạy cùng web process. Chưa an toàn scale ngang (cần Redis cho rate limit + owner store bền vững). |
| **Đính kèm file** | Nhúng data URL vào `messages.content` (đã nới `max_length` 5 MB); chưa có kho lưu trữ riêng, chưa quét MIME/virus. |

---

## 8. Phần phát triển mở rộng và các hướng tiếp theo

### 8.1 Multi-Agent theo Workspace

Đây là phần phát triển mở rộng của Orbit: ứng dụng AI nội bộ của **một công ty**, Admin tạo các **Workspace phòng ban**,
mỗi Workspace gắn một Agent chuyên môn; giám đốc dùng **Executive Agent** xem bức tranh liên phòng ban
qua các `WorkspaceBrief` đã kiểm chứng (không đọc raw chat liên phòng).

- Ba Workspace Agent định hướng: **Product Delivery**, **Quality Assurance**, **Executive**.
- Personal Agent là sản phẩm nền tảng riêng, không tính là Workspace Agent thứ tư.
- Repo đã có control plane, runtime, tool, UI và test đáng kể cho Workspace; các feature flag vẫn mặc định tắt và chưa có live acceptance riêng đủ để tuyên bố release.
- Thiết kế và hiện trạng: [Workspace Development](workspace-development/README.md) và
  [Development Report](workspace-development/DEVELOPMENT_REPORT.md).

### 8.2 Các hướng khác

1. **Xác minh deployment cùng một revision** và công bố rõ staging/production; xem [Deployment](DEPLOYMENT.md).
2. **Webhook Calendar sync** (`events.watch`) thay polling — cần domain public HTTPS.
3. **Mở rộng eval harness** — thêm case thật (ẩn danh) từ hội thoại người dùng để đo chính xác hơn
   trước khi báo cáo con số cuối; đặt coverage ≥ 60% thành CI gate cứng.
4. **Đo latency P95 + user feedback** trên môi trường target (biến `PENDING` thành số thật).
5. **Sẵn sàng scale ngang** — Redis cho rate limit dùng chung, owner store của agent thread bền vững,
   tách scheduler khỏi web process.
6. **Vector store** — chỉ thêm khi phát sinh nhu cầu semantic search rõ ràng (quyết định có chủ đích
   hiện tại là *không* thêm).
7. **Giảm false positive trích task** ở câu hỏi tu từ, FYI/việc đã xong, small talk; cải thiện resolve
   ngày cho "next week", deadline sửa lại, cách nói thứ trong tuần tiếng Việt.

---

## 9. Tài liệu liên quan

| Tài liệu | Nội dung |
|---|---|
| [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md) | Đề bài gốc |
| [README.md](../README.md) | Tính năng, cách chạy và dùng thử |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Kiến trúc sản phẩm nền tảng |
| [METRICS.md](../eval/METRICS.md) | Khung metric và benchmark |
| [EVALUATION_EVIDENCE.md](../eval/EVALUATION_EVIDENCE.md) | Bằng chứng release và số đo mới nhất |
| [TRACEABILITY_MATRIX.md](../eval/TRACEABILITY_MATRIX.md) | Yêu cầu ↔ test ↔ code ↔ evidence |
| [WORKLOG.md](../WORKLOG.md) | Nhật ký thay đổi và cách verify |
| [Workspace Development](workspace-development/README.md) | Phần phát triển mở rộng Multi-Agent |
