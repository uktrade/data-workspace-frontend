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

if [ -z "$2" ]; then
    echo "Usage: AWS_PROFILE=$AWS_PROFILE $0 <environment> <release-tag/commit-id>"
    exit 1
fi

if ! command -v ecs 2>&1 >/dev/null
then
    echo "The 'ecs' command could not be found - you might need to install it with 'pip install ecs-deploy'"
    exit 1
fi

if [[ -n $(git status -s) ]]; then
  echo "ERROR: Please commit untracked changes or revert before deploying"
  exit 1
fi

RELEASE_TAG="$2"

# make a note of users current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# checkout provided releast tag or commit id
git checkout $RELEASE_TAG --quiet

if [ "$1" == "dev" ]; then
  ENVIRONMENT=analysisworkspace-dev
elif [ "$1" == "staging" ]; then
  ENVIRONMENT=data-workspace-staging
elif [ "$1" == "prod" ]; then
  ENVIRONMENT=jupyterhub
else
  echo "ERROR: Argument not recognised - valid args are 'dev', 'staging' and 'prod'."
  git checkout $CURRENT_BRANCH --quiet
  exit 1
fi

# Verify that the user has provided a Release tag, not commit id, when the env is prod
# Get the current checked-out tag
CURRENT_TAG=$(git describe --tags --exact-match 2>/dev/null || echo "")
if [ "$1" == "prod" ] && [ "$CURRENT_TAG" == "" ]; then
    echo "ERROR: Please provide correct release tag and attempt again:"
    git checkout $CURRENT_BRANCH --quiet
    exit 1
fi

# Confirmation prompt
echo "You are about to deploy Data Workspace Frontend release tag $RELEASE_TAG to $1."
read -p "Are you sure you want to proceed? (yes/no): " CONFIRM

if [[ "$CONFIRM" != "yes" ]]; then
    echo "Deployment canceled."
    git checkout $CURRENT_BRANCH --quiet
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

# checkout user's branch
git checkout $CURRENT_BRANCH --quiet

echo "Triggering redeployment of webserver for $1 and release $RELEASE_TAG"
ecs deploy --timeout 500 $ENVIRONMENT $ENVIRONMENT-admin --tag $RELEASE_TAG

echo "Triggering redeployment of celery for $1 and release $RELEASE_TAG"
ecs deploy --timeout 500 $ENVIRONMENT $ENVIRONMENT-admin-celery --tag $RELEASE_TAG

echo "Deployment completed."
