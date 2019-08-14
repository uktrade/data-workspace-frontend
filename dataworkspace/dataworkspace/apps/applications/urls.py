from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.applications.views import application_spawning_html_view

urlpatterns = [
    path('<str:public_host>/spawning', login_required(application_spawning_html_view)),
]
