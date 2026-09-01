# Báo cáo đánh giá code và deployment — 2026-08-28

## 1. Kết luận

Trạng thái phát hành: **HOLD / CHƯA ĐỦ ĐIỀU KIỆN PHÁT HÀNH**.

Phần nền tảng và memory PostgreSQL đạt yêu cầu, nhưng release vẫn bị chặn bởi chất lượng Agent,
latency chat P95, WebSocket staging, accessibility và hiệu năng hiển thị. Google OAuth/Calendar thật
không được chạy theo yêu cầu của người dùng, vì vậy hạng mục đó là **SKIP**, không phải PASS.

Không sửa mã nguồn ứng dụng trong lần đánh giá staging này. Các thay đổi chỉ gồm file cấu hình mẫu,
báo cáo và artifact đánh giá. Dữ liệu test task/reminder đã được xóa sau khi chạy.

## 2. Phạm vi revision thực tế

Ba deployment hiện không cùng commit. Theo chỉ đạo, mỗi phần được đánh giá đúng theo revision đang chạy:

| Thành phần | Revision đang chạy | Nhánh deployment | Trạng thái |
|---|---|---|---|
| Backend Render `orbit-backend` | `def0bf3dfb4664f395d7a74bac6f23e39793870b` | `tuan` | live |
| User Vercel | `6c8b489f51e683ccd4218956989df1d5a696b43c` | `deploy` | ready |
| Admin Vercel | `8195003923c1a8387faf0fa1b526b267d09f60d8` | `tuan` | ready |
| Nhánh làm việc `hau` | `3517ef82bbf566603c46cdc6fa70a0a64305b72b` | `hau` | source app không khác trực tiếp `origin/deploy`; commit này thêm tài liệu đánh giá |

Vì revision không đồng nhất, E2E xác nhận tính tương thích của tổ hợp deployment hiện tại, nhưng không
chứng minh một release duy nhất đã được build từ cùng một commit. Đây vẫn là rủi ro phát hành.

## 3. Bảng kết quả tổng hợp

| Hạng mục | Kết quả mới nhất | Gate/diễn giải | Trạng thái |
|---|---:|---|---|
| Backend regression | 410/410 pass | Không failure/error | **PASS** |
| Coverage `src` | 66,71% | >= 60% | **PASS** |
| Alembic fresh upgrade | đến revision `20260826_25` | DB trắng nâng cấp không lỗi | **PASS** |
| Memory harness PostgreSQL | 9/9 pass | Toàn bộ repository test dùng PostgreSQL thật | **PASS** |
| PostgreSQL checkpoint reconnect | 1/1 pass | Ghi/đóng/mở/đọc lại được | **PASS** |
| Formal Agent acceptance | 5/17 pass (29,4%) | >= 80% | **FAIL** |
| Task title precision/F1 | 83,3% / 83,3% | >= 90% / >= 85% | **FAIL** |
| Chat staging | 10/10 HTTP 200 | P95 < 5.000 ms | **FAIL** — P95 5.242 ms |
| Browser user login/chat/routes | login + chat + 8/8 route | Luồng chính hoạt động | **PASS** |
| Browser admin login/routes | login + 6/6 route | Luồng chính hoạt động | **PASS** |
| Task API E2E | create/list/update/delete: 201/200/200/204 | Tất cả thao tác thành công | **PASS** |
| Reminder scheduler | trạng thái cuối `fired` | Reminder phải được xử lý | **PASS** |
| WebSocket staging | handshake HTTP 403 | Kết nối và nhận event | **FAIL** |
| Load API | 87/100 2xx, 13 HTTP 429 | Không lỗi ở tải đã chọn | **FAIL** |
| Axe user authenticated routes | 14 serious/critical theo tổng route | 0 serious/critical | **FAIL** |
| Axe admin authenticated routes | 11 serious/critical theo tổng route | 0 serious/critical | **FAIL** |
| Lighthouse user login | Performance 68, Accessibility 92 | >= 80 / >= 90 | **FAIL** performance |
| Lighthouse admin login | Performance 81, Accessibility 83 | >= 80 / >= 90 | **FAIL** accessibility |
| Web Vitals lab LCP | user 5.353 ms, admin 3.726 ms | <= 2.500 ms | **FAIL** |
| Web Vitals lab CLS | user 0,0027, admin 0 | <= 0,1 | **PASS** |
| Google OAuth/Calendar thật | không chạy theo yêu cầu | Cần tài khoản Google test | **SKIP** |
| User feedback thật | 0 participant | >= 5 participant | **PENDING** |

## 4. Kết quả staging chi tiết

### 4.1 Chat/model thật và chi phí

Đã gửi 10 request tuần tự đến `POST /api/v1/chat` trên Render:

