from contextlib import contextmanager
from unittest import mock

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse

from dataworkspace.apps.applications.models import (
    VisualisationApproval,
    ApplicationInstance,
)
from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data


@contextmanager
def _visualisation_ui_gitlab_mocks():
    with mock.patch(
        'dataworkspace.apps.applications.views._visualisation_gitlab_project'
    ) as projects_mock, mock.patch(
        'dataworkspace.apps.applications.views._visualisation_branches'
    ) as branches_mock, mock.patch(
        'dataworkspace.apps.applications.views.gitlab_has_developer_access'
    ) as access_mock:
        access_mock.return_value = True
        projects_mock.return_value = {'id': 1, 'default_branch': 'master'}
        branches_mock.return_value = [
            {
                'name': 'master',
                'commit': {'committed_date': '2020-04-14T21:25:22.000+00:00'},
            }
        ]

        yield projects_mock, branches_mock, access_mock


class TestDataVisualisationUICataloguePage:
    def test_successful_post_data(self, staff_client):
        visualisation = factories.VisualisationCatalogueItemFactory.create(
            short_description='old',
            published=False,
            visualisation_template__gitlab_project_id=1,
        )

        # Login to admin site
        staff_client.post(reverse('admin:index'), follow=True)

        with _visualisation_ui_gitlab_mocks():
            response = staff_client.post(
                reverse(
                    'visualisations:catalogue-item',
                    args=(visualisation.visualisation_template.gitlab_project_id,),
                ),
                {"short_description": "summary"},
                follow=True,
            )

        visualisation.refresh_from_db()
        assert response.status_code == 200
        assert visualisation.short_description == "summary"

    @pytest.mark.parametrize(
        "start_type, post_type, expected_type",
        (
            ("REQUIRES_AUTHORIZATION", "", "REQUIRES_AUTHENTICATION"),
            (
                "REQUIRES_AUTHENTICATION",
                "REQUIRES_AUTHORIZATION",
                "REQUIRES_AUTHORIZATION",
            ),
        ),
    )
    def test_can_set_user_access_type(
        self, staff_client, start_type, post_type, expected_type
    ):
        log_count = LogEntry.objects.count()
        visualisation = factories.VisualisationCatalogueItemFactory.create(
            short_description="summary",
            published=False,
            visualisation_template__gitlab_project_id=1,
            visualisation_template__user_access_type=start_type,
        )

        # Login to admin site
        staff_client.post(reverse('admin:index'), follow=True)

        with _visualisation_ui_gitlab_mocks():
            response = staff_client.post(
                reverse(
                    'visualisations:catalogue-item',
                    args=(visualisation.visualisation_template.gitlab_project_id,),
                ),
                {"short_description": "summary", "user_access_type": post_type},
                follow=True,
            )

        visualisation.refresh_from_db()
        assert response.status_code == 200
        assert visualisation.visualisation_template.user_access_type == expected_type
        assert LogEntry.objects.count() == log_count + 1

    def test_bad_post_data_no_short_description(self, staff_client):
        visualisation = factories.VisualisationCatalogueItemFactory.create(
            short_description='old',
            published=False,
            visualisation_template__gitlab_project_id=1,
        )

        # Login to admin site
        staff_client.post(reverse('admin:index'), follow=True)

        with _visualisation_ui_gitlab_mocks():
            response = staff_client.post(
                reverse(
                    'visualisations:catalogue-item',
                    args=(visualisation.visualisation_template.gitlab_project_id,),
                ),
                {"summary": ""},
                follow=True,
            )

        visualisation.refresh_from_db()
        assert response.status_code == 400
        assert visualisation.short_description == "old"
        assert "The visualisation must have a summary" in response.content.decode(
            response.charset
        )


class TestDataVisualisationUIApprovalPage:
    @pytest.mark.django_db
    def test_approve_visualisation_successfully(self):
        develop_visualisations_permission = Permission.objects.get(
            codename='develop_visualisations',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = factories.UserFactory.create(
            username='visualisation.creator@test.com',
            is_staff=False,
            is_superuser=False,
        )
        user.user_permissions.add(develop_visualisations_permission)
        visualisation = factories.VisualisationCatalogueItemFactory.create(
            published=False, visualisation_template__gitlab_project_id=1
        )

        # Login to admin site
        client = Client(**get_http_sso_data(user))
        client.post(reverse('admin:index'), follow=True)

        with _visualisation_ui_gitlab_mocks():
            response = client.post(
                reverse(
                    'visualisations:approvals',
                    args=(visualisation.visualisation_template.gitlab_project_id,),
                ),
                {
                    "approved": "on",
                    "approver": user.id,
                    "visualisation": str(visualisation.visualisation_template.id),
                },
                follow=True,
            )

        assert response.status_code == 200
        assert len(VisualisationApproval.objects.all()) == 1

    @pytest.mark.django_db
    def test_bad_post_data_approved_box_not_checked(self):
        develop_visualisations_permission = Permission.objects.get(
            codename='develop_visualisations',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = factories.UserFactory.create(
            username='visualisation.creator@test.com',
            is_staff=False,
            is_superuser=False,
        )
        user.user_permissions.add(develop_visualisations_permission)
        visualisation = factories.VisualisationCatalogueItemFactory.create(
            published=False, visualisation_template__gitlab_project_id=1
        )

        # Login to admin site
        client = Client(**get_http_sso_data(user))
        client.post(reverse('admin:index'), follow=True)

        with _visualisation_ui_gitlab_mocks():
            response = client.post(
                reverse(
                    'visualisations:approvals',
                    args=(visualisation.visualisation_template.gitlab_project_id,),
                ),
                {
                    "approver": user.id,
                    "visualisation": str(visualisation.visualisation_template.id),
                },
                follow=True,
            )

        visualisation.refresh_from_db()
        assert response.status_code == 400
        assert (
            "You must confirm that you have reviewed this visualisation"
            in response.content.decode(response.charset)
        )
        assert len(VisualisationApproval.objects.all()) == 0

    @pytest.mark.django_db
    def test_unapprove_visualisation_successfully(self):
        develop_visualisations_permission = Permission.objects.get(
            codename='develop_visualisations',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = factories.UserFactory.create(
            username='visualisation.creator@test.com',
            is_staff=False,
            is_superuser=False,
        )
        user.user_permissions.add(develop_visualisations_permission)
        vis_cat_item = factories.VisualisationCatalogueItemFactory.create(
            published=False, visualisation_template__gitlab_project_id=1
        )
        approval = factories.VisualisationApprovalFactory.create(
            approved=True,
            approver=user,
            visualisation=vis_cat_item.visualisation_template,
        )

        # Login to admin site
        client = Client(**get_http_sso_data(user))
        client.post(reverse('admin:index'), follow=True)

        with _visualisation_ui_gitlab_mocks():
            response = client.post(
                reverse(
                    'visualisations:approvals',
                    args=(vis_cat_item.visualisation_template.gitlab_project_id,),
                ),
                {
                    "approver": user.id,
                    "visualisation": str(vis_cat_item.visualisation_template.id),
                },
                follow=True,
            )

        approval.refresh_from_db()
        assert response.status_code == 200
        assert len(VisualisationApproval.objects.all()) == 1
        assert approval.approved is False
