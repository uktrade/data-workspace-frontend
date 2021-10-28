resource "aws_vpc_peering_connection" "jupyterhub" {
  peer_vpc_id   = "${aws_vpc.notebooks.id}"
  vpc_id        = "${aws_vpc.main.id}"
  auto_accept   = true

  accepter {
    allow_remote_vpc_dns_resolution = false
  }

  requester {
    allow_remote_vpc_dns_resolution = false
  }

  tags = {
    Name = "${var.prefix}"
  }
}

resource "aws_vpc" "notebooks" {
  cidr_block = "${var.vpc_notebooks_cidr}"

  enable_dns_support   = false
  enable_dns_hostnames = false

  tags = {
    Name = "${var.prefix}-notebooks"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_flow_log" "notebooks" {
  log_destination = "${aws_cloudwatch_log_group.vpc_main_flow_log.arn}"
  iam_role_arn   = "${aws_iam_role.vpc_notebooks_flow_log.arn}"
  vpc_id         = "${aws_vpc.notebooks.id}"
  traffic_type   = "ALL"
}

resource "aws_cloudwatch_log_group" "vpc_notebooks_flow_log" {
  name              = "${var.prefix}-vpc-notebooks-flow-log"
  retention_in_days = "3653"
}

resource "aws_iam_role" "vpc_notebooks_flow_log" {
  name = "${var.prefix}-vpc-notebooks-flow-log"
  assume_role_policy = "${data.aws_iam_policy_document.vpc_notebooks_flow_log_vpc_flow_logs_assume_role.json}"
}

data "aws_iam_policy_document" "vpc_notebooks_flow_log_vpc_flow_logs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["vpc-flow-logs.amazonaws.com"]
    }
  }
}

resource "aws_vpc" "main" {
  cidr_block = "${var.vpc_cidr}"

  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.prefix}"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_dhcp_options" "main" {
  domain_name_servers = ["AmazonProvidedDNS"]
  domain_name = "eu-west-2.compute.internal"

  tags = {
    Name = "${var.prefix}"
  }
}

resource "aws_vpc_dhcp_options_association" "main" {
  vpc_id          = "${aws_vpc.main.id}"
  dhcp_options_id = "${aws_vpc_dhcp_options.main.id}"
}

resource "aws_flow_log" "main" {
  log_destination = "${aws_cloudwatch_log_group.vpc_main_flow_log.arn}"
  iam_role_arn   = "${aws_iam_role.vpc_main_flow_log.arn}"
  vpc_id         = "${aws_vpc.main.id}"
  traffic_type   = "ALL"
}

resource "aws_cloudwatch_log_group" "vpc_main_flow_log" {
  name              = "${var.prefix}-vpc-main-flow-log"
  retention_in_days = "3653"
}

resource "aws_iam_role" "vpc_main_flow_log" {
  name = "${var.prefix}-vpc-main-flow-log"
  assume_role_policy = "${data.aws_iam_policy_document.vpc_main_flow_log_vpc_flow_logs_assume_role.json}"
}

data "aws_iam_policy_document" "vpc_main_flow_log_vpc_flow_logs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["vpc-flow-logs.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "vpc_main_flow_log" {
  name   = "${var.prefix}-vpc-main-flow-log"
  role   = "${aws_iam_role.vpc_main_flow_log.id}"
  policy =  "${data.aws_iam_policy_document.vpc_main_flow_log.json}"
}

data "aws_iam_policy_document" "vpc_main_flow_log" {
  statement {
    actions = [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
    ]

    resources = [
      "${aws_cloudwatch_log_group.vpc_main_flow_log.arn}:*",
    ]
  }
}

