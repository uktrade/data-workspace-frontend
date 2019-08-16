#!/bin/sh

set -e

python3 dnsmasq-set-dhcp.py

dnsmasq -k \
	--user=root \
	--no-hosts \
	--no-resolv \
	--log-queries \
	--log-facility=- \
	--server=/${AWS_ROUTE53_ZONE}/${DNS_SERVER} \
	--server=/amazonaws.com/${DNS_SERVER} \
	--server=/jupyterhub/${DNS_SERVER}
