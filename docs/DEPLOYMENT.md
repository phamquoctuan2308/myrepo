# Triển khai Orbit

## 1. Trạng thái và topology

Repository hỗ trợ hai cấu hình:

- `render.yaml`: demo topology, Core service có thể embed Workspace runtime.
- `render.production.yaml`: topology production/cô lập hơn.

Hai frontend Vite được triển khai thành hai project riêng; backend dùng PostgreSQL và chạy migration trước khi khởi động qua `scripts/start_web.sh`.

## 2. Chạy local

Yêu cầu Python 3.11+, Node.js 18+ và PostgreSQL.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python scripts\run_dev.py
```

Frontend:

```powershell
Set-Location Frontend
npm install
npm run dev:user
# Terminal khác: npm run dev:admin
```

User app dùng cổng `5173`, Admin app `5174`, backend `8000`.

## 3. Cấu hình production bắt buộc

- PostgreSQL `DATABASE_URL`.
- `SECRET_KEY` mạnh và CORS origin chính xác.
- API key của provider LLM được chọn.
- URL frontend/backend và WebSocket đúng HTTPS/WSS.
- Google OAuth/Calendar redirect URI khớp domain production nếu dùng Calendar.
- Không commit `.env`, access token hoặc credential thật.

Personal Agent là flow mặc định. Chỉ bật Workspace flags khi đã provision đúng membership/source, chạy migration và hoàn thành acceptance riêng:

```dotenv
MULTI_AGENT_ENABLED=false
PRODUCT_DELIVERY_AGENT_ENABLED=false
QUALITY_ASSURANCE_AGENT_ENABLED=false
EXECUTIVE_AGENT_ENABLED=false
```

## 4. CI và vận hành

- `.github/workflows/ci.yml` kiểm tra cả cấu hình Multi-Agent tắt và bật.
- `.github/workflows/keep-alive.yml` chỉ giảm khả năng Render free service ngủ; không phải SLA.
- Docker health check dùng `/health` cho Core hoặc readiness nội bộ cho runtime chuyên biệt.
- Trước release phải chạy backend tests, Ruff, frontend builds, migration và smoke test REST/WebSocket/HITL.

Không scale backend nhiều replica nếu chưa giải quyết coordination cho WebSocket, scheduler và process-local state. Backup database và diễn tập rollback migration trước khi đổi traffic production.

## 5. Tuyên bố môi trường

URL xuất hiện trong artifact đánh giá chỉ chứng minh môi trường tại thời điểm đo. Tài liệu bàn giao phải ghi rõ staging/production, commit đang chạy và ngày xác minh; không suy ra trạng thái deploy hiện tại chỉ từ source code.
