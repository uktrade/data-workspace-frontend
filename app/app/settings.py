import json
import os
import urllib.request

from app.utils import normalise_environment

env = normalise_environment(os.environ)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = env['SECRET_KEY']
DEBUG = 'localapps.com' in env['ALLOWED_HOSTS']


def aws_fargate_private_ip():
    with urllib.request.urlopen('http://169.254.170.2/v2/metadata') as response:
        return json.loads(response.read().decode('utf-8'))['Containers'][0]['Networks'][0]['IPv4Addresses'][0]


ALLOWED_HOSTS = \
    (env['ALLOWED_HOSTS']) if DEBUG else \
    (env['ALLOWED_HOSTS'] + [aws_fargate_private_ip()])

INTERNAL_IPS = ['127.0.0.1'] if DEBUG else []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'app.apps.JupyterHubDataAuthAdminAppConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'app.middleware.disable_client_side_caching',
]

AUTHENTICATION_BACKENDS = [
    'app.backends.AuthbrokerBackendUsernameIsEmail',
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

ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.contrib.messages.context_processors.messages',
                'app.context_processors.common',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'

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
            'OPTIONS': {'sslmode': 'require', 'MAX_CONNS': 20},
        }
        for database_name, database in env['DATA_DB'].items()
    }
}

DATABASES_DATA = env['DATA_DB']

AUTH_PASSWORD_VALIDATORS = [
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'app': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}

# Not all installations have this set
NOTEBOOKS_BUCKET = env.get('NOTEBOOKS_BUCKET', None)
APPSTREAM_URL = env['APPSTREAM_URL']

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env['REDIS_URL'],
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    },
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

# Only used when collectstatic is run
STATIC_ROOT = '/home/django/static/'

# Used when generating URLs for static files, and routed by nginx _before_
# hitting proxy.py, so must not conflict with an analysis application
STATIC_URL = '/__django_static/'

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# The application template models are populated by environment variables,
# since they can contain very low-level infrastructure details, and it means
# tests don't have to worry about fixtures / editing the database
APPLICATION_TEMPLATES = env['APPLICATION_TEMPLATES']
APPLICATION_ROOT_DOMAIN = env['APPLICATION_ROOT_DOMAIN']

ZENDESK_EMAIL = env['ZENDESK_EMAIL']
ZENDESK_SUBDOMAIN = env['ZENDESK_SUBDOMAIN']
ZENDESK_TOKEN = env['ZENDESK_TOKEN']

ZENDESK_SERVICE_FIELD_ID = env['ZENDESK_SERVICE_FIELD_ID']
ZENDESK_SERVICE_FIELD_VALUE = env['ZENDESK_SERVICE_FIELD_VALUE']

CELERY_BROKER_URL = env['REDIS_URL']
CELERY_BEAT_SCHEDULE = {
    'kill-idle-fargate-containers': {
        'task': 'app.shared.kill_idle_fargate',
        'schedule': 60 * 10,
        'args': (),
    },
}
CELERY_REDBEAT_REDIS_URL = env['REDIS_URL']

PROMETHEUS_DOMAIN = env['PROMETHEUS_DOMAIN']

GOOGLE_ANALYTICS_SITE_ID = env['GOOGLE_ANALYTICS_SITE_ID']
AWS_DEFAULT_REGION = env['AWS_DEFAULT_REGION']
AWS_ACCESS_KEY_ID = env['AWS_ACCESS_KEY_ID']
AWS_SECRET_ACCESS_KEY = env['AWS_SECRET_ACCESS_KEY']
AWS_UPLOADS_BUCKET = env['UPLOADS_BUCKET']
