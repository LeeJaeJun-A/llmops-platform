terraform {
  source = "../../../../modules//karpenter"
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

dependency "kubernetes" {
  config_path = "../kubernetes"
}

inputs = {
  environment            = local.env_vars.locals.environment
  cluster_name           = dependency.kubernetes.outputs.cluster_name
  cluster_endpoint       = dependency.kubernetes.outputs.cluster_endpoint
  cluster_ca_certificate = dependency.kubernetes.outputs.cluster_ca_certificate
  oidc_provider_arn      = dependency.kubernetes.outputs.oidc_provider_arn
  vpc_id                 = dependency.networking.outputs.vpc_id
  private_subnet_ids     = dependency.networking.outputs.private_subnet_ids
  node_security_group_id = dependency.kubernetes.outputs.node_security_group_id
}
