# Review thiết kế v1 — Lỗi logic & cải tiến trước khi code

> Bản v1 đã sửa được các lỗi của v0 ([draft-review](draft-review.md)). Tài liệu này rà lại v1 bằng cách **chạy nhẩm scenario chính (S1) qua đúng công thức trong tài liệu**. Kết quả: có 4 lỗi khiến S1 không chạy như timeline mô tả. Không lỗi nào làm đổi kiến trúc, nhưng nếu không sửa thì ngay buổi chạy thử đầu tiên số liệu sẽ khác hẳn kịch bản.
>
> Mức độ: 🔴 làm hỏng demo chính · 🟠 sai kỹ thuật, giám khảo có thể bắt lỗi · 🟢 cải tiến chất lượng.
>
> Các mục đánh dấu **[đã sửa trong docs]** đã được cập nhật trực tiếp vào tài liệu gốc. Các mục còn lại là task trong [team-plan](../70-delivery/team-plan.md).

---

## 1. Lỗi làm hỏng scenario chính

<a id="f1"></a>
### F1 🔴 Provider quality SLI bị pha loãng ở scope `target` — M3 không bao giờ bắn [đã sửa trong docs]

**Chạy nhẩm:** fault của S1 chỉ áp lên `order.extract` × `vendorA:large`. Nhưng `vendorA:large` còn phục vụ cả `chat.reply`, và route này cũng có validator (`refusal_pattern`, `lang:vi`), tức là cũng nằm trong `q_eligible`. Với mix 0.5 / 0.35 / 0.15, tỉ lệ quality bad của *target* chỉ còn khoảng `0.35 × (0.35 … 0.41) ≈ 12–14%` (tùy `ticket.summarize` có đi qua `vendorA:large` hay không), nên burn ≈ 12–14 < 14.4. **Monitor M3 và Sentinel không bao giờ vượt ngưỡng page.** Tệ hơn, nếu fault rơi vào route có ít traffic thì sự cố bị che hoàn toàn.

**Sửa:** thêm scope thứ ba `target_route` (key `vendorA:large|order.extract`) cho `sli_1m`/`sli_1h` và cho Provider SLO. A1 group thêm một lần theo `(target, route)`. Monitor M3 group by `{target, route}`; metric vốn đã có cả hai tag nên không tăng cardinality. Như vậy `dedup_key = sha1(slo_id|target|route)` khớp tự nhiên với scope này.

<a id="f2"></a>
### F2 🔴 `quality_fail` bị tính là lỗi availability [đã sửa trong docs]

**Chạy nhẩm:** trong A1, `ok = (outcome == "ok")`. Attempt bị cắt cụt có `outcome: "quality_fail"`, nên nó vừa là quality-bad vừa là **availability-bad**. Hệ quả trong S1:
- Availability burn cũng tăng, làm M1 có thể bắn. Composite M10 (`M1 ∧ ¬P_direct ∧ P_via_gw`) có thể ra chẩn đoán sai.
- Kênh `c1` của signature vector khác 0, nên S1 "trông giống" một vụ outage và Incident Memory recall sai.
- Mâu thuẫn với chính định nghĩa ở [slo §2](../50-reliability/slo-and-error-budget.md): quality valid = `ok ∧ có validator`. Nếu `quality_fail ∉ ok` thì attempt hỏng **không bao giờ** nằm trong mẫu số quality.

**Sửa:** định nghĩa thống nhất: **availability = có nhận được response; quality = response dùng được.** Trong A1/A2: `served = outcome ∈ {ok, quality_fail}`, availability good = `served`, quality valid = `served ∧ có validator`, quality good = `quality.pass`.

<a id="f3"></a>
### F3 🔴 Retry budget 10% chặn quality retry — Delivered không thể giữ 99% [đã sửa trong docs]

**Chạy nhẩm:** S1 làm hỏng 35% response của `order.extract` trên target chính. Để cứu hết thì cần khoảng 35% request được retry, nhưng [recovery-engine §1.3](../50-reliability/recovery-engine.md) giới hạn retry ≤ 10% request mỗi route. Breaker không mở được (`0.35 × 0.5 = 0.175 < 0.5`). Vậy trong ~2 phút trước khi actuator kịp hành động, Delivered quality chỉ vào khoảng 75–80%, không phải 99,4%. Done-criteria của P4 (*"Delivered ≥ 99% ngay cả khi chưa có control plane action"*) mâu thuẫn với chính tham số trong tài liệu.

