from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.catalogue.views import (
    dataset_full_path_view,
    SourceLinkDownloadView,
    datagroup_item_view,
    ReferenceDatasetDetailView,
    ReferenceDatasetDownloadView,
    SourceTableDownloadView,
    CustomDatasetQueryDownloadView,
    SourceViewDownloadView,
)


urlpatterns = [
    path('<str:slug>', login_required(datagroup_item_view), name='datagroup_item'),
    path(
        '<str:group_slug>/<str:set_slug>',
        login_required(dataset_full_path_view),
        name='dataset_fullpath',
    ),
    path(
        '<str:group_slug>/<str:set_slug>/<str:source_link_id>/link/download',
        login_required(SourceLinkDownloadView.as_view()),
        name='dataset_source_link_download',
    ),
    path(
        '<str:group_slug>/<str:set_slug>/<str:source_id>/table/download',
        login_required(SourceTableDownloadView.as_view()),
        name='dataset_source_table_download',
    ),
    path(
        '<str:group_slug>/<str:set_slug>/<str:source_id>/view/download',
        login_required(SourceViewDownloadView.as_view()),
        name='dataset_source_view_download',
    ),
    path(
        '<str:group_slug>/<str:set_slug>/<int:query_id>/query/download',
        login_required(CustomDatasetQueryDownloadView.as_view()),
        name='dataset_query_download',
    ),
    path(
        '<str:group_slug>/reference/<str:reference_slug>',
        login_required(ReferenceDatasetDetailView.as_view()),
        name='reference_dataset',
    ),
    path(
        '<str:group_slug>/reference/<str:reference_slug>/<str:format>',
        login_required(ReferenceDatasetDownloadView.as_view()),
        name='reference_dataset_download',
    ),
]
