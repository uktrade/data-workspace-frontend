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


class DataExplorerQueryResultsPermissionError(PermissionDenied):
    template_name = "errors/query_results_permission_denied.html"


class ManageVisualisationsPermissionDeniedError(PermissionDenied):
    template_name = "errors/manage_visualisations_permission_denied.html"


class PipelineBuilderPermissionDeniedError(PermissionDenied):
    template_name = "errors/pipeline_builder_permission_denied.html"


class DeveloperPermissionRequiredError(PermissionDenied):
    template_name = "errors/developer_permission_required.html"

    def __init__(self, project_name):
        super().__init__()
        self.template_context = {"project_name": project_name}


class DjangoAdminPermissionDeniedError(PermissionDenied):
    template_name = "errors/django_admin_permission_denied.html"


class ToolPermissionDeniedError(PermissionDenied):
    template_name = "errors/tool_permission_denied.html"
