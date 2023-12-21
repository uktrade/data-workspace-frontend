data "aws_region" "aws_region" {}
data "aws_caller_identity" "aws_caller_identity" {}

provider "aws" {}
provider "aws" {
  alias = "route53"
}
provider "aws" {
  alias = "mirror"
}

variable aws_availability_zones {
 type = list
}
variable aws_availability_zones_short {
 type = list
}

variable ip_whitelist {
  type = list
}

variable prefix {}
variable prefix_short {}
variable prefix_underscore {}

variable vpc_cidr {}
variable subnets_num_bits {}
variable vpc_notebooks_cidr {}
variable vpc_notebooks_subnets_num_bits {}
variable vpc_datasets_cidr {}

variable aws_route53_zone {}
variable admin_domain {}
variable appstream_domain {}
variable support_domain {}

variable admin_db_instance_class {}
variable admin_db_instance_version {
  default = "10.15"
}

variable admin_authbroker_client_id {}
variable admin_authbroker_client_secret {}
variable admin_authbroker_url {}
variable admin_environment {}
variable admin_deregistration_delay {
  type = number
  default = 300
}

variable uploads_bucket {}
variable appstream_bucket {}
variable notebooks_bucket {}
variable notebooks_bucket_cors_domains {
  type = list(string)
}
variable notebook_container_image {}
variable superset_container_image {}

variable alb_access_logs_bucket {}
variable alb_logs_account {}

variable cloudwatch_destination_arn {}

variable mirrors_bucket_name {}
variable mirrors_data_bucket_name {}

variable sentry_dsn {}
variable sentry_notebooks_dsn {}
variable sentry_environment {}

variable notebook_task_role_prefix {}
variable notebook_task_role_policy_name {}

variable healthcheck_domain {}

variable prometheus_domain {}

variable cloudwatch_subscription_filter {}
variable zendesk_email {}
variable zendesk_subdomain {}
variable zendesk_token {}
variable zendesk_service_field_id {}
variable zendesk_service_field_value {}

variable prometheus_whitelist {
  type = list
}
variable metrics_service_discovery_basic_auth_user {}
variable metrics_service_discovery_basic_auth_password {}

variable google_analytics_site_id {}

variable gitlab_ip_whitelist {
  type = list
}
variable gitlab_domain {}
variable gitlab_bucket {}
variable gitlab_instance_type {}
variable gitlab_memory {}
variable gitlab_cpu {}
variable gitlab_runner_instance_type {}
variable gitlab_runner_tap_instance_type {}
variable gitlab_runner_root_volume_size {}
variable gitlab_db_instance_class {}
variable gitlab_runner_visualisations_deployment_project_token {}
variable gitlab_runner_tap_project_token {}

variable gitlab_sso_id {}
variable gitlab_sso_secret {}
variable gitlab_sso_domain {}

variable superset_admin_users {}
variable superset_db_instance_class {}
variable superset_internal_domain {}

variable superset_dw_user_username {}
variable superset_dw_user_password {}

variable datasets_rds_cluster_backup_retention_period {}
variable datasets_rds_cluster_database_name {}
variable datasets_rds_cluster_master_username {}
variable datasets_rds_cluster_storage_encryption_enabled {}
variable datasets_rds_cluster_cluster_identifier {}
variable datasets_rds_cluster_instance_class {}
variable datasets_rds_cluster_instance_performance_insights_enabled {}
variable datasets_rds_cluster_instance_identifier {}

variable paas_cidr_block {}
variable paas_vpc_id {}
variable quicksight_cidr_block {}
variable datasets_subnet_cidr_blocks {
  type = list
}
variable dataset_subnets_availability_zones {
  type = list
}
variable quicksight_security_group_name {}
variable quicksight_security_group_description {}
variable quicksight_subnet_availability_zone {}
variable quicksight_namespace {}
variable quicksight_user_region {}
variable quicksight_vpc_arn {}
variable quicksight_dashboard_group {}
variable quicksight_sso_url {}
variable quicksight_author_custom_permissions {}
variable quicksight_author_iam_arn {}

variable shared_keypair_public_key {}

variable datasets_finder_instance_type {}
variable datasets_finder_instance_num {
  type = number
  default = 2
}
variable datasets_finder_ebs_size {
  type = number
  default = 100
}
variable flower_username {}
variable flower_password {}


variable mlflow_artifacts_bucket {}
variable mlflow_instances {}
variable mlflow_instances_long {}
variable mlflow_db_instance_class {}

variable jwt_public_key {}
variable jwt_private_key {}

locals {
  admin_container_name    = "jupyterhub-admin"
  admin_container_port    = "8000"
  admin_container_memory  = 2048
  admin_container_cpu     = 1024
  admin_alb_port          = "443"
  admin_api_path          = "/api/v1/databases"

  celery_container_memory = 4096
  celery_container_cpu    = 1024

  notebook_container_name     = "jupyterhub-notebook"
  notebook_container_port     = "8888"
  notebook_container_port_dev = "9000"

  notebook_container_memory = 8192
  notebook_container_cpu    = 1024

  user_provided_container_name   = "user-provided"
  user_provided_container_port   = "8888"
  user_provided_container_memory = 8192
  user_provided_container_cpu    = 1024

  logstash_container_name       = "jupyterhub-logstash"
  logstash_alb_port             = "443"
  logstash_container_memory     = 8192
  logstash_container_cpu        = 2048
  logstash_container_port       = "8889"
  logstash_container_api_port   = "9600"

  dns_rewrite_proxy_container_name       = "jupyterhub-dns-rewrite-proxy"
  dns_rewrite_proxy_container_memory     = 512
  dns_rewrite_proxy_container_cpu        = 256

  sentryproxy_container_name       = "jupyterhub-sentryproxy"
  sentryproxy_container_memory     = 512
  sentryproxy_container_cpu        = 256

  mirrors_sync_container_name    = "jupyterhub-mirrors-sync"
  mirrors_sync_container_memory  = 8192
  mirrors_sync_container_cpu     = 1024

  mirrors_sync_cran_binary_container_name    = "jupyterhub-mirrors-sync-cran-binary"
  mirrors_sync_cran_binary_container_memory  = 2048
  mirrors_sync_cran_binary_container_cpu     = 1024

  healthcheck_container_port = 8888
  healthcheck_container_name = "healthcheck"
  healthcheck_alb_port = "443"
  healthcheck_container_memory     = 512
  healthcheck_container_cpu        = 256

  prometheus_container_port = 9090
  prometheus_container_name = "prometheus"
  prometheus_alb_port = "443"
  prometheus_container_memory     = 512
  prometheus_container_cpu        = 256

  superset_container_memory = 8192
  superset_container_cpu    = 1024

  flower_container_memory = 8192
  flower_container_cpu    = 1024

  arango_container_memory = 8192
  arango_container_cpu    = 4096

  mlflow_container_memory = 8192
  mlflow_container_cpu    = 1024
  mlflow_port = 8004
}
