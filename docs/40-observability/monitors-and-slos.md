# Datadog SLOs & Monitors

> Quản lý bằng Terraform trong `infra/datadog/`. Query bên dưới là **dạng logic**. Cú pháp chính xác sẽ được kiểm chứng bằng `terraform plan` và Datadog monitor preview trong Phase 3 (chưa test trên trial thật, nên ghi chú ⚠ ở chỗ cần thử).

## 1. Datadog SLO objects

Datadog SLO là **ledger thứ hai** bên cạnh Sentinel. Hai ledger được đối chiếu ("dual-ledger SLO") để bắt lỗi telemetry.

| SLO | Loại | Good events | Total events | Target (demo profile) |
| :--- | :--- | :--- | :--- | :--- |
| Delivered availability — `chat.reply` | metric-based | `sum:reflex.request.count{route:chat.reply,outcome:ok}.as_count()` | `sum:reflex.request.count{route:chat.reply,!outcome:shed}.as_count()` | 99.5% |
| Delivered quality — `order.extract` | metric-based | `sum:reflex.quality.check{route:order.extract,check:all,result:pass}.as_count()` | `sum:reflex.quality.check{route:order.extract,check:all}.as_count()` | 99.5% |
| Delivered latency — `chat.reply` (<2000ms) | metric-based ⚠ | đếm request có latency dưới ngưỡng. Gateway phát thêm count `reflex.request.under_threshold{route,threshold:2000}` vì SLO metric-based cần count | `reflex.request.count{route:chat.reply,outcome:ok}` | 99% |
| Provider quality — per target | metric-based | `reflex.attempt.count{outcome:ok,attempt_kind:primary}` theo `target` | primary attempt không bị cancel | 99% |

