resource "aws_security_group" "dns_rewrite_proxy" {
  name        = "${var.prefix}-dns-rewrite-proxy"
  description = "${var.prefix}-dns-rewrite-proxy"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-dns-rewrite-proxy"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "dns_rewrite_proxy_ingress_healthcheck" {
  description       = "ingress-private-with-egress-healthcheck"
  type              = "ingress"
  from_port         = "8888"
  to_port           = "8888"
  protocol          = "tcp"
  cidr_blocks       = ["${aws_subnet.private_with_egress.*.cidr_block[0]}"]
  security_group_id = "${aws_security_group.dns_rewrite_proxy.id}"
}

resource "aws_security_group_rule" "dns_rewrite_proxy_ingress_udp" {
  count = "${length(aws_subnet.private_without_egress)}"

  description       = "ingress-private-without-egress-udp-${var.aws_availability_zones_short[count.index]}"
  type              = "ingress"
  from_port         = "53"
  to_port           = "53"
  protocol          = "udp"
  cidr_blocks       = ["${aws_subnet.private_without_egress[count.index].cidr_block}"]
  security_group_id = "${aws_security_group.dns_rewrite_proxy.id}"
}


resource "aws_security_group_rule" "dns_rewrite_proxy_egress_https" {
  description = "egress-dns-tcp"

  security_group_id = "${aws_security_group.dns_rewrite_proxy.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}


resource "aws_security_group" "sentryproxy_service" {
  name        = "${var.prefix}-sentryproxy"
  description = "${var.prefix}-sentryproxy"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-sentryproxy"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "sentryproxy_egress_https" {
  description = "egress-https"

  security_group_id = "${aws_security_group.sentryproxy_service.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "sentryproxy_ingress_http_notebooks" {
  description = "ingress-http"

  security_group_id        = "${aws_security_group.sentryproxy_service.id}"
  source_security_group_id = "${aws_security_group.notebooks.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group" "admin_alb" {
  name        = "${var.prefix}-admin-alb"
  description = "${var.prefix}-admin-alb"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-admin-alb"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "admin_alb_ingress_https_from_whitelist" {
  description = "ingress-https-from-whitelist"

  security_group_id = "${aws_security_group.admin_alb.id}"
  cidr_blocks       = concat("${var.ip_whitelist}", ["${aws_eip.nat_gateway.public_ip}/32"])

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "admin_alb_ingress_http_from_whitelist" {
  description = "ingress-http-from-whitelist"

  security_group_id = "${aws_security_group.admin_alb.id}"
  cidr_blocks       = "${var.ip_whitelist}"

  type      = "ingress"
  from_port = "80"
  to_port   = "80"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "admin_alb_ingress_icmp_host_unreachable_for_mtu_discovery_from_whitelist" {
  description = "ingress-icmp-host-unreachable-for-mtu-discovery-from-whitelist"

  security_group_id = "${aws_security_group.admin_alb.id}"
  cidr_blocks       = "${var.ip_whitelist}"

  type      = "ingress"
  from_port = 3
  to_port   = 0
  protocol  = "icmp"
}

resource "aws_security_group_rule" "admin_alb_egress_https_to_admin_service" {
  description = "egress-https-to-admin-service"

  security_group_id        = "${aws_security_group.admin_alb.id}"
  source_security_group_id = "${aws_security_group.admin_service.id}"

  type      = "egress"
  from_port = "${local.admin_container_port}"
  to_port   = "${local.admin_container_port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "admin_alb_egress_https_to_cloudwatch" {
  description = "egress-https-to-cloudwatch"

  security_group_id        = "${aws_security_group.admin_alb.id}"
  source_security_group_id = "${aws_security_group.cloudwatch.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group" "admin_redis" {
  name        = "${var.prefix}-admin-redis"
  description = "${var.prefix}-admin-redis"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-admin-redis"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "admin_redis_egress_https_to_cloudwatch" {
  description = "egress-https-to-cloudwatch"

  security_group_id        = "${aws_security_group.admin_redis.id}"
  source_security_group_id = "${aws_security_group.cloudwatch.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "admin_redis_ingress_from_admin_service" {
  description = "ingress-redis-from-admin-service"

  security_group_id        = "${aws_security_group.admin_redis.id}"
  source_security_group_id = "${aws_security_group.admin_service.id}"

  type      = "ingress"
  from_port = "6379"
  to_port   = "6379"
  protocol  = "tcp"
}

resource "aws_security_group" "admin_service" {
  name        = "${var.prefix}-admin-service"
  description = "${var.prefix}-admin-service"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-admin-service"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "admin_service_egress_http_to_superset_lb" {
  description = "egress-http-to-gitlab-service"

  security_group_id        = "${aws_security_group.admin_service.id}"
  source_security_group_id = "${aws_security_group.superset_lb.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "admin_service_egress_http_to_flower_lb" {
  description = "egress-http-to-flower-lb"

  security_group_id        = "${aws_security_group.admin_service.id}"
  source_security_group_id = "${aws_security_group.flower_lb.id}"

  type      = "egress"
  from_port = "80"
  to_port   = "80"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "admin_service_egress_http_to_mlflow" {
  description = "egress-http-to-mlflow-lb"

  security_group_id = "${aws_security_group.admin_service.id}"
  cidr_blocks       = ["${cidrhost("${aws_subnet.private_without_egress.*.cidr_block[0]}", 7)}/32"]

  type      = "egress"
  from_port = "${local.mlflow_port}"
  to_port   = "${local.mlflow_port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "admin_service_egress_http_to_gitlab_service" {
  description = "egress-http-to-gitlab-service"

  security_group_id        = "${aws_security_group.admin_service.id}"
  source_security_group_id = "${aws_security_group.gitlab_service.id}"

  type      = "egress"
  from_port = "80"
  to_port   = "80"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "gitlab_service_egress_https_to_ecr_api" {
  description = "egress-https-to-ecr-api"

  security_group_id        = "${aws_security_group.gitlab_service.id}"
  source_security_group_id = "${aws_security_group.ecr_api.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "admin_service_egress_https_to_cloudwatch" {
  description = "egress-https-to-cloudwatch"

  security_group_id        = "${aws_security_group.admin_service.id}"
  source_security_group_id = "${aws_security_group.cloudwatch.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "admin_service_egress_to_admin_service" {
  description = "egress-redis-to-admin-redis"

  security_group_id        = "${aws_security_group.admin_service.id}"
  source_security_group_id = "${aws_security_group.admin_redis.id}"

  type      = "egress"
  from_port = "6379"
  to_port   = "6379"
  protocol  = "tcp"
}


resource "aws_security_group_rule" "admin_service_ingress_https_from_admin_alb" {
  description = "ingress-https-from-admin-alb"

  security_group_id        = "${aws_security_group.admin_service.id}"
  source_security_group_id = "${aws_security_group.admin_alb.id}"

  type      = "ingress"
  from_port = "${local.admin_container_port}"
  to_port   = "${local.admin_container_port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "admin_service_egress_https_to_everywhere" {
  description = "egress-https-to-everywhere"

  security_group_id = "${aws_security_group.admin_service.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "admin_service_egress_http_to_notebooks" {
  description = "egress-https-to-everywhere"

  security_group_id        = "${aws_security_group.admin_service.id}"
  source_security_group_id = "${aws_security_group.notebooks.id}"

  type      = "egress"
  from_port = "${local.notebook_container_port}"
  to_port   = "${local.notebook_container_port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "admin_service_egress_http_dev_to_notebooks" {
  description = "egress-http-dev-to-notebooks"

  security_group_id        = "${aws_security_group.admin_service.id}"
  source_security_group_id = "${aws_security_group.notebooks.id}"

  type      = "egress"
  from_port = "${local.notebook_container_port_dev}"
  to_port   = "${local.notebook_container_port_dev}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "admin_service_egress_postgres_to_admin_db" {
  description = "egress-postgres-to-admin-db"

  security_group_id        = "${aws_security_group.admin_service.id}"
  source_security_group_id = "${aws_security_group.admin_db.id}"

  type      = "egress"
  from_port = "${aws_db_instance.admin.port}"
  to_port   = "${aws_db_instance.admin.port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "admin_service_egress_postgres_to_datasets_db" {
  description = "egress-postgres-to-datasets-db"

  security_group_id        = "${aws_security_group.admin_service.id}"
  source_security_group_id = "${aws_security_group.datasets.id}"

  type      = "egress"
  from_port = "${aws_rds_cluster_instance.datasets.port}"
  to_port   = "${aws_rds_cluster_instance.datasets.port}"
  protocol  = "tcp"
}

resource "aws_security_group" "admin_db" {
  name        = "${var.prefix}-admin-db"
  description = "${var.prefix}-admin-db"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-admin-db"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "admin_db_ingress_postgres_from_admin_service" {
  description = "ingress-postgres-from-admin-service"

  security_group_id        = "${aws_security_group.admin_db.id}"
  source_security_group_id = "${aws_security_group.admin_service.id}"

  type      = "ingress"
  from_port = "${aws_db_instance.admin.port}"
  to_port   = "${aws_db_instance.admin.port}"
  protocol  = "tcp"
}

resource "aws_security_group" "notebooks" {
  name        = "${var.prefix}-notebooks"
  description = "${var.prefix}-notebooks"
  vpc_id      = "${aws_vpc.notebooks.id}"

  tags = {
    Name = "${var.prefix}-notebooks"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "notebooks_egress_nfs_efs_mount_target_notebooks" {
  description = "egress-nfs-efs-mount-target"

  security_group_id        = "${aws_security_group.notebooks.id}"
  source_security_group_id = "${aws_security_group.efs_mount_target_notebooks.id}"

  type      = "egress"
  from_port = "2049"
  to_port   = "2049"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "notebooks_ingress_https_from_admin" {
  description = "ingress-https-from-jupytehub"

  security_group_id        = "${aws_security_group.notebooks.id}"
  source_security_group_id = "${aws_security_group.admin_service.id}"

  type      = "ingress"
  from_port = "${local.notebook_container_port}"
  to_port   = "${local.notebook_container_port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "notebooks_ingress_http_dev_from_admin" {
  description = "ingress-http-dev-from-jupytehub"

  security_group_id        = "${aws_security_group.notebooks.id}"
  source_security_group_id = "${aws_security_group.admin_service.id}"

  type      = "ingress"
  from_port = "${local.notebook_container_port_dev}"
  to_port   = "${local.notebook_container_port_dev}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "notebooks_ingress_http_from_prometheus" {
  description = "ingress-https-from-prometheus-service"

  security_group_id        = "${aws_security_group.notebooks.id}"
  source_security_group_id = "${aws_security_group.prometheus_service.id}"

  type      = "ingress"
  from_port = "${local.notebook_container_port + 1}"
  to_port   = "${local.notebook_container_port + 1}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "notebooks_egress_https_to_everywhere" {
  description = "egress-https-to-everywhere"

  security_group_id = "${aws_security_group.notebooks.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "notebooks_egress_http_to_everywhere" {
  description = "egress-http-to-everywhere"

  security_group_id = "${aws_security_group.notebooks.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "80"
  to_port   = "80"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "notebooks_egress_ssh_to_gitlab_service" {
  description = "ingress-ssh-from-nlb"

  security_group_id        = "${aws_security_group.notebooks.id}"
  source_security_group_id = "${aws_security_group.gitlab_service.id}"

  type      = "egress"
  from_port = "22"
  to_port   = "22"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "notebooks_egress_dns_udp" {
  description = "egress-dns-udp"

  security_group_id = "${aws_security_group.notebooks.id}"
  cidr_blocks       = ["${aws_subnet.private_with_egress.*.cidr_block[0]}"]

  type      = "egress"
  from_port = "53"
  to_port   = "53"
  protocol  = "udp"
}

resource "aws_security_group_rule" "notebooks_egress_postgres_to_datasets_db" {
  description = "egress-postgres-to-datasets-db"

  security_group_id        = "${aws_security_group.notebooks.id}"
  source_security_group_id = "${aws_security_group.datasets.id}"

  type      = "egress"
  from_port = "${aws_rds_cluster_instance.datasets.port}"
  to_port   = "${aws_rds_cluster_instance.datasets.port}"
  protocol  = "tcp"
}


resource "aws_security_group" "cloudwatch" {
  name        = "${var.prefix}-cloudwatch"
  description = "${var.prefix}-cloudwatch"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-cloudwatch"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "ecr_dkr" {
  name        = "${var.prefix}-ecr-dkr"
  description = "${var.prefix}-ecr-dkr"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-ecr-dkr"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "ecr_api" {
  name        = "${var.prefix}-ecr-api"
  description = "${var.prefix}-ecr-api"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-ecr-api"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "ecr_api_ingress_https_from_dns_rewrite_proxy" {
  description = "ingress-https-from-dns-rewrite-proxy"

  security_group_id        = "${aws_security_group.ecr_api.id}"
  source_security_group_id = "${aws_security_group.dns_rewrite_proxy.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "ecr_api_ingress_https_from_prometheus" {
  description = "ingress-https-from-prometheus-service"

  security_group_id        = "${aws_security_group.ecr_api.id}"
  source_security_group_id = "${aws_security_group.prometheus_service.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "ecr_api_ingress_https_from_sentryproxy" {
  description = "ingress-https-from-sentryproxy-service"

  security_group_id        = "${aws_security_group.ecr_api.id}"
  source_security_group_id = "${aws_security_group.sentryproxy_service.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "ecr_api_ingress_https_from_admin-service" {
  description = "ingress-https-from-admin-service"

  security_group_id        = "${aws_security_group.ecr_api.id}"
  source_security_group_id = "${aws_security_group.admin_service.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "ecr_api_ingress_https_from_gitlab_ec2" {
  description = "ingress-https-from-gitlab-ec2"

  security_group_id        = "${aws_security_group.ecr_api.id}"
  source_security_group_id = "${aws_security_group.gitlab-ec2.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "ecr_api_ingress_https_from_gitlab_runner" {
  description = "ingress-https-from-gitlab-runner"

  security_group_id        = "${aws_security_group.ecr_api.id}"
  source_security_group_id = "${aws_security_group.gitlab_runner.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "ecr_api_ingress_https_from_notebooks" {
  description = "ingress-https-from-notebooks"

  security_group_id        = "${aws_security_group.ecr_api.id}"
  source_security_group_id = "${aws_security_group.notebooks.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "ecr_api_ingress_https_from_mirrors_sync" {
  description = "ingress-https-from-mirrors-sync"

  security_group_id        = "${aws_security_group.ecr_api.id}"
  source_security_group_id = "${aws_security_group.mirrors_sync.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "ecr_api_ingress_https_from_superset" {
  description = "ingress-https-from-superset"

  security_group_id        = "${aws_security_group.ecr_api.id}"
  source_security_group_id = "${aws_security_group.superset_service.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "ecr_api_ingress_https_from_healthcheck" {
  description = "ingress-https-from-healthcheck-service"

  security_group_id        = "${aws_security_group.ecr_api.id}"
  source_security_group_id = "${aws_security_group.healthcheck_service.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "ecr_api_ingress_https_from_arango" {
  description = "ingress-https-from-arango-service"

  security_group_id        = "${aws_security_group.ecr_api.id}"
  source_security_group_id = "${aws_security_group.arango_service.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "cloudwatch_ingress_https_from_all" {
  description = "ingress-https-from-everywhere"

  security_group_id = "${aws_security_group.cloudwatch.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "ecr_dkr_ingress_https_from_all" {
  description = "ingress-https-from-everywhere"

  security_group_id = "${aws_security_group.ecr_dkr.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group" "mirrors_sync" {
  name        = "${var.prefix}-mirrors-sync"
  description = "${var.prefix}-mirrors-sync"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-mirrors-sync"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "mirrors_sync_egress_https_to_everywhere" {
  description = "egress-https-to-everywhere"

  security_group_id = "${aws_security_group.mirrors_sync.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group" "healthcheck_alb" {
  name        = "${var.prefix}-healthcheck-alb"
  description = "${var.prefix}-healthcheck-alb"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-healthcheck-alb"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "healthcheck_alb_egress_https_to_cloudwatch" {
  description = "egress-https-to-cloudwatch"

  security_group_id        = "${aws_security_group.healthcheck_alb.id}"
  source_security_group_id = "${aws_security_group.cloudwatch.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "healthcheck_alb_ingress_https_from_all" {
  description = "ingress-https-from-all"

  security_group_id = "${aws_security_group.healthcheck_alb.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "healthcheck_alb_egress_https_to_healthcheck_service" {
  description = "egress-https-to-healthcheck-service"

  security_group_id        = "${aws_security_group.healthcheck_alb.id}"
  source_security_group_id = "${aws_security_group.healthcheck_service.id}"

  type      = "egress"
  from_port = "${local.healthcheck_container_port}"
  to_port   = "${local.healthcheck_container_port}"
  protocol  = "tcp"
}

resource "aws_security_group" "healthcheck_service" {
  name        = "${var.prefix}-healthcheck_service"
  description = "${var.prefix}-healthcheck_service"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-healthcheck_service"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "healthcheck_service_egress_https_to_cloudwatch" {
  description = "egress-https-to-cloudwatch"

  security_group_id        = "${aws_security_group.healthcheck_service.id}"
  source_security_group_id = "${aws_security_group.cloudwatch.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "healthcheck_service_ingress_https_from_healthcheck_alb" {
  description = "ingress-https-from-healthcheck-alb"

  security_group_id        = "${aws_security_group.healthcheck_service.id}"
  source_security_group_id = "${aws_security_group.healthcheck_alb.id}"

  type      = "ingress"
  from_port = "${local.healthcheck_container_port}"
  to_port   = "${local.healthcheck_container_port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "healthcheck_service_egress_https_to_everywhere" {
  description = "ingress-https-from-healthcheck-alb"

  security_group_id = "${aws_security_group.healthcheck_service.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group" "prometheus_alb" {
  name        = "${var.prefix}-prometheus-alb"
  description = "${var.prefix}-prometheus-alb"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-prometheus-alb"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "prometheus_alb_egress_https_to_cloudwatch" {
  description = "egress-https-to-cloudwatch"

  security_group_id        = "${aws_security_group.prometheus_alb.id}"
  source_security_group_id = "${aws_security_group.cloudwatch.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "prometheus_alb_ingress_https_from_whitelist" {
  description = "ingress-https-from-all"

  security_group_id = "${aws_security_group.prometheus_alb.id}"
  cidr_blocks       = concat("${var.prometheus_whitelist}", ["${aws_eip.nat_gateway.public_ip}/32"])

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "prometheus_alb_egress_https_to_prometheus_service" {
  description = "egress-https-to-prometheus-service"

  security_group_id        = "${aws_security_group.prometheus_alb.id}"
  source_security_group_id = "${aws_security_group.prometheus_service.id}"

  type      = "egress"
  from_port = "${local.prometheus_container_port}"
  to_port   = "${local.prometheus_container_port}"
  protocol  = "tcp"
}

resource "aws_security_group" "prometheus_service" {
  name        = "${var.prefix}-prometheus_service"
  description = "${var.prefix}-prometheus_service"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-prometheus_service"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "prometheus_service_ingress_https_from_prometheus_alb" {
  description = "ingress-https-from-prometheus-alb"

  security_group_id        = "${aws_security_group.prometheus_service.id}"
  source_security_group_id = "${aws_security_group.prometheus_alb.id}"

  type      = "ingress"
  from_port = "${local.prometheus_container_port}"
  to_port   = "${local.prometheus_container_port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "prometheus_service_egress_https_to_everywhere" {
  description = "egress-https-from-prometheus-service"

  security_group_id = "${aws_security_group.prometheus_service.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "prometheus_service_egress_http_to_notebooks" {
  description = "egress-https-from-prometheus-service"

  security_group_id        = "${aws_security_group.prometheus_service.id}"
  source_security_group_id = "${aws_security_group.notebooks.id}"

  type      = "egress"
  from_port = "${local.notebook_container_port + 1}"
  to_port   = "${local.notebook_container_port + 1}"
  protocol  = "tcp"
}

resource "aws_security_group" "gitlab_service" {
  name        = "${var.prefix}-gitlab-service"
  description = "${var.prefix}-gitlab-service"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-gitlab-service"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "gitlab_service_ingress_http_from_nlb" {
  description = "ingress-https-from-nlb"

  security_group_id = "${aws_security_group.gitlab_service.id}"
  cidr_blocks       = ["${aws_eip.gitlab.private_ip}/32"]

  type      = "ingress"
  from_port = "80"
  to_port   = "80"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "gitlab_service_ingress_http_from_whitelist" {
  description = "ingress-http-from-whitelist"

  security_group_id = "${aws_security_group.gitlab_service.id}"
  cidr_blocks       = "${var.gitlab_ip_whitelist}"

  type      = "ingress"
  from_port = "80"
  to_port   = "80"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "gitlab_service_ingress_http_from_admin_service" {
  description = "ingress-http-from-admin-service"

  security_group_id        = "${aws_security_group.gitlab_service.id}"
  source_security_group_id = "${aws_security_group.admin_service.id}"

  type      = "ingress"
  from_port = "80"
  to_port   = "80"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "gitlab_service_ingress_https_from_gitlab_runner" {
  description = "ingress-https-from-gitlab-runner"

  security_group_id        = "${aws_security_group.gitlab_service.id}"
  source_security_group_id = "${aws_security_group.gitlab_runner.id}"

  type      = "ingress"
  from_port = "80"
  to_port   = "80"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "gitlab_service_ingress_ssh_from_nlb" {
  description = "ingress-ssh-from-nlb"

  security_group_id = "${aws_security_group.gitlab_service.id}"
  cidr_blocks       = ["${aws_eip.gitlab.private_ip}/32"]

  type      = "ingress"
  from_port = "22"
  to_port   = "22"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "gitlab_service_ingress_ssh_from_whitelist" {
  description = "ingress-http-from-whitelist"

  security_group_id = "${aws_security_group.gitlab_service.id}"
  cidr_blocks       = "${var.gitlab_ip_whitelist}"

  type      = "ingress"
  from_port = "22"
  to_port   = "22"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "gitlab_service_ingress_ssh_from_notebooks" {
  description = "ingress-ssh-from-nlb"

  security_group_id        = "${aws_security_group.gitlab_service.id}"
  source_security_group_id = "${aws_security_group.notebooks.id}"

  type      = "ingress"
  from_port = "22"
  to_port   = "22"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "gitlab_service_egress_https_to_everwhere" {
  description = "egress-https-to-everywhere"

  security_group_id = "${aws_security_group.gitlab_service.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "gitlab_service_egress_postgres_to_gitlab_db" {
  description = "egress-postgres-to-gitlab-db"

  security_group_id        = "${aws_security_group.gitlab_service.id}"
  source_security_group_id = "${aws_security_group.gitlab_db.id}"

  type      = "egress"
  from_port = "${aws_rds_cluster.gitlab.port}"
  to_port   = "${aws_rds_cluster.gitlab.port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "gitlab_service_egress_redis" {
  description = "egress-redis"

  security_group_id        = "${aws_security_group.gitlab_service.id}"
  source_security_group_id = "${aws_security_group.gitlab_redis.id}"

  type      = "egress"
  from_port = "6379"
  to_port   = "6379"
  protocol  = "tcp"
}

resource "aws_security_group" "gitlab_redis" {
  name        = "${var.prefix}-gitlab-redis"
  description = "${var.prefix}-gitlab-redis"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-admin-gitlab"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "admin_gitlab_ingress_from_gitlab_service" {
  description = "ingress-gitlab-from-admin-service"

  security_group_id        = "${aws_security_group.gitlab_redis.id}"
  source_security_group_id = "${aws_security_group.gitlab_service.id}"

  type      = "ingress"
  from_port = "6379"
  to_port   = "6379"
  protocol  = "tcp"
}

resource "aws_security_group" "gitlab_db" {
  name        = "${var.prefix}-gitlab-db"
  description = "${var.prefix}-gitlab-db"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-gitlab-db"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "gitlab_db_ingress_from_gitlab_service" {
  description = "egress-postgres-to-gitlab-db"

  security_group_id        = "${aws_security_group.gitlab_db.id}"
  source_security_group_id = "${aws_security_group.gitlab_service.id}"

  type      = "ingress"
  from_port = "${aws_rds_cluster.gitlab.port}"
  to_port   = "${aws_rds_cluster.gitlab.port}"
  protocol  = "tcp"
}

resource "aws_security_group" "gitlab-ec2" {
  name        = "${var.prefix}-gitlab-ec2"
  description = "${var.prefix}-gitlab-ec2"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-gitlab-ec2"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "gitlab-ec2-egress-all" {
  description = "egress-everything-to-everywhere"

  security_group_id = "${aws_security_group.gitlab-ec2.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "0"
  to_port   = "65535"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "gitlab-ec2-ingress-ssh" {
  description = "egress-ssh"

  security_group_id = "${aws_security_group.gitlab-ec2.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "ingress"
  from_port = "22"
  to_port   = "22"
  protocol  = "tcp"
}

resource "aws_security_group" "gitlab_runner" {
  name        = "${var.prefix}-gitlab-runner"
  description = "${var.prefix}-gitlab-runner"
  vpc_id      = "${aws_vpc.notebooks.id}"

  tags = {
    Name = "${var.prefix}-gitlab-runner"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "gitlab_runner_egress_https_to_ecr_api" {
  description = "egress-https-to-ecr-api"

  security_group_id        = "${aws_security_group.gitlab_runner.id}"
  source_security_group_id = "${aws_security_group.ecr_api.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "gitlab_runner_egress_dns_udp_dns_rewrite_proxy" {
  description = "egress-dns-udp-dns-rewrite-proxy"

  security_group_id = "${aws_security_group.gitlab_runner.id}"
  cidr_blocks       = ["${aws_subnet.private_with_egress.*.cidr_block[0]}"]

  type      = "egress"
  from_port = "53"
  to_port   = "53"
  protocol  = "udp"
}

# Connections to AWS package repos and GitLab
resource "aws_security_group_rule" "gitlab_runner_egress_http" {
  description = "egress-https"

  security_group_id = "${aws_security_group.gitlab_runner.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "80"
  to_port   = "80"
  protocol  = "tcp"
}

# Connections to ECR and CloudWatch
resource "aws_security_group_rule" "gitlab_runner_egress_https" {
  description = "egress-https"

  security_group_id = "${aws_security_group.gitlab_runner.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group" "superset_db" {
  name        = "${var.prefix}-superset-db"
  description = "${var.prefix}-superset-db"
  vpc_id      = "${aws_vpc.notebooks.id}"

  tags = {
    Name = "${var.prefix}-superset-db"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Connections to ECR and CloudWatch. ECR needs S3, and its VPC endpoint type
# does not have an IP range or security group to limit access to
resource "aws_security_group_rule" "superset_egress_https_all" {
  description = "egress-https-to-all"

  security_group_id = "${aws_security_group.superset_service.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "superset_db_ingress_postgres_superset_service" {
  description = "ingress-postgress-superset-service"

  security_group_id        = "${aws_security_group.superset_db.id}"
  source_security_group_id = "${aws_security_group.superset_service.id}"

  type      = "ingress"
  from_port = "5432"
  to_port   = "5432"
  protocol  = "tcp"
}

resource "aws_security_group" "superset_service" {
  name        = "${var.prefix}-superset-service"
  description = "${var.prefix}-superset-service"
  vpc_id      = "${aws_vpc.notebooks.id}"

  tags = {
    Name = "${var.prefix}-superset-service"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "superset_service_ingress_http_superset_lb" {
  description = "ingress-superset-lb"

  security_group_id        = "${aws_security_group.superset_service.id}"
  source_security_group_id = "${aws_security_group.superset_lb.id}"

  type      = "ingress"
  from_port = "8000"
  to_port   = "8000"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "superset_service_egress_postgres_superset_db" {
  description = "egress-postgres-superset-db"

  security_group_id        = "${aws_security_group.superset_service.id}"
  source_security_group_id = "${aws_security_group.superset_db.id}"

  type      = "egress"
  from_port = "5432"
  to_port   = "5432"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "superset_service_egress_postgres_datasets_db" {
  description = "egress-postgres-datasets-db"

  security_group_id        = "${aws_security_group.superset_service.id}"
  source_security_group_id = "${aws_security_group.datasets.id}"

  type      = "egress"
  from_port = "5432"
  to_port   = "5432"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "superset_service_egress_https_to_ecr_api" {
  description = "egress-https-to-ecr-api"

  security_group_id        = "${aws_security_group.superset_service.id}"
  source_security_group_id = "${aws_security_group.ecr_api.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "prometheus_service_egress_https_to_ecr_api" {
  description = "egress-https-to-ecr-api"

  security_group_id        = "${aws_security_group.prometheus_service.id}"
  source_security_group_id = "${aws_security_group.ecr_api.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "sentryproxy_service_egress_https_to_ecr_api" {
  description = "egress-https-to-ecr-api"

  security_group_id        = "${aws_security_group.sentryproxy_service.id}"
  source_security_group_id = "${aws_security_group.ecr_api.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}


resource "aws_security_group_rule" "superset_service_egress_https_to_cloudwatch" {
  description = "egress-https-to-cloudwatch"

  security_group_id        = "${aws_security_group.superset_service.id}"
  source_security_group_id = "${aws_security_group.cloudwatch.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "superset_service_egress_dns_udp_to_dns_rewrite_proxy" {
  description = "egress-dns-to-dns-rewrite-proxy"

  security_group_id = "${aws_security_group.superset_service.id}"
  cidr_blocks       = ["${aws_subnet.private_with_egress.*.cidr_block[0]}"]

  type      = "egress"
  from_port = "53"
  to_port   = "53"
  protocol  = "udp"
}

resource "aws_security_group" "superset_lb" {
  name        = "${var.prefix}-superset-lb"
  description = "${var.prefix}-superset-lb"
  vpc_id      = "${aws_vpc.notebooks.id}"

  tags = {
    Name = "${var.prefix}-superset-lb"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "superset_lb_ingress_http_admin_service" {
  description = "ingress-http-admin-service"

  security_group_id        = "${aws_security_group.superset_lb.id}"
  source_security_group_id = "${aws_security_group.admin_service.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "superset_lb_egress_http_superset_service" {
  description = "egress-http-superset-service"

  security_group_id        = "${aws_security_group.superset_lb.id}"
  source_security_group_id = "${aws_security_group.superset_service.id}"

  type      = "egress"
  from_port = "8000"
  to_port   = "8000"
  protocol  = "tcp"
}

resource "aws_security_group" "flower_lb" {
  name        = "${var.prefix}-flower-lb"
  description = "${var.prefix}-flower-lb"
  vpc_id      = "${aws_vpc.notebooks.id}"

  tags = {
    Name = "${var.prefix}-flower-lb"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "flower_lb_ingress_http_admin_service" {
  description = "ingress-admin-service"

  security_group_id        = "${aws_security_group.flower_lb.id}"
  source_security_group_id = "${aws_security_group.admin_service.id}"

  type      = "ingress"
  from_port = "80"
  to_port   = "80"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "flower_lb_egress_http_flower_service" {
  description = "egress-http-flower-service"

  security_group_id        = "${aws_security_group.flower_lb.id}"
  source_security_group_id = "${aws_security_group.flower_service.id}"

  type      = "egress"
  from_port = "80"
  to_port   = "80"
  protocol  = "tcp"
}

resource "aws_security_group" "flower_service" {
  name        = "${var.prefix}-flower-service"
  description = "${var.prefix}-flower-service"
  vpc_id      = "${aws_vpc.notebooks.id}"

  tags = {
    Name = "${var.prefix}-flower-service"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "flower_service_ingress_http_flower_lb" {
  description = "ingress-flower-lb"

  security_group_id        = "${aws_security_group.flower_service.id}"
  source_security_group_id = "${aws_security_group.flower_lb.id}"

  type      = "ingress"
  from_port = "80"
  to_port   = "80"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "flower_service_ingress_admin_redis" {
  description = "ingress-flower-service"

  security_group_id        = "${aws_security_group.admin_redis.id}"
  source_security_group_id = "${aws_security_group.flower_service.id}"

  type      = "ingress"
  from_port = "6379"
  to_port   = "6379"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "flower_service_egress_admin_redis" {
  description = "egress-redis-admin-redis"

  security_group_id        = "${aws_security_group.flower_service.id}"
  source_security_group_id = "${aws_security_group.admin_redis.id}"

  type      = "egress"
  from_port = "6379"
  to_port   = "6379"
  protocol  = "tcp"
}

resource "aws_security_group" "efs_notebooks" {
  name        = "${var.prefix}-efs-notebooks"
  description = "${var.prefix}-efs-notebooks"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-efs-notebooks"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "efs_mount_target_notebooks" {
  name        = "${var.prefix}-efs-mount-target-notebooks"
  description = "${var.prefix}-efs-mount-target-notebooks"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-efs-mount-target-notebooks"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "efs_mount_target_notebooks_nfs_ingress_notebooks" {
  description = "ingress-nfs-notebooks"

  security_group_id        = "${aws_security_group.efs_mount_target_notebooks.id}"
  source_security_group_id = "${aws_security_group.notebooks.id}"

  type      = "ingress"
  from_port = "2049"
  to_port   = "2049"
  protocol  = "tcp"
}


resource "aws_security_group" "quicksight" {
  name        = "${var.quicksight_security_group_name}"
  description = "${var.quicksight_security_group_description}"
  vpc_id      = "${aws_vpc.datasets.id}"

  tags = {
    Name = "${var.quicksight_security_group_name}"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "quicksight_ingress_all_from_datasets_db" {
  description = "ingress-all-from-datasets-db"

  security_group_id        = "${aws_security_group.quicksight.id}"
  source_security_group_id = "${aws_security_group.datasets.id}"

  type      = "ingress"
  from_port = "0"
  to_port   = "65535"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "quicksight_egress_postgres_to_datasets_db" {
  description = "egress-postgres-to-datasets-db"

  security_group_id        = "${aws_security_group.quicksight.id}"
  source_security_group_id = "${aws_security_group.datasets.id}"

  type      = "egress"
  from_port = "${aws_rds_cluster_instance.datasets.port}"
  to_port   = "${aws_rds_cluster_instance.datasets.port}"
  protocol  = "tcp"
}

resource "aws_security_group" "datasets" {
  name        = "${var.prefix}-datasets"
  description = "${var.prefix}-datasets"
  vpc_id      = "${aws_vpc.datasets.id}"

  tags = {
    Name = "${var.prefix}-datasets"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "datasets_db_ingress_postgres_from_admin" {
  description = "ingress-postgres-from-admin"

  security_group_id        = "${aws_security_group.datasets.id}"
  source_security_group_id = "${aws_security_group.admin_service.id}"

  type      = "ingress"
  from_port = "${aws_rds_cluster_instance.datasets.port}"
  to_port   = "${aws_rds_cluster_instance.datasets.port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "datasets_db_ingress_postgres_from_notebooks" {
  description = "ingress-postgres-from-notebooks"

  security_group_id        = "${aws_security_group.datasets.id}"
  source_security_group_id = "${aws_security_group.notebooks.id}"

  type      = "ingress"
  from_port = "${aws_rds_cluster_instance.datasets.port}"
  to_port   = "${aws_rds_cluster_instance.datasets.port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "datasets_db_ingress_postgres_from_paas" {
  description = "ingress-postgres-from-paas"

  security_group_id = "${aws_security_group.datasets.id}"
  cidr_blocks       = ["${var.paas_cidr_block}"]

  type      = "ingress"
  from_port = "${aws_rds_cluster_instance.datasets.port}"
  to_port   = "${aws_rds_cluster_instance.datasets.port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "datasets_db_ingress_postgres_from_superset" {
  description = "ingress-postgres-from-superset"

  security_group_id        = "${aws_security_group.datasets.id}"
  source_security_group_id = "${aws_security_group.superset_service.id}"

  type      = "ingress"
  from_port = "${aws_rds_cluster_instance.datasets.port}"
  to_port   = "${aws_rds_cluster_instance.datasets.port}"
  protocol  = "tcp"
}


resource "aws_security_group_rule" "datasets_db_ingress_all_from_quicksight" {
  description = "ingress-all-from-quicksight"

  security_group_id        = "${aws_security_group.datasets.id}"
  source_security_group_id = "${aws_security_group.quicksight.id}"

  type      = "ingress"
  from_port = "0"
  to_port   = "65535"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "datasets_db_egress_all_to_quicksight" {
  description = "egress-all-to-quicksight"

  security_group_id        = "${aws_security_group.datasets.id}"
  source_security_group_id = "${aws_security_group.quicksight.id}"

  type      = "egress"
  from_port = "0"
  to_port   = "65535"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "elasticsearch_ingress_from_admin" {
  description = "ingress-elasticsearch-https-from-admin"

  security_group_id        = "${aws_security_group.datasets.id}"
  source_security_group_id = "${aws_security_group.admin_service.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "elasticsearch_ingress_from_paas" {
  description = "ingress-elasticsearch-https-from-paas-ie-data-flow"

  security_group_id = "${aws_security_group.datasets.id}"
  cidr_blocks       = [var.paas_cidr_block]

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "ecr_api_ingress_https_from_flower" {
  description = "ingress-https-from-flower-service"

  security_group_id        = "${aws_security_group.ecr_api.id}"
  source_security_group_id = "${aws_security_group.flower_service.id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "flower_service_egress_https_to_ecr_api" {
  description = "egress-https-to-ecr-api"

  security_group_id        = "${aws_security_group.flower_service.id}"
  source_security_group_id = "${aws_security_group.ecr_api.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "flower_egress_https_all" {
  description = "egress-https-to-all"

  security_group_id = "${aws_security_group.flower_service.id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "flower_service_egress_dns_udp_to_dns_rewrite_proxy" {
  description = "egress-dns-to-dns-rewrite-proxy"

  security_group_id = "${aws_security_group.flower_service.id}"
  cidr_blocks       = ["${aws_subnet.private_with_egress.*.cidr_block[0]}"]

  type      = "egress"
  from_port = "53"
  to_port   = "53"
  protocol  = "udp"
}

resource "aws_security_group" "mlflow_service" {
  count       = "${length(var.mlflow_instances)}"
  name        = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}-service"
  description = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}-service"
  vpc_id      = "${aws_vpc.notebooks.id}"

  tags = {
    Name = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}-service"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "mlflow_service_ingress_http_mlflow_lb" {
  count       = "${length(var.mlflow_instances)}"
  description = "ingress-mlflow-lb"

  security_group_id = "${aws_security_group.mlflow_service[count.index].id}"
  cidr_blocks       = ["${aws_lb.mlflow.*.subnet_mapping[count.index].*.private_ipv4_address[0]}/32"]

  type      = "ingress"
  from_port = "${local.mlflow_port}"
  to_port   = "${local.mlflow_port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "mlflow_service_ingress_http_mlflow_dataflow_lb" {
  count       = "${length(var.mlflow_instances)}"
  description = "ingress-mlflow-dataflow-lb"

  security_group_id = "${aws_security_group.mlflow_service[count.index].id}"
  cidr_blocks       = ["${aws_lb.mlflow_dataflow.*.subnet_mapping[count.index].*.private_ipv4_address[0]}/32"]

  type      = "ingress"
  from_port = "${local.mlflow_port}"
  to_port   = "${local.mlflow_port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "mlflow_service_ingress_notebooks" {
  count       = "${length(var.mlflow_instances)}"
  description = "ingress-notebooks"

  security_group_id        = "${aws_security_group.mlflow_service[count.index].id}"
  source_security_group_id = "${aws_security_group.notebooks.id}"

  type      = "ingress"
  from_port = "${local.mlflow_port}"
  to_port   = "${local.mlflow_port}"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "ecr_api_ingress_https_from_mlflow" {
  count       = "${length(var.mlflow_instances)}"
  description = "ingress-https-from-mlflow-${var.mlflow_instances[count.index]}-service"

  security_group_id        = "${aws_security_group.ecr_api.id}"
  source_security_group_id = "${aws_security_group.mlflow_service[count.index].id}"

  type      = "ingress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "mlflow_service_egress_https_to_ecr_api" {
  count       = "${length(var.mlflow_instances)}"
  description = "egress-https-to-ecr-api"

  security_group_id        = "${aws_security_group.mlflow_service[count.index].id}"
  source_security_group_id = "${aws_security_group.ecr_api.id}"

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "mlflow_egress_https_all" {
  count       = "${length(var.mlflow_instances)}"
  description = "egress-https-to-all"

  security_group_id = "${aws_security_group.mlflow_service[count.index].id}"
  cidr_blocks       = ["0.0.0.0/0"]

  type      = "egress"
  from_port = "443"
  to_port   = "443"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "mlflow_service_egress_dns_udp_to_dns_rewrite_proxy" {
  count       = "${length(var.mlflow_instances)}"
  description = "egress-dns-to-dns-rewrite-proxy"

  security_group_id = "${aws_security_group.mlflow_service[count.index].id}"
  cidr_blocks       = ["${aws_subnet.private_with_egress.*.cidr_block[0]}"]

  type      = "egress"
  from_port = "53"
  to_port   = "53"
  protocol  = "udp"
}

resource "aws_security_group" "mlflow_db" {
  count       = "${length(var.mlflow_instances)}"
  name        = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}-db"
  description = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}-db"
  vpc_id      = "${aws_vpc.notebooks.id}"

  tags = {
    Name = "${var.prefix}-mlflow-${var.mlflow_instances[count.index]}-db"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "mlflow_db_ingress_postgres_mlflow_service" {
  count       = "${length(var.mlflow_instances)}"
  description = "ingress-postgress-mlflow-service-${var.mlflow_instances[count.index]}"

  security_group_id        = "${aws_security_group.mlflow_db[count.index].id}"
  source_security_group_id = "${aws_security_group.mlflow_service[count.index].id}"

  type      = "ingress"
  from_port = "5432"
  to_port   = "5432"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "mlflow_service_egress_postgres_mlflow_db" {
  count       = "${length(var.mlflow_instances)}"
  description = "egress-postgres-mlflow-db"

  security_group_id        = "${aws_security_group.mlflow_service[count.index].id}"
  source_security_group_id = "${aws_security_group.mlflow_db[count.index].id}"

  type      = "egress"
  from_port = "5432"
  to_port   = "5432"
  protocol  = "tcp"
}

resource "aws_security_group_rule" "notebooks_egress_http_to_mlflow_service" {
  count       = "${length(var.mlflow_instances)}"
  description = "egress-http-to-mlflow-service-${var.mlflow_instances[count.index]}"

  security_group_id        = "${aws_security_group.notebooks.id}"
  source_security_group_id = "${aws_security_group.mlflow_service[count.index].id}"

  type      = "egress"
  from_port = "${local.mlflow_port}"
  to_port   = "${local.mlflow_port}"
  protocol  = "tcp"
}

resource "aws_security_group" "arango_lb" {
  name        = "${var.prefix}-arango_lb"
  description = "${var.prefix}-arango_lb"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-arango_lb"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "arango_service" {
  name        = "${var.prefix}-arango_service"
  description = "${var.prefix}-arango_service"
  vpc_id      = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}-arango_service"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "arango_service_ingress_8529_arango_lb" {
  description = "ingress-arango-lb"

  security_group_id        = "${aws_security_group.arango_service.id}"
  source_security_group_id = "${aws_security_group.arango_lb.id}"

  type      = "ingress"
  from_port = "8529"
  to_port   = "8529"
  protocol  = "tcp"
}