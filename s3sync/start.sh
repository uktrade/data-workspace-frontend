#!/bin/sh

set -e

# Path-style even though it's deprecated. The bucket names have dots in, and
# at the time of writing the host-style certs returned by AWS are wildcards
# and don't support dots in the bucket name
# Excluding .checkpoints from remote to not have issues with jupyters3
# .checkpoints folders that are subfolders of files in S3. Other dot files
# already on the remote _are_ synced to local
# Exclude .__mobius3_flush__ files locally, since there is a suspected bug
# in mobius3 where they can end up being uploaded
mobius3 \
    /home/s3sync/data \
    ${S3_BUCKET} \
    https://s3-${S3_REGION}.amazonaws.com/{}/ \
    ${S3_REGION} \
    --prefix ${S3_PREFIX} \
    --log-level INFO \
    --credentials-source ecs-container-endpoint \
    --exclude-remote '(.*(/|^)\.checkpoints/)|(.*(/|^)bigdata/.*)' \
    --exclude-local '(.*(/|^)\.__mobius3_flush__.*)|(.*(/|^)bigdata/.*)' \
    --upload-on-create '^.*/\.git/.*$'
