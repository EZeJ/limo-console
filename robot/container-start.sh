#!/bin/bash
# Container startup always creates a disarmed command guard.
set -e
bash /control/manage.sh start
exec sleep infinity
