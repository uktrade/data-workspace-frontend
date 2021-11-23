# Sets the DHCP server in the VPC $VPC_ID to the current private IP address

import datetime
import hashlib
import hmac
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


def ec2_request(query):
    algorithm = "AWS4-HMAC-SHA256"

    now = datetime.datetime.utcnow()
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(b"").hexdigest()
    credential_scope = f"{datestamp}/{aws_region}/ec2/aws4_request"

    headers = {
        "host": aws_ec2_host,
        "x-amz-date": amzdate,
        "x-amz-security-token": security_token,
    }
    header_keys = sorted(headers.keys())
    signed_headers = ";".join(header_keys)

    def signature():
        def canonical_request():
            canonical_uri = "/"
            quoted_query = sorted(
                (urllib.parse.quote(key, safe="~"), urllib.parse.quote(value, safe="~"))
                for key, value in query.items()
            )
            canonical_querystring = "&".join(f"{key}={value}" for key, value in quoted_query)
            canonical_headers = "".join(f"{key}:{headers[key]}\n" for key in header_keys)

            return (
                f"POST\n{canonical_uri}\n{canonical_querystring}\n"
                + f"{canonical_headers}\n{signed_headers}\n{payload_hash}"
            )

        def sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        string_to_sign = (
            f"{algorithm}\n{amzdate}\n{credential_scope}\n"
            + hashlib.sha256(canonical_request().encode("utf-8")).hexdigest()
        )

        date_key = sign(("AWS4" + secret_access_key).encode("utf-8"), datestamp)
        region_key = sign(date_key, aws_region)
        service_key = sign(region_key, "ec2")
        request_key = sign(service_key, "aws4_request")
        return sign(request_key, string_to_sign).hex()

    final_headers = {
        **headers,
        "Authorization": f"{algorithm} Credential={access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature=" + signature(),
    }

    query_string = urllib.parse.urlencode(query)
    url = f"https://{aws_ec2_host}/?{query_string}"

    logger.debug("Making request to %s...", url)
    request = urllib.request.Request(url, headers=final_headers, data=b"", method="POST")
    try:
        with urllib.request.urlopen(request) as response:
            response_bytes = response.read()
    except urllib.error.HTTPError as exception:
        logger.debug(exception.read())
        raise

    logger.debug("Making request to %s... (done)", url)
    return response_bytes


print("Setting up logging...")
stdout_handler = logging.StreamHandler(sys.stdout)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(stdout_handler)
logger.debug("Setting up logging... (done)")

logger.debug("Parsing environment...")
aws_region = os.environ["AWS_REGION"]
logger.debug("Parsing environment... (aws_region: %s)", aws_region)
aws_ec2_host = os.environ["AWS_EC2_HOST"]
logger.debug("Parsing environment... (aws_ec2_host: %s)", aws_ec2_host)
vpc_id = os.environ["VPC_ID"]
logger.debug("Parsing environment... (vpc_id: %s)", vpc_id)
ip_address = os.environ["IP_ADDRESS"]
logger.debug("Parsing environment... (ip_address: %s)", ip_address)
aws_container_credentials_relative_uri = os.environ["AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"]
logger.debug(
    "Parsing environment... (aws_container_credentials_relative_uri: %s)",
    aws_container_credentials_relative_uri,
)
logger.debug("Parsing environment... (done)")

logger.debug("Finding credentials...")
with urllib.request.urlopen(
    f"http://169.254.170.2{aws_container_credentials_relative_uri}"
) as creds_response:
    creds = json.loads(creds_response.read().decode("utf-8"))
    access_key_id = creds["AccessKeyId"]
    secret_access_key = creds["SecretAccessKey"]
    security_token = creds["Token"]
logger.debug("Finding credentials... (done)")

logger.debug("Finding existing DHCP options...")
describe_vpc_response = ec2_request(
    {"Action": "DescribeVpcs", "Version": "2016-11-15", "VpcId.1": vpc_id}
)
existing_dhcp_options_id = re.search(
    b"<dhcpOptionsId>([^<]+)</dhcpOptionsId>", describe_vpc_response
)[1]
logger.debug(
    "Finding existing DHCP options... (existing_dhcp_options_id: %s)",
    existing_dhcp_options_id,
)
logger.debug("Finding existing DHCP options... (done)")

logger.debug("Creating DHCP options set...")
create_dhcp_options_response = ec2_request(
    {
        "Action": "CreateDhcpOptions",
        "Version": "2016-11-15",
        "DhcpConfiguration.1.Key": "domain-name-servers",
        "DhcpConfiguration.1.Value.1": ip_address,
    }
)
new_dhcp_options_id = re.search(
    b"<dhcpOptionsId>([^<]+)</dhcpOptionsId>", create_dhcp_options_response
)[1]
logger.debug("Creating DHCP options set... (new_dhcp_options_id:  %s)", new_dhcp_options_id)
logger.debug("Creating DHCP options set... (done)")

logger.debug("Tagging DHCP options set...")
create_dhcp_options_response = ec2_request(
    {
        "Action": "CreateTags",
        "Version": "2016-11-15",
        "ResourceId.1": new_dhcp_options_id.decode("ascii"),
        "Tag.1.Key": "Name",
        "Tag.1.Value": "jupyterhub-notebooks",
    }
)
logger.debug("Tagging DHCP options set... (done)")

logger.debug("Associating DHCP options...")
create_dhcp_options_response = ec2_request(
    {
        "Action": "AssociateDhcpOptions",
        "Version": "2016-11-15",
        "DhcpOptionsId": new_dhcp_options_id.decode("ascii"),
        "VpcId": vpc_id,
    }
)
logger.debug("Associating DHCP options... (done)")

logger.debug("Deleting existing DHCP options...")
create_dhcp_options_response = ec2_request(
    {
        "Action": "DeleteDhcpOptions",
        "Version": "2016-11-15",
        "DhcpOptionsId": existing_dhcp_options_id.decode("ascii"),
    }
)
logger.debug("Deleting existing DHCP options... (done)")
