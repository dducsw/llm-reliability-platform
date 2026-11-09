## Yêu cầu kỹ thuật tối thiểu đã đáp ứng (trang 4/6)

Tick **cả 5 ô**:

- [x] MongoDB là nền tảng dữ liệu vận hành chính — mọi telemetry, SLI, incident, action, policy đều nằm trong Atlas
- [x] Có dùng Aggregation Pipeline để phân tích dữ liệu — 18 pipeline A1–A18 (`packages/reflex-mongo/reflex_mongo/pipelines/`)
- [x] Có ít nhất 1 dashboard Datadog — 4 dashboard (D1 Ops, D2 SLO, D3 Cortex, D4 Mongo), quản lý bằng Terraform
- [x] Có ít nhất 1 monitor/alert Datadog — M1–M13 (burn-rate, composite, anomaly), Terraform
- [x] Có ít nhất 1 tính năng Datadog bổ sung — APM tracing, Logs pipeline, LLM Observability, Anomaly detection

---

## Phần B — Bài toán và giải pháp

### B.1 Bài toán và người dùng *

```
VẤN ĐỀ VẬN HÀNH: Các ứng dụng dùng LLM (chatbot, trích xuất đơn hàng, tóm tắt...) phụ thuộc vào API của nhà cung cấp bên ngoài, nhưng giám sát truyền thống chỉ nhìn "sống/chết" (HTTP 5xx, uptime). LLM hỏng theo kiểu khác: vẫn trả HTTP 200, latency bình thường, nhưng nội dung bị cắt cụt, sai JSON schema, từ chối ngầm — "silent failure". Uptime monitor đều xanh trong khi người dùng nhận dữ liệu rác, và đội vận hành chỉ biết khi khách phàn nàn. Khi phát hiện được thì việc điều tra (lỗi do vendor hay do chính gateway?) và xử lý (chuyển tải, rollback) vẫn làm thủ công, mất hàng chục phút, phải nhảy qua nhiều công cụ.

AI ĐƯỢC HƯỞNG LỢI:
- Đội SRE/On-call: tự động phát hiện -> điều tra -> xử lý -> chứng minh đã hồi phục; giảm MTTD/MTTR và giảm báo động nhiễu (burn-rate nhiều cửa sổ, gộp alert trùng).
- Đội phát triển/sản phẩm dùng LLM (ví dụ ứng dụng thương mại điện tử ShopMate): chỉ cần đổi base_url sang gateway tương thích OpenAI là có retry, failover, kiểm định chất lượng; người dùng cuối vẫn nhận đúng kết quả khi một vendor suy giảm (Delivered quality 100% khi Provider quality chỉ 67,9% trong kịch bản thử).
- Quản lý/FinOps: thấy rõ SLO, error budget và chi phí theo từng route/vendor để thương lượng với nhà cung cấp và chọn model.
```

### B.2 Giải pháp và tính năng chính *

