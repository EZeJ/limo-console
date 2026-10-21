# 架构与 API

[English](architecture.md) · [README](../README.zh-CN.md)

## 控制路径

```text
浏览器（localhost:18765）
        │ SSH 隧道 / JSON HTTP
        ▼
control_server.py（机器人回环地址 :8765）
        ├── 相机 JPEG、雷达点、地图 PNG、运行数据
        ├── 手动上限 + 指令保护 ──► /limo/cmd_vel ──► 底盘驱动
        └── 建图 / 导航管理
                 ├── SLAM ──► /map
                 └── Nav2 ──► /cmd_vel ──► 指令保护
```

静态 HTML/CSS/JavaScript 前端不依赖框架、统计服务、CDN 或远程翻译。`messages.js` 包含英译中词典，`i18n.js` 管理语言偏好和 DOM 更新。ROS 服务输出统一英文消息，状态字段与枚举值保持语言无关。

`Control` 是 `rclpy.Node`，与请求处理线程共用可重入锁。20 Hz 定时器发布受保护的速度指令，`ThreadingHTTPServer` 在另一个线程处理 HTTP。较慢的建图操作由工作线程执行，避免阻塞控制定时器。Nav2 使用 ROS Action，浏览器通过任务编号维持心跳归属。

## ROS 接口

