resource "aws_ecs_task_definition" "mirrors_sync_conda" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  family                = "jupyterhub-mirrors-sync-conda"
  container_definitions = templatefile(
    "${path.module}/ecs_main_mirrors_sync_container_definitions.json", {
      container_image    = "${aws_ecr_repository.mirrors_sync.repository_url}:latest"
      container_name     = "${local.mirrors_sync_container_name}"
      container_cpu      = "${local.mirrors_sync_container_cpu}"
      container_memory   = "${local.mirrors_sync_container_memory}"

      log_group  = "${aws_cloudwatch_log_group.mirrors_sync.*.name[count.index]}"
      log_region = "${data.aws_region.aws_region.name}"

      mirrors_bucket_region = "${data.aws_region.aws_region.name}"
      mirrors_bucket_host = "s3-${data.aws_region.aws_region.name}.amazonaws.com"
      mirrors_bucket_name = "${var.mirrors_bucket_name}"

      mirror_anaconda_r = "True"
      mirror_anaconda_conda_forge = "True"
      mirror_anaconda_conda_anaconda = "True"
      mirror_cran = "False"
      mirror_pypi = "False"
      mirror_debian = "False"
      mirror_nltk = "False"
    }
  )
  execution_role_arn    = "${aws_iam_role.mirrors_sync_task_execution.*.arn[count.index]}"
  task_role_arn         = "${aws_iam_role.mirrors_sync_task.*.arn[count.index]}"
  network_mode          = "awsvpc"
  cpu                   = "${local.mirrors_sync_container_cpu}"
  memory                = "${local.mirrors_sync_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

resource "aws_ecs_task_definition" "mirrors_sync_cran" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  family                = "jupyterhub-mirrors-sync-cran"
  container_definitions = templatefile(
    "${path.module}/ecs_main_mirrors_sync_container_definitions.json", {
      container_image    = "${aws_ecr_repository.mirrors_sync.repository_url}:latest"
      container_name     = "${local.mirrors_sync_container_name}"
      container_cpu      = "${local.mirrors_sync_container_cpu}"
      container_memory   = "${local.mirrors_sync_container_memory}"

      log_group  = "${aws_cloudwatch_log_group.mirrors_sync.*.name[count.index]}"
      log_region = "${data.aws_region.aws_region.name}"

      mirrors_bucket_region = "${data.aws_region.aws_region.name}"
      mirrors_bucket_host = "s3-${data.aws_region.aws_region.name}.amazonaws.com"
      mirrors_bucket_name = "${var.mirrors_bucket_name}"

      mirror_anaconda_r = "False"
      mirror_anaconda_conda_forge = "False"
      mirror_anaconda_conda_anaconda = "False"
      mirror_cran = "True"
      mirror_pypi = "False"
      mirror_debian = "False"
      mirror_nltk = "False"
    }
  )
  execution_role_arn    = "${aws_iam_role.mirrors_sync_task_execution.*.arn[count.index]}"
  task_role_arn         = "${aws_iam_role.mirrors_sync_task.*.arn[count.index]}"
  network_mode          = "awsvpc"
  cpu                   = "${local.mirrors_sync_container_cpu}"
  memory                = "${local.mirrors_sync_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

resource "aws_ecs_task_definition" "mirrors_sync_cran_binary" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  family                = "jupyterhub-mirrors-sync-cran-binary"
  container_definitions = templatefile(
    "${path.module}/ecs_main_mirrors_sync_cran_binary_container_definition.json", {
      container_image    = "${aws_ecr_repository.mirrors_sync_cran_binary.repository_url}:latest"
      container_name     = "${local.mirrors_sync_cran_binary_container_name}"
      container_cpu      = "${local.mirrors_sync_cran_binary_container_cpu}"
      container_memory   = "${local.mirrors_sync_cran_binary_container_memory}"

      log_group  = "${aws_cloudwatch_log_group.mirrors_sync.*.name[count.index]}"
      log_region = "${data.aws_region.aws_region.name}"

      mirrors_bucket_name = "${var.mirrors_bucket_name}"
    }
  )
  execution_role_arn    = "${aws_iam_role.mirrors_sync_task_execution.*.arn[count.index]}"
  task_role_arn         = "${aws_iam_role.mirrors_sync_task.*.arn[count.index]}"
  network_mode          = "awsvpc"
  cpu                   = "${local.mirrors_sync_container_cpu}"
  memory                = "${local.mirrors_sync_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

