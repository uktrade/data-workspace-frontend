from django.urls import path

from dataworkspace.apps.dw_admin.views import (ReferenceDatasetAdminEditView, ReferenceDatasetAdminDeleteView,
                                               SourceLinkUploadView)

urlpatterns = [
    path(
        'app/referencedata/<int:reference_dataset_id>/data/<int:record_id>/change/',
        view=ReferenceDatasetAdminEditView.as_view(),
        name='reference-dataset-record-edit'
    ),
    path(
        'app/referencedataset/<int:reference_dataset_id>/data/add/',
        view=ReferenceDatasetAdminEditView.as_view(),
        name='reference-dataset-record-add'
    ),
    path(
        'app/referencedata/<int:reference_dataset_id>/data/<str:record_id>/delete/',
        view=ReferenceDatasetAdminDeleteView.as_view(),
        name='reference-dataset-record-delete'
    ),
    path(
        'app/dataset/<str:dataset_id>/sourcelink/upload/',
        view=SourceLinkUploadView.as_view(),
        name='source-link-upload'
    ),
]
