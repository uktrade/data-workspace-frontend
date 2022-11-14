import base64

import json
import os
import urllib.request
from distutils.util import strtobool

from celery.schedules import crontab
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from django.conf.locale.en import formats as en_formats

import sentry
from dataworkspace.utils import normalise_environment

sentry.init_sentry(
    integrations=[
        AioHttpIntegration(),
        DjangoIntegration(),
        RedisIntegration(),
        CeleryIntegration(),
        SqlalchemyIntegration(),
    ]
)

env = normalise_environment(os.environ)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENVIRONMENT = env.get("ENVIRONMENT", "Dev")
SECRET_KEY = env["SECRET_KEY"]
LOCAL = "dataworkspace.test" in env["ALLOWED_HOSTS"]
DEBUG = bool(strtobool(env.get("DEBUG", str(LOCAL))))


def aws_fargate_private_ip():
    with urllib.request.urlopen("http://169.254.170.2/v2/metadata") as response:
        return json.loads(response.read().decode("utf-8"))["Containers"][0]["Networks"][0][
            "IPv4Addresses"
        ][0]


ALLOWED_HOSTS = (
    (env["ALLOWED_HOSTS"]) if LOCAL else (env["ALLOWED_HOSTS"] + [aws_fargate_private_ip()])
)

INTERNAL_IPS = ["127.0.0.1"] if LOCAL else []

ELASTIC_APM_URL = env.get("ELASTIC_APM_URL")
ELASTIC_APM_SECRET_TOKEN = env.get("ELASTIC_APM_SECRET_TOKEN")
ELASTIC_APM = (
    {
        "SERVICE_NAME": "data-workspace",
        "SECRET_TOKEN": ELASTIC_APM_SECRET_TOKEN,
        "SERVER_URL": ELASTIC_APM_URL,
        "ENVIRONMENT": env.get("ENVIRONMENT", "development"),
    }
    if ELASTIC_APM_SECRET_TOKEN
    else {}
)

# Used by `django.contrib.sites`, which enables `django.contrib.redirects`
# https://docs.djangoproject.com/en/3.0/ref/settings/#site-id
SITE_ID = 1

INSTALLED_APPS = [
    "dataworkspace.admin.DataWorkspaceAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.postgres",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sites",
    "django.contrib.redirects",
    "django.forms",
    "django_better_admin_arrayfield.apps.DjangoBetterAdminArrayfieldConfig",
    "adminsortable2",
    "ckeditor",
    "waffle",
    "rest_framework",
    "dataworkspace.apps.core",
    "dataworkspace.apps.accounts",
    "dataworkspace.apps.catalogue",
    "dataworkspace.apps.applications",
    "dataworkspace.apps.appstream",
    "dataworkspace.apps.datasets",
    "dataworkspace.apps.dw_admin",
    "dataworkspace.apps.api_v1",
    "dataworkspace.apps.eventlog",
    "dataworkspace.apps.request_data",
    "dataworkspace.apps.request_access",
    "dataworkspace.apps.your_files",
    "django_extensions",
    "dataworkspace.apps.explorer",
    "dataworkspace.apps.finder",
    "dynamic_models",
    "dataworkspace.apps.case_studies",
    "csp_helpers",
    "webpack_loader",
    "dataworkspace.apps.data_collections",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "waffle.middleware.WaffleMiddleware",
    "dataworkspace.middleware.disable_client_side_caching",
    "csp.middleware.CSPMiddleware",
    "django.contrib.redirects.middleware.RedirectFallbackMiddleware",
]

if DEBUG:
    INSTALLED_APPS.append("debug_toolbar")
    MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")

if ELASTIC_APM:
    INSTALLED_APPS.append("elasticapm.contrib.django")