resource "aws_ecs_task_definition" "mirrors_sync_cran_binary_rv4" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  family                = "jupyterhub-mirrors-sync-cran-binary-rv4"
  container_definitions = templatefile(
    "${path.module}/ecs_main_mirrors_sync_cran_binary_container_definition.json", {
      container_image    = "${aws_ecr_repository.mirrors_sync_cran_binary_rv4.repository_url}:latest"
      container_name     = "${local.mirrors_sync_cran_binary_container_name}"
      container_cpu      = "${local.mirrors_sync_cran_binary_container_cpu}"
      container_memory   = "${local.mirrors_sync_cran_binary_container_memory}"

      log_group  = "${aws_cloudwatch_log_group.mirrors_sync.*.name[count.index]}"
      log_region = "${data.aws_region.aws_region.name}"

      mirrors_bucket_name = "${var.mirrors_bucket_name}"
    }
  )
  execution_role_arn    = "${aws_iam_role.mirrors_sync_task_execution.*.arn[count.index]}"
  task_role_arn         = "${aws_iam_role.mirrors_sync_task.*.arn[count.index]}"
  network_mode          = "awsvpc"
  cpu                   = "${local.mirrors_sync_container_cpu}"
  memory                = "${local.mirrors_sync_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

resource "aws_ecs_task_definition" "mirrors_sync_pypi" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  family                = "jupyterhub-mirrors-sync-pypi"
  container_definitions = templatefile(
    "${path.module}/ecs_main_mirrors_sync_container_definitions.json", {
      container_image    = "${aws_ecr_repository.mirrors_sync.repository_url}:latest"
      container_name     = "${local.mirrors_sync_container_name}"
      container_cpu      = "${local.mirrors_sync_container_cpu}"
      container_memory   = "${local.mirrors_sync_container_memory}"

      log_group  = "${aws_cloudwatch_log_group.mirrors_sync.*.name[count.index]}"
      log_region = "${data.aws_region.aws_region.name}"

      mirrors_bucket_region = "${data.aws_region.aws_region.name}"
      mirrors_bucket_host = "s3-${data.aws_region.aws_region.name}.amazonaws.com"
      mirrors_bucket_name = "${var.mirrors_bucket_name}"

      mirror_anaconda_r = "False"
      mirror_anaconda_conda_forge = "False"
      mirror_anaconda_conda_anaconda = "False"
      mirror_cran = "False"
      mirror_pypi = "True"
      mirror_debian = "False"
      mirror_nltk = "False"
    }
  )
  execution_role_arn    = "${aws_iam_role.mirrors_sync_task_execution.*.arn[count.index]}"
  task_role_arn         = "${aws_iam_role.mirrors_sync_task.*.arn[count.index]}"
  network_mode          = "awsvpc"
  cpu                   = "${local.mirrors_sync_container_cpu}"
  memory                = "${local.mirrors_sync_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

resource "aws_ecs_task_definition" "mirrors_sync_debian" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  family                = "jupyterhub-mirrors-sync-debian"
  container_definitions = templatefile(
    "${path.module}/ecs_main_mirrors_sync_container_definitions.json", {
      container_image    = "${aws_ecr_repository.mirrors_sync.repository_url}:latest"
      container_name     = "${local.mirrors_sync_container_name}"
      container_cpu      = "${local.mirrors_sync_container_cpu}"
      container_memory   = "${local.mirrors_sync_container_memory}"

      log_group  = "${aws_cloudwatch_log_group.mirrors_sync.*.name[count.index]}"
      log_region = "${data.aws_region.aws_region.name}"

      mirrors_bucket_region = "${data.aws_region.aws_region.name}"
      mirrors_bucket_host = "s3-${data.aws_region.aws_region.name}.amazonaws.com"
      mirrors_bucket_name = "${var.mirrors_bucket_name}"

      mirror_anaconda_r = "False"
      mirror_anaconda_conda_forge = "False"
      mirror_anaconda_conda_anaconda = "False"
      mirror_cran = "False"
      mirror_pypi = "False"
      mirror_debian = "True"
      mirror_nltk = "False"
    }
  )
  execution_role_arn    = "${aws_iam_role.mirrors_sync_task_execution.*.arn[count.index]}"
  task_role_arn         = "${aws_iam_role.mirrors_sync_task.*.arn[count.index]}"
  network_mode          = "awsvpc"
  cpu                   = "${local.mirrors_sync_container_cpu}"
  memory                = "${local.mirrors_sync_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

