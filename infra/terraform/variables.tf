variable "dd_api_key" {
  type      = string
  sensitive = true
}

variable "dd_app_key" {
  type      = string
  sensitive = true
}

variable "dd_site" {
  type    = string
  default = "datadoghq.com"
}

variable "env" {
  type    = string
  default = "demo"
}

variable "profile" {
  description = "SLO time scale: demo | standard"
  type        = string
  default     = "demo"
}

variable "webhook_url" {
  description = "Public URL tới control-plane /hooks/datadog"
  type        = string
}

variable "webhook_token" {
  type      = string
  sensitive = true
}

variable "routes" {
  type    = list(string)
  default = ["order.extract", "chat.reply", "support.triage"]
}

variable "targets" {
  type    = list(string)
  default = ["vendorA:large", "vendorA:small", "vendorB:large"]
}
