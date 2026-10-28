# M3 (hai nửa), M7 — docs/40-observability/monitors-and-slos.md
# Chưa làm (thiếu metric nguồn): M6 và probe P_direct/P_via_gw (`reflex.probe.result` chưa được phát),
# M11 (`reflex.telemetry.dropped`), M12, M13; M1/M2/M4 cần SLO object (slos.tf).
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
