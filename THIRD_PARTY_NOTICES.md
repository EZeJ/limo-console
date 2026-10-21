# Third-party notices / 第三方声明

The original console application is licensed under GNU GPL v3.0 (GPL-3.0-only). The robot stack is installed separately and retains its own licenses. The focused driver patch includes upstream context under BSD-3-Clause; full vendor drivers, firmware, models and OS images are not distributed here.

控制台原创代码采用 GNU GPL v3.0 许可证（GPL-3.0-only）。机器人软件栈单独安装，遵循各自许可证。小范围驱动补丁保留 BSD-3-Clause 上游上下文；不分发完整厂商驱动、固件、模型或系统镜像。

- **AgileX LIMO:** [limo_ros2](https://github.com/agilexrobotics/limo_ros2/tree/humble) provides robot messages and hardware drivers. LIMO and AgileX names identify compatibility; no affiliation or endorsement is implied.
- **Navigation2:** [Navigation2 Humble](https://github.com/ros-navigation/navigation2/tree/humble). `robot/nav2_params.yaml` is adapted from the upstream Nav2 example configuration, with LIMO footprint, controller limits, return controllers, and local integration changes. The adapted configuration is distributed under Apache-2.0; see [the license text](LICENSES/Apache-2.0.txt). Original upstream notices remain applicable.
- **Cartographer:** [cartographer_ros](https://github.com/cartographer-project/cartographer_ros), Apache-2.0. `robot/cartographer.lua` follows the LIMO/Cartographer 2D configuration conventions and references separately installed upstream Lua configuration files.
- **SLAM Toolbox:** [slam_toolbox](https://github.com/SteveMacenski/slam_toolbox). Used as an optional separately installed mapping backend.
- **ROS 2 / Cyclone DDS / V4L2 Camera / Pillow:** separately installed runtime dependencies, each under its upstream license.

The preview illustration and generated map are synthetic project assets. They contain no camera capture, household map, or other robot-derived data.

预览插图和地图为项目生成的模拟素材，不含真实摄像头画面、住宅地图或其他机器人采集数据。

- **Driver integration patch:** `robot/integration/limo-base-watchdog-yaw.patch` adds command timeout and yaw-wrap fixes to the upstream AgileX driver. Context retains the [AgileX BSD-3-Clause license](LICENSES/BSD-3-Clause-AgileX.txt). Source URL and SHA-256 inputs are in `robot/integration/upstream.json`.
- **MCAP / PyAV / FFmpeg / NumPy:** separately installed recording dependencies under their respective upstream licenses. Codec availability depends on the PyAV/FFmpeg build.