AUTHENTICATION_BACKENDS = ["dataworkspace.apps.accounts.backends.AuthbrokerBackendUsernameIsEmail"]
AUTHBROKER_URL = env["AUTHBROKER_URL"]
AUTHBROKER_CLIENT_ID = env["AUTHBROKER_CLIENT_ID"]
AUTHBROKER_CLIENT_SECRET = env["AUTHBROKER_CLIENT_SECRET"]
LOGIN_REDIRECT_URL = "/"
APPSTREAM_AWS_SECRET_KEY = os.environ.get("APPSTREAM_AWS_SECRET_KEY")
APPSTREAM_AWS_ACCESS_KEY = os.environ.get("APPSTREAM_AWS_ACCESS_KEY")
APPSTREAM_AWS_REGION = os.environ.get("APPSTREAM_AWS_REGION")
APPSTREAM_STACK_NAME = os.environ.get("APPSTREAM_STACK_NAME")
APPSTREAM_FLEET_NAME = os.environ.get("APPSTREAM_FLEET_NAME")
AWS_ECR_ENDPOINT_URL = os.environ.get("AWS_ECR_ENDPOINT_URL")
DATASET_FINDER_ES_HOST = os.environ.get("DATASET_FINDER_ES_HOST")
DATASET_FINDER_ES_PORT = os.environ.get("DATASET_FINDER_ES_PORT")
DATASET_FINDER_ES_INSECURE = os.environ.get("DATASET_FINDER_ES_INSECURE", False)
DATASET_FINDER_AWS_REGION = os.environ.get("DATASET_FINDER_AWS_REGION")
DATASET_FINDER_DB_NAME = os.environ.get("DATASET_FINDER_DB_NAME")
SSO_ADMIN_SCOPE_TOKEN = os.environ.get("SSO_ADMIN_SCOPE_TOKEN")

ROOT_URLCONF = "dataworkspace.urls"

TEMPLATES = [
    {
        "NAME": "MainTemplates",
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.static",
                "dataworkspace.context_processors.common",
            ],
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
        },
    }
]

WSGI_APPLICATION = "dataworkspace.wsgi.application"

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

LOGGING_HANDLERS = ["dev" if DEBUG else "console"]
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"ecs": {"()": "dataworkspace.utils.DataWorkspaceECSFormatter"}},
    "handlers": {
        "dev": {"class": "logging.StreamHandler"},
        "console": {"class": "logging.StreamHandler", "formatter": "ecs"},
    },
    "loggers": {
        "django": {"handlers": LOGGING_HANDLERS, "level": "INFO"},
        "app": {"handlers": LOGGING_HANDLERS, "level": "INFO"},
        "dataworkspace": {"handlers": LOGGING_HANDLERS, "level": "INFO"},
        "celery": {"handlers": LOGGING_HANDLERS, "level": "INFO", "propagate": False},
    },
}

# Not all installations have this set
NOTEBOOKS_BUCKET = env.get("NOTEBOOKS_BUCKET", None)
APPSTREAM_URL = env["APPSTREAM_URL"]

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env["REDIS_URL"],
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

# This deliberately the same as the proxy: it changes the cookie value on
# login, which mitigates the risk of session fixation attack. Using the same
# cookie also means there are fewer cases to consider in terms of cookie
# expiration.
SESSION_COOKIE_NAME = ("__Secure-" if not LOCAL else "") + "data_workspace_session"
root_domain_no_port, _, _ = env["APPLICATION_ROOT_DOMAIN"].partition(":")
SESSION_COOKIE_DOMAIN = root_domain_no_port
SESSION_COOKIE_SECURE = not LOCAL
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

CSRF_COOKIE_SECURE = not LOCAL
CSRF_COOKIE_NAME = ("__Secure-" if not LOCAL else "") + "data_workspace_csrf"
CSRF_FAILURE_VIEW = "dataworkspace.apps.core.views.public_error_403_csrf_html_view"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# The application template models are populated by environment variables,
# since they can contain very low-level infrastructure details, and it means
# tests don't have to worry about fixtures / editing the database
APPLICATION_TEMPLATES = env["APPLICATION_TEMPLATES"]
APPLICATION_ROOT_DOMAIN = env["APPLICATION_ROOT_DOMAIN"]
APPLICATION_SPAWNER_OPTIONS = env.get("APPLICATION_SPAWNER_OPTIONS", {})

