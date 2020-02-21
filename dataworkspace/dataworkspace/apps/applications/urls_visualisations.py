from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.applications.views import visualisations_html_view

urlpatterns = [path('', login_required(visualisations_html_view), name='root')]
