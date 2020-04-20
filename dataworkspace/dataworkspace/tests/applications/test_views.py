from unittest import mock

from django.urls import reverse

from dataworkspace.tests import factories


class TestDataVisualisationUICataloguePage:
    def test_successful_post_data(self, staff_client):
        visualisation = factories.VisualisationCatalogueItemFactory.create(
            short_description='old',
            published=False,
            visualisation_template__gitlab_project_id=1,
        )

        # Login to admin site
        staff_client.post(reverse('admin:index'), follow=True)

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

    def test_bad_post_data_no_short_description(self, staff_client):
        visualisation = factories.VisualisationCatalogueItemFactory.create(
            short_description='old',
            published=False,
            visualisation_template__gitlab_project_id=1,
        )

        # Login to admin site
        staff_client.post(reverse('admin:index'), follow=True)

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
