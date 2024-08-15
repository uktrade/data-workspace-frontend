from django.urls import reverse
from django.conf import settings
from dataworkspace.apps.applications.models import (
    SizeConfig,
    UserToolConfiguration,
    ApplicationTemplate,
    ApplicationInstance,
)

from dataworkspace.apps.applications.utils import stable_identification_suffix


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
    trailing_horizontal_rule: bool
    tag: str
    tag_extra_css_class: str
    sort_order: int = 1

    def __init__(
        self,
        name: str,
        host_basename: str,
        summary: str,
        link: str,
        help_link: str = "",
        has_access: bool = False,
        tag: str = None,
        tag_extra_css_class: str = "",
    ):
        self.name = name
        self.host_basename = host_basename
        self.summary = summary
        self.link = link
        self.help_link = help_link
        self.has_access = has_access
        self.tag = tag
        self.tag_extra_css_class = tag_extra_css_class


def get_groups(request):
    tools = {
        "Visualisation Tools": {
            "group_name": "Visualisation Tools",
            "tools": [
                ToolsViewModel(
                    name="QuickSight",
                    host_basename="quicksight",
                    summary="Use Quicksight to create and share interactive dashboards using data from Data Workspace.",
                    help_link=None,
                    link=reverse("applications:quicksight_redirect"),
                    has_access=request.user.has_perm("applications.access_quicksight"),
                ),
                ToolsViewModel(
                    name="Superset",
                    host_basename="superset",
                    summary="Use Superset to create advanced visuals and dashboards using data from Data Workspace. "
                    "Requires SQL knowledge.",
                    help_link=None,
                    link=reverse("applications:superset_redirect"),
                    has_access=request.user.has_perm("applications.start_all_applications"),
                ),
            ],
            "group_description": "create dashboards",
            "group_link": "https://data-services-help.trade.gov.uk/data-workspace/how-to/"
            "see-tools-specific-guidance/quicksight/create-a-dashboard/",
        },
        "Data Analysis Tools": {
            "group_name": "Data Analysis Tools",
            "tools": [
                ToolsViewModel(
                    name="Data Explorer",
                    host_basename="dataexplorer",
                    summary="The Data Explorer is a simple tool to explore and work with master datasets on "
                    "Data Workspace using SQL.",
                    help_link=None,
                    link=reverse("applications:data_explorer_redirect"),
                    has_access=request.user.has_perm("applications.start_all_applications"),
                ),
                ToolsViewModel(
                    name="STATA",
                    host_basename=None,
                    summary="STATA is a statistical software package supplied by StataCorp. "
                    "Use it to view, manage and analyse data, as well as create graphical outputs.",
                    link=settings.APPSTREAM_URL,
                    has_access=request.user.has_perm("applications.access_appstream"),
                    help_link="https://data-services-help.trade.gov.uk/data-workspace/how-to/"
                    "see-tools-specific-guidance/spss-and-stata/",
                ),
            ],
            "group_description": "analyse data",
            "group_link": "https://data-services-help.trade.gov.uk/data-workspace/how-to/see-tools-specific-guidance/",
        },
        "Data Managament Tools": {
            "group_name": "Data Management Tools",
            "tools": [
                ToolsViewModel(
                    name="Your Files",
                    host_basename="files",
                    summary="Each Data Workspace user has a private home folder accessible by the tools "
                    "JupyterLab, RStudio, and Theia. You can use 'Your files' to upload files "
                    "to this folder, and download files from this folder.",
                    link=reverse("your-files:files"),
                    has_access=True,
                    help_link=None,
                ),
                ToolsViewModel(
                    name="GitLab",
                    host_basename="gitlab",
                    summary="Collaborate on and store analysis, projects and "
                    "code with your colleagues",
                    link=settings.GITLAB_URL_FOR_TOOLS,
                    has_access=True,
                ),
            ],
            "group_description": "upload data and share data",
            "group_link": "https://data-services-help.trade.gov.uk/data-workspace/how-to/"
            "see-tools-specific-guidance/your-files/start-using-your-files/",
        },
        "Integrated Development Environments": {
            "group_name": "Integrated Development Environments",
            "tools": [],
            "group_description": "write, modify and test software",
            "group_link": "https://data-services-help.trade.gov.uk/data-workspace/how-to/",
        },
    }
    return tools


def get_grouped_tools(request):
    sso_id_hex_short = stable_identification_suffix(str(request.user.profile.sso_id), short=True)

    def link(template):
        app = template.host_basename
        return f"{request.scheme}://{app}-{sso_id_hex_short}.{settings.APPLICATION_ROOT_DOMAIN}/"

    groups = get_groups(request)

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
        group = groups.get(application_template.group_name, None)
        if group:
            group["tools"].append(vm)

    for _key, value in groups.items():
        value["tools"].sort(key=lambda x: x.sort_order)

    return groups
