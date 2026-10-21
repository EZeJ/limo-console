# 安装与配置

[English](installation.md) · [返回 README](../README.zh-CN.md)

## 支持的环境

已验证的集成环境是 ARM64 Jetson 上运行于 Ubuntu 22.04 环境中的 ROS 2 Humble。若使用容器，宿主系统版本可以不同。本项目不是 ROS 1 应用；其他 ROS 发行版、相机、转向模式或驱动版本需要单独验证。

请先准备可工作的 [AgileX LIMO ROS 2 工作区](https://github.com/agilexrobotics/limo_ros2/tree/humble)，并按 [ROS 官方说明](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html)安装 Humble。本仓库不会安装固件或构建厂商工作区。

ROS 环境中需要：

- Python 3.10+、Pillow、Bash、tmux。
- `rclpy`、ROS 标准消息/服务/动作、`limo_msgs`、`limo_base`、`tf2_ros`。
- `v4l2_camera`、`ydlidar_ros2_driver`、`rmw_cyclonedds_cpp`。
- Nav2 和 `nav2_bringup`。当前服务启动时会导入 Nav2 接口，所以即使只手动驾驶也需要这些依赖。
- 建图需要 Cartographer ROS 或 SLAM Toolbox；默认选择 Cartographer。
- 可选高级桌面：RViz2、Xvfb、Openbox、x11vnc、websockify、noVNC。

配置好 ROS apt 源后，可安装常用 Ubuntu 依赖：

```sh
sudo apt-get update
sudo apt-get install python3-pil tmux \
  ros-humble-navigation2 ros-humble-nav2-bringup \
  ros-humble-cartographer-ros ros-humble-slam-toolbox \
  ros-humble-v4l2-camera ros-humble-rmw-cyclonedds-cpp
```

LIMO 消息、底盘和雷达驱动由厂商工作区提供，不能用 pip 包替代。

## 安装到 ROS 环境

将**本仓库**克隆或复制到机器人 ROS 环境中，执行：

```sh
sudo bash scripts/install.sh
```

若使用已有容器，请在容器内以 root 执行安装。`/control` 必须位于该环境内，并通过专用挂载目录或数据卷在重建容器后保留。不要挂载整个个人工作目录或主目录。

安装脚本只复制控制台源码与配置，不启动任何进程。被替换的源码会备份到 `/control/.backup-install-TIMESTAMP/`；地图、雷达扫描偏好、已选建图引擎和速度设置会保留。升级前先停车，并停止旧控制服务再替换文件。需要保留实时地图时，可以让 SLAM 进程继续运行。

运行账号需要对 `/control` 有读写权限，以保存状态、地图和日志，并需要串口和相机设备权限。请按部署环境设置所属账号与设备访问权限。

## 启动前检查配置

| 文件 | 用途与默认值 |
| --- | --- |
| `robot/env.sh` | Humble 路径 `/opt/ros/humble`；厂商工作区由 `LIMO_ROS_SETUP` 指定，默认 `/root/workspace/install/setup.bash`；ROS 域默认 `42`；DDS 仅本机通信 |
| `robot/bringup.launch.py` | 底盘串口 `ttyTHS1`；相机 `/dev/video0`、RGB 640×480；变换参数对应已测试的安装位置 |
| `robot/lidar.yaml` | 雷达串口与扫描参数，须核对实际型号 |
| `robot/cartographer.lua` | Cartographer 二维建图参数 |
| `robot/slam.yaml` | SLAM Toolbox 参数 |
| `robot/nav2_params.yaml` | 车身轮廓、障碍物层、规划/控制上限与返回控制器 |
| `robot/navigate.xml` | 重规划和路径跟随行为树 |
| `robot/cyclonedds.xml` | 本机 DDS 节点发现 |

如果工作区位置不同，在启动服务**之前**指定：

```sh
export LIMO_ROS_SETUP=/path/to/limo_ws/install/setup.bash
export ROS_DOMAIN_ID=42
source /control/env.sh
```

需要持久生效时，将变量放入你自己的服务或容器配置。端口有意固定为：机器人 HTTP `8765`、电脑隧道 `18765`；可选桌面为机器人 `6080`、电脑 `16080`。如修改端口，需要同步修改 HTTP Host 允许列表和隧道配置。直接使用局域网远程 URL 会被拒绝。

### 运动控制集成要求

`bringup.launch.py` 将底盘驱动订阅的 `/cmd_vel` 重映射为 `/limo/cmd_vel`。Nav2 发布 `/cmd_vel`，控制台检查后才发布最终的 `/limo/cmd_vel`。其他节点不应绕过该控制路径。

底盘驱动必须在停止收到指令时独立发送零速度。已测试驱动具有 350 ms 指令超时保护。控制台进程或计算机本身失效时，不能依靠控制台自行停车；原厂驱动可能需要另外增加超时保护。启用运动前必须确认驱动行为。厂商驱动补丁与固件不属于本仓库。

雷达暂停/恢复需要 `/start_scan`、`/stop_scan` 两个 `std_srvs/Empty` 服务，而且驱动在暂停后仍须响应服务。启动参数 `start_paused` 是已测试驱动的可选扩展，原厂版本可能忽略它。控制服务会在启动后通过服务重新应用已保存的暂停偏好。服务支持情况和物理电机控制能力取决于驱动。

相机曝光、增益、伽马、亮度及 60 Hz 防闪烁参数来自一款已测试设备。请核对实际 V4L2 控制项和当地照明频率；不支持的控制项或过高增益可能让其他相机的效果变差。

## 启动与连接

在机器人上：

```sh
bash /control/manage.sh start
bash /control/manage.sh status
```

正常应出现 `guard` 和 `base` 两个 tmux 会话。控制服务默认锁定驾驶。可以在同一环境读取状态：

```sh
curl --fail http://127.0.0.1:8765/status
```

在电脑上：

```sh
./scripts/tunnel.sh USER@ROBOT_HOST
```

保持终端打开，访问 **http://127.0.0.1:18765/**。认证由 SSH 处理，脚本不会保存密码。如果本地端口被占用，先关闭旧隧道；不要随意终止无关 SSH 会话。

高级桌面链接需要可选桌面依赖和第二条端口隧道。启动桌面服务前会先停车。

## 停止、更新与恢复

- `bash /control/manage.sh stop`：停车，传感器与建图可以继续运行。
- `bash /control/manage.sh shutdown`：停车并结束控制台管理的所有 tmux 会话，包含建图。请先保存地图。
- 更新：保存地图，停止服务，运行新版安装脚本，检查配置变化，然后重启。用户保存的设置会保留。
- 回滚：在服务停止时，从安装备份恢复源码/配置，然后重启。不要用无关备份覆盖当前地图和状态文件。

日志位于 `/control/logs/`。运行状态和地图属于部署私有数据，已加入版本控制忽略规则；提交公开问题前应先检查附件内容。
