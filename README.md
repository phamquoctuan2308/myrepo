# P-132 — Orbit AI Assistant

Dự án AI20K Build Phase: Orbit là trợ lý AI cá nhân nhúng trong ứng dụng chat, giúp người dùng tóm tắt hội thoại, trích xuất công việc/lịch hẹn, tạo nhắc nhở có xác nhận và quản lý lịch cá nhân. Multi-Agent theo Workspace là **hướng phát triển tiếp theo** để mở rộng Orbit từ trợ lý cá nhân thành trợ lý chuyên môn cho các nhóm trong công ty. Repo gồm **backend** (FastAPI + LangGraph, thư mục `src/`) và **frontend** (React + Vite, thư mục `Frontend/`).

## Mô hình sản phẩm

### Sản phẩm hiện tại: Personal Agent

Orbit hiện tập trung vào trợ lý cá nhân cho từng user. Task, Memory, Reminder và Calendar thuộc phạm vi cá nhân; AI chỉ đọc conversation khi user là participant và đã cấp quyền AI phù hợp.

Hệ thống có hai loại tài khoản:

- **User**: sử dụng chat, Personal Agent, task, calendar, reminder và memory của mình.
- **Platform Admin**: quản lý tài khoản, cấu hình AI, usage và audit; không mặc định có quyền đọc nội dung chat của user.

Personal Agent là flow mặc định của `POST /api/v1/chat` và trang `/assistant`. Mọi hành động có side effect như tạo/sửa/xóa Calendar hoặc Reminder đều phải chờ user xác nhận.

### Hướng mở rộng sau MVP: Multi-Agent theo Workspace

Multi-Agent chưa phải flow mặc định của sản phẩm hiện tại. Đây là hướng mở rộng đã được thiết kế để phục vụ bài toán cộng tác nội bộ:

```text
Company Root
├── Product Delivery Workspace → Product Delivery Agent
├── Quality Assurance Workspace → Quality Assurance Agent
└── Executive Workspace → Executive Agent
                                      └── tổng hợp brief hợp lệ
```

Khi triển khai giai đoạn này, Personal Agent vẫn được giữ nguyên cho dữ liệu cá nhân. Các Workspace Agent sẽ có scope, membership và tool riêng; Executive Agent chỉ tổng hợp `WorkspaceBrief` đã được kiểm chứng, không đọc raw chat liên phòng ban. Foundation và thiết kế chi tiết nằm trong thư mục [`docs/`](docs/), nhưng các feature flag Multi-Agent hiện mặc định tắt.

## Hiện có gì

### Đã hoạt động thật (có backend, có database)

- **Đăng ký / Đăng nhập / Đăng xuất**: tài khoản lưu trong PostgreSQL, mật khẩu hash bằng bcrypt, xác thực bằng JWT. Các route protected (`/assistant`, `/chat`, `/tasks`, ...) yêu cầu đăng nhập.
- **Đăng nhập bằng Google**: User app có nút Sign in with Google ở `/login` và `/register`. Backend xác minh Google ID token và lưu liên kết trong bảng `google_identities`; không cần client secret cho flow này.
- **Nhắn tin 1-1 và theo nhóm, real-time**: tạo conversation, gửi/nhận qua WebSocket, xem lịch sử và đếm tin chưa đọc. Chat hỗ trợ emoji, file đính kèm tối đa 5 file, mỗi file tối đa 3 MB, cùng giao diện responsive cho điện thoại.
- **Personal AI Agent**: `/api/v1/chat` chạy LangGraph planner với các tool cá nhân; `/assistant` là giao diện chat riêng có lưu danh sách thread và resume sau restart.
- **Tóm tắt và trích xuất task**: trong AI panel của conversation, Summarize và Extract tasks đọc context đã được kiểm tra consent; task suggestion được xác nhận bằng Accept/Dismiss.
- **Task, Inbox và Reminder**: CRUD task thật, `/tasks/inbox` gom task cần quyết định/quá hạn/sắp đến hạn/ưu tiên cao; reminder lưu DB, có scheduler và thông báo realtime.
- **Google Calendar per-user**: mỗi user tự kết nối Google Calendar của mình bằng OAuth; token được mã hóa trước khi lưu. Tạo/sửa/xóa event từ AI luôn yêu cầu human-in-the-loop.
- **Memory và agent chủ động**: user quản lý memory cá nhân; agent có thể phát hiện cam kết trong chat để tạo task suggestion, nhưng không tự tạo side effect Calendar/Reminder khi chưa được xác nhận.
- **Phân quyền Admin tách biệt**: Admin app chạy riêng ở cổng 5174, dùng `platform_role`; platform admin quản lý tài khoản, cấu hình AI, usage và audit.
- **Cảnh báo và giới hạn AI**: theo dõi usage theo ngày, cảnh báo khi gần hạn mức và chặn lượt gọi AI mới khi vượt ngân sách; lượt xác nhận đang chờ vẫn được hoàn tất.
- **Múi giờ thống nhất Asia/Ho_Chi_Minh**: frontend, scheduler và các mốc thống kê dùng giờ Hà Nội.

