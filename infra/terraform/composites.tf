# M3 = M3a && M3b && M3v (đủ mẫu) — tên khớp expectation `M3_quality_fast_burn` của scenarios/silent-brownout.yaml
resource "datadog_monitor" "m3" {
  name    = "[Reflex] M3_quality_fast_burn"
  type    = "composite"
  query   = "${datadog_monitor.m3_long.id} && ${datadog_monitor.m3_short.id} && ${datadog_monitor.m3_volume.id}"
  message = local.alert_message

  notify_no_data    = false
  renotify_interval = 30
  priority          = 1
  tags              = concat(local.common_tags, ["monitor:m3", "ledger:provider"])
}

# M9 Provider-side confirmed = M3 && P_direct → webhook mang diagnosis provider_side
resource "datadog_monitor" "m9_provider_side" {
  name = "[Reflex] M9_provider_side_confirmed"
  type = "composite"
  # Composite không được chứa composite (M3) → dùng thẳng hai nửa của M3
  query   = "${datadog_monitor.m3_long.id} && ${datadog_monitor.m3_short.id} && ${datadog_monitor.m3_volume.id} && ${datadog_monitor.p_direct.id}"
  message = "diagnosis:provider_side\n${local.alert_message}"

  notify_no_data    = false
  renotify_interval = 30
  priority          = 1
  tags              = concat(local.common_tags, ["monitor:m9", "diagnosis:provider_side"])
}

# M10 Gateway-side suspected = (M1 || M4) && !P_direct && P_via_gw
resource "datadog_monitor" "m10_gateway_side" {
  name    = "[Reflex] M10_gateway_side_suspected"
  type    = "composite"
  query   = "(${datadog_monitor.m1_availability_fast_burn.id} || ${datadog_monitor.m4_latency_burn.id}) && !${datadog_monitor.p_direct.id} && ${datadog_monitor.p_via_gw.id}"
  message = "diagnosis:gateway_side\n${local.alert_message}"

  notify_no_data    = false
  renotify_interval = 30
  priority          = 1
  tags              = concat(local.common_tags, ["monitor:m10", "diagnosis:gateway_side"])
}

# M12 Detector disagreement = đúng một trong hai detector có signal (XOR)
resource "datadog_monitor" "m12_detector_disagreement" {
  name    = "[Reflex] M12_detector_disagreement"
  type    = "composite"
  query   = "(${datadog_monitor.m12_signal_present["sentinel"].id} && !${datadog_monitor.m12_signal_present["datadog"].id}) || (${datadog_monitor.m12_signal_present["datadog"].id} && !${datadog_monitor.m12_signal_present["sentinel"].id})"
  message = "Sentinel và Datadog không đồng thuận trong 10 phút: một detector có signal, detector kia im lặng."

  notify_no_data = false
  priority       = 3
  tags           = concat(local.common_tags, ["monitor:m12", "meta:detector"])
}
