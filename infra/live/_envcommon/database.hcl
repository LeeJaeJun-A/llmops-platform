terraform {
  source = "${dirname(find_in_parent_folders())}/../modules//database"
}

inputs = {
  multi_az            = true
  deletion_protection = true
  backup_retention_period = 7
}
