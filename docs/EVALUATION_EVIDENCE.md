# Báo cáo đánh giá tổng hợp — Orbit

> **Phạm vi chấm chính:** Personal Agent theo đề bài gốc. Workspace Multi-Agent là phần phát triển mở rộng và chưa được tính là release mặc định trong báo cáo này. Xem [Workspace Development Report](workspace-development/DEVELOPMENT_REPORT.md).

Tạo lúc `2026-08-29T14:31:38.069228+00:00` từ source revision cơ sở `f0651a1`.

Báo cáo không chuyển bằng chứng còn thiếu thành điểm đạt. `PENDING` nghĩa là đã có runner/protocol nhưng
chưa có đủ kết quả hợp lệ hiện tại.

## 1. Tổng quan gate phát hành

| Hạng mục | Kết quả | Gate | Trạng thái |
|---|---:|---:|---|
| Automated tests | 414/414 passed, 0 skipped | No failures/errors | PASS |
| Source coverage | 66.8% | >=60% | PASS |
| Formal Agent acceptance | 50.0% case pass | Dataset gates | FAIL |
| Task title F1 | 97.0% | >=70% | PASS |
| Deadline accuracy | 95.3% | >=70% | PASS |
| Proactive detection | Precision 100.0%; recall 80.0% | Precision >=90%; recall theo dõi | PASS precision / cần cải thiện recall |
| API latency P95 | 21.2 ms | Configured runner gate | PASS |
| Staging chat | 10/10; P95 4545.1 ms | All complete; P95 <=5000 ms | PASS |
| PostgreSQL memory harness | 17/17 passed | No failures/errors | PASS |
| Staging WebSocket | 0/5 connected | 5 connections and all deliveries | FAIL |
| Staging HTTP load | 85/100 2xx | All requests return 2xx | FAIL |
| Browser functional E2E | User/admin login, chat, and routes | All functional checks pass | PASS |
| Browser accessibility | Serious/critical findings remain | Zero serious/critical findings | FAIL |
| Lighthouse aggregate | Both user/admin surfaces | All configured web gates pass | FAIL |
| Google Calendar OAuth | PARTIAL | Interactive consent and token exchange | FAIL |
| User feedback | Pending | >=5 participants | PENDING |

## 2. Vì sao từng mục là FAIL hoặc PENDING

Kết luận phát hành tổng thể: **FAIL** vì một hoặc nhiều gate bắt buộc dưới đây chưa đạt.

- **Formal Agent acceptance = FAIL:** chỉ 50.0% số case đạt; `case_pass_rate` 50.0% so với ngưỡng 80.0%; `tool_routing_accuracy` 59.3% so với ngưỡng 95.0%; `memory_isolation_pass_rate` 0.0% so với ngưỡng 100.0%.

- **Staging WebSocket = FAIL:** chỉ mở được 0/5 kết nối. Handshake trả về `Unexpected server response: 403`, nên không thể đo độ trễ phân phối hoặc quan sát event reminder qua WebSocket.

- **Staging HTTP load = FAIL:** chỉ 85/100 request trả về 2xx; phân bố status là `{"200": 85, "429": 15}`. 15 phản hồi HTTP 429 cho thấy đã chạm rate limit; đây không phải lỗi sập 5xx, nhưng vẫn không đạt gate yêu cầu toàn bộ request trả về 2xx.

- **Browser accessibility = FAIL:** gate yêu cầu không có lỗi serious/critical, nhưng ghi nhận 14 lỗi theo route user và 11 lỗi theo route admin. Các nhóm lỗi gồm `button-name, color-contrast, empty-table-header, heading-order, label, landmark-unique, nested-interactive, page-has-heading-one, select-name`; tổng theo route có thể lặp lại cùng một nhóm lỗi.

- **Lighthouse aggregate = FAIL:** performance user 61 < 80 và LCP user 6505.108 ms > 2500 ms; accessibility admin 83 < 90 và LCP admin 3642.232 ms > 2500 ms. Accessibility user, performance admin và hai phép đo CLS đều đạt, nhưng gate tổng yêu cầu tất cả phép kiểm tra cùng đạt.

