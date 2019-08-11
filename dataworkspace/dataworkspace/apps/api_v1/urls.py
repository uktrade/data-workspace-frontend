from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.api_v1.views import application_api_view, applications_api_view


urlpatterns = [
    path('application/<str:public_host>', csrf_exempt(login_required(application_api_view)),
         name='application-detail'),
    path('application', csrf_exempt(applications_api_view), name='application-list'),
]
