#!/usr/bin/env bash
# Apply only the documented patch; build it without restarting hardware.
set -euo pipefail
integration_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_root=${1:?Usage: patch_driver.sh /path/to/limo_ros2 /path/to/colcon_workspace}
build_root=${2:?A colcon workspace is required}
cpp="$source_root/limo_base/src/limo_driver.cpp"
header="$source_root/limo_base/include/limo_base/limo_driver.h"
python3 - "$cpp" "$header" <<'PY'
import sys
from pathlib import Path
assert all(Path(p).is_file() for p in sys.argv[1:]), 'LIMO driver source not found'
PY
if python3 "$integration_root/verify_driver.py" "$source_root"; then
  echo 'Required source changes are already present; rebuilding to verify the executable.'
else
  patch --dry-run -d "$source_root" -p1 < "$integration_root/limo-base-watchdog-yaw.patch"
  backup="$source_root/.limo-console-driver-backup-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$backup"
  cp "$cpp" "$header" "$backup/"
  patch -d "$source_root" -p1 < "$integration_root/limo-base-watchdog-yaw.patch"
fi
python3 "$integration_root/verify_driver.py" "$source_root"
set +u
source /control/env.sh
set -u
cd "$build_root"
colcon build --packages-select limo_base --executor sequential --parallel-workers 1
printf 'Built. Restart the base only after saving the map and ending recording.\n'