```
Reflex là AI Gateway + nền tảng vận hành vòng kín (Dual-Loop) đặt giữa ứng dụng và các LLM vendor.

NGUỒN DỮ LIỆU: mọi request/lần gọi vendor thực đi qua gateway (kèm canary probe mỗi 15 giây gọi thẳng vendor để tách lỗi vendor và lỗi gateway); dataset công khai Jwrede/llm-bench-data (CC0) làm baseline; chaos-proxy chèn lỗi có kiểm soát để kiểm thử.

THU THẬP & XỬ LÝ:
- Gateway (Fast Loop) định tuyến, circuit breaker, retry/hedge, và kiểm định chất lượng ngay trong luồng (JSON schema, finish_reason, truncation) — overhead ~2-4 ms, telemetry đẩy bất đồng bộ qua hàng đợi nên không chặn request.
- MongoDB Atlas là nền tảng dữ liệu chính: Time Series lưu telemetry, 18 aggregation pipeline (rollup $merge, burn-rate nhiều cửa sổ, EWMA/z-score, chẩn đoán provider vs gateway...), Change Streams hot-reload policy < 1s, Vector Search làm bộ nhớ sự cố, Atlas Search tìm postmortem.
- Datadog: APM, DogStatsD metrics, Logs, LLM Observability, 4 dashboard, 13 monitor, 4 SLO — toàn bộ quản lý bằng Terraform.

CẢNH BÁO & HÀNH ĐỘNG:
- Phát hiện bằng hai detector độc lập (Sentinel trên Mongo + Datadog Monitor, burn-rate đa cửa sổ), gộp thành một incident nhờ dedup_key.
- Cortex (AI SRE agent) điều tra bằng các công cụ chỉ-đọc, đưa giả thuyết kèm bằng chứng và đề xuất hành động an toàn; Policy Engine kiểm guardrail (tự duyệt hoặc chờ người duyệt trên Console); gateway áp policy mới ngay.
- Verifier chứng minh hồi phục bằng Wilson CI + z-test rồi mới đóng incident, failback 10% -> 50% -> 100%.
- Reflex Console (React, SSE thời gian thực): sơ đồ mạng, War Room, duyệt action, Time Machine tua lại sự cố.

KẾT QUẢ ĐẠT ĐƯỢC (đo thật, kịch bản silent-brownout): phát hiện ~80 giây; từ mở incident đến mitigated ~131 giây; người dùng nhận 601/601 request đúng (100%) dù vendor chỉ đạt 67,9%; Time Machine mô phỏng trên sự cố thật cho Reflex 99,95% so với static failover 93,08%; load test 50 rps x 30 phút: 90.000/90.000 thành công, overhead p99 4,0 ms.
```

### B.3 Điểm sáng tạo hoặc thách thức kỹ thuật

```
ĐIỂM SÁNG TẠO
- Đo "chất lượng", không chỉ "sống/chết": Quality SLI kiểm ngay trong luồng stream để bắt silent failure; tách Delivered SLO (người dùng nhận được) khỏi Provider SLO (nhà cung cấp hứa) — chứng minh gateway nâng độ tin cậy từ ~68% lên 100% trong kịch bản thử.
- Vòng kín có an toàn: AI chỉ đề xuất, luật cứng (Policy Engine) mới quyết định; mọi kết luận của Cortex dựa trên bằng chứng đọc từ Mongo/Datadog (log/trace được bọc là "untrusted data" chống prompt injection); nếu LLM sập thì tự chuyển sang rule-based.
- Chứng minh hồi phục bằng thống kê (Wilson CI, two-proportion z-test) thay vì "nhìn biểu đồ thấy ổn", rồi failback từng bậc.
- Incident Memory: chữ ký sự cố 64 chiều (16 khung x 4 chỉ số) + Atlas Vector Search để tìm sự cố tương tự trong quá khứ.
- Time Machine: dựng World Model từ telemetry thật bằng aggregation và replay sự cố để so sánh các chính sách (static failover vs Reflex) kèm sai số hiệu chuẩn (0,58 điểm %).
- Nhiều tính năng MongoDB + Datadog phối hợp: Time Series + $merge + TTL, Change Streams có resume token, Vector/Atlas Search; APM, LLM Observability, Events, composite monitor chẩn đoán "provider-side vs gateway-side".

THÁCH THỨC KỸ THUẬT ĐÃ GIẢI QUYẾT
- Giữ overhead gateway thấp (~2-4 ms) trong khi vẫn kiểm định chất lượng: chỉ kiểm cấu trúc trên luồng, cache policy trên RAM, telemetry bất đồng bộ; Mongo/Datadog sập vẫn không làm gateway ngừng chạy.
- Time Series collection không hỗ trợ Change Streams: tách dữ liệu nóng (Time Series) và collection vận hành thường (policies, incidents, actions) để watch; hot-reload policy < 1s có integration test.
- Chống trùng/race khi nhiều nguồn cảnh báo cùng mở một incident: dedup_key + partial unique index, $merge idempotent, lease collection cho leader election.
- Phát hiện nhanh nhưng ít báo động giả: burn-rate đa cửa sổ (dài + ngắn), hai detector độc lập và cảnh báo khi hai detector bất đồng (M12).
- Tách lỗi vendor và lỗi gateway: canary probe gọi trực tiếp vs qua gateway, kết hợp composite monitor M9/M10.
- Mô phỏng sự cố trung thực: chaos-proxy chèn lỗi truncate/TTFT có seed để tái lập; mọi bản ghi mô phỏng gắn meta.synthetic=true.
```