resource "aws_ecs_task_definition" "mirrors_sync_nltk" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  family                = "jupyterhub-mirrors-sync-nltk"
  container_definitions = templatefile(
    "${path.module}/ecs_main_mirrors_sync_container_definitions.json", {
      container_image    = "${aws_ecr_repository.mirrors_sync.repository_url}:latest"
      container_name     = "${local.mirrors_sync_container_name}"
      container_cpu      = "${local.mirrors_sync_container_cpu}"
      container_memory   = "${local.mirrors_sync_container_memory}"

      log_group  = "${aws_cloudwatch_log_group.mirrors_sync.*.name[count.index]}"
      log_region = "${data.aws_region.aws_region.name}"

      mirrors_bucket_region = "${data.aws_region.aws_region.name}"
      mirrors_bucket_host = "s3-${data.aws_region.aws_region.name}.amazonaws.com"
      mirrors_bucket_name = "${var.mirrors_bucket_name}"

      mirror_anaconda_r = "False"
      mirror_anaconda_conda_forge = "False"
      mirror_anaconda_conda_anaconda = "False"
      mirror_cran = "False"
      mirror_pypi = "False"
      mirror_debian = "False"
      mirror_nltk = "True"
    }
  )
  execution_role_arn    = "${aws_iam_role.mirrors_sync_task_execution.*.arn[count.index]}"
  task_role_arn         = "${aws_iam_role.mirrors_sync_task.*.arn[count.index]}"
  network_mode          = "awsvpc"
  cpu                   = "${local.mirrors_sync_container_cpu}"
  memory                = "${local.mirrors_sync_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

resource "aws_cloudwatch_log_group" "mirrors_sync" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name              = "jupyterhub-mirrors-sync"
  retention_in_days = "3653"
}

resource "aws_cloudwatch_log_subscription_filter" "mirrors_sync" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name            = "jupyterhub-mirrors-sync"
  log_group_name  = "${aws_cloudwatch_log_group.mirrors_sync.*.name[count.index]}"
  filter_pattern  = ""
  destination_arn = "${var.cloudwatch_destination_arn}"
}

resource "aws_iam_role" "mirrors_sync_task_execution" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name               = "mirrors-sync-task-execution"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.mirrors_sync_task_execution_ecs_tasks_assume_role.*.json[count.index]}"
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
  role       = "${aws_iam_role.mirrors_sync_task_execution.*.name[count.index]}"
  policy_arn = "${aws_iam_policy.mirrors_sync_task_execution.*.arn[count.index]}"
}

resource "aws_iam_policy" "mirrors_sync_task_execution" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name        = "jupyterhub-mirrors-sync-task-execution"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.mirrors_sync_task_execution.*.json[count.index]}"
}

data "aws_iam_policy_document" "mirrors_sync_task_execution" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.mirrors_sync.*.arn[count.index]}:*",
    ]
  }

  statement {
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]

    resources = [
      "${aws_ecr_repository.mirrors_sync.arn}",
      "${aws_ecr_repository.mirrors_sync_cran_binary.arn}",
      "${aws_ecr_repository.mirrors_sync_cran_binary_rv4.arn}",
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

resource "aws_iam_role" "mirrors_sync_task" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name               = "jupyterhub-mirrors-sync-task"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.mirrors_sync_task_ecs_tasks_assume_role.*.json[count.index]}"
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
  role       = "${aws_iam_role.mirrors_sync_task.*.name[count.index]}"
  policy_arn = "${aws_iam_policy.mirrors_sync_task.*.arn[count.index]}"
}

resource "aws_iam_policy" "mirrors_sync_task" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name        = "jupyterhub-mirrors-sync-task"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.mirrors_sync_task.*.json[count.index]}"
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
      "${aws_s3_bucket.mirrors.*.arn[count.index]}/*",
    ]
  }
  statement {
    actions = [
        "s3:ListBucket",
    ]

    resources = [
      "${aws_s3_bucket.mirrors.*.arn[count.index]}",
    ]
  }
}

resource "aws_cloudwatch_event_rule" "daily_at_four_am" {
  count = "${var.mirrors_bucket_name != "" ? 2 : 0}"
  name                = "daily-four-am-${count.index}"
  description         = "daily-four-am-${count.index}"
  schedule_expression = "cron(0 4 * * ? *)"
}

resource "aws_cloudwatch_event_target" "mirrors_sync_cran_binary_scheduled_task" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  target_id = "${var.prefix}-mirror-cran-binary"
  arn       = "${aws_ecs_cluster.main_cluster.arn}"
  rule      = "${aws_cloudwatch_event_rule.daily_at_four_am[0].name}"
  role_arn  = "${aws_iam_role.mirrors_sync_events.*.arn[count.index]}"

  ecs_target {
    task_count          = 1
    task_definition_arn = "${aws_ecs_task_definition.mirrors_sync_cran_binary.*.arn[count.index]}"
    launch_type = "FARGATE"
    propagate_tags = "TASK_DEFINITION"

    network_configuration {
      # In a public subnet to KISS and minimise costs. NAT traffic is more expensive
      subnets = "${aws_subnet.public.*.id}"
      security_groups = ["${aws_security_group.mirrors_sync.id}"]
      assign_public_ip = true
    }
  }
}