- **Google Calendar OAuth = FAIL/PARTIAL:** cấu hình runtime tạo thành công URL cấp quyền Google và callback origin khớp staging, nhưng `currently_connected` là `false` và consent tương tác là `NOT_RUN`. Chưa có authorization code/token exchange, nên chưa thể đánh dấu truy cập Calendar riêng tư là PASS.

- **User feedback = PENDING:** mới ghi nhận 0/5 người dùng thật bắt buộc. 5 phản hồi được tạo là dữ liệu kiểm thử hư cấu đã gắn nhãn rõ ràng và không được tính vào bằng chứng phát hành.

## 3. Kết quả chi tiết đã hợp nhất

Đây là **file báo cáo duy nhất dành cho người đọc**. Các JSON trong `eval/results/` chỉ là dữ liệu máy đọc
được giữ lại để kiểm chứng và tái lập, không phải các báo cáo cần đọc riêng.

### 3.1 Backend, coverage và PostgreSQL

| Phép đo | Kết quả | Trạng thái |
|---|---:|---|
| Automated tests | 414/414 passed, 0 skipped | PASS |
| Source coverage | 66.77% | PASS |
| PostgreSQL memory/quality harness | 17/17 | PASS |
| Database harness | PostgreSQL 17.10 tại 127.0.0.1:55432/orbit_agent_eval_test | Cô lập, không dùng production |

### 3.2 Agent acceptance và chất lượng AI

Formal acceptance chạy lúc `2026-08-29T08:22:15.022026+00:00` bằng
`openrouter/openai/gpt-4.1-mini`.

| Chỉ số | Kết quả | Gate | Trạng thái |
|---|---:|---:|---|
| Case pass | 15/30 (50.0%) | >=80% | FAIL |
| Tool routing | 59.3% | >=95% | FAIL |
| Task precision/recall/F1 | 100.0% / 100.0% / 100.0% | >=90% | PASS |
| Task due accuracy | 100.0% | >=90% | PASS |
| Task priority accuracy | 75.0% | Thông tin | N/A |
| Required fact recall | 79.2% | Thông tin | N/A |
| Forbidden claim rate | 0.0% | 0% | PASS |
| HITL pre-confirmation side effects | 0.0% | 0% | PASS |
| Memory retrieval/isolation/expired rejection | 0.0% / 0.0% / 0.0% | Isolation 100% | FAIL |
| Agent latency P50/P95 | 3679.57 / 6510.1 ms | Thông tin | N/A |
| LLM judge mean / unsupported claims | 0.811111 / 22.2% | Thông tin | N/A |
| Token / request / estimated cost | 171170 / 56 / $0.072664 | Thông tin | N/A |

### 3.3 Task extraction và chống tạo task giả

| Môi trường | Case/run | Precision | Recall | F1 | Date accuracy | Trạng thái |
|---|---:|---:|---:|---:|---:|---|
| Local OpenRouter `openai/gpt-4.1-mini` | 60 case | 96.0% | 98.0% | 97.0% | 95.3% | PASS |
| Staging `gemini-2.5-flash` | 60 case x 3 run | 86.8%..92.5% | 93.9%..100.0% | 90.2%..96.1% | 90.5%..95.3% | PASS |
| Non-commitment false-positive staging | 40 case | — | — | 100.0% không tạo sai | — | PASS |

Bộ non-commitment gồm greeting, discussion, question, delegated-to-other và completed-past; ghi nhận
`0` false positive,
`17104` token và chi phí ước tính
`$0.0028959`.

#### 3.3.1 Phát hiện chủ động trên luồng 300 tin nhắn

Đây là **technical evaluation**, không phải business evaluation: phép đo kiểm tra chất lượng phân loại/trích xuất
của pipeline và chi phí suy luận. Báo cáo business chỉ sử dụng kết quả này để diễn giải mức độ tin cậy và khả năng
pilot; nó không tự chứng minh product-market fit, ROI hay willingness-to-pay.

Trong 300 tin nhắn có 30 tin chứa task thật được gài và 270 tin nhiễu hoặc gần giống task:

| Chỉ số | Kết quả | Diễn giải |
|---|---:|---|
| Tin chứa task phát hiện đúng | 24/30 | Recall **80.0%** |
| Tin nhiễu bị phát hiện nhầm | 0/270 | Precision **100.0%** trên bài chạy này |
| Task records được app ghi nhận | 28 | Cần đối soát với phân rã theo loại ở dưới |
| Gợi ý sự kiện lịch | +3 | Pipeline phụ; trùng nội dung task #6, #96 và #116 nên không cộng lại vào recall |

