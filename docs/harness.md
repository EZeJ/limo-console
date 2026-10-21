# Robot harness and acceptance

[中文](harness.zh-CN.md) · [README](../README.md)

The design takes the capability-composition idea from [Code as Policies](https://code-as-policies.github.io/) and implements an observation → bounded operation → evidence check → recorded result loop. It does not implement LLM-generated policy execution or require a model API. Deterministic control and Nav2 remain responsible for execution.

`harness/client.py` exposes `observe`, `stop`, `start_recording`, `next_instance`, `end_recording`, `start_mapping` and bounded `drive_for`. Motion requires constructing the client with `allow_motion=True` and still passes every robot gate. The default client cannot move. `Outcome.verified` refers to its named postcondition: for a bounded drive it confirms stop output, not a measured travel distance.

```python
from harness.client import LimoHarness
robot = LimoHarness()  # motion disabled
state = robot.observe()
assert robot.stop().verified  # does not end recording
```

Stationary diagnostics never arm:

```sh
.venv/bin/python -m harness.diagnose --seconds 60 --output /private/check.json
```

The report separately checks odometry displacement, map-pose drift, map availability and recording readiness. Routes and exploration remain explicitly untested by this stationary probe. `harness.replay` reads verified files locally and exports measurements; `harness.recover` salvages complete CRC-valid MCAP records without deleting its input. Neither contains ROS publication or network operations.

## Acceptance matrix

| Check | Required evidence |
| --- | --- |
| Recording lifecycle | Connection starts no session; stopping the car preserves the session and increasing samples; only explicit finish completes it |
| 20 instance boundaries | Received sensor sequences and camera timestamps partition without duplicates; ordinary splits issue no stop |
| Sustained recording | 30 minutes at selected profile; no unexplained missing received samples or camera sequence gaps; counters agree with archived files |
| Lossless video | Decode FFV1 / PNG and compare RGB pixel hashes with transport source hashes |
| Transfer faults | Corruption, truncation or interrupted ACK never delete an unverified robot copy; retry is idempotent |
| Storage / disconnect | Recording incidents are visible and originals retained; data faults do not gate driving, while loss of the driving lease stops motion |
| Session data library | Totals match segment files; batch failures remain visible; continuous playback advances at a boundary; downloaded ZIP hash and contents match |
| Static SLAM | 60 seconds, odometry displacement <2 cm, map-pose drift <5 cm and <2° |
| Dynamic SLAM | Independently measured 2 m straight route, 90° turn and closed loop; final pose error ≤15 cm / 5°; inspect wall consistency |
| Autonomous mapping | Three runs, each reaching at least three reachable frontiers without blind fallback; measured coverage growth and bounded stop |
| Save/reload | Complete grid and checkpoint, reload grid with actual pose, verify localization and retained obstacles |

Hardware-free tests cannot satisfy the dynamic rows. Publish aggregate results only after the corresponding run; real MCAP, video, maps and detailed reports stay outside this public repository. Do not claim success merely because `/map` is fresh or an HTTP request returned 200.

## Known limits

- DDS messages lost before recorder receipt cannot be reconstructed or proved absent by its ingress sequence.
- Hardware exposes angular velocity, not a physical steering-angle or wheel-encoder topic in the tested driver.
- Camera/radio/storage throughput depends on the selected native mode and load. A transient buffer overrun is an incident, not silently compressed out of the timeline.
- A robot under furniture or near a wall may lack a footprint-safe frontier. The controller can try a bounded, lidar-checked in-place scan turn with zero linear velocity, then replan. It stops if neither a safe path nor a clear turn is available.
- Recovered crash tails are incomplete. A restarted camera/robot can require an explicitly new session to establish valid clocks and sequence ownership.
