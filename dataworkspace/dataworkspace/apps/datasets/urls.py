from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets import models, views

urlpatterns = [
    path('', login_required(views.find_datasets), name='find_datasets'),
    path(
        '<uuid:dataset_uuid>',
        login_required(views.DatasetDetailView.as_view()),
        name='dataset_detail',
    ),
    path(
        '<uuid:dataset_uuid>/link/<uuid:source_link_id>/download',
        login_required(views.SourceLinkDownloadView.as_view()),
        name='dataset_source_link_download',
    ),
    path(
        '<uuid:dataset_uuid>/view/<uuid:source_id>/download',
        login_required(views.SourceViewDownloadView.as_view()),
        name='dataset_source_view_download',
    ),
    path(
        '<uuid:dataset_uuid>/query/<int:query_id>/download',
        login_required(views.CustomDatasetQueryDownloadView.as_view()),
        name='dataset_query_download',
    ),
    path(
        '<uuid:dataset_uuid>/query/<int:query_id>/preview',
        login_required(views.CustomDatasetQueryPreviewView.as_view()),
        name='dataset_query_preview',
    ),
    path(
        '<uuid:dataset_uuid>/table/<uuid:table_uuid>/preview',
        login_required(views.SourceTablePreviewView.as_view()),
        name='dataset_table_preview',
    ),
    path(
        '<uuid:dataset_uuid>/table/<uuid:table_uuid>/columns',
        login_required(views.SourceTableColumnDetails.as_view()),
        name='source_table_column_details',
    ),
    path(
        '<uuid:dataset_uuid>/reference/<str:format>/download',
        login_required(views.ReferenceDatasetDownloadView.as_view()),
        name='reference_dataset_download',
    ),
    path(
        '<uuid:dataset_uuid>/eligibility-criteria',
        login_required(views.eligibility_criteria_view),
        name='eligibility_criteria',
    ),
    path(
        '<uuid:dataset_uuid>/eligibility-criteria-not-met',
        login_required(views.eligibility_criteria_not_met_view),
        name='eligibility_criteria_not_met',
    ),
    path(
        '<uuid:dataset_uuid>/request-access',
        login_required(views.request_access_view),
        name='request_access',
    ),
    path(
        '<uuid:dataset_uuid>/request-access-success',
        login_required(views.request_access_success_view),
        name='request_access_success',
    ),
    path(
        '<uuid:dataset_uuid>/related-data',
        login_required(views.RelatedDataView.as_view()),
        name='related_data',
    ),
    path(
        '<uuid:dataset_uuid>/preview/<int:object_id>',
        login_required(views.DataCutPreviewView.as_view()),
        {'model_class': models.CustomDatasetQuery},
        name='data_cut_query_preview',
    ),
    path(
        '<uuid:dataset_uuid>/preview/<uuid:object_id>',
        login_required(views.DataCutPreviewView.as_view()),
        {'model_class': models.SourceLink},
        name='data_cut_source_link_preview',
    ),
    path(
        '<uuid:dataset_uuid>/toggle-bookmark',
        login_required(views.toggle_bookmark),
        name='toggle_bookmark',
    ),
    path(
        '<uuid:dataset_uuid>/data-cut-usage-history',
        login_required(views.DatasetUsageHistoryView.as_view()),
        {'model_class': models.DataSet},
        name='usage_history',
    ),
    path(
        '<uuid:dataset_uuid>/visualisation-usage-history',
        login_required(views.DatasetUsageHistoryView.as_view()),
        {'model_class': models.VisualisationCatalogueItem},
        name='visualisation_usage_history',
    ),
    path(
        '<uuid:dataset_uuid>/table/<uuid:object_id>/grid',
        login_required(views.DataCutSourceDetailView.as_view()),
        {'model_class': models.SourceTable, 'download_enabled': False},
        name='source_table_detail',
    ),
    path(
        '<uuid:dataset_uuid>/table/<int:object_id>/grid',
        login_required(views.DataCutSourceDetailView.as_view()),
        {'model_class': models.CustomDatasetQuery, 'download_enabled': True},
        name='custom_dataset_query_detail',
    ),
    path(
        '<uuid:dataset_uuid>/table/<uuid:object_id>/data',
        login_required(views.DataGridDataView.as_view()),
        {'model_class': models.SourceTable, 'download_enabled': False},
        name='source_table_data',
    ),
    path(
        '<uuid:dataset_uuid>/table/<int:object_id>/data',
        login_required(views.DataGridDataView.as_view()),
        {'model_class': models.CustomDatasetQuery, 'download_enabled': True},
        name='custom_dataset_query_data',
    ),
]
