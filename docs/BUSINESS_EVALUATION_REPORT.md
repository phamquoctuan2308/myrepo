# Báo cáo tự đánh giá Business — Orbit AI Assistant

> **Đề tài:** AI Agent Trợ lý cá nhân trong Chat (tóm tắt hội thoại, nhắc việc, lên lịch)
> **Quy mô nhóm:** 4 thành viên
> **Ngày đánh giá:** 2026-08-30
> **Phạm vi:** Tự đánh giá Personal Agent theo đề bài gốc, sản phẩm đang chạy và bằng chứng trong repository. Workspace Multi-Agent là phần phát triển mở rộng, nằm ngoài điểm đánh giá business hiện tại; báo cáo không dùng kết quả Workspace để nâng điểm và không sử dụng khảo sát thị trường bên ngoài.

## 1. Mục tiêu báo cáo

Báo cáo trả lời ba câu hỏi:

1. Sản phẩm hiện tại đã đáp ứng đề tài đến mức nào?
2. Vì sao từng tiêu chí business được chấm ở mức đó?
3. Sản phẩm đã sẵn sàng pilot, thương mại hóa hoặc mở rộng hay chưa?

Điểm số trong báo cáo phản ánh **mức độ có bằng chứng của dự án**, không chỉ phản ánh ý tưởng có hấp dẫn hay không. Ví dụ, điểm Market thấp không có nghĩa thị trường chắc chắn nhỏ; nó có nghĩa dự án chưa có đủ số liệu để chứng minh thị trường.

## 2. Thông tin và bài toán đề tài

Người dùng nền tảng chat của Tập đoàn X nhận nhiều tin nhắn mỗi ngày qua các nhóm gia đình, công việc và cộng đồng doanh nghiệp. Task, lịch hẹn, deadline và lời hứa dễ bị chôn vùi trong luồng tin nhắn.

Orbit được xây dựng như một Personal AI Agent nằm trong ứng dụng chat, có các năng lực chính:

- Tóm tắt hội thoại theo yêu cầu.
- Trích xuất task, deadline và lịch hẹn.
- Chủ động phát hiện cam kết trong tin nhắn mới.
- Tạo reminder hoặc sự kiện Calendar sau khi người dùng xác nhận.
- Tìm kiếm tin nhắn cũ và sử dụng memory cá nhân.
- Quản lý ngân sách và chi phí AI ở phía Admin.

Phạm vi được chấm trong báo cáo là **một Personal Agent có nhiều tool**. Multi-Agent theo Workspace được theo dõi riêng trong [Workspace Development Report](workspace-development/DEVELOPMENT_REPORT.md).

## 3. Phương pháp chấm điểm

Mỗi tiêu chí business được chấm từ 0 đến 10:

| Điểm | Ý nghĩa |
|---:|---|
| 0–2 | Chưa có hoặc gần như không có bằng chứng |
| 3–4 | Mới là giả thuyết, có một phần triển khai |
| 5–6 | Đáp ứng một phần, còn thiếu bằng chứng quan trọng |
| 7–8 | Đáp ứng khá tốt ở mức MVP/pilot |
| 9–10 | Đã được xác thực bằng người dùng, doanh thu hoặc vận hành production |

Mười hai tiêu chí có trọng số bằng nhau. Tổng điểm tối đa là 120; điểm phần trăm được tính bằng:

```text
business_readiness = tổng điểm / 120 × 100
```

## 4. Kết luận điều hành

| Khía cạnh | Kết luận |
|---|---|
| Khả năng giải quyết đúng bài toán đề tài | Khá tốt |
| Mức hoàn thiện MVP kỹ thuật | Khá |
| Khả năng chạy pilot nhỏ | Có thể sau khi xử lý các lỗi release quan trọng |
| Business validation | Chưa đạt |
| Khả năng thương mại hóa ngay | Chưa đạt |
| Khả năng triển khai toàn Tập đoàn X | Chưa được chứng minh |
| Quyết định đề xuất | **ITERATE / CONTROLLED PILOT** |

