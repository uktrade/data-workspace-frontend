import logging
import requests

from django.conf import settings
from django.core.cache import cache


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


def gitlab_has_developer_access(user, gitlab_project_id):
    # Having developer access to a project is cached to mitigate slow requests
    # to GitLab. _Not_ having developer access to not cached to allow granting
    # of access to have an immediate effect
    #
    # This would still mean that once expired, the user would still have a
    # slower request. This could be avoided by a background job that polls
    # for permissions changes before they expire. Leaving that until there is
    # more evidence that a) the semantic behaviour is indeed what we want, and
    # b) the performance is slow enough to justify that.
    #
    # The caching is suspected to be particularly important for visualisation
    # previews: they can have multiple HTTP requests that each need to be
    # checked for authorisation. This includes websocket requests that are
    # expected to behave in almost real time. Websocket connections often drop
    # out, so even once the visualisation is loaded, a reconnection, which
    # would then need another authorisation check, should be speedy.
    cache_key = f'gitlab-developer--{gitlab_project_id}--{user.id}'
    has_access = cache.get(cache_key)
    if has_access:
        return True

    gitlab_users, status = gitlab_api_v4_with_status(
        'GET',
        f'/users',
        params=(('extern_uid', user.profile.sso_id), ('provider', 'oauth2_generic')),
    )

    if status != 200:
        raise Exception(
            f'Unable to find GitLab user for {user.profile.sso_id}: received {status}'
        )

    if len(gitlab_users) > 1:
        raise Exception(f'Too many GitLab users matching {user.profile.sso_id}')

    if not gitlab_users:
        return False

    gitlab_user = gitlab_users[0]
    gitlab_project_users = gitlab_api_v4(
        'GET',
        f'/projects/{gitlab_project_id}/members/all',
        params=(('user_ids', str(gitlab_user['id'])),),
    )

    has_access = any(
        (
            gitlab_project_user['id'] == gitlab_user['id']
            and gitlab_project_user['access_level'] >= int(DEVELOPER_ACCESS_LEVEL)
            for gitlab_project_user in gitlab_project_users
        )
    )
    if has_access:
        cache.set(cache_key, True, timeout=60 * 60)

    return has_access
