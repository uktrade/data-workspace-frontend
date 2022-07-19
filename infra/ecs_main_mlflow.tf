locals {
  mlflow_container_vars = {
    "0" = {
        container_image      = "${aws_ecr_repository.mlflow.repository_url}:master"
        container_name       = "mlflow"
        log_group            = "${aws_cloudwatch_log_group.mlflow[0].name}"
        log_region           = "${data.aws_region.aws_region.name}"
        cpu                  = "${local.mlflow_container_cpu}"
        memory               = "${local.mlflow_container_memory}"
        artifact_bucket_name = "${aws_s3_bucket.mlflow[0].bucket}"
        jwt_public_key       = "${var.jwt_public_key}"
        mlflow_hostname      = "http://mlflow--${var.mlflow_instances_long[0]}.${var.admin_domain}"
        tracking_server_host = "http://mlflow--${var.mlflow_instances_long[0]}.${var.admin_domain}:${local.mlflow_port}"
        database_uri         = "postgresql://${aws_rds_cluster.mlflow[0].master_username}:${random_string.aws_db_instance_mlflow_password[0].result}@${aws_rds_cluster.mlflow[0].endpoint}:5432/${aws_rds_cluster.mlflow[0].database_name}"
        proxy_port           = "${local.mlflow_port}"
    }
  }
}

resource "aws_ecs_service" "mlflow" {
  count                             = "${length(var.mlflow_instances)}"
  name                              = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}"
  cluster                           = "${aws_ecs_cluster.main_cluster.id}"
  task_definition                   = "${aws_ecs_task_definition.mlflow_service[count.index].arn}"
  desired_count                     = 1
  launch_type                       = "FARGATE"
  deployment_maximum_percent        = 200
  platform_version                  = "1.4.0"
  health_check_grace_period_seconds = "10"

  network_configuration {
    subnets         = ["${aws_subnet.private_without_egress.*.id[0]}"]
    security_groups = ["${aws_security_group.mlflow_service[count.index].id}"]
  }

  load_balancer {
    target_group_arn = "${aws_lb_target_group.mlflow[count.index].arn}"
    container_port   = "${local.mlflow_port}"
    container_name   = "mlflow"
  }

  service_registries {
    registry_arn   = "${aws_service_discovery_service.mlflow[count.index].arn}"
  }

  depends_on = [
    "aws_lb_listener.mlflow",
  ]
}

resource "aws_service_discovery_service" "mlflow" {
  count  = "${length(var.mlflow_instances)}"
  name   = "mlflow--${var.mlflow_instances_long[count.index]}"
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

resource "aws_ecs_task_definition" "mlflow_service" {
  count                    = "${length(var.mlflow_instances)}"
  family                   = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}"
  container_definitions    = "${data.template_file.mlflow_service_container_definitions[count.index].rendered}"
  execution_role_arn       = "${aws_iam_role.mlflow_task_execution[count.index].arn}"
  task_role_arn            = "${aws_iam_role.mlflow_task[count.index].arn}"
  network_mode             = "awsvpc"
  cpu                      = "${local.mlflow_container_cpu}"
  memory                   = "${local.mlflow_container_memory}"
  requires_compatibilities = ["FARGATE"]

  lifecycle {
    ignore_changes = [
      "revision",
    ]
  }
}

data "template_file" "mlflow_service_container_definitions" {
  count    = "${length(var.mlflow_instances)}"
  template = "${file("${path.module}/ecs_main_mlflow_container_definitions.json")}"

  vars     = "${local.mlflow_container_vars[count.index]}"
}

resource "aws_cloudwatch_log_group" "mlflow" {
  count             = "${length(var.mlflow_instances)}"
  name              = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}"
  retention_in_days = "3653"
}

resource "aws_iam_role" "mlflow_task_execution" {
  count             = "${length(var.mlflow_instances)}"
  name              = "${var.prefix}-mlflow-task-execution-${var.mlflow_instances[count.index]}"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.mlflow_task_execution_ecs_tasks_assume_role[count.index].json}"
}

data "aws_iam_policy_document" "mlflow_task_execution_ecs_tasks_assume_role" {
  count             = "${length(var.mlflow_instances)}"
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "mlflow_task_execution" {
  count             = "${length(var.mlflow_instances)}"
  role       = "${aws_iam_role.mlflow_task_execution[count.index].name}"
  policy_arn = "${aws_iam_policy.mlflow_task_execution[count.index].arn}"
}

resource "aws_iam_policy" "mlflow_task_execution" {
  count  = "${length(var.mlflow_instances)}"
  name   = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}-task-execution"
  path   = "/"
  policy = "${data.aws_iam_policy_document.mlflow_task_execution[count.index].json}"
}

