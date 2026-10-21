"""Web missions use Nav2; every motion still passes through the command gate."""
import io
import hashlib
import math
import subprocess
import threading
import time
import uuid
from pathlib import Path as FilePath

from PIL import Image
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from lifecycle_msgs.srv import GetState
from nav_msgs.msg import OccupancyGrid, Path
from nav2_msgs.action import NavigateToPose, FollowPath, ComputePathToPose
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener

from navigation_core import Trail, transform_pose, validate_goal
from exploration import Explorer


def yaw(q):
    return math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))


class Navigation:
    ACTIVE = ('starting', 'navigating', 'returning', 'exploring')

    def __init__(self, control):
        self.node = control
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, control)
        self.goto = ActionClient(control, NavigateToPose, '/navigate_to_pose')
        self.follow = ActionClient(control, FollowPath, '/follow_path')
        self.planner = ActionClient(control, ComputePathToPose, '/compute_path_to_pose')
        self.grid = None
        self.map_is_static = False
        self.png = None
        self.revision = 0
        self.content_revision = 0
        self.map_digest = None
        self.map_statistics = {}
        self.trail = Trail()
        self.plan = []
        self.target = None
        self.phase = 'idle'
        self.message = 'Start mapping and navigation, then click a free point on the map.'
        self.mission = None
        self.handle = None
        self.last_heartbeat = 0.
        self.last_odom = 0.
        self.last_map = 0.
        self.distance_remaining = None
        self.recording = False
        self.preparing = False
        self.return_mode = None
        self.explorer = Explorer(self)
        self.leg = 0
        self.last_transform = None
        self.lifecycle = {}
        self.lifecycle_pending = {}
        self.lifecycle_clients = {name: control.create_client(GetState, '/'+name+'/get_state')
                                  for name in ('controller_server', 'planner_server', 'bt_navigator')}
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                         reliability=ReliabilityPolicy.RELIABLE)
        control.create_subscription(OccupancyGrid, '/map', self.on_map, qos)
        control.create_subscription(Path, '/plan', self.on_plan, 1)
        control.create_timer(1., self.poll_lifecycle)

    def poll_lifecycle(self):
        now = time.monotonic()
        for name, client in self.lifecycle_clients.items():
            pending = self.lifecycle_pending.get(name)
            if pending:
                future, started = pending
                if now-started < 3.:
                    continue
                client.remove_pending_request(future)
                self.lifecycle_pending.pop(name, None)
            if not client.service_is_ready():
                continue
            future = client.call_async(GetState.Request())
            self.lifecycle_pending[name] = (future, now)
            def done(f, name=name):
                with self.node.lock:
                    current = self.lifecycle_pending.get(name)
                    if current is None or current[0] is not f:
                        return
                    self.lifecycle_pending.pop(name, None)
                    try:
                        self.lifecycle[name] = (f.result().current_state.id == 3, time.monotonic())
                    except Exception:
                        self.lifecycle[name] = (False, time.monotonic())
            future.add_done_callback(done)

    def on_map(self, msg):
        if (msg.header.frame_id != 'map' or not 0 < msg.info.width*msg.info.height <= 2000000
                or len(msg.data) != msg.info.width*msg.info.height or not msg.info.resolution > 0):
            return
        origin = msg.info.origin
        grid = dict(width=msg.info.width, height=msg.info.height, resolution=msg.info.resolution,
                    origin=[origin.position.x, origin.position.y, yaw(origin.orientation)], data=list(msg.data))
        pixels = bytes(45 if v < 0 else 230 if v <= 25 else 90 if v < 65 else 8 for v in msg.data)
        img = Image.frombytes('L', (msg.info.width, msg.info.height), pixels).transpose(Image.FLIP_TOP_BOTTOM)
        out = io.BytesIO()
        img.save(out, format='PNG')
        with self.node.lock:
            digest=hashlib.sha256(bytes(v & 255 for v in msg.data)).hexdigest()
            if digest!=self.map_digest:self.content_revision+=1;self.map_digest=digest
            free=sum(0<=v<=25 for v in msg.data)
            occupied=sum(v>=65 for v in msg.data)
            self.map_statistics=dict(free_area_m2=round(free*msg.info.resolution**2,3),
                                     occupied_area_m2=round(occupied*msg.info.resolution**2,3),
                                     content_revision=self.content_revision)
            self.grid, self.png = grid, out.getvalue()
            self.revision += 1
            self.last_map = time.monotonic()

    def on_plan(self, msg):
        with self.node.lock:
            if self.phase == 'navigating' and msg.header.frame_id == 'map':
                self.plan = [[p.pose.position.x, p.pose.position.y] for p in msg.poses][::max(1, len(msg.poses)//500)]

    def odom_pose(self):
        o = self.node.odom
        return [o['x'], o['y'], o['yaw']]

    def on_odom(self):
        self.last_odom = time.monotonic()
        if self.recording:
            self.trail.append(self.odom_pose())
            if len(self.trail.points) > 4000:
                self.stop('Trip recording limit reached; stopped.')

    def transform(self):
        if time.monotonic()-self.last_odom > 1:
            raise ValueError('Odometry is not fresh')
        try:
            tf = self.buffer.lookup_transform('map', 'odom', Time())
        except Exception:
            raise ValueError('Waiting for map localization')
        age = self.node.get_clock().now().nanoseconds/1e9 - (tf.header.stamp.sec+tf.header.stamp.nanosec/1e9)
        if abs(age) > 2:
            raise ValueError('Map localization is stale')
        t = tf.transform
        result = [t.translation.x, t.translation.y, yaw(t.rotation)]
        self.last_transform = result
        return result

    def ready(self):
        now = time.monotonic()
        return (self.grid is not None and (self.map_is_static or now-self.last_map < 10) and
                self.goto.server_is_ready() and self.follow.server_is_ready() and
                all(self.lifecycle.get(n, (False, 0))[0] and now-self.lifecycle[n][1] < 4
                    for n in self.lifecycle_clients))

    def check_ready(self):
        self.node.require_motion_allowed()
        if self.preparing:
            raise ValueError("Wait for mapping setup to finish")
        if self.phase in self.ACTIVE or self.node.gate.mode != 'stopped':
            raise ValueError('Stop the current driving session first')
        if not self.ready():
            raise ValueError('Mapping and navigation are not ready yet')
        if not self.node.scan_quality.get('usable'):
            raise ValueError('Scan coverage or timestamps are unsuitable for navigation')
        now = time.monotonic()
        status = self.node.status
        if now-self.node.last_status > 1 or now-self.node.last_scan > 1:
            raise ValueError('Fresh chassis and lidar data are required')
        if status.get('vehicle_state') != 0 or status.get('control_mode') != 1 or status.get('error_code'):
            raise ValueError('Chassis paused or not ready; check the robot')
        if status.get('motion_mode') != 0:
            raise ValueError('Navigation requires four-wheel differential mode')
        return self.transform()

    def prepare(self, backend=None):
        if backend is not None and backend not in ("cartographer", "slam_toolbox"):
            raise ValueError("Unknown mapping engine")
        if self.preparing:
            return
        if self.phase in self.ACTIVE or self.node.gate.mode != 'stopped':
            raise ValueError('Stop driving before starting mapping')
        self.preparing = True
        self.message = 'Starting live mapping and navigation…'
        if backend is not None:
            self.phase = 'idle'
            self.trail = Trail()
            self.target, self.plan = None, []
            self.last_map = 0.
        command = ['bash', '/control/manage.sh'] + (['mapping-engine', backend] if backend else ['explore'])
        def work():
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=60)
                if result.returncode:
                    raise RuntimeError(result.stderr[-200:] or result.stdout[-200:])
                message = 'Waiting for the map and navigation services…'
            except Exception as exc:
                message = 'Could not start navigation: '+str(exc)
            with self.node.lock:
                self.preparing = False
                self.message = message
        threading.Thread(target=work, daemon=True).start()

    def pose_message(self, pose):
        msg = PoseStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.node.get_clock().now().to_msg()
        msg.pose.position.x, msg.pose.position.y = float(pose[0]), float(pose[1])
        msg.pose.orientation.z, msg.pose.orientation.w = math.sin(pose[2]/2), math.cos(pose[2]/2)
        return msg

    def navigate(self, x, y):
        transform = self.check_ready()
        x, y = float(x), float(y)
        validate_goal(self.grid, x, y)
        current = transform_pose(self.odom_pose(), transform)
        if math.hypot(x-current[0], y-current[1]) < .08:
            raise ValueError('That point is already within arrival tolerance')
        self.trail.reset(self.odom_pose())
        self.target = [x, y]
        self.plan = []
        self.recording = True
        self.return_mode = None
        goal = NavigateToPose.Goal()
        goal.pose = self.pose_message([x, y, math.atan2(y-current[1], x-current[0])])
        goal.behavior_tree = '/control/navigate.xml'
        self.send(self.goto, goal, 'navigating')

    def return_home(self, preference='auto'):
        transform = self.check_ready()
        if preference not in ('auto', 'reverse', 'forward'):
            raise ValueError('Unknown return mode')
        rear_ok = self.node.clearance[1] > .4
        if preference == 'reverse' and not rear_ok:
            raise ValueError('Rear lidar cannot confirm free space; use turn-and-return')
        reverse = preference != 'forward' and rear_ok
        points = self.trail.returning(self.odom_pose(), reverse)
        mapped = [transform_pose(p, transform) for p in points]
        # Follow the recorded route; do not replace it with a new shortest route.
        goal = FollowPath.Goal()
        goal.path.header.frame_id = 'map'
        goal.path.header.stamp = self.node.get_clock().now().to_msg()
        goal.path.poses = [self.pose_message(p) for p in mapped]
        goal.controller_id = 'ReturnReverse' if reverse else 'ReturnForward'
        goal.goal_checker_id = 'return_goal_checker'
        self.target = mapped[-1][:2]
        self.plan = [p[:2] for p in mapped]
        self.recording = False
        self.return_mode = 'reverse' if reverse else 'forward'
        self.send(self.follow, goal, 'returning')

    def send(self, client, goal, phase):
        self.mission = token = self.mission if self.explorer.active else uuid.uuid4().hex
        self.leg += 1
        leg = self.leg
        self.phase = 'starting'
        self.message = 'Planning a route…' if phase == 'navigating' else 'Preparing the recorded return route…'
        self.last_heartbeat = time.monotonic()
        self.distance_remaining = None
        def feedback(msg):
            with self.node.lock:
                if self.mission == token:
                    f = msg.feedback
                    self.distance_remaining = float(getattr(f, 'distance_remaining', getattr(f, 'distance_to_goal', 0.)))
        future = client.send_goal_async(goal, feedback_callback=feedback)
        def accepted(f):
            with self.node.lock:
                try:
                    handle = f.result()
                    if self.mission != token or self.leg != leg or time.monotonic()-self.last_heartbeat > .6:
                        if handle.accepted:
                            handle.cancel_goal_async()
                        if self.mission == token:
                            self.stop('Connection timeout before route started.')
                        return
                    if not handle.accepted:
                        self.stop('Navigation rejected this route.', 'failed')
                        return
                    self.handle = handle
                    self.node.gate.arm('navigation', time.monotonic())
                    self.phase = phase
                    self.message = 'Exploration: driving to a target with obstacle checks.' if self.explorer.active else ('Navigating to the selected point.' if phase == 'navigating' else ('Reversing along the recorded route.' if self.return_mode == 'reverse' else 'Turning and following the recorded route home.'))
                    handle.get_result_async().add_done_callback(finished)
                except Exception as exc:
                    if self.mission == token:
                        self.stop('Navigation error: '+str(exc), 'failed')
        def finished(f):
            with self.node.lock:
                if self.mission != token or self.leg != leg:
                    return
                try:
                    status = f.result().status
                    if self.recording:
                        self.trail.append(self.odom_pose(), force=True)
                    if self.explorer.active:
                        self.explorer.finish_leg(status)
                        return
                    self.handle = None
                    self.node.gate.stop()
                    self.recording = False
                    self.mission = None
                    if status == GoalStatus.STATUS_SUCCEEDED:
                        self.phase = 'arrived' if phase == 'navigating' else 'home'
                        self.message = 'Arrived. The actual route is recorded for return.' if phase == 'navigating' else 'Returned to the starting point.'
                    else:
                        self.phase = 'failed'
                        self.message = 'Route stopped or blocked. Check the surroundings before retrying.'
                except Exception as exc:
                    self.stop('Navigation result error: '+str(exc), 'failed')
        future.add_done_callback(accepted)

    def heartbeat(self, token):
        if not token or token != self.mission or self.phase not in self.ACTIVE:
            raise ValueError('This navigation session has ended')
        self.last_heartbeat = self.node.gate.lease = time.monotonic()

    def stop(self, message='Navigation stopped.', phase='cancelled'):
        if self.phase in self.ACTIVE:
            self.node.get_logger().info('Mission stopped: '+message)
        if self.recording and self.node.odom:
            self.trail.append(self.odom_pose(), force=True)
        self.node.gate.stop()
        self.explorer.stop()
        self.recording = False
        self.mission = None
        if self.handle is not None:
            try:
                self.handle.cancel_goal_async()
            except Exception:
                pass
            self.handle = None
        if self.phase in self.ACTIVE or phase == 'failed':
            self.phase, self.message = phase, message

    def tick(self):
        if self.phase not in self.ACTIVE:
            return
        if time.monotonic()-self.last_heartbeat > .6:
            self.stop('Browser connection lost; navigation stopped.')
        elif self.phase not in ('starting', 'exploring') and self.node.gate.mode != 'navigation':
            self.stop('Motion guard stopped navigation: '+self.node.reason)
        elif not self.ready() or time.monotonic()-self.node.last_scan > 1 or time.monotonic()-self.node.last_status > 1:
            self.stop('Map, navigation or sensor data unavailable; stopped.')
        elif self.node.status.get('vehicle_state') != 0 or self.node.status.get('control_mode') != 1 or self.node.status.get('error_code'):
            self.stop('Chassis paused or not ready; stopped.')
        else:
            try:
                self.transform()
                if self.explorer.active:
                    self.explorer.tick()
            except ValueError as exc:
                self.stop(str(exc))

    def status(self, compact=False):
        transform = None
        pose = None
        try:
            transform = self.transform()
            pose = transform_pose(self.odom_pose(), transform)
        except ValueError:
            pass
        trail = [transform_pose(p, transform)[:2] for p in self.trail.points] if transform and not compact else []
        home = transform_pose(self.trail.points[0], transform)[:2] if transform and self.trail.points else None
        grid = {k:v for k,v in self.grid.items() if k != 'data'} if self.grid else None
        ready = self.ready() and pose is not None and not self.preparing
        message = self.message
        if ready and self.phase == 'idle':
            message = 'Click a mapped free point to plan and drive there.'
        return dict(mapping_backend=FilePath('/control/mapping-engine').read_text().strip() if FilePath('/control/mapping-engine').exists() else 'slam_toolbox', ready=ready, preparing=self.preparing, phase=self.phase, message=message,
                    mission_id=self.mission, pose=pose, target=self.target, map=grid, revision=self.revision,
                    trail=trail, plan=[] if compact else self.plan, home=home,
                    return_available=self.trail.length >= .06 and self.phase not in self.ACTIVE and self.phase != 'home',
                    reverse_available=self.node.clearance[1] > .4 and time.monotonic()-self.node.last_scan < 1,
                    return_mode=self.return_mode, distance_remaining=self.distance_remaining,
                    exploration=self.explorer.status())
