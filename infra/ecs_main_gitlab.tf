resource "aws_ecs_service" "gitlab" {
  name            = "${var.prefix}-gitlab"
  cluster         = "${aws_ecs_cluster.main_cluster.id}"
  task_definition = "${aws_ecs_task_definition.gitlab.arn}"
  desired_count   = 1
  launch_type     = "EC2"
  deployment_maximum_percent = 200

  network_configuration {
    subnets         = ["${aws_subnet.private_with_egress.*.id[0]}"]
    security_groups = ["${aws_security_group.gitlab_service.id}"]
  }

  load_balancer {
    target_group_arn = "${aws_lb_target_group.gitlab_80.arn}"
    container_port   = "80"
    container_name   = "gitlab"
  }

  load_balancer {
    target_group_arn = "${aws_lb_target_group.gitlab_22.arn}"
    container_port   = "22"
    container_name   = "gitlab"
  }

  service_registries {
    registry_arn   = "${aws_service_discovery_service.gitlab.arn}"
  }

  depends_on = [
    # The target group must have been associated with the listener first
    "aws_lb_listener.gitlab_443",
    "aws_lb_listener.gitlab_22",
  ]
}

resource "aws_service_discovery_service" "gitlab" {
  name = "gitlab"
  dns_config {
    namespace_id = "${aws_service_discovery_private_dns_namespace.jupyterhub.id}"
    dns_records {
      ttl = 10
      type = "A"
    }
  }

  # Needed for a service to be able to register instances with a target group,
  # but only if it has a service_registries, which we do
  # https://forums.aws.amazon.com/thread.jspa?messageID=852407&tstart=0
  health_check_custom_config {
    failure_threshold = 1
  }
}

resource "aws_ecs_task_definition" "gitlab" {
  family                   = "${var.prefix}-gitlab"
  container_definitions    = "${data.template_file.gitlab_container_definitions.rendered}"
  execution_role_arn       = "${aws_iam_role.gitlab_task_execution.arn}"
  task_role_arn            = "${aws_iam_role.gitlab_task.arn}"
  network_mode             = "awsvpc"
  cpu                      = "${local.gitlab_container_cpu}"
  memory                   = "${local.gitlab_container_memory}"
  requires_compatibilities = ["EC2"]

  volume {
    name      = "data-gitlab"
    host_path = "/data/gitlab"
  }

  lifecycle {
    ignore_changes = [
      "revision",
    ]
  }
}

data "template_file" "gitlab_container_definitions" {
  template = "${file("${path.module}/ecs_main_gitlab_container_definitions.json")}"

  vars {
    container_image   = "${var.gitlab_container_image}"
    container_name    = "gitlab"
    log_group         = "${aws_cloudwatch_log_group.gitlab.name}"
    log_region        = "${data.aws_region.aws_region.name}"

    gitlab_omnibus_config = "${jsonencode("${data.template_file.gitlab_container_definitions_gitlab_omnibus_config.rendered}")}"
    bucket                = "${aws_s3_bucket.gitlab.id}"
    bucket_region         = "${aws_s3_bucket.gitlab.region}"
  }
}

data "template_file" "gitlab_container_definitions_gitlab_omnibus_config" {
  template = "${file("${path.module}/ecs_main_gitlab_container_definitions_GITLAB_OMNIBUS_CONFIG.rb")}"

  vars {
    external_domain = "${var.gitlab_domain}"
    db__host        = "${aws_rds_cluster.gitlab.endpoint}"
    db__name        = "${aws_rds_cluster.gitlab.database_name}"
    db__password    = "${random_string.aws_db_instance_gitlab_password.result}"
    db__port        = "${aws_rds_cluster.gitlab.port}"
    db__user        = "${aws_rds_cluster.gitlab.master_username}"

    redis__host     = "${aws_elasticache_cluster.gitlab_redis.cache_nodes.0.address}"
    redis__port     = "${aws_elasticache_cluster.gitlab_redis.cache_nodes.0.port}"

    bucket__region  = "${aws_s3_bucket.gitlab.region}"
    bucket__domain  = "${aws_s3_bucket.gitlab.bucket_regional_domain_name}"

    sso__id     = "${var.gitlab_sso_id}"
    sso__secret = "${var.gitlab_sso_secret}"
    sso__domain = "${var.gitlab_sso_domain}"
  }
}

resource "aws_cloudwatch_log_group" "gitlab" {
  name              = "${var.prefix}-gitlab"
  retention_in_days = "3653"
}

