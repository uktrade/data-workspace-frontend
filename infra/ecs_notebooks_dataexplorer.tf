resource "aws_ecs_task_definition" "dataexplorer" {
  family                = "${var.prefix}-dataexplorer"
  container_definitions = "${data.template_file.dataexplorer_container_definitions.rendered}"
  execution_role_arn    = "${aws_iam_role.notebook_task_execution.arn}"
  network_mode          = "awsvpc"
  cpu                   = "${local.notebook_container_cpu}"
  memory                = "${local.notebook_container_memory}"
  requires_compatibilities = ["FARGATE"]

  volume {
    name = "home_directory"
  }

  lifecycle {
    ignore_changes = [
      "revision",
    ]
  }
}

data "external" "dataexplorer_current_tag" {
  program = ["${path.module}/task_definition_tag.sh"]

  query = {
    task_family = "${var.prefix}-dataexplorer"
    container_name = "${local.notebook_container_name}"
  }
}

data "external" "dataexplorer_metrics_current_tag" {
  program = ["${path.module}/task_definition_tag.sh"]

  query = {
    task_family = "${var.prefix}-dataexplorer"
    container_name = "metrics"
  }
}

data "external" "dataexplorer_s3sync_current_tag" {
  program = ["${path.module}/task_definition_tag.sh"]

  query = {
    task_family = "${var.prefix}-dataexplorer"
    container_name = "s3sync"
  }
}

data "template_file" "dataexplorer_container_definitions" {
  template = "${file("${path.module}/ecs_notebooks_notebook_container_definitions.json")}"

  vars {
    container_image  = "${var.dataexplorer_container_image}:master"
    container_name   = "${local.notebook_container_name}"

    log_group  = "${aws_cloudwatch_log_group.notebook.name}"
    log_region = "${data.aws_region.aws_region.name}"

    sentry_dsn = "${var.sentry_dsn}"
    sentry_environment = "${var.admin_environment}"

    metrics_container_image = "${var.metrics_container_image}:master"
    s3sync_container_image = "${var.s3sync_container_image}:master"

    home_directory = "/home/dataexplorer"
  }
}
