#!/usr/bin/env bash
# requirements:
# - login to aws

set -e

if [[ -z "${AWS_PROFILE}" ]]; then
  echo "You must set the AWS_PROFILE environment variable to the name of your profile. Often this is data-infrastructure-prod."
  exit 1
else
  echo "Using AWS profile $AWS_PROFILE"
fi

if [ -z "$1" ]; then
    echo "Usage: AWS_PROFILE=$AWS_PROFILE $0 <environment> [release-tag]"
    exit 1
fi

RELEASE_TAG="$2"

# If the environment is "prod", the release tag is mandatory
if [ "$1" == "prod" ] && [ -z "$RELEASE_TAG" ]; then
    echo "Error: Release tag is required for production deployments."
    echo "Usage: $0 prod <release-tag>"
    exit 1
fi

# Get the current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# If no release tag is provided (non-prod), use the branch name
if [ -z "$RELEASE_TAG" ]; then
    if [ "$1" == "prod" ]; then
        echo "Error: Release tag is required for production deployments."
        echo "Usage: $0 prod <release-tag>"
        exit 1
    fi
    RELEASE_TAG="$CURRENT_BRANCH"
    echo "Using branch name as tag: $RELEASE_TAG"
fi

# Get the current checked-out tag
CURRENT_TAG=$(git describe --tags --exact-match 2>/dev/null || echo "")

# Verify that the user has checked out the correct tag (only for prod)
if [ "$1" == "prod" ] && [ "$CURRENT_TAG" != "$RELEASE_TAG" ]; then
    echo "Error: You are not on the correct release tag."
    echo "   Expected: $RELEASE_TAG"
    echo "   Current:  ${CURRENT_TAG:-'(no tag found)'}"
    echo "   Please checkout the correct tag first:"
    echo "   git checkout $RELEASE_TAG"
    exit 1
fi

if [ "$1" == "dev" ]; then
  ENVIRONMENT=analysisworkspace-dev
elif [ "$1" == "staging" ]; then
  ENVIRONMENT=data-workspace-staging
elif [ "$1" == "prod" ]; then
  ENVIRONMENT=jupyterhub
else
  echo "Argument not recognised - valid args are 'dev', 'staging' and 'prod'."
  exit 1
fi

# Confirmation prompt
echo "You are about to deploy Data Workspace Frontend release tag $RELEASE_TAG to $1."
read -p "Are you sure you want to proceed? (yes/no): " CONFIRM

if [[ "$CONFIRM" != "yes" ]]; then
    echo "Deployment canceled."
    exit 1
fi

echo "Deploying $RELEASE_TAG to $1"

echo "Logging into ECR"
aws ecr get-login-password --region eu-west-2 | docker login --username AWS --password-stdin 165562107270.dkr.ecr.eu-west-2.amazonaws.com

echo "Building Docker image"
if [ "$(uname)" == "Darwin" ]; then
  DOCKER_DEFAULT_PLATFORM=linux/amd64 docker build -t admin:$RELEASE_TAG -f Dockerfile .
else
  docker build -t admin:$RELEASE_TAG -f Dockerfile .
fi

echo "Pushing docker image to ECR for $1 and release $RELEASE_TAG"
docker tag admin:$RELEASE_TAG 165562107270.dkr.ecr.eu-west-2.amazonaws.com/$ENVIRONMENT-admin:$RELEASE_TAG
docker push 165562107270.dkr.ecr.eu-west-2.amazonaws.com/$ENVIRONMENT-admin:$RELEASE_TAG

echo "Triggering redeployment of webserver for $1 and release $RELEASE_TAG"
aws ecs update-service --cluster $ENVIRONMENT --service $ENVIRONMENT-admin --force-new-deployment > /dev/null

echo "Triggering redeployment of celery for $1 and release $RELEASE_TAG"
aws ecs update-service --cluster $ENVIRONMENT --service $ENVIRONMENT-admin-celery --force-new-deployment > /dev/null

echo "Deployment completed. Note that the redeployment is asynchronous, and will take a few minutes to complete."
