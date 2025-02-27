import logging
from typing import Union

import requests
from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import transaction
from django.utils.encoding import force_str

from dataworkspace.apps.applications.fixtures.utils import get_fixture
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.utils import (
    dataset_type_to_manage_unpublished_permission_codename,
)

logger = logging.getLogger("app")

ECR_PROJECT_ID = settings.GITLAB_ECR_PROJECT_ID
RUNNING_PIPELINE_STATUSES = ("running", "pending")
SUCCESS_PIPELINE_STATUSES = ("success",)
DEVELOPER_ACCESS_LEVEL = 30
MAINTAINER_ACCESS_LEVEL = 40


def get_approver_type(
    gitlab_project_id: int, user_django: User = None, user_gitlab: dict = None
) -> Union[str, None]:
    if is_project_owner(user_gitlab, gitlab_project_id):
        return "Owner"
    elif is_dataworkspace_team_member(user_django, gitlab_project_id):
        return "Team Member"
    elif is_peer_reviewer(user_django, user_gitlab, gitlab_project_id):
        return "Peer Reviewer"


def gitlab_api_v4(method: str, path: str, params: tuple = ()):
    return gitlab_api_v4_with_status(method, path, params)[0]


def gitlab_api_v4_with_status(method: str, path: str, params: tuple = ()):
    if path.startswith("/"):
        path = path.lstrip("/")

    response = requests.request(
        method,
        f"{settings.GITLAB_URL}api/v4/{path}",
        params=params,
        headers={"PRIVATE-TOKEN": settings.GITLAB_TOKEN},
    )
    return response.json(), response.status_code


def gitlab_api_v4_ecr_pipeline_trigger(
    ecr_project_id,
    project_id,
    project_commit_id,
    ecr_repository_name,
    ecr_repository_tag,
):
    logger.debug("Starting pipeline: %s", ecr_project_id)
    pipeline = requests.post(
        f"{settings.GITLAB_URL}api/v4/projects/{ecr_project_id}/trigger/pipeline",
        data={
            "ref": "master",
            "token": settings.GITLAB_ECR_PROJECT_TRIGGER_TOKEN,
            "variables[PROJECT_ID]": project_id,
            "variables[PROJECT_COMMIT_ID]": project_commit_id,
            "variables[ECR_REPOSITORY_NAME]": ecr_repository_name,
            "variables[ECR_REPOSITORY_TAG]": ecr_repository_tag,
        },
    ).json()
    logger.debug("Started pipeline: %s", pipeline)
    return pipeline


def gitlab_has_developer_access(user: User, gitlab_project_id: int) -> bool:
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
    cache_key = f"gitlab-developer--{gitlab_project_id}--{user.id}"
    has_access = cache.get(cache_key)
    if has_access:
        return True

    gitlab_users, status = gitlab_api_v4_with_status(
        "GET",
        "/users",
        params=(("extern_uid", user.profile.sso_id), ("provider", "oauth2_generic")),
    )

    if status != 200:
        raise Exception(f"Unable to find GitLab user for {user.profile.sso_id}: received {status}")

    if len(gitlab_users) > 1:
        raise Exception(f"Too many GitLab users matching {user.profile.sso_id}")

    if not gitlab_users:
        return False

    gitlab_user = gitlab_users[0]
    gitlab_project_users = gitlab_api_v4(
        "GET",
        f"/projects/{gitlab_project_id}/members/all",
        params=(("user_ids", str(gitlab_user["id"])),),
    )

    has_access = any(
        (
            gitlab_project_user["id"] == gitlab_user["id"]
            and gitlab_project_user["access_level"] >= DEVELOPER_ACCESS_LEVEL
            for gitlab_project_user in gitlab_project_users
        )
    )

    if has_access:
        cache.set(cache_key, True, timeout=60 * 60)
        _ensure_user_has_manage_unpublish_perm(user)

    return has_access


def is_dataworkspace_team_member(user: User, gitlab_project_id: int) -> bool:
    return bool(user.is_superuser and gitlab_has_developer_access(user, gitlab_project_id))


def is_project_owner(user: User, gitlab_project_id: int) -> bool:
    current_gitlab_project_user = gitlab_project_member_by_id(user, gitlab_project_id)
    return bool(current_gitlab_project_user["access_level"] == MAINTAINER_ACCESS_LEVEL)


def is_peer_reviewer(user_django: User, user_gitlab: dict, gitlab_project_id: int) -> bool:
    if settings.GITLAB_FIXTURES:
        current_gitlab_project_user = gitlab_project_member_by_id(user_gitlab, gitlab_project_id)
        return bool(
            user_django.is_superuser is False
            and current_gitlab_project_user["access_level"] == DEVELOPER_ACCESS_LEVEL
        )
    else:
        return bool(
            user_django.is_superuser is False
            and gitlab_has_developer_access(user_gitlab, gitlab_project_id)
        )


def _ensure_user_has_manage_unpublish_perm(user: User):
    # Update the django permission controlling whether the user can preview unpublished visualisation catalogue pages.
    perm_codename = dataset_type_to_manage_unpublished_permission_codename(
        DataSetType.VISUALISATION
    )
    app_label, codename = perm_codename.split(".")
    perm = Permission.objects.get(content_type__app_label=app_label, codename=codename)

    if not user.has_perm(perm_codename):
        with transaction.atomic():
            user.user_permissions.add(perm)
            user.save()
            LogEntry.objects.log_action(
                user_id=user.pk,
                content_type_id=ContentType.objects.get_for_model(user).pk,
                object_id=user.pk,
                object_repr=force_str(user),
                action_flag=ADDITION,
                change_message="Added 'manage unpublished visualisations' permission",
            )


def gitlab_project_members(gitlab_project_id: int) -> list[dict]:
    if settings.GITLAB_FIXTURES:
        project_members = get_fixture("project_members_fixture.json")
    else:
        project_members = gitlab_api_v4("GET", f"/projects/{gitlab_project_id}/members/all")
    return project_members


def gitlab_project_member_by_id(gitlab_user: User, gitlab_project_id: int) -> dict:
    if settings.GITLAB_FIXTURES:
        (current_gitlab_project_user,) = get_fixture("project_member_fixture.json")
    else:
        (current_gitlab_project_user,) = gitlab_api_v4(
            "GET",
            f"/projects/{gitlab_project_id}/members/all",
            params=(("user_ids", str(gitlab_user["id"])),),
        )
    return current_gitlab_project_user
