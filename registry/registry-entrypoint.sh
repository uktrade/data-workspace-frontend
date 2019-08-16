#!/bin/sh

# Based on https://github.com/docker/distribution-library-image/, but generating a
# self-signed certificate on launch

set -e

openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -subj /CN=selfsigned \
    -keyout $HOME/ssl.key \
    -out $HOME/ssl.crt
chmod 0600 $HOME/ssl.key $HOME/ssl.crt

exec tini -- "$@"
