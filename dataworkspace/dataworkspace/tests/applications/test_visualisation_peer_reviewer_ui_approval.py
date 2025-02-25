from contextlib import contextmanager
from unittest import mock
import pytest
from bs4 import BeautifulSoup

from waffle.testutils import override_flag
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client, override_settings
from django.urls import reverse

from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.apps.applications.models import (
    ApplicationInstance,
    VisualisationApproval,
)

from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data


@contextmanager
def _visualisation_ui_gitlab_mocks(owner_access=True, peer_reviwer=False):
    with mock.patch(
        "dataworkspace.apps.applications.views._visualisation_gitlab_project"
    ) as projects_mock, mock.patch(
        "dataworkspace.apps.applications.views.gitlab_project_members"
    ) as project_members_mock, mock.patch(
        "dataworkspace.apps.applications.views.gitlab_is_project_owner"
    ) as owner_access_mock, mock.patch(
        "dataworkspace.apps.applications.views.gitlab_is_peer_reviewer"
    ) as peer_reviewer_access_mock, mock.patch(
        "dataworkspace.apps.applications.views._visualisation_branches"
    ) as branches_mock, mock.patch(
        "dataworkspace.apps.applications.views.gitlab_api_v4"
    ) as user_mock, mock.patch(
        "dataworkspace.apps.applications.views.gitlab_has_developer_access"
    ) as access_mock:
        access_mock.return_value = True
        projects_mock.return_value = {
            "id": 1,
            "default_branch": "master",
            "name": "test-gitlab-project",
            "description": "Some description",
        }
        branches_mock.return_value = [
            {
                "name": "master",
                "commit": {"committed_date": "2020-04-14T21:25:22.000+00:00"},
            }
        ]
        owner_access_mock.return_value = False
        peer_reviewer_access_mock.return_value = True
        project_members_mock.return_value = [
            {
                "id": 2,
                "name": "Ledia Luli",
                "username": "ledia.luli",
                "state": "active",
                "access_level": 30,
            }
        ]
        user_mock.return_value = [{"id": 1}]

        yield projects_mock, branches_mock, access_mock, owner_access_mock, user_mock, project_members_mock


class TestDataVisualisationOwnerUIApprovalPage:
    def assert_common_content(self, soup):
        peer_reviewer_header = soup.find_all("h2")
        peer_reviewer_header_text = peer_reviewer_header[0].contents
        peer_reviewer_body_text = header_two[1].contents
        generic_approval_list = soup.find_all(attrs={"data-test": "generic_approval_list"})
        owner_approval_list = soup.find_all(attrs={"data-test": "owner_approval_list"})

        assert "You're a peer reviewer for this visualisation" in first_header_two_text
        assert "Approve this visualisation" in second_header_two_text
        assert owner_approval_list
        assert generic_approval_list

    @override_flag(settings.THIRD_APPROVER, active=True)
    @pytest.mark.django_db
    def test_peer_reviewer_view_with_no_approvals(self):
        develop_visualisations_permission = Permission.objects.get(
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = factories.UserFactory.create(is_staff=False)
        user.user_permissions.add(develop_visualisations_permission)
        client = Client(**get_http_sso_data(user))
        with _visualisation_ui_gitlab_mocks():
            response = client.get(
                reverse("visualisations:approvals", args=(1,)),
                follow=True,
            )
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        approval_count_text = soup.find("p").contents

        self.assert_common_content(soup)
        assert "Currently 0 out of 3 have approved this visualisation." in approval_count_text
        assert response.status_code == 200

    @override_flag(settings.THIRD_APPROVER, active=True)
    @override_settings(GITLAB_FIXTURES=False)
    @pytest.mark.django_db
    def test_owner_view_with_one_peer_reviewer_approval(self):
        develop_visualisations_permission = Permission.objects.get(
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = factories.UserFactory.create(is_staff=False, is_superuser=False)
        user.user_permissions.add(develop_visualisations_permission)

        peer_reviewer = factories.UserFactory.create(
            first_name="Ledia", last_name="Luli", is_staff=False, is_superuser=False
        )

        v = factories.VisualisationTemplateFactory.create(gitlab_project_id=1)
        factories.VisualisationCatalogueItemFactory.create(
            name="test-gitlab-project",
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            visualisation_template=v,
        )
        factories.VisualisationApprovalFactory.create(
            approved=True, visualisation=v, approver=peer_reviewer
        )

        client = Client(**get_http_sso_data(user))
        with _visualisation_ui_gitlab_mocks():
            response = client.get(
                reverse("visualisations:approvals", args=(1,)),
                follow=True,
            )
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        approval_count_text = soup.find("p").contents

        self.assert_common_content(soup)
        assert "Currently 1 out of 3 have approved this visualisation." in approval_count_text
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_approve_visualisation_successfully(self):
        develop_visualisations_permission = Permission.objects.get(
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = factories.UserFactory.create(
            username="visualisation.creator@test.com",
            is_staff=False,
        )
        user.user_permissions.add(develop_visualisations_permission)
        visualisation = factories.VisualisationCatalogueItemFactory.create(
            published=False, visualisation_template__gitlab_project_id=1
        )

        # Login to admin site
        client = Client(**get_http_sso_data(user))
        client.post(reverse("admin:index"), follow=True)

        with _visualisation_ui_gitlab_mocks():
            response = client.post(
                reverse(
                    "visualisations:approvals",
                    args=(visualisation.visualisation_template.gitlab_project_id,),
                ),
                {
                    "action": "approve",
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
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = factories.UserFactory.create(
            username="visualisation.creator@test.com",
            is_staff=False,
            is_superuser=False,
        )
        user.user_permissions.add(develop_visualisations_permission)
        visualisation = factories.VisualisationCatalogueItemFactory.create(
            published=False, visualisation_template__gitlab_project_id=1
        )

        # Login to admin site
        client = Client(**get_http_sso_data(user))
        client.post(reverse("admin:index"), follow=True)

        with _visualisation_ui_gitlab_mocks():
            response = client.post(
                reverse(
                    "visualisations:approvals",
                    args=(visualisation.visualisation_template.gitlab_project_id,),
                ),
                {
                    "action": "approve",
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
    @override_settings(GITLAB_FIXTURES=False)
    def test_unapprove_visualisation_successfully(self):
        develop_visualisations_permission = Permission.objects.get(
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = factories.UserFactory.create(
            username="visualisation.creator@test.com",
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
        client.post(reverse("admin:index"), follow=True)

        with _visualisation_ui_gitlab_mocks():
            response = client.post(
                reverse(
                    "visualisations:approvals",
                    args=(vis_cat_item.visualisation_template.gitlab_project_id,),
                ),
                {
                    "action": "unapprove",
                    "approver": user.id,
                    "visualisation": str(vis_cat_item.visualisation_template.id),
                },
                follow=True,
            )

        approval.refresh_from_db()
        assert response.status_code == 200
        assert len(VisualisationApproval.objects.all()) == 1
        assert approval.approved is False
