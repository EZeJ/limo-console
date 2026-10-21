# 架构与 API

[English](architecture.md) · [README](../README.zh-CN.md)

## 进程与控制边界

浏览器连接电脑端 `127.0.0.1:18765`；电脑端通过 SSH 访问机器人 guard `:8765`。guard 连接独立记录服务 `:8766`、图像内存传输服务 `:8767`，并管理 SLAM／Nav2。录像和归档由电脑端负责，不依赖网页的驾驶轮询。

HTTP 均只监听回环地址。POST 需要 `X-Limo-Control: 1`、允许的 Host，以及存在时匹配的 Origin；guard／电脑端请求正文上限 16 KiB。访问控制由 SSH 提供，面向单个可信操作者，不提供多用户授权。

控制门限以 20 Hz 运行。指令 0.3 秒过期，驾驶租约 0.6 秒过期，记录健康 0.75 秒过期；另检查车端写入线程是否推进。异常会清除指令并锁定驾驶，需要重新启用。存在 `/control/stationary-mode` 时拒绝移动。底盘自身还需 350 毫秒看门狗。这些机制不能替代实际停车距离验证。

Nav2 发布 `/cmd_vel`，仅 guard 发布底盘消费的 `/limo/cmd_vel`。碰撞判断使用原始雷达。SLAM 单独使用 `/scan_mapping`：仅将邻近测距一致时孤立的远点标为 NaN，不把异常点变成空地，也不删除原始碰撞输入中的近处孤立障碍。自动探索有时间、距离、速度上限，没有直接盲走兜底。

## 数据格式与完整性

一个写入线程按顺序处理收到的非图像消息和分段命令。MCAP 保留原始 CDR 字节及完整 ROS 消息定义。MCAP 的 log/publish 时间为接收端墙钟；原始 ROS header 时间仍在消息中。会话连续序号标记收到的样本；序号 0 表示为回放重复附带的 TF／标定上下文，不计为新样本。分段与样本共用同一队列，并记录序号、机器人单调时钟和墙钟边界。

摄像头按所选帧率采样，携带 ROS 时间戳、采集单调时钟／墙钟、进程 ID、配置代次、尺寸和序号。电脑按单调时钟半开区间分配到实例。H.264 使用 JPEG 传输；FFV1／PNG 使用有像素哈希校验的无损 RGB 传输。`frames.csv` 保存源序号、采集／接收时间、播放时间和 RGB 哈希。无损相对于 ROS RGB，不是传感器原始 Bayer。

车端编码图像历史最多 120 帧、32 MiB，另有四帧编码队列，不写图像文件。非图像 MCAP 每 10 秒或未压缩 64 MiB 滚动；暂存容量和磁盘保留空间默认各 2 GiB，电脑预留 5 GiB。录制队列有 32 MiB 上限。溢出、存储异常、传输缺口或健康过期都会显示并锁定驾驶。

归档顺序：下载 → 大小／哈希校验 → 文件同步 → 原子重命名与目录同步 → 持久化凭据 → ACK → 车端持久化删除凭据 → 删除文件。ACK 可重复。实例清单列出全部必需分段 ID，缺少校验凭据不能标记完成。相机异常保留在对应实例中。崩溃可能丢失未刷盘尾部；恢复工具保留原件并明确标记不完整。

## HTTP 接口

| 接口 | 用途 |
| --- | --- |
| GET `/status`、`/scan`、`/camera.jpg`、`/navigation` | 状态、雷达显示、画面和导航状态 |
| GET `/configuration` | 配置文本及哈希 |
| GET `/map.png?v=REV`、`/maps`、`/maps/download?name=NAME` | 匹配版本的地图、列表、PGM/YAML ZIP |
| POST `/stop` `{}` | 只停车，不结束录制 |
| POST `/arm` `{"mode":"manual"}` | 检查通过后显式启用驾驶 |
| POST `/drive` `{"x":0,"z":0}` | 线速度 m/s、角速度 rad/s，并刷新手动租约 |
| POST `/heartbeat` `{"mission_id":"…"}` | 刷新对应导航任务租约 |
| POST `/manual/speed` `{"forward":0.1,"reverse":0.05,"angular":0.3}` | 停车并保存限速 |
| POST `/mapping/start` `{"backend":"cartographer"}` | 启动 SLAM，不发出驾驶目标 |
| POST `/mapping/save` `{"name":"room"}`、`/mapping/stop` `{}` | 保存栅格／SLAM 状态，或保存后结束 |
| POST `/mapping/load` `{"name":"room","pose":[0,0,0]}` | 加载栅格并初始化 AMCL；位姿为 x、y（米）、yaw（弧度） |
| POST `/navigation/prepare` `{}` | 启动 SLAM／Nav2，不发出目标 |
| POST `/navigation/goal` `{"x":1,"y":1}` | 地图坐标目标 |
| POST `/navigation/explore` `{"max_seconds":20,"max_distance":0.5,"max_speed":0.08}` | 限定探索范围；客户端需持续发送任务心跳 |
| POST `/navigation/return` `{"mode":"auto"}` | 沿已记录路线返回，属于显式移动操作 |
| POST `/events` `{…}` | 操作事件 |
| GET `/local/recording/status`、`/local/instances` | 电脑录制状态和实例列表 |
| POST `/local/recording/start`、`/local/recording/finish` `{}` | 用户控制开始／结束；连接不会开始录制 |
| POST `/local/recording/next` `{"request_id":"unique-id","name":"route"}` | 幂等分段，普通分段不停车 |
| POST `/local/recording/profile` `{"width":640,"height":480,"fps":10,"format":"h264"}` | 设置下次停车分段或开始录制时使用的规格 |
| POST `/local/recording/retry`、`/local/recording/open-folder` `{}` | 检查恢复／打开私人目录 |

异步操作需要轮询，等待 `busy`／`initializing`／`finishing` 清除，再检查错误和结果证据。HTTP 接受请求不代表实物动作成功。已取消的雷达写接口返回 410。`/recording/*`、`/capture/*` 属于内部传输接口，应用应使用电脑端生命周期接口，不直接抢占车端录制所有权。

离线回放／导出不导入 ROS、不建立网络连接、不发布话题，不能驱动车辆。参见 [harness 验收](harness.zh-CN.md)。