---

## Phần C — Kiến trúc và MongoDB

### C.1 Link sơ đồ kiến trúc *

```
<<LINK ảnh architecture.png>> https://drive.google.com/file/d/1lDqqqAdpC2TbMG-3XJApTKZWfl-EANvu/view?usp=sharing
```

### C.2 Mô tả kiến trúc và luồng dữ liệu

```
Reflex là một AI Gateway đứng giữa ứng dụng (ví dụ: ShopMate) và các nhà cung cấp LLM, hoạt động theo cơ chế Dual-Loop (chia làm hai luồng: Xử lý nhanh và Quản lý chậm) để đảm bảo hệ thống luôn thông minh, chịu lỗi tốt và tự động phục hồi. Hai luồng của của Reflex là:

1. Fast Loop (Data Plane - Luồng xử lý nhanh)

- Nhiệm vụ: Nhận request từ app, định tuyến, kiểm tra circuit breaker, gọi LLM vendor (hoặc qua chaos-proxy để test lỗi/mock).
- Kiểm tra chất lượng ngay lập tức: Gateway validate response ngay trên luồng (kiểm tra JSON schema, lỗi cụt chữ/silent failure). Nếu hỏng, nó tự động retry hoặc failover sang vendor khác.
- Tốc độ: Tối ưu tối đa, không chờ ghi Database hay Datadog. Telemetry được đẩy qua hàng đợi ngầm, cache nằm sẵn trên RAM.

2. Slow Loop (Control Plane + Cortex - Luồng quản lý & AI SRE)
Hệ thống tự động vận hành qua 5 bước:

- Telemetry (Thu thập): Ghi log/metric vào MongoDB Time Series và đẩy sang Datadog. Prober bắn canary mỗi 15 giây để phân biệt lỗi do nhà mạng hay do gateway.
- Detect (Phát hiện lỗi): Sentinel (control plane) tính toán tỷ lệ lỗi (burn-rate), kết hợp với Datadog Monitor để bắn cảnh báo. Các nguồn lỗi được gom chung, chống trùng lặp (dedup_key).
- Investigate (Điều tra bằng AI): AI SRE agent (Cortex) phân tích sự cố, tìm kiếm các lỗi tương tự bằng Vector Search trên MongoDB, tra cứu log/metric qua các công cụ đọc. Mọi kết luận đều dựa trên trạng thái thực tế.
- Respond & Verify (Xử lý & Xác thực):
+ Cortex đề xuất các hành động an toàn (như ngắt mạch, chuyển tải, điều chỉnh trọng số).
+ Policy Engine kiểm tra lại bằng luật cứng (tự động hoặc cần người duyệt).
+ Gateway cập nhật chính sách mới (hot-reload chưa tới 1 giây).
+ Hệ thống dùng thuật toán thống kê (Wilson CI, z-test) để chứng minh đã hồi phục rồi mới đóng sự cố, sau đó tăng dần traffic lại (10% -> 50% -> 100%).
- UI (Giao diện): Reflex Console (React) nhận dữ liệu thời gian thực qua Server-Sent Events (SSE) để hiển thị sơ đồ mạng, phòng chiến sự (War Room), duyệt action và tính năng "Time Machine" để tua lại lịch sử sự cố.

Thành phần phụ thuộc: MongoDB Atlas và Datadog (agent + SaaS) là bắt buộc, một LLM API cho Cortex (cấu hình qua biến môi trường). Nếu Mongo hoặc Datadog sập: Gateway vẫn chạy bình thường nhờ cache chính sách trên RAM. Nếu AI Cortex sập: Hệ thống tự động chuyển sang chế độ rule-based dựa trên luật có sẵn.
```

### C.3 Triển khai MongoDB *

