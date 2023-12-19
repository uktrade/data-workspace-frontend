resource "aws_ecr_repository" "user_provided" {
  name = "${var.prefix}-user-provided"
}

resource "aws_ecr_repository" "admin" {
  name = "${var.prefix}-admin"
}

resource "aws_ecr_repository" "jupyterlab_python" {
  name = "${var.prefix}-jupyterlab-python"
}

resource "aws_ecr_repository" "rstudio" {
  name = "${var.prefix}-rstudio"
}

resource "aws_ecr_repository" "rstudio_rv4" {
  name = "${var.prefix}-rstudio-rv4"
}

resource "aws_ecr_repository" "pgadmin" {
  name = "${var.prefix}-pgadmin"
}

resource "aws_ecr_repository" "remotedesktop" {
  name = "${var.prefix}-remotedesktop"
}

resource "aws_ecr_repository" "theia" {
  name = "${var.prefix}-theia"
}

resource "aws_ecr_repository" "s3sync" {
  name = "${var.prefix}-s3sync"
}

resource "aws_ecr_repository" "metrics" {
  name = "${var.prefix}-metrics"
}

resource "aws_ecr_repository" "sentryproxy" {
  name = "${var.prefix}-sentryproxy"
}

resource "aws_ecr_repository" "dns_rewrite_proxy" {
  name = "${var.prefix}-dns-rewrite-proxy"
}

resource "aws_ecr_repository" "healthcheck" {
  name = "${var.prefix}-healthcheck"
}

resource "aws_ecr_repository" "prometheus" {
  name = "${var.prefix}-prometheus"
}

resource "aws_ecr_repository" "gitlab" {
  name = "${var.prefix}-gitlab"
}

resource "aws_ecr_repository" "visualisation_base" {
  name = "${var.prefix}-visualisation-base"
}

resource "aws_ecr_repository" "visualisation_base_r" {
  name = "${var.prefix}-visualisation-base-r"
}

resource "aws_ecr_repository" "mirrors_sync" {
  name = "${var.prefix}-mirrors-sync"
}

resource "aws_ecr_repository" "mirrors_sync_cran_binary" {
  name = "${var.prefix}-mirrors-sync-cran-binary"
}

resource "aws_ecr_repository" "mirrors_sync_cran_binary_rv4" {
  name = "${var.prefix}-mirrors-sync-cran-binary-rv4"
}

resource "aws_ecr_repository" "superset" {
  name = "${var.prefix}-superset"
}

resource "aws_ecr_repository" "flower" {
  name = "${var.prefix}-flower"
}

resource "aws_ecr_repository" "mlflow" {
  name = "${var.prefix}-mlflow"
}

resource "aws_ecr_repository" "arango" {
  name = "${var.prefix}-arango"
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = "${aws_vpc.main.id}"
  service_name        = "com.amazonaws.${data.aws_region.aws_region.name}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  security_group_ids = ["${aws_security_group.ecr_dkr.id}"]
  subnet_ids = ["${aws_subnet.private_with_egress.*.id[0]}"]

  policy = "${data.aws_iam_policy_document.aws_vpc_endpoint_ecr.json}"
}

resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id            = "${aws_vpc.main.id}"
  service_name      = "com.amazonaws.${data.aws_region.aws_region.name}.ecr.api"
  vpc_endpoint_type = "Interface"
  private_dns_enabled = true

  security_group_ids = ["${aws_security_group.ecr_api.id}"]
  subnet_ids = ["${aws_subnet.private_with_egress.*.id[0]}"]

  policy = "${data.aws_iam_policy_document.aws_vpc_endpoint_ecr.json}"
}

data "aws_iam_policy_document" "aws_vpc_endpoint_ecr" {
  # Contains policies for both ECR and DKR endpoints, as recommended

  statement {
    principals {
      type = "AWS"
      identifiers = ["${aws_iam_role.admin_task.arn}"]
    }

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
    principals {
      type = "AWS"
      identifiers = ["${aws_iam_role.admin_task.arn}"]
    }

    actions = [
      "ecs:DescribeTaskDefinition",
    ]

    resources = [
      # ECS doesn't provide more-specific permission for DescribeTaskDefinition
      "*",
    ]
  }

  statement {
    principals {
      type = "AWS"
      identifiers = ["${aws_iam_role.admin_task.arn}"]
    }

    actions = [
      "ecs:RegisterTaskDefinition",
    ]

    resources = [
      # ECS doesn't provide more-specific permission for RegisterTaskDefinition
      "*",
    ]
  }

  statement {
    principals {
      type = "AWS"
      identifiers = ["${aws_iam_role.admin_task.arn}"]
    }

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
    principals {
      type = "AWS"
      identifiers = ["${aws_iam_role.admin_task.arn}"]
    }

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

  # For Fargate to start tasks
  statement {
    principals {
      type = "AWS"
      identifiers = ["*"]
    }

    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer"
    ]

    resources = [
      "*",
    ]
  }

  /* For ECS to fetch images */
  statement {
    principals {
      type = "AWS"
      identifiers = ["*"]
    }

    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]

    resources = [
      "${aws_ecr_repository.admin.arn}",
      "${aws_ecr_repository.jupyterlab_python.arn}",
      "${aws_ecr_repository.rstudio.arn}",
      "${aws_ecr_repository.rstudio_rv4.arn}",
      "${aws_ecr_repository.pgadmin.arn}",
      "${aws_ecr_repository.remotedesktop.arn}",
      "${aws_ecr_repository.theia.arn}",
      "${aws_ecr_repository.s3sync.arn}",
      "${aws_ecr_repository.metrics.arn}",
      "${aws_ecr_repository.sentryproxy.arn}",
      "${aws_ecr_repository.dns_rewrite_proxy.arn}",
      "${aws_ecr_repository.healthcheck.arn}",
      "${aws_ecr_repository.prometheus.arn}",
      "${aws_ecr_repository.gitlab.arn}",
      "${aws_ecr_repository.mirrors_sync.arn}",
      "${aws_ecr_repository.mirrors_sync_cran_binary.arn}",
      "${aws_ecr_repository.superset.arn}",
      "${aws_ecr_repository.flower.arn}",
      "${aws_ecr_repository.mlflow.arn}",
    ]
  }

  # For GitLab runner to login and get base images
  statement {
    principals {
      type = "AWS"
      identifiers = ["${aws_iam_role.gitlab_runner.arn}"]
    }

    actions = [
      "ecr:GetAuthorizationToken",
    ]

    resources = [
      "*",
    ]
  }

  statement {
    principals {
      type = "AWS"
      identifiers = ["${aws_iam_role.gitlab_runner.arn}"]
    }

    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]

    resources = [
      "${aws_ecr_repository.visualisation_base.arn}",
      "${aws_ecr_repository.visualisation_base_r.arn}",
    ]
  }

  # For GitLab runner to login and push user-provided images
  statement {
    principals {
      type = "AWS"
      identifiers = ["${aws_iam_role.gitlab_runner.arn}"]
    }

    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:GetRepositoryPolicy",
      "ecr:DescribeRepositories",
      "ecr:ListImages",
      "ecr:DescribeImages",
      "ecr:BatchGetImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
    ]
    resources = [
      "${aws_ecr_repository.user_provided.arn}",
    ]
  }
}
