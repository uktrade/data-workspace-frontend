#!/bin/sh

# When on EFS, we expect to not be able to change ownership, and we don't need to
chown -R theia:theia /home/theia

set -e

# Java programs can error if $HOSTNAME is not resolvable
echo "127.0.0.1 $HOSTNAME" >> /etc/hosts

sudo -E -H -u theia yarn theia start /home/theia \
	--plugins=local-dir:/root/plugins \
	--hostname=0.0.0.0 \
	--port=8888 \
	--cache-folder=/tmp/.yarn-cache