```
Triển khai: MongoDB Atlas (môi trường demo; chạy được cả trên cluster M0 512MB và atlas-local Docker cho dev/CI). Driver PyMongo async. Bootstrap idempotent bằng `task migrate`/`task seed`.

DATA MODEL phân tầng theo "nhiệt độ":
- HOT — 4 Time Series collection tách riêng theo tần suất & metaField: requests_ts (góc nhìn người dùng/Delivered SLO, meta.route), attempts_ts (từng lần gọi vendor/Provider SLO, meta.target), probes_ts (canary direct vs via-gateway), bench_ts (baseline từ dataset công khai, granularity hours). TTL 14 ngày cho 3 collection đầu.
- WARM — sli_1m (TTL 45 ngày), sli_1h (TTL 400 ngày), baselines: rollup bằng $merge.
- OPERATIONAL — targets, slos, policies (+policy_history), health_state, incidents, investigations, actions, postmortems, replays, chaos_runs, leases, stream_checkpoints.

AGGREGATION PIPELINE (Hệ thốn 18 pipeline A1–A18, mỗi pipeline đều có test): A1–A3 rollup $merge; A4 multi-window burn-rate tính một lượt quét cho mọi SLO; A5 error budget; A6 EWMA/z-score ($setWindowFields); A7 probe blindness; A8 first-bad timestamp; A9 signature vector 64D (16 khung x 4 chỉ số); A10 similar incidents ($vectorSearch); A11 chẩn đoán provider vs gateway; A12 top error contributors; A13 blast radius; A16 recovery-proof; A17 MTTx; A18 chi phí. Time Machine dựng World Model từ attempts_ts/probes_ts bằng aggregation.

INDEX: compound index theo meta + ts cho Time Series; unique compound (scope,key,env,ts) trên sli_1m để $merge idempotent; partial unique index incidents.dedup_key {is_open: true} chống mở trùng incident; TTL index; JSON Schema validator cho policies/incidents/actions.

TÍNH NĂNG KHÁC:
- Change Streams (có resume token lưu ở stream_checkpoints) trên policies, incidents, actions, health_state, chaos_runs: hot-reload policy < 1s (có integration test), Cortex bị kích hoạt khi có incident, SSE cho Console. Thiết kế tuân thủ giới hạn "Time Series không hỗ trợ Change Streams" nên chỉ watch collection thường.
- Atlas Vector Search: index incident_signature (64D, cosine, filter theo sli/scope/status) làm Incident Memory.
- Atlas Search: index postmortems_text để tìm full-text postmortem.
- Time Series + TTL + $merge cho vòng đời dữ liệu; leases collection cho leader election job định kỳ.
```

---

## Phần D — Datadog và kịch bản sự cố

### D.1 Triển khai Datadog *

```
NGUỒN TELEMETRY (unified service tagging: env, service, version, route, target, incident_id):
- APM/Tracing: ddtrace trên gateway, control-plane, cortex — span theo từng attempt (retry_reason, hedge), liên kết log↔trace.
- Metrics: DogStatsD, namespace reflex.* (request.latency, attempt.ttft, quality.pass/total, retry.amplification, cost.usd, probe.result, incident.open, telemetry.dropped, cortex.*).
- Logs: structlog JSON -> Datadog Agent; custom log pipeline + log-based metric theo finish_reason.
- LLM Observability: ml_app reflex-cortex — span agent -> workflow -> tool -> llm cho mỗi investigation.
- Events API: "policy applied", "Recovery Proof PASS" phủ lên mọi graph.

MONITORS (Terraform, infra/terraform): M1/M2 SLO burn-rate availability (fast/slow), M3 provider-quality fast burn (2 cửa sổ dài+ngắn + composite), M4 TTFT burn, M5 anomaly TTFT p99, M6 probe silence (no-data), M7 retry amplification, M8 cost anomaly, M9/M10 composite chẩn đoán "provider-side" vs "gateway-side" (M3 & probe direct fail), M11 telemetry dropped, M12 detector disagreement, M13 sức khỏe Cortex. Webhook (header bí mật) đẩy alert + tag diagnosis vào control-plane.

SLOs: 4 SLO (delivered availability, delivered quality, delivered latency, provider quality) — tách "Delivered SLO" (người dùng nhận được) khỏi "Provider SLO" (nhà cung cấp hứa).

DASHBOARDS (4, as code): D1 Operations (bố cục Detect -> Investigate -> Respond, widget "Delivered vs Provider"), D2 SLO & Error Budget, D3 Cortex/LLMObs, D4 MongoDB engine metrics.

Toàn bộ monitors/SLOs/dashboards/webhook tạo bằng Terraform (`task infra:datadog:apply`), tái lập được trên môi trường mới.
```

