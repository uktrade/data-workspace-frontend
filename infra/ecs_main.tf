resource "aws_ecs_cluster" "main_cluster" {
  name = "${var.prefix}"
}
