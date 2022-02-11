from dataworkspace.apps.applications.models import SizeConfig, UserToolConfiguration

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
    trailing_horizonal_rule: bool
    new: bool

    def __init__(
        self, name: str, host_basename: str, summary: str, link: str, help_link: str = "", is_new: bool = False
    ):
        self.name = name
        self.host_basename = host_basename
        self.summary = summary
        self.link = link
        self.help_link = help_link
        self.new = is_new


def get_grouped_tools():



    tools = [
        {
            "group_name": "Visualisation Tools",
            "tools": [
                ToolsViewModel(
                    "Quicksight",
                    "quicksight",
                    "Use Quicksight to create and share interactive dashboards using data from Data Workspace.",
                    "quicksight_url",
                ),
                ToolsViewModel(
                    "Superset",
                    "superset",
                    "Use Superset to create advanced visuals and dashbaords using data from Data Workspace. Requires SQL knowledge.",
                    "superset_url",
                    "",
                    True
                ),
            ],
            "group_description": "Use these tools to create dashboards",
        },
        {
            "group_name": "Data Analysis Tools",
            "tools": [
                ToolsViewModel(
                    "Data Explorer",
                    "dataexplorer",
                    "The Data Explorer is a simple tool to explore and work with master datasets on Data Workspace using SQL.",
                    "data_explorer_url",
                ),
                ToolsViewModel(
                    "pgAdmin",
                    "pgadmin",
                    "pgAdmin can be used to explore data on Data Workspace using SQL. It is an advanced alternative to Data Explorer, with additional functionality that lets you create and manage your own datasets.",
                    "pgadmin_url",
                    "Read more",
                ),
                ToolsViewModel(
                    "SPSS/STATA",
                    "spss",
                    "SPSS and STATA are statistical software packages supplied by IBM and StataCorp respectively. Use them to view, manage and analyse data, as well as create graphical outputs.",
                    "spss_url",
                    "Read more",
                ),
            ],
            "group_description": "Use these tools to analyse data",
        },
        {
            "group_name": "Data Management Tools",
            "tools": [
                ToolsViewModel(
                    "Your Files",
                    "files",
                    "Each Data Workspace user has a private home folder accessible by the tools JupyterLab, RStudio, and Theia. You can use 'Your files' to upload files to this folder, and download files from this folder.",
                    "files_url",
                ),
                ToolsViewModel(
                    "Gitlab",
                    "gitlab",
                    "Collaborate on and store analysis, projects and code with your colleagues",
                    "gitlab_url",
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
    return tools + ide_tools
