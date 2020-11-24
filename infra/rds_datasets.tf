resource "aws_db_parameter_group" "default" {
  name   = "postgres10-pgaudit"
  description = "Postgres10 with pgaudit csvlogging enabled"
  family = "postgres10"

  parameter {
    name  = "shared_preload_libraries"
    value = "pgaudit"
    apply_method = "pending-reboot"
  }

  parameter {
    name  = "log_destination"
    value = "csvlog"
  }
}
