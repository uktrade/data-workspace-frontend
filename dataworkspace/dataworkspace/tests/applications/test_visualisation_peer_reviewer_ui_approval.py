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
def _visualisation_ui_gitlab_mocks(
    peer_reviewer_access=True,
    access_level=30,
    project_members=None,
    user=[{"id": 3, "name": "Ledia Luli"}],
):
    with mock.patch(
        "dataworkspace.apps.applications.views._visualisation_gitlab_project"
    ) as projects_mock, mock.patch(
        "dataworkspace.apps.applications.views.gitlab_project_members"
    ) as project_members_mock, mock.patch(
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
        user_mock.return_value = user
        approver_type.return_value = "peer reviewer"

        yield projects_mock, branches_mock, access_mock, user_mock, project_members_mock, approver_type


class TestDataVisualisationPeerReviewerUIApprovalPage:
    def assert_common_content(
        self, soup, already_approved_by_peer_reviewer=False, self_approval=False
    ):
        peer_reviewer_header = soup.find_all("h2")
        buttons = soup.find_all("button", attrs={"type": "submit"})
        peer_reviewer_body = soup.find_all("p")
        peer_reviewer_header_text = peer_reviewer_header[0].contents
        peer_reviewer_body_text = peer_reviewer_body[1].contents
        generic_approval_list = soup.find_all(attrs={"data-test": "generic_approval_list"})
        if already_approved_by_peer_reviewer is False:
            assert "You're a peer reviewer for this visualisation" in peer_reviewer_header_text
            if self_approval is False:
                assert generic_approval_list
                assert (
                    "Once you have peer reviewed this visualisation, you can approve it below."
                    in peer_reviewer_body_text
                )
                assert "Approve" in buttons[0].contents
            else:
                assert "Unapprove" in buttons[0].contents

        else:
            assert "This visualisation has been peer-reviewed" in peer_reviewer_header_text
            assert len(buttons) < 1

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

    @freeze_time("2025-01-01 01:01:01")
    @override_flag(settings.THIRD_APPROVER, active=True)
    @override_settings(GITLAB_FIXTURES=False)
    @pytest.mark.django_db
    def test_peer_reviewer_view_with_a_peer_reviewer_approval(self):
        develop_visualisations_permission = Permission.objects.get(
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = factories.UserFactory.create(is_staff=False, is_superuser=False)
        user.user_permissions.add(develop_visualisations_permission)

        peer_reviewer = factories.UserFactory.create(
            first_name="Bob", last_name="Burger", is_staff=False, is_superuser=False
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
        with _visualisation_ui_gitlab_mocks(
            access_level=30,
            project_members=[
                {
                    "id": 1,
                    "name": "Bob Burger",
                    "username": "bob.burger",
                    "state": "active",
                    "access_level": 30,
                }
            ],
        ):
            response = client.get(
                reverse("visualisations:approvals", args=(1,)),
                follow=True,
            )
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        already_approve_heading = soup.find("h2").contents
        assert "This visualisation has been peer-reviewed" in already_approve_heading
        approval_count_text = soup.find("p").contents
        approval_list = soup.find(attrs={"data-test": "approvals-list"})
        approval_list_items = approval_list.find_all("li")

        self.assert_common_content(soup, already_approved_by_peer_reviewer=True)
        assert len(approval_list_items) == 1
        assert (
            approval_list_items[0]
            .get_text()
            .startswith(
                "Bob Burger (peer reviewer) approved this visualisation on Jan. 1, 2025, 1:01 a.m."
            )
        )
        assert "Currently 1 out of 3 have approved this visualisation." in approval_count_text
        assert response.status_code == 200

    @freeze_time("2025-01-01 01:01:01")
    @override_flag(settings.THIRD_APPROVER, active=True)
    @override_settings(GITLAB_FIXTURES=False)
    @pytest.mark.django_db
    def test_peer_reviewer_view_with_a_self_approval(self):
        develop_visualisations_permission = Permission.objects.get(
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        peer_reviewer = factories.UserFactory.create(
            first_name="Bob", last_name="Burger", is_staff=False, is_superuser=False
        )
        peer_reviewer.user_permissions.add(develop_visualisations_permission)

        v = factories.VisualisationTemplateFactory.create(gitlab_project_id=1)
        factories.VisualisationCatalogueItemFactory.create(
            name="test-gitlab-project",
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            visualisation_template=v,
        )
        factories.VisualisationApprovalFactory.create(
            approved=True, visualisation=v, approver=peer_reviewer
        )

        client = Client(**get_http_sso_data(peer_reviewer))
        with _visualisation_ui_gitlab_mocks(
            access_level=30,
            project_members=[
                {
                    "id": 1,
                    "name": "Bob Burger",
                    "username": "bob.burger",
                    "state": "active",
                    "access_level": 30,
                }
            ],
            user=[
                {
                    "id": 1,
                    "name": "Bob Burger",
                    "username": "bob.burger",
                    "state": "active",
                    "access_level": 30,
                }
            ],
        ):
            response = client.get(
                reverse("visualisations:approvals", args=(1,)),
                follow=True,
            )
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        approval_count_text = soup.find("p").contents
        approval_list = soup.find(attrs={"data-test": "approvals-list"})
        approval_list_items = approval_list.find_all("li")

        self.assert_common_content(soup, self_approval=True)
        assert len(approval_list_items) == 1
        assert (
            approval_list_items[0]
            .get_text()
            .startswith("You approved this visualisation on Jan. 1, 2025, 1:01 a.m.")
        )
        assert "Currently 1 out of 3 have approved this visualisation." in approval_count_text
        assert response.status_code == 200

    @freeze_time("2025-01-01 01:01:01")
    @override_flag(settings.THIRD_APPROVER, active=True)
    @override_settings(GITLAB_FIXTURES=False)
    @pytest.mark.django_db
    def test_peer_reviewer_view_with_an_owner_approval(self):
        develop_visualisations_permission = Permission.objects.get(
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = factories.UserFactory.create(is_staff=False, is_superuser=False)
        user.user_permissions.add(develop_visualisations_permission)

        owner = factories.UserFactory.create(
            first_name="Ledia", last_name="Luli", is_staff=False, is_superuser=False
        )

        v = factories.VisualisationTemplateFactory.create(gitlab_project_id=1)
        factories.VisualisationCatalogueItemFactory.create(
            name="test-gitlab-project",
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            visualisation_template=v,
        )
        factories.VisualisationApprovalFactory.create(
            approved=True, visualisation=v, approver=owner
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
    def test_peer_reviewer_view_with_one_team_member_approval(self):
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
    def test_second_peer_reviewer_view_with_all_approvals(self):
        develop_visualisations_permission = Permission.objects.get(
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        second_peer_reviewer = factories.UserFactory.create(
            first_name="Ledia", last_name="Luli", is_staff=False, is_superuser=False
        )
        second_peer_reviewer.user_permissions.add(develop_visualisations_permission)

        team_member_reviewer = factories.UserFactory.create(
            first_name="Bob", last_name="Burger", is_staff=False, is_superuser=True
        )

        owner = factories.UserFactory.create(
            first_name="Tina", last_name="Belcher", is_staff=False, is_superuser=False
        )

        peer_reviewer = factories.UserFactory.create(
            first_name="Gene", last_name="Belcher", is_staff=False, is_superuser=False
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
            approved=True, visualisation=v, approver=owner
        )

        project_members = [
            {
                "id": 1,
                "name": "Bob Burger",
                "username": "bob.burger",
                "state": "active",
                "access_level": 30,
            },
            {
                "id": 2,
                "name": "Tina Belcher",
                "username": "tina.belcher",
                "state": "active",
                "access_level": 40,
            },
            {
                "id": 3,
                "name": "Gene Belcher",
                "username": "gene.belcher",
                "state": "active",
                "access_level": 30,
            },
        ]

        client = Client(**get_http_sso_data(second_peer_reviewer))
        with _visualisation_ui_gitlab_mocks(project_members=project_members):
            response = client.get(
                reverse("visualisations:approvals", args=(1,)),
                follow=True,
            )
        soup = BeautifulSoup(response.content.decode(response.charset), features="lxml")
        second_peer_reviewer_body = soup.find_all("p")
        second_peer_reviewer_approval_count_text_one = second_peer_reviewer_body[1].contents
        second_peer_reviewer_approval_count_text_two = second_peer_reviewer_body[2].contents
        second_peer_reviewer_headers = soup.find_all("h2")
        second_peer_reviewer_header = second_peer_reviewer_headers[0].contents
        approval_list = soup.find(attrs={"data-test": "approvals-list"})
        approval_list_items = approval_list.find_all("li")

        assert len(approval_list_items) == 3
        assert (
            approval_list_items[0]
            .get_text()
            .startswith(
                "Tina Belcher (owner) approved this visualisation on Jan. 1, 2025, 1:01 a.m."
            )
        )
        assert (
            approval_list_items[1]
            .get_text()
            .startswith(
                "Gene Belcher (peer reviewer) approved this visualisation on Jan. 1, 2025, 1:01 a.m."
            )
        )
        assert (
            approval_list_items[2]
            .get_text()
            .startswith(
                "A member of the Data Workspace team approved this visualisation on Jan. 1, 2025, 1:01 a.m."
            )
        )
        assert "This visualisation has been peer-reviewed" in second_peer_reviewer_header
        assert (
            "This visualisation has already been peer reviewed by someone else. Their name is listed above."
            in second_peer_reviewer_approval_count_text_one
        )
        assert (
            "Only three approvals are needed: the owner, a peer reviewer and a Data Workspace team member."
            in second_peer_reviewer_approval_count_text_two
        )

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
