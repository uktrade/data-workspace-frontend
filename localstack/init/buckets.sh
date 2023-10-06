#!/bin/bash
set -x
awslocal s3 mb s3://notebooks.dataworkspace.local
awslocal s3 mb s3://uploads.dataworkspace.local
# Multipart file uploads from Your Files in the browser require ETag to be
# exposed but by default it's not, so we add a CORS config to expose it
awslocal s3api put-bucket-cors --bucket notebooks.dataworkspace.local --cors-configuration file:///docker-entrypoint-initaws.d/s3-cors.json
set +x
