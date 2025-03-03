from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets.requesting_data.views import StepOneView

urlpatterns = [

    path(
        "step-one",
        login_required(StepOneView.as_view()),
        name="step-one",
    ),

]
