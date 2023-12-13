import logging
import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache

import waffle
import redis

from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.core.utils import (
    close_all_connections_if_not_in_atomic_block,
    get_s3_prefix,
)

from dataworkspace.cel import celery_app

logger = logging.getLogger("app")


def _collect_your_files_stats():
    start_time = time.time()
    client = get_s3_client()
    paginator = client.get_paginator("list_objects_v2")
    users_to_update = (
        get_user_model()
        .objects.filter(
            profile__sso_status="active",
        )
        .exclude(profile__first_login=None)
    )
    logger.info("your_files_stats: Found %d users to collect stats for", users_to_update.count())
    for user in users_to_update:
        logger.info("your_files_stats: Collecting stats for user %s", user.email)
        user_home_prefix = get_s3_prefix(str(user.profile.sso_id))
        total_size = 0
        total_files = 0
        num_large_files = 0
        for page in paginator.paginate(Bucket=settings.NOTEBOOKS_BUCKET, Prefix=user_home_prefix):
            for metadata in page.get("Contents", []):
                if metadata["Key"].startswith(f"{user_home_prefix}bigdata"):
                    continue
                total_size += metadata["Size"]
                total_files += 1
                if metadata["Size"] / 1e9 > 5:
                    num_large_files += 1

        if total_files == 0:
            logger.info(
                "your_files_stats: User %s has no files stored currently. Skipping", user.email
            )
            continue

        logger.info(
            "your_files_stats: User %s has %d files with a total size of %d bytes (%d > 5 GB)",
            user.email,
            total_files,
            total_size,
            num_large_files,
        )

    logger.info(
        "your_files_stats: Took %s seconds to gather stats for %d users",
        round(time.time() - start_time, 2),
        users_to_update.count(),
    )


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def collect_your_files_stats():
    if not waffle.switch_is_active("enable_your_files_stats_collection"):
        logger.info("your_files_stats: Skipping run as waffle switch is inactive")
        return
    try:
        with cache.lock("your_files_stats", blocking_timeout=0, timeout=1800):
            _collect_your_files_stats()
    except redis.exceptions.LockError:
        logger.info("your_files_stats: Unable to acquire lock to sync your files stats")
