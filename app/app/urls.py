from django.contrib import admin
from django.shortcuts import (
	redirect,
)
from django.urls import (
    include,
    path,
)

from authbroker_client.client import (
	get_client,
	has_valid_token,
)

from app.views import (
    root_view,
    databases_view,
    table_data_view,
    healthcheck_view,
)


def authbroker_login_required(func):
    def decorated(request, *args, **kwargs):
        if not has_valid_token(get_client(request)):
            return redirect('authbroker:login')

        return func(request, *args, **kwargs)
    return decorated


admin.autodiscover()
admin.site.login = authbroker_login_required(admin.site.login)

urlpatterns = [
    path('', authbroker_login_required(root_view), name='root'),
    path('auth/', include('authbroker_client.urls', namespace='authbroker')),
    path('admin/', admin.site.urls),
    path('table_data/<str:database>/<str:schema>/<str:table>', authbroker_login_required(table_data_view), name='table_data'),
    path('api/v1/databases', databases_view),
    path('healthcheck', healthcheck_view),
]
