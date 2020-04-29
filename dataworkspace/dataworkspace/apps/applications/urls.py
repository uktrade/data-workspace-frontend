from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.applications.views import (
    application_spawning_html_view,
    application_running_html_view,
    tools_html_view,
)

urlpatterns = [
    path('', login_required(tools_html_view), name='tools'),
    path('<str:public_host>/spawning', login_required(application_spawning_html_view)),
    path('<str:public_host>/running', login_required(application_running_html_view)),
]
