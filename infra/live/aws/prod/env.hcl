locals {
  environment  = "prod"
  aws_region   = "ap-northeast-2"

  # Sizing
  k8s_node_instance_type = "m6i.xlarge"
  k8s_min_nodes          = 3
  k8s_max_nodes          = 10
  k8s_desired_nodes      = 3
  db_instance_class      = "db.r6g.large"
  redis_node_type        = "cache.r6g.large"
}
