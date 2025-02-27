from contextlib import contextmanager
from unittest import mock

import pytest
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client, override_settings
from django.urls import reverse
from freezegun import freeze_time
from waffle.testutils import override_flag

from dataworkspace.apps.applications.models import ApplicationInstance, VisualisationApproval
from dataworkspace.apps.datasets.constants import UserAccessType
from dataworkspace.tests import factories
from dataworkspace.tests.common import get_http_sso_data


@contextmanager
def _visualisation_ui_gitlab_mocks(owner_access=True, access_level=30, project_members=None):
    with mock.patch(
        "dataworkspace.apps.applications.views._visualisation_gitlab_project"
    ) as projects_mock, mock.patch(
        "dataworkspace.apps.applications.views.gitlab_project_members"
    ) as project_members_mock, mock.patch(
        "dataworkspace.apps.applications.gitlab.is_project_owner"
    ) as owner_access_mock, mock.patch(
        "dataworkspace.apps.applications.views._visualisation_branches"
    ) as branches_mock, mock.patch(
        "dataworkspace.apps.applications.views.gitlab_api_v4"
    ) as user_mock, mock.patch(
        "dataworkspace.apps.applications.views.gitlab_has_developer_access"
    ) as access_mock, mock.patch(
        "dataworkspace.apps.applications.views.get_approver_type"
    ) as approver_type:
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
        owner_access_mock.return_value = owner_access
        project_members_mock.return_value = (
            project_members
            if project_members
            else [
                {
                    "id": 2,
                    "name": "Ledia Luli",
                    "username": "ledia.luli",
                    "state": "active",
                    "access_level": access_level,
                }
            ]
        )
        user_mock.return_value = [{"id": 1}]
        approver_type.return_value = "owner"

        yield projects_mock, branches_mock, access_mock, owner_access_mock, user_mock, project_members_mock, approver_type


