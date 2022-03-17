from django.core.exceptions import PermissionDenied


class DatasetUnpublishedError(PermissionDenied):
    template_name = "errors/dataset_unpublished.html"
    template_context = {}

    def __init__(self, dataset, *args):
        super().__init__(*args)
        self.template_context = {"dataset": dataset}