### D.2 Kịch bản sự cố: Phát hiện -> Điều tra -> Xử lý *

```
Sự cố: "Silent Brownout" — vendorA:large vẫn trả HTTP 200, latency bình thường, nhưng ~35% response của route order.extract bị cắt cụt/sai JSON schema (chaos-proxy bật fault truncate p=0.35 + TTFT +180ms). Uptime monitor đều xanh; chỉ Quality SLI thấy lỗi.

PHÁT HIỆN
- Tín hiệu: Quality SLI của vendorA:large|order.extract tụt, burn-rate vượt 14.4x trên cả cửa sổ dài và ngắn (profile demo: 3m/30s). Hai detector độc lập: Sentinel (aggregation A4 trên Mongo, chu kỳ 10s) và Datadog Monitor M3. Hai nguồn gộp thành 1 incident nhờ dedup_key + partial unique index. Trong lúc đó gateway đã tự retry quality-aware sang vendorB nên người dùng chưa bị ảnh hưởng nhiều.

ĐIỀU TRA
- Composite M9 = M3 & probe gọi thẳng vendorA cũng hỏng -> chẩn đoán provider-side (không phải lỗi gateway).
- Cortex nhận incident qua Change Stream và điều tra bằng 9 lần gọi tool chỉ-đọc (lần chạy thật): mongo.probes_compare, mongo.top_contributors, dd.logs_search, dd.spans_search, memory.similar (Atlas Vector Search tìm incident tương tự), mongo.policy_timeline, memory.postmortem_search (Atlas Search), mongo.sli_window. Giả thuyết H1 (độ tin cậy 0,78): vendorA:large sinh output bị cắt (finish_reason=length) làm fail validator no_truncation và json_schema; probe direct và via-gateway cùng đạt 0,977 nên gateway không phải nguồn lỗi (H2, 0,15, bị loại). Mỗi giả thuyết kèm tham chiếu bằng chứng; toàn bộ chuỗi suy luận xem được trong Datadog LLM Observability (dashboard D3).

XỬ LÝ
- Cortex đề xuất shift_weight(order.extract, vendorA:large -> vendorB:large, 40% trong 900s). Policy Engine kiểm guardrail và tự duyệt (auto) vì đủ độ tin cậy; nếu độ tin cậy thấp thì action chuyển awaiting_approval để người duyệt trên Console. Actuator ghi policy version mới vào Mongo -> Change Stream -> mọi gateway hot-reload < 1s; Datadog Event "policy applied" phủ lên dashboard.
- (Biến thể: kịch bản "It's Us" — probe direct bình thường nhưng via-gateway chậm -> M10 gateway-side -> đề xuất rollback_flag cần người duyệt.)

CHỨNG MINH HỆ THỐNG TRỞ LẠI BÌNH THƯỜNG
- Verifier so SLI trước/sau bằng Wilson CI + two-proportion z-test: lần chạy thật cho verdict PASS (quality sau khi áp policy 100%, khoảng Wilson 95% = [0,904; 1,0]; mẫu nhỏ nên khoảng tin cậy rộng) -> Datadog Event Recovery Proof. Sau đó failback theo bậc 10% -> 50% -> 100%, mỗi bước có gate; bước failback cần người duyệt khi baseline dưới ngưỡng. Incident chuyển resolved khi hoàn tất, Cortex soạn postmortem và lưu signature vào Incident Memory.
- Time Machine replay trên chính sự cố: so sánh policy "static failover" (chỉ failover khi 5xx) với Reflex (xem số ở D.4).
```

