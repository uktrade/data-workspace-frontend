from django.conf import settings
from django.urls import include, path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.explorer.views import (
    CreateQueryView,
    DeleteQueryView,
    DownloadFromSqlView,
    DownloadQueryView,
    ListQueryLogView,
    ListQueryView,
    PlayQueryView,
    QueryView,
)

urlpatterns = [
    path('', login_required(PlayQueryView.as_view()), name='index'),
    path(
        'download/', login_required(DownloadFromSqlView.as_view()), name='download_sql'
    ),
    path('queries/', login_required(ListQueryView.as_view()), name='list_queries'),
    path(
        'queries/create/',
        login_required(CreateQueryView.as_view()),
        name='query_create',
    ),
    path(
        'queries/<int:query_id>/',
        login_required(QueryView.as_view()),
        name='query_detail',
    ),
    path(
        'queries/<int:query_id>/download/',
        login_required(DownloadQueryView.as_view()),
        name='download_query',
    ),
    path(
        'queries/<int:pk>/delete/',
        login_required(DeleteQueryView.as_view()),
        name='query_delete',
    ),
    path('logs/', login_required(ListQueryLogView.as_view()), name='explorer_logs'),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