Tổng điểm business là **66/120, tương đương 55/100**.

Lý do chính: Orbit đã có sản phẩm và workflow end-to-end tương đối rõ, nhưng chưa có người dùng thật, retention, willingness-to-pay, doanh thu, ROI hoặc capacity production. Vì vậy dự án đã chứng minh phần lớn **technical feasibility**, nhưng chưa chứng minh **business viability**.

## 5. Đánh giá mức đáp ứng yêu cầu đề tài

### 5.1 Yêu cầu cơ bản

| Yêu cầu | Trạng thái | Căn cứ và lý do đánh giá |
|---|---|---|
| Deploy online | Đạt ở mức staging | Báo cáo đánh giá đã chạy browser functional E2E trên staging. Tuy nhiên release gate tổng vẫn FAIL, nên chưa được xem là production-ready. |
| Đăng nhập | Đạt | Có đăng ký, đăng nhập, JWT, hash mật khẩu và route guard. |
| Tối thiểu hai vai trò | Đạt | Có người dùng thường và platform admin; quyền Admin tách khỏi dữ liệu cá nhân của user. |
| Tóm tắt hội thoại | Đạt | Quick Action gọi dữ liệu hội thoại thật và thực hiện tóm tắt theo yêu cầu. |
| Trích xuất task | Đạt tốt | Local task title F1 đạt 97%, date accuracy đạt 95,3%; staging F1 dao động khoảng 90,2–96,1%. |
| Tạo reminder có xác nhận | Đạt | Agent dừng tại bước human-in-the-loop và chỉ thực thi sau khi người dùng approve. |
| Hiển thị lịch cá nhân | Đạt một phần | UI, backend và Google Calendar integration đã có; lần đánh giá gần nhất chưa hoàn tất consent/token exchange thật trên staging. |
| Memory hội thoại | Có nhưng chưa ổn định | Memory và checkpoint bền vững đã được xây, nhưng formal Agent acceptance chưa vượt gate memory retrieval/isolation. |
| Xử lý lỗi cơ bản | Đạt một phần | Có error handling, audit và budget guard; kiểm thử staging còn lệch phiên bản WebSocket, rate-limit/load chưa qua gate và agent routing còn lỗi. |

### 5.2 Yêu cầu nâng cao

| Yêu cầu | Trạng thái | Căn cứ và lý do đánh giá |
|---|---|---|
| Proactive detection | Đạt một phần | Bài technical evaluation 300 tin đạt precision 100% nhưng recall 80% (24/30 task thật); hệ thống không tạo task từ 270 tin nhiễu nhưng còn bỏ sót cam kết mềm. |
| Đồng bộ Google Calendar hai chiều | Đã triển khai, chưa xác minh đầy đủ | Có CRUD và incremental synchronization; cần hoàn thành OAuth consent thật và kiểm tra end-to-end trên staging. |
| Task Inbox ưu tiên | Đạt | Có màn hình gom task AI, task quá hạn, task sắp đến hạn và task ưu tiên. |
| Cảnh báo token/chi phí | Đạt | Có usage log, daily budget, cảnh báo và chặn lượt gọi LLM mới khi hết ngân sách. |
| Đánh giá accuracy | Đạt | Có dataset, runner, precision/recall/F1, date accuracy và false-positive evaluation. |

### 5.3 Ràng buộc đề tài