class TestDataVisualisationOwnerUIApprovalPage:
    def assert_common_content(self, soup):
        header_two = soup.find_all("h2")
        first_header_two_text = header_two[0].contents
        second_header_two_text = header_two[1].contents
        generic_approval_list = soup.find_all(attrs={"data-test": "generic_approval_list"})
        owner_approval_list = soup.find_all(attrs={"data-test": "owner_approval_list"})

        assert "Who needs to approve this visualisation" in first_header_two_text
        assert "Approve this visualisation" in second_header_two_text
        assert owner_approval_list
        assert generic_approval_list

    @override_flag(settings.THIRD_APPROVER, active=True)
    @pytest.mark.django_db
    def test_owner_view_with_no_approvals(self):
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

    @freeze_time("2025-01-01 01:01:01")
    @override_flag(settings.THIRD_APPROVER, active=True)
    @override_settings(GITLAB_FIXTURES=False)
    @pytest.mark.django_db
    def test_owner_view_with_owner_approval(self):
        develop_visualisations_permission = Permission.objects.get(
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = factories.UserFactory.create(
            first_name="Ledia", last_name="Luli", is_staff=False, is_superuser=False
        )
        user.user_permissions.add(develop_visualisations_permission)

        v = factories.VisualisationTemplateFactory.create(gitlab_project_id=1)
        factories.VisualisationCatalogueItemFactory.create(
            name="test-gitlab-project",
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            visualisation_template=v,
        )
        factories.VisualisationApprovalFactory.create(
            approved=True, visualisation=v, approver=user
        )

        client = Client(**get_http_sso_data(user))
        with _visualisation_ui_gitlab_mocks(access_level=40):
            response = client.get(
                reverse("visualisations:approvals", args=(1,)),
                follow=True,
            )
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        approval_count_text = soup.find("p").contents
        approval_list = soup.find(attrs={"data-test": "approvals-list"})
        approval_list_items = approval_list.find_all("li")

        self.assert_common_content(soup)
        assert len(approval_list_items) == 1
        assert (
            approval_list_items[0]
            .get_text()
            .startswith(
                "Ledia Luli (owner) approved this visualisation on Jan. 1, 2025, 1:01 a.m."
            )
        )
        assert "Currently 1 out of 3 have approved this visualisation." in approval_count_text
        assert response.status_code == 200

    @freeze_time("2025-01-01 01:01:01")
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
        approval_list = soup.find(attrs={"data-test": "approvals-list"})
        approval_list_items = approval_list.find_all("li")

        self.assert_common_content(soup)
        assert len(approval_list_items) == 1
        assert (
            approval_list_items[0]
            .get_text()
            .startswith(
                "Ledia Luli (peer reviewer) approved this visualisation on Jan. 1, 2025, 1:01 a.m."
            )
        )
        assert "Currently 1 out of 3 have approved this visualisation." in approval_count_text
        assert response.status_code == 200

    @freeze_time("2025-01-01 01:01:01")
    @override_flag(settings.THIRD_APPROVER, active=True)
    @override_settings(GITLAB_FIXTURES=False)
    @pytest.mark.django_db
    def test_owner_view_with_one_team_member_approval(self):
        develop_visualisations_permission = Permission.objects.get(
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = factories.UserFactory.create(is_staff=False, is_superuser=False)
        user.user_permissions.add(develop_visualisations_permission)

        team_member_reviewer = factories.UserFactory.create(
            first_name="Ledia", last_name="Luli", is_staff=False, is_superuser=True
        )

        v = factories.VisualisationTemplateFactory.create(gitlab_project_id=1)
        factories.VisualisationCatalogueItemFactory.create(
            name="test-gitlab-project",
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            visualisation_template=v,
        )
        factories.VisualisationApprovalFactory.create(
            approved=True, visualisation=v, approver=team_member_reviewer
        )

        client = Client(**get_http_sso_data(user))
        with _visualisation_ui_gitlab_mocks():
            response = client.get(
                reverse("visualisations:approvals", args=(1,)),
                follow=True,
            )
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        approval_count_text = soup.find("p").contents
        approval_list = soup.find(attrs={"data-test": "approvals-list"})
        approval_list_items = approval_list.find_all("li")

        self.assert_common_content(soup)
        assert len(approval_list_items) == 1
        assert (
            approval_list_items[0]
            .get_text()
            .startswith(
                "A member of the Data Workspace team approved this visualisation on Jan. 1, 2025, 1:01 a.m."
            )
        )
        assert "Currently 1 out of 3 have approved this visualisation." in approval_count_text
        assert response.status_code == 200

    @freeze_time("2025-01-01 01:01:01")
    @override_flag(settings.THIRD_APPROVER, active=True)
    @override_settings(GITLAB_FIXTURES=False)
    @pytest.mark.django_db
    def test_owner_view_with_all_approvals(self):
        develop_visualisations_permission = Permission.objects.get(
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = factories.UserFactory.create(
            first_name="Ledia", last_name="Luli", is_staff=False, is_superuser=False
        )
        user.user_permissions.add(develop_visualisations_permission)

        team_member_reviewer = factories.UserFactory.create(
            first_name="James", last_name="Robinson", is_staff=False, is_superuser=True
        )

        peer_reviewer = factories.UserFactory.create(
            first_name="Ian", last_name="Leggett", is_staff=False, is_superuser=False
        )

        v = factories.VisualisationTemplateFactory.create(gitlab_project_id=1)
        factories.VisualisationCatalogueItemFactory.create(
            name="test-gitlab-project",
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            visualisation_template=v,
        )
        factories.VisualisationApprovalFactory.create(
            approved=True, visualisation=v, approver=team_member_reviewer
        )
        factories.VisualisationApprovalFactory.create(
            approved=True, visualisation=v, approver=peer_reviewer
        )
        factories.VisualisationApprovalFactory.create(
            approved=True, visualisation=v, approver=user
        )

        project_members = [
            {
                "id": 1,
                "name": "Ian Leggett",
                "username": "ian.leggett",
                "state": "active",
                "access_level": 30,
            },
            {
                "id": 2,
                "name": "Ledia Luli",
                "username": "ledia.luli",
                "state": "active",
                "access_level": 40,
            },
            {
                "id": 3,
                "name": "James Robinson",
                "username": "james.robinson",
                "state": "active",
                "access_level": 30,
            },
        ]

        client = Client(**get_http_sso_data(user))
        with _visualisation_ui_gitlab_mocks(project_members=project_members):
            response = client.get(
                reverse("visualisations:approvals", args=(1,)),
                follow=True,
            )
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        approval_count_text = soup.find("p").contents
        approval_list = soup.find(attrs={"data-test": "approvals-list"})
        approval_list_items = approval_list.find_all("li")

        self.assert_common_content(soup)
        assert len(approval_list_items) == 3
        assert (
            approval_list_items[0]
            .get_text()
            .startswith(
                "Ledia Luli (owner) approved this visualisation on Jan. 1, 2025, 1:01 a.m."
            )
        )
        assert (
            approval_list_items[1]
            .get_text()
            .startswith(
                "Ian Leggett (peer reviewer) approved this visualisation on Jan. 1, 2025, 1:01 a.m."
            )
        )
        assert (
            approval_list_items[2]
            .get_text()
            .startswith("A member of the Data Workspace team approved this visualisation on")
        )
        assert "Currently 3 out of 3 have approved this visualisation." in approval_count_text
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
