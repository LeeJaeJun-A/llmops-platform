variable "environment" {
  type = string
}

variable "project_name" {
  type    = string
  default = "llmops"
}

variable "vpc_id" {
  type = string
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "engine_version" {
  type    = string
  default = "16.6"
}

variable "database_name" {
  type    = string
  default = "llmops"
}

variable "multi_az" {
  type    = bool
  default = true
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "backup_retention_period" {
  type    = number
  default = 7
}

# Security Group
resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-${var.environment}-rds-"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "PostgreSQL from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-rds"
  }
}

# Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "${var.project_name}-${var.environment}"
  }
}

# Generate password
resource "random_password" "db_password" {
  length  = 32
  special = false
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier     = "${var.project_name}-${var.environment}"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name  = var.database_name
  username = "llmops"
  password = random_password.db_password.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  multi_az            = var.multi_az
  deletion_protection = var.deletion_protection
  storage_encrypted   = true
  allocated_storage   = 20
  max_allocated_storage = 100

  backup_retention_period = var.backup_retention_period
  skip_final_snapshot     = var.environment == "dev"

  tags = {
    Environment = var.environment
  }
}

output "endpoint" {
  value = aws_db_instance.main.endpoint
}

output "host" {
  value = aws_db_instance.main.address
}

output "port" {
  value = aws_db_instance.main.port
}

output "username" {
  value = aws_db_instance.main.username
}

output "database_url" {
  value     = "postgresql+asyncpg://llmops:${random_password.db_password.result}@${aws_db_instance.main.endpoint}/${var.database_name}"
  sensitive = true
}

output "password" {
  value     = random_password.db_password.result
  sensitive = true
}
