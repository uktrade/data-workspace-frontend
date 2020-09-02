import base64

import json
import os
import urllib.request

from celery.schedules import crontab
from sentry_sdk.integrations.django import DjangoIntegration

import sentry
from dataworkspace.utils import normalise_environment

sentry.init_sentry(integration=DjangoIntegration())

env = normalise_environment(os.environ)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENVIRONMENT = env.get("ENVIRONMENT", "Dev")
SECRET_KEY = env['SECRET_KEY']
DEBUG = 'dataworkspace.test' in env['ALLOWED_HOSTS']


def aws_fargate_private_ip():
    with urllib.request.urlopen('http://169.254.170.2/v2/metadata') as response:
        return json.loads(response.read().decode('utf-8'))['Containers'][0]['Networks'][
            0
        ]['IPv4Addresses'][0]


ALLOWED_HOSTS = (
    (env['ALLOWED_HOSTS'])
    if DEBUG
    else (env['ALLOWED_HOSTS'] + [aws_fargate_private_ip()])
)

INTERNAL_IPS = ['127.0.0.1'] if DEBUG else []

ELASTIC_APM_URL = env.get("ELASTIC_APM_URL")
ELASTIC_APM_SECRET_TOKEN = env.get("ELASTIC_APM_SECRET_TOKEN")
ELASTIC_APM = (
    {
        'SERVICE_NAME': 'data-workspace',
        'SECRET_TOKEN': ELASTIC_APM_SECRET_TOKEN,
        'SERVER_URL': ELASTIC_APM_URL,
        'ENVIRONMENT': env.get('ENVIRONMENT', 'development'),
        # 'DEBUG': True,  # Allow APM to send metrics when Django is in debug mode
    }
    if ELASTIC_APM_SECRET_TOKEN
    else {}
)

# Used by `django.contrib.sites`, which enables `django.contrib.redirects`
# https://docs.djangoproject.com/en/3.0/ref/settings/#site-id
SITE_ID = 1

INSTALLED_APPS = [
    'dataworkspace.admin.DataWorkspaceAdminConfig',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.postgres',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',
    'django.contrib.redirects',
    'django.forms',
    'django_better_admin_arrayfield.apps.DjangoBetterAdminArrayfieldConfig',
    'adminsortable2',
    'ckeditor',
    'waffle',
    'rest_framework',
    'dataworkspace.apps.core',
    'dataworkspace.apps.accounts',
    'dataworkspace.apps.catalogue',
    'dataworkspace.apps.applications',
    'dataworkspace.apps.appstream',
    'dataworkspace.apps.datasets',
    'dataworkspace.apps.dw_admin',
    'dataworkspace.apps.api_v1',
    'dataworkspace.apps.eventlog',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'waffle.middleware.WaffleMiddleware',
    'dataworkspace.middleware.disable_client_side_caching',
    'csp.middleware.CSPMiddleware',
    'django.contrib.redirects.middleware.RedirectFallbackMiddleware',
]

if DEBUG:
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')

if ELASTIC_APM:
    INSTALLED_APPS.append('elasticapm.contrib.django')

AUTHENTICATION_BACKENDS = [
    'dataworkspace.apps.accounts.backends.AuthbrokerBackendUsernameIsEmail'
]
AUTHBROKER_URL = env['AUTHBROKER_URL']
AUTHBROKER_CLIENT_ID = env['AUTHBROKER_CLIENT_ID']
AUTHBROKER_CLIENT_SECRET = env['AUTHBROKER_CLIENT_SECRET']
LOGIN_REDIRECT_URL = '/'
APPSTREAM_AWS_SECRET_KEY = os.environ.get('APPSTREAM_AWS_SECRET_KEY')
APPSTREAM_AWS_ACCESS_KEY = os.environ.get('APPSTREAM_AWS_ACCESS_KEY')
APPSTREAM_AWS_REGION = os.environ.get('APPSTREAM_AWS_REGION')
APPSTREAM_STACK_NAME = os.environ.get('APPSTREAM_STACK_NAME')
APPSTREAM_FLEET_NAME = os.environ.get('APPSTREAM_FLEET_NAME')
AWS_ECR_ENDPOINT_URL = os.environ.get('AWS_ECR_ENDPOINT_URL')

ROOT_URLCONF = 'dataworkspace.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': False,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.static',
                'dataworkspace.context_processors.common',
            ],
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
        },
    }
]

WSGI_APPLICATION = 'dataworkspace.wsgi.application'

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO'},
        'app': {'handlers': ['console'], 'level': 'INFO'},
    },
}

# Not all installations have this set
NOTEBOOKS_BUCKET = env.get('NOTEBOOKS_BUCKET', None)
APPSTREAM_URL = env['APPSTREAM_URL']

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env['REDIS_URL'],
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
    }
}

