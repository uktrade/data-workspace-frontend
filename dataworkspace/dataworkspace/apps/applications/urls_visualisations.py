from django.urls import path

from dataworkspace.apps.accounts.utils import login_required

from dataworkspace.apps.applications.views import (
    metabase_visualisation_embed_view,
    visualisations_html_view,
    visualisation_branch_html_view,
    visualisation_users_give_access_html_view,
    visualisation_users_with_access_html_view,
    visualisation_catalogue_item_html_view,
    visualisation_approvals_html_view,
    visualisation_datasets_html_view,
    visualisation_publish_html_view,
)
from dataworkspace.apps.datasets.views import get_quicksight_dashboard

urlpatterns = [
    path('', login_required(visualisations_html_view), name='root'),
    path(
        'metabase/<int:dashboard_id>',
        login_required(metabase_visualisation_embed_view),
        name='metabase_visualisation_embed',
    ),
    path(
        'quicksight/<str:dashboard_id>',
        login_required(get_quicksight_dashboard),
        name='get-quicksight-dashboard',
    ),
    path(
        '<str:gitlab_project_id>/branches/<str:branch_name>',
        login_required(visualisation_branch_html_view),
        name='branch',
    ),
    path(
        '<str:gitlab_project_id>/users/give-access',
        login_required(visualisation_users_give_access_html_view),
        name='users-give-access',
    ),
    path(
        '<str:gitlab_project_id>/users/with-access',
        login_required(visualisation_users_with_access_html_view),
        name='users-with-access',
    ),
    path(
        '<str:gitlab_project_id>/catalogue-item',
        login_required(visualisation_catalogue_item_html_view),
        name='catalogue-item',
    ),
    path(
        '<str:gitlab_project_id>/approvals',
        login_required(visualisation_approvals_html_view),
        name='approvals',
    ),
    path(
        '<str:gitlab_project_id>/datasets',
        login_required(visualisation_datasets_html_view),
        name='datasets',
    ),
    path(
        '<str:gitlab_project_id>/publish',
        login_required(visualisation_publish_html_view),
        name='publish',
    ),
]
