import os
import subprocess

keyfile = os.environ['HOME'] + '/ssl.key'
certfile = os.environ['HOME'] + '/ssl.crt'
subprocess.check_call([
    'openssl', 'req', '-new', '-newkey', 'rsa:2048', '-days', '3650', '-nodes', '-x509',
    '-subj', '/CN=selfsigned',
    '-keyout', keyfile,
    '-out', certfile,
], env={'RANDFILE': os.environ['HOME'] + '/openssl_rnd'})

bind = '0.0.0.0:8000'
workers = 4