# This deliberately the same as the proxy: it changes the cookie value on
# login, which mitigates the risk of session fixation attack. Using the same
# cookie also means there are fewer cases to consider in terms of cookie
# expiration.
SESSION_COOKIE_NAME = 'data_workspace_session'
root_domain_no_port, _, _ = env['APPLICATION_ROOT_DOMAIN'].partition(':')
SESSION_COOKIE_DOMAIN = root_domain_no_port
SESSION_COOKIE_SECURE = not DEBUG
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_NAME = 'data_workspace_csrf'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# The application template models are populated by environment variables,
# since they can contain very low-level infrastructure details, and it means
# tests don't have to worry about fixtures / editing the database
APPLICATION_TEMPLATES = env['APPLICATION_TEMPLATES']
APPLICATION_ROOT_DOMAIN = env['APPLICATION_ROOT_DOMAIN']
APPLICATION_SPAWNER_OPTIONS = env.get('APPLICATION_SPAWNER_OPTIONS', {})

# CSP Headers
CSP_DEFAULT_SRC = [APPLICATION_ROOT_DOMAIN]
CSP_OBJECT_SRC = ["'none'"]
CSP_UPGRADE_INSECURE_REQUESTS = not DEBUG
CSP_BASE_URI = [APPLICATION_ROOT_DOMAIN]
CSP_FONT_SRC = [APPLICATION_ROOT_DOMAIN, 'data:', 'https://fonts.gstatic.com']
CSP_FORM_ACTION = [APPLICATION_ROOT_DOMAIN, f'*.{APPLICATION_ROOT_DOMAIN}']
CSP_FRAME_ANCESTORS = [APPLICATION_ROOT_DOMAIN]
CSP_IMG_SRC = [
    APPLICATION_ROOT_DOMAIN,
    'data:',
    'https://www.googletagmanager.com',
    'https://www.googletagmanager.com',
    'https://www.google-analytics.com',
    'https://ssl.gstatic.com',
    'https://www.gstatic.com',
]
CSP_SCRIPT_SRC = [
    APPLICATION_ROOT_DOMAIN,
    'https://www.googletagmanager.com',
    'https://www.google-analytics.com',
    'https://tagmanager.google.com',
]
CSP_STYLE_SRC = [
    APPLICATION_ROOT_DOMAIN,
    "'unsafe-inline'",
    'https://tagmanager.google.com',
    'https://fonts.googleapis.com',
]
CSP_INCLUDE_NONCE_IN = ['script-src']


ZENDESK_EMAIL = env['ZENDESK_EMAIL']
ZENDESK_SUBDOMAIN = env['ZENDESK_SUBDOMAIN']
ZENDESK_TOKEN = env['ZENDESK_TOKEN']

ZENDESK_SERVICE_FIELD_ID = env['ZENDESK_SERVICE_FIELD_ID']
ZENDESK_SERVICE_FIELD_VALUE = env['ZENDESK_SERVICE_FIELD_VALUE']


NOTIFY_API_KEY = env['NOTIFY_API_KEY']
FERNET_EMAIL_TOKEN_KEY = env['FERNET_EMAIL_TOKEN_KEY']

NOTIFY_VISUALISATION_ACCESS_REQUEST_TEMPLATE_ID = '7cf395da-2f1b-4084-a526-f2fd68a15491'
NOTIFY_VISUALISATION_ACCESS_GRANTED_TEMPLATE_ID = '139d5e94-1044-49f9-99a9-2a094b8986ea'

CELERY_BROKER_URL = env['REDIS_URL']
CELERY_BEAT_SCHEDULE = {
    'kill-idle-fargate-containers': {
        'task': 'dataworkspace.apps.applications.utils.kill_idle_fargate',
        'schedule': 60 * 10,
        'args': (),
    },
    'populate-created-stopped-fargate-containers': {
        'task': 'dataworkspace.apps.applications.utils.populate_created_stopped_fargate',
        'schedule': 60 * 10,
        'args': (),
    },
    'delete-unused-datasets-users': {
        'task': 'dataworkspace.apps.applications.utils.delete_unused_datasets_users',
        'schedule': 60 * 10,
        'args': (),
    },
    'full-quicksight-permissions-sync': {
        'task': 'dataworkspace.apps.applications.utils.sync_quicksight_permissions',
        'schedule': crontab(minute=17, hour=1),
        'args': (),
    },
}
CELERY_REDBEAT_REDIS_URL = env['REDIS_URL']

PROMETHEUS_DOMAIN = env['PROMETHEUS_DOMAIN']

GTM_CONTAINER_ID = env.get('GTM_CONTAINER_ID', '')
GTM_CONTAINER_ENVIRONMENT_PARAMS = env.get('GTM_CONTAINER_ENVIRONMENT_PARAMS', '')

AWS_UPLOADS_BUCKET = env['UPLOADS_BUCKET']
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