| Metric | TTFB | Tổng thời gian |
|---|---:|---:|
| P50 | 1.763 ms | 1.764 ms |
| P95 | 5.241 ms | 5.242 ms |
| P99 | 7.369 ms | 7.370 ms |
| Max | 7.901 ms | 7.902 ms |

10/10 request trả HTTP 200 và Agent ở trạng thái `completed`. Endpoint hiện trả response không streaming,
vì vậy TTFB gần như thời gian hoàn thành cả response; không được gọi đây là TTFT thật. Muốn đo TTFT phải
có endpoint streaming/SSE/WebSocket phát token.

Runtime Render được xác minh qua API là `openai/gpt-4.1-mini`. Giá cấu hình tham khảo là $0,40/1M input
token và $1,60/1M output token. Tuy nhiên dashboard usage không tăng token hay request sau 10 lần gọi,
nên cost/run là **UNAVAILABLE**, không phải `$0`. Cần sửa/kiểm tra pipeline ghi usage trước khi tính chi phí.
Kết quả Agent cũ dùng 91.691 token với model khác cũng không được áp giá của model staging hiện tại.

### 4.2 Browser E2E

Playwright với Chrome thật đã xác nhận:

- User đăng nhập thành công và chuyển đến `/chat`.
- Chat UI gửi một prompt và số message tăng từ 0 lên 2.
- Các trang `/assistant`, `/chat`, `/tasks`, `/tasks/inbox`, `/reminders`, `/calendar`, `/memory`,
  `/profile` đều render HTTP 200.
- Admin đăng nhập thành công; `/admin`, `/admin/users`, `/admin/user-data`, `/admin/ai`,
  `/admin/ai-usage`, `/admin/audit-log` đều render HTTP 200.
- User app phát sinh một console error HTTP 409 khi Calendar chưa kết nối Google; admin không có console error.

### 4.3 Task, reminder, WebSocket và load

- Task staging: tạo, nhìn thấy trong danh sách, cập nhật và xóa đều thành công.
- Reminder staging: tạo thành công và scheduler chuyển trạng thái sang `fired`; sau đó dữ liệu test được xóa.
- WebSocket `wss://orbit-backend-xkgq.onrender.com/api/v1/ws` trả HTTP 403 ngay khi handshake cho cả
  kịch bản realtime. Vì không kết nối được, message overhead và delivery latency không thể đo.
- Load 100 request với concurrency 5: 87 HTTP 200 và 13 HTTP 429; P50 306 ms, P95 1.203 ms,
  max 3.464 ms. Rate limit đang bảo vệ hệ thống, nhưng bài load theo tiêu chí tất cả request thành công
  vẫn FAIL. Muốn đo throughput hạ tầng riêng cần một profile/token test được cấp rate-limit phù hợp.
- Không thấy một queue độc lập trong bằng chứng runtime; lần này chỉ chứng minh scheduler bằng thay đổi
  trạng thái reminder, không chứng minh khả năng chịu lỗi của distributed queue.

### 4.4 Memory trên PostgreSQL thật

Đã chạy lại toàn bộ 9 test của `tests/test_memory_harness.py` bằng fixture ngoài repository, đặt
`DATABASE_URL` trước khi import ứng dụng và cố ý không nạp fixture SQLite trong `tests/conftest.py`.

Kết quả: **9/9 PASS trong 10,57 giây** trên PostgreSQL 17.10, database riêng
`orbit_agent_eval_test` tại `127.0.0.1:55432`. Test bao phủ retrieval, TTL/lifecycle, cross-user isolation,
semantic retrieval, replacement/provenance, context budget, heartbeat compaction và maintenance.

PostgreSQL local cô lập là lựa chọn đúng cho harness vì test drop/create schema và ghi dữ liệu phá hủy.
Không chạy harness này thẳng vào database production của Render. Deployment được kiểm tra qua API E2E;
database test local dùng để chứng minh repository thực sự tương thích PostgreSQL thay vì SQLite.

### 4.5 Accessibility và Web Vitals

Axe trên các route đã đăng nhập ghi nhận lỗi lặp theo từng trang. Các nhóm chính gồm `button-name`,
`select-name`, `label`, `color-contrast`, `nested-interactive`, `heading-order` và `landmark-unique`.
Tổng theo route là 14 serious/critical ở user và 11 ở admin; con số này có thể lặp cùng một nguyên nhân
trên nhiều route.

Lighthouse navigation lab trên hai trang login:

| App | Performance | Accessibility | Best Practices | SEO | FCP | LCP | TBT | CLS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| User | 68 | 92 | 96 | 82 | 4.663 ms | 5.353 ms | 0,5 ms | 0,0027 |
| Admin | 81 | 83 | 96 | 82 | 3.649 ms | 3.726 ms | 0 ms | 0 |

INP không có trong lần navigation-only này. INP cần dữ liệu RUM từ người dùng thật hoặc một bài tương tác
riêng; không được tự suy diễn từ TBT. Chunk Calendar 1.058,80 kB minified ở baseline build vẫn là rủi ro.

