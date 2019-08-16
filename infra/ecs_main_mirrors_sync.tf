resource "aws_ecs_task_definition" "mirrors_sync" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  family                = "jupyterhub-mirrors-sync"
  container_definitions = "${data.template_file.mirrors_sync_container_definitions.rendered}"
  execution_role_arn    = "${aws_iam_role.mirrors_sync_task_execution.arn}"
  task_role_arn         = "${aws_iam_role.mirrors_sync_task.arn}"
  network_mode          = "awsvpc"
  cpu                   = "${local.mirrors_sync_container_cpu}"
  memory                = "${local.mirrors_sync_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

data "template_file" "mirrors_sync_container_definitions" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  template = "${file("${path.module}/ecs_main_mirrors_sync_container_definitions.json")}"

  vars {
    container_image    = "${var.mirrors_sync_container_image}"
    container_name     = "${local.mirrors_sync_container_name}"
    container_cpu      = "${local.mirrors_sync_container_cpu}"
    container_memory   = "${local.mirrors_sync_container_memory}"

    log_group  = "${aws_cloudwatch_log_group.mirrors_sync.name}"
    log_region = "${data.aws_region.aws_region.name}"

    mirrors_bucket_region = "${data.aws_region.aws_region.name}"
    mirrors_bucket_host = "s3-${data.aws_region.aws_region.name}.amazonaws.com"
    mirrors_bucket_name = "${var.mirrors_bucket_name}"
  }
}

resource "aws_cloudwatch_log_group" "mirrors_sync" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name              = "jupyterhub-mirrors-sync"
  retention_in_days = "3653"
}

resource "aws_cloudwatch_log_subscription_filter" "mirrors_sync" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name            = "jupyterhub-mirrors-sync"
  log_group_name  = "${aws_cloudwatch_log_group.mirrors_sync.name}"
  filter_pattern  = ""
  destination_arn = "${var.cloudwatch_destination_arn}"
}

resource "aws_iam_role" "mirrors_sync_task_execution" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name               = "mirrors-sync-task-execution"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.mirrors_sync_task_execution_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "mirrors_sync_task_execution_ecs_tasks_assume_role" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "mirrors_sync_task_execution" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  role       = "${aws_iam_role.mirrors_sync_task_execution.name}"
  policy_arn = "${aws_iam_policy.mirrors_sync_task_execution.arn}"
}

resource "aws_iam_policy" "mirrors_sync_task_execution" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name        = "jupyterhub-mirrors-sync-task-execution"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.mirrors_sync_task_execution.json}"
}

data "aws_iam_policy_document" "mirrors_sync_task_execution" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.mirrors_sync.arn}",
    ]
  }
}

resource "aws_iam_role" "mirrors_sync_task" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name               = "jupyterhub-mirrors-sync-task"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.mirrors_sync_task_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "mirrors_sync_task_ecs_tasks_assume_role" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "mirrors_sync" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  role       = "${aws_iam_role.mirrors_sync_task.name}"
  policy_arn = "${aws_iam_policy.mirrors_sync_task.arn}"
}

resource "aws_iam_policy" "mirrors_sync_task" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name        = "jupyterhub-mirrors-sync-task"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.mirrors_sync_task.json}"
}

data "aws_iam_policy_document" "mirrors_sync_task" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  statement {
    actions = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
    ]

    resources = [
      "${aws_s3_bucket.mirrors.arn}/*",
    ]
  }
}