| Loại cam kết | Phát hiện | Recall |
|---|---:|---:|
| Tự cam kết, có giờ rõ ràng | 10/10 | 100.0% |
| Tự cam kết, có hạn chót theo ngày | 8/10 | 80.0% |
| Cuộc hẹn và mời đích danh | 3/4 | 75.0% |
| Tự cam kết, hành động chung chung, không có giờ cụ thể | 3/6 | 50.0% |

Sáu false negative đều dùng cam kết mềm hoặc thời gian không có giờ đồng hồ cụ thể:

| ID | Nội dung | Phân tích khả dĩ |
|---:|---|---|
| 36 | “Tấn ơi, 3h chiều thứ Tư mình họp review sprint nhé, vào cùng mình với.” | Cùng mẫu với các lời mời được bắt ở #116, #186 và #256. Việc bỏ sót có thể do độ bất định khi chạy ở temperature 0.7; cần chạy lặp lại trước khi kết luận nguyên nhân. |
| 126 | “Mình sẽ cập nhật xong tài liệu kiến trúc trước cuối tuần này.” | “Trước cuối tuần này” là mốc thời gian mềm, không có giờ để neo hạn. |
| 146 | “Mình sẽ merge nhánh feature/calendar sau khi CI xanh, muộn nhất tối nay.” | Điều kiện “sau khi CI xanh” kết hợp hạn chót mềm có thể bị đọc thành hành động chưa chắc chắn. |
| 176 | “Mình sẽ fix con bug rớt kết nối realtime, cố gắng xong trong hôm nay.” | Cụm dè dặt “cố gắng” có thể bị đọc như ý định thay vì cam kết. |
| 206 | “Tối nay mình dựng môi trường staging mới cho team QA test.” | Có buổi trong ngày nhưng là câu trần thuật hành động, không có giờ hoặc từ khóa hạn chót. |
| 276 | “Mình nhận việc liên hệ nhà cung cấp server, sẽ gọi cho họ trong chiều nay.” | Có hành động và buổi trong ngày nhưng không có giờ cụ thể. |

Kết quả cho thấy detector ưu tiên precision: không làm phiền người dùng bằng task giả, nhưng bỏ sót 20% task thật.
Nhóm có giờ đồng hồ đạt 100%, còn nhóm hành động chung chung chỉ đạt 50%. Vì vậy trạng thái phù hợp là
**đạt gate precision nhưng cần cải thiện recall**, chưa nên mô tả proactive detection là hoàn thiện.

Có một điểm cần đối soát trong artifact nguồn: 24 tin được phát hiện, trong đó bảng theo loại cho biết có 3 tin
“hẹn + mời đích danh” sinh hai task mỗi tin, về số học sẽ tạo `21 + 3 × 2 = 27` Task records. Con số 28 chỉ
khớp nếu có 4 tin sinh đôi hoặc có thêm một record từ nguồn khác. Báo cáo giữ nguyên số 28 do app ghi nhận nhưng
không dùng nó để tính precision/recall cho đến khi truy vết từng record.

**Usage và chi phí của bài chạy 300 tin:**

| Chỉ số | Giá trị |
|---|---:|
| Model và đơn giá | `gpt-4o-mini`; $0.15/1M input, $0.60/1M output token |
| Prompt tokens | 183,047 |
| Completion tokens | 10,502 |
| Tổng token | 193,549 |
| Số lần gọi LLM | 372 |
| Chi phí tính lại | **$0.0338** |
| Trung bình trên mỗi tin | khoảng 645 token và 1.24 lần gọi |
| Gồm smoke test 3 tin và poll kết quả | 196,595 token; **$0.0343** |

Phép tính độc lập là `183047 / 1e6 × 0.15 + 10502 / 1e6 × 0.60 = $0.03375225`, làm tròn thành
`$0.0338`, khớp `estimated_cost_usd` của app. `usage_logs` chưa gắn nhãn theo tính năng, nên tổng này gộp
stage 1 kiểm tra liên quan, stage 2 trích xuất theo cửa sổ và bộ trích xuất sự kiện lịch chạy song song. Không có
lần gọi `/chat`; toàn bộ usage được quy cho pipeline phát hiện chủ động trong phạm vi bài chạy, nhưng chưa thể
tách chi phí riêng của từng stage.

