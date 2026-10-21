# Architecture and API

[中文](architecture.zh-CN.md) · [README](../README.md)

## Process boundaries

```text
Browser → computer companion :18765 → SSH → robot guard :8765
                 │                           ├─ gated /limo/cmd_vel → base
                 ├─ local video/frames       ├─ Nav2 /cmd_vel → guard
                 └─ verified MCAP archive    ├─ recorder :8766 → bounded MCAP spool
                                             ├─ camera :8767 → bounded RAM only
                                             └─ SLAM ← /scan_mapping ← raw /scan
```

All HTTP listeners use loopback. The companion owns recording independently of browser control polling. POST requests require `X-Limo-Control: 1`, a permitted Host and a matching Origin when supplied; the guard/companion limit bodies to 16 KiB. SSH supplies access control. Use one trusted operator; this is not a multi-user authorization system.

The 20 Hz gate requires fresh chassis/sensor state, fresh commands and a live control lease. Commands expire after 0.3 s; leases after 0.6 s. Recording health expires after 0.75 s, with an independent recorder worker-progress check. Faults disarm, discard commands and require explicit re-arming. `/control/stationary-mode` rejects all motion capabilities. A base-driver 350 ms watchdog covers loss of the guard publisher. These software mechanisms do not certify braking distances.

Nav2 reads raw lidar and publishes `/cmd_vel`; only the guard publishes `/limo/cmd_vel`. Mapping uses a separate scan channel that turns isolated far spikes into NaN, preserving unknown space. It never removes closer isolated obstacles from the raw collision input. Exploration has finite time, distance and speed budgets and no direct open-loop motion fallback.

## Data contract

One recorder writer serializes ingress and boundary commands. Non-image messages retain their original CDR bytes and complete ROS message schemas. MCAP log/publish times are receiver wall-clock timestamps; source ROS headers remain inside messages. A session-wide sequence identifies received samples. Sequence zero marks repeated TF/calibration context, not a new received sample. Instance boundaries use the same ordered queue and record sequence, robot monotonic time and wall time.

The camera selects frames at the requested rate and carries source ROS timestamp, capture monotonic/wall time, boot ID, generation, dimensions and sequence. The computer assigns frames to half-open monotonic instance intervals. H.264 uses JPEG transport; FFV1/PNG use verified lossless RGB transport. `frames.csv` records source sequence, capture/receive timestamps, presentation time and RGB hash. Lossless storage is relative to the ROS RGB frame, not camera sensor raw data.

The robot's image history is bounded by 120 frames and 32 MiB encoded bytes, plus a four-frame encoding queue. No image files are written there. Non-image chunks roll every 10 seconds or 64 MiB uncompressed. Spool limit and free-space reserve default to 2 GiB each; the computer reserves 5 GiB. Queue overflow, disk failure, transport gaps or health loss are surfaced and lock driving. The recorder's bounded queue is 32 MiB.

Transfer order is download → size/hash verification → file fsync → atomic rename/directory sync → durable receipt → ACK → robot durable deletion receipt → unlink. ACK retries are idempotent. Completed-instance manifests enumerate required chunk IDs; missing receipts prevent a complete status. Camera incidents remain attached to their instance. A crash can lose an unflushed tail; recovery preserves originals and declares incomplete status.

## HTTP capabilities

| Endpoint | Purpose |
| --- | --- |
| GET `/status`, `/scan`, `/camera.jpg`, `/navigation` | State, scan display, current frame, map/mission state |
| GET `/configuration` | Versioned configuration text and hashes |
| GET `/map.png?v=REV`, `/maps`, `/maps/download?name=NAME` | Revision-matched map, saved maps, PGM/YAML ZIP |
| POST `/stop` `{}` | Stop/disarm only; recording continues |
| POST `/arm` `{"mode":"manual"}` | Explicit arming after health checks |
| POST `/drive` `{"x":0,"z":0}` | Linear m/s and angular rad/s; refresh manual lease |
| POST `/heartbeat` `{"mission_id":"…"}` | Refresh matching navigation lease |
| POST `/manual/speed` `{"forward":0.1,"reverse":0.05,"angular":0.3}` | Stop and persist manual limits |
| POST `/mapping/start` `{"backend":"cartographer"}` | Start SLAM without a movement goal |
| POST `/mapping/save` `{"name":"room"}`, `/mapping/stop` `{}` | Save grid/checkpoint; save then finish |
| POST `/mapping/load` `{"name":"room","pose":[0,0,0]}` | Load grid and seed AMCL; pose is x/y/metres and yaw/radians |
| POST `/navigation/prepare` `{}` | Start SLAM/Nav2 services, no goal |
| POST `/navigation/goal` `{"x":1,"y":1}` | Validated map-frame target |
| POST `/navigation/explore` `{"max_seconds":20,"max_distance":0.5,"max_speed":0.08}` | Bounded frontier run; browser/client must maintain mission heartbeat |
| POST `/navigation/return` `{"mode":"auto"}` | Follow recorded return path; explicit motion operation |
| POST `/events` `{…}` | Record operator metadata |
| GET `/local/recording/status`, `/local/instances` | Computer recording state/history |
| POST `/local/recording/start`, `/local/recording/finish` `{}` | User-owned lifecycle; connection never starts recording |
| POST `/local/recording/next` `{"request_id":"unique-id","name":"route"}` | Idempotent split without ordinary stop |
| POST `/local/recording/profile` `{"width":640,"height":480,"fps":10,"format":"h264"}` | Stage next stopped boundary/start profile |
| POST `/local/recording/retry`, `/local/recording/open-folder` `{}` | Check fault recovery / reveal private local directory |

Async map/recording operations require polling until `busy`, `initializing` or `finishing` clears, then examining errors and evidence. HTTP acceptance is not physical success. Retired lidar write endpoints return 410. `/recording/*` and `/capture/*` are companion transport APIs; applications should use the local lifecycle endpoints rather than taking ownership of the robot recorder directly.

Offline replay/export never imports ROS, opens a network connection or publishes topics. It cannot issue chassis commands. See [harness validation](harness.md).