# CSP Headers
CSP_DEFAULT_SRC = [APPLICATION_ROOT_DOMAIN]
CSP_OBJECT_SRC = ["'none'"]
CSP_UPGRADE_INSECURE_REQUESTS = not LOCAL
CSP_BASE_URI = [APPLICATION_ROOT_DOMAIN]
CSP_FONT_SRC = [APPLICATION_ROOT_DOMAIN, "data:", "https://fonts.gstatic.com"]
CSP_FORM_ACTION = [APPLICATION_ROOT_DOMAIN, f"*.{APPLICATION_ROOT_DOMAIN}"]
CSP_FRAME_ANCESTORS = [APPLICATION_ROOT_DOMAIN]
CSP_CONNECT_SRC = [
    APPLICATION_ROOT_DOMAIN,
    "https://www.google-analytics.com",
    "*.google-analytics.com",
    "*.analytics.google.com",
    "*.googletagmanager.com",
]
CSP_IMG_SRC = [
    APPLICATION_ROOT_DOMAIN,
    "data:",
    "https://www.googletagmanager.com",
    "https://www.googletagmanager.com",
    "https://www.google-analytics.com",
    "https://ssl.gstatic.com",
    "https://www.gstatic.com",
    "*.google-analytics.com",
    "*.googletagmanager.com",
]
CSP_SCRIPT_SRC = [
    APPLICATION_ROOT_DOMAIN,
    "https://www.googletagmanager.com",
    "https://www.google-analytics.com",
    "https://tagmanager.google.com",
    "*.googletagmanager.com",
]
CSP_STYLE_SRC = [
    APPLICATION_ROOT_DOMAIN,
    "'unsafe-inline'",
    "https://tagmanager.google.com",
    "https://fonts.googleapis.com",
]
CSP_INCLUDE_NONCE_IN = ["script-src"]

# Allow for connecting to the webpack hotloader for local development
if DEBUG:
    CSP_CONNECT_SRC += [
        f"{APPLICATION_ROOT_DOMAIN.split(':')[0]}:3000",
        f"ws://{APPLICATION_ROOT_DOMAIN.split(':')[0]}:3000",
    ]


ZENDESK_EMAIL = env["ZENDESK_EMAIL"]
ZENDESK_SUBDOMAIN = env["ZENDESK_SUBDOMAIN"]
ZENDESK_TOKEN = env["ZENDESK_TOKEN"]

ZENDESK_SERVICE_FIELD_ID = env["ZENDESK_SERVICE_FIELD_ID"]
ZENDESK_SERVICE_FIELD_VALUE = env["ZENDESK_SERVICE_FIELD_VALUE"]


NOTIFY_API_KEY = env["NOTIFY_API_KEY"]
FERNET_EMAIL_TOKEN_KEY = env["FERNET_EMAIL_TOKEN_KEY"]

NOTIFY_VISUALISATION_ACCESS_REQUEST_TEMPLATE_ID = "7cf395da-2f1b-4084-a526-f2fd68a15491"
NOTIFY_VISUALISATION_ACCESS_GRANTED_TEMPLATE_ID = "139d5e94-1044-49f9-99a9-2a094b8986ea"
NOTIFY_SHARE_EXPLORER_QUERY_TEMPLATE_ID = "8fe771ef-e8b6-4ff2-98a9-8ba208b5a3fa"

NOTIFY_DATASET_NOTIFICATIONS_COLUMNS_TEMPLATE_ID = "9f992c0d-f6c0-4569-9d06-9e415304f5f9"
NOTIFY_DATASET_NOTIFICATIONS_ALL_DATA_TEMPLATE_ID = "daca1854-a2b3-4020-9c19-59bdf6bb309c"

CELERY_BROKER_URL = env["REDIS_URL"]
CELERY_RESULT_BACKEND = env["REDIS_URL"]

CELERY_ROUTES = {
    "dataworkspace.apps.explorer.tasks._run_querylog_query": {"queue": "explorer.tasks"},
    "dataworkspace.apps.applications.spawner.spawn": {"queue": "applications.spawner.spawn"},
}

