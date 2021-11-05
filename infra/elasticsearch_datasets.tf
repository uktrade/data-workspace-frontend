locals {
  es_domain_name = "${var.prefix_short}-finder"
}

resource "aws_iam_service_linked_role" "datasets_finder" {
  # This is a shared resource between all envs ... couldn't find a way to have
  # one per env as it automatically assigns the same name (and custom suffixes aren't
  # allowed for ES service linked roles).
  aws_service_name = "es.amazonaws.com"
}

resource "aws_elasticsearch_domain" "datasets_finder" {
  domain_name           = "${local.es_domain_name}"
  elasticsearch_version = "7.9"

  cluster_config {
    dedicated_master_enabled = false
    instance_type = var.datasets_finder_instance_type
    instance_count = var.datasets_finder_instance_num
  }

  domain_endpoint_options {
    enforce_https = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  encrypt_at_rest {
    enabled = true
  }

  ebs_options {
    ebs_enabled = true
    volume_type = "gp2"
    volume_size = var.datasets_finder_ebs_size
  }

  vpc_options {
    subnet_ids = [aws_subnet.datasets[0].id]
    security_group_ids = [aws_security_group.datasets.id]
  }

  snapshot_options {
    automated_snapshot_start_hour = 23
  }

  log_publishing_options {
    enabled = true
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.dataset_finder_index_slow_logs.arn
    log_type = "INDEX_SLOW_LOGS"
  }

  log_publishing_options {
    enabled = true
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.dataset_finder_search_slow_logs.arn
    log_type = "SEARCH_SLOW_LOGS"
  }

  log_publishing_options {
    enabled = true
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.dataset_finder_application_logs.arn
    log_type = "ES_APPLICATION_LOGS"
  }

  access_policies = <<CONFIG
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "${aws_iam_role.admin_task.arn}"
      },
      "Action": ["es:ESHttp*"],
      "Resource": "arn:aws:es:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:domain/${local.es_domain_name}/*"
    },
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "${aws_iam_user.datasets_finder_data_flow.arn}"
      },
      "Action": "es:*",
      "Resource": "arn:aws:es:${data.aws_region.aws_region.name}:${data.aws_caller_identity.aws_caller_identity.account_id}:domain/${local.es_domain_name}/*"
    }
  ]
}
CONFIG

  depends_on = [aws_iam_service_linked_role.datasets_finder]
}

resource "aws_cloudwatch_log_group" "dataset_finder_index_slow_logs" {
  name = "${var.prefix}-datasets-finder-index-slow-logs"
  retention_in_days = 365
}

resource "aws_cloudwatch_log_group" "dataset_finder_search_slow_logs" {
  name = "${var.prefix}-datasets-finder-search-slow-logs"
  retention_in_days = 365
}

resource "aws_cloudwatch_log_group" "dataset_finder_application_logs" {
  name = "${var.prefix}-datasets-finder-application-logs"
  retention_in_days = 365
}


resource "aws_cloudwatch_log_resource_policy" "dataset_finder" {
  policy_document = data.aws_iam_policy_document.dataset_finder.json
  policy_name     = "${var.prefix}-dataset-finder"
}

data "aws_iam_policy_document" "dataset_finder" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:PutLogEventsBatch",
    ]

    resources = [
      "${aws_cloudwatch_log_group.dataset_finder_index_slow_logs.arn}:*",
      "${aws_cloudwatch_log_group.dataset_finder_search_slow_logs.arn}:*",
      "${aws_cloudwatch_log_group.dataset_finder_application_logs.arn}:*",
    ]

    principals {
      identifiers = ["es.amazonaws.com"]
      type = "Service"
    }
  }
}

resource "aws_iam_user" "datasets_finder_data_flow" {
  name = "${var.prefix}-datasets-finder"
}

resource "aws_iam_access_key" "datasets_finder_data_flow" {
  user = aws_iam_user.datasets_finder_data_flow.name
}

output "datasets_finder_data_flow_access_key_id" {
  value = aws_iam_access_key.datasets_finder_data_flow.id
}

output "datasets_finder_data_flow_secret_access_key" {
  value = aws_iam_access_key.datasets_finder_data_flow.secret
}
