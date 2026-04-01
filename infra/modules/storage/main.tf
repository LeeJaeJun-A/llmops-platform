variable "environment" {
  type = string
}

variable "project_name" {
  type    = string
  default = "llmops"
}

# S3 Bucket for Langfuse event storage
resource "aws_s3_bucket" "langfuse" {
  bucket = "${var.project_name}-${var.environment}-langfuse"

  tags = {
    Environment = var.environment
  }
}

resource "aws_s3_bucket_versioning" "langfuse" {
  bucket = aws_s3_bucket.langfuse.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "langfuse" {
  bucket = aws_s3_bucket.langfuse.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "langfuse" {
  bucket                  = aws_s3_bucket.langfuse.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# IAM user for Langfuse S3 access
resource "aws_iam_user" "langfuse_s3" {
  name = "${var.project_name}-${var.environment}-langfuse-s3"

  tags = {
    Environment = var.environment
  }
}

resource "aws_iam_user_policy" "langfuse_s3" {
  name = "langfuse-s3-access"
  user = aws_iam_user.langfuse_s3.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        Resource = [
          aws_s3_bucket.langfuse.arn,
          "${aws_s3_bucket.langfuse.arn}/*",
        ]
      }
    ]
  })
}

resource "aws_iam_access_key" "langfuse_s3" {
  user = aws_iam_user.langfuse_s3.name
}

output "langfuse_bucket_name" {
  value = aws_s3_bucket.langfuse.id
}

output "langfuse_bucket_arn" {
  value = aws_s3_bucket.langfuse.arn
}

output "langfuse_s3_access_key_id" {
  value = aws_iam_access_key.langfuse_s3.id
}

output "langfuse_s3_secret_access_key" {
  value     = aws_iam_access_key.langfuse_s3.secret
  sensitive = true
}
