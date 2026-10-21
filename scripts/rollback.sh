#!/usr/bin/env bash
# Run inside the ROS environment after explicitly ending recording and mapping.
set -euo pipefail
backup=${1:?Usage: rollback.sh /control/.backup-install-TIMESTAMP}
[[ "$backup" =~ ^/control/\.backup-install-[0-9-]+$ && -d "$backup" ]] || exit 2
python3 - <<'PY'
import json,urllib.request
s=json.load(urllib.request.urlopen('http://127.0.0.1:8765/status'))
assert s['mode']=='stopped' and not s['recording']['active'] and not s['mapping']['active'], 'Stop, end recording, and save/finish mapping first'
PY
bash /control/manage.sh shutdown
cp -a "$backup/." /control/
bash /control/manage.sh start
