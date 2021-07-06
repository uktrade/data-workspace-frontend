import os

from gunicorn import SERVER_SOFTWARE
from gunicorn.http import wsgi
from gunicorn.http.wsgi import FileWrapper, WSGIErrorsWrapper

reload = True
workers = 1


def patched_base_environ(cfg):
    return {
        'wsgi.errors': WSGIErrorsWrapper(cfg),
        'wsgi.version': (1, 0),
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
        'wsgi.file_wrapper': FileWrapper,
        'wsgi.input_terminated': True,
        'SERVER_SOFTWARE': SERVER_SOFTWARE,
        'HTTP_SSO_PROFILE_USER_ID': os.environ['HTTP_SSO_PROFILE_EMAIL'],
        'HTTP_SSO_PROFILE_EMAIL': os.environ['HTTP_SSO_PROFILE_EMAIL'],
        'HTTP_SSO_PROFILE_FIRST_NAME': os.environ['HTTP_SSO_PROFILE_FIRST_NAME'],
        'HTTP_SSO_PROFILE_LAST_NAME': os.environ['HTTP_SSO_PROFILE_LAST_NAME'],
        'HTTP_CREDENTIALS_DB_HOST': os.environ['DB_HOST'],
        'HTTP_CREDENTIALS_DB_USER': os.environ['DB_USER'],
        'HTTP_CREDENTIALS_DB_NAME': os.environ['DB_NAME'],
        'HTTP_CREDENTIALS_DB_PASSWORD': os.environ['DB_PASSWORD'],
        'HTTP_CREDENTIALS_DB_PORT': os.environ['DB_PORT'],
        'HTTP_DASHBOARDS': os.environ.get('DASHBOARDS', ''),
    }


wsgi.base_environ = patched_base_environ
