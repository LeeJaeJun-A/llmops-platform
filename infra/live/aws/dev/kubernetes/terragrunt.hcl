terraform {
  source = "../../../../modules//kubernetes"
}

include "root" {
  path = find_in_parent_folders()
}

locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

dependency "networking" {
  config_path = "../networking"
}

inputs = {
  environment        = local.env_vars.locals.environment
  vpc_id             = dependency.networking.outputs.vpc_id
  vpc_cidr           = dependency.networking.outputs.vpc_cidr
  private_subnet_ids = dependency.networking.outputs.private_subnet_ids
  node_instance_type = local.env_vars.locals.k8s_node_instance_type
  node_min_size      = local.env_vars.locals.k8s_min_nodes
  node_max_size      = local.env_vars.locals.k8s_max_nodes
  node_desired_size  = local.env_vars.locals.k8s_desired_nodes
}
