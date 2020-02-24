data "aws_region" "aws_region" {}
data "aws_caller_identity" "aws_caller_identity" {}

variable "aws_availability_zones" {
 type = "list"
}
variable "aws_availability_zones_short" {
 type = "list"
}

variable "ip_whitelist" {
  type = "list"
}

variable "prefix" {}
variable "prefix_short" {}
variable "prefix_underscore" {}

variable "vpc_cidr" {}
variable "subnets_num_bits" {}
variable "vpc_notebooks_cidr" {}
variable "vpc_notebooks_subnets_num_bits" {}

variable "aws_route53_zone" {}
variable "admin_domain" {}
variable "appstream_domain" {}
variable "support_domain" {}

variable "registry_container_image" {}
variable "registry_proxy_remoteurl" {}
variable "registry_proxy_username" {}
variable "registry_proxy_password" {}
variable "registry_internal_domain" {}

variable "admin_container_image" {}
variable "admin_db_instance_class" {}

variable "admin_authbroker_client_id" {}
variable "admin_authbroker_client_secret" {}
variable "admin_authbroker_url" {}
variable "admin_environment" {}

variable "uploads_bucket" {}
variable "appstream_bucket" {}
variable "notebooks_bucket" {}
variable "notebook_container_image" {}
variable "jupyterlab_python_container_image" {}
variable "jupyterlab_r_container_image" {}
variable "rstudio_container_image" {}
variable "pgadmin_container_image" {}
variable "metabase_container_image" {}
variable "pgweb_container_image" {}
variable "remotedesktop_container_image" {}

variable "alb_access_logs_bucket" {}
variable "alb_logs_account" {}

variable "dnsmasq_container_image" {}
variable "sentryproxy_container_image" {}

variable "cloudwatch_destination_arn" {}

variable "mirrors_bucket_name" {}
variable "mirrors_sync_container_image" {}
variable "mirrors_data_bucket_name" {}

variable "sentry_dsn" {}

variable "notebook_task_role_prefix" {}
variable "notebook_task_role_policy_name" {}

variable healthcheck_container_image {}
variable healthcheck_domain {}

variable prometheus_container_image {}
variable prometheus_domain {}

variable cloudwatch_subscription_filter {}
variable zendesk_email {}
variable zendesk_subdomain {}
variable zendesk_token {}
variable zendesk_service_field_id {}
variable zendesk_service_field_value {}

variable prometheus_whitelist {
  type = "list"
}
variable metrics_service_discovery_basic_auth_user {}
variable metrics_service_discovery_basic_auth_password {}
variable metrics_container_image {}

variable s3sync_container_image {}

variable google_analytics_site_id {}
variable google_data_studio_connector_pattern {}

variable gitlab_domain {}
variable gitlab_bucket {}
variable gitlab_container_image {}
variable gitlab_db_instance_class {}

variable gitlab_sso_id {}
variable gitlab_sso_secret {}
variable gitlab_sso_domain {}

locals {
  registry_container_name    = "jupyterhub-registry"
  registry_container_port    = "5000"
  registry_container_memory  = 4096
  registry_container_cpu     = 2048
  registry_alb_port          = "443"

  admin_container_name    = "jupyterhub-admin"
  admin_container_port    = "8000"
  admin_container_memory  = 2048
  admin_container_cpu     = 1024
  admin_alb_port          = "443"
  admin_api_path          = "/api/v1/databases"

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

  dnsmasq_container_name       = "jupyterhub-dnsmasq"
  dnsmasq_container_memory     = 512
  dnsmasq_container_cpu        = 256

  sentryproxy_container_name       = "jupyterhub-sentryproxy"
  sentryproxy_container_memory     = 512
  sentryproxy_container_cpu        = 256

  mirrors_sync_container_name    = "jupyterhub-mirrors-sync"
  mirrors_sync_container_memory  = 8192
  mirrors_sync_container_cpu     = 1024

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

  gitlab_container_memory = 8192
  gitlab_container_cpu    = 4096
}
