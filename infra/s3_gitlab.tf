# One bucket is used over several, to maximise chance of connection resuse
# since path-style access is being phased out

resource "aws_s3_bucket" "gitlab" {
  bucket = "${var.gitlab_bucket}"

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
}

resource "aws_s3_bucket_policy" "gitlab" {
  bucket = "${aws_s3_bucket.gitlab.id}"
  policy = "${data.aws_iam_policy_document.gitlab_bucket.json}"
}

data "aws_iam_policy_document" "gitlab_bucket" {
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
      "arn:aws:s3:::${aws_s3_bucket.gitlab.id}/*",
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

resource "aws_s3_bucket_object" "ssh_host_rsa_key" {
  bucket = "${aws_s3_bucket.gitlab.id}"
  key    = "sshd/ssh_host_rsa_key"
  source = "./ssh_host_rsa_key"
  etag   = "${md5(file("./ssh_host_rsa_key"))}"
}

resource "aws_s3_bucket_object" "ssh_host_rsa_key_pub" {
  bucket = "${aws_s3_bucket.gitlab.id}"
  key    = "sshd/ssh_host_rsa_key.pub"
  source = "./ssh_host_rsa_key.pub"
  etag   = "${md5(file("./ssh_host_rsa_key.pub"))}"
}

resource "aws_s3_bucket_object" "ssh_host_ecdsa_key" {
  bucket = "${aws_s3_bucket.gitlab.id}"
  key    = "sshd/ssh_host_ecdsa_key"
  source = "./ssh_host_ecdsa_key"
  etag   = "${md5(file("./ssh_host_ecdsa_key"))}"
}

resource "aws_s3_bucket_object" "ssh_host_ecdsa_key_pub" {
  bucket = "${aws_s3_bucket.gitlab.id}"
  key    = "sshd/ssh_host_ecdsa_key.pub"
  source = "./ssh_host_ecdsa_key.pub"
  etag   = "${md5(file("./ssh_host_ecdsa_key.pub"))}"
}

resource "aws_s3_bucket_object" "ssh_host_ed25519_key" {
  bucket = "${aws_s3_bucket.gitlab.id}"
  key    = "sshd/ssh_host_ed25519_key"
  source = "./ssh_host_ed25519_key"
  etag   = "${md5(file("./ssh_host_ed25519_key"))}"
}

resource "aws_s3_bucket_object" "ssh_host_ed25519_key_pub" {
  bucket = "${aws_s3_bucket.gitlab.id}"
  key    = "sshd/ssh_host_ed25519_key.pub"
  source = "./ssh_host_ed25519_key.pub"
  etag   = "${md5(file("./ssh_host_ed25519_key.pub"))}"
}

resource "aws_s3_bucket_object" "gitlab_secrets_json" {
  bucket = "${aws_s3_bucket.gitlab.id}"
  key    = "secrets/gitlab-secrets.json"
  source = "./gitlab-secrets.json"
  etag   = "${md5(file("./gitlab-secrets.json"))}"
}
