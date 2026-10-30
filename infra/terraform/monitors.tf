# M3 (hai nửa), M7 — docs/40-observability/monitors-and-slos.md
# `env` phải trùng REFLEX_ENV của stack (compose local = "local"), vì metric gắn tag env đó.

locals {
  # Datadog đánh giá tối thiểu theo phút: demo 3m/30s của Sentinel làm tròn thành 3m/1m
  burn_windows = var.profile == "demo" ? { long = "last_3m", short = "last_1m" } : { long = "last_1h", short = "last_5m" }

  provider_slo_objective = 0.995
  fast_burn_factor       = 14.4
  # burn = tỷ lệ lỗi / error budget ≥ 14.4  ⇔  tỷ lệ lỗi ≥ 14.4 × (1 - objective)
  quality_error_threshold = tonumber(format("%.4f", local.fast_burn_factor * (1 - local.provider_slo_objective)))

  quality_error_ratio = "(sum:reflex.attempt.quality.total{env:${var.env}} by {target,route}.as_count() - sum:reflex.attempt.quality.pass{env:${var.env}} by {target,route}.as_count()) / sum:reflex.attempt.quality.total{env:${var.env}} by {target,route}.as_count()"

  alert_message = <<-EOT
    {{#is_alert}}🚨 [Reflex] {{monitor.name}}
    target={{target.name}} route={{route.name}} value={{value}} (threshold {{threshold}})
    Logs: https://app.${var.dd_site}/logs?query=service%3Areflex-gateway%20%40target%3A{{target.name}}%20-%40outcome%3Aok
    @webhook-${local.webhook_name}
    {{/is_alert}}
    {{#is_recovery}}✅ Recovered — Reflex sẽ đính kèm Recovery Proof. @webhook-${local.webhook_name}{{/is_recovery}}
  EOT
}

# M3a/M3b — chất lượng theo attempt của từng {target, route}: cửa sổ dài và ngắn.
# Gộp bằng composite M3 (composites.tf) để chỉ báo khi cả hai cùng vượt ngưỡng (giảm báo động giả).
resource "datadog_monitor" "m3_long" {
  name    = "[Reflex] M3a Provider quality burn (long window)"
  type    = "query alert"
  query   = "sum(${local.burn_windows.long}):${local.quality_error_ratio} > ${local.quality_error_threshold}"
  message = "Thành phần của M3_quality_fast_burn (cửa sổ dài)."

  monitor_thresholds {
    critical = local.quality_error_threshold
  }

  notify_no_data      = false
  require_full_window = false
  evaluation_delay    = 30
  include_tags        = true
  priority            = 1
  tags                = concat(local.common_tags, ["monitor:m3", "ledger:provider"])
}

resource "datadog_monitor" "m3_short" {
  name    = "[Reflex] M3b Provider quality burn (short window)"
  type    = "query alert"
  query   = "sum(${local.burn_windows.short}):${local.quality_error_ratio} > ${local.quality_error_threshold}"
  message = "Thành phần của M3_quality_fast_burn (cửa sổ ngắn)."

  monitor_thresholds {
    critical = local.quality_error_threshold
  }

  notify_no_data      = false
  require_full_window = false
  evaluation_delay    = 30
  include_tags        = true
  priority            = 1
  tags                = concat(local.common_tags, ["monitor:m3", "ledger:provider"])
}

# M7 — retry amplification: số attempt trung bình mỗi request vượt 1.5 (retry storm)
resource "datadog_monitor" "m7_retry_amplification" {
  name    = "[Reflex] M7_retry_amplification"
  type    = "query alert"
  query   = "avg(last_5m):avg:reflex.retry.amplification{env:${var.env}} by {route} > 1.5"
  message = local.alert_message

  monitor_thresholds {
    critical = 1.5
  }

  notify_no_data      = false
  require_full_window = false
  evaluation_delay    = 30
  renotify_interval   = 30
  include_tags        = true
  priority            = 2
  tags                = concat(local.common_tags, ["monitor:m7"])
}

# M1/M2 — Delivered availability burn (chat.reply). Datadog bắt buộc cửa sổ dài 1h–2d nên demo cũng dùng 1h/5m.
resource "datadog_monitor" "m1_availability_fast_burn" {
  name    = "[Reflex] M1_availability_fast_burn"
  type    = "slo alert"
  query   = "burn_rate(\"${datadog_service_level_objective.delivered_availability_chat_reply.id}\").over(\"7d\").long_window(\"1h\").short_window(\"5m\") > ${local.fast_burn_factor}"
  message = local.alert_message

  monitor_thresholds {
    critical = local.fast_burn_factor
  }

  notify_no_data      = false
  require_full_window = false
  renotify_interval   = 30
  priority            = 1
  tags                = concat(local.common_tags, ["monitor:m1", "ledger:delivered"])
}

resource "datadog_monitor" "m2_availability_slow_burn" {
  name    = "[Reflex] M2_availability_slow_burn"
  type    = "slo alert"
  query   = "burn_rate(\"${datadog_service_level_objective.delivered_availability_chat_reply.id}\").over(\"7d\").long_window(\"6h\").short_window(\"30m\") > 6"
  message = local.alert_message

  monitor_thresholds {
    critical = 6
  }

  notify_no_data      = false
  require_full_window = false
  renotify_interval   = 120
  priority            = 2
  tags                = concat(local.common_tags, ["monitor:m2", "ledger:delivered"])
}

# P_direct / P_via_gw — probe quality theo target; nguyên liệu của composite M9/M10 (chẩn đoán provider vs gateway)
locals {
  probe_fail_ratio = { for path in ["direct", "via_gateway"] :
    path => "sum:reflex.probe.result{env:${var.env},path:${path},result:fail} by {target}.as_count() / sum:reflex.probe.result{env:${var.env},path:${path}} by {target}.as_count()"
  }
}

resource "datadog_monitor" "p_direct" {
  name    = "[Reflex] P_direct probe quality low"
  type    = "query alert"
  query   = "sum(${local.burn_windows.long}):${local.probe_fail_ratio["direct"]} > 0.1"
  message = "Probe gọi thẳng vendor (bỏ qua gateway) có tỉ lệ fail > 10%. Thành phần của M9/M10."

  monitor_thresholds {
    critical = 0.1
  }

  notify_no_data      = false
  require_full_window = false
  evaluation_delay    = 30
  priority            = 2
  tags                = concat(local.common_tags, ["monitor:p_direct", "ledger:provider"])
}

resource "datadog_monitor" "p_via_gw" {
  name    = "[Reflex] P_via_gw probe quality low"
  type    = "query alert"
  query   = "sum(${local.burn_windows.long}):${local.probe_fail_ratio["via_gateway"]} > 0.1"
  message = "Probe qua gateway có tỉ lệ fail > 10%. Thành phần của M10."

  monitor_thresholds {
    critical = 0.1
  }

  notify_no_data      = false
  require_full_window = false
  evaluation_delay    = 30
  priority            = 2
  tags                = concat(local.common_tags, ["monitor:p_via_gw", "ledger:delivered"])
}

# M6 — Probe silence: mù về chất lượng nếu prober im > 3 phút
resource "datadog_monitor" "m6_probe_silence" {
  name    = "[Reflex] M6_probe_silence"
  type    = "query alert"
  query   = "sum(last_5m):sum:reflex.probe.result{env:${var.env}} by {target,path}.as_count() < 1"
  message = local.alert_message

  monitor_thresholds {
    critical = 1
  }

  notify_no_data    = true
  no_data_timeframe = 5
  evaluation_delay  = 30
  renotify_interval = 30
  priority          = 2
  tags              = concat(local.common_tags, ["monitor:m6", "meta:blindness"])
}

# M11 — telemetry bị drop (queue đầy): số liệu đang thiếu, đừng tin dashboard
resource "datadog_monitor" "m11_telemetry_dropped" {
  name    = "[Reflex] M11_telemetry_dropped"
  type    = "query alert"
  query   = "sum(last_5m):sum:reflex.telemetry.dropped{env:${var.env}}.as_count() > 0"
  message = local.alert_message

  monitor_thresholds {
    critical = 0
  }

  notify_no_data      = false
  require_full_window = false
  priority            = 3
  tags                = concat(local.common_tags, ["monitor:m11", "meta:telemetry"])
}

# M4 — Delivered latency burn (chat.reply). Doc gốc gọi là "TTFT"; gateway chưa đo TTFT cấp request nên dùng latency toàn request.
resource "datadog_monitor" "m4_latency_burn" {
  name    = "[Reflex] M4_latency_burn"
  type    = "slo alert"
  query   = "burn_rate(\"${datadog_service_level_objective.delivered_latency_chat_reply.id}\").over(\"7d\").long_window(\"1h\").short_window(\"5m\") > ${local.fast_burn_factor}"
  message = local.alert_message

  monitor_thresholds {
    critical = local.fast_burn_factor
  }

  notify_no_data      = false
  require_full_window = false
  renotify_interval   = 60
  priority            = 2
  tags                = concat(local.common_tags, ["monitor:m4", "ledger:delivered", "sli:latency"])
}

# M5 — p99 latency của primary attempt lệch khỏi band lịch sử, theo target (phát hiện sớm, cảnh báo mức thấp)
resource "datadog_monitor" "m5_latency_anomaly" {
  name    = "[Reflex] M5_latency_p99_anomaly"
  type    = "query alert"
  query   = "avg(last_4h):anomalies(p99:reflex.attempt.latency{env:${var.env},attempt_kind:primary} by {target}, 'agile', 3, direction='above', interval=60, alert_window='last_15m', count_default_zero='true', seasonality='hourly') >= 1"
  message = "Latency p99 của {{target.name}} bất thường so với band lịch sử. Cảnh báo sớm, chưa chắc vi phạm SLO."

  monitor_thresholds {
    critical          = 1
    critical_recovery = 0
  }

  monitor_threshold_windows {
    trigger_window  = "last_15m"
    recovery_window = "last_15m"
  }

  notify_no_data      = false
  require_full_window = false
  priority            = 3
  tags                = concat(local.common_tags, ["monitor:m5", "sli:latency"])
}

# M8 — chi phí tăng bất thường (tiền): chỉ thông báo, không kích hoạt mitigation
resource "datadog_monitor" "m8_cost_anomaly" {
  name    = "[Reflex] M8_cost_anomaly"
  type    = "query alert"
  query   = "avg(last_4h):anomalies(sum:reflex.cost.usd{env:${var.env}}.as_rate(), 'basic', 3, direction='above', interval=60, alert_window='last_15m', count_default_zero='true') >= 1"
  message = "Chi phí LLM ($/s) vượt band thường lệ. Kiểm tra retry/hedge storm hoặc route đổi sang model đắt."

  monitor_thresholds {
    critical          = 1
    critical_recovery = 0
  }

  monitor_threshold_windows {
    trigger_window  = "last_15m"
    recovery_window = "last_15m"
  }

  notify_no_data      = false
  require_full_window = false
  priority            = 3
  tags                = concat(local.common_tags, ["monitor:m8", "meta:cost"])
}

# M13 — Cortex health: tỉ lệ điều tra lỗi > 20% (metric phát từ CortexAgent.investigate)
resource "datadog_monitor" "m13_cortex_errors" {
  name    = "[Reflex] M13_cortex_error_rate"
  type    = "query alert"
  query   = "sum(last_30m):sum:reflex.cortex.investigation{env:${var.env},status:error}.as_count() / sum:reflex.cortex.investigation{env:${var.env}}.as_count() > 0.2"
  message = "Cortex điều tra lỗi > 20% trong 30 phút — Reflex sẽ rơi về rules fallback (R4)."

  monitor_thresholds {
    critical = 0.2
  }

  notify_no_data      = false
  require_full_window = false
  priority            = 3
  tags                = concat(local.common_tags, ["monitor:m13", "meta:cortex"])
}

# M13b — Cortex chậm: p95 thời lượng điều tra > 180s
resource "datadog_monitor" "m13_cortex_slow" {
  name    = "[Reflex] M13_cortex_slow"
  type    = "query alert"
  query   = "percentile(last_30m):p95:reflex.cortex.investigation.duration{env:${var.env}} > 180"
  message = "Cortex p95 thời lượng điều tra > 180s."

  monitor_thresholds {
    critical = 180
  }

  notify_no_data      = false
  require_full_window = false
  priority            = 3
  tags                = concat(local.common_tags, ["monitor:m13", "meta:cortex"])
}

# M12 — Detector disagreement: Sentinel và Datadog mở số incident khác nhau trong 10 phút (cần webhook đã nối, webhooks.tf)
resource "datadog_monitor" "m12_detector_disagreement" {
  name    = "[Reflex] M12_detector_disagreement"
  type    = "query alert"
  query   = "sum(last_10m):abs(default_zero(sum:reflex.incident.open{env:${var.env},source:sentinel}.as_count()) - default_zero(sum:reflex.incident.open{env:${var.env},source:datadog}.as_count())) > 0"
  message = "Sentinel và Datadog không đồng thuận về incident trong 10 phút — một detector đang mù hoặc báo giả."

  monitor_thresholds {
    critical = 0
  }

  notify_no_data      = false
  require_full_window = false
  priority            = 3
  tags                = concat(local.common_tags, ["monitor:m12", "meta:detector"])
}
