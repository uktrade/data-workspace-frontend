#!/bin/bash

set -e

mkdir -p /home/dw/Desktop/
cp /org.qgis.qgis.desktop /home/dw/Desktop/
cp /gretl.desktop /home/dw/Desktop/

tigervncserver -SecurityTypes None -xstartup /usr/bin/lxsession :1

# The webserver for static files that is build into websocketify occasionally
# returns 500s. So we don't use it, and instead serve static files through nginx
nginx -c /nginx.conf

websockify 8886 localhost:5901
