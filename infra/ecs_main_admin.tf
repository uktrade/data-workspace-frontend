locals {
  admin_container_vars = {
    container_image   = "${aws_ecr_repository.admin.repository_url}:${data.external.admin_current_tag.result.tag}"
    container_name    = "${local.admin_container_name}"
    container_port    = "${local.admin_container_port}"
    container_cpu     = "${local.admin_container_cpu}"
    container_memory  = "${local.admin_container_memory}"

    log_group  = "${aws_cloudwatch_log_group.admin.name}"
    log_region = "${data.aws_region.aws_region.name}"

    root_domain               = "${var.admin_domain}"
    admin_db__host            = "${aws_db_instance.admin.address}"
    admin_db__name            = "${aws_db_instance.admin.db_name}"
    admin_db__password        = "${random_string.aws_db_instance_admin_password.result}"
    admin_db__port            = "${aws_db_instance.admin.port}"
    admin_db__user            = "${aws_db_instance.admin.username}"
    datasets_db__host         = "${aws_rds_cluster_instance.datasets.endpoint}"
    datasets_db__name         = "${aws_rds_cluster.datasets.database_name}"
    datasets_db__password     = "${random_string.aws_rds_cluster_instance_datasets_password.result}"
    datasets_db__port         = "${aws_rds_cluster_instance.datasets.port}"
    datasets_db__user         = "${aws_rds_cluster.datasets.master_username}"
    datasets_db__instance_id  = "${aws_rds_cluster_instance.datasets.identifier}"
    authbroker_client_id      = "${var.admin_authbroker_client_id}"
    authbroker_client_secret  = "${var.admin_authbroker_client_secret}"
    authbroker_url            = "${var.admin_authbroker_url}"
    secret_key                = "${random_string.admin_secret_key.result}"

    environment = "${var.admin_environment}"

    uploads_bucket = "${var.uploads_bucket}"
    notebooks_bucket = "${var.notebooks_bucket}"
    mirror_remote_root = "https://s3-${data.aws_region.aws_region.name}.amazonaws.com/${var.mirrors_data_bucket_name != "" ? var.mirrors_data_bucket_name : var.mirrors_bucket_name}/"

    appstream_url = "https://${var.appstream_domain}/"
    support_url = "https://${var.support_domain}/"

    redis_url = "redis://${aws_elasticache_cluster.admin.cache_nodes.0.address}:6379"

    sentry_dsn = "${var.sentry_dsn}"

    notebook_task_role__role_prefix                        = "${var.notebook_task_role_prefix}"
    notebook_task_role__permissions_boundary_arn           = "${aws_iam_policy.notebook_task_boundary.arn}"
    notebook_task_role__assume_role_policy_document_base64 = "${base64encode(data.aws_iam_policy_document.notebook_s3_access_ecs_tasks_assume_role.json)}"
    notebook_task_role__policy_name                        = "${var.notebook_task_role_policy_name}"
    notebook_task_role__policy_document_template_base64    = "${base64encode(data.aws_iam_policy_document.notebook_s3_access_template.json)}"
    notebook_task_role__s3_bucket_arn                      = "${aws_s3_bucket.notebooks.arn}"
    fargate_spawner__aws_region            = "${data.aws_region.aws_region.name}"
    fargate_spawner__aws_ecs_host          = "ecs.${data.aws_region.aws_region.name}.amazonaws.com"
    fargate_spawner__notebook_port         = "${local.notebook_container_port}"
    fargate_spawner__task_custer_name      = "${aws_ecs_cluster.notebooks.name}"
    fargate_spawner__task_container_name   = "${local.notebook_container_name}"
    fargate_spawner__task_definition_arn   = "${aws_ecs_task_definition.notebook.family}:${aws_ecs_task_definition.notebook.revision}"
    fargate_spawner__task_security_group   = "${aws_security_group.notebooks.id}"
    fargate_spawner__task_subnet           = "${aws_subnet.private_without_egress.*.id[0]}"

    fargate_spawner__jupyterlabpython_task_definition_arn = "${aws_ecs_task_definition.jupyterlabpython.family}"
    fargate_spawner__rstudio_task_definition_arn   = "${aws_ecs_task_definition.rstudio.family}"
    fargate_spawner__rstudio_rv4_task_definition_arn   = "${aws_ecs_task_definition.rstudio_rv4.family}"
    fargate_spawner__pgadmin_task_definition_arn   = "${aws_ecs_task_definition.pgadmin.family}"
    fargate_spawner__remotedesktop_task_definition_arn  = "${aws_ecs_task_definition.remotedesktop.family}"
    fargate_spawner__theia_task_definition_arn  = "${aws_ecs_task_definition.theia.family}"
    fargate_spawner__superset_task_definition_arn  = "${aws_ecs_task_definition.superset.family}"

    fargate_spawner__user_provided_task_definition_arn                        = "${aws_ecs_task_definition.user_provided.family}"
    fargate_spawner__user_provided_task_role__policy_document_template_base64 = "${base64encode(data.aws_iam_policy_document.user_provided_access_template.json)}"
    fargate_spawner__user_provided_ecr_repository__name = "${aws_ecr_repository.user_provided.name}"

    zendesk_email = "${var.zendesk_email}"
    zendesk_subdomain = "${var.zendesk_subdomain}"
    zendesk_token = "${var.zendesk_token}"
    zendesk_service_field_id = "${var.zendesk_service_field_id}"
    zendesk_service_field_value = "${var.zendesk_service_field_value}"

    prometheus_domain = "${var.prometheus_domain}"
    metrics_service_discovery_basic_auth_user = "${var.metrics_service_discovery_basic_auth_user}"
    metrics_service_discovery_basic_auth_password = "${var.metrics_service_discovery_basic_auth_password}"

    google_analytics_site_id = "${var.google_analytics_site_id}"

    superset_root = "https://${var.superset_internal_domain}"
    superset_dw_user_username = "${var.superset_dw_user_username}"
    superset_dw_user_password = "${var.superset_dw_user_password}"

    quicksight_namespace = "${var.quicksight_namespace}"
    quicksight_user_region = "${var.quicksight_user_region}"
    quicksight_vpc_arn = "${var.quicksight_vpc_arn}"
    quicksight_dashboard_group = "${var.quicksight_dashboard_group}"
    quicksight_author_custom_permissions = "${var.quicksight_author_custom_permissions}"
    quicksight_author_iam_arn = "${var.quicksight_author_iam_arn}"
    quicksight_sso_url = "${var.quicksight_sso_url}"
    admin_dashboard_embedding_role_arn = "${aws_iam_role.admin_dashboard_embedding.arn}"

    efs_id = "${aws_efs_file_system.notebooks.id}"

    visualisation_cloudwatch_log_group = "${aws_cloudwatch_log_group.notebook.name}"
    
    flower_root = "http://${aws_lb.flower.dns_name}"

    jwt_private_key = "${var.jwt_private_key}"
    mlflow_port = "${local.mlflow_port}"
  }
}

