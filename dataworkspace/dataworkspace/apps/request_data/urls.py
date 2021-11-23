from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.request_data.views import (
    RequestData,
    RequestDataWhoAreYou,
    RequestDataDescription,
    RequestDataPurpose,
    RequestDataLocation,
    RequestDataSecurityClassification,
    RequestDataOwnerOrManager,
    RequestDataCheckAnswers,
    RequestDataConfirmationPage,
    RequestDataLicence,
)

urlpatterns = [
    path("", login_required(RequestData.as_view()), name="index"),
    path(
        "<int:pk>/who-are-you",
        login_required(RequestDataWhoAreYou.as_view()),
        name="who-are-you",
    ),
    path(
        "<int:pk>/description",
        login_required(RequestDataDescription.as_view()),
        name="describe-data",
    ),
    path(
        "<int:pk>/purpose",
        login_required(RequestDataPurpose.as_view()),
        name="purpose-of-data",
    ),
    path(
        "<int:pk>/security-classification",
        login_required(RequestDataSecurityClassification.as_view()),
        name="security-classification",
    ),
    path(
        "<int:pk>/location",
        login_required(RequestDataLocation.as_view()),
        name="location-of-data",
    ),
    path(
        "<int:pk>/licence",
        login_required(RequestDataLicence.as_view()),
        name="licence-of-data",
    ),
    path(
        "<int:pk>/owner-or-manager",
        login_required(RequestDataOwnerOrManager.as_view()),
        name="owner-or-manager",
    ),
    path(
        "<int:pk>/check-answers",
        login_required(RequestDataCheckAnswers.as_view()),
        name="check-answers",
    ),
    path(
        "<int:pk>/confirmation",
        login_required(RequestDataConfirmationPage.as_view()),
        name="confirmation-page",
    ),
]
