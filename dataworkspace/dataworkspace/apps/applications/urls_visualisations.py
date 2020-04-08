from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.applications.views import (
    visualisations_html_view,
    visualisation_branch_html_view,
    visualisation_users_with_access_html_view,
)

urlpatterns = [
    path('', login_required(visualisations_html_view), name='root'),
    path(
        '<str:gitlab_project_id>/branches/<str:branch_name>',
        login_required(visualisation_branch_html_view),
        name='branch',
    ),
    path(
        '<str:gitlab_project_id>/users',
        login_required(visualisation_users_with_access_html_view),
        name='users',
    ),
]
