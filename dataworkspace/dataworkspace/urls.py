import logging

from django.contrib import admin
from django.urls import path, include

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.catalogue.views import root_view
from dataworkspace.apps.core.views import (
    public_error_403_html_view, public_error_404_html_view,
    public_error_500_html_view, healthcheck_view, SupportView, table_data_view
)
from dataworkspace.apps.appstream.views import (
    appstream_view,
    appstream_admin_view,
    appstream_restart,
    appstream_fleetstatus,
)

logger = logging.getLogger('app')

admin.autodiscover()
admin.site.site_header = 'Data Workspace'
admin.site.login = login_required(admin.site.login)

urlpatterns = [
    path('', login_required(root_view), name='root'),
    path('error_403', public_error_403_html_view),
    path('error_404', public_error_404_html_view),
    path('error_500', public_error_500_html_view),
    path('appstream/', login_required(appstream_view), name='appstream'),
    path('appstream-admin/', login_required(appstream_admin_view), name='appstream_admin'),
    path('appstream-restart/', login_required(appstream_restart), name='appstream_restart'),
    path('appstream-admin/fleetstatus', appstream_fleetstatus, name='appstream_fleetstatus'),
    path('application/', include(('dataworkspace.apps.applications.urls', 'applications'), namespace='applications')),
    path('catalogue/', include(('dataworkspace.apps.catalogue.urls', 'catalogue'), namespace='catalogue')),
    path('datasets/', include(('dataworkspace.apps.datasets.urls', 'datasets'), namespace='datasets')),
    path('healthcheck', healthcheck_view),  # No authentication
    path('support/', login_required(SupportView.as_view()), name='support'),
    path('support/success/<str:ticket_id>', login_required(SupportView.as_view()),
         name='support-success'),
    path('table_data/<str:database>/<str:schema>/<str:table>',
         login_required(table_data_view), name='table_data'),
    path('api/v1/', include(('dataworkspace.apps.api_v1.urls', 'api_v1'), namespace='api-v1')),
    path('admin/', include(('dataworkspace.apps.dw_admin.urls', 'dw_admin'), namespace='dw-admin')),
    path('admin/', admin.site.urls),
]

handler403 = public_error_403_html_view
handler404 = public_error_404_html_view
handler500 = public_error_500_html_view
