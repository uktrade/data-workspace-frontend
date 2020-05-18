#!/bin/sh

# When on EFS, we expect to not be able to change ownership, and we don't need to
chown -R jovyan:jovyan /home/jovyan

set -e

sudo -E -H -u jovyan /opt/conda/bin/jupyter \
	lab \
	--config=/etc/jupyter/jupyter_notebook_config.py \
	--NotebookApp.token='' \
	--NotebookApp.ip='0.0.0.0' \
	--NotebookApp.allow_remote_access=True \
	--NotebookApp.port=8888
