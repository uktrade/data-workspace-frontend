from django.db import models


LINKED_FIELD_IDENTIFIER = "IDENTIFIER"
LINKED_FIELD_DISPLAY_NAME = "DISPLAY_NAME"

# Map some postgres data types to types ag-grid can filter against.
# If not set falls back to `text` on the frontend
GRID_DATA_TYPE_MAP = {
    "smallint": "numeric",
    "integer": "numeric",
    "bigint": "numeric",
    "decimal": "numeric",
    "numeric": "numeric",
    "real": "numeric",
    "timestamp": "date",
    "timestamp with time zone": "date",
    "timestamp without time zone": "date",
    "date": "date",
    "boolean": "boolean",
    "text[]": "array",
    "varchar[]": "array",
    "uuid[]": "array",
    "integer[]": "array",
}


class DataSetType(models.IntegerChoices):
    # Used to define what kind of data set we're dealing with.
    # These values are persisted to the database - do not change them.
    REFERENCE = 0, "Reference Dataset"
    MASTER = 1, "Master Dataset"
    DATACUT = 2, "Data Cut"
    VISUALISATION = 3, "Visualisation"


class DataLinkType(models.IntegerChoices):
    SOURCE_LINK = 0
    SOURCE_TABLE = 1
    SOURCE_VIEW = 2
    CUSTOM_QUERY = 3


class TagType(models.IntegerChoices):
    SOURCE = 1, "Source"
    TOPIC = 2, "Topic"


class UserAccessType(models.TextChoices):
    OPEN = "OPEN", "Everyone - for public data only, suitable to be shown in demos"
    REQUIRES_AUTHENTICATION = "REQUIRES_AUTHENTICATION", "All logged in users"
    REQUIRES_AUTHORIZATION = (
        "REQUIRES_AUTHORIZATION",
        "Only specific authorized users or email domains",
    )


GRID_ACRONYM_MAP = (
    ("ITA", "International Trade Advisor"),
    ("LEP", "Local Enterprise Partnership"),
    ("OMIS", "Overseas Market Introduction Service"),
    ("FCDO", "Foreign Commonwealth and Development Office"),
    ("FDI", "Foreign Direct Investment"),
    ("EW", "export wins"),
    ("export win", "export wins"),
    ("BOP", "Balance of Payments"),
    ("CSP", "Civil Service Pensions"),
    ("DIT", "Department for International Trade"),
    ("DMAS", "Digital Market Access Service"),
    ("DNB", "Dun and Bradstreet"),
    ("GA", "Google Analytics"),
    ("EU", "European Union"),
    ("ESS", "Export Support Service"),
    ("FEX", "Find Exporters"),
    ("GTI", "Global Trade and Investment"),
    ("ODI", "Overseas Direct Investment"),
    ("QA", "Quality Assurance"),
    ("RTT", "Ready to Trade"),
    ("BED", "Business Engagement Database"),
    ("CHEG", "Check how to export goods"),
    ("CSL", "Civil Service Learning"),
    ("TAP", "Tariffs Application Platform"),
    ("FFT", "Financial Forecast Tool"),
    ("FFT", "Finance Forecast Tool"),
    ("ONS", "Office for National Statistics"),
    ("GPC", "Government Procurement Card"),
    ("IRAP", "Information and Risk Assurance Process"),
    ("ITC", "International Trade Centre"),
    ("SOO", "Selling Online Overseas"),
    ("TPU", "Trade Policy Uncertainty Index"),
    ("WDI", "World Development Indicators"),
    ("WITS", "World Integrated Trade Solution"),
    ("SSO", "Single Sign On"),
    ("SRM", "Strategic Relationship Management"),
    ("TRQ", "Tariff Rate Quotas"),
    ("WTO", "World Trade Organisation"),
    ("TWUK", "Trade with the UK"),
    ("UKTI", "UK Trade and Investment"),
    ("CRM", "Customer Relationship Managament"),
    ("OMIS", "Overseas Market Introduction Service"),
    ("FCDO", "Foreign Commonwealth and Development Office"),
    ("UKSBS", "Oracle"),
    ("export", "export wins"),
    ("great gov uk", "great.gov.uk"),
    ("companies", "company"),
    ("governance", "governance"),
    ("tech", "technology"),
    ("regions", "region"),
    ("interaction", "interactions"),
    ("investment", "investments"),
    ("service delivery", "service deliveries"),
    ("adviser", "advisor"),
    ("advisers", "advisors"),
    ("adviser", "Advisors"),
    ("Coronavirus", "Covid"),
)


class NotificationType(models.TextChoices):
    COLUMNS = "columns", "Only when columns are added, removed, or renamed"
    ALL_CHANGES = "all_changes", "All changes"


class PipelineType(models.TextChoices):
    SQL = "sql", "SQL Pipeline"
    SHAREPOINT = "sharepoint", "Sharepoint Pipeline"


class AggregationType(models.TextChoices):
    NONE = "none", "No aggregation"
    COUNT = "count", "Count"
    SUM = "sum", "Sum"
    AVG = "avg", "Average"
    MIN = "min", "Minimum"
    MAX = "max", "Maximum"
