# Log pipeline cho reflex-gateway (JSON structlog): remap level/timestamp, gắn incident_phase; log-based metric finish_reason.
# Facet `@target @route @outcome ...` tự có khi attribute được index; Datadog provider chưa có resource facet.
resource "datadog_logs_custom_pipeline" "gateway" {
  name       = "[Reflex] gateway"
  is_enabled = true

  filter {
    query = "service:reflex-gateway env:${var.env}"
  }

  processor {
    status_remapper {
      name       = "level → status"
      sources    = ["level"]
      is_enabled = true
    }
  }

  processor {
    date_remapper {
      name       = "timestamp → date"
      sources    = ["timestamp"]
      is_enabled = true
    }
  }

  processor {
    category_processor {
      name       = "incident_phase"
      target     = "incident_phase"
      is_enabled = true

      category {
        name = "mitigated"
        filter {
          query = "@event:(policy.applied OR action.applied)"
        }
      }
      category {
        name = "degraded"
        filter {
          query = "@event:(breaker.open OR quality.fail) OR @outcome:(error OR quality_fail)"
        }
      }
    }
  }
}

# Tín hiệu đối chiếu thứ hai cho truncation (finish_reason=length)
resource "datadog_logs_metric" "finish_reason" {
  name = "reflex.log.finish_reason"

  compute {
    aggregation_type = "count"
  }

  filter {
    query = "service:reflex-gateway env:${var.env} @finish_reason:*"
  }

  group_by {
    path     = "@finish_reason"
    tag_name = "finish_reason"
  }

  group_by {
    path     = "@target"
    tag_name = "target"
  }
}
