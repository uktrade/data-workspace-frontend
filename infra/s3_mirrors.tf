resource "aws_s3_bucket" "mirrors" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  bucket = "${var.mirrors_bucket_name}"

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
}

data "aws_s3_bucket" "mirrors" {
  count = "${var.mirrors_data_bucket_name != "" ? 1 : 0}"
  bucket = "${var.mirrors_data_bucket_name}"
  provider = "aws.mirror"
}

resource "aws_s3_bucket_policy" "mirrors" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  bucket = "${aws_s3_bucket.mirrors.id}"
  policy = "${data.aws_iam_policy_document.mirrors.json}"
}

data "aws_iam_policy_document" "mirrors" {
  count = "${var.mirrors_bucket_name != "" ? 1 : 0}"
  statement {
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = [
      "s3:*",
    ]
    resources = [
      "arn:aws:s3:::${aws_s3_bucket.mirrors.id}/*",
    ]
    condition {
      test = "Bool"
      variable = "aws:SecureTransport"
      values = [
        "false"
      ]
    }
  }

  # We are happy with public GET
  statement {
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = [
        "s3:GetObject",
    ]

    resources = [
      "${aws_s3_bucket.mirrors.arn}/*",
    ]
  }
}
