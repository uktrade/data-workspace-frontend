resource "aws_ecr_repository" "user_provided" {
  name = "${var.prefix}-user-provided"
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
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer"
    ]

    resources = [
      "*",
    ]
  }
}
