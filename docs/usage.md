# User guide

[中文](usage.zh-CN.md) · [README](../README.md)

## Record, drive, split

1. Run `scripts/connect.sh USER@ROBOT_HOST` on the computer. Opening the page does not start recording.
2. Choose a recording profile if needed, then click **Start recording**. Wait for the capture and archival health checks. Driving remains locked until recording is ready.
3. Enable manual drive. Hold W/A/S/D, arrows or a direction button; release to stop. Space and either Stop button disarm immediately. Stops do **not** end recording.
4. Press **N** or **Next instance** to mark a new route/task. An optional name labels the next instance. This does not stop driving or restart subscriptions.
5. Click **End recording** when the session is over. The robot stops, video containers are finalized and remaining sensor chunks are archived. Keep the companion running until completion.

A browser refresh does not change recording ownership. Closing the browser leaves recording running in the companion. Closing the companion or losing power interrupts collection and must not be treated as a normal user finish.

Forward and reverse limits are independently adjustable from 0 to 1 m/s, and left/right turning share a 0–2 rad/s limit. Saving limits stops and disarms. Autonomous exploration has separate bounded limits. Manual driving does not perform automatic obstacle avoidance.

## Files and profiles

Use **Open folder** to see `~/Documents/Limo Console/recordings/SESSION/INSTANCE/`. A directory contains `manifest.json`, `frames.csv`, `camera.mp4` or `camera.mkv` or `frames/*.png`, and `sensors/*.mcap` with verified receipts. Session-level `configuration.json` captures source configuration and hashes. Paths are private and never uploaded by the console.

Default: 640×480 at 10 fps, JPEG transport and H.264 MP4 storage. FFV1 and PNG use lossless PNG transport from raw RGB/BGR pixels, with a pixel hash checked before writing. “Lossless” is relative to the ROS RGB image, not sensor raw/Bayer data. Native resolution is confirmed after applying a camera setting; there is no upscaling disguised as a higher resolution.

Profiles apply at the next instance boundary while the robot is stopped, or at the next recording start. Profile changes can create a camera reconfiguration interval; frames retain their original timestamps. A five-second rate check rejects clearly unsustainable choices. Hardware support does not guarantee sustained throughput at every resolution/rate.

Raw `/scan`, `/odom`, `/imu`, TF, camera calibration, chassis state, navigation/map topics, operator events and command-gate ticks are recorded when published and supported. Actual steering-angle and wheel-encoder channels are unavailable from the tested driver. Do not interpret commanded angular velocity as measured steering angle.

Export a completed instance without ROS or a robot connection:

```sh
.venv/bin/python -m harness.replay '/private/path/SESSION/INSTANCE' --export
```

Outputs include odometry, derived acceleration, IMU, requested/applied control and event CSVs, plus validation JSON. IMU acceleration includes gravity and bias; odometry acceleration is a finite difference. Original messages remain in MCAP. Sequence verification covers messages received by the recorder, not losses upstream of its subscription. Frame timestamps align camera capture with robot monotonic time and preserve the source ROS stamp; they are not a claim of hardware synchronization.

## Mapping

Start mapping while stopped, then drive slowly with overlap between observations. Camera and lidar continue running. The mapping scan filter rejects isolated far returns only; raw scans are preserved and remain the collision input. Observe free-area growth, localization and map shape. A live grid is not proof of an accurate route.

Save a unique map name. The save creates PGM/YAML and a Cartographer `.pbstream` or SLAM Toolbox `.posegraph`/`.data` checkpoint. Download ZIP contains the portable PGM/YAML pair; checkpoints stay in `/control/maps/`. Save-and-finish stops SLAM after a successful save. Exploration's emergency/terminal map snapshot is a grid snapshot, not a full SLAM checkpoint.

To load a map, first save and finish the current mapping session. In **Autonomous navigation**, select the saved map and enter the robot's actual X, Y and heading on that map. **Load saved map & localize** starts AMCL without a driving goal. Check that the displayed robot pose matches reality before explicitly navigating. Checkpoint resume in a backend-specific SLAM process is an advanced operation; loading the grid is localization, not automatic restoration of an editable SLAM session.

Automatic exploration checks footprint-safe targets with Nav2. There is no blind straight-step or spin fallback. If a route is unavailable or the map does not change after a target, exploration stops with a reason. Recording continues. Default exploration budget: 120 seconds, 6 metres, 0.15 m/s. The HTTP API can request tighter bounds.

## Recovery

- A recording fault stops/disarms driving, preserves the session and reports the gap or failure. Available streams continue. After fixing a transient network/storage problem, **Retry recording** checks recovery without creating a new session; driving still needs re-enabling. A robot/camera-process restart may require explicitly ending the interrupted session and starting another.
- Never delete a robot chunk merely because it was downloaded. The companion acknowledges only after length/hash checks and durable local file/receipt writes; interrupted or mismatched transfers retain the robot copy.
- Incomplete robot MCAP files are preserved and marked interrupted. Copy them privately to the computer, then salvage complete CRC-valid records:

  ```sh
  .venv/bin/python -m harness.recover interrupted.partial.mcap recovered.mcap
  ```

  Recovery never overwrites the input and never labels a recovered tail as complete. Unflushed bytes/frames at a crash can be unrecoverable. Fragmented MP4 and partial CSVs are retained for inspection; do not rename them and assume completeness.
- If the camera is dark, first check ambient light, lens obstruction and the supported exposure controls. Recording quality cannot recover absent illumination.
- Stationary maintenance is indicated explicitly. Removing `/control/stationary-mode` allows future arming; it does not arm or move the robot.
