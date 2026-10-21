# 安装与部署

[English](installation.md) · [README](../README.zh-CN.md)

## 依赖环境

机器人需要 Ubuntu 22.04、ROS 2 Humble、Python 3.10+、Pillow、tmux、可用的 LIMO 厂商工作空间以及串口／摄像头权限。ROS 依赖包括 `limo_base`、`limo_msgs`、`ydlidar_ros2_driver`、`rclpy`、`tf2_ros`、`v4l2_camera`、`rmw_cyclonedds_cpp`、Nav2，以及 Cartographer ROS 或 SLAM Toolbox。即使只手动驾驶，控制服务也会导入 Nav2 消息接口。

配置好官方 ROS apt 源后：

```sh
sudo apt-get install python3-pil python3-pip tmux \
  ros-humble-navigation2 ros-humble-nav2-bringup \
  ros-humble-cartographer-ros ros-humble-slam-toolbox \
  ros-humble-v4l2-camera ros-humble-rmw-cyclonedds-cpp
```

电脑需要 macOS 或 Linux、Python 3.10+ 和 SSH。`scripts/connect.sh` 会建立 `.venv` 并安装电脑端依赖。系统 Python 过旧时，设置 `LIMO_PYTHON=/path/to/python3`。当前进程锁和目录同步实现暂不支持 Windows。

## 首次安装到机器人

把本仓库复制进机器人的 ROS 环境，保留 `scripts/` 和 `requirements-recorder.txt`。使用容器时，在容器内以 root 身份执行：

```sh
sudo bash scripts/install.sh
```

安装程序会安装 MCAP 依赖，把控制台文件放入 `/control`，不会启动车端进程。建议将 `/control` 单独持久挂载。被替换的源码保存在 `/control/.backup-install-TIMESTAMP/`；地图、记录和限速设置保留。

检查以下配置是否适合实际硬件：

| 文件 | 内容 |
| --- | --- |
| `env.sh` | Humble、`LIMO_ROS_SETUP` 工作空间，默认 `/root/workspace/install/setup.bash`；ROS domain 42；DDS 仅本机 |
| `bringup.launch.py` | 底盘串口 `ttyTHS1`、摄像头 `/dev/video0`、传感器安装位姿和曝光 |
| `lidar.yaml` | 雷达型号、串口、方向、量程、扫描参数 |
| `cartographer.lua`、`slam.yaml` | 使用 `/scan_mapping` 建图；原始 `/scan` 不变 |
| `nav2_params.yaml`、`navigate.xml` | 车身轮廓、代价地图、规划器、控制器和限速 |

工作空间不同时，在服务或容器环境中设置 `LIMO_ROS_SETUP`。传感器安装 TF 必须与实物一致。曝光参数也需要适配具体摄像头。

## 驱动集成

底盘只能订阅 `/limo/cmd_vel`，其唯一发布者应为控制台 guard。Nav2 发布 `/cmd_vel`，不能绕过 guard。底盘驱动还必须独立处理指令超时，主动发送零速度。

`robot/integration/` 包含小范围补丁、来源和校验脚本：

```sh
bash /control/integration/patch_driver.sh /path/to/limo_ros2 /path/to/colcon_workspace
```

脚本先试应用补丁，备份两个文件，再只编译 `limo_base`，不会重启硬件。补丁增加 350 毫秒指令看门狗、IMU 积分初始化和航向跨 ±180° 的处理。已经修改的源码会被识别；未知版本补丁不匹配时应审查差异，不要强行应用。若厂商驱动也发布静态 IMU TF，需要与控制台的安装 TF 核对，避免重复发布。

源码检查不能证明实际停车性能；投入正常驾驶前，还需在合适条件下验证断指令停车。

## 启动与连接

仅检查传感器时，先开启静止维护锁：

```sh
touch /control/stationary-mode
bash /control/manage.sh start
source /control/env.sh
python3 /control/doctor.py
```

预期进程会话为 `base`、`guard`、`recorder`、`capture`、`scan_filter`，建图和导航单独启动。doctor 只读检查话题、指令路由、驱动源码与状态，不发布移动指令。机器人准备好后，可主动删除 `/control/stationary-mode` 退出维护；删除锁不会自动启用驾驶。

电脑上运行：

```sh
./scripts/connect.sh USER@ROBOT_HOST
# 自定义数据目录：
./scripts/connect.sh USER@ROBOT_HOST --data-dir /path/to/private/recordings
```

打开 **http://127.0.0.1:18765/**，手动开始录制，等待就绪，再启用驾驶。只关闭浏览器不会结束录制，电脑端服务需要保持运行。旧版 `tunnel.sh` 只用于诊断或桌面转发，不提供电脑录制，因此单独使用它不能启用驾驶。

## 升级与回滚

先手动结束录制，保存并结束建图，确认停车。电脑上执行：

```sh
python3 scripts/deploy.py USER@ROBOT_HOST --container limo_control
```

部署脚本只使用 `git archive` 打包**已经提交的控制台文件**。检查停车和空闲状态后，停止服务、备份并安装、以未启用驾驶状态启动，再执行诊断。不复制上一级工作空间、凭据或数据集。该脚本适合已有控制台的容器；新环境按首次安装步骤操作。

在机器人 ROS 环境内、录制和建图均已结束时回滚：

```sh
bash scripts/rollback.sh /control/.backup-install-TIMESTAMP
```

只恢复备份源码，不恢复或覆盖私人数据。驱动补丁的回滚单独处理：从驱动备份恢复两个文件并重新编译。需要保留当前 SLAM 会话时，不要重启底盘。

`manage.sh stop` 只停车。`manage.sh shutdown` 会停止所有进程并中断采集；正常关机前应先结束录制、保存并结束建图。断电会被标记为异常中断，不会伪装成正常完成。
