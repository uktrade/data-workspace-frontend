import os

from gunicorn import SERVER_SOFTWARE
from gunicorn.http import wsgi
from gunicorn.http.wsgi import FileWrapper, WSGIErrorsWrapper

reload = True
workers = 1


def dummy_base_environ(cfg):
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
    }


wsgi.base_environ = dummy_base_environ