resource "aws_ecs_service" "admin" {
  name                       = "${var.prefix}-admin"
  cluster                    = "${aws_ecs_cluster.main_cluster.id}"
  task_definition            = "${aws_ecs_task_definition.admin.arn}"
  desired_count              = 2
  launch_type                = "FARGATE"
  platform_version           = "1.4.0"
  deployment_maximum_percent = 600
  timeouts {}

  network_configuration {
    subnets         = "${aws_subnet.private_with_egress.*.id}"
    security_groups = ["${aws_security_group.admin_service.id}"]
  }

  load_balancer {
    target_group_arn = "${aws_alb_target_group.admin.arn}"
    container_port   = "${local.admin_container_port}"
    container_name   = "${local.admin_container_name}"
  }

  service_registries {
    registry_arn   = "${aws_service_discovery_service.admin.arn}"
  }

  depends_on = [
    # The target group must have been associated with the listener first
    "aws_alb_listener.admin",
  ]
}

resource "aws_service_discovery_service" "admin" {
  name = "${var.prefix}-admin"
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

resource "aws_ecs_task_definition" "admin" {
  family                   = "${var.prefix}-admin"
  container_definitions    = "${data.template_file.admin_container_definitions.rendered}"
  execution_role_arn       = "${aws_iam_role.admin_task_execution.arn}"
  task_role_arn            = "${aws_iam_role.admin_task.arn}"
  network_mode             = "awsvpc"
  cpu                      = "${local.admin_container_cpu}"
  memory                   = "${local.admin_container_memory}"
  requires_compatibilities = ["FARGATE"]

  lifecycle {
    ignore_changes = [
      "revision",
    ]
  }
}

data "template_file" "admin_container_definitions" {
  template = "${file("${path.module}/ecs_main_admin_container_definitions.json")}"

  vars = "${merge(local.admin_container_vars, tomap({"container_command" = "[\"/dataworkspace/start.sh\"]"}))}"
}

