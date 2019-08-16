resource "aws_ecs_cluster" "notebooks" {
  name = "${var.prefix}-notebooks"
}
