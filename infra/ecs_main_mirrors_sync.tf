resource "aws_ecs_task_definition" "mirrors_sync_conda" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  family                = "jupyterhub-mirrors-sync-conda"
  container_definitions = "${data.template_file.mirrors_sync_container_definitions_conda.rendered}"
  execution_role_arn    = "${aws_iam_role.mirrors_sync_task_execution.arn}"
  task_role_arn         = "${aws_iam_role.mirrors_sync_task.arn}"
  network_mode          = "awsvpc"
  cpu                   = "${local.mirrors_sync_container_cpu}"
  memory                = "${local.mirrors_sync_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

data "template_file" "mirrors_sync_container_definitions_conda" {
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

    mirror_anaconda_r = "True"
    mirror_anaconda_conda_forge = "True"
    mirror_anaconda_conda_anaconda = "True"
    mirror_cran = "False"
    mirror_pypi = "False"
    mirror_debian = "False"
    mirror_nltk = "False"
    mirror_openstreetmap = "False"
  }
}

resource "aws_ecs_task_definition" "mirrors_sync_cran" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  family                = "jupyterhub-mirrors-sync-cran"
  container_definitions = "${data.template_file.mirrors_sync_container_definitions_cran.rendered}"
  execution_role_arn    = "${aws_iam_role.mirrors_sync_task_execution.arn}"
  task_role_arn         = "${aws_iam_role.mirrors_sync_task.arn}"
  network_mode          = "awsvpc"
  cpu                   = "${local.mirrors_sync_container_cpu}"
  memory                = "${local.mirrors_sync_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

data "template_file" "mirrors_sync_container_definitions_cran" {
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

    mirror_anaconda_r = "False"
    mirror_anaconda_conda_forge = "False"
    mirror_anaconda_conda_anaconda = "False"
    mirror_cran = "True"
    mirror_pypi = "False"
    mirror_debian = "False"
    mirror_nltk = "False"
    mirror_openstreetmap = "False"
  }
}

resource "aws_ecs_task_definition" "mirrors_sync_pypi" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  family                = "jupyterhub-mirrors-sync-pypi"
  container_definitions = "${data.template_file.mirrors_sync_container_definitions_pypi.rendered}"
  execution_role_arn    = "${aws_iam_role.mirrors_sync_task_execution.arn}"
  task_role_arn         = "${aws_iam_role.mirrors_sync_task.arn}"
  network_mode          = "awsvpc"
  cpu                   = "${local.mirrors_sync_container_cpu}"
  memory                = "${local.mirrors_sync_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

data "template_file" "mirrors_sync_container_definitions_pypi" {
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

    mirror_anaconda_r = "False"
    mirror_anaconda_conda_forge = "False"
    mirror_anaconda_conda_anaconda = "False"
    mirror_cran = "False"
    mirror_pypi = "True"
    mirror_debian = "False"
    mirror_nltk = "False"
    mirror_openstreetmap = "False"
  }
}

resource "aws_ecs_task_definition" "mirrors_sync_debian" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  family                = "jupyterhub-mirrors-sync-debian"
  container_definitions = "${data.template_file.mirrors_sync_container_definitions_debian.rendered}"
  execution_role_arn    = "${aws_iam_role.mirrors_sync_task_execution.arn}"
  task_role_arn         = "${aws_iam_role.mirrors_sync_task.arn}"
  network_mode          = "awsvpc"
  cpu                   = "${local.mirrors_sync_container_cpu}"
  memory                = "${local.mirrors_sync_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

data "template_file" "mirrors_sync_container_definitions_debian" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  template = "${file("${path.module}/ecs_main_mirrors_sync_container_definitions.json")}"

  vars {
    container_image    = "quay.io/uktrade/data-workspace-mirrors-sync:master"
    container_name     = "${local.mirrors_sync_container_name}"
    container_cpu      = "${local.mirrors_sync_container_cpu}"
    container_memory   = "${local.mirrors_sync_container_memory}"

    log_group  = "${aws_cloudwatch_log_group.mirrors_sync.name}"
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
    mirror_openstreetmap = "False"
  }
}

resource "aws_ecs_task_definition" "mirrors_sync_nltk" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  family                = "jupyterhub-mirrors-sync-nltk"
  container_definitions = "${data.template_file.mirrors_sync_container_definitions_nltk.rendered}"
  execution_role_arn    = "${aws_iam_role.mirrors_sync_task_execution.arn}"
  task_role_arn         = "${aws_iam_role.mirrors_sync_task.arn}"
  network_mode          = "awsvpc"
  cpu                   = "${local.mirrors_sync_container_cpu}"
  memory                = "${local.mirrors_sync_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

data "template_file" "mirrors_sync_container_definitions_nltk" {
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

    mirror_anaconda_r = "False"
    mirror_anaconda_conda_forge = "False"
    mirror_anaconda_conda_anaconda = "False"
    mirror_cran = "False"
    mirror_pypi = "False"
    mirror_debian = "False"
    mirror_nltk = "True"
    mirror_openstreetmap = "False"
  }
}

resource "aws_ecs_task_definition" "mirrors_sync_openstreetmap" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  family                = "jupyterhub-mirrors-sync-openstreetmap"
  container_definitions = "${data.template_file.mirrors_sync_container_definitions_openstreetmap.rendered}"
  execution_role_arn    = "${aws_iam_role.mirrors_sync_task_execution.arn}"
  task_role_arn         = "${aws_iam_role.mirrors_sync_task.arn}"
  network_mode          = "awsvpc"
  cpu                   = "${local.mirrors_sync_container_cpu}"
  memory                = "${local.mirrors_sync_container_memory}"
  requires_compatibilities = ["FARGATE"]
}

