from psycogreen.gevent import (
	patch_psycopg,
)

bind = 'unix:/home/django/nginx_gunicorn_socket'
worker_class = 'gevent'
workers = 1
worker_connections = 1024

def post_fork(_, __):
    patch_psycopg()
