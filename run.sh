#!/bin/bash

# NOTE this file should be +x for owner and group (-rwxr-xr--)
# The umask is necessary so that the socket file created (/tmp/um/um_1.sock, below) is read/writeable by group, as nginx user (www-data) belongs to ohs group, in order to accomplish this

cd /home/ohs/um/um
export PATH="/home/ohs/um/ve/bin"
export PYTHONPATH="/home/ohs/um/um"
umask 0002

python -m aiohttp.web --path=/tmp/um/um_1.sock app.main:init
