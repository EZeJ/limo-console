#!/bin/bash
set -eo pipefail
source /control/env.sh
mkdir -p /control/logs /control/maps

run() {
    local name="$1"; shift
    if ! tmux has-session -t "=$name" 2>/dev/null; then
        # A container boot and a Mac start request can arrive together.
        tmux new-session -d -s "$name" "bash -lc 'source /control/env.sh; exec $* >> /control/logs/$name.log 2>&1'" || tmux has-session -t "=$name"
    fi
}
halt() {
    if tmux has-session -t "=$1" 2>/dev/null; then
        tmux send-keys -t "$1:" C-c || true
        for i in {1..30}; do
            tmux has-session -t "=$1" 2>/dev/null || return 0
            sleep .1
        done
        tmux kill-session -t "=$1"
    fi
}
stop_motion() {
    python3 - <<'PY'
from urllib.request import Request, urlopen
try:
    urlopen(Request('http://127.0.0.1:8765/stop', data=b'{}', headers={'X-Limo-Control':'1'}), timeout=2).read()
except Exception as e:
    print('Control guard unavailable:', e)
PY
}
base() {
    run scan_filter python3 /control/scan_filter.py
    run recorder python3 /control/recorder_service.py
    run capture python3 /control/camera_service.py
    run guard python3 /control/control_server.py
    run base ros2 launch /control/bringup.launch.py
}
mapping() {
    local engine=slam_toolbox
    [ ! -f /control/mapping-engine ] || read -r engine < /control/mapping-engine
    case "$engine" in
      cartographer) run mapping ros2 launch /control/cartographer.launch.py ;;
      slam_toolbox) run mapping ros2 launch slam_toolbox online_async_launch.py slam_params_file:=/control/slam.yaml use_sim_time:=false ;;
      *) echo 'Unknown mapping engine' >&2; return 1 ;;
    esac
}
case "${1:-status}" in
  map-start)
    case "${2:-cartographer}" in cartographer|slam_toolbox) ;; *) exit 2 ;; esac
    stop_motion
    halt navigation
    halt rviz
    if tmux has-session -t =mapping 2>/dev/null; then
      current=$(cat /control/mapping-engine 2>/dev/null || echo slam_toolbox)
      [ "$current" = "${2:-cartographer}" ] || { echo 'Stop and save the current map before changing engines' >&2; exit 1; }
    fi
    echo "${2:-cartographer}" > /control/mapping-engine
    base
    mapping
    ;;
  map-stop)
    stop_motion
    halt navigation
    halt rviz
    halt mapping
    ;;
  mapping-engine)
    case "${2:-}" in cartographer|slam_toolbox) ;; *) exit 2 ;; esac
    if [ "$2" = cartographer ]; then ros2 pkg prefix cartographer_ros >/dev/null; fi
    stop_motion
    if tmux has-session -t =mapping 2>/dev/null; then
      ros2 run nav2_map_server map_saver_cli -f "/control/maps/before_switch_$(date +%Y%m%d_%H%M%S)" --ros-args -p save_map_timeout:=8.0
    fi
    halt navigation
    halt rviz
    halt mapping
    echo "$2" > /control/mapping-engine
    exec bash /control/manage.sh explore
    ;;
  start) base ;;
  manual)
    stop_motion
    halt navigation
    halt rviz
    base
    ;;
  desktop)
    base
    run display Xvfb :1 -screen 0 1280x800x24 -nolisten tcp -ac
    for i in {1..30}; do [ -S /tmp/.X11-unix/X1 ] && break; sleep .1; done
    run wm openbox
    run vnc x11vnc -display :1 -localhost -rfbport 5901 -forever -shared -nopw -noxdamage
    run web websockify --web /usr/share/novnc 127.0.0.1:6080 127.0.0.1:5901
    frame=odom
    if tmux has-session -t =mapping 2>/dev/null || tmux has-session -t =navigation 2>/dev/null; then frame=map; fi
    run rviz rviz2 -f "$frame"
    ;;
  map)
    stop_motion
    halt navigation
    halt rviz
    base
    mapping
    ;;
  explore)
    stop_motion
    halt rviz
    base
    mapping
    run navigation ros2 launch nav2_bringup navigation_launch.py params_file:=/control/nav2_params.yaml use_sim_time:=false use_composition:=False autostart:=true
    ;;
  save)
    [[ "${2:-}" =~ ^[A-Za-z0-9_-]+$ ]] || { echo 'Use a map name containing letters, numbers, _ or -'; exit 1; }
    [ ! -e "/control/maps/$2.yaml" ] || { echo 'Map already exists; choose a new name'; exit 1; }
    ros2 run nav2_map_server map_saver_cli -f "/control/maps/$2" --ros-args -p save_map_timeout:=15.0
    ;;
  navigate)
    [[ "${2:-}" =~ ^[A-Za-z0-9_-]+$ ]] && [ -f "/control/maps/$2.yaml" ] || { echo 'Saved map not found'; exit 1; }
    stop_motion
    halt mapping
    halt navigation
    halt rviz
    base
    run navigation ros2 launch nav2_bringup bringup_launch.py map:="/control/maps/$2.yaml" params_file:=/control/nav2_params.yaml use_sim_time:=false use_composition:=False autostart:=true
    ;;
  stop) stop_motion ;;
  shutdown)
    stop_motion
    for s in navigation mapping guard recorder capture scan_filter base rviz web vnc wm display; do halt "$s"; done
    ;;
  status) tmux list-sessions ;;
  *) echo 'Commands: start desktop map explore save NAME navigate NAME stop shutdown status'; exit 1 ;;
esac
