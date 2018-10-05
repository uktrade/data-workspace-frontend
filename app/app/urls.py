from django.contrib import admin
from django.urls import (
    include,
    path,
)

from authbroker_client.client import authbroker_login_required

from app.views import (
    databases_view,
    healthcheck_view,
)

admin.autodiscover()
admin.site.login = authbroker_login_required(admin.site.login)

urlpatterns = [
    path('auth/', include('authbroker_client.urls', namespace='authbroker')),
    path('admin/', admin.site.urls),
    path('api/v1/databases', databases_view),
    path('healthcheck', healthcheck_view),
]
