# Installation and configuration

[中文](installation.zh-CN.md) · [Back to README](../README.md)

## Supported environment

The integration was exercised with a LIMO running ROS 2 Humble inside an Ubuntu 22.04 environment on an ARM64 Jetson. The host OS may differ if ROS runs in a container. The console is not a ROS 1 application. Other distributions, cameras, steering modes, or driver builds need integration testing.

Start with a working [AgileX LIMO ROS 2 workspace](https://github.com/agilexrobotics/limo_ros2/tree/humble). Install Humble using the [official ROS installation instructions](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html). This repository does not install firmware or build the vendor workspace.

Required packages and tools in the ROS environment:

- Python 3.10+, Pillow, Bash, and tmux.
- `rclpy`, ROS standard messages/services/actions, `limo_msgs`, `limo_base`, and `tf2_ros`.
- `v4l2_camera`, `ydlidar_ros2_driver`, and `rmw_cyclonedds_cpp`.
- Nav2 and `nav2_bringup`, even for the current manual-only server: its modules import Nav2 interfaces at startup.
- Cartographer ROS and/or SLAM Toolbox for mapping. The default mapping action selects Cartographer.
- Optional desktop only: RViz2, Xvfb, Openbox, x11vnc, websockify, and noVNC.

After configuring ROS apt sources, the common Ubuntu dependencies can be installed with:

```sh
sudo apt-get update
sudo apt-get install python3-pil tmux \
  ros-humble-navigation2 ros-humble-nav2-bringup \
  ros-humble-cartographer-ros ros-humble-slam-toolbox \
  ros-humble-v4l2-camera ros-humble-rmw-cyclonedds-cpp
```

The vendor workspace must provide the LIMO messages, base driver, and lidar driver; these are not substituted with pip packages.

## Install into the ROS environment

Clone or copy **this repository** into the robot's ROS environment, then run:

```sh
sudo bash scripts/install.sh
```

In an existing container, run the installer as root inside that container. `/control` must be inside that environment and must persist across container recreation, for example through a dedicated bind mount or volume. Do not bind the entire personal workspace or home directory.

The installer copies only console source and configuration. It starts no processes. It backs up replaced source files under `/control/.backup-install-TIMESTAMP/` and leaves maps, scan preference, selected mapping engine, and speed settings intact. For an upgrade, stop driving first and stop the existing guard before replacing its files. Keep the SLAM process running if you need to preserve its live map.

The service account needs read/write access to `/control` (for state, map, and log files), serial-device access, and camera access. Choose ownership and device permissions appropriate to your deployment.

## Review configuration before starting

| File | Purpose / defaults |
| --- | --- |
| `robot/env.sh` | Humble at `/opt/ros/humble`; vendor overlay from `LIMO_ROS_SETUP`, default `/root/workspace/install/setup.bash`; ROS domain defaults to `42`; localhost-only DDS |
| `robot/bringup.launch.py` | Chassis serial `ttyTHS1`; camera `/dev/video0`, RGB 640×480; transforms for the tested sensor mounting |
| `robot/lidar.yaml` | Lidar serial path and scanner settings; verify them against your model |
| `robot/cartographer.lua` | Cartographer 2D SLAM tuning |
| `robot/slam.yaml` | SLAM Toolbox tuning |
| `robot/nav2_params.yaml` | Robot footprint, obstacle layers, planner/controller limits, and return controllers |
| `robot/navigate.xml` | Navigation behavior tree with replanning and path following |
| `robot/cyclonedds.xml` | Local DDS peer discovery |

Override a different overlay **before** starting the services:

```sh
export LIMO_ROS_SETUP=/path/to/limo_ws/install/setup.bash
export ROS_DOMAIN_ID=42
source /control/env.sh
```

Persist those environment variables in your own service or container configuration. The UI/server ports are intentionally fixed: robot HTTP `8765`, local tunnel `18765`; optional robot desktop `6080`, local tunnel `16080`. If you change these, update the HTTP Host allowlist and tunnel together. A remote LAN URL is deliberately rejected.

### Required motion integration

`bringup.launch.py` remaps the base driver's `/cmd_vel` subscription to `/limo/cmd_vel`. Nav2 publishes `/cmd_vel`; the console gate checks it and publishes the final `/limo/cmd_vel`. No other node should bypass that gate.

The chassis driver must independently send zero velocity if command updates stop. The tested driver had a 350 ms timeout. The console cannot enforce a stop if its own process or the computer fails; a stock vendor driver may need this watchdog added separately. Confirm driver behavior before enabling movement. Vendor driver patches and firmware are outside this repository.

Lidar pause/resume expects `/start_scan` and `/stop_scan` as `std_srvs/Empty`, with a driver that remains responsive to both while paused. The `start_paused` launch parameter is an optional extension of the tested driver; stock versions may ignore it. The server re-applies saved pause intent through the services after startup. Support for these services and physical motor control is driver-dependent.

Camera parameters (`gain`, `gamma`, `brightness`, auto exposure, and 60 Hz anti-flicker) reflect one tested camera. Review V4L2 controls and local lighting frequency; unsupported controls or excessive gain can make another camera look worse.

## Start and connect

On the robot:

```sh
bash /control/manage.sh start
bash /control/manage.sh status
```

Expected tmux sessions are `guard` and `base`. The guard starts disarmed. Check the loopback endpoint from the same environment:

```sh
curl --fail http://127.0.0.1:8765/status
```

On your computer:

```sh
./scripts/tunnel.sh USER@ROBOT_HOST
```

Keep that terminal open, then visit **http://127.0.0.1:18765/**. SSH manages authentication; no password is stored by the helper. If a local port is occupied, close the previous tunnel before retrying. Do not blindly terminate unrelated SSH sessions.

The optional desktop link needs the optional desktop packages and the second tunnel. It stops driving before launching the desktop services.

## Stop, update, and recover

- `bash /control/manage.sh stop`: stop motion; sensors and mapping may remain running.
- `bash /control/manage.sh shutdown`: stop motion and all console-managed tmux sessions, including mapping. Save the map first.
- To update: save your map, stop services, run the installer from the new checkout, review config changes, then start again. Saved user settings are preserved.
- To roll back: with services stopped, restore source/configuration from the install backup, then restart. Do not overwrite current map/state files with unrelated backups.

Logs are written under `/control/logs/`. Runtime state and maps are private deployment data; they are ignored by version control and should not be attached to public issues without review.
