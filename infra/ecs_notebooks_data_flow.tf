resource "aws_ecs_task_definition" "data_flow_ide" {
  family                = "${var.prefix}-data-flow-ide"
  container_definitions = "${data.template_file.data_flow_ide_container_definitions.rendered}"
  execution_role_arn    = "${aws_iam_role.notebook_task_execution.arn}"
  network_mode          = "awsvpc"
  cpu                   = "${local.notebook_container_cpu}"
  memory                = "${local.notebook_container_memory}"
  requires_compatibilities = ["FARGATE"]

  volume {
    name = "home_directory"
  }

  volume {
    name = "dags"
  }

  lifecycle {
    ignore_changes = [
      "revision",
    ]
  }
}

data "external" "data_flow_ide_current_tag" {
  program = ["${path.module}/task_definition_tag.sh"]

  query = {
    task_family = "${var.prefix}-data-flow-ide"
    container_name = "${local.notebook_container_name}"
  }
}

data "external" "data_flow_ide_data_flow_current_tag" {
  program = ["${path.module}/task_definition_tag.sh"]

  query = {
    task_family = "${var.prefix}-data-flow-ide"
    container_name = "data_flow"
  }
}

data "external" "data_flow_ide_metrics_current_tag" {
  program = ["${path.module}/task_definition_tag.sh"]

  query = {
    task_family = "${var.prefix}-data-flow-ide"
    container_name = "metrics"
  }
}

data "external" "data_flow_ide_s3sync_current_tag" {
  program = ["${path.module}/task_definition_tag.sh"]

  query = {
    task_family = "${var.prefix}-data-flow-ide"
    container_name = "s3sync"
  }
}

data "template_file" "data_flow_ide_container_definitions" {
  template = "${file("${path.module}/ecs_notebooks_data_flow_container_definitions.json")}"

  vars = {
    container_image  = "${aws_ecr_repository.data_flow_ide.repository_url}:master"
    container_name   = "${local.notebook_container_name}"

    log_group  = "${aws_cloudwatch_log_group.notebook.name}"
    log_region = "${data.aws_region.aws_region.name}"

    sentry_dsn = "${var.sentry_dsn}"
    sentry_environment = "${var.sentry_environment}"

    data_flow_container_image = "${aws_ecr_repository.data_flow.repository_url}:master"
    metrics_container_image = "${aws_ecr_repository.metrics.repository_url}:master"
    s3sync_container_image = "${aws_ecr_repository.s3sync.repository_url}:master"
  }
}