| Ràng buộc | Mức đáp ứng | Vì sao |
|---|---|---|
| Human-in-the-loop | Tốt | Bộ đánh giá ghi nhận 0% side effect xảy ra trước xác nhận. Con số 0% ở đây là kết quả tốt: không có hành động ghi nào chạy trước khi approve. |
| Bảo mật và quyền riêng tư | Một phần | Có authentication, owner check, conversation participant check, consent và tách quyền Admin. Tuy nhiên nội dung cần xử lý vẫn có thể được gửi tới LLM provider bên ngoài. Vì vậy chưa thể tuyên bố đáp ứng E2E hoặc xử lý hoàn toàn trong vùng giải mã của người dùng. |
| Độ chính xác task cao | Khá tốt | F1 và date accuracy cao trên bộ task extraction. Tuy vậy formal Agent acceptance tổng chỉ đạt 50%, nên chất lượng toàn agent chưa ổn định tương đương chất lượng riêng use case task. |
| Giảm false reminder | Khá | Bài proactive 300 tin ghi nhận 0/270 false positive; các bộ nhỏ trước đó ghi nhận staging 0/40 và local OpenRouter 1/40. Precision cao nhưng recall proactive mới đạt 80%, nên vẫn cần kiểm tra bằng dữ liệu thật. |
| Tối ưu độ trễ | Một phần | Chat staging P95 gần ngưỡng 5 giây; một số benchmark sâu chậm hơn. Chưa có streaming token thực sự. |
| Tối ưu chi phí | Một phần | Có quick action bỏ qua planner khi tool đã xác định, usage tracking và budget guard. Chưa có cache embedding hoặc batch LLM call như gợi ý đề tài. |
| Semantic search/vector memory | Chưa đầy đủ | Sản phẩm hiện không có Qdrant/pgvector làm semantic memory theo kiến trúc gợi ý. Đây không bắt buộc nếu use case vẫn đạt, nhưng chưa đáp ứng phần tối ưu tìm kiếm ngữ nghĩa. |

### 5.4 Ý nghĩa business của benchmark proactive 300 tin

Số liệu precision, recall, lỗi theo loại câu và token/cost chi tiết thuộc **technical evaluation**. Ở góc nhìn
business, bài đo này cung cấp bốn tín hiệu:

- **Niềm tin và notification fatigue:** 0/270 tin nhiễu tạo task sai là tín hiệu tốt cho trải nghiệm; hệ thống ít có
  nguy cơ làm người dùng mất niềm tin vì cảnh báo thừa trong phạm vi dataset hiện tại.
- **Giá trị sử dụng chưa trọn vẹn:** recall 80% nghĩa là còn bỏ sót 1/5 task thật. Orbit có thể hỗ trợ người dùng,
  nhưng chưa đủ bằng chứng để hứa “không bỏ sót công việc” hoặc thay thế hoàn toàn việc tự kiểm tra hội thoại.
- **Phạm vi giá trị rõ hơn:** cam kết có giờ cụ thể đạt recall 100%, còn hành động chung chung chỉ đạt 50%. Pilot
  nên ưu tiên nhóm công việc có deadline/lịch rõ ràng và tiếp tục đo tỷ lệ task bị bỏ sót trên hội thoại thật.
- **Tín hiệu unit cost ban đầu:** $0,0338 cho 300 tin tương đương khoảng $0,1125/1.000 tin nếu giữ nguyên cùng
  model và cơ cấu dữ liệu. Đây mới là AI variable cost của pipeline trong bài synthetic, chưa gồm hạ tầng, nhân sự,
  support, chi phí tuân thủ hoặc tải production nên chưa thể dùng làm ROI.

Vì vậy benchmark này củng cố quyết định **ITERATE / CONTROLLED PILOT**: đủ an toàn để thử nghiệm có giám sát
nhờ false positive thấp, nhưng cần cải thiện recall và thu thập acceptance rate, dismiss rate, missed-task rate cùng
chi phí trên mỗi task được người dùng chấp nhận trước khi rollout rộng.

## 6. Tự đánh giá theo 12 tiêu chí Business

### 6.1 Problem — 9/10

**Đánh giá:** Orbit giải quyết vấn đề có logic rõ ràng: thông tin hành động bị chôn vùi trong lượng lớn tin nhắn.

**Vì sao chấm cao:**

- Đề tài nêu rõ bối cảnh hàng trăm tin nhắn mỗi ngày.
- Task, lịch hẹn, deadline và lời hứa là dữ liệu có giá trị hành động cao.
- Các tính năng Orbit xây dựng bám trực tiếp vào vấn đề: summary, extraction, reminder và Calendar.
- Có thể quan sát và đo vấn đề bằng số task bỏ lỡ hoặc thời gian đọc lại chat.

