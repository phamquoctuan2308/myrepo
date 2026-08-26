# P-132 — Orbit AI Assistant

Dự án AI20K Build Phase: một AI agent nhúng trong ứng dụng chat, giúp tóm tắt hội thoại, trích xuất công việc/lịch hẹn, tạo nhắc nhở (có xác nhận trước khi thực hiện) và quản lý lịch cá nhân. Repo gồm 2 phần: **backend** (FastAPI + LangGraph, thư mục `src/`) và **frontend** (React + Vite, thư mục `Frontend/`).

## Mô hình sản phẩm

Orbit dùng hai loại tài khoản: người dùng và `platform_admin`. Task, Memory, Reminder và Calendar
thuộc trực tiếp về từng người dùng. Hội thoại chỉ có thể được đọc bởi participant đang hoạt động;
platform admin không có đường API đọc nội dung tin nhắn gốc.

## Hiện có gì

### Đã hoạt động thật (có backend, có database)

- **Đăng ký / Đăng nhập / Đăng xuất**: tài khoản lưu thật trong database PostgreSQL, mật khẩu hash bằng bcrypt, xác thực bằng JWT. Route bên trong ứng dụng (`/assistant`, `/chat`, `/tasks`, ...) được bảo vệ — chưa đăng nhập sẽ tự chuyển về `/login`.
- **Đăng nhập bằng Google**: nút "Sign in with Google" trên `/login` và `/register` (cùng 1 nút xử lý cả đăng nhập lẫn đăng ký lần đầu). Backend xác minh ID token của Google (`src/auth/google_oauth.py`), không cần client secret. Tài khoản Google được lưu trong bảng `google_identities` riêng (không đụng bảng `users`/mật khẩu hiện có); nếu email trùng tài khoản mật khẩu có sẵn thì tự liên kết — nhưng chỉ khi Google xác nhận `email_verified`. Cần tự tạo Google OAuth Client ID (xem mục "Cách chạy web" bước 2) mới bật được nút này.
- **Agent nhớ hội thoại bền vững qua PostgreSQL**: agent dùng `AsyncPostgresSaver` — hội thoại/interrupt sống sót qua restart backend. Trên Windows, bắt buộc chạy bằng `python scripts/run_dev.py` thay vì `uvicorn` CLI trực tiếp — xem mục "Cách chạy web" bên dưới.
- **Nhắn tin 1-1 và theo nhóm, real-time**: tạo cuộc trò chuyện 1-1 hoặc nhóm (chọn nhiều người), gửi/nhận tin nhắn tức thời qua WebSocket, xem lại lịch sử tin nhắn, đếm tin nhắn chưa đọc.
- **AI Agent (chat với AI)**: endpoint `/api/v1/chat` (yêu cầu đăng nhập) dùng LangGraph, có tool gọi Google Calendar và tạo nhắc nhở với bước xác nhận (human-in-the-loop) trước khi thực hiện. Hỗ trợ 3 provider LLM (Google Gemini, Groq, hoặc OpenAI — đổi qua `LLM_PROVIDER` trong `.env`) để dễ chuyển khi một bên hết quota.
- **AI Assistant cá nhân** (`/assistant`): khung chat riêng nối thẳng vào agent thật ở trên (không phải dữ liệu mẫu) — hỏi tự do, khi agent muốn tạo lịch/nhắc việc sẽ hiện nút Xác nhận/Huỷ ngay trong chat.
- **Phân quyền Admin tách biệt**: quyền nền tảng dùng `platform_role`. Platform admin quản lý tài khoản, cấu hình AI, thống kê usage và audit log; không có API đọc/quản lý hội thoại, Task, Memory hay Reminder của người dùng.
- **Cảnh báo + tự chặn khi vượt hạn mức token/chi phí**: khi lượng dùng vượt ngưỡng cấu hình, platform admin đang online nhận cảnh báo realtime; các lượt gọi LLM mới bị chặn khi hết ngân sách nhưng lượt xác nhận đang chờ vẫn được hoàn tất.
- **Tóm tắt hội thoại theo yêu cầu**: trong trang Chat, bấm icon AI trên header → **Summarize** — AI đọc tin nhắn thật (theo scope 20/50 tin gần nhất đang chọn) và trả về bản tóm tắt.
- **Trích xuất Task từ hội thoại**: cùng panel AI → **Extract tasks** — AI tìm việc cần làm/lịch hẹn trong hội thoại, lưu vào trang `/tasks` mục "AI suggestions"; người dùng bấm **Accept**/**Dismiss** để xác nhận. Panel AI còn có **Find schedule**, **Deadlines**, **Suggest reminder** (hiện nút Xác nhận/Huỷ ngay trong panel vì tạo reminder cần human-in-the-loop), cùng ô **Ask Orbit** để hỏi tự do về hội thoại đang xem.
- **Task Inbox ưu tiên** (`/tasks/inbox`): gom gợi ý AI cần quyết định, task quá hạn, sắp đến hạn và task ưu tiên cao thành các nhóm dễ xử lý.
- **Google Calendar riêng theo người dùng, đồng bộ 2 chiều, realtime**: mỗi người kết nối tài khoản Google của mình bằng OAuth; refresh token được mã hóa trong database. Sự kiện WebSocket chỉ gửi cho chủ lịch. Candidate rút ra từ chat nhóm vẫn cần manager xác nhận, rồi được ghi vào lịch của chính manager đó. Thay đổi từ Google được bắt bằng incremental sync token và polling (`CALENDAR_POLL_INTERVAL_SECONDS`).
- **Nhắc nhở bền vững + realtime**: trang `/reminders` tạo nhắc nhở thật, lưu DB, sống sót qua restart server (APScheduler + `SQLAlchemyJobStore`); khi đến giờ, đẩy thông báo realtime qua WebSocket dù đang ở trang nào.
- **Hồ sơ cá nhân** (`/profile`): sửa tên/chức danh/timezone/tuỳ chọn thông báo và đổi mật khẩu — lưu thật vào database, không còn là dữ liệu mẫu.
- **Memory có phạm vi rõ ràng** (`/memory`): thêm/sửa/xoá "điều Orbit nên nhớ về bạn". Agent chỉ tìm kiếm memory và task thuộc đúng user của lượt chat hiện tại.
- **Agent chủ động (proactive), realtime**: mỗi tin nhắn mới trong Chat được rà tự động (pre-filter rẻ + LLM xác nhận) — nếu chứa cam kết/lịch hẹn/hạn chót, Orbit tự tạo gợi ý và đẩy thẳng vào `/tasks` mục "AI suggestions" qua WebSocket (không cần refresh) kèm toast, không cần người dùng chủ động yêu cầu. Toàn bộ thao tác Task (accept/dismiss/complete/xoá) cũng đồng bộ realtime giữa các tab/thiết bị.
- **Múi giờ thống nhất Asia/Ho_Chi_Minh (Hà Nội)**: mọi nơi hiển thị ngày giờ đều quy về giờ Hà Nội qua utility riêng của `Frontend/user` và `Frontend/admin`. Backend cũng cố định giờ Hà Nội cho scheduler và mốc "hôm nay" của thống kê token.

### Công cụ đánh giá (dev, không phải tính năng người dùng)

- `scripts/eval_extract_tasks.py` — đo Precision/Recall/F1 của việc trích xuất **tiêu đề** task, và riêng **độ chính xác ngày giờ** (`due_at` có resolve đúng "ngày mai"/"thứ Sáu này" theo ngày chạy thật không — hai thứ này lệch pha nhau: tiêu đề đúng không có nghĩa ngày đúng) trên bộ dữ liệu tay (8 case tiếng Việt + Anh, có cả case không có task để đo độ chính xác). Gọi LLM thật nên không nằm trong `pytest tests/` — chạy tay: `python scripts/eval_extract_tasks.py`. Kết quả gần nhất (model `gpt-4o-mini` qua OpenAI): **Title F1 = 100%, Date accuracy = 100%** (8/8 case, 7/7 case có ngày).

### Chưa xong

- **Deploy online**: có `Dockerfile`/`docker-compose.yml` nhưng chưa deploy lên domain public.

## Kiến trúc

> **Backend nằm ở thư mục [`src/`](src/) ở gốc repo** (FastAPI + LangGraph), tách biệt hoàn toàn với hai frontend ở [`Frontend/user/`](Frontend/user/) và [`Frontend/admin/`](Frontend/admin/) (React + Vite). Trên Windows, chạy backend bằng `python scripts/run_dev.py` từ thư mục gốc repo.

```
├── src/                  # Backend — FastAPI + LangGraph
│   ├── agents/           # Agent LangGraph (planner, tools, state)
│   ├── api/               # REST routes: auth, chat (người-với-người), agent chat
│   ├── auth/              # Hash mật khẩu, tạo/kiểm tra JWT
│   ├── db/                # SQLAlchemy models + session (PostgreSQL)
│   ├── models/             # Pydantic schemas
│   ├── services/           # chat_service, scheduler, llm, usage_service
│   ├── websocket/          # Kênh real-time cho chat
│   └── main.py             # Điểm khởi tạo FastAPI app
├── tests/                 # pytest cho backend
└── Frontend/               # npm workspace: user app (5173) + admin app (5174)
    └── src/
        ├── api/            # Gọi REST API + WebSocket client
        ├── context/         # AuthContext (JWT, user hiện tại)
        ├── hooks/            # useConversations, useMessages
        ├── components/        # Component theo tính năng (chat, layout, ...)
        ├── pages/              # Các trang ứng dụng
        └── router/              # React Router + ProtectedRoute
```

## Cách chạy web (local development)

Cần chạy backend (cổng 8000) và ít nhất một frontend. User app chạy ở cổng 5173; Admin app độc lập chạy ở cổng 5174.

### 1. Chuẩn bị

- Python 3.11+
- Node.js 18+ và npm
- PostgreSQL đang chạy (local hoặc Docker) — bắt buộc, dự án không còn hỗ trợ SQLite. Tạo sẵn 1
  database (ví dụ `orbit`), sẽ dùng địa chỉ này cho `DATABASE_URL` ở bước 2.
- Đã clone repo và `cd` vào thư mục gốc dự án

### 2. Chạy Backend

```bash
# Tạo virtual environment (chỉ cần làm 1 lần)
python -m venv .venv

# Kích hoạt venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# Cài dependency
pip install -r requirements.txt

# Tạo file cấu hình (chỉ cần làm 1 lần)
cp .env.example .env
# Mở .env, điền GOOGLE_API_KEY (lấy tại https://aistudio.google.com/apikey) nếu muốn dùng tính năng AI chat (tóm tắt, calendar, nhắc nhở).
#   Nếu tài khoản Google chưa có quota free-tier (lỗi 429/quota=0 khi gọi), đổi provider:
#   - Groq: LLM_PROVIDER=groq, GROQ_API_KEY (lấy tại https://console.groq.com/keys), MODEL_NAME=openai/gpt-oss-20b.
#   - OpenAI: LLM_PROVIDER=openai, OPENAI_API_KEY (lấy tại https://platform.openai.com/api-keys), MODEL_NAME=gpt-4o-mini.
# Sửa DATABASE_URL trỏ vào database Postgres đã tạo ở bước 1 (postgresql://user:pass@host:5432/dbname) — bắt buộc, không có giá trị mặc định.
# Điền ADMIN_BOOTSTRAP_KEY để tạo admin đầu tiên tại http://localhost:5174/register.
# Đăng ký ở User frontend luôn tạo tài khoản thường; không còn tự cấp role admin.
# Muốn bật nút "Đăng nhập bằng Google": tạo 1 OAuth Client ID loại "Web application" tại
#   https://console.cloud.google.com/apis/credentials, Authorized JavaScript origins:
#   http://localhost:5173. Điền Client ID vào GOOGLE_OAUTH_CLIENT_ID ở đây, và giá trị y hệt vào
#   VITE_GOOGLE_CLIENT_ID trong Frontend/user/.env (bước 3) — không điền thì nút Google bị vô hiệu
#   động, các tính năng khác không ảnh hưởng.
# Muốn bật nút "Connect Google Calendar" (mỗi user tự nối Calendar riêng của họ):
#   1. Bật "Google Calendar API" tại https://console.cloud.google.com — APIs & Services → Library.
#   2. OAuth consent screen: thêm scope https://www.googleapis.com/auth/calendar, thêm email từng
#      người sẽ test vào "Test users" (scope nhạy cảm nên app ở chế độ Testing, tối đa 100 test
#      user, ai không có trong danh sách sẽ gặp lỗi access_denied).
#   3. Credentials → Create Credentials → OAuth client ID → Web application (KHÁC client đăng nhập
#      ở trên — client này cần đổi authorization code lấy refresh token nên phải có Client Secret).
#   4. Authorized redirect URIs: thêm ĐÚNG http://localhost:8000/api/v1/calendar/oauth/callback
#      (đây là redirect thật, không phải popup — phải khớp từng ký tự với GOOGLE_CALENDAR_REDIRECT_URI).
# Điền GOOGLE_CALENDAR_CLIENT_ID + GOOGLE_CALENDAR_CLIENT_SECRET ở đây — không cần điền gì ở
#   Frontend/user/.env.local (khác với nút đăng nhập ở trên, nút Connect Calendar không cần biến VITE_* nào,
#   toàn bộ OAuth chạy ở backend). Cũng cần CREDENTIAL_ENCRYPTION_KEY (mã hoá refresh token trước
#   khi lưu DB) — sinh 1 lần bằng:
#     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#   Không điền GOOGLE_CALENDAR_CLIENT_ID/SECRET thì nút Connect vẫn hiện nhưng bấm vào báo lỗi rõ
#   ràng thay vì mở được màn hình Google; các tính năng khác không ảnh hưởng.

# Chạy backend
# Windows PowerShell (bắt buộc dùng launcher này để chọn SelectorEventLoop):
python scripts/run_dev.py

# macOS/Linux:
# uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Nếu có `make` (macOS/Linux, hoặc cài Make trên Windows), có thể dùng `make run`.

**Windows**: luôn dùng `python scripts/run_dev.py` thay cho lệnh `uvicorn` ở trên (cùng `--reload`, cùng cổng 8000) — không phải tuỳ chọn. Lý do: agent memory bền vững (`AsyncPostgresSaver`) cần `SelectorEventLoop`, nhưng CLI `uvicorn` trên Windows luôn chọn `ProactorEventLoop` trước cả khi app được import, không có cờ nào sửa được — `run_dev.py` gọi `uvicorn.run()` trực tiếp bằng Python để chỉ định đúng loại event loop.

Kiểm tra backend đã chạy: mở `http://localhost:8000/health` phải trả về `{"status":"ok",...}`. Swagger UI (danh sách toàn bộ API) ở `http://localhost:8000/docs`.

### 3. Chạy hai Frontend

Frontend đã tách thành hai app độc lập:

```bash
cd Frontend
npm install
npm run dev:user
# Terminal khác, nếu cần giao diện quản trị:
npm run dev:admin
```

Mở `http://localhost:5173` cho ứng dụng người dùng và `http://localhost:5174` cho Admin. Cấu hình local nằm riêng trong `Frontend/user/.env` và `Frontend/admin/.env`, tạo từ file `.env.example` tương ứng.

### 4. Dùng thử

1. Vào `http://localhost:5173/register`, tạo tài khoản.
2. Mở thêm một trình duyệt/tab ẩn danh khác, tạo tài khoản thứ hai.
3. Từ tài khoản thứ nhất, vào trang **Chats**, bấm nút bút (soạn tin nhắn) để chọn người và bắt đầu chat 1-1 hoặc chọn nhiều người để tạo nhóm.
4. Gửi tin nhắn — tài khoản còn lại sẽ nhận tin nhắn theo thời gian thực nếu đang mở cùng cuộc trò chuyện, hoặc thấy số tin nhắn chưa đọc.
5. Muốn thử **Admin**: đăng ký tài khoản có email trùng `INITIAL_ADMIN_EMAIL`, sau đó đăng nhập ứng dụng Admin tại `http://localhost:5174/login`. Backend vẫn là lớp bắt buộc kiểm tra `platform_role`.
6. Muốn thử **AI Summarize / Extract tasks / Find schedule / Deadlines / Ask Orbit**: cần điền `GOOGLE_API_KEY` (hoặc Groq, xem bước 2) thật trong `.env`. Trong 1 cuộc trò chuyện có vài tin nhắn, bấm icon AI trên header (⭐) rồi thử từng quick action, hoặc gõ câu hỏi tự do vào ô "Ask Orbit".
7. Muốn thử **AI Assistant cá nhân** (`/assistant`): vào trang này và chat trực tiếp — nếu bạn yêu cầu tạo lịch/nhắc việc, agent sẽ hỏi lại xác nhận ngay trong khung chat trước khi tạo thật.
8. Muốn xem **theo dõi token AI**: vào `/admin` (cần tài khoản admin, xem bước 5) — 2 stat card "AI tokens used today"/"AI requests today" và banner cảnh báo khi dùng ≥80% ngân sách `DAILY_TOKEN_BUDGET`. Hạ tạm `DAILY_TOKEN_BUDGET` (ví dụ `=50`) trong `.env` rồi restart backend nếu muốn thấy toast cảnh báo realtime (`usage_budget_alert` qua WebSocket) xuất hiện ngay khi đang ở bất kỳ trang nào, không cần mở `/admin` — và xác nhận `/chat` bị chặn hẳn (không chỉ cảnh báo) một khi đã vượt hẳn ngân sách.
9. Muốn thử **Agent chủ động**: gửi 1 tin nhắn kiểu "nhớ họp lúc 3h chiều mai nhé" trong trang Chat — vài giây sau sẽ có toast "Orbit spotted a commitment" ở góc phải, và gợi ý xuất hiện trong `/tasks` mục "AI suggestions".
10. Muốn thử **Memory**: vào `/memory`, bấm "Add memory" để lưu một điều bạn muốn Orbit nhớ, sửa/xoá qua menu 3 chấm trên mỗi thẻ.
11. Muốn thử **Task Inbox ưu tiên**: vào `/tasks/inbox` (hoặc mục "Inbox" trong Sidebar) — task quá hạn/sắp đến hạn/priority cao/cần quyết định được nhóm riêng khỏi danh sách task đầy đủ ở `/tasks`.
12. Muốn thử **Đăng nhập bằng Google**: cần đã điền `GOOGLE_OAUTH_CLIENT_ID`/`VITE_GOOGLE_CLIENT_ID` thật (xem bước 2, 3). Vào `/login` hoặc `/register` của User frontend, bấm nút Google — lần đầu sẽ tạo tài khoản thường; admin đầu tiên phải tạo qua màn hình bootstrap của Admin.
13. Muốn thử **Calendar (per-user)**: cần đã điền `GOOGLE_CALENDAR_CLIENT_ID`/`GOOGLE_CALENDAR_CLIENT_SECRET`/`GOOGLE_CALENDAR_REDIRECT_URI`/`CREDENTIAL_ENCRYPTION_KEY` thật (xem bước 2 — client riêng, khác client đăng nhập, cần Authorized redirect URI khớp chính xác). Vào `/calendar`, bấm **Connect Google Calendar** (mở popup thật tới Google, không phải giả lập), chọn tài khoản Google, đồng ý quyền truy cập — popup tự đóng, sau đó xem/tạo/sửa/xoá sự kiện thật trên đúng Calendar của tài khoản Google vừa chọn. Đăng nhập bằng 2 tài khoản khác nhau và tự Connect 2 Google account khác nhau ở mỗi bên để thấy rõ mỗi người có Calendar riêng, không dùng chung — tạo sự kiện bên A không hiện bên B.

### 5. Test Calendar cùng nhiều thành viên trong nhóm

Calendar là tính năng **per-user** (mỗi người tự connect đúng Google Calendar của mình), nhưng cả nhóm **dùng chung 1 OAuth Client** (`GOOGLE_CALENDAR_CLIENT_ID`/`SECRET`) — không cần ai tạo Google Cloud project riêng, và không cần deploy online mới test được.

1. **Một người trong nhóm** tạo Google Cloud project + OAuth Client theo đúng hướng dẫn ở bước 2 (mục "Connect Google Calendar"). Ở phần OAuth consent screen ("Audience" trong Console bản mới) → **Test users**, add **email Gmail của tất cả thành viên sẽ test** (tối đa 100, app đang ở chế độ Testing) — không phải chỉ email của người tạo.
2. Người đó gửi `GOOGLE_CALENDAR_CLIENT_ID` + `GOOGLE_CALENDAR_CLIENT_SECRET` cho cả nhóm qua kênh riêng tư (chat nhóm) — **không** đưa lên GitHub/PR, không commit vào `.env`.
3. Mỗi thành viên còn lại `git pull` rồi tự chạy backend + frontend trên máy mình như bước 1-3 ở trên, với:
   - `DATABASE_URL` trỏ vào **database Postgres riêng trên máy họ** (không dùng chung DB với người khác — mỗi người có dữ liệu độc lập, kể cả token Calendar đã mã hoá).
   - `GOOGLE_CALENDAR_CLIENT_ID`/`GOOGLE_CALENDAR_CLIENT_SECRET` = giá trị nhận ở bước 2 (dùng chung cho cả nhóm).
   - `GOOGLE_CALENDAR_REDIRECT_URI` giữ nguyên mặc định `http://localhost:8000/api/v1/calendar/oauth/callback` — ai cũng chạy backend ở `localhost:8000` trên máy mình nên không cần đổi.
   - `CREDENTIAL_ENCRYPTION_KEY` **tự sinh riêng** cho máy mình (không cần trùng với người khác, vì mỗi người có DB riêng ở trên).
4. Mỗi người tự đăng ký 1 tài khoản Orbit riêng (bước 4.1), vào `/calendar` → **Connect Google Calendar** → chọn đúng Gmail đã được add làm Test user ở bước 1.

Lỗi thường gặp khi test theo nhóm:
- Bấm Connect ra lỗi `access_denied` ngay ở màn hình Google → email dùng để đăng nhập Google **không nằm trong Test users** (quay lại bước 1, add thêm).
- Backend báo lỗi ngay khi bấm Connect, không mở được popup Google → quên điền hoặc quên **restart backend** sau khi sửa `GOOGLE_CALENDAR_CLIENT_ID`/`SECRET` trong `.env`.
- Popup Google đóng lại nhưng báo "Could not connect Google Calendar." → xem log ở terminal đang chạy `python scripts/run_dev.py` ngay lúc đó để biết lý do cụ thể (thường in kèm traceback ở dòng `Failed to exchange the authorization code`).

### Chạy test backend

Unit test dùng SQLite in-memory và `MemorySaver`, không đụng tới database dev. Các integration test
checkpoint PostgreSQL chỉ chạy khi có `TEST_DATABASE_URL`; nếu muốn chạy chúng, tạo database riêng
và đặt biến môi trường đó trước khi gọi pytest.

```bash
pytest tests/ -v
# hoặc: make test
```

### Chạy database migration

Sao lưu database trước khi nâng cấp, sau đó chạy:

```bash
alembic upgrade head
```

Revision `20260813_08` loại bỏ schema phân vùng cũ nhưng giữ nguyên hội thoại, tin nhắn và dữ liệu cá nhân của các tài khoản đã đăng ký.

### Checklist chạy production

Production không tự gọi `create_all`; schema phải được nâng cấp có kiểm soát trước khi khởi động app:

```bash
alembic upgrade head
```

Đặt `APP_ENV=production`, dùng PostgreSQL, tạo `SECRET_KEY` ngẫu nhiên tối thiểu 32 byte, khai báo chính xác `CORS_ORIGINS` và API key tương ứng `LLM_PROVIDER`. Ứng dụng sẽ từ chối khởi động nếu còn SQLite, secret mẫu, CORS wildcard hoặc thiếu LLM credential trong production. Luôn sao lưu database và chạy migration trên staging trước.

### Lint và build kiểm tra

```bash
# Từ thư mục gốc
ruff check src/ tests/

# Frontend production build
cd Frontend
npm run build
```

### Chạy backend bằng Docker

```bash
docker compose up --build
```

Docker Compose hiện chỉ chạy backend tại cổng `8000`; frontend chạy riêng bằng `npm run dev`.

## Công nghệ sử dụng

| Layer | Công nghệ |
| --- | --- |
| AI Agent | LangGraph + LangChain (Google Gemini, Groq hoặc OpenAI, đổi qua `LLM_PROVIDER`) |
| Backend | FastAPI, Pydantic 2, SQLAlchemy 2 async + PostgreSQL, JWT (PyJWT) + bcrypt, WebSocket |
| Migration | Alembic (schema hiện tại dùng user ownership và conversation participants) |
| Agent memory | `AsyncPostgresSaver` trong development/production; `MemorySaver` cô lập trong unit test |
| Frontend | React 18, Vite, React Router, React Hook Form, Bootstrap 5, Framer Motion |
| Calendar / Scheduler | Google Calendar API clients, APScheduler |
| Test | pytest, pytest-asyncio, httpx |
| Lint | ruff |

## Tài liệu thiết kế

- [docs/README.md](docs/README.md) — mục lục và quy tắc single source of truth cho cả team.
- [docs/BRIEF.md](docs/BRIEF.md) — ý tưởng, giá trị và phạm vi sản phẩm.
- [docs/PRD.md](docs/PRD.md) — nghiệp vụ, yêu cầu và acceptance criteria.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — kiến trúc, data boundary, agent runtime và security.

## Tài liệu khác

- [CLAUDE.md](CLAUDE.md) — hướng dẫn chi tiết cho AI coding assistant làm việc trong repo này (quy ước code, lệnh chạy đầy đủ).
- [Frontend/README.md](Frontend/README.md) — hướng dẫn riêng cho frontend (cấu trúc, xử lý lỗi thường gặp khi chạy npm trên Windows).
- [Frontend/detai.md](Frontend/detai.md) — đề bài / yêu cầu gốc của dự án.
- [ARCHITECTURE.md](ARCHITECTURE.md) — con trỏ tương thích đến kiến trúc canonical trong `docs/`.
- [ROADMAP.md](ROADMAP.md) — bảng đối chiếu từng yêu cầu đề bài với trạng thái thật hiện tại + việc còn lại theo độ ưu tiên.
- [docs/deploy.md](docs/deploy.md) — hướng dẫn deploy production (Render + Supabase + Vercel + CD qua GitHub Actions), từng bước dashboard theo đúng thứ tự + checklist verify end-to-end.
- [WORKLOG.md](WORKLOG.md) — nhật ký công việc theo ngày của cả nhóm.
