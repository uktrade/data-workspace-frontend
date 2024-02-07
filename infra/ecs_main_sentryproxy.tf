resource "aws_ecs_service" "sentryproxy" {
  name             = "${var.prefix}-sentryproxy"
  cluster          = "${aws_ecs_cluster.main_cluster.id}"
  task_definition  = "${aws_ecs_task_definition.sentryproxy.arn}"
  desired_count    = 1
  launch_type      = "FARGATE"
  platform_version = "1.4.0"

  network_configuration {
    subnets         = "${aws_subnet.private_with_egress.*.id}"
    security_groups = ["${aws_security_group.sentryproxy_service.id}"]
  }

  service_registries {
    registry_arn   = "${aws_service_discovery_service.sentryproxy.arn}"
  }
}

data "external" "sentryproxy_current_tag" {
  program = ["${path.module}/container-tag.sh"]

  query = {
    cluster_name = "${aws_ecs_cluster.main_cluster.name}"
    service_name = "${var.prefix}-sentryproxy"
    container_name = "${local.sentryproxy_container_name}"
  }
}

resource "aws_service_discovery_service" "sentryproxy" {
  name = "${var.prefix}-sentryproxy"

  dns_config {
    namespace_id = "${aws_service_discovery_private_dns_namespace.jupyterhub.id}"
    dns_records {
      ttl = 10
      type = "A"
    }
  }

  # Needed for a service to be able to register instances with a target group,
  # but only if it has a service_registries, which we do
  # https://forums.aws.amazon.com/thread.jspa?messageID=852407&tstart=0
  health_check_custom_config {
    failure_threshold = 1
  }
}

resource "aws_ecs_task_definition" "sentryproxy" {
  family                   = "${var.prefix}-sentryproxy"
  container_definitions    = templatefile(
    "${path.module}/ecs_main_sentryproxy_container_definitions.json", {
      container_image  = "${aws_ecr_repository.sentryproxy.repository_url}:${data.external.sentryproxy_current_tag.result.tag}"
      container_name   = "${local.sentryproxy_container_name}"
      container_cpu    = "${local.sentryproxy_container_cpu}"
      container_memory = "${local.sentryproxy_container_memory}"

      log_group  = "${aws_cloudwatch_log_group.sentryproxy.name}"
      log_region = "${data.aws_region.aws_region.name}"
    }
  )
  execution_role_arn       = "${aws_iam_role.sentryproxy_task_execution.arn}"
  task_role_arn            = "${aws_iam_role.sentryproxy_task.arn}"
  network_mode             = "awsvpc"
  cpu                      = "${local.sentryproxy_container_cpu}"
  memory                   = "${local.sentryproxy_container_memory}"
  requires_compatibilities = ["FARGATE"]

  lifecycle {
    ignore_changes = [
      "revision",
    ]
  }
}

resource "aws_cloudwatch_log_group" "sentryproxy" {
  name              = "${var.prefix}-sentryproxy"
  retention_in_days = "3653"
}

resource "aws_cloudwatch_log_subscription_filter" "sentryproxy" {
  count = "${var.cloudwatch_subscription_filter ? 1 : 0}"
  name            = "${var.prefix}-sentryproxy"
  log_group_name  = "${aws_cloudwatch_log_group.sentryproxy.name}"
  filter_pattern  = ""
  destination_arn = "${var.cloudwatch_destination_arn}"
}

resource "aws_iam_role" "sentryproxy_task_execution" {
  name               = "${var.prefix}-sentryproxy-task-execution"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.sentryproxy_task_execution_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "sentryproxy_task_execution_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "sentryproxy_task_execution" {
  role       = "${aws_iam_role.sentryproxy_task_execution.name}"
  policy_arn = "${aws_iam_policy.sentryproxy_task_execution.arn}"
}

resource "aws_iam_policy" "sentryproxy_task_execution" {
  name        = "${var.prefix}-sentryproxy-task-execution"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.sentryproxy_task_execution.json}"
}

data "aws_iam_policy_document" "sentryproxy_task_execution" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.sentryproxy.arn}:*",
    ]
  }

  statement {
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]

    resources = [
      "${aws_ecr_repository.sentryproxy.arn}",
    ]
  }

  statement {
    actions = [
      "ecr:GetAuthorizationToken",
    ]

    resources = [
      "*",
    ]
  }
}

resource "aws_iam_role" "sentryproxy_task" {
  name               = "${var.prefix}-sentryproxy-task"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.sentryproxy_task_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "sentryproxy_task_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}
