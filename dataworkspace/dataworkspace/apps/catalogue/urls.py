from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.catalogue.views import (
    dataset_full_path_view, SourceLinkDownloadView, datagroup_item_view,
    ReferenceDatasetDetailView, ReferenceDatasetDownloadView
)


urlpatterns = [
    path('<str:slug>', login_required(datagroup_item_view), name='datagroup_item'),
    path('<str:group_slug>/<str:set_slug>', login_required(dataset_full_path_view), name='dataset_fullpath'),
    path('<str:group_slug>/<str:set_slug>/<str:source_link_id>/download', login_required(SourceLinkDownloadView.as_view()),
         name='dataset_source_link_download'),
    path('<str:group_slug>/reference/<str:reference_slug>', login_required(ReferenceDatasetDetailView.as_view()),
         name='reference_dataset'),
    path('<str:group_slug>/reference/<str:reference_slug>/<str:format>',
         login_required(ReferenceDatasetDownloadView.as_view()),
         name='reference_dataset_download'),
]
