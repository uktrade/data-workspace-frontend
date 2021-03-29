import pytest
import requests_mock
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.test import override_settings

from dataworkspace.apps.applications.gitlab import gitlab_has_developer_access
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.utils import (
    dataset_type_to_manage_unpublished_permission_codename,
)
from dataworkspace.tests import factories


class TestGitlabHasDeveloperAccess:
    @override_settings(
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}}
    )
    @pytest.mark.django_db
    def test_grants_manage_unpublished_visualisations_permission(self):
        user = factories.UserFactory.create(
            username='visualisation.creator@test.com',
            is_staff=False,
            is_superuser=False,
        )
        visualisation = factories.VisualisationCatalogueItemFactory.create(
            published=False, visualisation_template__gitlab_project_id=1
        )
        perm_codename = dataset_type_to_manage_unpublished_permission_codename(
            DataSetType.VISUALISATION
        )
        assert user.has_perm(perm_codename) is False

        with requests_mock.Mocker() as rmock:
            rmock.get(
                f'http://127.0.0.1:8007/api/v4/users?extern_uid={user.profile.sso_id}&provider=oauth2_generic',
                json=[{"id": 1}],
            )
            rmock.get(
                'http://127.0.0.1:8007/api/v4/projects/1/members/all?user_ids=1',
                json=[{"id": 1, "access_level": 50}],
            )
            has_access = gitlab_has_developer_access(
                user, visualisation.visualisation_template.gitlab_project_id
            )

        # Permissions are cached on the instance so we need to re-fetch it entirely - refresh_from_db insufficient.
        # https://docs.djangoproject.com/en/3.0/topics/auth/default/#permission-caching
        user = get_object_or_404(get_user_model(), pk=user.id)
        assert has_access is True
        assert user.has_perm(perm_codename) is True
