# Delivered + Provider SLO (dual ledger) — docs/40-observability/monitors-and-slos.md
# Datadog SLO chỉ có timeframe 7d/30d/90d; cửa sổ demo 6h chỉ tồn tại ở Sentinel (burn rate vẫn là tỉ lệ).

resource "datadog_service_level_objective" "delivered_availability_chat_reply" {
  name        = "[Reflex] Delivered availability — chat.reply"
  type        = "metric"
  description = "Delivered ledger: request thành công / request không bị shed."

  query {
    numerator   = "sum:reflex.request{env:${var.env},route:chat.reply,outcome:ok}.as_count()"
    denominator = "sum:reflex.request{env:${var.env},route:chat.reply,!outcome:shed}.as_count()"
  }

  thresholds {
    timeframe = "7d"
    target    = 99.5
  }

  tags = concat(local.common_tags, ["ledger:delivered", "route:chat.reply"])
}

resource "datadog_service_level_objective" "delivered_quality_order_extract" {
  name        = "[Reflex] Delivered quality — order.extract"
  type        = "metric"
  description = "Delivered ledger: request qua validator / request có kiểm tra chất lượng."

  query {
    numerator   = "sum:reflex.quality.pass{env:${var.env},route:order.extract}.as_count()"
    denominator = "sum:reflex.quality.total{env:${var.env},route:order.extract}.as_count()"
  }

  thresholds {
    timeframe = "7d"
    target    = 99.5
  }

  tags = concat(local.common_tags, ["ledger:delivered", "route:order.extract"])
}

# Provider ledger: thấp hơn Delivered (vendor chỉ hứa 99%, Reflex giao 99.5%)
resource "datadog_service_level_objective" "provider_quality" {
  for_each    = toset(var.targets)
  name        = "[Reflex] Provider quality — ${each.key}"
  type        = "metric"
  description = "Provider ledger: attempt qua validator / attempt có kiểm tra, theo target đã gọi."

  query {
    numerator   = "sum:reflex.attempt.quality.pass{env:${var.env},target:${each.key}}.as_count()"
    denominator = "sum:reflex.attempt.quality.total{env:${var.env},target:${each.key}}.as_count()"
  }

  thresholds {
    timeframe = "7d"
    target    = 99.0
  }

  tags = concat(local.common_tags, ["ledger:provider", "target:${each.key}"])
}

# Delivered latency: request ok nhanh hơn 2000ms / request ok (gateway phát `reflex.request.under_threshold`)
resource "datadog_service_level_objective" "delivered_latency_chat_reply" {
  name        = "[Reflex] Delivered latency — chat.reply (<2000ms)"
  type        = "metric"
  description = "Delivered ledger: request ok có latency dưới 2000ms / request ok."

  query {
    numerator   = "sum:reflex.request.under_threshold{env:${var.env},route:chat.reply,threshold:2000}.as_count()"
    denominator = "sum:reflex.request{env:${var.env},route:chat.reply,outcome:ok}.as_count()"
  }

  thresholds {
    timeframe = "7d"
    target    = 99.0
  }

  tags = concat(local.common_tags, ["ledger:delivered", "route:chat.reply", "sli:latency"])
}
