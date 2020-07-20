resource "aws_ecs_service" "dnsmasq" {
  name            = "${var.prefix}-dnsmasq"
  cluster         = "${aws_ecs_cluster.main_cluster.id}"
  task_definition = "${aws_ecs_task_definition.dnsmasq.arn}"
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = ["${aws_subnet.private_with_egress.*.id[0]}"]
    security_groups = ["${aws_security_group.dnsmasq.id}"]
  }
}

data "external" "dnsmasq_current_tag" {
  program = ["${path.module}/container-tag.sh"]

  query = {
    cluster_name = "${aws_ecs_cluster.main_cluster.name}"
    service_name = "${var.prefix}-dnsmasq"  # Manually specified to avoid a cycle
    container_name = "${local.dnsmasq_container_name}"
  }
}

resource "aws_ecs_task_definition" "dnsmasq" {
  family                = "${var.prefix}-dnsmasq"
  container_definitions = "${data.template_file.dnsmasq_container_definitions.rendered}"
  execution_role_arn    = "${aws_iam_role.dnsmasq_task_execution.arn}"
  task_role_arn         = "${aws_iam_role.dnsmasq_task.arn}"
  network_mode          = "awsvpc"
  cpu                   = "${local.dnsmasq_container_cpu}"
  memory                = "${local.dnsmasq_container_memory}"
  requires_compatibilities = ["FARGATE"]

  lifecycle {
    ignore_changes = [
      "revision",
    ]
  }
}

data "template_file" "dnsmasq_container_definitions" {
  template = "${file("${path.module}/ecs_main_dnsmasq_container_definitions.json")}"

  vars {
    container_image    = "${var.dnsmasq_container_image}:${data.external.dnsmasq_current_tag.result.tag}"
    container_name     = "${local.dnsmasq_container_name}"
    container_cpu      = "${local.dnsmasq_container_cpu}"
    container_memory   = "${local.dnsmasq_container_memory}"

    log_group  = "${aws_cloudwatch_log_group.dnsmasq.name}"
    log_region = "${data.aws_region.aws_region.name}"

    dns_server   = "${cidrhost(aws_vpc.main.cidr_block, 2)}"
    aws_region   = "${data.aws_region.aws_region.name}"
    aws_ec2_host = "ec2.${data.aws_region.aws_region.name}.amazonaws.com"
    vpc_id       = "${aws_vpc.notebooks.id}"
    aws_route53_zone = "${var.aws_route53_zone}"
  }
}

resource "aws_cloudwatch_log_group" "dnsmasq" {
  name              = "${var.prefix}-dnsmasq"
  retention_in_days = "3653"
}

resource "aws_cloudwatch_log_subscription_filter" "dnsmasq" {
  count = "${var.cloudwatch_subscription_filter ? 1 : 0}"
  name            = "${var.prefix}-dnsmasq"
  log_group_name  = "${aws_cloudwatch_log_group.dnsmasq.name}"
  filter_pattern  = ""
  destination_arn = "${var.cloudwatch_destination_arn}"
}

resource "aws_iam_role" "dnsmasq_task_execution" {
  name               = "${var.prefix}-dnsmasq-task-execution"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.dnsmasq_task_execution_ecs_tasks_assume_role.json}"
}

data "aws_iam_policy_document" "dnsmasq_task_execution_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "dnsmasq_task_execution" {
  role       = "${aws_iam_role.dnsmasq_task_execution.name}"
  policy_arn = "${aws_iam_policy.dnsmasq_task_execution.arn}"
}

resource "aws_iam_policy" "dnsmasq_task_execution" {
  name        = "${var.prefix}-dnsmasq-task-execution"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.dnsmasq_task_execution.json}"
}

data "aws_iam_policy_document" "dnsmasq_task_execution" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.dnsmasq.arn}",
    ]
  }
}

resource "aws_iam_role" "dnsmasq_task" {
  name               = "${var.prefix}-dnsmasq-task"
  path               = "/"
  assume_role_policy = "${data.aws_iam_policy_document.dnsmasq_task_ecs_tasks_assume_role.json}"
}

resource "aws_iam_role_policy_attachment" "dnsmasq" {
  role       = "${aws_iam_role.dnsmasq_task.name}"
  policy_arn = "${aws_iam_policy.dnsmasq_task.arn}"
}

resource "aws_iam_policy" "dnsmasq_task" {
  name        = "${var.prefix}-dnsmasq-task"
  path        = "/"
  policy       = "${data.aws_iam_policy_document.dnsmasq_task.json}"
}

data "aws_iam_policy_document" "dnsmasq_task" {
  statement {
    actions = [
      "ec2:AssociateDhcpOptions",
      "ec2:CreateDhcpOptions",
      "ec2:CreateTags",
      "ec2:DeleteDhcpOptions",
      "ec2:DescribeVpcs",
    ]

    resources = [
      "*",
    ]
  }
}

data "aws_iam_policy_document" "dnsmasq_task_ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}
