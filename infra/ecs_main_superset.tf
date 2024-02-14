resource "aws_ecs_service" "superset" {
  count           = var.superset_on ? 1 : 0
  name            = "${var.prefix}-superset"
  cluster         = "${aws_ecs_cluster.main_cluster.id}"
  task_definition = "${aws_ecs_task_definition.superset_service[count.index].arn}"
  desired_count   = 2
  launch_type     = "FARGATE"
  deployment_maximum_percent = 200
  platform_version = "1.4.0"
  health_check_grace_period_seconds = "10"

  network_configuration {
    subnets         = ["${aws_subnet.private_without_egress.*.id[0]}"]
    security_groups = ["${aws_security_group.superset_service.id}"]
  }

  load_balancer {
    target_group_arn = "${aws_lb_target_group.superset_8000[count.index].arn}"
    container_port   = "8000"
    container_name   = "superset"
  }

  depends_on = [
    "aws_lb_listener.superset_443",
  ]
}

resource "aws_ecs_task_definition" "superset_service" {
  count                    = var.superset_on ? 1 : 0
  family                   = "${var.prefix}-superset"
  container_definitions    = templatefile(
    "${path.module}/ecs_main_superset_container_definitions.json", {
      container_image = "${aws_ecr_repository.superset.repository_url}:master"
      container_name  = "superset"
      log_group       = "${aws_cloudwatch_log_group.superset[count.index].name}"
      log_region      = "${data.aws_region.aws_region.name}"
      cpu             = "${local.superset_container_cpu}"
      memory          = "${local.superset_container_memory}"

      db_host        = "${aws_rds_cluster.superset[count.index].endpoint}"
      db_name        = "${aws_rds_cluster.superset[count.index].database_name}"
      db_password    = "${random_string.aws_db_instance_superset_password.result}"
      db_port        = "${aws_rds_cluster.superset[count.index].port}"
      db_user        = "${aws_rds_cluster.superset[count.index].master_username}"
      admin_users    = "${var.superset_admin_users}"
      secret_key     = "${random_string.superset_secret_key.result}"

      sentry_dsn = "${var.sentry_notebooks_dsn}"
      sentry_environment = "${var.sentry_environment}"
    }
  )
  execution_role_arn       = "${aws_iam_role.superset_task_execution[count.index].arn}"
  task_role_arn            = "${aws_iam_role.superset_task[count.index].arn}"
  network_mode             = "awsvpc"
  cpu                      = "${local.superset_container_cpu}"
  memory                   = "${local.superset_container_memory}"
  requires_compatibilities = ["FARGATE"]

  lifecycle {
    ignore_changes = [
      "revision",
    ]
  }
}

resource "aws_cloudwatch_log_group" "superset" {
  count             = var.superset_on ? 1 : 0
  name              = "${var.prefix}-superset"
  retention_in_days = "3653"
}

resource "aws_cloudwatch_log_subscription_filter" "superset" {
  count           = var.cloudwatch_subscription_filter && var.superset_on ? 1 : 0
  name            = "${var.prefix}-superset"
  log_group_name  = "${aws_cloudwatch_log_group.superset[count.index].name}"
  filter_pattern  = ""
  destination_arn = "${var.cloudwatch_destination_arn}"
}

resource "aws_iam_role" "superset_task_execution" {
  count              = var.superset_on ? 1 : 0
  name               = "${var.prefix}-superset-task-execution"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.superset_task_execution_ecs_tasks_assume_role[count.index].json}"
}

data "aws_iam_policy_document" "superset_task_execution_ecs_tasks_assume_role" {
  count = var.superset_on ? 1 : 0
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "superset_task_execution" {
  count      = var.superset_on ? 1 : 0
  role       = "${aws_iam_role.superset_task_execution[count.index].name}"
  policy_arn = "${aws_iam_policy.superset_task_execution[count.index].arn}"
}

resource "aws_iam_policy" "superset_task_execution" {
  count  = var.superset_on ? 1 : 0
  name   = "${var.prefix}-superset-task-execution"
  path   = "/"
  policy = "${data.aws_iam_policy_document.superset_task_execution[count.index].json}"
}

data "aws_iam_policy_document" "superset_task_execution" {
  count = var.superset_on ? 1 : 0
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.superset[count.index].arn}:*",
    ]
  }

  statement {
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]

    resources = [
      "${aws_ecr_repository.superset.arn}",
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

resource "aws_iam_role" "superset_task" {
  count              = var.superset_on ? 1 : 0
  name               = "${var.prefix}-superset-task"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.superset_task_ecs_tasks_assume_role[count.index].json}"
}

