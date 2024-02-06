terraform {
  backend "s3" {
    region         = "REPLACE_ME"
    encrypt        = true
    bucket         = "REPLACE_ME"
    key            = "REPLACE_ME.tfstate"
    dynamodb_table = "REPLACE_ME"
  }
}

provider "aws" {
  region  = "eu-west-2"
  profile = "jupyterhub"
  version = "= 3.73.0"
}

provider "aws" {
  region  = "eu-west-2"
  profile = "jupyterhub"
  alias   = "route53"
  version = "= 3.73.0"

  assume_role {
    role_arn = "REPLACE_ME"
  }
}

provider "aws" {
  region  = "eu-west-2"
  profile = "jupyterhub"
  alias   = "mirror"
  version = "= 3.73.0"
}

module "jupyterhub" {
  source = "../../data-workspace/infra"

  providers = {
    aws         = aws
    aws.route53 = aws.route53
    aws.mirror  = aws.mirror
  }

  prefix            = "jupyterhub"
  prefix_underscore = "jupyterhub"
  prefix_short      = "jupyterhub"

  notebook_task_role_prefix      = "jhub-"
  notebook_task_role_policy_name = "jupyterhub-task"

  vpc_cidr                       = "172.16.0.0/16"
  subnets_num_bits               = "5"
  vpc_notebooks_cidr             = "172.17.0.0/16"
  vpc_notebooks_subnets_num_bits = "5"
  vpc_datasets_cidr              = "172.18.4.0/22"

  aws_availability_zones       = ["eu-west-2a", "eu-west-2b", "eu-west-2c"]
  aws_availability_zones_short = ["a", "b", "c"]
  ip_whitelist = [
    "0.0.0.0/0",
  ]

  aws_route53_zone = "REPLACE_ME"
  admin_domain     = "REPLACE_ME"
  appstream_domain = "REPLACE_ME"
  support_domain   = "REPLACE_ME"

  superset_internal_domain = "REPLACE_ME"

  admin_db_instance_class        = "db.t3.medium"
  admin_authbroker_client_id     = "REPLACE_ME"
  admin_authbroker_client_secret = "REPLACE_ME"
  admin_authbroker_url           = "REPLACE_ME"
  admin_environment              = file("admin_environment.json")
  admin_deregistration_delay     = 300

  uploads_bucket   = "REPLACE_ME"
  appstream_bucket = "REPLACE_ME"
  notebooks_bucket = "REPLACE_ME"
  notebooks_bucket_cors_domains  = ["REPLACE_ME"]

  notebook_container_image          = "REPLACE_ME"
  superset_container_image          = "REPLACE_ME"

  alb_access_logs_bucket = "REPLACE_ME"
  alb_logs_account       = "REPLACE_ME"

  cloudwatch_destination_arn = "REPLACE_ME"

  mirrors_data_bucket_name     = ""
  mirrors_bucket_name          = "REPLACE_ME"

  sentry_dsn         = "REPLACE_ME"
  sentry_notebooks_dsn = "REPLACE_ME"
  sentry_environment = "Production"

  healthcheck_domain          = "REPLACE_ME"

  prometheus_domain          = "REPLACE_ME"

  cloudwatch_subscription_filter = true

  zendesk_email               = "REPLACE_ME"
  zendesk_subdomain           = "REPLACE_ME"
  zendesk_token               = "REPLACE_ME"
  zendesk_service_field_id    = "REPLACE_ME"
  zendesk_service_field_value = "REPLACE_ME"

  prometheus_whitelist = []
  metrics_service_discovery_basic_auth_user     = "REPLACE_ME"
  metrics_service_discovery_basic_auth_password = "REPLACE_ME"

  google_analytics_site_id             = "REPLACE_ME"

  gitlab_ip_whitelist = []

  gitlab_domain                                         = "REPLACE_ME"
  gitlab_bucket                                         = "REPLACE_ME"
  gitlab_db_instance_class                              = "db.t3.medium"
  gitlab_sso_id                                         = "REPLACE_ME"
  gitlab_sso_secret                                     = "REPLACE_ME"
  gitlab_sso_domain                                     = "REPLACE_ME"
  gitlab_runner_visualisations_deployment_project_token = "REPLACE_ME"
  gitlab_instance_type                                  = "t3a.xlarge"
  gitlab_runner_instance_type                           = "t3a.medium"
  gitlab_runner_root_volume_size                        = "128"
  gitlab_cpu                                            = "4096"
  gitlab_memory                                         = "8192"

  superset_admin_users       = "REPLACE_ME"
  superset_db_instance_class = "db.t3.medium"

  datasets_rds_cluster_backup_retention_period               = 10
  datasets_rds_cluster_database_name                         = "REPLACE_ME"
  datasets_rds_cluster_master_username                       = "REPLACE_ME"
  datasets_rds_cluster_storage_encryption_enabled            = "true"
  datasets_rds_cluster_cluster_identifier                    = "REPLACE_ME"
  datasets_rds_cluster_instance_class                        = "db.r5.2xlarge"
  datasets_rds_cluster_instance_performance_insights_enabled = "true"
  datasets_rds_cluster_instance_identifier                   = "REPLACE_ME"

  paas_cidr_block       = "10.0.0.0/16"
  paas_vpc_id           = "REPLACE_ME"
  quicksight_cidr_block = "172.18.5.128/25"
  quicksight_vpc_arn    = "REPLACE_ME"
  datasets_subnet_cidr_blocks = [
    "172.18.4.0/25",
    "172.18.4.128/25",
    "172.18.5.0/25",
  ]
  dataset_subnets_availability_zones = [
    "eu-west-2a",
    "eu-west-2b",
    "eu-west-2b",
  ] # The second and third subnet on the live environment are both in the same az

  quicksight_security_group_name        = "jupyterhub-quicksight"
  quicksight_security_group_description = "Allow quicksight to connect to data workspace datasets DB"
  quicksight_subnet_availability_zone   = "eu-west-2b"
  quicksight_namespace = "default"
  quicksight_dashboard_group = "DataWorkspace"
  quicksight_user_region = "eu-west-2"
  quicksight_sso_url = "REPLACE_ME"
  quicksight_author_custom_permissions = "author-custom-permissions"
  quicksight_author_iam_arn = "REPLACE_ME"

  shared_keypair_public_key = "REPLACE_ME"

  superset_dw_user_username = "REPLACE_ME"
  superset_dw_user_password = "REPLACE_ME"

  flower_username = "REPLACE_ME"
  flower_password = "REPLACE_ME"

  jwt_private_key = "-----BEGIN PRIVATE KEY-----\\REPLACE_ME\\n-----END PRIVATE KEY-----\\n"
  jwt_public_key = "-----BEGIN PUBLIC KEY-----\\REPLACE_ME\\n-----END PUBLIC KEY-----\\n"

  mlflow_artifacts_bucket = "REPLACE_ME"
  mlflow_instances = ["REPLACE_ME"]
  mlflow_instances_long = ["REPLACE_ME"]
  mlflow_db_instance_class = "db.t3.medium"
}