data "external" "admin_current_tag" {
  program = ["${path.module}/container-tag.sh"]

  query = {
    cluster_name = "${aws_ecs_cluster.main_cluster.name}"
    service_name = "${var.prefix}-admin"  # Manually specified to avoid a cycle
    container_name = "jupyterhub-admin"
  }
}

resource "aws_ecs_service" "admin_celery" {
  name                       = "${var.prefix}-admin-celery"
  cluster                    = "${aws_ecs_cluster.main_cluster.id}"
  task_definition            = "${aws_ecs_task_definition.admin_celery.arn}"
  desired_count              = 2
  launch_type                = "FARGATE"
  platform_version           = "1.4.0"
  deployment_maximum_percent = 600
  timeouts {}

  network_configuration {
    subnets         = "${aws_subnet.private_with_egress.*.id}"
    security_groups = ["${aws_security_group.admin_service.id}"]
  }
}

resource "aws_ecs_task_definition" "admin_celery" {
  family                   = "${var.prefix}-admin-celery"
  container_definitions    = "${data.template_file.admin_celery_container_definitions.rendered}"
  execution_role_arn       = "${aws_iam_role.admin_task_execution.arn}"
  task_role_arn            = "${aws_iam_role.admin_task.arn}"
  network_mode             = "awsvpc"
  cpu                      = "${local.celery_container_cpu}"
  memory                   = "${local.celery_container_memory}"
  requires_compatibilities = ["FARGATE"]

  lifecycle {
    ignore_changes = [
      "revision",
    ]
  }
}

data "template_file" "admin_celery_container_definitions" {
  template = "${file("${path.module}/ecs_main_admin_container_definitions.json")}"

  vars = "${merge(local.admin_container_vars, tomap({"container_command" = "[\"/dataworkspace/start-celery.sh\"]"}))}"
}

resource "random_string" "admin_secret_key" {
  length = 256
  special = false
}

resource "aws_cloudwatch_log_group" "admin" {
  name              = "${var.prefix}-admin"
  retention_in_days = "3653"
}

resource "aws_cloudwatch_log_subscription_filter" "admin" {
  count = "${var.cloudwatch_subscription_filter ? 1 : 0}"
  name            = "${var.prefix}-admin"
  log_group_name  = "${aws_cloudwatch_log_group.admin.name}"
  filter_pattern  = ""
  destination_arn = "${var.cloudwatch_destination_arn}"
}

resource "aws_iam_role" "admin_task_execution" {
  name               = "${var.prefix}-admin-task-execution"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.admin_task_execution_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "admin_task_execution_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "admin_task_execution" {
  role       = "${aws_iam_role.admin_task_execution.name}"
  policy_arn = "${aws_iam_policy.admin_task_execution.arn}"
}

resource "aws_iam_policy" "admin_task_execution" {
  name        = "${var.prefix}-admin-task-execution"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.admin_task_execution.json}"
}

