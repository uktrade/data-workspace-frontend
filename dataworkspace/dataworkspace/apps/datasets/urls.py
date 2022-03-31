from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets import models, views
from dataworkspace.apps.datasets.subscriptions import views as subscription_views

urlpatterns = [
    path("", login_required(views.find_datasets), name="find_datasets"),
    path(
        "<uuid:dataset_uuid>",
        login_required(views.DatasetDetailView.as_view()),
        name="dataset_detail",
    ),
    path(
        "<uuid:dataset_uuid>/link/<uuid:source_link_id>/download",
        login_required(views.SourceLinkDownloadView.as_view()),
        name="dataset_source_link_download",
    ),
    path(
        "<uuid:dataset_uuid>/view/<uuid:source_id>/download",
        login_required(views.SourceViewDownloadView.as_view()),
        name="dataset_source_view_download",
    ),
    path(
        "<uuid:dataset_uuid>/query/<int:query_id>/download",
        login_required(views.CustomDatasetQueryDownloadView.as_view()),
        name="dataset_query_download",
    ),
    path(
        "<uuid:dataset_uuid>/query/<int:query_id>/preview",
        login_required(views.CustomDatasetQueryPreviewView.as_view()),
        name="dataset_query_preview",
    ),
    path(
        "<uuid:dataset_uuid>/table/<uuid:table_uuid>/preview",
        login_required(views.SourceTablePreviewView.as_view()),
        name="dataset_table_preview",
    ),
    path(
        "<uuid:dataset_uuid>/table/<uuid:table_uuid>/columns",
        login_required(views.SourceTableColumnDetails.as_view()),
        name="source_table_column_details",
    ),
    path(
        "<uuid:dataset_uuid>/columns",
        login_required(views.ReferenceDatasetColumnDetails.as_view()),
        name="reference_dataset_column_details",
    ),
    path(
        "<uuid:dataset_uuid>/grid",
        login_required(views.ReferenceDatasetGridView.as_view()),
        name="reference_dataset_grid",
    ),
    path(
        "<uuid:dataset_uuid>/reference/<str:format>/download",
        login_required(views.ReferenceDatasetDownloadView.as_view()),
        name="reference_dataset_download",
    ),
    path(
        "<uuid:dataset_uuid>/eligibility-criteria",
        login_required(views.eligibility_criteria_view),
        name="eligibility_criteria",
    ),
    path(
        "<uuid:dataset_uuid>/eligibility-criteria-not-met",
        login_required(views.eligibility_criteria_not_met_view),
        name="eligibility_criteria_not_met",
    ),
    path(
        "<uuid:dataset_uuid>/related-data",
        login_required(views.RelatedDataView.as_view()),
        name="related_data",
    ),
    path(
        "<uuid:dataset_uuid>/related-visualisations",
        login_required(views.RelatedVisualisationsView.as_view()),
        name="related_visualisations",
    ),
    path(
        "<uuid:dataset_uuid>/preview/<int:object_id>",
        login_required(views.DataCutPreviewView.as_view()),
        {"model_class": models.CustomDatasetQuery},
        name="data_cut_query_preview",
    ),
    path(
        "<uuid:dataset_uuid>/preview/<uuid:object_id>",
        login_required(views.DataCutPreviewView.as_view()),
        {"model_class": models.SourceLink},
        name="data_cut_source_link_preview",
    ),
    path(
        "<uuid:dataset_uuid>/toggle-bookmark",
        login_required(views.toggle_bookmark),
        name="toggle_bookmark",
    ),
    path(
        "<uuid:dataset_uuid>/data-cut-usage-history",
        login_required(views.DatasetUsageHistoryView.as_view()),
        {"model_class": models.DataSet},
        name="usage_history",
    ),
    path(
        "<uuid:dataset_uuid>/visualisation-usage-history",
        login_required(views.DatasetUsageHistoryView.as_view()),
        {"model_class": models.VisualisationCatalogueItem},
        name="visualisation_usage_history",
    ),
    path(
        "<uuid:dataset_uuid>/table/<uuid:object_id>/grid",
        login_required(views.DataCutSourceDetailView.as_view()),
        {"model_class": models.SourceTable},
        name="source_table_detail",
    ),
    path(
        "<uuid:dataset_uuid>/table/<int:object_id>/grid",
        login_required(views.DataCutSourceDetailView.as_view()),
        {"model_class": models.CustomDatasetQuery},
        name="custom_dataset_query_detail",
    ),
    path(
        "<uuid:dataset_uuid>/table/<uuid:object_id>/data",
        login_required(views.DataGridDataView.as_view()),
        {"model_class": models.SourceTable},
        name="source_table_data",
    ),
    path(
        "<uuid:dataset_uuid>/table/<int:object_id>/data",
        login_required(views.DataGridDataView.as_view()),
        {"model_class": models.CustomDatasetQuery},
        name="custom_dataset_query_data",
    ),
    path(
        "<uuid:dataset_uuid>/visualisation/<int:object_id>/",
        login_required(views.DatasetVisualisationView.as_view()),
        {"model_class": models.DataSet},
        name="dataset_visualisation",
    ),
    path(
        "<uuid:dataset_uuid>/visualisation-preview/<int:object_id>/",
        login_required(views.DatasetVisualisationPreview.as_view()),
        {"model_class": models.DataSet},
        name="dataset_visualisation-preview",
    ),
    path(
        "<uuid:dataset_uuid>/datacut/<int:query_id>/columns",
        login_required(views.CustomQueryColumnDetails.as_view()),
        name="custom_query_column_details",
    ),
    path(
        "<uuid:dataset_uuid>/subscription_start",
        login_required(subscription_views.DataSetSubscriptionStartView.as_view()),
        name="subscription_start",
    ),
    path(
        "<uuid:pk>/subscription_options",
        login_required(subscription_views.DataSetSubscriptionView.as_view()),
        name="subscription_options",
    ),
    path(
        "<uuid:pk>/subscription_review",
        login_required(subscription_views.DataSetSubscriptionReview.as_view()),
        name="subscription_review",
    ),
    path(
        "<uuid:subscription_id>/subscription_confirm",
        login_required(subscription_views.DataSetSubscriptionConfirm.as_view()),
        name="subscription_confirm",
    ),
    path(
        "email_preferences",
        login_required(subscription_views.current_user_email_preferences_list),
        name="email_preferences",
    ),
    path(
        "<str:subscription_id>/unsubscribe",
        login_required(subscription_views.DataSetSubscriptionUnsubscribe.as_view()),
        name="subscription_unsubscribe",
    ),
    path(
        "<uuid:dataset_uuid>/<uuid:source_id>/changelog/",
        login_required(views.SourceChangelogView.as_view()),
        {"model_class": models.SourceTable},
        name="source_table_changelog",
    ),
    path(
        "<uuid:dataset_uuid>/<str:source_id>/changelog/",
        login_required(views.SourceChangelogView.as_view()),
        {"model_class": models.CustomDatasetQuery},
        name="custom_dataset_query_changelog",
    ),
    path(
        "reference/<uuid:dataset_uuid>/changelog/",
        login_required(views.SourceChangelogView.as_view()),
        {"model_class": models.ReferenceDataset},
        name="reference_dataset_changelog",
    ),
    path(
        "<uuid:dataset_uuid>/chart/<int:object_id>/",
        login_required(views.DatasetChartView.as_view()),
        {"model_class": models.DataSet},
        name="dataset_chart",
    ),
    path(
        "<uuid:dataset_uuid>/chart/<int:object_id>/data",
        login_required(views.DatasetChartDataView.as_view()),
        {"model_class": models.DataSet},
        name="dataset_chart_data",
    ),
]