### Công cụ phát triển

- `alembic upgrade head` — nâng cấp schema database theo migration hiện tại.
- `pytest tests/` — test backend và policy; `ruff check src/ tests/` — lint backend; `npm run build` — build hai frontend.
- `scripts/seed_multi_agent_demo.py` — dữ liệu synthetic phục vụ thử nghiệm hướng Multi-Agent tương lai, không cần cho flow Personal Agent thông thường.

### Chưa xong

- **Deploy online public**: đã có Docker, Render/Vercel và workflow nhưng chưa xác nhận domain production trong source code.
- **Mở rộng Multi-Agent**: hiện là roadmap sau MVP. Repo đã có foundation/thiết kế thử nghiệm cho Company Root, Agent Workspace, Delivery/QA/Executive profile, scope guard và `WorkspaceBrief`, nhưng chưa phải trải nghiệm mặc định cho người dùng.
- **Nghiệp vụ chuyên môn mở rộng**: milestone, dependency và các nguồn dữ liệu phòng ban cần được bổ sung dần bằng resource thật; khi thiếu nguồn, hệ thống phải báo data gap thay vì tự suy đoán.

## Kiến trúc

> **Backend** nằm trong [`src/`](src/) và có một FastAPI process dùng chung cho REST, WebSocket, Personal Agent và scheduler. Hai frontend là [`Frontend/user/`](Frontend/user/) và [`Frontend/admin/`](Frontend/admin/).

```text
├── src/
│   ├── agents/
│   │   ├── graph.py            # LangGraph Personal Agent và checkpoint
│   │   ├── nodes/              # planner, guardrail, context và compaction
│   │   ├── tools/              # personal tools; foundation specialist ở các module riêng
│   │   ├── contracts.py        # contract chung cho agent và hướng mở rộng
│   │   ├── router.py           # router/scope foundation cho Multi-Agent tương lai
│   │   └── policies/           # authorization và resource guard
│   ├── api/                    # auth, chat, task, calendar, admin và workspace routes
│   ├── db/                     # SQLAlchemy models, session và Alembic migrations
│   ├── models/                 # Pydantic request/response schemas
│   ├── services/               # chat, memory, calendar, reminder, scheduler và workspace
│   └── websocket/              # kênh realtime
├── tests/                      # backend, authorization và HITL tests
└── Frontend/
    ├── user/                   # User app, cổng 5173
    ├── admin/                  # Admin app, cổng 5174
    └── src/                    # component/style dùng chung và compatibility surfaces
```

### Flow hiện tại và hướng mở rộng

