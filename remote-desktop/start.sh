#!/bin/bash

set -e

mkdir -p /home/dw/.vnc

# We can't put things in the home directory in the Dockerfile, since the
# home directory is a bound volume, and its contents will disappear
cp /xstartup /home/dw/.vnc/xstartup
cp /passwd /home/dw/.vnc/passwd
chmod 600 /home/dw/.vnc/passwd

mkdir -p /home/dw/Desktop/
cp /org.qgis.qgis.desktop /home/dw/Desktop/

vncserver :1

# The webserver for static files that is build into websocketify occasionally
# returns 500s. So we don't use it, and instead serve static files through nginx
nginx -c /nginx.conf

/usr/bin/websockify 8886 localhost:5901
