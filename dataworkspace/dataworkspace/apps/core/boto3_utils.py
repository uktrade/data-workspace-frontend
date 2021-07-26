import logging

import boto3
from django.conf import settings

logger = logging.getLogger(__name__)


def get_boto3_s3_client():
    endpoint_url = settings.AWS_S3_ENDPOINT_URL
    logger.debug("AWS_S3_ENDPOINT_URL is %s", endpoint_url)
    client = boto3.client("s3", endpoint_url=endpoint_url)
    return client
