resource "aws_s3_bucket" "mlflow" {
  count  = "${length(var.mlflow_instances)}"
  bucket = "${var.mlflow_artifacts_bucket}-${var.mlflow_instances[count.index]}"

  versioning {
    enabled = true
  }

  lifecycle_rule {
    enabled = true

    noncurrent_version_expiration {
      days = 365
    }
    abort_incomplete_multipart_upload_days = 7
  }
}

resource "aws_s3_bucket_policy" "mlflow" {
  count  = "${length(var.mlflow_instances)}"
  bucket = "${aws_s3_bucket.mlflow[count.index].id}"
  policy = "${data.aws_iam_policy_document.mlflow[count.index].json}"
}

data "aws_iam_policy_document" "mlflow" {
  count  = "${length(var.mlflow_instances)}"
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
      "arn:aws:s3:::${aws_s3_bucket.mlflow[count.index].id}/*",
    ]
    condition {
      test = "Bool"
      variable = "aws:SecureTransport"
      values = [
        "false"
      ]
    }
  }
}
