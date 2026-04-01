terraform {
  source = "../../../../modules//redis"
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
  private_subnet_ids = dependency.networking.outputs.private_subnet_ids
  node_type          = local.env_vars.locals.redis_node_type
}
