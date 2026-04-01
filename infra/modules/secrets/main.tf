variable "environment" {
  type = string
}

variable "project_name" {
  type    = string
  default = "llmops"
}

variable "database_url" {
  type      = string
  sensitive = true
}

variable "redis_url" {
  type = string
}

variable "anthropic_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "gemini_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "langfuse_public_key" {
  type    = string
  default = ""
}

variable "langfuse_secret_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "api_keys" {
  type      = string
  sensitive = true
  # No default — must be explicitly provided per environment
}

# Secrets Manager for application secrets
resource "aws_secretsmanager_secret" "app" {
  name = "${var.project_name}/${var.environment}/app"

  tags = {
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    DATABASE_URL        = var.database_url
    REDIS_URL           = var.redis_url
    ANTHROPIC_API_KEY   = var.anthropic_api_key
    GEMINI_API_KEY      = var.gemini_api_key
    LANGFUSE_PUBLIC_KEY = var.langfuse_public_key
    LANGFUSE_SECRET_KEY = var.langfuse_secret_key
    API_KEYS            = var.api_keys
  })
}

output "secret_arn" {
  value = aws_secretsmanager_secret.app.arn
}

output "secret_name" {
  value = aws_secretsmanager_secret.app.name
}
