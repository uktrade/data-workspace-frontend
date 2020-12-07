import json
from contextlib import contextmanager
from unittest import mock

import botocore
import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client, override_settings
from django.urls import reverse

from dataworkspace.apps.applications.models import (
    VisualisationApproval,
    ApplicationInstance,
    UserToolConfiguration,
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
        projects_mock.return_value = {
            'id': 1,
            'default_branch': 'master',
            'name': 'test-gitlab-project',
        }
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
            user_access_type=start_type,
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
                {"short_description": "summary", "user_access_type": post_type},
                follow=True,
            )

        visualisation.refresh_from_db()
        assert response.status_code == 200
        assert visualisation.user_access_type == expected_type
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


class TestQuickSightPollAndRedirect:
    @pytest.mark.django_db
    @override_settings(QUICKSIGHT_SSO_URL='https://sso.quicksight')
    def test_view_redirects_to_quicksight_sso_url(self):
        user = get_user_model().objects.create(is_staff=True, is_superuser=True)

        # Login to admin site
        client = Client(**get_http_sso_data(user))
        client.post(reverse('admin:index'), follow=True)

        with mock.patch(
            "dataworkspace.apps.applications.views.sync_quicksight_permissions"
        ):
            resp = client.get(reverse("applications:quicksight_redirect"), follow=False)

        assert resp['Location'] == 'https://sso.quicksight'

    @pytest.mark.django_db
    def test_view_starts_celery_polling_job(self):
        user = get_user_model().objects.create(is_staff=True, is_superuser=True)

        # Login to admin site
        client = Client(**get_http_sso_data(user))
        client.post(reverse('admin:index'), follow=True)

        with mock.patch(
            "dataworkspace.apps.applications.views.sync_quicksight_permissions"
        ) as sync_mock:
            client.get(reverse("applications:quicksight_redirect"), follow=False)

        assert sync_mock.delay.call_args_list == [
            mock.call(
                user_sso_ids_to_update=(user.profile.sso_id,),
                poll_for_user_creation=True,
            )
        ]


class TestToolsPage:
    @pytest.mark.django_db
    def test_user_with_no_size_config_shows_default_config(self):
        factories.ApplicationTemplateFactory()
        user = get_user_model().objects.create()

        client = Client(**get_http_sso_data(user))
        response = client.get(reverse('applications:tools'), follow=True)

        assert len(response.context['applications']) == 1
        assert (
            response.context['applications'][0]['tool_configuration'].size_config.name
            == 'Medium'
        )
        assert (
            response.context['applications'][0]['tool_configuration'].size_config.cpu
            == 1024
        )
        assert (
            response.context['applications'][0]['tool_configuration'].size_config.memory
            == 8192
        )

    @pytest.mark.django_db
    def test_user_with_size_config_shows_correct_config(self):
        tool = factories.ApplicationTemplateFactory()
        user = get_user_model().objects.create()
        UserToolConfiguration.objects.create(
            user=user, tool_template=tool, size=UserToolConfiguration.SIZE_EXTRA_LARGE
        )

        client = Client(**get_http_sso_data(user))
        response = client.get(reverse('applications:tools'), follow=True)

        assert len(response.context['applications']) == 1
        assert (
            response.context['applications'][0]['tool_configuration'].size_config.name
            == 'Extra Large'
        )
        assert (
            response.context['applications'][0]['tool_configuration'].size_config.cpu
            == 4096
        )
        assert (
            response.context['applications'][0]['tool_configuration'].size_config.memory
            == 30720
        )


class TestUserToolSizeConfigurationView:
    @pytest.mark.django_db
    def test_get_shows_all_size_choices(self):
        tool = factories.ApplicationTemplateFactory()
        user = get_user_model().objects.create()

        client = Client(**get_http_sso_data(user))
        response = client.get(
            reverse(
                'applications:configure_tool_size',
                kwargs={'tool_host_basename': tool.host_basename},
            ),
        )
        assert response.status_code == 200
        assert b'Small' in response.content
        assert b'Medium (default)' in response.content
        assert b'Large' in response.content
        assert b'Extra Large' in response.content

    @pytest.mark.django_db
    def test_post_creates_new_tool_configuration(self):
        tool = factories.ApplicationTemplateFactory(nice_name='RStudio')
        user = get_user_model().objects.create()

        assert not tool.user_tool_configuration.filter(user=user).first()

        client = Client(**get_http_sso_data(user))
        response = client.post(
            reverse(
                'applications:configure_tool_size',
                kwargs={'tool_host_basename': tool.host_basename},
            ),
            {'size': UserToolConfiguration.SIZE_EXTRA_LARGE},
            follow=True,
        )
        assert response.status_code == 200
        assert str(list(response.context['messages'])[0]) == 'Saved RStudio size'
        assert (
            tool.user_tool_configuration.filter(user=user).first().size
            == UserToolConfiguration.SIZE_EXTRA_LARGE
        )

    @pytest.mark.django_db
    def test_post_updates_existing_tool_configuration(self):
        tool = factories.ApplicationTemplateFactory(nice_name='RStudio')
        user = get_user_model().objects.create()
        UserToolConfiguration.objects.create(
            user=user, tool_template=tool, size=UserToolConfiguration.SIZE_EXTRA_LARGE
        )

        client = Client(**get_http_sso_data(user))
        response = client.post(
            reverse(
                'applications:configure_tool_size',
                kwargs={'tool_host_basename': tool.host_basename},
            ),
            {'size': UserToolConfiguration.SIZE_SMALL},
            follow=True,
        )
        assert response.status_code == 200
        assert str(list(response.context['messages'])[0]) == 'Saved RStudio size'
        assert (
            tool.user_tool_configuration.filter(user=user).first().size
            == UserToolConfiguration.SIZE_SMALL
        )