if not strtobool(env.get("DISABLE_CELERY_BEAT_SCHEDULE", "0")):
    CELERY_BEAT_SCHEDULE = {
        "kill-idle-fargate-containers": {
            "task": "dataworkspace.apps.applications.utils.kill_idle_fargate",
            "schedule": 60 * 10,
            "args": (),
        },
        "populate-created-stopped-fargate-containers": {
            "task": "dataworkspace.apps.applications.utils.populate_created_stopped_fargate",
            "schedule": 60 * 10,
            "args": (),
        },
        "delete-unused-datasets-users": {
            "task": "dataworkspace.apps.applications.utils.delete_unused_datasets_users",
            "schedule": 60 * 10,
            "args": (),
        },
        "full-quicksight-permissions-sync": {
            "task": "dataworkspace.apps.applications.utils.sync_quicksight_permissions",
            "schedule": crontab(minute=17, hour=1),
            "args": (),
        },
        "clean-up-old-data-explorer-playground-sql-queries": {
            "task": "dataworkspace.apps.explorer.tasks.cleanup_playground_sql_table",
            "schedule": 60 * 60 * 6,
            "args": (),
        },
        "clean-up-old-data-explorer-materialized-views": {
            "task": "dataworkspace.apps.explorer.tasks.cleanup_temporary_query_tables",
            "schedule": crontab(minute=0, hour=0),
            "args": (),
        },
        "sync-sso-users-from-activity-stream": {
            "task": "dataworkspace.apps.applications.utils.sync_activity_stream_sso_users",
            "schedule": 60,
            "args": (),
        },
        "sync-tool-query-logs": {
            "task": "dataworkspace.apps.applications.utils.sync_tool_query_logs",
            "schedule": 60 * 2,
            "args": (),
        },
        "long-running-queries-monitor": {
            "task": "dataworkspace.apps.applications.utils.long_running_query_alert",
            "schedule": 60 * 5,
            "args": (),
        },
        "process-quicksight-dashboard-visualisations": {
            "task": "dataworkspace.apps.datasets.utils.process_quicksight_dashboard_visualisations",
            "schedule": 60 * 5,
            "args": (),
        },
        "push-tool-monitoring-dashboard-datasets": {
            "task": "dataworkspace.apps.applications.utils.push_tool_monitoring_dashboard_datasets",
            "schedule": 60,
            "args": (),
        },
        "link-superset-visualisations-to-related-datasets": {
            "task": "dataworkspace.apps.datasets.utils.link_superset_visualisations_to_related_datasets",
            "schedule": 60 * 5,
            "args": (),
        },
        "update-metadata-with-source-table-id": {
            "task": "dataworkspace.apps.datasets.utils.update_metadata_with_source_table_id",
            "schedule": 60 * 5,
            "args": (),
        },
        "store-custom-dataset-query-metadata": {
            "task": "dataworkspace.apps.datasets.utils.store_custom_dataset_query_metadata",
            "schedule": 60 * 5,
            "args": (),
        },
        "store-reference-dataset-metadata": {
            "task": "dataworkspace.apps.datasets.utils.store_reference_dataset_metadata",
            "schedule": 60 * 5,
            "args": (),
        },
        "refresh-published-chart-data": {
            "task": "dataworkspace.apps.core.charts.tasks.refresh_published_chart_data",
            "schedule": crontab(minute=0, hour=6),
            "args": (),
        },
        "send-notification-emails": {
            "task": "dataworkspace.apps.datasets.utils.send_notification_emails",
            "schedule": 60 * 5,
            "args": (),
        },
        "update-search-popularity": {
            "task": "dataworkspace.apps.datasets.search.update_datasets_average_daily_users",
            "schedule": crontab(minute=30),
            "args": (),
        },
    }

CELERY_REDBEAT_REDIS_URL = env["REDIS_URL"]

PROMETHEUS_DOMAIN = env["PROMETHEUS_DOMAIN"]

GTM_CONTAINER_ID = env.get("GTM_CONTAINER_ID", "")
GTM_CONTAINER_ENVIRONMENT_PARAMS = env.get("GTM_CONTAINER_ENVIRONMENT_PARAMS", "")

AWS_UPLOADS_BUCKET = env["UPLOADS_BUCKET"]
S3_LOCAL_ENDPOINT_URL = env.get("S3_LOCAL_ENDPOINT_URL", "")
STS_LOCAL_ENDPOINT_URL = env.get("STS_LOCAL_ENDPOINT_URL", "")

YOUR_FILES_CONNECT_SRC = [
    APPLICATION_ROOT_DOMAIN,
    "https://s3.eu-west-2.amazonaws.com",
] + ([S3_LOCAL_ENDPOINT_URL] if DEBUG else [])

