import sys

from dataworkspace.settings.base import *


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'dataworkspace',
        'USER': 'postgres',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '5432',
    },
    **{
        database_name: {
            'ENGINE': 'django_db_geventpool.backends.postgresql_psycopg2',
            'NAME': 'dataworkspace',
            'HOST': 'localhost',
            'USER': 'postgres',
            'PASSSWORD': '',
            'PORT': '5432',
        }
        for database_name, database in env['DATA_DB'].items()
    }
}

STATIC_URL = '/static/'