data "aws_iam_policy_document" "admin_task_execution" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.admin.arn}:*",
    ]
  }

  statement {
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]

    resources = [
      "${aws_ecr_repository.admin.arn}",
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

resource "aws_iam_role" "admin_dashboard_embedding" {
  name = "${var.prefix}-quicksight-embedding"
  path = "/"
  assume_role_policy = "${data.aws_iam_policy_document.admin_dashboard_embedding_assume_role.json}"
}

resource "aws_iam_policy" "admin_dashboard_embedding" {
  name        = "${var.prefix}-quicksight-dashboard-embedding"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.admin_dashboard_embedding.json}"
}

data "aws_iam_policy_document" "admin_dashboard_embedding" {
  statement {
    actions = ["quicksight:RegisterUser"]
    resources = ["*"]
  }
  statement {
    actions = ["quicksight:CreateGroupMembership"]
    resources = ["*"]
  }
  statement {
    actions = ["quicksight:DescribeDashboard"]
    resources = ["*"]
  }
  statement {
    actions = ["quicksight:GetDashboardEmbedUrl"]
    resources = ["arn:aws:quicksight:*:${data.aws_caller_identity.aws_caller_identity.account_id}:dashboard/*"]
  }
  statement {
    actions = ["quicksight:GetAuthCode"]
    resources = ["arn:aws:quicksight:*:${data.aws_caller_identity.aws_caller_identity.account_id}:user/${var.quicksight_namespace}/${var.prefix}-quicksight-embedding/*"]
  }
}

data "aws_iam_policy_document" "admin_dashboard_embedding_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type = "AWS"
      identifiers = ["${aws_iam_role.admin_task.arn}"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "admin_dashboard_embedding" {
  role       = "${aws_iam_role.admin_dashboard_embedding.name}"
  policy_arn = "${aws_iam_policy.admin_dashboard_embedding.arn}"
}

resource "aws_iam_role" "admin_task" {
  name               = "${var.prefix}-admin-task"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.admin_task_ecs_tasks_assume_role.json}"
}

resource "aws_iam_role_policy_attachment" "admin_access_uploads_bucket" {
  role       = "${aws_iam_role.admin_task.name}"
  policy_arn = "${aws_iam_policy.admin_access_uploads_bucket.arn}"
}

resource "aws_iam_policy" "admin_access_uploads_bucket" {
  name        = "${var.prefix}-admin-access-uploads-bucket"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.admin_access_uploads_bucket.json}"
}

data "aws_iam_policy_document" "admin_access_uploads_bucket" {
  statement {
    actions = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
    ]

    resources = [
      "${aws_s3_bucket.uploads.arn}/*",
    ]
  }

  statement {
    actions = [
      "s3:GetBucketLocation",
    ]

    resources = [
      "${aws_s3_bucket.uploads.arn}",
    ]
  }
}

resource "aws_iam_role_policy_attachment" "admin_run_tasks" {
  role       = "${aws_iam_role.admin_task.name}"
  policy_arn = "${aws_iam_policy.admin_run_tasks.arn}"
}

resource "aws_iam_policy" "admin_run_tasks" {
  name        = "${var.prefix}-admin-run-tasks"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.admin_run_tasks.json}"
}

