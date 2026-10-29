# Outputs cho Datadog resources: Dashboards, SLOs, Monitors

output "dashboard_ops_id" {
  description = "ID của dashboard Operations (D1)"
  value       = datadog_dashboard_json.ops.id
}

output "dashboard_slo_id" {
  description = "ID của dashboard SLO & Error Budget (D2)"
  value       = datadog_dashboard_json.slo.id
}

output "dashboard_cortex_id" {
  description = "ID của dashboard Cortex Agent (D3)"
  value       = datadog_dashboard_json.cortex.id
}

output "slo_chat_reply_id" {
  description = "SLO ID cho Delivered availability (chat.reply)"
  value       = datadog_service_level_objective.delivered_availability_chat_reply.id
}

output "slo_order_extract_id" {
  description = "SLO ID cho Delivered quality (order.extract)"
  value       = datadog_service_level_objective.delivered_quality_order_extract.id
}
