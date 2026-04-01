terraform {
  source = "../../../../modules//secrets"
}

include "root" {
  path = find_in_parent_folders()
}

locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

dependency "database" {
  config_path = "../database"
}

dependency "redis" {
  config_path = "../redis"
}

inputs = {
  environment  = local.env_vars.locals.environment
  database_url = dependency.database.outputs.database_url
  redis_url    = dependency.redis.outputs.redis_url
}
