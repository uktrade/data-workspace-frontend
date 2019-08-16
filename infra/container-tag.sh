#!/bin/bash

set -e

QUERY=$(</dev/stdin)
CLUSTER_NAME=`echo $QUERY | jq --raw-output '.cluster_name'`
SERVICE_NAME=`echo $QUERY | jq --raw-output '.service_name'`
CONTAINER_NAME=`echo $QUERY | jq --raw-output '.container_name'`

TASK_DEFINITION=`aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region eu-west-2 | jq --raw-output .services[0].taskDefinition` 
IMAGE=`aws ecs describe-task-definition --task-definition $TASK_DEFINITION --region eu-west-2 | jq --raw-output '.taskDefinition.containerDefinitions[] | select(.name=="'${CONTAINER_NAME}'").image'`
TAG=`echo $IMAGE | sed -E 's/(.*):(.*)/\2/'`
echo "{\"tag\":\"${TAG}\"}"