**Vì sao chưa đạt 10/10:**

- Chưa có phỏng vấn người dùng thật.
- Chưa đo số task bị bỏ lỡ trước khi dùng Orbit.
- Chưa đo số phút người dùng mất để đọc và tổng hợp chat.
- Báo cáo hiện ghi nhận 0/5 feedback thật.

Do đó, vấn đề **hợp lý và có khả năng tồn tại**, nhưng mức độ đau chưa được kiểm chứng bằng dữ liệu thực tế.

### 6.2 Target Customer — 8/10

**Đánh giá:** Khách hàng và người dùng ban đầu tương đối rõ trong đề tài.

**Người dùng trực tiếp:**

- Nhân viên và thành viên các nhóm chat của Tập đoàn X.
- Người nhận nhiều tin nhắn và thường xuyên phải chuyển nội dung chat thành việc cần làm.
- Trưởng nhóm hoặc người có nhiều lịch hẹn, cam kết và deadline.

**Người mua hoặc tài trợ:**

- Tập đoàn X hoặc đơn vị vận hành nền tảng chat.
- Phòng chuyển đổi số, CNTT hoặc bộ phận vận hành.
- Trưởng đơn vị muốn giảm bỏ sót và thời gian phối hợp công việc.

**Vì sao chấm 8/10:** Đề tài đã cung cấp một hệ sinh thái người dùng cụ thể, tốt hơn việc nhắm chung vào “mọi người dùng Internet”.

**Vì sao chưa đạt 10/10:**

- Chưa biết Tập đoàn X có bao nhiêu MAU/DAU.
- Chưa xác định nhóm nào đau nhất và nên pilot trước.
- Chưa có buyer interview hoặc quy trình phê duyệt ngân sách.
- Chưa biết nhân viên có chấp nhận cho AI đọc hội thoại hay không.

### 6.3 Value Proposition — 8/10

**Đề xuất giá trị:**

> Orbit giúp người dùng không bỏ sót công việc trong hội thoại bằng cách tự tóm tắt, phát hiện task/deadline và chuyển chúng thành reminder hoặc Calendar có xác nhận.

**Vì sao chấm 8/10:**

- Sản phẩm không chỉ trả lời câu hỏi mà tạo workflow từ thông tin đến hành động.
- Proactive detection giảm yêu cầu người dùng phải chủ động nhớ và hỏi AI.
- HITL giữ quyền quyết định cho người dùng.
- Task Inbox gom các việc cần xử lý tại một nơi.
- Accuracy riêng cho task extraction đã có bằng chứng tương đối tốt.

**Vì sao chưa đạt 10/10:**

- Chưa đo mức giảm thời gian xử lý.
- Chưa đo tỷ lệ giảm task/deadline bị bỏ lỡ.
- Chưa có retention hoặc helpfulness từ người dùng thật.
- Formal Agent acceptance mới đạt 50% và tool routing mới đạt 59,3%, làm giảm độ tin cậy của trải nghiệm tổng thể.

### 6.4 Market — 5/10

**Đánh giá:** Thị trường ban đầu tồn tại dưới dạng captive market trong hệ sinh thái Tập đoàn X, nhưng quy mô chưa được chứng minh.

**Vì sao có 5 điểm:**

- Đề tài xác định một nền tảng chat và một tập người dùng cụ thể.
- Nếu Tập đoàn X có lượng người dùng và tin nhắn đủ lớn, sản phẩm có đường phân phối nội bộ thuận lợi hơn một startup bắt đầu từ số 0.
- Nhu cầu productivity và quản lý công việc có thể lặp lại hằng ngày.

**Vì sao không cao hơn:**

- Không có số user, số nhóm, số tin nhắn/ngày hoặc số task phát sinh.
- Chưa tính TAM, SAM và nhóm có thể tiếp cận trong pilot.
- Chưa biết tỷ lệ người dùng bật quyền AI.
- Chưa có dữ liệu cho thị trường ngoài Tập đoàn X.

