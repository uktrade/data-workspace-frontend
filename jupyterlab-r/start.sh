#!/bin/sh

set -e

chown -R jovyan:jovyan /home/jovyan

sudo -E -H -u jovyan /opt/conda/bin/jupyter \
    lab \
    --config=/etc/jupyter/jupyter_notebook_config.py \
    --NotebookApp.token='' \
    --NotebookApp.ip='0.0.0.0' \
    --NotebookApp.allow_remote_access=True \
    --NotebookApp.port=8888
