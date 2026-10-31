terraform {
  required_version = ">= 1.6"

  # State trên Terraform Cloud; workspace để Execution Mode = Local (key Datadog đọc từ .env qua TF_VAR_*)
  cloud {
    organization = "llm-reliability-platform"
    workspaces {
      name = "llm-reliability-platform"
    }
  }

  required_providers {
    datadog = {
      source  = "DataDog/datadog"
      version = "~> 3.46"
    }
  }
}

provider "datadog" {
  api_key = var.dd_api_key
  app_key = var.dd_app_key
  api_url = "https://api.${var.dd_site}/"
}