Điểm 5/10 không kết luận thị trường nhỏ; nó kết luận dự án **chưa có bằng chứng định lượng về thị trường**.

### 6.5 Competitors — 4/10

**Đánh giá:** Nhiều công cụ đã giải quyết từng phần của bài toán, nhưng dự án chưa phân tích cạnh tranh chính thức.

Các lựa chọn thay thế của người dùng gồm:

- Tự ghi task bằng tay từ chat.
- Dùng ChatGPT/Gemini để tóm tắt nội dung đã copy.
- Dùng Microsoft Copilot hoặc Slack AI trong hệ sinh thái tương ứng.
- Dùng Notion, ClickUp, Todoist hoặc Google Calendar để quản lý việc sau khi nhập thủ công.

**Vì sao chỉ chấm 4/10:**

- Chưa có competitor matrix.
- Chưa benchmark cùng một bộ use case.
- Chưa so sánh giá, privacy, accuracy và switching cost.
- Chưa chứng minh người dùng sẽ bỏ cách hiện tại để dùng Orbit.

Điểm này đánh giá **mức độ hiểu cạnh tranh của dự án**, không đánh giá rằng đối thủ yếu.

### 6.6 Differentiation — 7/10

**Điểm khác biệt tiềm năng:**

- Agent được gắn trực tiếp trong app chat của Tập đoàn X.
- Đọc context đã được người dùng cấp quyền thay vì yêu cầu copy thủ công.
- Chủ động phát hiện task và lịch hẹn khi tin nhắn tới.
- Kết nối liên tục giữa Chat, Task, Reminder, Calendar và Memory.
- HITL trước side effect.
- Có quản lý token và chi phí cho Admin.
- Hỗ trợ các biểu đạt thời gian tiếng Việt trong task extraction.

**Vì sao chấm 7/10:** Những điểm trên tạo ra trải nghiệm liền mạch hơn việc ghép nhiều công cụ riêng lẻ.

**Vì sao chưa cao hơn:**

- Phần lớn khác biệt là tính năng có thể được đối thủ sao chép.
- Chưa có dữ liệu độc quyền hoặc network effect.
- Chưa chứng minh accuracy tốt hơn các giải pháp thay thế.
- Yêu cầu E2E của đề tài chưa được đáp ứng đầy đủ.
- Nếu người dùng phải chuyển sang một app chat mới, switching cost có thể làm mất lợi thế tích hợp.

Lợi thế mạnh nhất về dài hạn nên là **tích hợp sâu với dữ liệu và quyền của nền tảng Tập đoàn X**, không phải chỉ là sử dụng LLM.

### 6.7 Business Model — 3/10

**Mô hình phù hợp nhất:**

1. **Sản phẩm nội bộ:** Tập đoàn đầu tư để giảm chi phí lao động và giảm bỏ sót công việc.
2. **B2B license:** Thu phí theo active user/tháng hoặc license doanh nghiệp.
3. **Private deployment:** Thu phí cao hơn cho private cloud/on-premise nếu có yêu cầu dữ liệu nghiêm ngặt.

**Vì sao chỉ chấm 3/10:**

- Chưa có mức giá.
- Chưa có billing/paywall.
- Chưa xác định budget owner.
- Chưa có willingness-to-pay.
- Chưa có sales hoặc procurement process.

Không nên chọn quảng cáo vì sản phẩm xử lý hội thoại riêng tư; quảng cáo làm giảm niềm tin và không phù hợp định vị trợ lý công việc.

### 6.8 Cost — 6/10

**Chi phí cần tính:**

```text
total_cost =
    AI API
  + application server
  + PostgreSQL/storage
  + monitoring và logging
  + Calendar integration
  + nhân sự phát triển/vận hành
  + security/compliance
  + customer support
  + marketing/sales
```

**Vì sao chấm 6/10:**

