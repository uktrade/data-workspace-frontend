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

  policy = "${data.aws_iam_policy_document.aws_vpc_endpoint_ecr_dkr.json}"
}

data "aws_iam_policy_document" "aws_vpc_endpoint_ecr_dkr" {
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
