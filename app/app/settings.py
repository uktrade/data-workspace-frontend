import json
import os
import urllib.request

from app.utils import normalise_environment

env = normalise_environment(os.environ)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = env['SECRET_KEY']
DEBUG = env['ALLOWED_HOSTS'] == ['localhost']

def aws_fargate_private_ip():
    with urllib.request.urlopen('http://169.254.170.2/v2/metadata') as response:
        return json.loads(response.read().decode('utf-8'))['Containers'][0]['Networks'][0]['IPv4Addresses'][0]

ALLOWED_HOSTS = \
    env['ALLOWED_HOSTS'] if DEBUG else \
    env['ALLOWED_HOSTS'] + [aws_fargate_private_ip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'govuk_template_base',
    'govuk_template',
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
                'govuk_template_base.context_processors.govuk_template_base',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        **env['ADMIN_DB'],
        'OPTIONS': {'sslmode': 'require'},
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
NOTEBOOKS_URL = env['NOTEBOOKS_URL']
SUPPORT_URL = env['SUPPORT_URL']

SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_NAME = 'analysis_workspace_admin_session'

CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_NAME = 'analysis_workspace_admin_csrf'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Only used when collectstatic is run
STATIC_ROOT = '/home/django/static/'

# Used when generating URLs for static files
STATIC_URL = '/static/'

GOVUK_SERVICE_SETTINGS = {
    'name': 'Analysis Workspace',
    'phase': 'alpha',
    'header_link_view_name': 'root',
    'header_links': [],
}
