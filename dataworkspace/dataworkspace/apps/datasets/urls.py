from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets import views

urlpatterns = [
    path('', login_required(views.find_datasets), name='find_datasets'),
    path(
        '<str:dataset_uuid>',
        login_required(views.DatasetDetailView.as_view()),
        name='dataset_detail',
    ),
    path(
        '<str:dataset_uuid>/eligibility-criteria',
        login_required(views.eligibility_criteria_view),
        name='eligibility_criteria',
    ),
    path(
        '<str:dataset_uuid>/eligibility-criteria-not-met',
        login_required(views.eligibility_criteria_not_met_view),
        name='eligibility_criteria_not_met',
    ),
    path(
        '<str:dataset_uuid>/request-access',
        login_required(views.request_access_view),
        name='request_access',
    ),
    path(
        'request-access-success',
        login_required(views.request_access_success_view),
        name='request_access_success',
    ),
]
