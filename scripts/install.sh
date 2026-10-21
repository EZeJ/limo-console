#!/usr/bin/env bash
# Run inside the robot's ROS 2 environment. This installs files but starts no motors.
set -euo pipefail
console_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ${EUID} != 0 ]]; then
  echo 'Run with sudo (or as root inside the ROS container) to install into /control.' >&2
  exit 1
fi
mkdir -p /control/web /control/logs /control/maps
python3 -m pip install -r "$console_root/requirements-recorder.txt"
backup_dir="/control/.backup-install-$(date +%Y%m%d-%H%M%S)"
# Keep an exact backup of replaced source files. Never overwrite saved runtime settings.
for source in "$console_root"/robot/*.{py,sh,yaml,lua,xml} "$console_root"/robot/web/*; do
  [[ -f "$source" ]] || continue
  relative=${source#"$console_root/robot/"}
  destination="/control/$relative"
  if [[ -f "$destination" ]]; then
    mkdir -p "$backup_dir/$(dirname "$relative")"
    cp -p -- "$destination" "$backup_dir/$relative"
  fi
  install -m 644 -- "$source" "$destination"
done
mkdir -p /control/integration "$backup_dir"
cp -a /control/integration "$backup_dir/"
cp -a "$console_root/robot/integration/." /control/integration/
chmod +x /control/manage.sh /control/container-start.sh
printf 'Installed in /control. Existing runtime settings were preserved.\n'
printf 'Review the configuration and driver watchdog before starting.\n'
