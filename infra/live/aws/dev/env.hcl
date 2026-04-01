locals {
  environment  = "dev"
  aws_region   = "ap-northeast-2"

  # Sizing
  k8s_node_instance_type = "t3.medium"
  k8s_min_nodes          = 1
  k8s_max_nodes          = 3
  k8s_desired_nodes      = 2
  db_instance_class      = "db.t4g.small"
  redis_node_type        = "cache.t4g.micro"
}
