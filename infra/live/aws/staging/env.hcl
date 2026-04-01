locals {
  environment  = "staging"
  aws_region   = "ap-northeast-2"

  # Sizing
  k8s_node_instance_type = "m6i.large"
  k8s_min_nodes          = 2
  k8s_max_nodes          = 5
  k8s_desired_nodes      = 2
  db_instance_class      = "db.t4g.medium"
  redis_node_type        = "cache.t4g.small"
}
