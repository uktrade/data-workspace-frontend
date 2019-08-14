from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets.views import request_access_view, request_access_success_view

urlpatterns = [
    path('request-access/<str:group_slug>/<str:set_slug>', login_required(request_access_view), name='request_access'),
    path('request_access_success/', login_required(request_access_success_view), name='request_access_success'),
]
