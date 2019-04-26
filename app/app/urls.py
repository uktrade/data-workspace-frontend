from django.contrib import (
    admin,
)
from django.contrib.auth import (
    authenticate,
    login,
)
from django.http import (
    HttpResponseForbidden,
)
from django.urls import (
    path,
)

from app.views import (
    root_view,
    databases_view,
    table_data_view,
    healthcheck_view,
)

def login_required(func):
    def _login_required(request, *args, **kwargs):

        # We "login" on every request
        user = authenticate(request)
        if user is None:
            return HttpResponseForbidden()
        login(request, user)

        return func(request, *args, **kwargs)
    return _login_required


admin.autodiscover()
admin.site.login = login_required(admin.site.login)

urlpatterns = [
    path('', login_required(root_view), name='root'),
    path('admin/', admin.site.urls),
    path('table_data/<str:database>/<str:schema>/<str:table>', login_required(table_data_view), name='table_data'),
    path('api/v1/databases', databases_view),
    path('healthcheck', healthcheck_view),
]
