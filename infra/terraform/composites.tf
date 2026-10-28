# M3 = M3a && M3b — tên khớp expectation `M3_quality_fast_burn` của scenarios/silent-brownout.yaml
resource "datadog_monitor" "m3" {
  name    = "[Reflex] M3_quality_fast_burn"
  type    = "composite"
  query   = "${datadog_monitor.m3_long.id} && ${datadog_monitor.m3_short.id}"
  message = local.alert_message

  notify_no_data    = false
  renotify_interval = 30
  priority          = 1
  tags              = concat(local.common_tags, ["monitor:m3", "ledger:provider"])
}

# M9 Provider-side confirmed = M3 && P_direct
# M10 Gateway-side suspected = (M1 || M4) && !P_direct && P_via_gw
# TODO(P3): cần monitor probe P_direct / P_via_gw — chờ prober phát `reflex.probe.result`
