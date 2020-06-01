resource "aws_ecs_service" "metabase_multiuser" {
  name            = "${var.prefix}-metabase-multiuser"
  cluster         = "${aws_ecs_cluster.main_cluster.id}"
  task_definition = "${aws_ecs_task_definition.metabase_multiuser.arn}"
  desired_count   = 2
  launch_type     = "FARGATE"
  deployment_maximum_percent = 200
  platform_version = "1.4.0"
  health_check_grace_period_seconds = "120"

  network_configuration {
    subnets         = ["${aws_subnet.private_without_egress.*.id[0]}"]
    security_groups = ["${aws_security_group.metabase_multiuser_service.id}"]
  }

  load_balancer {
    target_group_arn = "${aws_lb_target_group.metabase_multiuser_8000.arn}"
    container_port   = "8000"
    container_name   = "metabase-multiuser"
  }

  depends_on = [
    "aws_lb_listener.metabase_multiuser_443",
  ]
}

resource "aws_ecs_task_definition" "metabase_multiuser" {
  family                   = "${var.prefix}-metabase-multiuser"
  container_definitions    = "${data.template_file.metabase_multiuser_container_definitions.rendered}"
  execution_role_arn       = "${aws_iam_role.metabase_multiuser_task_execution.arn}"
  task_role_arn            = "${aws_iam_role.metabase_multiuser_task.arn}"
  network_mode             = "awsvpc"
  cpu                      = "${local.metabase_multiuser_container_cpu}"
  memory                   = "${local.metabase_multiuser_container_memory}"
  requires_compatibilities = ["FARGATE"]

  lifecycle {
    ignore_changes = [
      "revision",
    ]
  }
}

data "template_file" "metabase_multiuser_container_definitions" {
  template = "${file("${path.module}/ecs_main_metabase_multiuser_container_definitions.json")}"

  vars {
    container_image = "${var.metabase_multiuser_container_image}"
    container_name  = "metabase-multiuser"
    log_group       = "${aws_cloudwatch_log_group.metabase_multiuser.name}"
    log_region      = "${data.aws_region.aws_region.name}"
    cpu             = "${local.metabase_multiuser_container_cpu}"
    memory          = "${local.metabase_multiuser_container_memory}"

    db_host        = "${aws_rds_cluster.metabase_multiuser.endpoint}"
    db_name        = "${aws_rds_cluster.metabase_multiuser.database_name}"
    db_password    = "${random_string.aws_db_instance_metabase_multiuser_password.result}"
    db_port        = "${aws_rds_cluster.metabase_multiuser.port}"
    db_user        = "${aws_rds_cluster.metabase_multiuser.master_username}"

    proxy_domain      = "${var.metabase_proxy_domain}"
    proxy_cached_body = "${var.metabase_proxy_cached_body}"

    secret_key = "${random_string.metabase_multiuser_secret_key.result}"
  }
}

resource "aws_cloudwatch_log_group" "metabase_multiuser" {
  name              = "${var.prefix}-metabase-multiuser"
  retention_in_days = "3653"
}

resource "aws_cloudwatch_log_subscription_filter" "metabase_multiuser" {
  count = "${var.cloudwatch_subscription_filter ? 1 : 0}"
  name            = "${var.prefix}-metabase-multiuser"
  log_group_name  = "${aws_cloudwatch_log_group.metabase_multiuser.name}"
  filter_pattern  = ""
  destination_arn = "${var.cloudwatch_destination_arn}"
}

resource "aws_iam_role" "metabase_multiuser_task_execution" {
  name               = "${var.prefix}-metabase-multiuser-task-execution"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.metabase_multiuser_task_execution_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "metabase_multiuser_task_execution_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "metabase_multiuser_task_execution" {
  role       = "${aws_iam_role.metabase_multiuser_task_execution.name}"
  policy_arn = "${aws_iam_policy.metabase_multiuser_task_execution.arn}"
}

