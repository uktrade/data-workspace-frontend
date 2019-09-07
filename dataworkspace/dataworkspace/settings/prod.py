from dataworkspace.settings.base import *


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
        }
        for database_name, database in env['DATA_DB'].items()
    }
}

# Only used when collectstatic is run
STATIC_ROOT = '/home/django/static/'

# Used when generating URLs for static files, and routed by nginx _before_
# hitting proxy.py, so must not conflict with an analysis application
STATIC_URL = '/__django_static/'
