#!/bin/sh

set -e

python3 set-dhcp.py
python3 nameserver.py
