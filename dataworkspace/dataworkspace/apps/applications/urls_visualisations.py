from django.urls import path

from dataworkspace.apps.accounts.utils import login_required

from dataworkspace.apps.applications.views import (
    visualisation_latest_log_GET,
    visualisation_link_html_view,
    visualisations_html_view,
    visualisation_users_give_access_html_view,
    visualisation_users_with_access_html_view,
    visualisation_catalogue_item_html_view,
    visualisation_approvals_html_view,
    visualisation_datasets_html_view,
    visualisation_publish_html_view,
    visualisation_branch_html_view,
)


urlpatterns = [
    path('', login_required(visualisations_html_view), name='root'),
    path(
        'link/<str:link_id>', login_required(visualisation_link_html_view), name='link'
    ),
    path(
        '<str:gitlab_project_id>/branches/<path:branch_name>',
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
    path(
        '<str:gitlab_project_id>/logs/<str:commit_id>',
        login_required(visualisation_latest_log_GET),
        name='logs',
    ),
]
