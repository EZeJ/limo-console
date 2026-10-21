#!/usr/bin/env bash
set -euo pipefail
console_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ $# -lt 1 ]]; then echo 'Usage: scripts/connect.sh USER@ROBOT_HOST [companion options]' >&2; exit 2; fi
robot_target=$1; shift
cd "$console_root"
if [[ ! -x .venv/bin/python ]]; then
  python_bin=${LIMO_PYTHON:-python3}
  "$python_bin" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required; set LIMO_PYTHON"'
  "$python_bin" -m venv .venv
fi
if ! .venv/bin/python -c 'import av, mcap, numpy, PIL' 2>/dev/null; then
  .venv/bin/python -m pip install -r requirements-companion.txt
fi
exec .venv/bin/python -m companion.server --ssh "$robot_target" "$@"