YOUR_FILES_SCRIPT_SRC = [] + (["http://0.0.0.0:3000", "'unsafe-eval'"] if DEBUG else [])

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

S3_ASSUME_ROLE_POLICY_DOCUMENT = base64.b64decode(
    env["S3_ASSUME_ROLE_POLICY_DOCUMENT_BASE64"]
).decode("utf-8")
S3_POLICY_NAME = env["S3_POLICY_NAME"]
S3_POLICY_DOCUMENT_TEMPLATE = base64.b64decode(env["S3_POLICY_DOCUMENT_TEMPLATE_BASE64"]).decode(
    "utf-8"
)
S3_PERMISSIONS_BOUNDARY_ARN = env["S3_PERMISSIONS_BOUNDARY_ARN"]
S3_ROLE_PREFIX = env["S3_ROLE_PREFIX"]
S3_NOTEBOOKS_BUCKET_ARN = env["S3_NOTEBOOKS_BUCKET_ARN"]
EFS_ID = env["EFS_ID"]

YOUR_FILES_ENABLED = env.get("YOUR_FILES_ENABLED", "False") == "True"


CKEDITOR_CONFIGS = {
    "default": {
        "toolbar": "Custom",
        "enterMode": 3,
        "height": 350,
        "toolbar_Custom": [
            ["Bold", "Italic", "Underline", "CodeSnippet"],
            [
                "NumberedList",
                "BulletedList",
                "-",
                "Outdent",
                "Indent",
                "-",
                "Link",
                "Unlink",
            ],
            ["Format"],
            ["Cut", "Copy", "Paste", "-", "Undo", "Redo"],
        ],
        "format_tags": "p;h2;h3;h4;h5;h6",
        "linkShowAdvancedTab": False,
        "extraPlugins": "codesnippet",
        "codeSnippet_languages": {
            "bash": "Bash",
            "json": "JSON",
            "python": "Python",
            "r": "R",
            "pgsql": "SQL",
        },
    }
}

FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

SEARCH_RESULTS_DATASETS_PER_PAGE = 15

REFERENCE_DATASET_PREVIEW_NUM_OF_ROWS = int(env.get("REFERENCE_DATASET_PREVIEW_NUM_OF_ROWS", 1000))
DATASET_PREVIEW_NUM_OF_ROWS = int(env.get("DATASET_PREVIEW_NUM_OF_ROWS", 10))

# We explicitly allow some environments to not have a connection to GitLab
GITLAB_URL = env.get("GITLAB_URL")
GITLAB_TOKEN = env.get("GITLAB_TOKEN")
GITLAB_VISUALISATIONS_GROUP = env.get("GITLAB_VISUALISATIONS_GROUP")
GITLAB_ECR_PROJECT_ID = env.get("GITLAB_ECR_PROJECT_ID")
GITLAB_ECR_PROJECT_TRIGGER_TOKEN = env.get("GITLAB_ECR_PROJECT_TRIGGER_TOKEN")

GITLAB_URL_FOR_TOOLS = env.get("GITLAB_URL_FOR_TOOLS", "")

DATABASES = {
    "default": {
        "ENGINE": "django_db_geventpool.backends.postgresql_psycopg2",
        "CONN_MAX_AGE": 0,
        **env["ADMIN_DB"],
        "OPTIONS": {"sslmode": "require", "MAX_CONNS": 20},
    },
    **{
        database_name: {
            "ENGINE": "django_db_geventpool.backends.postgresql_psycopg2",
            "CONN_MAX_AGE": 0,
            **database,
            "OPTIONS": {"sslmode": "require", "MAX_CONNS": 100},
            "TEST": {"MIGRATE": False},
        }
        for database_name, database in env["DATA_DB"].items()
    },
}

DATABASES_DATA = {db: db_config for db, db_config in DATABASES.items() if db in env["DATA_DB"]}
# Only used when collectstatic is run
STATIC_ROOT = "/home/django/static/"

# Used when generating URLs for static files, and routed by nginx _before_
# hitting proxy.py, so must not conflict with an analysis application
STATIC_URL = "/__django_static/"


CKEDITOR_BASEPATH = STATIC_URL + "ckeditor/ckeditor/"


REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 100,
}

QUICKSIGHT_USER_REGION = env["QUICKSIGHT_USER_REGION"]
QUICKSIGHT_VPC_ARN = env["QUICKSIGHT_VPC_ARN"]
QUICKSIGHT_DASHBOARD_HOST = (
    "https://eu-west-2.quicksight.aws.amazon.com"  # For proof-of-concept: plan to remove this.
)
QUICKSIGHT_DASHBOARD_GROUP = "DataWorkspace"
QUICKSIGHT_DASHBOARD_EMBEDDING_ROLE_ARN = env["QUICKSIGHT_DASHBOARD_EMBEDDING_ROLE_ARN"]
QUICKSIGHT_SSO_URL = "https://sso.trade.gov.uk/idp/sso/init?sp=aws-quicksight&RelayState=https://quicksight.aws.amazon.com"
QUICKSIGHT_AUTHOR_CUSTOM_PERMISSIONS = "author-custom-permissions"
VISUALISATION_EMBED_DOMAINS = env.get("VISUALISATION_EMBED_DOMAINS", [])

WAFFLE_CREATE_MISSING_FLAGS = True
WAFFLE_FLAG_DEFAULT = bool(strtobool(env.get("WAFFLE_FLAG_DEFAULT", "False")))

WAFFLE_CREATE_MISSING_SWITCHES = True
WAFFLE_SWITCH_DEFAULT = False


# ----------------------
# Data Explorer Settings
# ----------------------
DEFAULT_SCHEMA = env.get("EXPLORER_APP_SCHEMA", "public")

DEBUG_TOOLBAR_CONFIG = {
    "SHOW_COLLAPSED": True,
}

