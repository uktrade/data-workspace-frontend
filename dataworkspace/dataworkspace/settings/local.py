import sys

from dataworkspace.settings.base import *


TESTING = len(sys.argv) > 1 and sys.argv[1] == 'test'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'dataworkspace',
        'USER': 'postgres',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
