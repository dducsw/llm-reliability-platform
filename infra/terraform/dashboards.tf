# Dashboards từ JSON: ops (D1), slo (D2), cortex (D3) — docs/40-observability/dashboards.md

resource "datadog_dashboard_json" "ops" {
  dashboard = file("${path.module}/dashboards/ops.json")
}

resource "datadog_dashboard_json" "slo" {
  dashboard = file("${path.module}/dashboards/slo.json")
}

resource "datadog_dashboard_json" "cortex" {
  dashboard = file("${path.module}/dashboards/cortex.json")
}

resource "datadog_dashboard_json" "mongo" {
  dashboard = file("${path.module}/dashboards/mongo.json")
}
