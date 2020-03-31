from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.api_v1.views import (
    application_api_view,
    applications_api_view,
    aws_credentials_api_view,
    table_api_schema_view,
    table_api_rows_view,
)


urlpatterns = [
    path(
        'application/<str:public_host>',
        csrf_exempt(login_required(application_api_view)),
        name='application-detail',
    ),
    path('application', csrf_exempt(applications_api_view), name='application-list'),
    path(
        'aws_credentials',
        csrf_exempt(login_required(aws_credentials_api_view)),
        name='aws-credentials',
    ),
    path(
        'table/<str:table_id>/schema',
        csrf_exempt(login_required(table_api_schema_view)),
        name='table-scheme',
    ),
    path(
        'table/<str:table_id>/rows',
        csrf_exempt(login_required(table_api_rows_view)),
        name='table-rows',
    ),
    path(
        'dataset/',
        include(
            ('dataworkspace.apps.api_v1.datasets.urls', 'dataset'), namespace='dataset'
        ),
    ),
    path(
        'reference-dataset/',
        include(
            ('dataworkspace.apps.api_v1.datasets.urls', 'reference-dataset'),
            namespace='reference-dataset',
        ),
    ),
    path(
        'eventlog/',
        include(
            ('dataworkspace.apps.api_v1.eventlog.urls', 'eventlog'),
            namespace='eventlog',
        ),
    ),
    path(
        'account/',
        include(
            ('dataworkspace.apps.api_v1.accounts.urls', 'account'), namespace='account'
        ),
    ),
    path(
        'application-instance/',
        include(
            ('dataworkspace.apps.api_v1.applications.urls', 'application-instance'),
            namespace='application-instance',
        ),
    ),
]
