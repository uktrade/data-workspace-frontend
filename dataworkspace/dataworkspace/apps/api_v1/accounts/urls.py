from django.urls import path

from dataworkspace.apps.api_v1.accounts.views import UserViewSet

urlpatterns = [path("users", UserViewSet.as_view({"get": "list"}), name="users")]