### D.3 Link dashboard Datadog hoặc ảnh chụp màn hình *

```
Dashboard D1 Operations: <<LINK dashboard công khai / shared link>> https://drive.google.com/file/d/1bihJihLBy2mSYHMUhd4g-9Afr1XK5b4d/view?usp=drive_link
Dashboard D2 SLO & Error Budget: <<LINK>> https://drive.google.com/file/d/1vQrbl9532Jjw7GkO4EnveyxFzfbtEYGt/view?usp=drive_link
Dashboard D3 Cortex LLMObs: <<LINK>> https://drive.google.com/file/d/1yVR4-aW_MCpsZOeT4qEM8-gvU1-gzPZn/view?usp=drive_link
Dashboard D4 MongoDB engine: <<LINK>> https://drive.google.com/file/d/1GOZTgC3ueaISe1rSz493arwql7tY00ty/view?usp=drive_link

```

> Nếu link dashboard cần đăng nhập: dùng Datadog "Share dashboard -> public URL", hoặc đưa link ảnh trên (repo phải mở được) / upload ảnh lên Drive.

### D.4 Kết quả đo được

```
1) Kịch bản silent-brownout (--fast, lỗi truncate 35% + TTFT +180ms lên vendorA:large trong 3 phút, seed 42):
   - Phát hiện: lỗi đầu tiên 07:46:50 -> Sentinel mở incident 07:48:10 (sấp xỉ 80 giây). Datadog Monitor M3 chuyển Alert (runner xác nhận <=150s).
   - Điều tra -> xử lý: Cortex (9 tool call, độ tin cậy 0,78) kết luận provider-side; action shift_weight tự duyệt; từ lúc mở incident đến mitigated sấp xỉ 131 giây. Verifier cho Recovery Proof PASS.
   - Bảo vệ người dùng: route order.extract nhận 601 request trong 3 phút lỗi; 193 request (32,1%) có lần gọi đầu hỏng và được quality-retry cứu. Delivered quality = 601/601 (100%) trong khi Provider quality của lần gọi đầu = 408/601 (67,9%).
   - Overhead gateway sấp xỉ 1,6 ms (smoke test).
2) Time Machine (MÔ PHỎNG, replay dữ liệu thật từ Atlas, nhiều seed) trên sự cố INC-202610300552-4a9b57: Delivered thực tế 99,37%; app gọi thẳng vendor 92,44%; static failover 93,08% (155 request hỏng, đốt hết budget); Reflex 99,95% (sấp xỉ 1 request hỏng, đốt 5,5% budget, +~$0,39). Sai số hiệu chuẩn 0,58 điểm %. Tắt quality retry thì Reflex rơi về mức static failover.
3) Hot-reload policy qua Change Stream < 1 giây (integration test khẳng định < 1,0s).
4) Load test 50 rps x 30 phút trên Atlas M0 (ghi trong handover 27/10): 90.000/90.000 request thành công; overhead gateway p50/p95/p99 = 2,3 / 3,4 / 4,0 ms; ~5,4 MB lưu trữ / 100.000 request.
```

---

## Phần E — Mã nguồn, tài liệu và demo

### E.1 Link repository mã nguồn *

```
https://github.com/dducsw/llm-reliability-platform
(Nếu private: đã cấp quyền đọc cho tài khoản giám khảo do BTC cung cấp.)
```

### E.2 Link README / hướng dẫn cài đặt *

```
https://github.com/dducsw/llm-reliability-platform/blob/main/README.md
```

### E.3 Link video demo *

```
<<LINK video demo>> https://drive.google.com/file/d/1ZPUA3hM5iwwP9qEYgAqIisY4ddTL1YfD/view?usp=sharing
```

### E.4 Link slide thuyết trình

```
<<LINK Google Slides / PDF>>
(Nguồn trong repo: docs/submission/slide.md, bản web: docs/submission/slide.html)
```

### E.5 Link demo trực tiếp

