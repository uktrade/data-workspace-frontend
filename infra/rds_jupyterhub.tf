# resource "aws_db_instance" "jupyterhub" {
#   identifier = "${var.prefix}"

#   allocated_storage = 20
#   storage_type = "gp2"
#   engine = "postgres"
#   engine_version = "10.6"
#   instance_class = "db.t2.medium"

#   apply_immediately = true

#   backup_retention_period = 31
#   backup_window = "03:29-03:59"

#   name = "${var.prefix_underscore}"
#   username = "${var.prefix_underscore}_master"
#   password = "${random_string.aws_db_instance_jupyterhub_password.result}"

#   final_snapshot_identifier = "${var.prefix}-final-snapshot"

#   vpc_security_group_ids = ["${aws_security_group.jupyterhub_db.id}"]
#   db_subnet_group_name = "${aws_db_subnet_group.jupyterhub.name}"
# }

resource "aws_db_subnet_group" "jupyterhub" {
  name       = "${var.prefix}"
  subnet_ids = ["${aws_subnet.private_with_egress.*.id}"]

  tags {
    Name = "${var.prefix}"
  }
}

# resource "random_string" "aws_db_instance_jupyterhub_password" {
#   length = 128
#   special = false
# }
