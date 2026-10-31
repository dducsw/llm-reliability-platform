# Dashboards từ JSON: ops, slo, cortex, mongo (template variable env/target/route)
resource "datadog_dashboard_json" "reflex" {
  for_each  = toset(["ops", "slo", "cortex", "mongo"])
  dashboard = file("${path.module}/dashboards/${each.key}.json")
}
