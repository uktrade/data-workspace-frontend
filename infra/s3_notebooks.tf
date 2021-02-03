resource "aws_s3_bucket" "notebooks" {
  bucket = "${var.notebooks_bucket}"

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

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "POST", "PUT", "HEAD", "DELETE"]
    allowed_origins = var.notebooks_bucket_cors_domains
    expose_headers  = ["ETag", "x-amz-meta-mtime"]
    max_age_seconds = 3000
  }
}

resource "aws_s3_bucket_policy" "notebooks" {
  bucket = "${aws_s3_bucket.notebooks.id}"
  policy = "${data.aws_iam_policy_document.notebooks.json}"
}

data "aws_iam_policy_document" "notebooks" {
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
      "arn:aws:s3:::${aws_s3_bucket.notebooks.id}/*",
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
