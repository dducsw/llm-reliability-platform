# Id Datadog để seed vào collection `slos.datadog` (đối chiếu dual-ledger với Sentinel)
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
