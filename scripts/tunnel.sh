#!/usr/bin/env bash
# Only localhost listeners are opened. SSH prompts for credentials as usual.
set -euo pipefail
if [[ $# != 1 || "$1" == -* || "$1" != *@* ]]; then
  echo 'Usage: ./scripts/tunnel.sh USER@ROBOT_HOST' >&2
  exit 2
fi
exec ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 \
  -L 127.0.0.1:18765:127.0.0.1:8765 \
  -L 127.0.0.1:16080:127.0.0.1:6080 "$1"