data "aws_iam_policy_document" "mlflow_task_execution" {
  count  = "${length(var.mlflow_instances)}"
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.mlflow[count.index].arn}:*",
    ]
  }

  statement {
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]

    resources = [
      "${aws_ecr_repository.mlflow.arn}",
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

resource "aws_iam_role" "mlflow_task" {
  count  = "${length(var.mlflow_instances)}"
  name               = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}-task"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.mlflow_task_ecs_tasks_assume_role[count.index].json}"
}

data "aws_iam_policy_document" "mlflow_task_ecs_tasks_assume_role" {
  count  = "${length(var.mlflow_instances)}"
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "mlflow_access_artifacts_bucket" {
  count  = "${length(var.mlflow_instances)}"
  role       = "${aws_iam_role.mlflow_task[count.index].name}"
  policy_arn = "${aws_iam_policy.mlflow_access_artifacts_bucket[count.index].arn}"
}

resource "aws_iam_policy" "mlflow_access_artifacts_bucket" {
  count  = "${length(var.mlflow_instances)}"
  name        = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}-access-artifacts-bucket"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.mlflow_access_artifacts_bucket[count.index].json}"
}


data "aws_iam_policy_document" "mlflow_access_artifacts_bucket" {
  count  = "${length(var.mlflow_instances)}"
  statement {
    actions = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
    ]

    resources = [
      "${aws_s3_bucket.mlflow[count.index].arn}/*",
    ]
  }

  statement {
    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]

    resources = [
      "${aws_s3_bucket.mlflow[count.index].arn}",
    ]
  }
}

resource "aws_lb" "mlflow" {
  count  = "${length(var.mlflow_instances)}"
  name               = "${var.prefix}-mf-${var.mlflow_instances[count.index]}"
  load_balancer_type = "application"
  internal           = true
  security_groups    = ["${aws_security_group.mlflow_lb[count.index].id}"]
  subnets            = "${aws_subnet.private_without_egress.*.id}"
}

resource "aws_lb_listener" "mlflow" {
  count  = "${length(var.mlflow_instances)}"
  load_balancer_arn = "${aws_lb.mlflow[count.index].arn}"
  port              = "${local.mlflow_port}"
  protocol          = "HTTP"

  default_action {
    target_group_arn = "${aws_lb_target_group.mlflow[count.index].arn}"
    type             = "forward"
  }
}

resource "aws_lb_target_group" "mlflow" {
  count  = "${length(var.mlflow_instances)}"
  name_prefix = "f${var.mlflow_instances[count.index]}-"
  port        = "${local.mlflow_port}"
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

resource "aws_iam_role" "mlflow_ecs" {
  count  = "${length(var.mlflow_instances)}"
  name               = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}-ecs"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.mlflow_ecs_assume_role[count.index].json}"
}

resource "aws_iam_role_policy_attachment" "mlflow_ecs" {
  count  = "${length(var.mlflow_instances)}"
  role       = "${aws_iam_role.mlflow_ecs[count.index].name}"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceRole"
}

data "aws_iam_policy_document" "mlflow_ecs_assume_role" {
  count  = "${length(var.mlflow_instances)}"
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs.amazonaws.com"]
    }
  }
}

resource "aws_rds_cluster" "mlflow" {
  count                   = "${length(var.mlflow_instances)}"
  cluster_identifier      = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}"
  engine                  = "aurora-postgresql"
  availability_zones      = "${var.aws_availability_zones}"
  database_name           = "${var.prefix_underscore}_mlflow_${var.mlflow_instances[count.index]}"
  master_username         = "${var.prefix_underscore}_mlflow_master_${var.mlflow_instances[count.index]}"
  master_password         = "${random_string.aws_db_instance_mlflow_password[count.index].result}"
  backup_retention_period = 31
  preferred_backup_window = "03:29-03:59"
  apply_immediately       = true

  vpc_security_group_ids = ["${aws_security_group.mlflow_db[count.index].id}"]
  db_subnet_group_name   = "${aws_db_subnet_group.mlflow[count.index].name}"

  final_snapshot_identifier  = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}"
}

resource "aws_rds_cluster_instance" "mlflow" {
  count              = "${length(var.mlflow_instances)}"
  identifier_prefix  = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}-"
  cluster_identifier = "${aws_rds_cluster.mlflow[count.index].id}"
  engine             = "${aws_rds_cluster.mlflow[count.index].engine}"
  engine_version     = "${aws_rds_cluster.mlflow[count.index].engine_version}"
  instance_class     = "${var.mlflow_db_instance_class}"
}

resource "aws_db_subnet_group" "mlflow" {
  count              = "${length(var.mlflow_instances)}"
  name               = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}"
  subnet_ids         = "${aws_subnet.private_without_egress.*.id}"

  tags = {
    Name = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "random_string" "aws_db_instance_mlflow_password" {
  count   = "${length(var.mlflow_instances)}"
  length  = 99
  special = false
}