**Sửa:** tách hai loại budget, vì hai rủi ro khác nhau:

| Budget | Áp cho | Rủi ro cần chặn | Đơn vị |
| :--- | :--- | :--- | :--- |
| `retry.budget_ratio` (10%) | Retry do lỗi transient (5xx, timeout, 429) | Thundering herd lên vendor đang quá tải | Số request |
| `rescue` (mới) | Quality retry **sang target khác** | Chi phí tăng vọt | **Chi phí**: `max_extra_cost_ratio` (mặc định 0.6 cho route P0 non-stream) |

Quality retry không dồn thêm tải lên vendor đang hỏng (nó đi sang target khác), nên giới hạn đúng là tiền chứ không phải số lần. Thêm nữa, thành phần `Q(t)` trong router dùng EWMA *theo (target, route)* với half-life ngắn (~5s). Nhờ đó gateway tự giảm traffic về target hỏng trong vài giây, trước cả khi Cortex vào cuộc.

<a id="f4"></a>
### F4 🔴 Timeline phát hiện của S1 không khớp toán burn rate [đã sửa trong docs]

**Chạy nhẩm** (sau F1, fault 35%, objective 99%, budget 1%, burn bão hòa = 35):
- Với profile demo cũ (page = 5m/1m): cửa sổ dài vượt 14.4 khi phần xấu chiếm `14.4/35 = 41%` của 5 phút, tức **≈ T+2m04s**. Cộng thêm tick 10s, và với Datadog là `evaluation_delay` 30s, ra khoảng T+2m40s. Timeline cũ ghi Sentinel ở T+30s và M3 ở T+60s; cả hai đều không thể xảy ra.

**Sửa:**
- Profile demo **page = 3m / 30s** (tỉ lệ long/short ≈ 6). Cửa sổ ngắn ≤ 1 phút được tính **trực tiếp trên raw TS**, dùng `$dateTrunc` với `binSize: 10, unit: "second"`. Lượng dữ liệu nhỏ (8 rps × 60s) và vẫn bucket-skip theo `meta`. Cửa sổ dài vẫn lấy từ `sli_1m`.
- Kết quả tính được: Sentinel mở incident ở **≈ T+80s**, Datadog M3 ở **≈ T+1m50s**. Từ đây có luôn một câu chuyện tốt cho pitch: *detector nằm cạnh dữ liệu phát hiện trước Datadog khoảng 30s; ADR-0004 đo được chênh lệch này.*
- Thêm `tools/burn_calc.py`: từ (fault %, objective, windows, rps) tính ra thời điểm alert theo lý thuyết. `expectations` trong scenario YAML lấy số từ công cụ này thay vì đoán. Một unit test giữ cho timeline trong docs không bị lệch khỏi toán.

---

## 2. Lỗi kỹ thuật giám khảo có thể bắt

<a id="f5"></a>
### F5 🟠 SLO wildcard `target:*:quality` không join được trong A4 [đã sửa trong docs]
A4 `$lookup` theo `key`, nhưng document seed có key là `*`. **Sửa:** `slos` lưu dạng *template* (`template: true`) và migrate/seed **materialize** ra một document cho mỗi target, mỗi target × route (`template_id` trỏ về template). Khi thêm target mới thì job `slo:expand` sinh SLO tương ứng.

<a id="f6"></a>
### F6 🟠 Recovery Proof đo sai đại lượng trong S1 [đã sửa trong docs]
Sau F3, Delivered quality *đã* ≈ 99% trước khi có action, vì rescue đã cứu. So sánh Delivered trước và sau action gần như luôn PASS, nên **không chứng minh được action có tác dụng**. Giá trị thật của `shift_weight` trong S1 là **bỏ sự phụ thuộc vào rescue**: rescue rate giảm, chi phí giảm, latency giảm (bớt một vòng gọi).

**Sửa:** Verifier kiểm định ba đại lượng và ghi cả ba:
1. **No-regression:** Delivered SLI ≥ objective (Wilson CI_low).
2. **Primary health:** quality của *primary attempt* trên route (scope `target_route` của target đang nhận traffic chính) ≥ objective.
3. **Rescue dependency:** rescue rate sau action giảm có ý nghĩa thống kê so với trong sự cố (two-proportion test).