resource "aws_cloudwatch_log_subscription_filter" "gitlab" {
  count = "${var.cloudwatch_subscription_filter ? 1 : 0}"
  name            = "${var.prefix}-gitlab"
  log_group_name  = "${aws_cloudwatch_log_group.gitlab.name}"
  filter_pattern  = ""
  destination_arn = "${var.cloudwatch_destination_arn}"
}

resource "aws_iam_role" "gitlab_task_execution" {
  name               = "${var.prefix}-gitlab-task-execution"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.gitlab_task_execution_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "gitlab_task_execution_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "gitlab_task_execution" {
  role       = "${aws_iam_role.gitlab_task_execution.name}"
  policy_arn = "${aws_iam_policy.gitlab_task_execution.arn}"
}

resource "aws_iam_policy" "gitlab_task_execution" {
  name   = "${var.prefix}-gitlab-task-execution"
  path   = "/"
  policy = "${data.aws_iam_policy_document.gitlab_task_execution.json}"
}

data "aws_iam_policy_document" "gitlab_task_execution" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.gitlab.arn}",
    ]
  }
}

resource "aws_iam_role" "gitlab_task" {
  name               = "${var.prefix}-gitlab-task"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.gitlab_task_ecs_tasks_assume_role.json}"
}

resource "aws_iam_role_policy_attachment" "gitlab_access_gitlab_bucket" {
  role       = "${aws_iam_role.gitlab_task.name}"
  policy_arn = "${aws_iam_policy.gitlab_access_uploads_bucket.arn}"
}

resource "aws_iam_policy" "gitlab_access_uploads_bucket" {
  name   = "${var.prefix}-gitlab-access-gitlab-bucket"
  path   = "/"
  policy = "${data.aws_iam_policy_document.gitlab_access_gitlab_bucket.json}"
}

data "aws_iam_policy_document" "gitlab_access_gitlab_bucket" {
  statement {
    actions = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
    ]

    resources = [
      "${aws_s3_bucket.gitlab.arn}/*",
    ]
  }

  statement {
    actions = [
      "s3:GetBucketLocation",
      "s3:ListObjects",
    ]

    resources = [
      "${aws_s3_bucket.gitlab.arn}",
    ]
  }
}

data "aws_iam_policy_document" "gitlab_task_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_lb" "gitlab" {
  name               = "${var.prefix}-gitlab"
  load_balancer_type = "network"

  subnet_mapping {
    subnet_id     = "${aws_subnet.public.*.id[0]}"
    allocation_id = "${aws_eip.gitlab.id}"
  }
}

resource "aws_lb_listener" "gitlab_443" {
  load_balancer_arn = "${aws_lb.gitlab.arn}"
  port              = "443"
  protocol          = "TLS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = "${aws_acm_certificate.gitlab.arn}"

  default_action {
    target_group_arn = "${aws_lb_target_group.gitlab_80.arn}"
    type             = "forward"
  }
}

resource "aws_lb_listener" "gitlab_22" {
  load_balancer_arn = "${aws_lb.gitlab.arn}"
  port              = "22"
  protocol          = "TCP"

  default_action {
    target_group_arn = "${aws_lb_target_group.gitlab_22.arn}"
    type             = "forward"
  }
}