data "aws_iam_policy_document" "admin_run_tasks" {
  statement {
    actions = [
      "ecs:RunTask",
    ]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values = [
        "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:cluster/${aws_ecs_cluster.notebooks.name}",
      ]
    }

    resources = [
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.notebook.family}",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.notebook.family}-*",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.jupyterlabpython.family}",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.jupyterlabpython.family}-*",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.rstudio.family}",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.rstudio.family}-*",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.rstudio_rv4.family}",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.rstudio_rv4.family}-*",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.pgadmin.family}",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.pgadmin.family}-*",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.remotedesktop.family}",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.remotedesktop.family}-*",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.theia.family}",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.theia.family}-*",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.superset.family}",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.superset.family}-*",
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task-definition/${aws_ecs_task_definition.user_provided.family}-*",
    ]
  }

  statement {
    actions = [
      "ecr:DescribeImages",
      "ecr:BatchGetImage",
      "ecr:PutImage",
    ]

    resources = [
      "${aws_ecr_repository.user_provided.arn}",
    ]
  }

  statement {
    actions = [
      "ecs:DescribeTaskDefinition",
    ]

    resources = [
      # ECS doesn't provide more-specific permission for DescribeTaskDefinition
      "*",
    ]
  }

  statement {
    actions = [
      "ecs:RegisterTaskDefinition",
    ]

    resources = [
      # ECS doesn't provide more-specific permission for RegisterTaskDefinition
      "*",
    ]
  }

  statement {
    actions = [
      "ecs:StopTask",
    ]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values = [
        "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:cluster/${aws_ecs_cluster.notebooks.name}",
      ]
    }

    resources = [
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task/*",
    ]
  }

  statement {
    actions = [
      "ecs:DescribeTasks",
    ]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values = [
        "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:cluster/${aws_ecs_cluster.notebooks.name}",
      ]
    }

    resources = [
      "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:task/*",
    ]
  }

  statement {
    actions = [
      "iam:PassRole"
    ]
    resources = [
      "${aws_iam_role.notebook_task_execution.arn}",
    ]
  }

  statement {
    actions = [
      "iam:GetRole",
      "iam:PassRole",
      "iam:UpdateAssumeRolePolicy",

      # The admin application creates temporary credentials, via AssumeRole, for a
      # user to manage their files in S3. The role, and therfore permissions are
      # exactly the ones that a user's containers can assume
      "sts:AssumeRole",
    ]

    resources = [
      "arn:aws:iam::${data.aws_caller_identity.aws_caller_identity.account_id}:role/${var.notebook_task_role_prefix}*"
    ]
  }

  statement {
    actions = [
      "iam:CreateRole",
      "iam:PutRolePolicy",
    ]

    resources = [
      "arn:aws:iam::${data.aws_caller_identity.aws_caller_identity.account_id}:role/${var.notebook_task_role_prefix}*"
    ]

    # The boundary means that JupyterHub can't create abitrary roles:
    # they must have this boundary attached. At most, they will
    # be able to have access to the entire bucket, and only
    # from inside the VPC
    condition {
      test     = "StringEquals"
      variable = "iam:PermissionsBoundary"
      values   = [
        "${aws_iam_policy.notebook_task_boundary.arn}",
      ]
    }
  }

  statement {
    actions = [
      "quicksight:*",
    ]

    resources = [
      # ECS doesn't provide more-specific permission for RegisterTaskDefinition
      "*",
    ]
  }

  statement {
    actions = [
      "sts:AssumeRole",
    ]

    resources = [
      "${aws_iam_role.admin_dashboard_embedding.arn}"
    ]
  }
}

resource "aws_iam_role_policy_attachment" "admin_admin_store_db_creds_in_s3_task" {
  role       = "${aws_iam_role.admin_task.name}"
  policy_arn = "${aws_iam_policy.admin_store_db_creds_in_s3_task.arn}"
}

resource "aws_iam_role" "admin_store_db_creds_in_s3_task" {
  name               = "${var.prefix}-admin-store-db-creds-in-s3-task"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.admin_task_ecs_tasks_assume_role.json}"
}

resource "aws_iam_role_policy_attachment" "admin_store_db_creds_in_s3_task" {
  role       = "${aws_iam_role.admin_store_db_creds_in_s3_task.name}"
  policy_arn = "${aws_iam_policy.admin_store_db_creds_in_s3_task.arn}"
}

resource "aws_iam_policy" "admin_store_db_creds_in_s3_task" {
  name        = "${var.prefix}-admin-store-db-creds-in-s3-task"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.admin_store_db_creds_in_s3_task.json}"
}

data "aws_iam_policy_document" "admin_store_db_creds_in_s3_task" {
  statement {
    actions = [
        "s3:PutObject",
        "s3:PutObjectAcl",
    ]

    resources = [
      "${aws_s3_bucket.notebooks.arn}/*",
      "arn:aws:s3:::appstream2-36fb080bb8-eu-west-1-664841488776/*",
    ]
  }
}

data "aws_iam_policy_document" "admin_task_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_alb" "admin" {
  name            = "${var.prefix}-admin"
  subnets         = "${aws_subnet.public.*.id}"
  security_groups = ["${aws_security_group.admin_alb.id}"]
  enable_deletion_protection = true
  timeouts {}

  access_logs {
    bucket  = "${aws_s3_bucket.alb_access_logs.id}"
    prefix  = "admin"
    enabled = true
  }

  depends_on = [
    "aws_s3_bucket_policy.alb_access_logs",
  ]
}

resource "aws_alb_listener" "admin" {
  load_balancer_arn = "${aws_alb.admin.arn}"
  port              = "${local.admin_alb_port}"
  protocol          = "HTTPS"

  default_action {
    target_group_arn = "${aws_alb_target_group.admin.arn}"
    type             = "forward"
  }

  ssl_policy      = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn = "${aws_acm_certificate_validation.admin.certificate_arn}"
}

resource "aws_alb_listener" "admin_http" {
  load_balancer_arn = "${aws_alb.admin.arn}"
  port              = "80"
  protocol          = "HTTP"

  default_action {
    target_group_arn = "${aws_alb_target_group.admin.arn}"
    type             = "forward"
  }
}

resource "aws_alb_target_group" "admin" {
  name_prefix = "jhadm-"
  port        = "${local.admin_container_port}"
  protocol    = "HTTP"
  vpc_id      = "${aws_vpc.main.id}"
  target_type = "ip"
  deregistration_delay = "${var.admin_deregistration_delay}"

  health_check {
    path = "/healthcheck"
    protocol = "HTTP"
    healthy_threshold = 3
    unhealthy_threshold = 2
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_elasticache_cluster" "admin" {
  cluster_id           = "${var.prefix_short}-admin"
  engine               = "redis"
  node_type            = "cache.t2.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis5.0"
  engine_version       = "5.0.6"
  port                 = 6379
  subnet_group_name    = "${aws_elasticache_subnet_group.admin.name}"
  security_group_ids   = ["${aws_security_group.admin_redis.id}"]
}

resource "aws_elasticache_subnet_group" "admin" {
  name               = "${var.prefix_short}-admin"
  subnet_ids         = "${aws_subnet.private_with_egress.*.id}"
}

resource "aws_iam_role_policy_attachment" "admin_cloudwatch_logs" {
  role       = "${aws_iam_role.admin_task.name}"
  policy_arn = "${aws_iam_policy.admin_cloudwatch_logs.arn}"
}

resource "aws_iam_policy" "admin_cloudwatch_logs" {
  name        = "${var.prefix}-admin-cloudwatch-logs"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.admin_cloudwatch_logs.json}"
}

data "aws_iam_policy_document" "admin_cloudwatch_logs" {
  statement {
    actions = ["logs:GetLogEvents"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy_attachment" "admin_datasets_database_rds_logs" {
  role       = "${aws_iam_role.admin_task.name}"
  policy_arn = "${aws_iam_policy.admin_datasets_database_rds_logs.arn}"
}

resource "aws_iam_policy" "admin_datasets_database_rds_logs" {
  name        = "${var.prefix}-admin-datasets-database-rds-logs"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.admin_datasets_database_rds_logs.json}"
}

data "aws_iam_policy_document" "admin_datasets_database_rds_logs" {
  statement {
    actions = [
      "rds:DownloadDBLogFilePortion",
      "rds:DescribeDBLogFiles"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy_attachment" "admin_list_ecs_tasks" {
  role       = "${aws_iam_role.admin_task.name}"
  policy_arn = "${aws_iam_policy.admin_list_ecs_tasks.arn}"
}

resource "aws_iam_policy" "admin_list_ecs_tasks" {
  name        = "${var.prefix}-admin-list-ecs-tasks"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.admin_list_ecs_tasks.json}"
}

data "aws_iam_policy_document" "admin_list_ecs_tasks" {
  statement {
    actions = [
      "ecs:ListTasks",
      "ecs:DescribeTasks"
    ]
    resources = ["*"]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values = [
        "arn:aws:ecs:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:cluster/${aws_ecs_cluster.notebooks.name}",
      ]
    }
  }
}
