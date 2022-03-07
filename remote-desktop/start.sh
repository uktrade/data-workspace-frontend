#!/bin/bash

set -e

echo "127.0.0.1 $HOSTNAME" >> /etc/hosts

mkdir -p /home/dw/Desktop/
cp /org.qgis.qgis.desktop /home/dw/Desktop/
cp /gretl.desktop /home/dw/Desktop/

cd /home/dw
export XDG_RUNTIME_DIR=/tmp/runtime-dw
sudo -E -H -u dw \
	tigervncserver -SecurityTypes None -xstartup /usr/bin/startlxqt :1

# The webserver for static files that is build into websocketify occasionally
# returns 500s. So we don't use it, and instead serve static files through nginx
nginx -c /nginx.conf

sudo -E -H -u dw \
	websockify 8886 localhost:5901