- Đã có usage log và budget control.
- Có thể đo token và request theo model/provider.
- Đã có ước tính một phần AI cost khoảng 0,417266 USD/1.000 tin nhắn theo workload giả định.
- Bài proactive 300 tin cho tín hiệu AI variable cost ban đầu khoảng 0,1125 USD/1.000 tin nếu giữ nguyên model và cơ cấu dữ liệu của benchmark.
- Có cơ chế chặn cuộc gọi LLM mới khi hết ngân sách.

**Vì sao chưa cao hơn:**

- Con số trên là ngoại suy local, không phải hóa đơn production.
- Chưa bao gồm toàn bộ AI workload.
- Usage proactive hiện gộp stage kiểm tra liên quan, stage trích xuất và calendar extractor, nên chưa phân bổ được chi phí theo từng stage.
- Chưa tính nhân sự, support, monitoring, backup và incident response.
- Chưa tính chi phí trên active user hoặc accepted AI outcome.
- Chưa biết chi phí khi tăng từ 100 lên 10.000 user.

### 6.9 Revenue — 2/10

**Đánh giá:** Chưa có bằng chứng doanh thu.

**Vì sao có 2 điểm thay vì 0:**

- Có thể hình thành mô hình B2B seat/license.
- Với sản phẩm nội bộ, có thể quy đổi năng suất thành lợi ích tài chính.

**Vì sao điểm rất thấp:**

- Không có paying user.
- Không có hợp đồng hoặc ngân sách pilot.
- Không có giá được khách hàng chấp nhận.
- Không có conversion, ARPU hoặc retention.

Nếu Orbit là sản phẩm nội bộ, chỉ số phù hợp hơn revenue là ROI:

```text
monthly_benefit =
    active_users
  × minutes_saved_per_day
  × working_days
  × labor_cost_per_minute

ROI = (monthly_benefit - monthly_cost) / monthly_cost
```

Hiện chưa có số phút tiết kiệm và chi phí lao động, nên chưa thể tính ROI thật.

### 6.10 Feasibility — 7/10

**Vì sao chấm 7/10:**

- Nhóm 4 người đã xây được backend, hai frontend, database và AI agent.
- Có Auth, Chat, Task, Reminder, Calendar, Memory, proactive flow và Admin dashboard.
- Báo cáo gần nhất ghi nhận 414/414 automated test pass.
- Browser functional E2E cho user/admin đã pass.
- Task extraction có accuracy tương đối tốt.

Những bằng chứng trên cho thấy nhóm đủ năng lực hoàn thiện MVP và chạy pilot nhỏ.

**Vì sao chưa cao hơn:**

- Release gate tổng vẫn FAIL.
- Formal Agent acceptance, đồng bộ phiên bản WebSocket staging, load gate, accessibility và Google OAuth còn vấn đề.
- Nhóm 4 người còn phải chia nguồn lực cho product, customer interview, vận hành, support và security.
- Chưa có khả năng trực 24/7 hoặc xử lý incident ở quy mô doanh nghiệp.

Kết luận feasibility:

| Mục tiêu | Khả năng của nhóm 4 người |
|---|---|
| Hoàn thiện MVP/demo | Khả thi |
| Pilot 10–20 người | Khả thi sau khi sửa lỗi P0 |
| Khoảng 100 tài khoản | Có thể với managed infrastructure và tải đồng thời thấp |
| Production toàn Tập đoàn X | Chưa đủ bằng chứng và nguồn lực |
| Vận hành 10.000 người dùng | Chưa khả thi ở trạng thái hiện tại |

### 6.11 Scalability — 3/10

**Vì sao có 3 điểm:**

- Backend sử dụng FastAPI async và PostgreSQL, là nền tảng có thể mở rộng.
- Đã có container/deployment và load-test tooling.
- Có rate limiting và budget guard để bảo vệ tài nguyên.

**Vì sao điểm thấp:**

