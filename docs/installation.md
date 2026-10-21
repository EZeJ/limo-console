# Installation and deployment

[中文](installation.zh-CN.md) · [README](../README.md)

## Prerequisites

Robot: Ubuntu 22.04, ROS 2 Humble, Python 3.10+, Pillow, tmux, an existing LIMO vendor workspace and serial/camera permissions. Required ROS packages include `limo_base`, `limo_msgs`, `ydlidar_ros2_driver`, `rclpy`, `tf2_ros`, `v4l2_camera`, `rmw_cyclonedds_cpp`, Nav2, Cartographer ROS and/or SLAM Toolbox. Nav2 interfaces are imported by the control service even for manual driving.

After configuring the official ROS apt repositories:

```sh
sudo apt-get install python3-pil python3-pip tmux \
  ros-humble-navigation2 ros-humble-nav2-bringup \
  ros-humble-cartographer-ros ros-humble-slam-toolbox \
  ros-humble-v4l2-camera ros-humble-rmw-cyclonedds-cpp
```

Computer: macOS or Linux, Python 3.10+, SSH. `scripts/connect.sh` creates `.venv` and installs `requirements-companion.txt`. Set `LIMO_PYTHON=/path/to/python3` if the default Python is too old. Windows is not currently supported by the process-lock and directory-sync implementation.

## First robot installation

Copy this repository into the robot's ROS environment, including `scripts/` and `requirements-recorder.txt`. In a container, install as root inside that container:

```sh
sudo bash scripts/install.sh
```

The installer installs MCAP dependencies and console files into `/control`; it starts no robot processes. `/control` should be a persistent dedicated bind mount or volume. Replaced source is backed up under `/control/.backup-install-TIMESTAMP/`. Maps, recordings and speed settings are preserved.

Review these files for your hardware:

| File | Purpose |
| --- | --- |
| `env.sh` | Humble, `LIMO_ROS_SETUP` overlay (default `/root/workspace/install/setup.bash`), ROS domain 42, localhost DDS |
| `bringup.launch.py` | Base serial `ttyTHS1`, camera `/dev/video0`, mounting transforms, camera exposure |
| `lidar.yaml` | Lidar model, serial path, direction, range and scan settings |
| `cartographer.lua`, `slam.yaml` | Mapping with `/scan_mapping`; raw `/scan` remains unchanged |
| `nav2_params.yaml`, `navigate.xml` | Footprint, costmaps, planner/controller, motion limits |

A different vendor overlay can be selected with `LIMO_ROS_SETUP` in your service/container environment before startup. Confirm mounting transforms against your actual hardware. Camera exposure settings are device-specific.

## Driver integration

The base must subscribe to `/limo/cmd_vel`, with the console guard as its only publisher. Nav2 outputs `/cmd_vel`; it cannot bypass the guard. The driver must independently send zero when command input becomes stale.

The focused patch and source provenance are in `robot/integration/`. For the supported AgileX source layout:

```sh
bash /control/integration/patch_driver.sh /path/to/limo_ros2 /path/to/colcon_workspace
```

It dry-runs the patch, backs up the two changed files and builds only `limo_base`. It does not restart hardware. Changes add a 350 ms command watchdog, initialize IMU integration and handle yaw wrap correctly. Already-patched source is recognized. An unfamiliar source revision fails the dry run; review that diff instead of forcing it. Review any vendor-provided static IMU TF against the console's mounting TF to avoid duplicate authorities.

Source inspection is not a physical stopping test. Validate command-loss behavior separately in a suitable setup before normal driving.

## Start and connect

For sensor-only maintenance, create the lock before starting:

```sh
touch /control/stationary-mode
bash /control/manage.sh start
source /control/env.sh
python3 /control/doctor.py
```

Expected sessions: `base`, `guard`, `recorder`, `capture`, `scan_filter`; mapping/navigation are separate. The doctor reads topics, routing, driver source and status without publishing motion. To leave maintenance, remove `/control/stationary-mode` intentionally after the robot is ready; removing it never arms driving.

On the computer:

```sh
./scripts/connect.sh USER@ROBOT_HOST
# Alternative storage location:
./scripts/connect.sh USER@ROBOT_HOST --data-dir /path/to/private/recordings
```

Open **http://127.0.0.1:18765/**. Start recording explicitly, wait for readiness, then enable driving. Closing a browser tab does not stop recording while the companion remains running. Keep the companion terminal open. The legacy `tunnel.sh` is for diagnostics/desktop forwarding; it does not provide computer recording, so it cannot enable driving on its own.

## Upgrade and rollback

First end recording explicitly, then save and finish mapping. Stop driving. From the computer:

```sh
python3 scripts/deploy.py USER@ROBOT_HOST --container limo_control
```

The helper deploys **committed console files only** using `git archive`. It checks the stopped/idle state, stops managed services, installs with backup, starts disarmed and runs diagnostics. It never copies the parent workspace, credentials or datasets. It targets an existing console container; use the first-install procedure for a new environment.

Inside the robot ROS environment, with recording and mapping ended:

```sh
bash scripts/rollback.sh /control/.backup-install-TIMESTAMP
```

The script restores backed-up source, not private data. Driver rollback is separate: restore the two driver files from their dedicated backup and rebuild the vendor package. Do not restart the base during a live mapping session you want to retain.

`manage.sh stop` stops motion only. `manage.sh shutdown` stops all managed processes and therefore interrupts active data collection; use End recording and save/finish mapping before intentional shutdown. A power loss is recorded as interruption, not normal completion.
