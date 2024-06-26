from django.urls import path

# pylint: disable=consider-using-from-import
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
    path(
        "generate-mlflow-jwt",
        views.generate_mlflow_jwt,
        name="generate-mlflow-jwt",
    ),
    path(
        "newslettersubscription",
        views.NewsletterSubscriptionViewSet.as_view({"get": "list"}),
        name="newslettersubscription",
    ),
    path(
        "teams",
        views.TeamViewSet.as_view({"get": "list"}),
        name="teams",
    ),
    path(
        "user-inline-feedback-survey",
        views.UserInlineFeedbackSurveyViewSet.as_view({"get": "list"}),
        name="user-inline-feedback-survey",
    ),
]