data "template_file" "mirrors_sync_container_definitions_openstreetmap" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  template = "${file("${path.module}/ecs_main_mirrors_sync_container_definitions.json")}"

  vars {
    container_image    = "quay.io/uktrade/data-workspace-mirrors-sync:master"
    container_name     = "${local.mirrors_sync_container_name}"
    container_cpu      = "${local.mirrors_sync_container_cpu}"
    container_memory   = "${local.mirrors_sync_container_memory}"

    log_group  = "${aws_cloudwatch_log_group.mirrors_sync.name}"
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
    mirror_nltk = "False"
    mirror_openstreetmap = "True"
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
  statement {
    actions = [
        "s3:ListBucket",
    ]

    resources = [
      "${aws_s3_bucket.mirrors.arn}",
    ]
  }
}

resource "aws_cloudwatch_event_rule" "daily_at_four_am" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name                = "daily-four-am"
  description         = "daily-four-am"
  schedule_expression = "cron(0 4 * * ? *)"
}

resource "aws_cloudwatch_event_target" "mirrors_sync_pypi_scheduled_task" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  target_id = "${var.prefix}-mirror-pypi"
  arn       = "${aws_ecs_cluster.main_cluster.arn}"
  rule      = "${aws_cloudwatch_event_rule.daily_at_four_am.name}"
  role_arn  = "${aws_iam_role.mirrors_sync_events.arn}"

  ecs_target {
    task_count          = 1
    task_definition_arn = "${aws_ecs_task_definition.mirrors_sync_pypi.arn}"
    launch_type = "FARGATE"
    network_configuration {
      # In a public subnet to KISS and minimise costs. NAT traffic is more expensive
      subnets =["${aws_subnet.public.*.id}"]
      security_groups = ["${aws_security_group.mirrors_sync.id}"]
      assign_public_ip = true
    }
  }
}

resource "aws_cloudwatch_event_target" "mirrors_sync_conda_scheduled_task" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  target_id = "${var.prefix}-mirror-conda"
  arn       = "${aws_ecs_cluster.main_cluster.arn}"
  rule      = "${aws_cloudwatch_event_rule.daily_at_four_am.name}"
  role_arn  = "${aws_iam_role.mirrors_sync_events.arn}"

  ecs_target {
    task_count          = 1
    task_definition_arn = "${aws_ecs_task_definition.mirrors_sync_conda.arn}"
    launch_type = "FARGATE"
    network_configuration {
      # In a public subnet to KISS and minimise costs. NAT traffic is more expensive
      subnets =["${aws_subnet.public.*.id}"]
      security_groups = ["${aws_security_group.mirrors_sync.id}"]
      assign_public_ip = true
    }
  }
}

resource "aws_cloudwatch_event_target" "mirrors_sync_cran_scheduled_task" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  target_id = "${var.prefix}-mirror-cran"
  arn       = "${aws_ecs_cluster.main_cluster.arn}"
  rule      = "${aws_cloudwatch_event_rule.daily_at_four_am.name}"
  role_arn  = "${aws_iam_role.mirrors_sync_events.arn}"

  ecs_target {
    task_count          = 1
    task_definition_arn = "${aws_ecs_task_definition.mirrors_sync_cran.arn}"
    launch_type = "FARGATE"
    network_configuration {
      # In a public subnet to KISS and minimise costs. NAT traffic is more expensive
      subnets =["${aws_subnet.public.*.id}"]
      security_groups = ["${aws_security_group.mirrors_sync.id}"]
      assign_public_ip = true
    }
  }
}

resource "aws_cloudwatch_event_target" "mirrors_sync_nltk_scheduled_task" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  target_id = "${var.prefix}-mirror-pypi"
  arn       = "${aws_ecs_cluster.main_cluster.arn}"
  rule      = "${aws_cloudwatch_event_rule.daily_at_four_am.name}"
  role_arn  = "${aws_iam_role.mirrors_sync_events.arn}"

  ecs_target {
    task_count          = 1
    task_definition_arn = "${aws_ecs_task_definition.mirrors_sync_nltk.arn}"
    launch_type = "FARGATE"
    network_configuration {
      # In a public subnet to KISS and minimise costs. NAT traffic is more expensive
      subnets =["${aws_subnet.public.*.id}"]
      security_groups = ["${aws_security_group.mirrors_sync.id}"]
      assign_public_ip = true
    }
  }
}

resource "aws_iam_role" "mirrors_sync_events" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  name = "${var.prefix_underscore}_mirrors_sync_events"
  assume_role_policy = "${data.aws_iam_policy_document.mirrors_sync_events_assume_role_policy.json}"
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
  role = "${aws_iam_role.mirrors_sync_events.id}"
  policy = "${data.aws_iam_policy_document.mirrors_sync_events_run_tasks.json}"
}

data "aws_iam_policy_document" "mirrors_sync_events_run_tasks" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  statement {
    actions = [
      "ecs:RunTask",
    ]

    resources = [
      "arn:aws:ecs:*:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.mirrors_sync_cran.family}:*",
      "arn:aws:ecs:*:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.mirrors_sync_conda.family}:*",
      "arn:aws:ecs:*:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.mirrors_sync_pypi.family}:*",
      "arn:aws:ecs:*:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.mirrors_sync_nltk.family}:*",
    ]
  }

  statement {
    actions = [
      "iam:PassRole"
    ]
    resources = [
      "${aws_iam_role.mirrors_sync_task.arn}",
      "${aws_iam_role.mirrors_sync_task_execution.arn}",
    ]
    condition {
      test = "StringLike"
      variable = "iam:PassedToService"
      values = ["ecs-tasks.amazonaws.com"]
    }
  }
}