- Load test gần nhất chỉ có 85/100 request trả 2xx; 15 request bị rate limiter trả 429. Đây không phải bằng chứng server bị sập, nhưng vẫn không đạt gate yêu cầu và chưa xác định được throughput thực tế.
- WebSocket test ghi nhận 0/5 kết nối, nhưng nguyên nhân đã xác định là backend staging lệch phiên bản với runner: staging không có `POST /api/v1/auth/ws-ticket`, runner không kiểm tra status rồi mở socket với ticket không hợp lệ, nên handshake bị từ chối 403. Kết quả này không chứng minh WebSocket không chịu được tải; nó cho thấy capacity realtime chưa được đo hợp lệ.
- Scheduler và WebSocket còn phụ thuộc process-local.
- Chưa có queue/Redis Pub/Sub cho nhiều instance.
- Chưa có capacity test theo concurrent user.
- Chưa chứng minh mức tối thiểu 10 người dùng đồng thời.

Không thể suy ra khả năng phục vụ 10.000 user chỉ từ số tài khoản. Cần đo riêng:

- DAU/MAU.
- Peak concurrent users.
- Tin nhắn/phút.
- AI request/phút.
- WebSocket connections.
- Token/user/ngày.

Lộ trình kỹ thuật sơ bộ:

| Quy mô | Điều kiện cần |
|---|---|
| 100 user | Deploy backend đồng bộ với runner, chạy lại WebSocket/rate-limit test, chứng minh 10 concurrent user và không mất task/reminder |
| 1.000 user | Nhiều API instance, Redis Pub/Sub, worker queue, DB pooling, external scheduler |
| 10.000 user | Autoscaling, tách workload realtime/AI, cache, quota nhiều provider, observability và disaster recovery |

### 6.12 Risk — 4/10

Điểm Risk phản ánh **mức độ dự án đã kiểm soát rủi ro**, không phải rủi ro thấp hay cao.

**Vì sao có 4 điểm:**

- Có HITL.
- Có authentication, authorization và consent.
- Có audit/usage log và budget guard.
- Có test false-positive và security-related behavior.

**Vì sao chưa cao hơn:**

| Rủi ro | Mức độ | Lý do |
|---|---|---|
| Product-market fit | Cao | Chưa có feedback, retention hoặc willingness-to-pay |
| AI accuracy | Cao | Agent acceptance và routing chưa đạt gate |
| Privacy/E2E | Cao | Raw context có thể đi qua external LLM; chưa đáp ứng đầy đủ E2E |
| Chi phí AI | Trung bình–cao | Tăng theo usage và phụ thuộc giá/quota provider |
| Vendor dependency | Trung bình | Phụ thuộc LLM provider, Google Calendar và cloud platform |
| Vận hành | Cao | Nhóm 4 người, chưa có trực 24/7 hoặc incident process |
| Scalability | Cao | Capacity realtime chưa được đo hợp lệ, load gate chưa pass và kiến trúc còn process-local |
| Pháp lý/compliance | Chưa đánh giá | Chưa có retention policy, DPA, quy trình xóa/xuất dữ liệu và đánh giá dữ liệu doanh nghiệp |

Formal memory isolation gate chưa đạt không tự động chứng minh đã xảy ra rò rỉ production, nhưng đủ để chưa được phép tuyên bố hệ thống an toàn ở quy mô doanh nghiệp.

## 7. Vì sao kết luận là ITERATE/PILOT

Orbit không bị đánh giá là thất bại vì:

- Bài toán và target context tương đối rõ.
- Sản phẩm đã chạy end-to-end.
- Task extraction có chất lượng tốt trên dataset hiện có.
- HITL và budget control đã được triển khai.
- Nhóm 4 người đã chứng minh khả năng xây MVP.

Orbit cũng chưa được đánh giá là GO/Scale vì:

- Chưa có người dùng thật.
- Chưa đo time saved, retention hoặc reduction in missed tasks.
- Chưa có pricing, buyer validation hoặc ROI.
- Release gate tổng vẫn FAIL.
- E2E/privacy chưa đáp ứng đầy đủ đề tài.
- Chưa chứng minh capacity tối thiểu và khả năng scale.

Do đó quyết định hợp lý nhất là **chạy pilot có kiểm soát**, không bổ sung quá nhiều tính năng mới và chưa rollout toàn Tập đoàn X.

