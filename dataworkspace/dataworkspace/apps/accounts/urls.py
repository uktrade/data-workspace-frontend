from django.urls import path
from dataworkspace.dataworkspace.apps.accounts.views import ProfileSettingsView


urlpatterns = [
    path("homepage-settings", ProfileSettingsView.as_view(), name="homepage-settings")
]
