resource "aws_ecs_task_definition" "notebook" {
  family                = "${var.prefix}-notebook"
  container_definitions = "${data.template_file.notebook_container_definitions.rendered}"
  execution_role_arn    = "${aws_iam_role.notebook_task_execution.arn}"
  # task_role_arn         = "${aws_iam_role.notebook_task.arn}"
  network_mode          = "awsvpc"
  cpu                   = "${local.notebook_container_cpu}"
  memory                = "${local.notebook_container_memory}"
  requires_compatibilities = ["FARGATE"]

  ephemeral_storage {
    size_in_gib = 50
  }

  volume {
    name = "home_directory"
  }

  lifecycle {
    ignore_changes = [
      "revision",
    ]
  }
}

data "external" "notebook_current_tag" {
  program = ["${path.module}/task_definition_tag.sh"]

  query = {
    task_family = "${var.prefix}-notebook"
    container_name = "${local.notebook_container_name}"
  }
}

data "external" "notebook_metrics_current_tag" {
  program = ["${path.module}/task_definition_tag.sh"]

  query = {
    task_family = "${var.prefix}-notebook"
    container_name = "metrics"
  }
}

data "external" "notebook_s3sync_current_tag" {
  program = ["${path.module}/task_definition_tag.sh"]

  query = {
    task_family = "${var.prefix}-notebook"
    container_name = "s3sync"
  }
}

data "template_file" "notebook_container_definitions" {
  template = "${file("${path.module}/ecs_notebooks_notebook_container_definitions.json")}"

  vars = {
    container_image  = "${var.notebook_container_image}:${data.external.notebook_current_tag.result.tag}"
    container_name   = "${local.notebook_container_name}"

    log_group  = "${aws_cloudwatch_log_group.notebook.name}"
    log_region = "${data.aws_region.aws_region.name}"

    sentry_dsn = "${var.sentry_notebooks_dsn}"
    sentry_environment = "${var.sentry_environment}"

    metrics_container_image = "${aws_ecr_repository.metrics.repository_url}:${data.external.notebook_metrics_current_tag.result.tag}"
    s3sync_container_image = "${aws_ecr_repository.s3sync.repository_url}:${data.external.notebook_s3sync_current_tag.result.tag}"

    home_directory = "/home/jovyan"
  }
}

resource "aws_cloudwatch_log_group" "notebook" {
  name              = "${var.prefix}-notebook"
  retention_in_days = "3653"
}

resource "aws_cloudwatch_log_subscription_filter" "notebook" {
  count = "${var.cloudwatch_subscription_filter ? 1 : 0}"
  name            = "${var.prefix}-notebook"
  log_group_name  = "${aws_cloudwatch_log_group.notebook.name}"
  filter_pattern  = ""
  destination_arn = "${var.cloudwatch_destination_arn}"
}

resource "aws_iam_role" "notebook_task_execution" {
  name               = "${var.prefix}-notebook-task-execution"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.notebook_task_execution_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "notebook_task_execution_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "notebook_task_execution" {
  role       = "${aws_iam_role.notebook_task_execution.name}"
  policy_arn = "${aws_iam_policy.notebook_task_execution.arn}"
}

resource "aws_iam_policy" "notebook_task_execution" {
  name        = "${var.prefix}-notebook-task-execution"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.notebook_task_execution.json}"
}

data "aws_iam_policy_document" "notebook_task_execution" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.notebook.arn}:*",
    ]
  }

  statement {
    actions = [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
    ]

    resources = [
      "*",
    ]
  }
}

data "aws_iam_policy_document" "notebook_s3_access_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    principals {
      type        = "AWS"
      identifiers = ["${aws_iam_role.admin_task.arn}"]
    }
  }
}