`PASS = (1) ∧ ((2) ∨ (3))`. Slide có thêm một câu: *"Reflex mua thời gian, Cortex gỡ bỏ nhu cầu phải cứu."*

<a id="f7"></a>
### F7 🟠 Datadog SLO không có cửa sổ 6h [đã sửa trong docs]
Datadog SLO chỉ có timeframe 7d / 30d / 90d. Profile demo 6h vì vậy chỉ tồn tại ở Sentinel. **Không ảnh hưởng burn rate alert** (burn là tỉ lệ), nhưng widget "budget remaining" của Datadog sẽ hiển thị theo 7d. **Sửa:** dashboard D2 so sánh dual-ledger theo **good/total trên cùng khoảng thời gian** (rate), không so budget. Ghi chú này vào [monitors-and-slos](../40-observability/monitors-and-slos.md) khi viết Terraform.

<a id="f8"></a>
### F8 🟠 Datadog trial 14 ngày < thời gian chấm (đến 22/11)
Trial tạo trong tuần đầu build sẽ hết hạn trước vòng chung kết. **Sửa:**
- Org A (trial của thành viên 1) dùng để dev từ bây giờ.
- Org B (trial của thành viên 2) tạo khoảng 3–4 ngày trước hạn nộp và chỉ dùng cho demo và chấm điểm. Nhờ Terraform ([ADR-0007](../20-architecture/adr/0007-observability-as-code.md)) nên dựng lại chỉ là một lệnh `apply`.
- Hỏi BTC về tài khoản sponsor. Quay video và chụp dashboard ngay từ G1.

<a id="f9"></a>
### F9 🟢 A8 hard-code quality
`bad` trong A8 chỉ xét quality. **Sửa:** sinh pipeline theo `sli` của SLO, giống cách A4 được sinh.

<a id="f10"></a>
### F10 🟢 Hai khái niệm thang thời gian chồng nhau [đã sửa trong docs]
`time_scale = 720` và "profile demo" cùng tồn tại ở [incident-scenarios §0](../10-product/incident-scenarios.md). **Sửa:** chỉ giữ **profile** (`standard`, `demo`). Nhãn "DEMO TIME" hiển thị tên profile và các cửa sổ của nó.

<a id="f11"></a>
### F11 🟢 Sơ đồ thiếu `attempts_ts` [đã sửa trong docs]
Mermaid ở [system-architecture](../20-architecture/system-architecture.md) và [data model §1](../30-data/mongodb-data-model.md) chỉ vẽ `requests_ts · probes_ts · bench_ts`. Cần bổ sung `attempts_ts` cho đúng với bảng.

---

<a id="improvements"></a>
## 3. Cải tiến quy trình và chất lượng

| # | Cải tiến | Vì sao | Ở đâu |
| :--- | :--- | :--- | :--- |
| I1 | **`reflex-core` pure ngay từ đầu** (clock và rng inject từ commit đầu tiên của router/breaker/retry) | Bỏ hẳn bước refactor 8.1; Time Machine dùng được code ngay khi router xong | SE-4.x |
| I2 | **Fixture generator** sinh `attempts_ts`/`requests_ts` có seed, dùng cùng `events.py` | DE viết và test toàn bộ pipeline **không cần chờ gateway**; cũng dùng để benchmark 10M document | DE-0.3 |
| I3 | **Read-model layer** `reflex_mongo/readmodels/` | DE viết query cho từng màn hình, SE chỉ nối endpoint. Ranh giới sạch, không ai phải sửa code của người kia | DE-6.1 |
| I4 | **`task judge:verify`**: một lệnh chạy S1 `--fast`, in ra *Proof Report* (MTTD, Delivered vs Provider, Recovery Proof, explain summary của A1/A4/A9) | Giám khảo tự kiểm chứng con số trong 3 phút; ăn điểm Technical và Presentation | J-9 |
| I5 | **Teach-back**: mỗi người phải trình bày được phần của người kia | Vòng Q&A chung kết hỏi ngẫu nhiên. Declaration ghi "đội hiểu toàn bộ giải pháp" | Mỗi gate |
| I6 | **Burn calculator** làm nguồn sự thật cho timeline (F4) | Không còn số "bịa" trong tài liệu và slide | DE-0.4 |
