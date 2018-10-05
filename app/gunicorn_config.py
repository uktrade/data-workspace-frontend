import os
import subprocess

keyfile = os.environ['KEYFILE']
certfile = os.environ['CERTFILE']
bind = '0.0.0.0:8000'
workers = 4
