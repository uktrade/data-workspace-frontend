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
}

resource "aws_s3_bucket_logging" "uploads_logging" {
  bucket = aws_s3_bucket.uploads.id
  target_bucket = aws_s3_bucket.logging.id
  target_prefix = "logs/"
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

  server_side_encryption_configuration {
    rule {
      bucket_key_enabled = true
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
}
