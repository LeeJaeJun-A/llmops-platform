terraform {
  source = "../../../../modules//storage"
}

include "root" {
  path = find_in_parent_folders()
}

locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

inputs = {
  environment = local.env_vars.locals.environment
}