TEMPLATES += [
    {
        "NAME": "ExplorerTemplates",
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "apps", "explorer", "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]


def sort_database_config(database_list):
    config = {}
    for database in database_list:
        config[database["name"]] = database["credentials"]["uri"]
    return config


EXPLORER_CONNECTIONS = json.loads(env.get("EXPLORER_CONNECTIONS", "{}"))
EXPLORER_DEFAULT_CONNECTION = env.get("EXPLORER_DEFAULT_CONNECTION")

EXPLORER_SCHEMA_EXCLUDE_TABLE_PREFIXES = (
    "auth_",
    "contenttypes_",
    "sessions_",
    "admin_",
    "django",
    "dynamic_models",
    "data_explorer",
    "_data_explorer_tmp_query_",
)

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

STATICFILES_DIRS += [
    os.path.join(BASE_DIR, "static", "assets"),
]

ENABLE_DEBUG_TOOLBAR = bool(env.get("ENABLE_DEBUG_TOOLBAR", DEBUG))

EXPLORER_SCHEMA_INCLUDE_VIEWS = False
EXPLORER_SCHEMA_INCLUDE_TABLE_PREFIXES = None

# Celery
CELERY_ACCEPT_CONTENT = ["pickle", "json"]

# date and time formats
en_formats.SHORT_DATE_FORMAT = "d/m/Y"
en_formats.SHORT_DATETIME_FORMAT = "d/m/Y P"


EXPLORER_DEFAULT_ROWS = int(env.get("EXPLORER_DEFAULT_ROWS", 1000))
EXPLORER_QUERY_TIMEOUT_MS = int(env.get("EXPLORER_QUERY_TIMEOUT_MS", 900_000))  # 15 minutes

EXPLORER_DEFAULT_DOWNLOAD_ROWS = int(env.get("EXPLORER_DEFAULT_DOWNLOAD_ROWS", 1000))

EXPLORER_RECENT_QUERY_COUNT = int(env.get("EXPLORER_RECENT_QUERY_COUNT", 10))

EXPLORER_UNSAFE_RENDERING = strtobool(env.get("EXPLORER_UNSAFE_RENDERING", "0"))
EXPLORER_CSV_DELIMETER = env.get("EXPLORER_CSV_DELIMETER", ",")

EXPLORER_DATA_EXPORTERS = [
    ("csv", "dataworkspace.apps.explorer.exporters.CSVExporter"),
    ("excel", "dataworkspace.apps.explorer.exporters.ExcelExporter"),
    ("json", "dataworkspace.apps.explorer.exporters.JSONExporter"),
]

ACTIVITY_STREAM_BASE_URL = env.get("ACTIVITY_STREAM_BASE_URL")
ACTIVITY_STREAM_HAWK_CREDENTIALS_ID = env.get("ACTIVITY_STREAM_HAWK_CREDENTIALS_ID")
ACTIVITY_STREAM_HAWK_CREDENTIALS_KEY = env.get("ACTIVITY_STREAM_HAWK_CREDENTIALS_KEY")

DATASETS_DB_INSTANCE_ID = env.get("DATASETS_DB_INSTANCE_ID", "analysisworkspace-dev-test-1-aurora")
PGAUDIT_LOG_SCOPES = env.get("PGAUDIT_LOG_SCOPES")

VISUALISATION_CLOUDWATCH_LOG_GROUP = env.get("VISUALISATION_CLOUDWATCH_LOG_GROUP")

PGAUDIT_LOG_TYPE = env.get("PGAUDIT_LOG_TYPE", "rds")
POSTGRES_LOG_HEADERS = [
    "log_time",
    "user_name",
    "database_name",
    "process_id",
    "connection_from",
    "session_id",
    "session_line_num",
    "command_tag",
    "session_start_time",
    "virtual_transaction_id",
    "transaction_id",
    "error_severity",
    "sql_state_code",
    "message",
    "detail",
    "hint",
    "internal_query",
    "internal_query_pos",
    "context",
    "query",
    "query_pos",
    "location",
]
PGAUDIT_LOG_HEADERS = [
    "audit_type",
    "statement_id",
    "substatement_id",
    "class",
    "command",
    "object_type",
    "object_name",
    "statement",
    "parameter",
    "connection_from",
]

PGAUDIT_IGNORE_STATEMENTS_RE = [
    r"^SELECT version()(;)?$",
    r"^SELECT current_schema()(;)?$",
    r"^SELECT CAST\('.*?' AS VARCHAR\(\d+\)\) AS \w(;)?$",
    (
        r"^SELECT table_schema, table_name( )?FROM information_schema.tables( )?"
        r"WHERE table_schema not in .*?ORDER BY table_schema, table_name;$"
    ),
    r"^BEGIN(;)?$",
    r"^ROLLBACK(;)?$",
    r"^COMMIT(;)?$",
    r"^FETCH FORWARD \d+ FROM \"\w+\"(;)?$",
    r"^SHOW STANDARD_CONFORMING_STRINGS(;)?$",
    r"^SHOW TRANSACTION ISOLATION LEVEL(;)?$",
    r"^SET STATEMENT_TIMEOUT = \d+(;)?$",
    r"^SET TIMEZONE='\w+'(;)?$",
    r"^SET CLIENT_ENCODING TO '.*?'(;)?$",
]

TOOL_QUERY_LOG_ADMIN_LIST_QUERY_TRUNC_LENGTH = env.get(
    "TOOL_QUERY_LOG_ADMIN_LIST_QUERY_TRUNC_LENGTH", 200
)
TOOL_QUERY_LOG_ADMIN_DETAIL_QUERY_TRUNC_LENGTH = env.get(
    "TOOL_QUERY_LOG_ADMIN_DETAIL_QUERY_TRUNC_LENGTH", 5000
)
TOOL_QUERY_LOG_API_QUERY_TRUNC_LENGTH = env.get(
    "TOOL_QUERY_LOG_API_QUERY_TRUNC_LENGTH",
    TOOL_QUERY_LOG_ADMIN_DETAIL_QUERY_TRUNC_LENGTH,
)

# Feature flags
DATASET_FINDER_ADMIN_ONLY_FLAG = "DATASET_FINDER_ADMIN_ONLY_FLAG"
DATA_CUT_ENHANCED_PREVIEW_FLAG = "DATA-CUT-ENHANCED-PREVIEW"
SUPERSET_FLAG = "SUPERSET-ACCESSIBLE"
DATA_GRID_REFERENCE_DATASET_FLAG = "DATA-GRID-REFERENCE-DATASET"
NOTIFY_ON_MASTER_DATASET_CHANGE_FLAG = "NOTIFY_ON_MASTER_DATASET_CHANGE_FLAG"
NOTIFY_ON_DATACUT_CHANGE_FLAG = "NOTIFY_ON_DATACUT_CHANGE_FLAG"
NOTIFY_ON_REFERENCE_DATASET_CHANGE_FLAG = "NOTIFY_ON_REFERENCE_DATASET_CHANGE_FLAG"
DATASET_CHANGELOG_PAGE_FLAG = "DATASET_CHANGELOG_PAGE"
CHART_BUILDER_BUILD_CHARTS_FLAG = "CHART_BUILDER_BUILD_CHARTS"
CHART_BUILDER_PUBLISH_CHARTS_FLAG = "CHART_BUILDER_PUBLISH_CHARTS"
DATA_UPLOADER_UI_FLAG = "DATA_UPLOADER_UI"
ACCESSIBLE_AUTOCOMPLETE_FLAG = "ACCESSIBLE_AUTOCOMPLETE_FLAG"
SUGGESTED_SEARCHES_FLAG = "SUGGESTED_SEARCHES_FLAG"
COLLECTIONS_FLAG = "COLLECTIONS_FLAG"

DATASET_FINDER_SEARCH_RESULTS_PER_PAGE = 200

SLACK_SENTRY_CHANNEL_WEBHOOK = env.get("SLACK_SENTRY_CHANNEL_WEBHOOK", None)
LONG_RUNNING_QUERY_ALERT_THRESHOLD = env.get("LONG_RUNNING_QUERY_ALERT_THRESHOLD", "15 minutes")

DATAFLOW_IMPORTS_BUCKET_ROOT = "data-flow-imports"
DATAFLOW_API_CONFIG = {
    "DATAFLOW_BASE_URL": env.get("DATAFLOW_BASE_URL"),
    "DATAFLOW_HAWK_ID": env.get("DATAFLOW_HAWK_ID"),
    "DATAFLOW_HAWK_KEY": env.get("DATAFLOW_HAWK_KEY"),
    "DATAFLOW_S3_IMPORT_DAG": env.get("DATAFLOW_S3_IMPORT_DAG"),
    "DATAFLOW_RESTORE_TABLE_DAG": env.get("DATAFLOW_RESTORE_TABLE_DAG"),
}

# We increase this from the default (1000) because we want some datasets to be able to be granted to thousands of users
# This is not an ideal solution, but it is a quite one. A better solution might eventually involve groups of users,
# and granting a single group permissions on a dataset. For our admin dataset permissions, django sends one form field
# per user granted, rather than a single field with e.g. comma-separated users.
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

PROTOCOL = "http://" if LOCAL else "https://"
SUPERSET_DOMAINS = {
    "view": f"{PROTOCOL}superset.{APPLICATION_ROOT_DOMAIN}",
    "edit": f"{PROTOCOL}superset-edit.{APPLICATION_ROOT_DOMAIN}",
    "admin": f"{PROTOCOL}superset-admin.{APPLICATION_ROOT_DOMAIN}",
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

TEAMS_DATA_WORKSPACE_COMMUNITY_URL = env.get("TEAMS_DATA_WORKSPACE_COMMUNITY_URL", "")
DATA_WORKSPACE_ROADMAP_URL = env.get("DATA_WORKSPACE_ROADMAP_URL", "")

CLAMAV_URL = env.get("CLAMAV_URL", "")
CLAMAV_USER = env.get("CLAMAV_USER", "")
CLAMAV_PASSWORD = env.get("CLAMAV_PASSWORD", "")

WEBPACK_STATS_FILE = "react_apps-stats.json" if not DEBUG else "react_apps-stats-hot.json"
WEBPACK_LOADER = {
    "DEFAULT": {
        "CACHE": not DEBUG,
        "BUNDLE_DIR_NAME": "js/bundles",
        "STATS_FILE": os.path.join(BASE_DIR, "static", "js", "stats", WEBPACK_STATS_FILE),
        "POLL_INTERVAL": 0.1,
        "IGNORE": [r".+\.hot-update.js", r".+\.map"],
    }
}

JWT_PRIVATE_KEY = env.get("JWT_PRIVATE_KEY", "")
MLFLOW_PORT = env.get("MLFLOW_PORT", "")
