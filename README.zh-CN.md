# Limo Console

**为 AgileX LIMO 打造的中英文机器人控制工作台。**

[English](README.md) · 简体中文

实时查看前置摄像头，通过键盘或触控驾驶，自行设定速度上限，并在行驶中绘制环境地图。Limo Console 与 ROS 2 机器人软件栈运行在同一环境，通过 SSH 隧道访问，无需云服务，也无需构建前端。

![Limo Console 中文界面——模拟预览，未连接真实机器人](docs/console-zh.jpg)

## 功能

- **手动驾驶：**按住行驶、松开停车，支持 W/A/S/D 和方向键；停车按钮始终可见；前进、后退、转向上限独立设置。
- **实时观察：**前置摄像头、雷达俯视图、电池电压、实际线速度与角速度。
- **环境建图：**启动 SLAM 时不自动行驶，支持命名保存、保存并结束，以及下载可移植的 PGM + YAML 地图 ZIP。
- **雷达数据控制：**暂停和恢复扫描，验证设备状态并保留设置。暂停数据**不代表雷达电机停止旋转**。
- **可选自动导航：**明确开启后才能点击地图下达目标，支持有限时长和距离的自动探索，以及沿记录路线返回。
- **中英文切换：**按钮、状态、验证信息和无障碍标签均有翻译，语言偏好只保存在本地浏览器中。

## 不连接机器人也能预览

建议使用 Python 3.10 或更新版本。从全新克隆开始：

```sh
git clone https://github.com/EZeJ/limo-console.git
cd limo-console
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/preview.py
```

打开 **http://127.0.0.1:18766/**。预览使用绘制的相机场景和生成的模拟地图，不导入 ROS、不连接机器人，也不会执行运动。预览中的速度设置仅保存在内存中；驾驶与建图操作会被拒绝。

## 连接真实机器人

集成目标是 **Ubuntu 22.04 上的 ROS 2 Humble**，并要求已有可工作的 LIMO 驱动工作区。本仓库仅包含控制台和集成配置，不包含机器人固件、预构建系统镜像或厂商驱动源码。

1. 按照[安装指南](docs/installation.zh-CN.md)准备依赖、检查硬件参数，将控制台安装到机器人 ROS 环境的 `/control`。
2. 确认底盘仅订阅经过保护的 `/limo/cmd_vel`，并具备独立的指令超时停车机制。
3. 在机器人上启动：

   ```sh
   bash /control/manage.sh start
   ```

4. 在你的电脑上，用自己的账号和主机名建立隧道：

   ```sh
   ./scripts/tunnel.sh USER@ROBOT_HOST
   ```

5. 打开 **http://127.0.0.1:18765/**。启动后默认锁定驾驶，准备好后再主动启用手动驾驶。

**公开源码不会公开机器人服务。** HTTP 服务仅监听回环地址，访问控制依赖 SSH。不要将该端口通过公网代理暴露，也不要改为监听公网接口。

## 文档

| 内容 | 简体中文 | English |
| --- | --- | --- |
| 安装、依赖与配置 | [安装与配置](docs/installation.zh-CN.md) | [Installation](docs/installation.md) |
| 驾驶、建图、雷达与故障排查 | [使用指南](docs/usage.zh-CN.md) | [User guide](docs/usage.md) |
| ROS 接口、HTTP API 与控制机制 | [架构与 API](docs/architecture.zh-CN.md) | [Architecture & API](docs/architecture.md) |
| 开发与验证 | [开发说明](CONTRIBUTING.zh-CN.md) | [Contributing](CONTRIBUTING.md) |

## 使用边界

手动驾驶依赖操作者观察环境，不会自动避障。前置摄像头无法确认后方净空。连接或必要传感器数据超时后，控制台会停止发送运动指令；但它不是经过安全认证的控制器，仍依赖底盘驱动自身的超时停车机制。

手动速度与自动导航速度独立。前进、后退可设 **0–1.00 m/s**，转向可设 **0–2.00 rad/s**，左右共用同一上限。角速度范围是应用提供的设置范围，不是实测底盘性能指标。保存速度时会停车并锁定驾驶。

## 仓库范围

```text
robot/          Python 控制服务、ROS 启动与配置文件、静态网页
scripts/        本地模拟预览、安装脚本、SSH 隧道脚本
tests/          无需硬件的控制、地图导出与多语言验证
docs/           中英文指南与模拟界面截图
```

仓库不包含运行时地图、日志、摄像头录像、设备地址、密码或用户保存的机器人设置。忽略规则会排除生成数据；发布自己的分支前，仍应检查新增文件。

## 许可证

控制台原创代码采用 [GNU GPL v3.0 许可证（GPL-3.0-only）](LICENSE)。上游集成与基于 Nav2 的配置说明见[第三方声明](THIRD_PARTY_NOTICES.md)。Limo Console 是独立项目，并非 AgileX 官方产品。