class TestVisualisationLogs:
    @pytest.mark.django_db
    def test_not_developer(self):
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

        client = Client(**get_http_sso_data(user))
        client.post(reverse('admin:index'), follow=True)

        with mock.patch(
            'dataworkspace.apps.applications.views.gitlab_has_developer_access'
        ) as access_mock:
            access_mock.return_value = False
            response = client.get(reverse('visualisations:logs', args=(1, 'xxx')))
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_commit_does_not_exist(self, mocker):
        application_template = factories.ApplicationTemplateFactory()
        factories.ApplicationInstanceFactory(
            application_template=application_template,
            commit_id='',
            spawner_application_template_options=json.dumps(
                {'CONTAINER_NAME': 'user-defined-container'}
            ),
            spawner_application_instance_id=json.dumps(
                {'task_arn': 'arn:test:vis/task-id/999'}
            ),
        )
        mock_get_application_template = mocker.patch(
            'dataworkspace.apps.applications.views._application_template'
        )
        mock_get_application_template.return_value = application_template
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
        client = Client(**get_http_sso_data(user))
        client.post(reverse('admin:index'), follow=True)
        with _visualisation_ui_gitlab_mocks():
            response = client.get(reverse('visualisations:logs', args=(1, 'xxx')))
            assert response.status_code == 200
            assert response.content == b'No logs were found for this visualisation.'

    @pytest.mark.django_db
    def test_no_events(self, mocker):
        application_template = factories.ApplicationTemplateFactory()
        factories.ApplicationInstanceFactory(
            application_template=application_template,
            commit_id='xxx',
            spawner_application_template_options=json.dumps(
                {'CONTAINER_NAME': 'user-defined-container'}
            ),
            spawner_application_instance_id=json.dumps(
                {'task_arn': 'arn:test:vis/task-id/999'}
            ),
        )
        mock_get_application_template = mocker.patch(
            'dataworkspace.apps.applications.views._application_template'
        )
        mock_get_application_template.return_value = application_template
        mock_boto = mocker.patch('dataworkspace.apps.applications.utils.boto3.client')
        mock_boto.return_value.get_log_events.side_effect = botocore.exceptions.ClientError(
            error_response={'Error': {'Code': 'ResourceNotFoundException'}},
            operation_name='get_log_events',
        )
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
        client = Client(**get_http_sso_data(user))
        client.post(reverse('admin:index'), follow=True)
        with _visualisation_ui_gitlab_mocks():
            response = client.get(reverse('visualisations:logs', args=(1, 'xxx')))
            assert response.status_code == 200
            assert response.content == b'No logs were found for this visualisation.'

    @pytest.mark.django_db
    def test_with_events(self, mocker):
        application_template = factories.ApplicationTemplateFactory()
        factories.ApplicationInstanceFactory(
            application_template=application_template,
            commit_id='xxx',
            spawner_application_template_options=json.dumps(
                {'CONTAINER_NAME': 'user-defined-container'}
            ),
            spawner_application_instance_id=json.dumps(
                {'task_arn': 'arn:test:vis/task-id/999'}
            ),
        )
        mock_get_application_template = mocker.patch(
            'dataworkspace.apps.applications.views._application_template'
        )
        mock_get_application_template.return_value = application_template
        mock_boto = mocker.patch('dataworkspace.apps.applications.utils.boto3.client')
        mock_boto.return_value.get_log_events.side_effect = [
            {
                'nextForwardToken': '12345',
                'events': [{'timestamp': 1605891793796, 'message': 'log message 1'}],
            },
            {'events': [{'timestamp': 1605891793797, 'message': 'log message 2'}]},
        ]
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

        client = Client(**get_http_sso_data(user))
        client.post(reverse('admin:index'), follow=True)

        with _visualisation_ui_gitlab_mocks():
            response = client.get(reverse('visualisations:logs', args=(1, 'xxx')))
            assert response.status_code == 200
            assert response.content == (
                b'2020-11-20 17:03:13.796000 - log message 1\n'
                b'2020-11-20 17:03:13.797000 - log message 2\n'
            )
