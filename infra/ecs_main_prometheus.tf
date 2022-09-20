resource "aws_ecs_service" "prometheus" {
  name             = "${var.prefix}-prometheus"
  cluster          = "${aws_ecs_cluster.main_cluster.id}"
  task_definition  = "${aws_ecs_task_definition.prometheus.arn}"
  desired_count    = 1
  launch_type      = "FARGATE"
  platform_version = "1.4.0"

  network_configuration {
    subnets         = "${aws_subnet.private_with_egress.*.id}"
    security_groups = ["${aws_security_group.prometheus_service.id}"]
  }

  load_balancer {
    target_group_arn = "${aws_alb_target_group.prometheus.arn}"
    container_port   = "${local.prometheus_container_port}"
    container_name   = "${local.prometheus_container_name}"
  }

  service_registries {
    registry_arn   = "${aws_service_discovery_service.prometheus.arn}"
  }

  depends_on = [
    # The target group must have been associated with the listener first
    aws_alb_listener.prometheus,
  ]
}

data "external" "prometheus_current_tag" {
  program = ["${path.module}/container-tag.sh"]

  query = {
    cluster_name = "${aws_ecs_cluster.main_cluster.name}"
    service_name = "${var.prefix}-prometheus"  # Manually specified to avoid a cycle
    container_name = "${local.prometheus_container_name}"
  }
}

resource "aws_service_discovery_service" "prometheus" {
  name = "${var.prefix}-prometheus"
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

resource "aws_ecs_task_definition" "prometheus" {
  family                   = "${var.prefix}-prometheus"
  container_definitions    = "${data.template_file.prometheus_container_definitions.rendered}"
  execution_role_arn       = "${aws_iam_role.prometheus_task_execution.arn}"
  task_role_arn            = "${aws_iam_role.prometheus_task.arn}"
  network_mode             = "awsvpc"
  cpu                      = "${local.prometheus_container_cpu}"
  memory                   = "${local.prometheus_container_memory}"
  requires_compatibilities = ["FARGATE"]

  lifecycle {
    ignore_changes = [
      revision,
    ]
  }
}

data "template_file" "prometheus_container_definitions" {
  template = "${file("${path.module}/ecs_main_prometheus_container_definitions.json")}"

  vars = {
    container_image   = "${aws_ecr_repository.prometheus.repository_url}:${data.external.prometheus_current_tag.result.tag}"
    container_name    = "${local.prometheus_container_name}"
    container_port    = "${local.prometheus_container_port}"
    container_cpu     = "${local.prometheus_container_cpu}"
    container_memory  = "${local.prometheus_container_memory}"

    log_group  = "${aws_cloudwatch_log_group.prometheus.name}"
    log_region = "${data.aws_region.aws_region.name}"

    port = "${local.prometheus_container_port}"
    url = "https://${var.admin_domain}/api/v1/application"
    metrics_service_discovery_basic_auth_user = "${var.metrics_service_discovery_basic_auth_user}"
    metrics_service_discovery_basic_auth_password = "${var.metrics_service_discovery_basic_auth_password}"
  }
}

resource "aws_cloudwatch_log_group" "prometheus" {
  name              = "${var.prefix}-prometheus"
  retention_in_days = "3653"
}

resource "aws_cloudwatch_log_subscription_filter" "prometheus" {
  count = "${var.cloudwatch_subscription_filter ? 1 : 0}"
  name            = "${var.prefix}-prometheus"
  log_group_name  = "${aws_cloudwatch_log_group.prometheus.name}"
  filter_pattern  = ""
  destination_arn = "${var.cloudwatch_destination_arn}"
}

resource "aws_iam_role" "prometheus_task_execution" {
  name               = "${var.prefix}-prometheus-task-execution"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.prometheus_task_execution_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "prometheus_task_execution_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "prometheus_task_execution" {
  role       = "${aws_iam_role.prometheus_task_execution.name}"
  policy_arn = "${aws_iam_policy.prometheus_task_execution.arn}"
}

resource "aws_iam_policy" "prometheus_task_execution" {
  name        = "${var.prefix}-prometheus-task-execution"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.prometheus_task_execution.json}"
}

data "aws_iam_policy_document" "prometheus_task_execution" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.prometheus.arn}:*",
    ]
  }

  statement {
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]

    resources = [
      "${aws_ecr_repository.prometheus.arn}",
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

resource "aws_iam_role" "prometheus_task" {
  name               = "${var.prefix}-prometheus-task"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.prometheus_task_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "prometheus_task_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_alb" "prometheus" {
  name            = "${var.prefix}-pm"
  subnets         = "${aws_subnet.public.*.id}"
  security_groups = ["${aws_security_group.prometheus_alb.id}"]

  access_logs {
    bucket  = "${aws_s3_bucket.alb_access_logs.id}"
    prefix  = "prometheus"
    enabled = true
  }

  depends_on = [
    aws_s3_bucket_policy.alb_access_logs,
  ]
}

resource "aws_alb_listener" "prometheus" {
  load_balancer_arn = "${aws_alb.prometheus.arn}"
  port              = "${local.prometheus_alb_port}"
  protocol          = "HTTPS"

  default_action {
    target_group_arn = "${aws_alb_target_group.prometheus.arn}"
    type             = "forward"
  }

  ssl_policy      = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn = "${aws_acm_certificate_validation.prometheus.certificate_arn}"
}

resource "aws_alb_target_group" "prometheus" {
  name_prefix = "pm-"
  port        = "${local.prometheus_container_port}"
  protocol    = "HTTP"
  vpc_id      = "${aws_vpc.main.id}"
  target_type = "ip"

  health_check {
    path = "/-/healthy"
    protocol = "HTTP"
    healthy_threshold = 2
    unhealthy_threshold = 2
  }

  lifecycle {
    create_before_destroy = true
  }
}