resource "aws_subnet" "public" {
  count = "${length(var.aws_availability_zones)}"
  vpc_id     = "${aws_vpc.main.id}"
  cidr_block = "${cidrsubnet(aws_vpc.main.cidr_block, var.subnets_num_bits, count.index)}"

  availability_zone = "${var.aws_availability_zones[count.index]}"

  tags = {
    Name = "${var.prefix}-public-${var.aws_availability_zones_short[count.index]}"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_subnet" "private_with_egress" {
  count      = "${length(var.aws_availability_zones)}"
  vpc_id     = "${aws_vpc.main.id}"
  cidr_block = "${cidrsubnet(aws_vpc.main.cidr_block, var.subnets_num_bits, length(var.aws_availability_zones) + count.index)}"

  availability_zone = "${var.aws_availability_zones[count.index]}"

  tags = {
    Name = "${var.prefix}-private-with-egress-${var.aws_availability_zones_short[count.index]}"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_subnet" "public_whitelisted_ingress" {
  count      = "${length(var.aws_availability_zones)}"
  vpc_id     = "${aws_vpc.main.id}"
  cidr_block = "${cidrsubnet(aws_vpc.main.cidr_block, var.subnets_num_bits, length(var.aws_availability_zones) * 2 + count.index)}"

  availability_zone = "${var.aws_availability_zones[count.index]}"

  tags = {
    Name = "${var.prefix}-public-whitelisted-ingress-${var.aws_availability_zones_short[count.index]}"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route_table_association" "public_whitelisted_ingress" {
  count          = "${length(var.aws_availability_zones)}"
  subnet_id      = "${aws_subnet.public_whitelisted_ingress.*.id[count.index]}"
  route_table_id = "${aws_route_table.public.id}"
}

resource "aws_subnet" "private_without_egress" {
  count      = "${length(var.aws_availability_zones)}"
  vpc_id     = "${aws_vpc.notebooks.id}"
  cidr_block = "${cidrsubnet(aws_vpc.notebooks.cidr_block, var.vpc_notebooks_subnets_num_bits, count.index)}"

  availability_zone = "${var.aws_availability_zones[count.index]}"

  tags = {
    Name = "${var.prefix}-private-without-egress-${var.aws_availability_zones_short[count.index]}"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route_table" "public" {
  vpc_id = "${aws_vpc.main.id}"
  tags = {
    Name = "${var.prefix}-public"
  }
}

resource "aws_route_table_association" "jupyterhub_public" {
  count          = "${length(var.aws_availability_zones)}"
  subnet_id      = "${aws_subnet.public.*.id[count.index]}"
  route_table_id = "${aws_route_table.public.id}"
}

resource "aws_route" "public_internet_gateway_ipv4" {
  route_table_id         = "${aws_route_table.public.id}"
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = "${aws_internet_gateway.main.id}"
}

resource "aws_route_table" "private_with_egress" {
  vpc_id = "${aws_vpc.main.id}"
  tags = {
    Name = "${var.prefix}-private-with-egress"
  }
}

resource "aws_route_table_association" "jupyterhub_private_with_egress" {
  count          = "${length(var.aws_availability_zones)}"
  subnet_id      = "${aws_subnet.private_with_egress.*.id[count.index]}"
  route_table_id = "${aws_route_table.private_with_egress.id}"
}

resource "aws_route" "jupyterhub_to_private_with_egress_to_notebooks" {
  count = "${length(var.aws_availability_zones)}"

  route_table_id            = "${aws_route_table.private_with_egress.id}"
  destination_cidr_block    = "${aws_subnet.private_without_egress.*.cidr_block[count.index]}"
  vpc_peering_connection_id = "${aws_vpc_peering_connection.jupyterhub.id}"
}

resource "aws_route" "private_with_egress_nat_gateway_ipv4" {
  route_table_id         = "${aws_route_table.private_with_egress.id}"
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = "${aws_nat_gateway.main.id}"
}

resource "aws_internet_gateway" "main" {
  vpc_id = "${aws_vpc.main.id}"

  tags = {
    Name = "${var.prefix}"
  }
}

resource "aws_nat_gateway" "main" {
  allocation_id = "${aws_eip.nat_gateway.id}"
  subnet_id     = "${aws_subnet.public.*.id[0]}"

  tags = {
    Name = "${var.prefix}"
  }
}

resource "aws_eip" "nat_gateway" {
  vpc = true
}

resource "aws_route_table" "private_without_egress" {
  vpc_id = "${aws_vpc.notebooks.id}"
  tags = {
    Name = "${var.prefix}-private-without-egress"
  }
}

resource "aws_route" "private_without_egress_to_jupyterhub" {
  count = "${length(var.aws_availability_zones)}"

  route_table_id            = "${aws_route_table.private_without_egress.id}"
  destination_cidr_block    = "${aws_subnet.private_with_egress.*.cidr_block[count.index]}"
  vpc_peering_connection_id = "${aws_vpc_peering_connection.jupyterhub.id}"
}

resource "aws_route_table_association" "jupyterhub_private_without_egress" {
  count          = "${length(var.aws_availability_zones)}"
  subnet_id      = "${aws_subnet.private_without_egress.*.id[count.index]}"
  route_table_id = "${aws_route_table.private_without_egress.id}"
}

resource "aws_service_discovery_private_dns_namespace" "jupyterhub" {
  name = "jupyterhub"
  description = "jupyterhub"
  vpc = "${aws_vpc.main.id}"
}

resource "aws_vpc" "datasets" {
  cidr_block = "${var.vpc_datasets_cidr}"

  enable_dns_support   = true
  enable_dns_hostnames = false

  tags = {
    Name = "${var.prefix}-datasets"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_flow_log" "datasets" {
  log_destination_type = "s3"
  log_destination = "arn:aws:s3:::flowlog-${data.aws_caller_identity.aws_caller_identity.account_id}/${aws_vpc.datasets.id}"
  vpc_id         = "${aws_vpc.datasets.id}"
  traffic_type   = "ALL"
}

resource "aws_vpc_peering_connection" "datasets_to_paas" {
  peer_vpc_id   = "${var.paas_vpc_id}"
  vpc_id        = "${aws_vpc.datasets.id}"

  accepter {
    allow_remote_vpc_dns_resolution = false
  }

  tags = {
    Name = "${var.prefix}-datasets-to-paas"
  }
}

resource "aws_vpc_peering_connection" "datasets_to_main" {
  peer_vpc_id   = "${aws_vpc.datasets.id}"
  vpc_id        = "${aws_vpc.main.id}"

  accepter {
    allow_remote_vpc_dns_resolution = false
  }

  requester {
    allow_remote_vpc_dns_resolution = false
  }

  tags = {
    Name = "${var.prefix}-datasets-to-main"
  }
}

resource "aws_vpc_peering_connection" "datasets_to_notebooks" {
  peer_vpc_id   = "${aws_vpc.datasets.id}"
  vpc_id        = "${aws_vpc.notebooks.id}"

  accepter {
    allow_remote_vpc_dns_resolution = false
  }

  requester {
    allow_remote_vpc_dns_resolution = false
  }

  tags = {
    Name = "${var.prefix}-datasets-to-notebooks"
  }
}

resource "aws_route_table" "datasets" {
  vpc_id = "${aws_vpc.datasets.id}"
  tags = {
    Name = "${var.prefix}-datasets"
  }
}

resource "aws_main_route_table_association" "datasets" {
  vpc_id         = "${aws_vpc.datasets.id}"
  route_table_id = "${aws_route_table.datasets.id}"
}

resource "aws_route" "pcx_datasets_to_paas" {
  route_table_id            = "${aws_route_table.datasets.id}"
  destination_cidr_block    = "${var.paas_cidr_block}"
  vpc_peering_connection_id = "${aws_vpc_peering_connection.datasets_to_paas.id}"
}

resource "aws_route" "pcx_datasets_to_main" {
  route_table_id            = "${aws_route_table.datasets.id}"
  destination_cidr_block    = "${aws_vpc.main.cidr_block}"
  vpc_peering_connection_id = "${aws_vpc_peering_connection.datasets_to_main.id}"
}

resource "aws_route" "pcx_datasets_to_notebooks" {
  route_table_id            = "${aws_route_table.datasets.id}"
  destination_cidr_block    = "${aws_vpc.notebooks.cidr_block}"
  vpc_peering_connection_id = "${aws_vpc_peering_connection.datasets_to_notebooks.id}"
}

resource "aws_route" "pcx_private_with_egress_to_datasets" {
  route_table_id            = "${aws_route_table.private_with_egress.id}"
  destination_cidr_block    = "${aws_vpc.datasets.cidr_block}"
  vpc_peering_connection_id = "${aws_vpc_peering_connection.datasets_to_main.id}"
}

resource "aws_route" "pcx_datasets_to_private_without_egress" {
  route_table_id            = "${aws_route_table.private_without_egress.id}"
  destination_cidr_block    = "${aws_vpc.datasets.cidr_block}"
  vpc_peering_connection_id = "${aws_vpc_peering_connection.datasets_to_notebooks.id}"
}


resource "aws_subnet" "datasets" {
  count      = "${length(var.aws_availability_zones)}"
  vpc_id     = "${aws_vpc.datasets.id}"
  cidr_block = "${var.datasets_subnet_cidr_blocks[count.index]}"

  availability_zone = "${var.dataset_subnets_availability_zones[count.index]}"

  tags = {
    Name = "${var.prefix}-datasets-${var.aws_availability_zones_short[count.index]}"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route_table_association" "datasets" {
  count          = "${length(var.aws_availability_zones)}"
  subnet_id      = "${aws_subnet.datasets.*.id[count.index]}"
  route_table_id = "${aws_route_table.datasets.id}"
}

resource "aws_subnet" "datasets_quicksight" {
  vpc_id     = "${aws_vpc.datasets.id}"
  cidr_block = "${var.quicksight_cidr_block}"

  availability_zone = "${var.quicksight_subnet_availability_zone}"

  tags = {
    Name = "${var.prefix}-datasets-quicksight"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route_table_association" "datasets_quicksight" {
  subnet_id      = "${aws_subnet.datasets_quicksight.id}"
  route_table_id = "${aws_route_table.datasets.id}"
}
