from django.urls import reverse
from dataworkspace.apps.applications.models import SizeConfig, UserToolConfiguration, ApplicationTemplate
from django.conf import settings


class ToolsViewModel:
    group_name: str
    host_basename: str
    summary: str
    link: str
    help_link: str
    instance: str
    customisable_instance: bool = False
    has_access: bool
    tool_configuration: SizeConfig = None
    # remove this
    trailing_horizonal_rule: bool
    new: bool

    def __init__(
        self, name: str, host_basename: str, summary: str, 
        link: str, help_link: str = "", is_new: bool = False,
        has_access: bool = False
    ):
        self.name = name
        self.host_basename = host_basename
        self.summary = summary
        self.link = link
        self.help_link = help_link
        self.new = is_new
        self.has_access = has_access


def get_grouped_tools(request):
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
                    new=True

                ),
            ],
            "group_description": "Use these tools to create dashboards",
        },
        {
            "group_name": "Data Analysis Tools",
            "tools": [
                ToolsViewModel(
                    name="Data Explorer",
                    host_basename="dataexplorer",
                    summary="The Data Explorer is a simple tool to explore and work with master datasets on Data Workspace using SQL.",
                    help_link=None,
                    link="url'explorer:index'",
                    has_access=request.user.has_perm("applications.start_all_applications"),
                ),
                # ToolsViewModel(
                #     "pgAdmin",
                #     "pgadmin",
                #     "pgAdmin can be used to explore data on Data Workspace using SQL. It is an advanced alternative to Data Explorer, with additional functionality that lets you create and manage your own datasets.",
                #     "pgadmin_url",
                #     "Read more",
                # ),
                ToolsViewModel(
                    mame="SPSS / STATA",
                    host_basename="??",
                    summary="SPSS and STATA are statistical software packages supplied by IBM and StataCorp respectively. Use them to view, manage and analyse data, as well as create graphical outputs.",
                    link=settings.APPSTREAM_URL,
                    has_access=request.user.has_perm("applications.access_appstream"),
                    help_link='https://data-services-help.trade.gov.uk/data-workspace/how-articles/tools-and-how-access-them/start-using-spss/'
                ),
            ],
            "group_description": "Use these tools to analyse data",
        },
        {
            "group_name": "Data Management Tools",
            "tools": [
                ToolsViewModel(
                    name="Your Files",
                    host_basename="files",
                    summary="Each Data Workspace user has a private home folder accessible by the tools JupyterLab, RStudio, and Theia. You can use 'Your files' to upload files to this folder, and download files from this folder.",
                    link=settings.YOUR_FILES_ENABLED,
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
            "group_description": "Use these tools to upload data and share data",
        }
    ]
    
    rstudio =   ToolsViewModel(
                    "RStudio",
                    "rstudio",
                    "RStudio is an integrated development environment (IDE). Use it for statistical programming using R.",
                    "rstudio_url",
                    "Read more",
                )

    rstudio.tool_configuration = UserToolConfiguration.default_config()
    rstudio.customisable_instance = True

    ide_tools = [
        {
            "group_name": "Integrated Development Environments",
            "tools": [
              rstudio,
                ToolsViewModel(
                    "JupyterLab Python",
                    "jupyterlab",
                    "JupyterLab is an integrated development environment (IDE). Use it to create interactive Python notebooks which enable data cleaning, data transformation and statistical modelling.",
                    "jupyterlab_url",
                    "Read more",
                ),
                ToolsViewModel(
                    "Theia",
                    "theia",
                    "Theia is an integrated development environment (IDE). Use it to do file-based analysis, create visualisations, and analyse datasets from Data Workspace using Structured Query Language (SQL).",
                    "theia_url",
                ),
            ],
            "group_description": "Use these tools to write, modify and test software",
        },
    ]

    all_tools= tools + ide_tools


    # groups = {
    #     "Integrated Development Environments": []
    # }

    # loop through dictionary in django template
    # for key,value in object.items ....

    for application_template in ApplicationTemplate.objects.all().filter(visible=True, application_type="TOOL").exclude(nice_name="Superset").order_by("nice_name"):
        pass        
        group =  # find the group from all_tools that has name == application_template.group_name
        # group = groups[application_template.group_name]

        # group.append(ToolsViewModel(...create from actual model))
        #  ToolsViewModel(
        #             name=application_template.name,
        #             host_basename=application_template.host_basename,
        #             summary=application_template.summary,
        #             link=settings.?
        #             has_access=request.user.has_perm("applications.start_all_applications"),
                    
        #         ),
        




    return all_tools