data "aws_iam_policy_document" "superset_task_ecs_tasks_assume_role" {
  count = var.superset_on ? 1 : 0
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_lb" "superset" {
  count              = var.superset_on ? 1 : 0
  name               = "${var.prefix}-superset"
  load_balancer_type = "application"
  internal           = true
  security_groups    = ["${aws_security_group.superset_lb.id}"]
  subnets            = "${aws_subnet.private_without_egress.*.id}"
  enable_deletion_protection  = true
}

resource "aws_lb_listener" "superset_443" {
  count             = var.superset_on ? 1 : 0
  load_balancer_arn = "${aws_lb.superset[count.index].arn}"
  port              = "443"
  protocol          = "HTTPS"

  ssl_policy      = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn = "${aws_acm_certificate_validation.superset_internal[count.index].certificate_arn}"

  default_action {
    target_group_arn = "${aws_lb_target_group.superset_8000[count.index].arn}"
    type             = "forward"
  }
}

resource "aws_lb_target_group" "superset_8000" {
  count       = var.superset_on ? 1 : 0
  name_prefix = "s8000-"
  port        = "8000"
  vpc_id      = "${aws_vpc.notebooks.id}"
  target_type = "ip"
  protocol    = "HTTP"

  health_check {
    protocol = "HTTP"
    interval = 10
    healthy_threshold   = 2
    unhealthy_threshold = 5

    path = "/health"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_rds_cluster" "superset" {
  count                   = var.superset_on ? 1 : 0
  cluster_identifier      = "${var.prefix}-superset"
  engine                  = "aurora-postgresql"
  availability_zones      = "${var.aws_availability_zones}"
  database_name           = "${var.prefix_underscore}_superset"
  master_username         = "${var.prefix_underscore}_superset_master"
  master_password         = "${random_string.aws_db_instance_superset_password.result}"
  backup_retention_period = 31
  preferred_backup_window = "03:29-03:59"
  apply_immediately       = true

  vpc_security_group_ids = ["${aws_security_group.superset_db.id}"]
  db_subnet_group_name   = "${aws_db_subnet_group.superset[count.index].name}"

  final_snapshot_identifier  = "${var.prefix}-superset"

  copy_tags_to_snapshot          = true
  enable_global_write_forwarding = false
}

resource "aws_rds_cluster_instance" "superset" {
  count              = var.superset_on ? 1 : 0
  identifier         = "${var.prefix}-superset"
  cluster_identifier = "${aws_rds_cluster.superset[count.index].id}"
  engine             = "${aws_rds_cluster.superset[count.index].engine}"
  engine_version     = "${aws_rds_cluster.superset[count.index].engine_version}"
  instance_class     = "${var.superset_db_instance_class}"
  promotion_tier     = 1
}

resource "aws_db_subnet_group" "superset" {
  count      = var.superset_on ? 1 : 0
  name       = "${var.prefix}-superset"
  subnet_ids = "${aws_subnet.private_without_egress.*.id}"

  tags = {
    Name = "${var.prefix}-superset"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "random_string" "aws_db_instance_superset_password" {
  length = 99
  special = false
}

resource "aws_iam_role" "superset_ecs" {
  count              = var.superset_on ? 1 : 0
  name               = "${var.prefix}-superset-ecs"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.superset_ecs_assume_role[count.index].json}"
}

resource "aws_iam_role_policy_attachment" "superset_ecs" {
  count      = var.superset_on ? 1 : 0
  role       = "${aws_iam_role.superset_ecs[count.index].name}"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceRole"
}

data "aws_iam_policy_document" "superset_ecs_assume_role" {
  count = var.superset_on ? 1 : 0
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs.amazonaws.com"]
    }
  }
}

resource "random_string" "superset_secret_key" {
  length = 64
  special = false
}
