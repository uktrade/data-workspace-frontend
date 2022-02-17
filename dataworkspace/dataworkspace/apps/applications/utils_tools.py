from django.urls import reverse
from dataworkspace.apps.applications.models import (
    SizeConfig,
    UserToolConfiguration,
    ApplicationTemplate,
    ApplicationInstance,
)

from dataworkspace.apps.applications.utils import stable_identification_suffix

from django.conf import settings


class ToolsViewModel:
    group_name: str
    host_basename: str
    summary: str
    link: str
    help_link: str
    instance: ApplicationInstance
    customisable_instance: bool = False
    has_access: bool
    tool_configuration: SizeConfig = None
    # remove this
    trailing_horizonal_rule: bool
    new: bool
    sort_order: int = 1

    def __init__(
        self,
        name: str,
        host_basename: str,
        summary: str,
        link: str,
        help_link: str = "",
        is_new: bool = False,
        has_access: bool = False,
    ):
        self.name = name
        self.host_basename = host_basename
        self.summary = summary
        self.link = link
        self.help_link = help_link
        self.new = is_new
        self.has_access = has_access


def get_grouped_tools(request):

    sso_id_hex_short = stable_identification_suffix(str(request.user.profile.sso_id), short=True)

    def link(application_template):
        app = application_template.host_basename
        return f"{request.scheme}://{app}-{sso_id_hex_short}.{settings.APPLICATION_ROOT_DOMAIN}/"

    tools = [
        {
            "group_name": "Visualisation Tools",
            "tools": [
                ToolsViewModel(
                    name="Quicksight",
                    host_basename="quicksight",
                    summary="Use Quicksight to create and share interactive dashboards using data from Data Workspace.",
                    help_link=None,
                    link=reverse("applications:quicksight_redirect"),
                    has_access=request.user.has_perm("applications.start_all_applications"),
                ),
                ToolsViewModel(
                    name="Superset",
                    host_basename="superset",
                    summary="Use Superset to create advanced visuals and dashbaords using data from Data Workspace. Requires SQL knowledge.",
                    help_link=None,
                    link=settings.SUPERSET_DOMAINS["edit"],
                    has_access=request.user.has_perm("applications.start_all_applications"),
                    # new=True
                ),
            ],
            "group_description": "create dashboards",
            "group_link": "https://data-services-help.trade.gov.uk/data-workspace/how-to/2-analyse-data/create-a-dashboard/",
        },
        {
            "group_name": "Data Analysis Tools",
            "tools": [
                ToolsViewModel(
                    name="Data Explorer",
                    host_basename="dataexplorer",
                    summary="The Data Explorer is a simple tool to explore and work with master datasets on Data Workspace using SQL.",
                    help_link=None,
                    link=reverse("explorer:index"),
                    has_access=request.user.has_perm("applications.start_all_applications"),
                ),
                ToolsViewModel(
                    name="SPSS / STATA",
                    host_basename=None,
                    summary="SPSS and STATA are statistical software packages supplied by IBM and StataCorp respectively. Use them to view, manage and analyse data, as well as create graphical outputs.",
                    link=settings.APPSTREAM_URL,
                    has_access=request.user.has_perm("applications.access_appstream"),
                    help_link="https://data-services-help.trade.gov.uk/data-workspace/how-articles/tools-and-how-access-them/start-using-spss/",
                ),
            ],
            "group_description": "analyse data",
            "group_link": "https://data-services-help.trade.gov.uk/data-workspace/how-to/2-analyse-data/",
        },
        {
            "group_name": "Data Management Tools",
            "tools": [
                ToolsViewModel(
                    name="Your Files",
                    host_basename="files",
                    summary="Each Data Workspace user has a private home folder accessible by the tools JupyterLab, RStudio, and Theia. You can use 'Your files' to upload files to this folder, and download files from this folder.",
                    link=reverse("your-files:files"),
                    has_access=request.user.has_perm("applications.start_all_applications"),
                    help_link=None,
                ),
                ToolsViewModel(
                    name="Gitlab",
                    host_basename="gitlab",
                    summary="Collaborate on and store analysis, projects and code with your colleagues",
                    link=settings.GITLAB_URL_FOR_TOOLS,
                    has_access=request.user.has_perm("applications.start_all_applications"),
                ),
            ],
            "group_description": "upload data and share data",
            "group_link": "https://data-services-help.trade.gov.uk/data-workspace/how-to/2-analyse-data/upload-your-own-data/",
        },
        {
            "group_name": "Integrated Development Environments",
            "tools": [],
            "group_description": "write, modify and test software",
            "group_link": "https://data-services-help.trade.gov.uk/data-workspace/how-to/",
        },
    ]

    application_instances = {
        application_instance.application_template: application_instance
        for application_instance in ApplicationInstance.objects.filter(
            owner=request.user, state__in=["RUNNING", "SPAWNING"]
        )
    }

    for application_template in (
        ApplicationTemplate.objects.all()
        .filter(visible=True, application_type="TOOL")
        .exclude(nice_name="Superset")
        .order_by("nice_name")
    ):
        vm = ToolsViewModel(
            name=application_template.nice_name,
            host_basename=application_template.host_basename,
            summary=application_template.application_summary,
            link=link(application_template),
            has_access=request.user.has_perm("applications.start_all_applications"),
            help_link=application_template.application_help_link,
        )

        vm.instance = application_instances.get(application_template, None)
        vm.tool_configuration = (
            application_template.user_tool_configuration.filter(user=request.user).first()
            or UserToolConfiguration.default_config()
        )
        vm.customisable_instance = True

        for group in tools:
            if group["group_name"] == application_template.group_name:
                group["tools"].append(vm)

    for group in tools:
        group["tools"].sort(key=lambda x: x.sort_order)

    return tools