| 接口 | 类型 | 方向与用途 |
| --- | --- | --- |
| `/limo_status` | `limo_msgs/msg/LimoStatus` | 读取底盘模式、故障与电压 |
| `/odom` | `nav_msgs/msg/Odometry` | 读取位姿和实测速度 |
| `/scan` | `sensor_msgs/msg/LaserScan` | 读取扫描点和净空 |
| `/camera/image_raw` | `sensor_msgs/msg/Image` | 读取 RGB/BGR 图像 |
| `/map` | `nav_msgs/msg/OccupancyGrid` | 通过 transient-local QoS 接收地图 |
| `/plan` | `nav_msgs/msg/Path` | 读取当前导航路线 |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | 接收待检查的 Nav2 指令 |
| `/limo/cmd_vel` | `geometry_msgs/msg/Twist` | 发布最终受保护的底盘指令 |
| `/start_scan`、`/stop_scan` | `std_srvs/srv/Empty` | 请求恢复/暂停雷达 |
| `/navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | 目标点导航 |
| `/follow_path` | `nav2_msgs/action/FollowPath` | 按记录路线返回 |
| `/compute_path_to_pose` | `nav2_msgs/action/ComputePathToPose` | 探索路线预检查 |

导航还会查询 `controller_server`、`planner_server`、`bt_navigator` 的生命周期状态，并使用 `map → odom` TF 变换。请按实际机器人检查 `bringup.launch.py` 中的传感器安装变换。

## 指令保护与超时

| 条件 | 当前行为 |
| --- | --- |
| 主动停车、模式切换、保存速度 | 锁定驾驶并清除旧指令 |
| 心跳租约超过 0.6 秒 | 停车，要求重新启用 |
| 指令超过 0.3 秒 | 等待新指令期间输出零速度 |
| 底盘状态超过 1 秒 | 停车，要求重新启用 |
| 手动驾驶相机超过 2 秒 | 停车，要求重新启用 |
| 导航扫描超过 1 秒 | 停车，要求重新启用 |
| 浏览器相机画面超过 1.5 秒 | 浏览器请求停车 |
| 底盘暂停、控制模式错误或故障 | 输出零速度，具体状态处理取决于条件 |

手动输出按用户保存的上限截断。导航独立限制为前进 0.50 m/s、后退 0.05 m/s、转向 0.30 rad/s，并根据净空进一步减速。这些是软件限制，不是制动性能保证。浏览器约每 100 ms 请求一次，持续运动需要健康连接。进程或计算机失效时，必须依赖独立的底盘驱动超时保护。

`/arm` 不会在任意 API 客户端之间建立独占授权。应由一个可信操作者和浏览器会话控制；此接口不用于不可信多用户场景。

## HTTP API

机器人端仅监听回环地址 `8765`，电脑通过隧道使用回环地址 `18765`。允许的 Host 为 `127.0.0.1:8765`、`127.0.0.1:18765`、`localhost:18765`。POST 需要 JSON、`X-Limo-Control: 1` 请求头；若存在 Origin，必须与 Host 匹配。请求体限制为 1024 字节。这些检查配合 SSH 使用，不等同于用户认证。

### 读取

| GET | 返回内容 |
| --- | --- |
| `/status` | 模式、输出、底盘/里程计、传感器时效、速度设置、雷达、建图与精简导航状态 |
| `/scan` | 显示点、在线标志、雷达状态、前后净空 |
| `/camera.jpg` | 新鲜相机 JPEG；不可用或过期时返回 503 |
| `/navigation` | 完整导航状态、地图信息、轨迹、路线、任务与探索状态 |
| `/map.png?v=REVISION` | 地图图像；版本变化时返回 409，尚无地图时返回 503 |
| `/maps` | 已保存且完整的 PGM/YAML 地图对 |
| `/maps/download?name=NAME` | YAML 使用相对图像路径的 ZIP |

### 写入

| POST | JSON 请求体 | 效果 |
| --- | --- | --- |
| `/stop` | `{}` | 停车并锁定，取消导航 |
| `/arm` | `{"mode":"manual"}` | 就绪检查后启用驾驶 |
| `/drive` | `{"x":0.0,"z":0.0}` | 线速度 m/s、角速度 rad/s，并更新手动控制租约 |
| `/heartbeat` | `{"mission_id":"…"}` | 更新对应导航任务租约 |
| `/manual/speed` | `{"forward":0.1,"reverse":0.05,"angular":0.3}` | 停车、验证并保存；省略 angular 时保留当前转向上限 |
| `/lidar/pause`、`/lidar/resume` | `{}` | 停车，异步改变扫描状态 |
| `/mapping/start` | `{"backend":"cartographer"}` | 停车并启动 SLAM，也支持 `slam_toolbox` |
| `/mapping/save` | `{"name":"room_01"}` | 停车并保存新地图；null 或省略名称时自动命名 |
| `/mapping/stop` | `{}` | 先保存当前新鲜地图，再停止 SLAM |
| `/navigation/prepare` | `{}` 或 `{"backend":"cartographer"}` | 启动建图/Nav2 或切换引擎，可能重置建图任务 |
| `/navigation/goal` | `{"x":0.0,"y":0.0}` | 前往经过验证的 map 坐标系目标 |
| `/navigation/explore` | `{}` | 开始有界的未知区域边缘探索 |
| `/navigation/return` | `{"mode":"auto"}` | 沿记录路线返回，模式为 `auto`、`forward`、`reverse` |
| `/desktop` | `{}` | 停车并启动可选本地桌面 |

写入通常返回状态快照。异步操作通过 `busy` / `preparing` 表示已接受，需要继续轮询直至完成并检查 `error`。HTTP 200 本身不能证明物理设备动作已完成。验证错误返回 400 和 `{"error":"…"}`；Host、Origin 或请求头检查失败返回 403。

通过隧道进行无运动的状态查询：

```sh
curl --fail http://127.0.0.1:18765/status
```

不要为了验证连接而发送非零行驶指令。

## 文件与生命周期

运行数据位于 `/control`：`manual-speed.json`、`lidar-state.json`、`mapping-engine`、`maps/` 和 `logs/`，均不属于源码。速度与扫描偏好使用临时文件替换保存。地图导出检查名称、拒绝符号链接和目录穿越、要求文件完整，并限制文件大小。重复名称会被拒绝。

`manage.sh` 管理 `guard`、`base`、`mapping`、`navigation` 及可选桌面 tmux 会话。地图生命周期与自动任务独立，停止导航后 SLAM 可以继续更新。控制服务重启会保留磁盘设置，但重置内存中的任务归属和返回轨迹。完整重启 SLAM 不会恢复未保存的实时 SLAM 任务。

## 验证范围

无硬件测试覆盖限速、超时保护、雷达状态切换、地图路径与导出、保存失败处理、翻译占位符和 DOM 绑定。测试不能证明制动距离、电机停转、定位质量或所有 Nav2/驱动组合的兼容性。模拟预览不代表硬件兼容性验证。
