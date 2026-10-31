# Id Datadog của SLO/monitor; `mongo_slo_links` được tools/sync_datadog_ids.py ghi vào `slos.datadog` (đối chiếu dual-ledger)
output "slo_ids" {
  description = "Delivered + Provider SLO của Datadog, khóa theo tên logic"
  value = merge(
    {
      delivered_availability_chat_reply = datadog_service_level_objective.delivered_availability_chat_reply.id
      delivered_quality_order_extract   = datadog_service_level_objective.delivered_quality_order_extract.id
      delivered_latency_chat_reply      = datadog_service_level_objective.delivered_latency_chat_reply.id
    },
    { for t, s in datadog_service_level_objective.provider_quality : "provider_quality:${t}" => s.id }
  )
}

output "monitor_ids" {
  value = {
    m1  = datadog_monitor.m1_availability_fast_burn.id
    m3  = datadog_monitor.m3.id
    m9  = datadog_monitor.m9_provider_side.id
    m10 = datadog_monitor.m10_gateway_side.id
    m2  = datadog_monitor.m2_availability_slow_burn.id
    m4  = datadog_monitor.m4_latency_burn.id
    m5  = datadog_monitor.m5_latency_anomaly.id
    m7  = datadog_monitor.m7_retry_amplification.id
    m8  = datadog_monitor.m8_cost_anomaly.id
    m11 = datadog_monitor.m11_telemetry_dropped.id
    m12 = datadog_monitor.m12_detector_disagreement.id
    m13 = [datadog_monitor.m13_cortex_errors.id, datadog_monitor.m13_cortex_slow.id]
  }
}

# Khóa = `_id` trong collection `slos` (seeds/slos.yaml). SLO Datadog không có bản Sentinel tương ứng (availability/latency
# chat.reply) thì không có ở đây.
output "mongo_slo_links" {
  value = merge(
    {
      "route:order.extract:quality" = {
        slo_id = datadog_service_level_objective.delivered_quality_order_extract.id
        # Delivered quality chưa có monitor Datadog riêng (M3 là Provider ledger)
        monitor_ids = tolist([])
      }
    },
    { for t, s in datadog_service_level_objective.provider_quality : "target:${t}:quality" => {
      slo_id      = s.id
      monitor_ids = tolist([datadog_monitor.m3.id, datadog_monitor.m9_provider_side.id])
    } }
  )
}

output "dashboard_ids" {
  description = "ID dashboard Datadog (ops, slo, cortex, mongo)"
  value       = { for k, d in datadog_dashboard_json.reflex : k => d.id }
}
