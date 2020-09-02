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
        '<str:dataset_uuid>/link/<str:source_link_id>/download',
        login_required(views.SourceLinkDownloadView.as_view()),
        name='dataset_source_link_download',
    ),
    path(
        '<str:dataset_uuid>/view/<str:source_id>/download',
        login_required(views.SourceViewDownloadView.as_view()),
        name='dataset_source_view_download',
    ),
    path(
        '<str:dataset_uuid>/query/<int:query_id>/download',
        login_required(views.CustomDatasetQueryDownloadView.as_view()),
        name='dataset_query_download',
    ),
    path(
        '<str:dataset_uuid>/query/<int:query_id>/preview',
        login_required(views.CustomDatasetQueryPreviewView.as_view()),
        name='dataset_query_preview',
    ),
    path(
        '<str:dataset_uuid>/table/<str:table_uuid>/preview',
        login_required(views.SourceTablePreviewView.as_view()),
        name='dataset_table_preview',
    ),
    path(
        '<str:dataset_uuid>/reference/<str:format>/download',
        login_required(views.ReferenceDatasetDownloadView.as_view()),
        name='reference_dataset_download',
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
        '<str:dataset_uuid>/request-access-success',
        login_required(views.request_access_success_view),
        name='request_access_success',
    ),
]
