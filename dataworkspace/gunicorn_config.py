from psycogreen.gevent import (
    patch_psycopg,
)

bind = '127.0.0.1:8002'
worker_class = 'gevent'
workers = 1
worker_connections = 1024


def post_fork(_, __):
    patch_psycopg()