resource "aws_lb_target_group" "gitlab_80" {
  name_prefix = "gl80-"
  port        = "80"
  vpc_id      = "${aws_vpc.main.id}"
  target_type = "ip"
  protocol = "TCP"

  health_check {
    protocol = "TCP"
    interval = 10
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb_target_group" "gitlab_22" {
  name_prefix = "gl22-"
  port        = "22"
  vpc_id      = "${aws_vpc.main.id}"
  target_type = "ip"
  protocol    = "TCP"

  health_check {
    protocol = "TCP"
    interval = 10
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_elasticache_cluster" "gitlab_redis" {
  cluster_id           = "${var.prefix_short}-gitlab"
  engine               = "redis"
  node_type            = "cache.t2.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis5.0"
  engine_version       = "5.0.3"
  port                 = 6379
  subnet_group_name    = "${aws_elasticache_subnet_group.gitlab.name}"
  security_group_ids   = ["${aws_security_group.gitlab_redis.id}"]
}

resource "aws_elasticache_subnet_group" "gitlab" {
  name       = "${var.prefix_short}-gitlab"
  subnet_ids = ["${aws_subnet.private_with_egress.*.id}"]
}

resource "aws_rds_cluster" "gitlab" {
  cluster_identifier      = "${var.prefix}-gitlab"
  engine                  = "aurora-postgresql"
  availability_zones      = ["${var.aws_availability_zones}"]
  database_name           = "${var.prefix_underscore}_gitlab"
  master_username         = "${var.prefix_underscore}_gitlab_master"
  master_password         = "${random_string.aws_db_instance_gitlab_password.result}"
  backup_retention_period = 31
  preferred_backup_window = "03:29-03:59"
  apply_immediately       = true

  vpc_security_group_ids = ["${aws_security_group.gitlab_db.id}"]
  db_subnet_group_name   = "${aws_db_subnet_group.gitlab.name}"
  #ca_cert_identifier     = "rds-ca-2019"
}

resource "aws_rds_cluster_instance" "gitlab" {
  count              = 2
  identifier_prefix  = "${var.prefix}-gitlab"
  cluster_identifier = "${aws_rds_cluster.gitlab.id}"
  engine             = "${aws_rds_cluster.gitlab.engine}"
  engine_version     = "${aws_rds_cluster.gitlab.engine_version}"
  instance_class     = "${var.gitlab_db_instance_class}"
}

resource "aws_db_subnet_group" "gitlab" {
  name       = "${var.prefix}-gitlab"
  subnet_ids = ["${aws_subnet.private_with_egress.*.id}"]

  tags {
    Name = "${var.prefix}-gitlab"
  }
}


resource "random_string" "aws_db_instance_gitlab_password" {
  length = 99
  special = false
}

resource "aws_acm_certificate" "gitlab" {
  domain_name       = "${aws_route53_record.gitlab.name}"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate_validation" "gitlab" {
  certificate_arn = "${aws_acm_certificate.gitlab.arn}"
}

resource "aws_iam_role" "gitlab_ecs" {
  name               = "${var.prefix}-gitlab-ecs"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.gitlab_ecs_assume_role.json}"
}

resource "aws_iam_role_policy_attachment" "gitlab_ecs" {
  role       = "${aws_iam_role.gitlab_ecs.name}"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceRole"
}

data "aws_iam_policy_document" "gitlab_ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "gitlab_ec2" {
  name               = "${var.prefix}-gitlab-ec2"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.gitlab_ec2_assume_role.json}"
}

data "aws_iam_policy_document" "gitlab_ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "gitlab_ec2" {
  role       = "${aws_iam_role.gitlab_ec2.name}"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_instance_profile" "gitlab_ec2" {
  name = "${var.prefix}-gitlab-ec2"
  path = "/"
  roles = ["${aws_iam_role.gitlab_ec2.id}"]
}

resource "aws_instance" "gitlab" {
  ami           = "ami-0749bd3fac17dc2cc"
  instance_type = "t3a.xlarge"
  iam_instance_profile = "${aws_iam_instance_profile.gitlab_ec2.id}"
  availability_zone = "${var.aws_availability_zones[0]}"

  vpc_security_group_ids      = ["${aws_security_group.gitlab-ec2.id}"]
  associate_public_ip_address = "false"
  key_name                    = "michal"
  subnet_id                   = "${aws_subnet.private_with_egress.*.id[0]}"
  user_data                   = <<EOF
  #!/bin/bash
  echo ECS_CLUSTER=${aws_ecs_cluster.main_cluster.id} >> /etc/ecs/ecs.config

  # Follow symlinks to find the real device
  device=$(sudo readlink -f /dev/sdh)

  # Wait for the drive to be attached
  while [ ! -e $device ] ; do sleep 1 ; done

  # Format /dev/sdh if it does not contain a partition yet
  if [ "$(sudo file -b -s $device)" == "data" ]; then
    sudo mkfs -t ext4 $device
  fi

  # Mount the drive
  sudo mkdir -p /data
  sudo mount $device /data

  # Persist the volume in /etc/fstab so it gets mounted again
  sudo echo "$device /data ext4 defaults,nofail 0 2" >> /etc/fstab

  sudo mkdir -p /data/gitlab
  EOF

  tags = {
    Name = "${var.prefix}-gitlab"
  }
}

resource "aws_ebs_volume" "gitlab" {
  availability_zone = "${var.aws_availability_zones[0]}"
  size              = 256
  encrypted         = true

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "${var.prefix}-gitlab"
  }
}

resource "aws_volume_attachment" "gitlab" {
  device_name = "/dev/sdh"
  volume_id   = "${aws_ebs_volume.gitlab.id}"
  instance_id = "${aws_instance.gitlab.id}"
}

resource "aws_eip" "gitlab" {
  vpc = true

  lifecycle {
    # VPN routing may depend on this
    prevent_destroy = true
  }
}
