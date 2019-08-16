resource "aws_ecs_service" "registry" {
  name            = "${var.prefix}-registry"
  cluster         = "${aws_ecs_cluster.main_cluster.id}"
  task_definition = "${aws_ecs_task_definition.registry.arn}"
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = ["${aws_subnet.private_with_egress.*.id}"]
    security_groups = ["${aws_security_group.registry_service.id}"]
  }

  load_balancer {
    target_group_arn = "${aws_alb_target_group.registry.arn}"
    container_port   = "${local.registry_container_port}"
    container_name   = "${local.registry_container_name}"
  }

  depends_on = [
    # The target group must have been associated with the listener first
    "aws_alb_listener.registry",
  ]
}

resource "aws_ecs_task_definition" "registry" {
  family                = "${var.prefix}-registry"
  container_definitions = "${data.template_file.registry_container_definitions.rendered}"
  execution_role_arn    = "${aws_iam_role.registry_task_execution.arn}"
  task_role_arn         = "${aws_iam_role.registry_task.arn}"
  network_mode          = "awsvpc"
  cpu                   = "${local.registry_container_cpu}"
  memory                = "${local.registry_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

data "template_file" "registry_container_definitions" {
  template = "${file("${path.module}/ecs_main_registry_container_definitions.json")}"

  vars {
    container_image  = "${var.registry_container_image}"
    container_name   = "${local.registry_container_name}"
    container_port   = "${local.registry_container_port}"
    container_cpu    = "${local.registry_container_cpu}"
    container_memory = "${local.registry_container_memory}"

    log_group  = "${aws_cloudwatch_log_group.registry.name}"
    log_region = "${data.aws_region.aws_region.name}"

    registry_proxy_remoteurl = "${var.registry_proxy_remoteurl}"
    registry_proxy_username  = "${var.registry_proxy_username}"
    registry_proxy_password  = "${var.registry_proxy_password}"
  }
}

resource "aws_cloudwatch_log_group" "registry" {
  name              = "${var.prefix}-registry"
  retention_in_days = "3653"
}

resource "aws_cloudwatch_log_subscription_filter" "registry" {
  count = "${var.cloudwatch_subscription_filter ? 1 : 0}"
  name            = "${var.prefix}-registry"
  log_group_name  = "${aws_cloudwatch_log_group.registry.name}"
  filter_pattern  = ""
  destination_arn = "${var.cloudwatch_destination_arn}"
}

resource "aws_iam_role" "registry_task_execution" {
  name               = "${var.prefix}-registry-task-execution"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.registry_task_execution_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "registry_task_execution_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "registry_task_execution" {
  role       = "${aws_iam_role.registry_task_execution.name}"
  policy_arn = "${aws_iam_policy.registry_task_execution.arn}"
}

resource "aws_iam_policy" "registry_task_execution" {
  name        = "${var.prefix}-registry-task-execution"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.registry_task_execution.json}"
}

data "aws_iam_policy_document" "registry_task_execution" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.registry.arn}",
    ]
  }
}

resource "aws_iam_role" "registry_task" {
  name               = "${var.prefix}-registry-task"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.registry_task_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "registry_task_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_alb" "registry" {
  name            = "${var.prefix}-registry"
  subnets         = ["${aws_subnet.private_with_egress.*.id}"]
  security_groups = ["${aws_security_group.registry_alb.id}"]
  internal        = true

  access_logs {
    bucket  = "${aws_s3_bucket.alb_access_logs.id}"
    prefix  = "registry"
    enabled = true
  }

  depends_on = [
    "aws_s3_bucket_policy.alb_access_logs",
  ]
}

resource "aws_alb_listener" "registry" {
  load_balancer_arn = "${aws_alb.registry.arn}"
  port              = "${local.registry_alb_port}"
  protocol          = "HTTPS"

  default_action {
    target_group_arn = "${aws_alb_target_group.registry.arn}"
    type             = "forward"
  }

  ssl_policy      = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn = "${aws_acm_certificate_validation.registry.certificate_arn}"
}

resource "aws_alb_target_group" "registry" {
  name_prefix = "jhreg-"
  port        = "${local.registry_container_port}"
  protocol    = "HTTPS"
  vpc_id      = "${aws_vpc.main.id}"
  target_type = "ip"

  lifecycle {
    create_before_destroy = true
  }
}
