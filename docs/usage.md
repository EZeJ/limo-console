# User guide

[中文](usage.zh-CN.md) · [README](../README.md)

## Language and workspace

Choose **EN** or **中文** in the top bar. The selection survives refreshes in this browser; it does not change robot settings. The left navigation jumps to Drive, Mapping, and Devices. On narrow screens the panels stack vertically, while the top-bar stop control stays accessible.

## Drive manually

1. Confirm that the current camera image is visible, the chassis is online, and the physical pause button is released.
2. Set forward, reverse, and turning limits; select **Apply speed limits**. Saving stops and disarms the robot. Settings persist on the robot.
3. Select **Enable manual drive**.
4. Hold an on-screen direction or a keyboard key. Releasing it sends a zero command. Forward/reverse can be combined with a turn.
5. Select **Stop & disarm**, use the top-bar **Stop**, or press **Space** to stop and lock driving.

| Input | Action |
| --- | --- |
| W / ↑ | Forward |
| S / ↓ | Reverse |
| A / ← | Turn left |
| D / → | Turn right |
| Space | Stop and disarm |

Direction shortcuts are ignored while editing an input. Space remains the stop shortcut. A hidden tab, window blur, stale camera frames, or lost connection ends driving. A second tab does not inherit the first tab's armed state; it reports that another page is controlling the robot. Stop can interrupt that control.

### Speed limits

Forward and reverse each accept 0–1.00 m/s. Turning accepts 0–2.00 rad/s for both directions. Zero disables the corresponding motion component. Defaults are 0.10 m/s forward, 0.05 m/s reverse, and 0.30 rad/s turning. One radian per second is about 57 degrees per second.

These are commanded maximums. Actual speed depends on the chassis, traction, steering mode, and battery. The telemetry displays measured odometry, not the requested limit. Autonomous navigation keeps its own configuration and is not sped up by manual settings.

Manual driving does not use lidar to avoid obstacles. Observe the environment yourself, including the rear before reversing. The camera's field of view is limited.

## Build and export a map

1. Keep lidar scanning active.
2. Choose Cartographer or SLAM Toolbox before starting a session.
3. Select **Start mapping**. The robot stops; SLAM starts without a movement goal.
4. Once the map appears, enable manual driving and move through the space. Both camera and map update live.
5. Optionally enter a name (1–64 ASCII letters, numbers, underscores, or hyphens) and select **Save map**. An empty name generates a timestamped name. Saving stops movement but keeps SLAM running.
6. Select a saved map, then **Download map ZIP**. It contains `.pgm` and `.yaml`; the YAML image path is relative so the files can be moved together.
7. **Save & finish** saves the current fresh map, then stops mapping. If saving fails, the SLAM session remains active for retry. Existing map names are never overwritten.

The map canvas is a display by default. Clicking it cannot drive the robot until the navigation option is explicitly enabled. Map colors distinguish known free space, obstacles, and unknown regions; the arrow shows the estimated robot pose. A mapping restart may start a new SLAM session. Save any important map before switching engines or shutting down.

## Lidar pause / resume

**Pause scan data** stops movement, requests `/stop_scan`, and waits for scan data to stop. **Resume scan data** requests `/start_scan` and waits for fresh scans. The preference survives a guard restart. A driver error or timeout is shown instead of reporting unverified success.

This controls data acquisition. It does not verify physical rotation and did not stop the motor on the tested hardware. Mapping and navigation require fresh scans; camera-guided manual driving can remain available with scans paused. Resuming a scan never automatically resumes a driving task.

## Optional autonomous navigation

Open **Autonomous navigation** in the mapping panel and select **Enable navigation**. Wait for Nav2 and localization to become ready. Autonomous operation requires differential-drive mode and fresh chassis, camera, lidar, and map data.

- **Map goals:** enable **Allow map clicks to send driving goals**, then click known free space. The selected point is checked against the robot footprint. This action moves the robot.
- **Explore automatically:** selects reachable frontiers through Nav2. A run is bounded by two minutes, six meters, or twelve reached goals. The stop control remains available.
- **Return along route:** follows recorded odometry back toward the session start. Auto mode uses reverse only when rear lidar clearance is available; otherwise it turns and travels forward. This is a session route, not a persistent global “home.”

When exploration cannot find a route in a narrow area, it may attempt a lidar-checked straight step at 0.035 m/s, stopping at roughly 2.5 cm, a three-second deadline, or insufficient clearance. It then waits 2.5 seconds before planning again; this is a settling delay, not a guarantee of a new map revision. At most six such steps are attempted. Repeated step messages mean it is struggling to find a route, not that you should increase manual speed.

## Troubleshooting

| Symptom | Check / action |
| --- | --- |
| Browser cannot connect | Keep the SSH tunnel running; check `manage.sh status` and `curl http://127.0.0.1:8765/status` inside the robot environment. |
| Enable driving is unavailable | Verify fresh camera frames, chassis state, command-control mode, physical pause switch, and completion of any device/mapping operation. |
| Turning feels capped | Change **Turning** under Speed limits, apply, then re-enable driving. Confirm the applied value; manual settings do not change Nav2 limits. |
| Camera is dark or overexposed | Check lighting and supported camera controls in `bringup.launch.py`. Review auto exposure, gain, gamma, and anti-flicker frequency for your camera. |
| Lidar resumes but no scans arrive | Check serial power/connection and driver services. Pause must not terminate the driver process that provides resume. |
| Lidar still makes noise while paused | Data pause does not stop the motor. The UI cannot verify physical rotation. |
| Map does not appear | Verify `/scan`, `/map`, the `map → odom → base_link` transforms, and the mapping log. Allow up to 25 seconds for startup; retry after correcting the underlying error. |
| Map save fails | Check disk space, write permissions, and map freshness. Use a different name if it already exists. |
| Exploration stops repeatedly | Unknown space, narrow corridors, insufficient scan coverage, or obstacles can prevent a valid route. Continue manual mapping to improve coverage. |
| Optional desktop fails | Install the optional desktop tools and ensure local port 16080 is forwarded. This does not affect the primary console. |

Do not post raw logs, camera images, maps, hostnames, or connection details publicly without checking their contents.