## 8. Pilot business đề xuất

### 8.1 Quy mô

- 10–20 người dùng thật.
- 2–3 nhóm chat có nhiều task/deadline.
- Thời gian 2 tuần.
- Có baseline trước pilot ít nhất 3 ngày.

### 8.2 Dữ liệu cần thu thập

- Số phút đọc/tổng hợp chat trước và sau Orbit.
- Số task/deadline bị bỏ lỡ.
- Số summary được đánh giá hữu ích.
- Số task suggestion được Accept, Edit và Dismiss.
- Số reminder/calendar được Confirm và Reject.
- D7 retention.
- Privacy concern và false reminder report.
- Token và chi phí trên accepted outcome.

### 8.3 Gate business

| KPI | Ngưỡng đề xuất | Vì sao cần |
|---|---:|---|
| Hoàn thành ít nhất hai use case AI | ≥70% người dùng | Chứng minh activation |
| Quay lại trong tuần thứ hai | ≥50% | Chứng minh giá trị lặp lại |
| Summary/task hữu ích | ≥70% | Chứng minh chất lượng cảm nhận |
| Giảm thời gian xử lý | ≥30% | Chứng minh lợi ích năng suất |
| False reminder | <5% | Bảo vệ trust |
| Side effect có xác nhận | 100% | Gate an toàn bắt buộc |
| Critical privacy incident | 0 | Hard gate |
| Capacity | ≥10 concurrent users | Chứng minh MVP vận hành tối thiểu |
| Value/cost ratio | ≥3 lần | Chứng minh hiệu quả tài chính sơ bộ |

Nếu không đạt retention hoặc time-saving, nhóm cần điều chỉnh target segment/value proposition thay vì tiếp tục thêm tính năng.

## 9. Ưu tiên cho nhóm 4 người

1. **Product/Customer:** tuyển người pilot, phỏng vấn và đo business KPI.
2. **Backend/AI:** sửa routing, memory gate, false-positive và Calendar OAuth.
3. **Frontend/UX:** hoàn thiện onboarding, consent, feedback và accessibility quan trọng.
4. **Infrastructure/QA:** đồng bộ phiên bản staging/runner, bổ sung kiểm tra status khi lấy WebSocket ticket, chạy lại rate-limit/load test, monitoring và dữ liệu đánh giá.

Ưu tiên cao nhất không phải xây thêm module mới. Nhóm cần chứng minh rằng ba use case hiện tại — summary, task extraction và reminder/calendar có xác nhận — tạo ra giá trị thực.

## 10. Kết luận cuối

Orbit đã đáp ứng khá tốt đề tài ở mức **MVP kỹ thuật**. Sản phẩm có workflow hợp lý, nhiều chức năng chạy thật và bằng chứng accuracy tốt cho task extraction.

Tuy nhiên, Orbit chưa đáp ứng đầy đủ **business readiness** vì chưa có bằng chứng người dùng, ROI, mô hình doanh thu, production capacity và tuân thủ privacy/E2E theo yêu cầu cao nhất của đề tài.

> **Kết luận: 55/100 — ITERATE / CONTROLLED PILOT.**

Sản phẩm nên được phép pilot với nhóm nhỏ sau khi sửa các lỗi release P0. Chỉ nên rollout rộng hoặc thương mại hóa khi đã đạt gate người dùng, ROI, privacy và capacity.

## 11. Nguồn bằng chứng nội bộ

- [README.md](../README.md) — tính năng sản phẩm và hướng dẫn chạy.
- [Architecture](ARCHITECTURE.md) — kiến trúc Personal Agent và security boundary.
- [Evaluation Evidence](EVALUATION_EVIDENCE.md) — test, accuracy, latency, cost, WebSocket, load, OAuth và feedback.
- [Metrics](../eval/METRICS.md) — định nghĩa metric, benchmark và cost model.
- [WORKLOG.md](../WORKLOG.md) — lịch sử triển khai và các quyết định kỹ thuật.
