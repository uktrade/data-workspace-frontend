#!/bin/bash

# Follows the Terraform External Program Protocol to extract the current
# Docker tag in the Task Defintion. Used so `terraform apply` does not
# conflict with deployments from Jenkins that change the Docker tag

set -e

QUERY=$(</dev/stdin)
TASK_FAMILY=`echo $QUERY | jq --raw-output '.task_family'`
CONTAINER_NAME=`echo $QUERY | jq --raw-output '.container_name'`

IMAGE=`aws ecs describe-task-definition --task-definition $TASK_FAMILY --region eu-west-2 | jq --raw-output '.taskDefinition.containerDefinitions[] | select(.name=="'${CONTAINER_NAME}'").image'`
TAG=`echo $IMAGE | sed -E 's/(.*):(.*)/\2/'`
echo "{\"tag\":\"${TAG}\"}"