> ⚠ Datadog SLO chỉ có timeframe 7d/30d/90d, nên SLO window 6h của profile demo chỉ tồn tại ở Sentinel. Burn rate alert không bị ảnh hưởng vì burn là tỉ lệ. Dashboard D2 đối chiếu dual-ledger theo **good/total trên cùng khoảng thời gian**, không đối chiếu budget ([review F7](../00-strategy/design-review-v1.md#f7)).

> Provider SLO được đặt **thấp hơn** Delivered SLO. Thông điệp sản phẩm nằm ngay ở đây: vendor chỉ hứa 99%, nhưng nhờ Reflex, người dùng nhận được 99,5%.

## 2. Danh mục Monitor

| ID | Tên | Loại | Logic | Severity | Bước | Nối với |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **M1** | Delivered availability fast burn | SLO burn rate alert | burn(long=1h, short=5m) ≥ 14.4 *(demo: 5m/1m)* | P1 | Detect | webhook → incident |
| **M2** | Delivered availability slow burn | SLO burn rate alert | burn(6h/30m) ≥ 6 | P2 | Detect | webhook |
| **M3** | Provider quality fast burn | metric alert ×2 + composite | `(1 - pass/total)` của quality **group by `{target, route}`** ([review F1](../00-strategy/design-review-v1.md#f1)), cửa sổ dài **và** ngắn (demo 3m/30s, Datadog làm tròn lên 1m), ≥ 14.4 × budget | P1 | Detect | webhook |
| **M4** | TTFT SLO burn — interactive | SLO burn rate | trên SLO TTFT của `chat.reply` | P2 | Detect | webhook |
| **M5** | TTFT p99 anomaly | anomaly | `anomalies(p99:reflex.attempt.latency{attempt_kind:primary} by {target}, 'agile', 3)` ⚠ | P3 | Detect sớm | Cortex (warning) |
| **M6** | Probe silence | metric, `notify_no_data` | `sum:reflex.probe.result{*} by {target,path}.as_count()` không có dữ liệu trong 3 phút | P2 | Detect (blindness) | webhook |
| **M7** | Retry amplification | metric | `avg:reflex.retry.amplification by {route}` > 1.5 trong 5m | P2 | Detect (storm) | webhook |
| **M8** | Cost burn anomaly | anomaly / forecast | `sum:reflex.cost.usd{*}.as_rate()` vượt band | P3 | Detect (tiền) | Slack |
| **M9** | **Provider-side confirmed** | **composite** | `M3 && P_direct` (P_direct = monitor phụ: probe `path:direct` quality < 90% cho target) | P1 | Investigate | webhook (`diagnosis:provider_side`) |
| **M10** | **Gateway-side suspected** | **composite** | `(M1 \|\| M4) && !P_direct && P_via_gw` | P1 | Investigate | webhook (`diagnosis:gateway_side`) |
| **M11** | Telemetry drop | metric | `sum:reflex.telemetry.dropped{*}.as_count()` > 0 trong 5m | P3 | Meta | Slack |
| M12 | Detector disagreement | metric | `reflex.incident.open{source:sentinel}` khác `…{source:datadog}` trong 10m | P3 | Meta | Slack |
| M13 | Cortex health | LLMObs / APM | error rate của `reflex-cortex` investigation > 20% hoặc p95 > 180s | P3 | Meta | Slack |

### Vì sao cần composite M9 và M10

Đây là phần **Investigate tự động ngay trong Datadog**. Giám khảo Datadog sẽ đánh giá cao kiểu dùng này. Hai monitor cơ sở (traffic thật xấu, probe gọi thẳng xấu hoặc tốt) kết hợp lại cho ra *chẩn đoán*, không chỉ là *báo động*. Webhook mang tag `diagnosis:*`. Incident manager ghi tag này vào `incident.diagnosis`. Cortex coi đó là prior.

## 3. Mẫu monitor message (template)

```text
{{#is_alert}}🚨 [Reflex] {{monitor.name}}
target={{target.name}} route={{route.name}}
burn(short)={{value}} — threshold {{threshold}}
Dashboard: https://app.{{site}}/dashboard/<ops-id>?tpl_var_target={{target.name}}&from_ts={{last_triggered_at_epoch}}
Logs:      https://app.{{site}}/logs?query=service%3Areflex-gateway%20%40target%3A{{target.name}}%20-%40outcome%3Aok
Runbook:   https://github.com/<org>/llm-reliability-platform/blob/main/docs/50-reliability/runbooks.md#{{monitor.id}}
@webhook-reflex-incident
{{/is_alert}}
{{#is_recovery}}✅ Recovered — Reflex will attach Recovery Proof. @webhook-reflex-incident{{/is_recovery}}
```

## 4. Webhook payload

```json
{
  "source": "datadog",
  "alert_id": "$ALERT_ID",
  "alert_transition": "$ALERT_TRANSITION",
  "monitor_id": "$ALERT_QUERY_ID",
  "monitor_name": "$ALERT_TITLE",
  "priority": "$ALERT_PRIORITY",
  "tags": "$TAGS",
  "date": "$DATE",
  "link": "$LINK",
  "value": "$ALERT_METRIC"
}
```
Header: `X-Reflex-Webhook-Token: <secret>`. Endpoint `POST /hooks/datadog` idempotent theo `(alert_id, alert_transition)`. `Recovered` không tự resolve incident. Nó chỉ thêm signal vào incident; quyền resolve thuộc về Verifier.

⚠ Biến template của webhook cần kiểm chứng lại với tài liệu Datadog hiện hành khi viết Terraform.

## 5. Alert hygiene

- Mọi monitor có `renotify_interval`, `evaluation_delay: 30` (tránh dữ liệu chưa đầy đủ) và `require_full_window: false` cho cửa sổ ngắn.
- Group-by theo `target` hoặc `route`, không group theo `gateway_id` (vì breaker là local, chuyện bình thường).
- Downtime tự động **không** được dùng cho chaos. Chaos là sự cố thật của hệ thống demo, nên monitor phải bắn.
