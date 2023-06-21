from django.core.exceptions import PermissionDenied


class BasePermissionDeniedError(PermissionDenied):
    redirect_url = "/error_403?param=9111"


class BaseDatasetPermissionDeniedError(BasePermissionDeniedError):
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


class DataExplorerQueryResultsPermissionError(BasePermissionDeniedError):
    template_name = "errors/query_results_permission_denied.html"


class ManageVisualisationsPermissionDeniedError(BasePermissionDeniedError):
    template_name = "errors/manage_visualisations_permission_denied.html"


class PipelineBuilderPermissionDeniedError(BasePermissionDeniedError):
    template_name = "errors/pipeline_builder_permission_denied.html"


class DeveloperPermissionRequiredError(BasePermissionDeniedError):
    template_name = "errors/developer_permission_required.html"

    def __init__(self, project_name):
        super().__init__()
        self.template_context = {"project_name": project_name}


class DjangoAdminPermissionDeniedError(BasePermissionDeniedError):
    template_name = "errors/django_admin_permission_denied.html"


class ToolPermissionDeniedError(BasePermissionDeniedError):
    template_name = "errors/tool_permission_denied.html"
    redirect_url = "/error_403_tool_access"


class ToolInvalidUserError(BasePermissionDeniedError):
    template_name = "errors/error_403_invalid_tool_user.html"
    redirect_url = "/error_403_tool_invalid"
