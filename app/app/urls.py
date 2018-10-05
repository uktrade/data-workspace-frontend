from django.contrib import admin
from django.urls import path

from app.views import (
	credentials_view,
	healthcheck_view,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/credentials', credentials_view),
    path('healthcheck', healthcheck_view),
]
