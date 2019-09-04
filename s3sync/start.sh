#!/bin/sh

set -e

# Path-style even though it's deprecated. The bucket names have dots in, and
# at the time of writing the host-style certs returned by AWS are wildcards
# and don't support dots in the bucket name
# Excluding .checkpoints to not have issues with jupyters3 .checkpoints
# folders that are subfolders of files in S3
# Excluding all all dot files locally since they are a) probably unnecessary
# and b) contains a sqlite database for temporary data
mobius3 \
    /home/s3sync/data \
    https://s3-${S3_REGION}.amazonaws.com/${S3_BUCKET}/ \
    ${S3_REGION} \
    --prefix ${S3_PREFIX} \
    --log-level INFO \
    --credentials-source ecs-container-endpoint \
    --exclude-remote '(.*(/|^)\.checkpoints/)|(.*(/|^)bigdata/.*)' \
    --exclude-local '(.*/\..*)|(.*(/|^)bigdata/.*)'