### 3.4 Staging API, latency, WebSocket và scheduler

| Luồng | Kết quả | Ghi chú |
|---|---:|---|
| Chat benchmark mới nhất | 10/10, P50 1551.483 ms, P95 4545.144 ms | Endpoint không streaming; TTFB không phải TTFT thật |
| Summary benchmark sâu | 25/25, P95 8010.157 ms | Run staging riêng trước benchmark mới nhất |
| Task-extraction benchmark sâu | 25/25, P95 5869.951 ms | Run staging riêng |
| Planner benchmark sâu | 4/5, P95 8419.351 ms | Có 1 HTTP 500 sau khoảng 60,7 giây |
| Known cost subtotal / 1000 messages | $0.152487 | Chưa gồm `proactive_extraction, rolling_summary`; không phải tổng hoàn chỉnh |
| WebSocket | 0/5 kết nối | Unexpected server response: 403 |
| Task CRUD | 201/200/200/204 | Create/list/update/delete PASS |
| Reminder scheduler | fired | Scheduler fired; event WebSocket không quan sát được do handshake 403 |
| HTTP load | 85/100 2xx; {"200": 85, "429": 15} | 15 HTTP 429, không có 5xx trong load 100 request |

Benchmark sâu ghi nhận telemetry `openai/gpt-4o-mini`, còn benchmark chat mới nhất ghi nhận
`google/gemini-2.5-flash`.
Hai artifact có thời điểm khác nhau nên không được coi là cùng một cấu hình runtime. Usage delta của benchmark mới nhất bằng 0,
vì vậy báo cáo **không** diễn giải thành chi phí thực bằng 0.

### 3.5 Browser, accessibility và Lighthouse

| Surface | Functional E2E | Serious/critical theo route | Performance | Accessibility | LCP | CLS |
|---|---|---:|---:|---:|---:|---:|
| User | Login + chat + 8/8 route PASS | 14 | 61 | 92 | 6505.108 ms | 0.002921 |
| Admin | Login + 6/6 route PASS | 11 | 82 | 83 | 3642.232 ms | 0 |

Các nhóm lỗi accessibility: `button-name, color-contrast, empty-table-header, heading-order, label, landmark-unique, nested-interactive, page-has-heading-one, select-name`. INP chưa đo vì
Lighthouse navigation-only không cung cấp dữ liệu tương tác thật.

### 3.6 Google Calendar-only OAuth

Google Sign-In đã được loại khỏi phạm vi theo yêu cầu; chỉ luồng cấp quyền Calendar được đánh giá.

| Kiểm tra | Kết quả |
|---|---|
| Tạo authorization URL | 200; host `accounts.google.com` |
| Calendar scope và client ID | Có |
| Client ID khớp cấu hình Calendar local | true |
| Redirect URI | `https://orbit-backend-xkgq.onrender.com/api/v1/calendar/oauth/callback` |
| Callback FRONTEND_ORIGIN khớp staging | true; `https://c3-app-132-auo2.vercel.app` |
| Account đánh giá đã kết nối | false |
| Google consent/token exchange | NOT_RUN |

Kết luận Calendar: **PARTIAL/FAIL**. Cấu hình runtime đủ để bắt đầu OAuth, nhưng truy cập Calendar riêng tư vẫn cần
người dùng Google hoàn tất màn consent; ứng dụng không cần dùng Google Sign-In làm cơ chế đăng nhập.

### 3.7 Feedback

- Feedback thật: `0/5` người, trạng thái **PENDING**.
- Feedback mô phỏng: `5` người hư cấu,
  task completion `80.0%`,
  rating `3.6/5`, helpfulness
  `4.0/5`, trust
  `3.6/5`.
- Dữ liệu mô phỏng chỉ kiểm thử pipeline và **không được tính** làm feedback thật hoặc gate phát hành.

### 3.8 Mẫu báo cáo tổng đã điền