```text
Hiện tại
  user → auth/consent → Personal Agent LangGraph → personal tools → câu trả lời/HITL

Sau MVP
  user + workspace membership → deterministic router → Delivery/QA Agent
  Executive membership → validated WorkspaceBrief → Executive Agent
```

Trong giai đoạn hiện tại, `requested_scope=personal` là mặc định. `requested_scope=workspace|aggregate` chỉ dành cho prototype và giai đoạn mở rộng sau MVP; quyền thật không đến từ field client tự khai mà được backend resolve từ membership, resource binding và policy.

## Cách chạy web (local development)

Cần chạy backend ở cổng 8000 và ít nhất User frontend ở cổng 5173. Admin frontend ở cổng 5174 chỉ cần chạy khi quản lý hệ thống.

### 1. Chuẩn bị

- Python 3.11+
- Node.js 18+ và npm
- PostgreSQL cho runtime chính; SQLite chỉ nên dùng cho unit test/compatibility.
- Đã clone repo và `cd` vào thư mục gốc dự án.

### 2. Chạy Backend

```bash
# Tạo virtual environment một lần
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt

# Tạo cấu hình local
cp .env.example .env
# PowerShell có thể dùng: Copy-Item .env.example .env
```

Trong `.env`, điền `DATABASE_URL` tới PostgreSQL và một provider LLM (`GOOGLE_API_KEY`, hoặc Groq/OpenAI tương ứng). Các flag Multi-Agent giữ nguyên `false` nếu chỉ chạy sản phẩm Personal Agent:

```dotenv
MULTI_AGENT_ENABLED=false
PRODUCT_DELIVERY_AGENT_ENABLED=false
QUALITY_ASSURANCE_AGENT_ENABLED=false
EXECUTIVE_AGENT_ENABLED=false
```

```bash
# Windows PowerShell: dùng launcher để chọn SelectorEventLoop cho async checkpointer
python scripts/run_dev.py

# macOS/Linux
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Kiểm tra backend: `http://localhost:8000/health`. Swagger UI: `http://localhost:8000/docs`.

### 3. Chạy hai Frontend

```bash
cd Frontend
npm install
npm run dev:user

# Terminal khác nếu cần Admin app
npm run dev:admin
```

Mở `http://localhost:5173` cho User app và `http://localhost:5174` cho Admin app. Cấu hình frontend nằm ở `Frontend/user/.env` và `Frontend/admin/.env`, tạo từ `.env.example` tương ứng.

### 4. Dùng thử

1. Vào `http://localhost:5173/register`, tạo tài khoản user.
2. Mở một tab ẩn danh khác để tạo tài khoản thứ hai và thử chat 1-1/nhóm.
3. Trong `/chat`, mở AI panel để thử Summarize, Extract tasks, Find schedule hoặc Ask Orbit.
4. Vào `/assistant` để chat trực tiếp với Personal Agent; tạo/sửa/xóa Calendar hoặc Reminder sẽ dừng lại chờ xác nhận.
5. Mở `http://localhost:5174/register`, dùng `ADMIN_BOOTSTRAP_KEY` để tạo platform admin đầu tiên, rồi đăng nhập tại `/login` của Admin app.
6. Vào `/tasks/inbox` để xem task suggestion, task quá hạn và task sắp đến hạn.
7. Vào `/calendar` để kết nối Google Calendar per-user nếu đã cấu hình OAuth.
8. Các trang `/workspaces` và `/workspace-briefs` thuộc hướng Multi-Agent mở rộng; chỉ dùng khi team đã provision workspace và bật đúng feature flags.

### 5. Test Calendar cùng nhiều thành viên

Calendar là per-user: mỗi thành viên tự kết nối Google Calendar của mình, nhưng nhóm có thể dùng chung một OAuth client. Không chia sẻ `CLIENT_SECRET` qua Git hoặc commit vào `.env`.

