from django.conf import settings
from django.urls import include, path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.explorer.views import (
    CreateQueryView,
    DeleteQueryView,
    DownloadFromQuerylogView,
    ListQueryLogView,
    ListQueryView,
    PlayQueryView,
    QueryLogResultView,
    QueryView,
    RunningQueryView,
    ShareQueryConfirmationView,
    ShareQueryView,
    QueryLogUpdateView,
    UserSchemaAccordian,
)

urlpatterns = [
    path("", login_required(PlayQueryView.as_view()), name="index"),
    path(
        "download/<int:querylog_id>",
        login_required(DownloadFromQuerylogView.as_view()),
        name="download_querylog",
    ),
    path(
        "query/<int:query_log_id>/",
        login_required(RunningQueryView.as_view()),
        name="running_query",
    ),
    path("queries/", login_required(ListQueryView.as_view()), name="list_queries"),
    path(
        "queries/create/",
        login_required(CreateQueryView.as_view()),
        name="query_create",
    ),
    path(
        "queries/<int:query_id>/",
        login_required(QueryView.as_view()),
        name="query_detail",
    ),
    path(
        "queries/<int:pk>/delete/",
        login_required(DeleteQueryView.as_view()),
        name="query_delete",
    ),
    path("logs/", login_required(ListQueryLogView.as_view()), name="explorer_logs"),
    path(
        "logs/<int:querylog_id>/results-json/",
        login_required(QueryLogResultView.as_view()),
        name="querylog_results",
    ),
    path(
        "queries/share/",
        login_required(ShareQueryView.as_view()),
        name="share_query",
    ),
    path(
        "queries/share/confirmation/<int:recipient_id>",
        login_required(ShareQueryConfirmationView.as_view()),
        name="share_query_confirmation",
    ),
    path(
        "query/<int:pk>/update/",
        login_required(QueryLogUpdateView.as_view()),
        name="update_query_state",
    ),
    path(
        "schema/",
        login_required(UserSchemaAccordian.as_view()),
        name="user_schema",
    ),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
