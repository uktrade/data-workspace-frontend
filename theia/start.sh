#!/bin/bash

set -e

chown -R theia:theia /home/theia

sudo --user theia \
  yarn theia start /home/theia \
  --plugins=local-dir:/root/plugins \
  --hostname=0.0.0.0  \
  --port=8888 \
  --cache-folder=/tmp/.yarn-cache
