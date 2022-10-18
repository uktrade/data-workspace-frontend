#!/bin/bash
set -x
awslocal s3 mb s3://notebooks.dataworkspace.local
awslocal s3 mb s3://uploads.dataworkspace.local
set +x