## 5. Những phần chưa thể kết luận PASS

1. Google Sign-In, OAuth consent, refresh token và thao tác event thật: **SKIP theo yêu cầu người dùng**.
2. TTFT token thật: endpoint `/api/v1/chat` không streaming.
3. WebSocket delivery/latency: handshake staging đang bị 403.
4. Cost/run: staging không ghi usage cho 10 request thành công.
5. INP/field Web Vitals: chưa có RUM hoặc bài tương tác chuyên biệt.
6. User satisfaction: chưa có tối thiểu 5 người tham gia thật.
7. Release đồng nhất: backend, user và admin chưa cùng revision.

## 6. Cách triển khai và chạy lại đánh giá

### 6.1 Cấu hình an toàn

Sao chép `.env.example` thành `.env`, chỉ điền secret trong `.env`. Không commit password, Render token,
Vercel token hoặc model key. Dùng tài khoản staging riêng và bật `E2E_ALLOW_TEST_DATA_WRITE=true` chỉ khi
cho phép runner tạo rồi xóa task/reminder test.

Các URL/ID công khai đã được điền trong `.env.example`. Với lần đánh giá này không cần
`VERCEL_AUTOMATION_BYPASS_SECRET`; direct admin public URL được dùng thay cho deployment bị Vercel bảo vệ.

### 6.2 Xác minh revision trước khi đo

Qua Render API, lấy latest live deploy và commit cho backend. Qua Vercel API, lọc deployment
`target=production` của hai project và ghi `githubCommitSha`. Nếu ba SHA khác nhau, phải ghi kết quả theo
từng component giống mục 2, không tuyên bố toàn hệ thống đang cùng một release.

### 6.3 Chạy PostgreSQL memory harness

Database phải là database test có thể xóa schema, tuyệt đối không dùng `DATABASE_URL` production:

```powershell
& "C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe" `
  -D "D:\deploy\.orbit-postgres-eval-20260828" `
  -o "-p 55432" start

cd D:\deploy\copy_build_phase
$env:TEST_DATABASE_URL = "postgresql+asyncpg://orbit_eval@127.0.0.1:55432/orbit_agent_eval_test"
python -m pytest D:\deploy\.orbit-pg-memory-harness -q `
  --junitxml=eval/results/memory-harness-postgres.junit.xml
```

Điểm kiểm soát quan trọng: `DATABASE_URL` phải được đặt trước khi import `src.db.session`, và runner không
được nạp `tests/conftest.py` đang thay repository bằng SQLite.

### 6.4 Chạy staging benchmark và browser E2E

```powershell
cd D:\deploy\.orbit-e2e-tools
node chat-benchmark.mjs
node realtime-load.mjs
node browser-e2e.mjs

node .\node_modules\lighthouse\cli\index.js `
  "https://c3-app-132-auo2.vercel.app/login" `
  --chrome-path="C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --chrome-flags="--headless --no-sandbox --disable-gpu" `
  --only-categories=performance,accessibility,best-practices,seo `
  --output=json `
  --output-path="D:\deploy\copy_build_phase\eval\results\lighthouse-user-staging.raw.json" `
  --quiet
```

Chạy tương tự cho admin URL. Sau mỗi lần chạy phải kiểm tra cleanup dữ liệu test, tách HTTP 429 khỏi lỗi
5xx và ghi rõ TTFB không phải TTFT nếu endpoint không streaming.

### 6.5 Quy tắc chấm

- `PASS`: có artifact mới và đạt gate.
- `FAIL`: đã đo nhưng không đạt gate hoặc luồng không chạy được.
- `SKIP`: chủ động loại khỏi phạm vi; không được tính như PASS.
- `PENDING`: chưa có dữ liệu đủ tin cậy.
- Không tính cost khi token usage không được ghi; không coi usage delta 0 là chi phí thật bằng 0.
- Không chạy harness phá hủy trên production database.

## 7. Artifact mới nhất

- `results/latency-chat-staging-latest.json` / `.md`
- `results/realtime-load-staging-latest.json` / `.md`
- `results/browser-e2e-staging-latest.json` / `.md`
- Ảnh chụp chứa dữ liệu tài khoản staging được giữ ngoài Git tại
  `D:\deploy\orbit-eval-artifacts-20260828\browser-*-staging.png`
- `results/memory-harness-postgres-latest.json` / `.md`
- `results/memory-harness-postgres.junit.xml`
- `results/lighthouse-staging-latest.json` / `.md`
- `results/lighthouse-user-staging.raw.json`, `results/lighthouse-admin-staging.raw.json`
- `results/agent_acceptance_latest.json` / `.md`

Các file `latest` là nguồn kết quả hiện hành; không dùng report lịch sử để thay cho lần chạy này.
