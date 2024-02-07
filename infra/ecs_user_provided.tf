resource "aws_ecs_task_definition" "user_provided" {
  family                = "${var.prefix}-user-provided"
  container_definitions    = templatefile(
    "${path.module}/ecs_user_provided_container_definitions.json", {
      container_name   = "${local.user_provided_container_name}"
      container_cpu    = "${local.user_provided_container_cpu}"
      container_memory = "${local.user_provided_container_memory}"
      container_image  = "${aws_ecr_repository.user_provided.repository_url}"

      log_group  = "${aws_cloudwatch_log_group.notebook.name}"
      log_region = "${data.aws_region.aws_region.name}"

      sentry_dsn = "${var.sentry_notebooks_dsn}"

      metrics_container_image = "${aws_ecr_repository.metrics.repository_url}:master"
    }
  )
  execution_role_arn    = "${aws_iam_role.notebook_task_execution.arn}"
  network_mode          = "awsvpc"
  cpu                   = "${local.user_provided_container_cpu}"
  memory                = "${local.user_provided_container_memory}"
  requires_compatibilities = ["FARGATE"]


  lifecycle {
    ignore_changes = [
      "revision",
    ]
  }
}

data "external" "user_provided_metrics_current_tag" {
  program = ["${path.module}/task_definition_tag.sh"]

  query = {
    task_family = "${var.prefix}-user-provided"
    container_name = "metrics"
  }
}

data "aws_iam_policy_document" "user_provided_access_template" {
  statement {
    resources = ["*"]
    actions = ["*"]
    effect = "Deny"
  }
}
