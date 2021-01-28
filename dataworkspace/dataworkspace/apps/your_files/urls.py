from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.your_files.views import file_browser_html_view

urlpatterns = [path('', login_required(file_browser_html_view), name='files')]
