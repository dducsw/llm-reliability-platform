# Dashboards từ JSON: ops, slo, cortex (template variable env/target/route)
resource "datadog_dashboard_json" "reflex" {
  for_each  = toset(["ops", "slo", "cortex"])
  dashboard = file("${path.module}/dashboards/${each.key}.json")
}
