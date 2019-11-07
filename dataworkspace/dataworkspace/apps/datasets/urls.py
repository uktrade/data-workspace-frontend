from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets import views

urlpatterns = [
    path(
        '<str:group_slug>/<str:set_slug>/eligibility-criteria',
        login_required(views.eligibility_criteria_view),
        name='eligibility_criteria',
    ),
    path(
        '<str:group_slug>/<str:set_slug>/eligibility-criteria-not-met',
        login_required(views.eligibility_criteria_not_met_view),
        name='eligibility_criteria_not_met',
    ),
    path(
        '<str:group_slug>/<str:set_slug>/request-access',
        login_required(views.request_access_view),
        name='request_access',
    ),
    path(
        'request-access-success',
        login_required(views.request_access_success_view),
        name='request_access_success',
    ),
]