GOOGLE_DATA_STUDIO_CONNECTOR_PATTERN = env['GOOGLE_DATA_STUDIO_CONNECTOR_PATTERN']

S3_ASSUME_ROLE_POLICY_DOCUMENT = base64.b64decode(
    env['S3_ASSUME_ROLE_POLICY_DOCUMENT_BASE64']
).decode('utf-8')
S3_POLICY_NAME = env['S3_POLICY_NAME']
S3_POLICY_DOCUMENT_TEMPLATE = base64.b64decode(
    env['S3_POLICY_DOCUMENT_TEMPLATE_BASE64']
).decode('utf-8')
S3_PERMISSIONS_BOUNDARY_ARN = env['S3_PERMISSIONS_BOUNDARY_ARN']
S3_ROLE_PREFIX = env['S3_ROLE_PREFIX']
EFS_ID = env['EFS_ID']

YOUR_FILES_ENABLED = env.get('YOUR_FILES_ENABLED', 'False') == 'True'


CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'Custom',
        'enterMode': 3,
        'height': 350,
        'toolbar_Custom': [
            ['Bold', 'Italic', 'Underline'],
            [
                'NumberedList',
                'BulletedList',
                '-',
                'Outdent',
                'Indent',
                '-',
                'JustifyLeft',
                'JustifyCenter',
                'JustifyRight',
                'JustifyBlock',
                '-',
                'Link',
                'Unlink',
            ],
            ['Format'],
            ['Cut', 'Copy', 'Paste', '-', 'Undo', 'Redo'],
        ],
        'format_tags': 'div;p;h1;h2;h3;h4;h5;h6',
        'linkShowAdvancedTab': False,
    }
}

FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'

SEARCH_RESULTS_DATASETS_PER_PAGE = 15

REFERENCE_DATASET_PREVIEW_NUM_OF_ROWS = int(
    env.get('REFERENCE_DATASET_PREVIEW_NUM_OF_ROWS', 1000)
)
DATASET_PREVIEW_NUM_OF_ROWS = int(env.get('DATASET_PREVIEW_NUM_OF_ROWS', 10))

# We explicitly allow some environments to not have a connection to GitLab
GITLAB_URL = env.get('GITLAB_URL')
GITLAB_TOKEN = env.get('GITLAB_TOKEN')
GITLAB_VISUALISATIONS_GROUP = env.get('GITLAB_VISUALISATIONS_GROUP')
GITLAB_ECR_PROJECT_ID = env.get('GITLAB_ECR_PROJECT_ID')
GITLAB_ECR_PROJECT_TRIGGER_TOKEN = env.get('GITLAB_ECR_PROJECT_TRIGGER_TOKEN')

DATABASES = {
    'default': {
        'ENGINE': 'django_db_geventpool.backends.postgresql_psycopg2',
        'CONN_MAX_AGE': 0,
        **env['ADMIN_DB'],
        'OPTIONS': {'sslmode': 'require', 'MAX_CONNS': 20},
    },
    **{
        database_name: {
            'ENGINE': 'django_db_geventpool.backends.postgresql_psycopg2',
            'CONN_MAX_AGE': 0,
            **database,
            'OPTIONS': {'sslmode': 'require', 'MAX_CONNS': 100},
            'TEST': {'MIGRATE': False},
        }
        for database_name, database in env['DATA_DB'].items()
    },
}

DATABASES_DATA = {
    db: db_config for db, db_config in DATABASES.items() if db in env['DATA_DB']
}

# Only used when collectstatic is run
STATIC_ROOT = '/home/django/static/'

# Used when generating URLs for static files, and routed by nginx _before_
# hitting proxy.py, so must not conflict with an analysis application
STATIC_URL = '/__django_static/'


CKEDITOR_BASEPATH = STATIC_URL + 'ckeditor/ckeditor/'


REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.CursorPagination',
    'PAGE_SIZE': 100,
}

QUICKSIGHT_USER_REGION = env['QUICKSIGHT_USER_REGION']
QUICKSIGHT_VPC_ARN = env['QUICKSIGHT_VPC_ARN']
QUICKSIGHT_DASHBOARD_HOST = 'https://eu-west-2.quicksight.aws.amazon.com'  # For proof-of-concept: plan to remove this.
QUICKSIGHT_DASHBOARD_GROUP = "DataWorkspace"
QUICKSIGHT_DASHBOARD_EMBEDDING_ROLE_ARN = env['QUICKSIGHT_DASHBOARD_EMBEDDING_ROLE_ARN']
QUICKSIGHT_SSO_URL = (
    "https://sso.trade.gov.uk/idp/sso/init?sp=aws-quicksight"
    "&RelayState=https://quicksight.aws.amazon.com"
)
QUICKSIGHT_AUTHOR_CUSTOM_PERMISSIONS = 'author-custom-permissions'

WAFFLE_CREATE_MISSING_SWITCHES = True
WAFFLE_SWITCH_DEFAULT = False
