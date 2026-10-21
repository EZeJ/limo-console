// English source messages and Simplified Chinese translations.
const translations = {
  "Heading (degrees)": "朝向（度）",
  "Load saved map & localize": "加载地图并定位",
  "Load a saved map using the robot's actual pose on that map. Loading never sends a driving goal.": "填写机器人在所选地图上的实际位置和朝向。加载地图只启动定位，不会发出驾驶目标。",
  "Save and finish current mapping before loading a map": "请先保存并结束当前建图，再加载地图",
  "Provide the robot pose on the saved map: x, y and heading in radians": "请填写机器人在所选地图上的 X、Y 和朝向",
  "Loading map and localization…": "正在加载地图与定位…",
  "Map loaded. Check localization before driving.": "地图已加载，请确认定位后再启用驾驶。",
  "Saved map not found": "找不到已保存的地图",
  "Known free area {0} m² · Localization {1} · Route accuracy needs a driving test": "已知空地 {0} m² · 定位{1} · 路线精度需通过行驶测试验证",
  "No footprint-safe reachable frontier. Stopped; continue manual mapping to reveal a route.": "没有满足车身净空要求的可达探索边界。已停车；请先手动补充地图，找到可通行路线。",
  "Map did not change after reaching the target. Stopped; inspect scan and localization health.": "到达目标后地图没有变化。已停车；请检查雷达与定位状态。",
  "Scan coverage or timestamps are unsuitable for navigation": "雷达覆盖范围或时间戳暂不满足导航要求",
  "Start recording": "开始录制",
  "End recording": "结束录制",
  "Recording": "正在录制",
  "Not recording": "尚未录制",
  "Finishing recording…": "正在完成归档…",
  "Stopping the robot keeps recording. Only End recording closes the session.": "停车不会中断录制。点击「结束录制」才会关闭本次记录。",
  "Start recording first": "请先开始录制",
  "Recording companion shut down unexpectedly": "电脑录制服务已退出，记录标记为中断",
  "Robot recorder needs recovery; keep existing data and end this recording explicitly": "车端录制需要恢复；数据已保留，请手动结束本次录制后重试",
  "Stationary maintenance mode; driving is locked": "静止维护模式：驾驶已锁定",
  Stopped: "已停止",
  "Navigation stopped.": "导航已停止。",
  "Chassis paused or not ready (state 1); check the robot pause button":
    "底盘处于暂停状态，请先释放机器人上的暂停按钮。",
  "Chassis paused or not ready (state -1); check the robot pause button":
    "正在等待底盘状态。",
  "Chassis is not in command control mode": "底盘尚未进入指令控制模式。",
  "Chassis must be online before arming": "底盘离线，暂时无法启用驾驶。",
  "Chassis paused or not ready; check the robot pause button":
    "底盘未就绪，请检查机器人上的暂停按钮。",
  "Camera must be online for manual driving":
    "需要先恢复摄像头，才能手动驾驶。",
  "Lidar must be online for navigation": "需要先恢复雷达，才能自动导航。",
  "Chassis reports an error": "底盘报告故障，请检查机器人。",
  "Navigation requires four-wheel differential mode":
    "自动导航需要四轮差速模式。",
  "Connection timeout; re-arm required": "连接超时，已停车；请重新启用驾驶。",
  "Sensor timeout; re-arm required": "传感器数据超时，已停车；请重新启用驾驶。",
  "Waiting for command": "等待方向指令",
  "Camera-guided manual control": "摄像头辅助驾驶中；松开方向键即停车。",
  "No usable front lidar returns": "前方没有有效雷达读数，已停车。",
  "No usable rear lidar returns": "后方没有有效雷达读数，已停车。",
  "Obstacle close to chassis": "障碍物距离过近，已停车。",
  Ready: "设备已就绪",
  "Manual control is not armed": "请先启用手动驾驶。",
  "Wait for mapping setup to finish": "请等待建图服务启动完成。",
  "Stop the current driving session first": "请先停止当前驾驶任务。",
  "Mapping and navigation are not ready yet": "建图和导航尚未就绪。",
  "Fresh chassis, lidar and camera data are required":
    "需要正常的底盘、雷达和摄像头数据。",
  "Stop driving before starting mapping": "请先停车，再启动建图。",
  "Starting live mapping and navigation…": "正在启动实时建图和导航…",
  "Waiting for the map and navigation services…": "正在等待地图和导航服务…",
  "Start mapping and navigation, then click a free point on the map.":
    "先启动建图与导航，再点击地图中的空地。",
  "Click a mapped free point to plan and drive there.":
    "点击地图中已知的空地，即可规划并前往。",
  "Camera unavailable; navigation stopped.": "摄像头不可用，导航已停止。",
  "Browser connection lost; navigation stopped.":
    "浏览器连接中断，导航已停止。",
  "Map, navigation or sensor data unavailable; stopped.":
    "地图、导航或传感器不可用，已停车。",
  "Chassis paused or not ready; stopped.": "底盘暂停或未就绪，已停车。",
  "Waiting for map localization": "正在等待地图定位。",
  "Map localization is stale": "地图定位数据已过期。",
  "Odometry is not fresh": "里程计数据已过期。",
  "That point is already within arrival tolerance":
    "目标点距离太近，无需移动。",
  "Rear lidar cannot confirm free space; use turn-and-return":
    "后方空间无法确认，请选择转向返回。",
  "Enable manual drive": "启用手动驾驶",
  "Manual drive enabled": "手动驾驶已启用",
  "Stopped. Enable manual drive when ready.":
    "已停车。准备好后可重新启用手动驾驶。",
  "Stopped. Enable manual drive to use the direction controls.":
    "已停车。启用手动驾驶后可使用方向控制。",
  "Robot connected": "机器人已连接",
  "Obstacle pause": "避障暂停",
  Navigating: "导航中",
  "Controlled by another tab": "其他页面正在控制",
  "Chassis paused": "底盘已暂停",
  "Another tab is controlling the robot. Stop to end movement.":
    "机器人正由其他页面控制；立即停车可终止运动。",
  online: "在线",
  offline: "离线",
  "scan paused": "扫描暂停",
  Scanning: "扫描中",
  "Camera {0} · Chassis {1} · Lidar {2}": "摄像头{0} · 底盘{1} · 雷达{2}",
  "Cannot connect to the robot": "无法连接机器人",
  Disconnected: "连接已断开",
  "Connection lost": "连接中断",
  "Check the robot connection": "请检查机器人连接",
  "Camera unavailable. Driving stopped.": "摄像头不可用，驾驶已停止",
  FORWARD: "车头方向",
  "{0} points · 1 m rings · 3 m range": "{0} 个测距点 · 每圈 1 m · 视野 3 m",
  "Scan paused": "扫描已暂停",
  "No scan data": "未收到雷达数据",
  "Mapping startup timed out. Please retry.": "建图服务启动超时，请重试。",
  "Current engine: ": "当前引擎：",
  "Navigation ready": "导航已就绪",
  "Starting…": "正在启动…",
  "Enable navigation": "启用自动导航",
  "Exploration running…": "自动建图运行中…",
  "Starting mapping…": "正在启动建图…",
  "Explore automatically": "▶ 自动建图 · 巡游周围",
  "{0} targets · {1} retries · {2} m · {3} s":
    "已探索 {0} 个目标 · 换点 {1} 次 · {2} m · {3} s",
  "Awaiting a goal": "等待选点",
  Exploring: "自动探索中",
  "Exploration complete": "本轮建图结束",
  Planning: "正在规划",
  "Driving to goal": "正在前往目标",
  "Following route home": "沿原路返回",
  Arrived: "已到达",
  "Returned home": "已返回",
  "Route incomplete": "路线未完成",
  "Exploration · ": "自动建图 · ",
  "Navigation not started": "导航未启动",
  "Waiting for map and localization": "等待地图与定位",
  "Chassis not ready. Check the pause button, camera, and connection.":
    "底盘未就绪：请检查暂停按钮、相机与连接。",
  "Rear scan available. Slow reverse return is supported.":
    "后方雷达可用：支持低速倒车返回。",
  "No valid rear scan. Auto return turns and drives forward; reverse-only return is unavailable.":
    "后方雷达无有效读数：自动返回将转向前进；仅倒车模式暂不可用。",
  "Goal ({0}, {1}) m": "目标 ({0}, {1}) m",
  " · {0} m remaining": " · 剩余 {0} m",
  "Wait for a fresh camera frame.": "请等待相机画面恢复。",
  "Resume lidar scanning before using navigation.":
    "请先恢复激光雷达，再使用自动导航。",
  "Start mapping and navigation, then wait for the map.":
    "请先启动建图与导航，等待地图就绪。",
  "Stop the current task before choosing another goal.":
    "请先停止当前任务，再选择新目标。",
  "Camera frames are stale. Navigation cannot start.":
    "相机画面不新鲜，暂不能开始导航。",
  "Choose free space inside the map.": "请选择地图范围内的空地。",
  Connecting: "连接中",
  Pausing: "暂停中",
  Resuming: "恢复中",
  "Retry needed": "需要重试",
  Reading: "读取中",
  "Scan data paused. This does not stop the lidar motor.":
    "扫描数据已暂停；当前雷达电机不会因此停止",
  "Reading lidar status…": "正在读取雷达状态…",
  "Pausing…": "正在暂停…",
  "Retry pause": "重试暂停数据",
  "Pause scan data": "暂停扫描数据",
  "Resuming…": "正在恢复…",
  "Resume scan data": "恢复扫描数据",
  "Robot stopped while changing lidar state.":
    "机器人已停车，正在切换雷达状态。",
  "Camera-guided manual driving is available.": "可通过摄像头进行手动驾驶。",
  "Chassis offline. Check the connection.": "底盘离线，请检查连接。",
  "Chassis paused. Release the robot's physical pause button.":
    "底盘处于暂停状态，请释放机器人上的暂停按钮。",
  "Chassis is not in command control mode.": "底盘尚未进入指令控制模式。",
  "Chassis fault. Driving is unavailable.": "底盘报告故障，暂时无法驾驶。",
  "Wait for the camera to reconnect.": "请等待摄像头恢复。",
  "Wait for the lidar state change to finish.": "请等待雷达切换完成。",
  "Scan data paused. Camera-guided manual driving remains available.":
    "扫描数据已暂停，可通过摄像头低速手动驾驶。",
  "Camera and chassis ready. You can enable driving.":
    "底盘与摄像头已就绪，可启用驾驶。",
  "Stopped. Changing lidar state.": "已停车，正在切换雷达状态。",
  "Command sent. Verifying device state.": "已提交指令，正在确认设备状态。",
  "Applied: forward {0} / reverse {1} m/s · turn {2} rad/s (about {3}°/s)":
    "已生效：前进 {0} / 后退 {1} m/s · 转向 {2} rad/s（约 {3}°/秒）",
  "Forward {0} m/s · Reverse {1} m/s · Turn {2} rad/s":
    "前进 {0} m/s · 后退 {1} m/s · 转向 {2} rad/s",
  "Enter a speed between 0 and 1.00 m/s.": "请输入 0–1.00 m/s 范围内的速度。",
  "Enter a turning speed between 0 and 2.00 rad/s.":
    "转向速度请输入 0–2.00 rad/s。",
  "Stopped. Saving speed limits.": "正在保存速度上限，机器人已停车。",
  "Saved. Re-enable driving to use these limits.":
    "已保存；重新启用驾驶后按此上限行驶。",
  Starting: "启动中",
  Saving: "保存中",
  Finishing: "结束中",
  Working: "处理中",
  "Waiting for map": "等待地图",
  Mapping: "实时建图",
  "Not mapping": "未在建图",
  "Start mapping, then drive manually to expand the map.":
    "点击开始建图，使用手动驾驶扩展地图。",
  "{0} × {1} m · {2} cm/cell · Arrow: robot":
    "地图尺寸 {0} × {1} m · 分辨率 {2} cm/格 · 箭头：机器人",
  "Saved: ": "已保存：",
  "Mapping operations stop the robot first.": "建图操作会先停车。",
  "Operation requested. Waiting for completion…": "操作已提交，等待完成…",
  "No saved maps": "暂无已保存地图",
  "Saved maps are temporarily unavailable.": "地图列表暂时无法读取。",
  "Map names must use 1–64 letters, numbers, underscores, or hyphens.":
    "地图名称需为 1–64 位字母、数字、下划线或短横线。",
  "Invalid map path.": "地图路径无效。",
  "Map files are incomplete or missing.": "地图文件不完整或不存在。",
  "Map files are too large for direct download.":
    "地图文件过大，无法直接下载。",
  "Map metadata has no valid image path.": "地图元数据缺少有效的图像路径。",
  "Start mapping, then drive slowly to explore the space.":
    "点击开始建图，再使用手动驾驶缓慢巡视。",
  "No map received. Check lidar or retry mapping.":
    "尚未收到地图，请检查雷达或重试开始建图。",
  "Map updating live. Drive manually to expand coverage.":
    "地图实时更新中；可手动驾驶扩展地图。",
  "Service did not start": "服务未成功启动",
  "Mapping operation failed: ": "建图操作失败：",
  "That map name already exists. Choose a new name.":
    "该地图名称已存在，请使用新名称。",
  "Map save did not produce complete files. Please retry.":
    "地图保存未生成完整文件，请重试。",
  "A mapping operation is in progress. Please wait.":
    "正在处理建图操作，请稍候。",
  "Unknown mapping operation.": "未知建图操作。",
  "Unsupported mapping engine.": "不支持的建图引擎。",
  "Start mapping and wait for a map before saving.":
    "请先开始建图，等待地图生成后再保存。",
  "Starting mapping. Waiting for the first map…":
    "正在启动建图，等待第一张地图…",
  "Saving map…": "正在保存地图…",
  "Saving and finishing mapping…": "正在保存并结束建图…",
  "Mapping started. Waiting for the map…": "建图服务已启动，正在等待地图…",
  "Map saved: ": "地图已保存：",
  "Mapping finished.": "建图已结束。",
  "; mapping finished.": "；建图已结束。",
  "Lidar state is changing. Please wait before retrying.":
    "雷达正在切换状态，请稍候再试。",
  "Lidar change timed out. Check the connection and retry.":
    "雷达切换超时；请检查设备连接后重试。",
  "Lidar driver could not execute the command. Please retry.":
    "雷达驱动未能执行指令，请重试。",
  "Cannot reach the lidar control service.": "无法连接雷达控制服务。",
  "Connecting to lidar control service": "正在连接雷达控制服务",
  "Pausing scan data…": "正在暂停扫描数据…",
  "Scan data paused; this function does not stop the lidar motor.":
    "扫描数据已暂停；此功能不能让当前雷达电机停转",
  "Resuming scan data…": "正在恢复扫描数据…",
  "Lidar is scanning": "雷达正在扫描",
  "No lidar data. Try resuming the scan.": "未收到雷达数据，可尝试恢复扫描",
  "Resume lidar and wait for fresh scans before mapping or navigation.":
    "请先恢复激光雷达，等待扫描正常后再使用建图和导航。",
  "Speed must be a number in m/s.": "速度必须是数字，单位为 m/s。",
  "Forward and reverse limits must be between 0 and 1.0 m/s.":
    "前进和后退最高速度均需在 0–1.0 m/s 范围内。",
  "Turning speed must be a number in rad/s.":
    "转向速度必须是数字，单位为 rad/s。",
  "Turning speed must be between 0 and 2.00 rad/s.":
    "转向最高速度需在 0–2.00 rad/s 范围内。",
  "Wait for mapping startup to finish before changing lidar state.":
    "建图服务正在启动，请等待完成后再切换雷达。",
  "Wait for the lidar state change before enabling driving.":
    "请等待雷达切换完成后再启用驾驶。",
  "Goal is too close to unknown space for the robot footprint. Explore more or choose a point farther inside free space.":
    "目标靠近未知区域，车身空间不足；请点击「自动建图」补全地图，或选择更靠内的空地。",
  "Exploration: driving to a target with obstacle checks.":
    "自动建图：前往探索点，实时避障。",
  "Path planning service is not ready": "路径规划服务尚未就绪",
  "Exploration: looking for reachable frontiers…":
    "自动建图：正在寻找可安全到达的未知区域边缘…",
  "Narrow-space mapping: moving slowly along the lidar-confirmed corridor, then stopping within about 3 cm to replan.":
    "狭窄空间补图：沿雷达确认的车身通路缓慢直行，最多 3 cm 后停车重规划。",
  "Exploration cancelled. Robot stopped.": "探索路线已取消，机器人已停车。",
  "Several targets were unreachable. Stopped and requested a map save. Check the surrounding routes.":
    "多个探索点连续无法到达，已停车并保存地图；请检查周围通路。",
  "Exploration path is no longer valid. Stopped; updating the map and selecting another target.":
    "当前探索点路径失效，已停车；正在更新地图并选择其他目标。",
  "Target reached. Updating the map and selecting the next target…":
    "已到达探索点，更新地图并选择下一个目标…",
  "Exploration time or distance limit reached. Map retained; start another run to continue.":
    "本轮自动建图已达到时间或路程上限，地图已保留。可再次点击继续。",
  "Control mode changed during a mapping step. Stopped.":
    "直行补图期间控制模式改变，已停车。",
  "Mapping step deviated from its heading. Stopped.":
    "直行补图方向偏离，已停车。",
  "Mapping step complete. Stopped briefly to let the map update before replanning…":
    "直行补图已停车，等待地图更新后重新规划…",
  "Mapping step made no useful progress. Stopped; no automatic reverse.":
    "直行补图无有效位移，已停车；不会自动倒车。",
  "Control mode changed during scanning. Stopped.":
    "扫描期间控制模式改变，已停车。",
  "Not enough clearance to scan. Stopped and requested a map save.":
    "扫描周围净空不足，已停车并保存地图。",
  "Surroundings scan complete. Waiting for map updates before selecting a target…":
    "周围扫描完成，等待地图更新并重新选择探索点…",
  "Surroundings scan timed out. Stopped.": "周围扫描超时，已停车。",
  "Obstacle pause: stopped, waiting up to 15 seconds for clearance. Stop is always available.":
    "避障暂停：已停车，等待周围空间恢复（最多 15 秒）；可随时 STOP。",
  "Could not confirm cancellation of the previous route. Exploration stopped.":
    "无法确认旧路线已取消，已停止自动建图。",
  "Previous route cancellation timed out. Exploration stopped.":
    "旧路线取消超时，已停止自动建图。",
  "Clearance remains blocked. Stopped and requested a map save. Clear nearby obstacles before retrying.":
    "周围空间持续受阻，已停止并保存地图；请移开近处物品后重试。",
  "Path precheck timed out. Stopped.": "路径预检查超时，已停车。",
  "Frontier calculation timed out. Stopped.": "探索点计算超时，已停车。",
  "No reachable exploration targets nearby. A map save was requested. Drive manually to a more open area before exploring again.":
    "附近没有可安全到达的探索点。地图已保存；请在相机监看下手动移至更开阔处，再继续自动建图。",
  "Frontier calculation failed: ": "探索目标计算失败：",
  "Forward corridor is blocked or scan coverage is insufficient; rotation is unavailable. Stopped; the map continues updating.":
    "前方车身通路有障碍或雷达覆盖不足，且无法安全旋转；已停车，当前地图仍会更新。",
  "Initial map is incomplete. Turning slowly to scan before selecting a target. Stop is always available.":
    "起始地图不完整：低速原地扫描一圈，再自动选择探索点；可随时 STOP。",
  "Exploration: checking paths to candidate targets…":
    "自动建图：检查探索点的可达路径…",
  "Path check failed: ": "路径检查失败：",
  "Saved map: ": "已保存地图：",
  "Save failed: ": "保存失败：",
  "Skip to controls": "跳转到控制面板",
  "Workspace navigation": "工作区导航",
  WORKSPACE: "工作空间",
  Drive: "手动驾驶",
  Devices: "设备管理",
  "Your local robot workspace": "你的本地机器人工作台",
  "LOCAL CONNECTION": "本地连接",
  Workspace: "工作空间",
  "Robot control": "机器人控制",
  "Stop robot": "停止机器人",
  Stop: "停车",
  "THE WORLD, FROM YOUR ROBOT": "从机器人视角，探索身边世界",
  "Take the controls.": "掌控每一步。",
  "See clearly. Move precisely. Explore your space.":
    "看清环境，精准移动，探索你的空间。",
  "Preview mode · Synthetic data · No robot is connected":
    "预览模式 · 模拟数据 · 未连接机器人",
  "Live camera": "实时画面",
  "FRONT VIEW": "前方视野",
  "Robot front camera": "机器人前置摄像头",
  LIVE: "实时",
  "Front camera": "前置摄像头",
  "Auto exposure": "自动曝光",
  "Connecting to camera…": "正在连接摄像头…",
  "Connecting to robot…": "正在连接机器人…",
  Surroundings: "周围环境",
  "Lidar top view; the robot faces up": "雷达俯视图，上方为车头方向",
  "Reading scan…": "正在读取扫描数据…",
  Telemetry: "运行数据",
  "Battery voltage": "电池电压",
  "Linear speed": "行驶速度",
  "Angular speed": "转向速度",
  "Manual drive": "手动驾驶",
  "HOLD TO MOVE": "按住行驶",
  "Hold a direction to move. Release to stop.": "按住方向键行驶，松开即停车。",
  "Hold to move forward": "按住前进",
  "Hold to turn left": "按住左转",
  "Hold to turn right": "按住右转",
  "Hold to reverse": "按住后退",
  "or arrow keys": "或方向键",
  "Checking camera and chassis…": "正在检查摄像头与底盘…",
  "Speed limits": "速度上限",
  "YOUR PACE": "由你决定",
  Forward: "前进",
  Reverse: "后退",
  Turning: "转向",
  "Forward speed slider": "前进速度滑块",
  "Reverse speed slider": "后退速度滑块",
  "Turning speed slider": "转向速度滑块",
  "Maximum forward speed in meters per second": "前进最高速度，米每秒",
  "Maximum reverse speed in meters per second": "后退最高速度，米每秒",
  "Maximum turning speed in radians per second": "最大转向速度，弧度每秒",
  "Linear: 0–1 m/s · Turning: 0–2 rad/s. Saving stops the robot.":
    "直行 0–1 m/s · 转向 0–2 rad/s。保存时先停车。",
  "Apply speed limits": "保存速度上限",
  "Stop & disarm": "停车并锁定",
  "You control obstacle clearance. Manual drive does not avoid obstacles automatically.":
    "请自行观察周围空间。手动驾驶不会自动避障。",
  "Lidar scanning": "激光雷达",
  "Waiting for lidar…": "正在等待雷达…",
  "Pausing stops scan data, not the motor. Mapping and navigation need an active scan.":
    "暂停只停止扫描数据，不会停止电机。建图和导航需要雷达持续扫描。",
  "MAKE ROOM FOR EXPLORATION": "为探索，绘一张地图",
  "Build a map of your world.": "让周围的世界清晰可见。",
  "Occupancy map": "环境栅格地图",
  "LIVE SLAM": "实时建图",
  "Live map; clicking is disabled until navigation goals are enabled":
    "实时地图；启用点击导航前，点击不会驱动机器人",
  "Your next discovery starts here.": "探索，从这里开始。",
  "Start mapping, then drive to reveal your surroundings.":
    "启动建图，驾驶机器人逐步描绘周围环境。",
  "Free space": "已知空地",
  Obstacle: "障碍物",
  Unknown: "未知区域",
  Robot: "机器人",
  "Mapping session": "建图任务",
  "Capture your surroundings while you drive.": "边驾驶，边记录周围环境。",
  "SLAM engine": "建图引擎",
  "Start mapping": "开始建图",
  "Map name (optional)": "地图名称（可选）",
  "e.g. room_01": "例如 room_01",
  "Save map": "保存地图",
  "Save & finish": "保存并结束",
  "Saving pauses movement. Existing maps are never overwritten.":
    "保存时会先停车，已有地图不会被覆盖。",
  "Saved maps": "已保存的地图",
  "Loading…": "加载中…",
  "Download map ZIP": "下载地图 ZIP",
  "Autonomous navigation": "自动导航与探索",
  "Apply selected engine": "应用所选引擎",
  "Allow map clicks to send driving goals": "允许点击地图下达行驶目标",
  "Robot will move. Each exploration run is limited to 2 minutes or 6 meters.":
    "机器人将自动行驶。每轮探索最多 2 分钟或 6 米。",
  "Return mode": "返回方式",
  "Auto · reverse when clear": "自动 · 后方可通行时倒车",
  "Turn and drive forward": "转向后前进返回",
  "Reverse only": "仅倒车返回",
  "Return along route": "沿原路返回",
  "Stop navigation": "停止导航",
  "Checking devices…": "正在检查设备…",
  "Advanced desktop ↗": "高级桌面 ↗",
  "Arrived. The actual route is recorded for return.":
    "已到达。实际行驶轨迹已记录，可用于返回。",
  "Chassis paused or not ready; check the robot":
    "底盘暂停或未就绪，请检查机器人。",
  "Connection timeout before route started.": "路线开始前连接超时，已停车。",
  "Could not start navigation: ": "无法启动导航：",
  "Mission stopped: ": "任务已停止：",
  "Motion guard stopped navigation: ": "运动保护已停止导航：",
  "Navigating to the selected point.": "正在前往选定目标。",
  "Navigation error: ": "导航错误：",
  "Navigation rejected this route.": "导航拒绝执行此路线。",
  "Navigation result error: ": "导航结果错误：",
  "Planning a route…": "正在规划路线…",
  "Preparing the recorded return route…": "正在准备沿记录路线返回…",
  "Returned to the starting point.": "已返回起点。",
  "Reversing along the recorded route.": "正在沿记录路线倒车返回。",
  "Route stopped or blocked. Check the surroundings before retrying.":
    "路线停止或受阻，请检查周围环境后重试。",
  "This navigation session has ended": "本次导航任务已结束。",
  "Trip recording limit reached; stopped.": "行驶轨迹记录已达上限，已停车。",
  "Turning and following the recorded route home.":
    "正在转向，并沿记录路线前进返回。",
  "Unknown mapping engine": "未知建图引擎",
  "Unknown return mode": "未知返回方式",
  "Request too large": "请求内容过大",
  "Unknown endpoint": "未知接口",
  "Mode must be manual or navigation": "模式必须为手动驾驶或导航",
  "Narrow-space straight step": "狭窄空间低速直行补图",
  "Straight-step clearance unavailable": "无法确认直行通路净空",
  "Velocity must be finite": "速度必须为有限数值",
  "No active route to cancel": "没有可取消的路线",
  "Map updated; request current metadata": "地图已更新，请获取最新地图数据",
  "Preview only. Connect a robot to drive or map.":
    "当前仅为预览。连接机器人后才能驾驶或建图。",
  "Route returned no path": "路线未返回有效路径",
  Language: "语言",
  Space: "空格",
  "Target coordinates must be finite": "目标坐标必须为有限数值",
  "Target is outside the mapped free area": "目标超出已知可通行区域",
  "Target is too close to an obstacle": "目标距离障碍物过近",
  "No recorded trip to return along yet": "尚无可用于返回的行驶轨迹",
  "Robot moved away from the recorded route; start a new trip":
    "机器人已离开记录路线，请开始新的行驶任务",
  "Recorded route is too short": "记录路线过短，无法返回",
  "Camera & lidar": "相机与雷达",
  "Data recording": "数据记录",
  "Next instance": "下一段",
  "Saved on this computer": "保存在这台电脑",
  "Open folder": "打开文件夹",
  "Recording settings & instances": "录制设置与任务分段",
  Format: "保存格式",
  "H.264 video (compressed)": "H.264 压缩视频",
  "FFV1 video (lossless)": "FFV1 无损视频",
  "PNG frames (lossless)": "PNG 无损图像序列",
  Resolution: "分辨率",
  "Frame rate": "帧率",
  "Use for next instance": "下一段使用此配置",
  "Profile changes require a stopped robot. Images are never saved on the robot.":
    "更改采集配置需先停车。图像不会保存在机器人上。",
  "Optional label for the next instance": "下一段的名称（可选）",
  "Retry recording": "重试录制",
  "Stop & finish recording": "停车并结束采集",
  "Lidar runs continuously for recording, mapping, and navigation.":
    "雷达持续扫描，用于数据记录、建图和导航。",
  "Preview only": "模拟预览",
  "Recording automatically": "正在自动记录",
  "Preparing recording…": "正在准备录制…",
  "Recording error · driving locked": "记录故障 · 驾驶已锁定",
  "Recording not ready": "录制尚未就绪",
  "{0} frames · {1} archived": "{0} 帧 · 已归档 {1}",
  "Connect using scripts/connect.sh to save on this computer":
    "通过 scripts/connect.sh 连接，即可将数据保存到电脑",
  "{0} chunks verified · {1} free on computer · Robot copies are deleted only after verification":
    "已校验 {0} 个数据块 · 电脑剩余 {1} · 校验成功后才删除车端副本",
  "Profile queued. Stop driving, then start the next instance.":
    "配置已暂存。停车后点击下一段生效。",
  recording: "记录中",
  closing: "正在结束",
  video_saved: "视频已保存",
  complete: "已完成",
  interrupted: "已中断",
  pending_transfer: "等待传输",
  "Computer recording is not ready; driving is locked":
    "电脑录制尚未就绪，驾驶已锁定",
  "Recording service is unavailable; driving is locked":
    "录制服务不可用，驾驶已锁定",
  "Fresh lidar scans are required": "需要新鲜的雷达扫描数据",
  "Recording owner mismatch": "录制会话不匹配",
  "Another recorder is active": "已有另一台电脑正在录制",
  "Recording is not ready": "录制尚未就绪",
  "Stop driving before applying a camera profile":
    "请先停车，再应用相机录制配置",
  "Camera resolution is not supported": "相机不支持此分辨率",
  "Unsupported camera recording profile": "不支持的相机录制配置",
  "Camera configuration service unavailable": "相机配置服务不可用",
  "Camera configuration timed out": "相机配置超时",
  "Camera rejected this resolution": "相机拒绝了此分辨率",
  "Camera did not produce the requested native resolution":
    "相机未输出要求的原生分辨率",
  "Computer recording storage is full": "电脑录制存储空间不足",
  "Robot recording storage is full": "机器人数据缓存空间不足",
  "Recording queue overflow": "数据记录队列溢出",
  "Some ROS topics could not be recorded": "部分 ROS 数据无法记录",
  "Camera frames were lost; driving is locked": "相机帧丢失，驾驶已锁定",
  "Camera transport restarted; start a new recording session":
    "相机传输已重启，请建立新的录制任务",
  "Camera frame unavailable": "无法读取相机帧",
  "Camera frame is stale": "相机帧已过期",
  "Camera encoding queue overflow": "相机编码队列溢出",
  "Lossless frame checksum mismatch": "无损图像校验失败",
  "Video recording failed: ": "视频记录失败：",
  "Recording connection lost: ": "录制连接中断：",
  "Data archival failed: ": "数据归档失败：",
  "Final data remains on the robot: ": "最后一段数据仍保留在机器人上：",
  "Robot service unavailable: ": "机器人服务不可用：",
  "Robot connection unavailable: ": "无法连接机器人：",
  "Instance name is too long": "任务名称过长",
  "Archive checksum mismatch; robot copy retained":
    "归档校验失败，车端副本已保留",
};