resource "aws_cloudwatch_event_target" "mirrors_sync_cran_binary_rv4_scheduled_task" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  target_id = "${var.prefix}-mirror-cran-binary-rv4"
  arn       = "${aws_ecs_cluster.main_cluster.arn}"
  rule      = "${aws_cloudwatch_event_rule.daily_at_four_am[0].name}"
  role_arn  = "${aws_iam_role.mirrors_sync_events.*.arn[count.index]}"

  ecs_target {
    task_count          = 1
    task_definition_arn = "${aws_ecs_task_definition.mirrors_sync_cran_binary_rv4.*.arn[count.index]}"
    launch_type = "FARGATE"
    propagate_tags = "TASK_DEFINITION"

    network_configuration {
      # In a public subnet to KISS and minimise costs. NAT traffic is more expensive
      subnets = "${aws_subnet.public.*.id}"
      security_groups = ["${aws_security_group.mirrors_sync.id}"]
      assign_public_ip = true
    }
  }
}

resource "aws_cloudwatch_event_target" "mirrors_sync_nltk_scheduled_task" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  target_id = "${var.prefix}-mirror-nltk"
  arn       = "${aws_ecs_cluster.main_cluster.arn}"
  rule      = "${aws_cloudwatch_event_rule.daily_at_four_am[0].name}"
  role_arn  = "${aws_iam_role.mirrors_sync_events.*.arn[count.index]}"

  ecs_target {
    task_count          = 1
    task_definition_arn = "${aws_ecs_task_definition.mirrors_sync_nltk.*.arn[count.index]}"
    launch_type = "FARGATE"
    propagate_tags = "TASK_DEFINITION"

    network_configuration {
      # In a public subnet to KISS and minimise costs. NAT traffic is more expensive
      subnets = "${aws_subnet.public.*.id}"
      security_groups = ["${aws_security_group.mirrors_sync.id}"]
      assign_public_ip = true
    }
  }
}

resource "aws_cloudwatch_event_target" "mirrors_sync_debian_task" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  target_id = "${var.prefix}-mirror-debian"
  arn       = "${aws_ecs_cluster.main_cluster.arn}"
  rule      = "${aws_cloudwatch_event_rule.daily_at_four_am[1].name}"
  role_arn  = "${aws_iam_role.mirrors_sync_events.*.arn[count.index]}"

  ecs_target {
    task_count          = 1
    task_definition_arn = "${aws_ecs_task_definition.mirrors_sync_debian.*.arn[count.index]}"
    launch_type = "FARGATE"
    propagate_tags = "TASK_DEFINITION"

    network_configuration {
      # In a public subnet to KISS and minimise costs. NAT traffic is more expensive
      subnets = "${aws_subnet.public.*.id}"
      security_groups = ["${aws_security_group.mirrors_sync.id}"]
      assign_public_ip = true
    }
  }
}

resource "aws_iam_role" "mirrors_sync_events" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name = "${var.prefix_underscore}_mirrors_sync_events"
  assume_role_policy = "${data.aws_iam_policy_document.mirrors_sync_events_assume_role_policy.*.json[count.index]}"
}

data "aws_iam_policy_document" "mirrors_sync_events_assume_role_policy" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "mirrors_sync_events_run_mirror" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name = "${var.prefix_underscore}_mirrors_sync_events_run_mirror"
  role = "${aws_iam_role.mirrors_sync_events.*.id[count.index]}"
  policy = "${data.aws_iam_policy_document.mirrors_sync_events_run_tasks.*.json[count.index]}"
}

data "aws_iam_policy_document" "mirrors_sync_events_run_tasks" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  statement {
    actions = [
      "ecs:RunTask",
    ]

    resources = [
      "arn:aws:ecs:*:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.mirrors_sync_cran.*.family[count.index]}:*",
      "arn:aws:ecs:*:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.mirrors_sync_cran_binary.*.family[count.index]}:*",
      "arn:aws:ecs:*:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.mirrors_sync_conda.*.family[count.index]}:*",
      "arn:aws:ecs:*:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.mirrors_sync_pypi.*.family[count.index]}:*",
      "arn:aws:ecs:*:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.mirrors_sync_nltk.*.family[count.index]}:*",
      "arn:aws:ecs:*:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.mirrors_sync_debian.*.family[count.index]}:*",
    ]
  }

  statement {
    actions = [
      "iam:PassRole"
    ]
    resources = [
      "${aws_iam_role.mirrors_sync_task.*.arn[count.index]}",
      "${aws_iam_role.mirrors_sync_task_execution.*.arn[count.index]}",
    ]
    condition {
      test = "StringLike"
      variable = "iam:PassedToService"
      values = ["ecs-tasks.amazonaws.com"]
    }
  }
}