**MÔI TRƯỜNG:** `server/staging` cho accuracy/latency và `local PostgreSQL cô lập` cho phép đo
false-reminder/cost OpenRouter. Accuracy chạy với
`LLM_PROVIDER=google` ·
`MODEL_NAME=gemini-2.5-flash` · ngày chạy
`2026-08-29`.

Cost đủ 6 tác vụ chạy riêng với
`LLM_PROVIDER=openrouter` ·
`MODEL_NAME=openai/gpt-4.1-mini`.
Không gộp hai model/môi trường thành cùng một runtime.

1. **ACCURACY**

   - Số ca test: **60 ca x 3 lần chạy = 180 lượt đánh giá**.
   - Precision/Recall/F1 trung bình: **89.9% / 96.6% / 93.1%**.
   - Qua 3 lần chạy: precision **86.8%–92.5%**; recall **93.9%–100.0%**; F1 **90.2%–96.1%**.
   - Date accuracy: **119/127 (93.7%)**.
   - File máy đọc đính kèm trong repo: `eval/extract_report.json`.

2. **FALSE REMINDER**

   - Server/staging: cỡ mẫu **40**; false positive **0 → 0.0%**.
   - Local OpenRouter: cỡ mẫu **40**; false positive **1 → 2.5%**; case lỗi `DELEGATE-01`.

3. **LATENCY (`/chat`)**

   - Nguồn: **đo tay bằng scripted HTTP benchmark** · n = **25 cho mỗi quick action**.
   - Tóm tắt: p50 **1577.519 ms** · p95 **2043.043 ms**.
   - Trích task: p50 **1795.494 ms** · p95 **2566.973 ms**.

4. **DAILY_TOKEN_BUDGET đang áp dụng:** server/deployment **300000 token/ngày** tại thời điểm đo; local harness **200000 token/ngày**.

5. **CHI PHÍ**

| Tác vụ | Model | in_tok tb | out_tok tb | cost/lần (USD) | tần suất / 1.000 tin |
|---|---|---:|---:|---:|---:|
| Tóm tắt | openai/gpt-4.1-mini | 3826.0 | 63.0 | $0.00163120 | 10 |
| Trích task | openai/gpt-4.1-mini | 270.0 | 95.0 | $0.00026000 | 10 |
| Planner (1 vòng) | openai/gpt-4.1-mini | 3822.0 | 186.0 | $0.00182640 | 120 |
| Proactive relevance | openai/gpt-4.1-mini | 240.0 | 7.0 | $0.00010720 | 1000 |
| Proactive extraction | openai/gpt-4.1-mini | 1372.0 | 65.0 | $0.00065280 | 100 |
| Rolling summary | openai/gpt-4.1-mini | 248.0 | 65.0 | $0.00020320 | 33 |
| **Tổng ước tính / 1.000 tin** |  |  |  | **$0.417266** | A/B/C/D bên dưới |

Giả định:

- **A:** 100% tin đủ điều kiện đi qua proactive relevance → 1.000 relevance call/1.000 tin.
- **B:** 10% tin được relevance đánh dấu liên quan → 100 proactive extraction call/1.000 tin.
- **C:** 10 lượt tóm tắt thủ công và 10 lượt trích task thủ công/1.000 tin.
- **D:** 120 lượt chat thường, trung bình 1 vòng planner/lượt; rolling summary dự kiến 33 lượt/1.000 tin.

Tổng **$0.417266/1.000 tin** là phép ngoại suy từ mẫu local OpenRouter, không phải hóa đơn production thực tế.

## 4. Lệnh tái lập

```powershell
python scripts/run_coverage.py
python scripts/benchmark_api_latency.py --base-url http://127.0.0.1:8000 --endpoint /health
python scripts/eval_user_agent.py
python scripts/eval_extract_tasks.py
python scripts/summarize_user_feedback.py
python scripts/generate_evaluation_evidence.py
```

## 5. Phần vẫn cần con người hoặc dữ liệu bên ngoài

- Cần tối thiểu 5 người dùng thật cung cấp feedback ẩn danh; không chấp nhận rating mô phỏng.
- Cần một người dùng hoàn tất Google Calendar consent và token exchange.
- Cần dữ liệu tương tác thật hoặc controlled interaction để đo INP.
- Cần chạy lại coverage/JUnit sau thay đổi source đáng kể.