1. Tạo Google Cloud OAuth client cho Calendar và thêm email test users.
2. Gửi `GOOGLE_CALENDAR_CLIENT_ID`/`SECRET` qua kênh riêng tư.
3. Mỗi thành viên chạy backend/frontend local với PostgreSQL và `CREDENTIAL_ENCRYPTION_KEY` riêng.
4. Mỗi người đăng nhập User app, vào `/calendar` và connect đúng Google account của mình.

### Chạy test backend

```bash
pytest tests/ -v
# hoặc: make test
```

Test integration dùng PostgreSQL riêng qua `TEST_DATABASE_URL` khi cần. Unit test có thể dùng SQLite in-memory/MemorySaver.

### Chạy database migration

```bash
alembic upgrade head
```

Luôn backup database và kiểm tra migration trên staging trước khi nâng cấp production. Dockerfile production cũng chạy migration trước khi khởi động Uvicorn.

### Lint và build kiểm tra

```bash
ruff check src/ tests/

cd Frontend
npm run build
```

### Chạy backend bằng Docker

```bash
docker compose up --build
```

Docker Compose chạy backend ở cổng 8000; frontend chạy riêng bằng npm.

## Công nghệ sử dụng

| Layer | Công nghệ |
| --- | --- |
| Personal Agent hiện tại | LangGraph + LangChain, tool calling, PostgreSQL checkpointer |
| Backend | FastAPI, Pydantic 2, SQLAlchemy async, PostgreSQL, JWT, bcrypt, WebSocket |
| Frontend | React 18, Vite, React Router, Bootstrap 5, Framer Motion |
| Calendar / Scheduler | Google Calendar API, APScheduler |
| Migration | Alembic |
| Test / Lint | pytest, pytest-asyncio, httpx, ruff |
| Multi-Agent sau MVP | Agent Workspace, deterministic router, scope/resource guard, WorkspaceBrief và Executive aggregation |

## Tài liệu định hướng Multi-Agent

- [docs/README.md](docs/README.md) — mục lục và quy tắc single source of truth.
- [docs/BRIEF.md](docs/BRIEF.md) — hướng mở rộng sản phẩm theo Workspace.
- [docs/PRD.md](docs/PRD.md) — yêu cầu và acceptance criteria cho giai đoạn mở rộng.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — data boundary, router, agent runtime và security.
- [docs/AGENT_SYSTEM_DESIGN.md](docs/AGENT_SYSTEM_DESIGN.md) — prompt, tool, guardrail, memory và HITL của Personal/Multi-Agent.
- [docs/ENTERPRISE_WORKSPACE_FOUNDATION.md](docs/ENTERPRISE_WORKSPACE_FOUNDATION.md) — Company Root, Workspace, role và membership.
- [docs/MULTI_AGENT_IMPLEMENTATION_PLAN.md](docs/MULTI_AGENT_IMPLEMENTATION_PLAN.md) — kế hoạch phát triển sau MVP.
- [docs/MULTI_AGENT_TEST_DATASET.md](docs/MULTI_AGENT_TEST_DATASET.md) — dataset thử nghiệm hướng Multi-Agent.

## Tài liệu khác

- [CLAUDE.md](CLAUDE.md) — hướng dẫn cho AI coding assistant.
- [Frontend/README.md](Frontend/README.md) — cấu trúc và cách chạy hai frontend.
- [Frontend/detai.md](Frontend/detai.md) — đề bài gốc của dự án.
- [ARCHITECTURE.md](ARCHITECTURE.md) — kiến trúc runtime tương thích và con trỏ tới tài liệu canonical.
- [ROADMAP.md](ROADMAP.md) — trạng thái yêu cầu và việc còn lại.
- [DEPLOYMENT.md](DEPLOYMENT.md) — kế hoạch hạ tầng production.
- [docs/deploy.md](docs/deploy.md) — hướng dẫn triển khai dashboard từng bước.
- [WORKLOG.md](WORKLOG.md) — nhật ký thay đổi theo ngày của cả nhóm.
