import json
import os
import urllib.request

from app.utils import normalise_environment

env = normalise_environment(os.environ)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = env['SECRET_KEY']
DEBUG = False

def aws_fargate_private_ip():
    with urllib.request.urlopen('http://169.254.170.2/v2/metadata') as response:
        return json.loads(response.read().decode('utf-8'))['Containers'][0]['Networks'][0]['IPv4Addresses'][0]

ALLOWED_HOSTS = \
    env['ALLOWED_HOSTS'] if env['ALLOWED_HOSTS'] == ['localhost'] else \
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
    'authbroker_client',
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
LOGIN_REDIRECT_URL = '/admin'

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

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Only used when collectstatic is run
STATIC_ROOT = '/home/django/static/'

# Used when generating URLs for static files
STATIC_URL = '/static/'
