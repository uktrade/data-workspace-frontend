from django.urls import path

import dataworkspace.apps.api_v1.core.views as views

urlpatterns = [
    path(
        "user-satisfaction-surveys",
        views.UserSatisfactionSurveyViewSet.as_view({"get": "list"}),
        name="user-satisfaction-surveys",
    ),
    path(
        "get-superset-role-credentials",
        views.get_superset_credentials,
        name="get-superset-role-credentials",
    ),
]
