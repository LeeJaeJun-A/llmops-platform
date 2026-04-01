terraform {
  source = "../../../../modules//database"
}

include "root" {
  path = find_in_parent_folders()
}

include "envcommon" {
  path   = "${dirname(find_in_parent_folders())}/_envcommon/database.hcl"
  expose = true
}

locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

dependency "networking" {
  config_path = "../networking"
}

inputs = {
  environment         = local.env_vars.locals.environment
  vpc_id              = dependency.networking.outputs.vpc_id
  vpc_cidr            = dependency.networking.outputs.vpc_cidr
  private_subnet_ids  = dependency.networking.outputs.private_subnet_ids
  instance_class      = local.env_vars.locals.db_instance_class
  multi_az            = false  # dev override
  deletion_protection = false  # dev override
}