data "aws_iam_policy_document" "notebook_s3_access_template" {
  statement {
    actions = [
      "s3:ListBucket",
    ]

    resources = [
      "${aws_s3_bucket.notebooks.arn}",
    ]

    condition {
      test = "ForAnyValue:StringLike"
      variable = "s3:prefix"
      values = ["__S3_PREFIXES__"]
    }
  }

  statement {
    actions = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
    ]

    resources = [
      "${aws_s3_bucket.notebooks.arn}",
    ]

    condition {
      test = "ForAnyValue:StringLike"
      variable = "s3:prefix"
      values = ["__S3_PREFIXES__"]
    }
  }

  statement {
    actions = [
      "elasticfilesystem:ClientMount",
      "elasticfilesystem:ClientWrite",
    ]

    condition {
      test = "StringEquals"
      variable = "elasticfilesystem:AccessPointArn"
      values = [
        "arn:aws:elasticfilesystem:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:access-point/__ACCESS_POINT_ID__"
      ]
    }

    resources = [
      "${aws_efs_file_system.notebooks.arn}",
    ]
  }
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = "${aws_vpc.notebooks.id}"
  service_name      = "com.amazonaws.${data.aws_region.aws_region.name}.s3"
  vpc_endpoint_type = "Gateway"

  policy = "${data.aws_iam_policy_document.aws_vpc_endpoint_s3_notebooks.json}"
}

data "aws_iam_policy_document" "aws_vpc_endpoint_s3_notebooks" {
  statement {
    principals {
      type = "AWS"
      identifiers = ["*"]
    }

    actions = [
      "s3:ListBucket",
    ]

    resources = [
      "${aws_s3_bucket.notebooks.arn}",
      "${aws_s3_bucket.mlflow[0].arn}",
    ]
  }

  statement {
    principals {
      type = "AWS"
      identifiers = ["*"]
    }

    actions = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
    ]

    resources = [
      "${aws_s3_bucket.notebooks.arn}/*",
      "${aws_s3_bucket.mlflow[0].arn}/*",
    ]
  }

  statement {
    principals {
      type = "AWS"
      identifiers = ["*"]
    }

    actions = [
        "s3:GetBucketLocation",
        "s3:ListBucket",
    ]

    resources = [
      "${aws_s3_bucket.mlflow[0].arn}",
    ]
  }

  statement {
    principals {
      type = "*"
      identifiers = ["*"]
    }

    actions = [
        "s3:GetObject",
    ]

    resources = [
      "arn:aws:s3:::${var.mirrors_data_bucket_name != "" ? var.mirrors_data_bucket_name : var.mirrors_bucket_name}/*",
    ]
  }

  statement {
    principals {
      type = "AWS"
      identifiers = ["*"]
    }

    actions = [
        "s3:GetObject",
    ]

    resources = [
      # For docker to pull from ECR
      "arn:aws:s3:::prod-${data.aws_region.aws_region.name}-starport-layer-bucket/*",
      # For AWS Linux 2 packages
      "arn:aws:s3:::amazonlinux.*.amazonaws.com/*",
    ]
  }
}

resource "aws_iam_policy" "notebook_task_boundary" {
  name   = "${var.prefix}-notebook-task-boundary"
  policy = "${data.aws_iam_policy_document.jupyterhub_notebook_task_boundary.json}"
}

data "aws_iam_policy_document" "jupyterhub_notebook_task_boundary" {
  statement {
    actions = [
      "s3:ListBucket",
    ]

    resources = [
      "${aws_s3_bucket.notebooks.arn}",
    ]
  }

  statement {
    actions = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
    ]

    resources = [
      "${aws_s3_bucket.notebooks.arn}/*",
    ]
  }

  statement {
    actions = [
      "elasticfilesystem:ClientMount",
      "elasticfilesystem:ClientWrite",
    ]

    resources = [
      "${aws_efs_file_system.notebooks.arn}",
    ]
  }
}

resource "aws_vpc_endpoint_route_table_association" "s3" {
  vpc_endpoint_id = "${aws_vpc_endpoint.s3.id}"
  route_table_id  = "${aws_route_table.private_without_egress.id}"
}

resource "aws_vpc_endpoint" "cloudwatch_logs" {
  vpc_id            = "${aws_vpc.main.id}"
  service_name      = "com.amazonaws.${data.aws_region.aws_region.name}.logs"
  vpc_endpoint_type = "Interface"

  security_group_ids = ["${aws_security_group.cloudwatch.id}"]
  subnet_ids = ["${aws_subnet.private_with_egress.*.id[0]}"]

  private_dns_enabled = true
}

resource "aws_vpc_endpoint" "cloudwatch_monitoring" {
  vpc_id            = "${aws_vpc.main.id}"
  service_name      = "com.amazonaws.${data.aws_region.aws_region.name}.monitoring"
  vpc_endpoint_type = "Interface"

  security_group_ids = ["${aws_security_group.cloudwatch.id}"]
  subnet_ids = ["${aws_subnet.private_with_egress.*.id[0]}"]

  private_dns_enabled = true
}
