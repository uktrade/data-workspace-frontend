data "aws_route53_zone" "aws_route53_zone" {
  provider = "aws.route53"
  name = "${var.aws_route53_zone}"
}

resource "aws_route53_record" "admin" {
  provider = "aws.route53"
  zone_id = "${data.aws_route53_zone.aws_route53_zone.zone_id}"
  name    = "${var.admin_domain}"
  type    = "A"

  alias {
    name                   = "${aws_alb.admin.dns_name}"
    zone_id                = "${aws_alb.admin.zone_id}"
    evaluate_target_health = false
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "applications" {
  provider = "aws.route53"
  zone_id = "${data.aws_route53_zone.aws_route53_zone.zone_id}"
  name    = "*.${var.admin_domain}"
  type    = "A"

  alias {
    name                   = "${aws_alb.admin.dns_name}"
    zone_id                = "${aws_alb.admin.zone_id}"
    evaluate_target_health = false
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate" "admin" {
  domain_name       = "${aws_route53_record.admin.name}"
  subject_alternative_names = ["*.${aws_route53_record.admin.name}"]
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate_validation" "admin" {
  certificate_arn = "${aws_acm_certificate.admin.arn}"
}

resource "aws_route53_record" "healthcheck" {
  provider = "aws.route53"
  zone_id = "${data.aws_route53_zone.aws_route53_zone.zone_id}"
  name    = "${var.healthcheck_domain}"
  type    = "A"

  alias {
    name                   = "${aws_alb.healthcheck.dns_name}"
    zone_id                = "${aws_alb.healthcheck.zone_id}"
    evaluate_target_health = false
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate" "healthcheck" {
  domain_name       = "${aws_route53_record.healthcheck.name}"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate_validation" "healthcheck" {
  certificate_arn = "${aws_acm_certificate.healthcheck.arn}"
}

resource "aws_route53_record" "prometheus" {
  provider = "aws.route53"
  zone_id = "${data.aws_route53_zone.aws_route53_zone.zone_id}"
  name    = "${var.prometheus_domain}"
  type    = "A"

  alias {
    name                   = "${aws_alb.prometheus.dns_name}"
    zone_id                = "${aws_alb.prometheus.zone_id}"
    evaluate_target_health = false
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate" "prometheus" {
  domain_name       = "${aws_route53_record.prometheus.name}"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate_validation" "prometheus" {
  certificate_arn = "${aws_acm_certificate.prometheus.arn}"
}

resource "aws_route53_record" "gitlab" {
  provider = "aws.route53"
  zone_id  = "${data.aws_route53_zone.aws_route53_zone.zone_id}"
  name     = "${var.gitlab_domain}"
  type     = "A"

  alias {
    name                   = "${aws_lb.gitlab.dns_name}"
    zone_id                = "${aws_lb.gitlab.zone_id}"
    evaluate_target_health = false
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "superset_internal" {
  count   = var.superset_on ? 1 : 0
  provider = "aws.route53"
  zone_id = "${data.aws_route53_zone.aws_route53_zone.zone_id}"
  name    = "${var.superset_internal_domain}"
  type    = "A"

  alias {
    name                   = "${aws_lb.superset[count.index].dns_name}"
    zone_id                = "${aws_lb.superset[count.index].zone_id}"
    evaluate_target_health = false
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "mlflow_internal" {
  count  = var.mlflow_on ? length(var.mlflow_instances) : 0
  provider = "aws.route53"
  zone_id = "${data.aws_route53_zone.aws_route53_zone.zone_id}"
  name    = "mlflow--${var.mlflow_instances_long[count.index]}--internal.${var.admin_domain}"
  type    = "A"
  ttl     = "60"
  records = [aws_lb.mlflow.*.subnet_mapping[count.index].*.private_ipv4_address[0]]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "mlflow_data_flow" {
  count  = var.mlflow_on ? length(var.mlflow_instances) : 0
  provider = "aws.route53"
  zone_id = "${data.aws_route53_zone.aws_route53_zone.zone_id}"
  name    = "mlflow--${var.mlflow_instances_long[count.index]}--data-flow.${var.admin_domain}"
  type    = "A"
  ttl     = "60"
  records = [aws_lb.mlflow_dataflow.*.subnet_mapping[count.index].*.private_ipv4_address[0]]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate" "superset_internal" {
  count             = var.superset_on ? 1 : 0
  domain_name       = "${aws_route53_record.superset_internal[count.index].name}"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate_validation" "superset_internal" {
  count           = var.superset_on ? 1 : 0
  certificate_arn = "${aws_acm_certificate.superset_internal[count.index].arn}"
}

# resource "aws_route53_record" "jupyterhub" {
#   zone_id = "${data.aws_route53_zone.aws_route53_zone.zone_id}"
#   name    = "${var.jupyterhub_domain}."
#   type    = "A"

#   alias {
#     name                   = "${aws_alb.jupyterhub.dns_name}"
#     zone_id                = "${aws_alb.jupyterhub.zone_id}"
#     evaluate_target_health = false
#   }

#   lifecycle {
#     create_before_destroy = true
#   }
# }

# resource "aws_acm_certificate" "jupyterhub" {
#   domain_name       = "${aws_route53_record.jupyterhub.name}"
#   validation_method = "DNS"

#   # subject_alternative_names = [
#   #   "${var.jupyterhub_secondary_domain}",
#   # ]

#   lifecycle {
#     create_before_destroy = true
#   }
# }

# resource "aws_acm_certificate_validation" "jupyterhub" {
#   certificate_arn = "${aws_acm_certificate.jupyterhub.arn}"
# }
