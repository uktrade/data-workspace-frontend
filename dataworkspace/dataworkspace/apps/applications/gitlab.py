import logging
import requests

from django.conf import settings


logger = logging.getLogger('app')

ECR_PROJECT_ID = settings.GITLAB_ECR_PROJECT_ID
RUNNING_PIPELINE_STATUSES = ('running', 'pending')
SUCCESS_PIPELINE_STATUSES = ('success',)
DEVELOPER_ACCESS_LEVEL = '30'


def gitlab_api_v4(method, path, params=()):
    return gitlab_api_v4_with_status(method, path, params)[0]


def gitlab_api_v4_with_status(method, path, params=()):
    response = requests.request(
        method,
        f'{settings.GITLAB_URL}api/v4/{path}',
        params=params,
        headers={'PRIVATE-TOKEN': settings.GITLAB_TOKEN},
    )
    return response.json(), response.status_code


def gitlab_api_v4_ecr_pipeline_trigger(
    ecr_project_id,
    project_id,
    project_commit_id,
    ecr_repository_name,
    ecr_repository_tag,
):
    logger.debug('Starting pipeline: %s', ecr_project_id)
    pipeline = requests.post(
        f'{settings.GITLAB_URL}api/v4/projects/{ecr_project_id}/trigger/pipeline',
        data={
            'ref': 'master',
            'token': settings.GITLAB_ECR_PROJECT_TRIGGER_TOKEN,
            'variables[PROJECT_ID]': project_id,
            'variables[PROJECT_COMMIT_ID]': project_commit_id,
            'variables[ECR_REPOSITORY_NAME]': ecr_repository_name,
            'variables[ECR_REPOSITORY_TAG]': ecr_repository_tag,
        },
    ).json()
    logger.debug('Started pipeline: %s', pipeline)
    return pipeline
