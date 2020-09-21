#!/bin/bash

source ./dataworkspace/dataworkspace/apps/explorer/scripts/functions.sh

# Install dockerize https://github.com/jwilder/dockerize
run "wget https://github.com/jwilder/dockerize/releases/download/v0.6.1/dockerize-linux-amd64-v0.6.1.tar.gz"
run "tar -C /usr/local/bin -xzvf dockerize-linux-amd64-v0.6.1.tar.gz"
