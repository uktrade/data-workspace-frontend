resource "aws_s3_bucket" "alb_access_logs" {
  bucket = "${var.alb_access_logs_bucket}"

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }

  lifecycle_rule {
    enabled = true
    expiration {
      days = 3653
    }
  }
}

resource "aws_s3_bucket_policy" "alb_access_logs" {
  bucket = "${aws_s3_bucket.alb_access_logs.id}"
  policy = "${data.aws_iam_policy_document.aws_s3_bucket_policy_alb_access_logs.json}"
}

data "aws_iam_policy_document" "aws_s3_bucket_policy_alb_access_logs" {
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
      "arn:aws:s3:::${aws_s3_bucket.alb_access_logs.id}/*",
    ]
    condition {
      test = "Bool"
      variable = "aws:SecureTransport"
      values = [
        "false"
      ]
    }
  }

  statement {
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["${var.alb_logs_account}"]
    }
    actions = [
      "s3:PutObject",
    ]
    resources = [
      "arn:aws:s3:::${aws_s3_bucket.alb_access_logs.id}/*",
    ]
  }
}