```
<<LINK demo nếu có (không điền tài khoản/mật khẩu vào form)>>
Nếu không có bản host công khai: để trống hoặc ghi "Chạy local bằng `task up` theo README; xem video demo".
```

### E.6 Khai báo thành phần tái sử dụng, dataset và công cụ AI *

```
THƯ VIỆN/CODE CÓ SẴN (open source): FastAPI, Uvicorn, httpx, Pydantic v2, PyMongo, structlog, fastjsonschema, scipy/numpy (Wilson CI, z-test), ddtrace + datadog (DogStatsD), React, Vite, TanStack, Tailwind, shadcn/ui, Apache ECharts, Terraform Datadog provider, Task, uv, Docker. Giấy phép MIT/BSD/Apache-2.0/MPL-2.0. Router, circuit breaker, retry/hedge, validator, SLI/burn-rate, Time Machine, Cortex agent do nhóm tự viết (không dùng LiteLLM/Portkey hay template gateway có sẵn).

DATASET BÊN NGOÀI: `Jwrede/llm-bench-data` (CC0 1.0) — nạp vào bench_ts làm baseline/hình dạng sự cố lịch sử, không chứa PII.
DỮ LIỆU TỰ TẠO: prompt ShopMate, mock-llm output, kịch bản chaos (scenarios/, seeds/); mọi bản ghi mô phỏng gắn meta.synthetic=true.

LLM TRONG SẢN PHẨM: Cortex gọi LLM qua API (model cấu hình bằng biến môi trường CORTEX_MODEL; demo dùng LLM_BASE_URL/LLM_MODEL trong .env — hiện cấu hình DeepSeek). Dữ liệu gửi LLM là telemetry tổng hợp, không có nội dung người dùng; log/trace được bọc là "untrusted data" chống prompt injection.
CÔNG CỤ AI HỖ TRỢ PHÁT TRIỂN: Claude Code (rà soát, viết test, chuẩn hóa tài liệu). Nhóm hiểu và giải thích được toàn bộ giải pháp.
HẠ TẦNG: MongoDB Atlas, Datadog (trial), LLM vendor API.
```

### E.7 Hạn chế và hướng phát triển

```
HẠN CHẾ
- Kiểm định chất lượng in-flight mới ở mức cấu trúc (JSON schema, finish_reason, truncation, từ chối ngầm); chưa kiểm đúng sai ngữ nghĩa sâu để giữ overhead gateway thấp.
- Trạng thái circuit breaker nằm trong RAM từng gateway; mở rộng hàng chục node cần lớp chia sẻ trạng thái.
- Cortex phụ thuộc LLM ngoài (vài giây mỗi investigation); dưới 1 giây dựa vào luật cứng ở Fast Loop. Bộ đánh giá Cortex (`task cortex:eval`) mới có ground truth đầy đủ cho kịch bản silent-brownout.
- Guardrail yêu cầu người duyệt bước failback đầu tiên khi baseline chất lượng dưới ngưỡng -> incident không tự `resolved` hoàn toàn; đây là chủ ý an toàn nhưng làm vòng khép kín cần 1 thao tác của người.
- Dữ liệu demo là synthetic + fault chèn; Time Machine chỉ biết hành vi target ở thời điểm có traffic (đã hiển thị độ tin cậy và sai số hiệu chuẩn). SLO profile demo dùng cửa sổ rút ngắn.
- Một số cửa sổ Datadog (SLO 6h) chỉ tồn tại ở Sentinel vì Datadog SLO chỉ hỗ trợ 7d/30d/90d.

HƯỚNG PHÁT TRIỂN
- Hướng phát triển gần: Helm chart/K8s + autoscaling theo metric Datadog; embedding nhỏ chạy cục bộ (ONNX) cho kiểm tra ngữ nghĩa nhẹ ở gateway; hoàn thiện ground truth + eval cho cả 6 kịch bản. Cortex tự lưu trữ (model mã nguồn mở qua vLLM); adapter cho LangChain/LlamaIndex/LiteLLM; chia sẻ health state giữa gateway.
- Dài hạn: định tuyến đa vùng active-active với Atlas Global Clusters.
```
