# Architecture and API

[中文](architecture.zh-CN.md) · [README](../README.md)

## Control path

```text
Browser (localhost:18765)
        │ SSH tunnel / JSON HTTP
        ▼
control_server.py (robot loopback:8765)
        ├── Camera JPEG, lidar points, map PNG, telemetry
        ├── Manual limits + command gate ──► /limo/cmd_vel ──► base driver
        └── Mapping / navigation manager
                 ├── SLAM ──► /map
                 └── Nav2 ──► /cmd_vel ──► command gate
```

The static HTML/CSS/JavaScript UI has no framework, analytics, CDN, or remote translation service. `messages.js` contains the English-to-Chinese catalog; `i18n.js` owns language choice and DOM updates. The ROS server emits canonical English messages, while status fields and enumeration values stay language-neutral.

`Control` is an `rclpy.Node` with a reentrant lock shared with request handlers. Its 20 Hz timer publishes gated velocity. `ThreadingHTTPServer` handles requests in another thread. Slow mapping operations run in a worker so they do not block the control timer. Nav2 goals use ROS actions; the browser keeps a mission identifier for heartbeat ownership.

## ROS integration

| Interface | Type | Direction / purpose |
| --- | --- | --- |
| `/limo_status` | `limo_msgs/msg/LimoStatus` | Read chassis mode, errors, and battery |
| `/odom` | `nav_msgs/msg/Odometry` | Read pose and measured velocity |
| `/scan` | `sensor_msgs/msg/LaserScan` | Read scan points and clearance |
| `/camera/image_raw` | `sensor_msgs/msg/Image` | Read RGB/BGR frames |
| `/map` | `nav_msgs/msg/OccupancyGrid` | Read SLAM map with transient-local QoS |
| `/plan` | `nav_msgs/msg/Path` | Read active navigation path |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | Read Nav2 commands before gating |
| `/limo/cmd_vel` | `geometry_msgs/msg/Twist` | Publish final guarded chassis commands |
| `/start_scan`, `/stop_scan` | `std_srvs/srv/Empty` | Driver pause/resume requests |
| `/navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | Goal navigation |
| `/follow_path` | `nav2_msgs/action/FollowPath` | Recorded-route return |
| `/compute_path_to_pose` | `nav2_msgs/action/ComputePathToPose` | Exploration preflight |

Navigation also queries lifecycle state for `controller_server`, `planner_server`, and `bt_navigator`, and uses the `map → odom` TF transform. Review sensor mounting transforms in `bringup.launch.py` for your robot.

## Command gate and timeouts

| Condition | Current behavior |
| --- | --- |
| Explicit stop, mode change, speed save | Disarm and discard the old command |
| Lease older than 0.6 s | Stop and require re-arming |
| Command older than 0.3 s | Output zero while waiting for commands |
| Chassis status older than 1 s | Stop and require re-arming |
| Manual camera older than 2 s | Stop and require re-arming |
| Navigation scan older than 1 s | Stop and require re-arming |
| Browser camera older than 1.5 s | Browser requests stop |
| Chassis pause, wrong control mode, or error | Output zero; behavior depends on condition |

Manual output is clamped to user-selected limits. Navigation has independent 0.50 m/s forward, 0.05 m/s reverse, and 0.30 rad/s caps, plus clearance-based reductions. These are software limits, not guarantees of braking performance. The browser sends requests approximately every 100 ms; a healthy session is required for continued movement. A separate chassis-driver timeout is mandatory for process/computer failure handling.

The `/arm` API does not establish exclusive authorization across arbitrary clients. Use one trusted operator/browser session at a time. The interface is not intended for untrusted multi-user access.

## HTTP API

All endpoints are on the robot's loopback port `8765`, forwarded to computer loopback port `18765`. Allowed Host values are `127.0.0.1:8765`, `127.0.0.1:18765`, and `localhost:18765`. POST requires JSON, header `X-Limo-Control: 1`, and a matching Origin when supplied. Request bodies are limited to 1024 bytes. These checks complement SSH access; they are not user authentication.

### Reads

| GET | Response |
| --- | --- |
| `/status` | Mode, output, chassis/odometry, sensor freshness, speed settings, lidar, mapping, compact navigation state |
| `/scan` | Display points, online flag, lidar state, front/rear clearance |
| `/camera.jpg` | Fresh camera JPEG; 503 if unavailable/stale |
| `/navigation` | Full navigation state, map metadata, trail, plan, mission and exploration state |
| `/map.png?v=REVISION` | Map image; 409 when metadata revision changed, 503 before a map exists |
| `/maps` | Saved complete PGM/YAML map pairs |
| `/maps/download?name=NAME` | ZIP with a relative YAML image path |

### Writes

| POST | JSON body | Effect |
| --- | --- | --- |
| `/stop` | `{}` | Stop and disarm; cancel navigation |
| `/arm` | `{"mode":"manual"}` | Arm after readiness checks |
| `/drive` | `{"x":0.0,"z":0.0}` | Linear m/s and angular rad/s command; refresh manual lease |
| `/heartbeat` | `{"mission_id":"…"}` | Refresh the matching navigation mission lease |
| `/manual/speed` | `{"forward":0.1,"reverse":0.05,"angular":0.3}` | Stop, validate, persist limits; omitted angular preserves its current value |
| `/lidar/pause`, `/lidar/resume` | `{}` | Stop; asynchronously change scan state |
| `/mapping/start` | `{"backend":"cartographer"}` | Stop; start selected SLAM backend (`slam_toolbox` also accepted) |
| `/mapping/save` | `{"name":"room_01"}` | Stop; save a new map; null/omitted name generates a name |
| `/mapping/stop` | `{}` | Save a fresh map first, then stop SLAM |
| `/navigation/prepare` | `{}` or `{"backend":"cartographer"}` | Start mapping/Nav2 or switch engine; may reset the mapping session |
| `/navigation/goal` | `{"x":0.0,"y":0.0}` | Navigate to a validated map-frame goal |
| `/navigation/explore` | `{}` | Begin bounded frontier exploration |
| `/navigation/return` | `{"mode":"auto"}` | Follow recorded route; modes `auto`, `forward`, `reverse` |
| `/desktop` | `{}` | Stop; start optional local desktop services |

Mutation responses normally return a status snapshot. Async requests report acceptance through `busy`/`preparing`; poll until completion and inspect `error`. An HTTP 200 alone does not prove a physical device action completed. Validation errors return HTTP 400 with `{"error":"…"}`; rejected Host/Origin/header checks return HTTP 403.

A harmless status request through the tunnel:

```sh
curl --fail http://127.0.0.1:18765/status
```

Do not issue nonzero drive commands merely to test connectivity.

## Files and lifecycle

Runtime files live under `/control`: `manual-speed.json`, `lidar-state.json`, `mapping-engine`, `maps/`, and `logs/`. They are not source files. Speed/scan settings use temporary-file replacement. Map downloads validate names, reject symlinks/traversal, require complete pairs, and limit file size. Save collisions are rejected.

`manage.sh` manages tmux sessions `guard`, `base`, `mapping`, and `navigation`, plus optional desktop sessions. Map lifecycle and autonomous mission state are separate: stopping navigation can leave SLAM updating. A guard restart preserves disk settings but resets in-memory navigation ownership and the recorded return trail. A full SLAM restart does not restore an unsaved live SLAM session.

## Verification boundary

Hardware-free tests cover gate limits and watchdogs, scan state transitions, export/path validation, map-save failure behavior, language placeholders, and DOM element wiring. They do not certify stopping distances, motor shutdown, localization quality, or all Nav2/driver combinations. The preview uses synthetic inputs and cannot establish hardware compatibility.
