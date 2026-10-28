# Webhook → control-plane /hooks/datadog, header X-Reflex-Webhook-Token.
# Body khớp reflex_cp.hooks.payload.DatadogWebhookPayload ($TAGS là chuỗi "a:b,c:d").
# Monitor gọi webhook bằng `@webhook-${local.webhook_name}` trong message.

locals {
  webhook_name = "reflex-control-plane-${var.env}"
}

resource "datadog_webhook" "reflex" {
  name      = local.webhook_name
  url       = var.webhook_url
  encode_as = "json"

  custom_headers = jsonencode({
    "X-Reflex-Webhook-Token" = var.webhook_token
  })

  payload = jsonencode({
    monitor_id       = "$ALERT_ID"
    alert_id         = "$ALERT_CYCLE_KEY"
    alert_transition = "$ALERT_TRANSITION"
    title            = "$EVENT_TITLE"
    tags             = "$TAGS"
    diagnosis        = "$TEXT_ONLY_MSG"
    date             = "$DATE"
  })
}
