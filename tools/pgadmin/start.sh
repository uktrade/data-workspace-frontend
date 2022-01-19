#!/bin/sh

chown -R pgadmin:pgadmin /home/pgadmin

set -e

# Typically, we use set the owner of files/folders (not in the home directory)
# in the Dockerfile. However, we've changed the ID of the pgadmin user,
# and changing to the same owner but a different ID doesn't seem to get
# properly saved when done from the Dockerfile. So, we do it here.
touch /pgadmin4/.pgpass /pgadmin4/servers.json
chown -R pgadmin:pgadmin \
	/pgadmin4/config_distro.py \
	/pgadmin4/.pgpass \
	/pgadmin4/servers.json \
	/var/lib/pgadmin \
	/var/log/pgadmin

sudo -E -H -u pgadmin python3 /disable_activity.py &
sudo -E -H -u pgadmin /entrypoint.sh
