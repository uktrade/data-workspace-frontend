from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.applications.views import (
    UserToolSizeConfigurationView,
    application_running_html_view,
    application_spawning_html_view,
    data_explorer_redirect,
    quicksight_start_polling_sync_and_redirect,
    superset_redirect,
    tools_html_view,
)

urlpatterns = [
    path("", login_required(tools_html_view), name="tools"),
    path("<str:public_host>/spawning", login_required(application_spawning_html_view)),
    path("<str:public_host>/running", login_required(application_running_html_view)),
    path(
        "quicksight/redirect",
        login_required(quicksight_start_polling_sync_and_redirect),
        name="quicksight_redirect",
    ),
    path(
        "explorer/redirect",
        login_required(data_explorer_redirect),
        name="data_explorer_redirect",
    ),
    path(
        "superset/redirect",
        login_required(superset_redirect),
        name="superset_redirect",
    ),
    path(
        "configure-size/<str:tool_host_basename>/",
        login_required(UserToolSizeConfigurationView.as_view()),
        name="configure_tool_size",
    ),
]