resource "aws_iam_policy" "metabase_multiuser_task_execution" {
  name   = "${var.prefix}-metabase-multiuser-task-execution"
  path   = "/"
  policy = "${data.aws_iam_policy_document.metabase_multiuser_task_execution.json}"
}

data "aws_iam_policy_document" "metabase_multiuser_task_execution" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.metabase_multiuser.arn}",
    ]
  }
}

resource "aws_iam_role" "metabase_multiuser_task" {
  name               = "${var.prefix}-metabase-multiuser-task"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.metabase_multiuser_task_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "metabase_multiuser_task_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_lb" "metabase_multiuser" {
  name               = "${var.prefix}-metabase"
  load_balancer_type = "application"
  internal           = true
  security_groups    = ["${aws_security_group.metabase_multiuser_lb.id}"]
  subnets            = ["${aws_subnet.private_without_egress.*.id}"]
}

resource "aws_lb_listener" "metabase_multiuser_443" {
  load_balancer_arn = "${aws_lb.metabase_multiuser.arn}"
  port              = "443"
  protocol          = "HTTPS"

  ssl_policy      = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn = "${aws_acm_certificate_validation.metabase_multiuser_internal.certificate_arn}"

  default_action {
    target_group_arn = "${aws_lb_target_group.metabase_multiuser_8000.arn}"
    type             = "forward"
  }
}

resource "aws_lb_target_group" "metabase_multiuser_8000" {
  name_prefix = "s8000-"
  port        = "8000"
  vpc_id      = "${aws_vpc.notebooks.id}"
  target_type = "ip"
  protocol    = "HTTP"

  health_check {
    protocol = "HTTP"
    interval = 10
    healthy_threshold   = 2
    unhealthy_threshold = 2

    path = "/health"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_rds_cluster" "metabase_multiuser" {
  cluster_identifier      = "${var.prefix}-metabase-multiuser"
  engine                  = "aurora-postgresql"
  availability_zones      = ["${var.aws_availability_zones}"]
  database_name           = "${var.prefix_underscore}_metabase_multiuser"
  master_username         = "${var.prefix_underscore}_metabase_multiuser_master"
  master_password         = "${random_string.aws_db_instance_metabase_multiuser_password.result}"
  backup_retention_period = 31
  preferred_backup_window = "03:29-03:59"
  apply_immediately       = true

  vpc_security_group_ids = ["${aws_security_group.metabase_multiuser_db.id}"]
  db_subnet_group_name   = "${aws_db_subnet_group.metabase_multiuser.name}"

  final_snapshot_identifier  = "${var.prefix}-metabase"
}

resource "aws_rds_cluster_instance" "metabase_multiuser" {
  count              = 1
  identifier_prefix  = "${var.prefix}-metabase"
  cluster_identifier = "${aws_rds_cluster.metabase_multiuser.id}"
  engine             = "${aws_rds_cluster.metabase_multiuser.engine}"
  engine_version     = "${aws_rds_cluster.metabase_multiuser.engine_version}"
  instance_class     = "${var.metabase_multiuser_db_instance_class}"
}

resource "aws_db_subnet_group" "metabase_multiuser" {
  name       = "${var.prefix}-metabase-multiuser"
  subnet_ids = ["${aws_subnet.private_without_egress.*.id}"]

  tags {
    Name = "${var.prefix}-metabase-multiuser"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "random_string" "aws_db_instance_metabase_multiuser_password" {
  length = 99
  special = false
}

resource "aws_iam_role" "metabase_multiuser_ecs" {
  name               = "${var.prefix}-metabase-multiuser-ecs"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.metabase_multiuser_ecs_assume_role.json}"
}

resource "aws_iam_role_policy_attachment" "metabase_multiuser_ecs" {
  role       = "${aws_iam_role.metabase_multiuser_ecs.name}"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceRole"
}

data "aws_iam_policy_document" "metabase_multiuser_ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs.amazonaws.com"]
    }
  }
}

resource "random_string" "metabase_multiuser_secret_key" {
  length = 64
  special = false
}

resource "random_string" "metabase_multiuser_user_secret_password_key" {
  length = 64
  special = false
}
