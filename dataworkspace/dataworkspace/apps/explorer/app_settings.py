from django.conf import settings

EXPLORER_CONNECTIONS = getattr(settings, 'EXPLORER_CONNECTIONS', {})
EXPLORER_DEFAULT_CONNECTION = getattr(settings, 'EXPLORER_DEFAULT_CONNECTION', None)

EXPLORER_DEFAULT_ROWS = getattr(settings, 'EXPLORER_DEFAULT_ROWS', 1000)
EXPLORER_QUERY_TIMEOUT_MS = getattr(settings, 'EXPLORER_QUERY_TIMEOUT_MS', 60000)
EXPLORER_DEFAULT_DOWNLOAD_ROWS = getattr(
    settings, 'EXPLORER_DEFAULT_DOWNLOAD_ROWS', 1000
)

EXPLORER_SCHEMA_EXCLUDE_TABLE_PREFIXES = getattr(
    settings,
    'EXPLORER_SCHEMA_EXCLUDE_TABLE_PREFIXES',
    (
        'auth_',
        'contenttypes_',
        'sessions_',
        'admin_',
        'django',
        'dynamic_models',
        'data_explorer',
    ),
)

EXPLORER_SCHEMA_INCLUDE_TABLE_PREFIXES = getattr(
    settings, 'EXPLORER_SCHEMA_INCLUDE_TABLE_PREFIXES', None
)
EXPLORER_SCHEMA_INCLUDE_VIEWS = getattr(
    settings, 'EXPLORER_SCHEMA_INCLUDE_VIEWS', False
)

EXPLORER_RECENT_QUERY_COUNT = getattr(settings, 'EXPLORER_RECENT_QUERY_COUNT', 10)

EXPLORER_DATA_EXPORTERS = getattr(
    settings,
    'EXPLORER_DATA_EXPORTERS',
    [
        ('csv', 'dataworkspace.apps.explorer.exporters.CSVExporter'),
        ('excel', 'dataworkspace.apps.explorer.exporters.ExcelExporter'),
        ('json', 'dataworkspace.apps.explorer.exporters.JSONExporter'),
    ],
)
CSV_DELIMETER = getattr(settings, "EXPLORER_CSV_DELIMETER", ",")

# API access
EXPLORER_TOKEN = getattr(settings, 'EXPLORER_TOKEN', 'CHANGEME')


UNSAFE_RENDERING = getattr(settings, "EXPLORER_UNSAFE_RENDERING", False)
