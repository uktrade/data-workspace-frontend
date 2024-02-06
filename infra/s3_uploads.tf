resource "aws_s3_bucket" "uploads" {
  bucket = "${var.uploads_bucket}"

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }

  versioning {
    enabled    = true
    mfa_delete = false
  }

  logging {
    target_bucket = "${aws_s3_bucket.logging.id}"
  }

}

resource "aws_s3_bucket_policy" "uploads" {
  bucket = "${aws_s3_bucket.uploads.id}"
  policy = "${data.aws_iam_policy_document.uploads_bucket.json}"
}

data "aws_iam_policy_document" "uploads_bucket" {
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
      "arn:aws:s3:::${aws_s3_bucket.uploads.id}/*",
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

resource "aws_s3_bucket" "logging" {
  bucket = "${var.uploads_bucket}-logging"
  acl    = "log-delivery-write"

  server_side_encryption_configuration {
    rule {
      bucket_key_enabled = true
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
}
