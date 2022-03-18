from django.core.exceptions import PermissionDenied


class BaseDatasetPermissionDeniedError(PermissionDenied):
    template_name: str
    template_context: dict = {}

    def __init__(self, dataset, *args):
        super().__init__(*args)
        self.template_context = {"dataset": dataset}


class DatasetUnpublishedError(BaseDatasetPermissionDeniedError):
    template_name = "errors/dataset_unpublished.html"


class DatasetPreviewDisabledError(BaseDatasetPermissionDeniedError):
    template_name = "errors/dataset_preview_disabled.html"


class DatasetPermissionDenied(BaseDatasetPermissionDeniedError):
    template_name = "errors/dataset_permission_denied.html"
