resource "aws_ecs_service" "flower" {
  name            = "${var.prefix}-flower"
  cluster         = "${aws_ecs_cluster.main_cluster.id}"
  task_definition = "${aws_ecs_task_definition.flower_service.arn}"
  desired_count   = 1
  launch_type     = "FARGATE"
  deployment_maximum_percent = 200
  platform_version = "1.4.0"
  health_check_grace_period_seconds = "10"

  network_configuration {
    subnets         = ["${aws_subnet.private_without_egress.*.id[0]}"]
    security_groups = ["${aws_security_group.flower_service.id}"]
  }

  load_balancer {
    target_group_arn = "${aws_lb_target_group.flower_80.arn}"
    container_port   = "80"
    container_name   = "flower"
  }

  depends_on = [
    "aws_lb_listener.flower_80",
  ]
}

resource "aws_ecs_task_definition" "flower_service" {
  family                   = "${var.prefix}-flower"
  container_definitions    = "${data.template_file.flower_service_container_definitions.rendered}"
  execution_role_arn       = "${aws_iam_role.flower_task_execution.arn}"
  task_role_arn            = "${aws_iam_role.flower_task.arn}"
  network_mode             = "awsvpc"
  cpu                      = "${local.flower_container_cpu}"
  memory                   = "${local.flower_container_memory}"
  requires_compatibilities = ["FARGATE"]

  lifecycle {
    ignore_changes = [
      "revision",
    ]
  }
}

data "template_file" "flower_service_container_definitions" {
  template = "${file("${path.module}/ecs_main_flower_container_definitions.json")}"

  vars = {
    container_image = "${aws_ecr_repository.flower.repository_url}:master"
    container_name  = "flower"
    log_group       = "${aws_cloudwatch_log_group.flower.name}"
    log_region      = "${data.aws_region.aws_region.name}"
    cpu             = "${local.flower_container_cpu}"
    memory          = "${local.flower_container_memory}"
    redis_url       = "redis://${aws_elasticache_cluster.admin.cache_nodes.0.address}:6379"
    flower_username = "${var.flower_username}"
    flower_password = "${var.flower_password}"
  }
}

resource "aws_cloudwatch_log_group" "flower" {
  name              = "${var.prefix}-flower"
  retention_in_days = "3653"
}

resource "aws_iam_role" "flower_task_execution" {
  name               = "${var.prefix}-flower-task-execution"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.flower_task_execution_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "flower_task_execution_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "flower_task_execution" {
  role       = "${aws_iam_role.flower_task_execution.name}"
  policy_arn = "${aws_iam_policy.flower_task_execution.arn}"
}

resource "aws_iam_policy" "flower_task_execution" {
  name   = "${var.prefix}-flower-task-execution"
  path   = "/"
  policy = "${data.aws_iam_policy_document.flower_task_execution.json}"
}

data "aws_iam_policy_document" "flower_task_execution" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.flower.arn}:*",
    ]
  }

  statement {
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]

    resources = [
      "${aws_ecr_repository.flower.arn}",
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

resource "aws_iam_role" "flower_task" {
  name               = "${var.prefix}-flower-task"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.flower_task_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "flower_task_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_lb" "flower" {
  name               = "${var.prefix}-flower"
  load_balancer_type = "application"
  internal           = true
  security_groups    = ["${aws_security_group.flower_lb.id}"]
  subnets            = "${aws_subnet.private_without_egress.*.id}"
}

resource "aws_lb_listener" "flower_80" {
  load_balancer_arn = "${aws_lb.flower.arn}"
  port              = "80"
  protocol          = "HTTP"

  default_action {
    target_group_arn = "${aws_lb_target_group.flower_80.arn}"
    type             = "forward"
  }
}

resource "aws_lb_target_group" "flower_80" {
  name_prefix = "f80-"
  port        = "80"
  vpc_id      = "${aws_vpc.notebooks.id}"
  target_type = "ip"
  protocol    = "HTTP"

  health_check {
    protocol = "HTTP"
    interval = 10
    healthy_threshold   = 2
    unhealthy_threshold = 5

    path = "/healthcheck"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_iam_role" "flower_ecs" {
  name               = "${var.prefix}-flower-ecs"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.flower_ecs_assume_role.json}"
}

resource "aws_iam_role_policy_attachment" "flower_ecs" {
  role       = "${aws_iam_role.flower_ecs.name}"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceRole"
}

data "aws_iam_policy_document" "flower_ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs.amazonaws.com"]
    }
  }
}
