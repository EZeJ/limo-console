#!/usr/bin/env python3
"""Loopback-only control API, reached over an SSH tunnel."""
import json
import hashlib
import io
import math
from pathlib import Path
import threading
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from PIL import Image as PILImage

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan, Image
from limo_msgs.msg import LimoStatus
from action_msgs.srv import CancelGoal
from std_msgs.msg import String
from safety import Gate
from navigation import Navigation
from lidar_health import LidarHealth
from scan_quality import scan_metrics
from mapping_control import MappingControl, export_map
from speed_settings import load_limits, save_limits, RATED_MAX, ANGULAR_MAX


class Control(Node):
    def __init__(self):
        super().__init__('limo_console_guard')
        self.lock = threading.RLock()
        self.stationary_lock = Path('/control/stationary-mode')
        self.speed_settings_path = Path('/control/manual-speed.json')
        self.gate = Gate(**load_limits(self.speed_settings_path))
        self.last_status = self.last_scan = self.last_camera = float('-inf')
        self.status = {}
        self.odom = {}
        self.clearance = (0.0, 0.0, 0.0)
        self.scan_points = []
        self.lidar_points = []
        self.scan_quality = {}
        self.reason = 'Stopped'
        self.output = (0.0, 0.0)
        self.jpeg = None
        self.last_jpeg = 0.0
        self.pub = self.create_publisher(Twist, '/limo/cmd_vel', 1)
        self.cancel = self.create_client(CancelGoal, '/navigate_to_pose/_action/cancel_goal')
        self.cancel_follow = self.create_client(CancelGoal, '/follow_path/_action/cancel_goal')
        self.lidar = LidarHealth()
        self.recording = {'ready': False, 'active': False}
        self.last_recording = float('-inf')
        self.event_sequence = 0
        self.event_pub = self.create_publisher(String, '/console/events', 100)
        self.tick_pub = self.create_publisher(String, '/console/control_tick', 100)
        self.create_subscription(String, '/console/recording_health', self.on_recording_health, 10)
        self.navigation = Navigation(self)
        self.mapping = MappingControl(self.navigation, self.lock)
        self.create_subscription(LimoStatus, '/limo_status', self.on_status, 10)
        self.create_subscription(Odometry, '/odom', self.on_odom, 10)
        self.create_subscription(LaserScan, '/scan', self.on_scan, qos_profile_sensor_data)
        self.create_subscription(Image, '/camera/image_raw', self.on_camera, QoSProfile(depth=1))
        self.create_subscription(Twist, '/cmd_vel', self.on_nav, 1)
        self.create_timer(0.05, self.tick)

    def on_status(self, msg):
        with self.lock:
            self.last_status = time.monotonic()
            self.status = {k: getattr(msg, k) for k in ('battery_voltage', 'vehicle_state', 'control_mode', 'error_code', 'motion_mode')}

    def on_odom(self, msg):
        with self.lock:
            p, q = msg.pose.pose.position, msg.pose.pose.orientation
            self.odom = dict(x=p.x, y=p.y, yaw=math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z)), linear=msg.twist.twist.linear.x, angular=msg.twist.twist.angular.z)
            self.navigation.on_odom()

    def on_camera(self, msg):
        self.last_camera = time.monotonic()

    def on_recording_health(self, msg):
        try:
            status = json.loads(msg.data)
            if not isinstance(status, dict): return
            with self.lock:
                self.recording = status
                self.last_recording = time.monotonic()
        except (ValueError, TypeError): pass

    def recording_problem(self):
        if time.monotonic()-self.last_recording > .75:
            return 'Recording service is unavailable; driving is locked'
        if not self.recording.get('ready'):
            return self.recording.get('error') or 'Computer recording is not ready; driving is locked'
        return ''

    def require_recording(self):
        if self.stationary_lock.exists():
            raise ValueError('Stationary maintenance mode; driving is locked')
        reason = self.recording_problem()
        if reason: raise ValueError(reason)

    def log_event(self, name, data):
        self.event_sequence += 1
        event = String()
        event.data = json.dumps(dict(sequence=self.event_sequence, event=name, data=data,
                                    monotonic_ns=time.monotonic_ns(), wall_ns=time.time_ns()), allow_nan=False)
        self.event_pub.publish(event)

    def on_scan(self, msg):
        with self.lock:
            self.scan_quality = scan_metrics(msg,self.get_clock().now().nanoseconds)
            front, rear, closest = [], [], []
            points = []
            all_points = []
            for i, distance in enumerate(msg.ranges):
                if not math.isfinite(distance) or distance < msg.range_min or distance > msg.range_max:
                    continue
                angle = msg.angle_min + i * msg.angle_increment
                all_points.append((0.103+distance*math.cos(angle), distance*math.sin(angle)))
                if i % 2 == 0:
                    points.append([round(0.103 + distance * math.cos(angle), 3), round(distance * math.sin(angle), 3)])
                closest.append(distance)
                if math.cos(angle) > 0.7:
                    front.append(distance)
                if math.cos(angle) < -0.7:
                    rear.append(distance)
            # A scan containing no usable returns cannot establish clear space.
            self.clearance = tuple(min(v) if v else 0.0 for v in (front, rear, closest))
            self.scan_points = points
            self.lidar_points = all_points
            self.last_scan = time.monotonic()

    def on_nav(self, msg):
        with self.lock:
            if self.gate.mode == 'navigation':
                try:
                    speed=msg.linear.x
                    if self.navigation.explorer.active:speed=min(speed,self.navigation.explorer.max_speed)
                    self.gate.receive(speed, msg.angular.z, time.monotonic())
                except ValueError:
                    self.gate.stop()

    def tick(self):
        with self.lock:
            now = time.monotonic()
            self.lidar.tick(now-self.last_scan)
            recording_problem = self.recording_problem()
            motion_problem = ('Stationary maintenance mode; driving is locked'
                              if self.stationary_lock.exists() else recording_problem)
            if motion_problem and (self.gate.mode != 'stopped' or self.navigation.explorer.active):
                self.navigation.stop(motion_problem)
                self.gate.stop()
            self.navigation.tick()
            self.output, self.reason = self.gate.output(now, now-self.last_status, now-self.last_scan, *self.clearance, self.status.get('error_code', 0), self.status.get('motion_mode', -1), camera_age=now-self.last_camera, vehicle_state=self.status.get('vehicle_state', -1), control_mode=self.status.get('control_mode', -1))
            msg = Twist()
            msg.linear.x, msg.angular.z = self.output
            self.pub.publish(msg)
            audit = String()
            audit.data = json.dumps(dict(monotonic_ns=time.monotonic_ns(), wall_ns=time.time_ns(),
                                        mode=self.gate.mode, requested=self.gate.command, output=self.output,
                                        reason=self.reason, limits=self.gate.manual_limits, odometry=self.odom,
                                        recording_ready=not bool(recording_problem)), allow_nan=False)
            self.tick_pub.publish(audit)
            if motion_problem and self.gate.mode == 'stopped': self.reason = motion_problem

    def stop_motion(self):
        self.navigation.stop()
        self.gate.stop()
        self.tick()
        for client in (self.cancel, self.cancel_follow):
            if client.service_is_ready():
                client.call_async(CancelGoal.Request())

    def request(self, path, data):
        with self.lock:
            now = time.monotonic()
            if path not in ('/status', '/heartbeat'):
                self.log_event('request', {'path':path, 'arguments':data})
            if path in ('/arm', '/drive', '/navigation/goal', '/navigation/explore', '/navigation/return'):
                self.require_recording()
            if path in ('/navigation/prepare', '/navigation/goal', '/navigation/explore', '/navigation/return'):
                self.lidar.require_scanning()
            if path == '/mapping/start':
                self.lidar.require_scanning()
            if path == '/stop':
                self.stop_motion()
            elif path == '/manual/speed':
                self.stop_motion()
                limits = save_limits(self.speed_settings_path, data.get('forward'), data.get('reverse'),
                                     data.get('angular', self.gate.manual_limits['angular']))
                self.gate.set_manual_limits(**limits)
            elif path in ('/mapping/start', '/mapping/save', '/mapping/stop','/mapping/load'):
                self.stop_motion()
                self.mapping.request(path.rsplit('/', 1)[-1], data.get('name'), data.get('backend'),data.get('pose'))
            elif path == '/arm':
                if data.get('mode') == 'navigation':
                    self.lidar.require_scanning()
                if self.navigation.preparing:
                    raise ValueError('Wait for mapping setup to finish')
                if now-self.last_status > 1:
                    raise ValueError('Chassis must be online before arming')
                if self.status.get('vehicle_state') != 0:
                    raise ValueError('Chassis paused or not ready; check the robot pause button')
                if self.status.get('control_mode') != 1:
                    raise ValueError('Chassis is not in command control mode')
                if data.get('mode') == 'manual' and now-self.last_camera > 2:
                    raise ValueError('Camera must be online for manual driving')
                if data.get('mode') == 'navigation' and now-self.last_scan > 1:
                    raise ValueError('Lidar must be online for navigation')
                if self.status.get('error_code'):
                    raise ValueError('Chassis reports an error')
                if data.get('mode') == 'navigation' and self.status.get('motion_mode') != 0:
                    raise ValueError('Navigation requires four-wheel differential mode')
                self.navigation.stop()
                self.gate.arm(data['mode'], now)
                for client in (self.cancel, self.cancel_follow):
                    if client.service_is_ready():
                        client.call_async(CancelGoal.Request())
            elif path == '/heartbeat':
                if data.get('mission_id'):
                    self.navigation.heartbeat(data['mission_id'])
                else:
                    self.gate.lease = now
            elif path == '/navigation/prepare':
                self.navigation.prepare(data.get("backend"))
            elif path == '/navigation/goal':
                self.navigation.navigate(data['x'], data['y'])
            elif path == '/navigation/explore':
                self.navigation.explorer.start(data.get('max_seconds',120),data.get('max_distance',6),data.get('max_speed',.15))
            elif path == '/navigation/return':
                self.navigation.return_home(data.get('mode', 'auto'))
            elif path == '/drive':
                if self.gate.mode != 'manual':
                    raise ValueError('Manual control is not armed')
                self.gate.receive(float(data['x']), float(data['z']), now)
                self.gate.lease = now
            elif path != '/status':
                raise ValueError('Unknown endpoint')
            return dict(mode=self.gate.mode, reason=self.reason, chassis=self.status,
                        stationary_mode=self.stationary_lock.exists(),
                        recording=dict(self.recording, ready=not bool(self.recording_problem())),
                        manual_speed=dict(self.gate.manual_limits, rated_max=RATED_MAX, angular_max=ANGULAR_MAX),
                        odometry=self.odom, output=self.output,
                        front_clearance=self.clearance[0], rear_clearance=self.clearance[1],
                        chassis_online=now-self.last_status < 1,
                        lidar_online=now-self.last_scan < 1,
                        lidar=self.lidar.snapshot(),
                        scan_quality=self.scan_quality,
                        mapping=self.mapping.status(),
                        camera_online=now-self.last_camera < 2,
                        navigation={k:v for k,v in self.navigation.status(compact=True).items()
                                    if k not in ('map', 'trail', 'plan')})


def main():
    rclpy.init()
    node = Control()

    class Handler(BaseHTTPRequestHandler):
        def valid_host(self):
            return self.headers.get('Host') in ('127.0.0.1:18765', 'localhost:18765', '127.0.0.1:8765')

        def bytes_reply(self, body, kind):
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def proxy(self, target, data=None):
            request = Request(target, data=data, headers={'X-Limo-Control':'1', 'Content-Type':'application/json'})
            try: response = urlopen(request, timeout=25 if data is not None else 5)
            except HTTPError as exc: response = exc
            except (URLError, TimeoutError) as exc:
                self.bad_request('Robot service unavailable: '+str(exc)); return
            with response:
                self.send_response(response.status)
                for name in ('Content-Type','Content-Length','X-Limo-Frame'):
                    if response.headers.get(name): self.send_header(name,response.headers[name])
                self.send_header('Cache-Control','no-store');self.end_headers()
                try:
                    for block in iter(lambda:response.read(256*1024),b''):self.wfile.write(block)
                except (BrokenPipeError,ConnectionResetError):pass

        def do_GET(self):
            if not self.valid_host():
                self.send_error(403)
                return
            path = urlsplit(self.path).path
            if path.startswith('/recording/'):
                return self.proxy('http://127.0.0.1:8766'+self.path[len('/recording'):])
            if path.startswith('/capture/'):
                return self.proxy('http://127.0.0.1:8767'+self.path[len('/capture'):])
            if path == '/':
                self.bytes_reply(Path('/control/web/index.html').read_bytes(), 'text/html; charset=utf-8')
            elif path in ('/app.js', '/messages.js', '/i18n.js', '/recording.js', '/style.css'):
                kind = 'application/javascript' if path.endswith('.js') else 'text/css'
                self.bytes_reply(Path('/control/web'+path).read_bytes(), kind+'; charset=utf-8')
            elif path == '/camera.jpg':
                self.proxy('http://127.0.0.1:8767/frame')
            elif path == '/status':
                self.reply('/status', {})
            elif path == '/configuration':
                files={}
                for name in ('bringup.launch.py','lidar.yaml','slam.yaml','cartographer.lua','nav2_params.yaml','navigate.xml','scan_quality.py','safety.py'):
                    value=Path('/control',name).read_bytes()
                    files[name]={'sha256':hashlib.sha256(value).hexdigest(),'text':value.decode()}
                self.bytes_reply(json.dumps({'version':1,'files':files}).encode(),'application/json')
            elif path == '/navigation':
                with node.lock:
                    body = json.dumps(node.navigation.status()).encode()
                self.bytes_reply(body, 'application/json')
            elif path == '/maps':
                self.bytes_reply(json.dumps({'maps': node.mapping.list_maps()}).encode(), 'application/json')
            elif path == '/maps/download':
                try:
                    name = parse_qs(urlsplit(self.path).query).get('name', [''])[0]
                    body = export_map(node.mapping.maps, name)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/zip')
                    self.send_header('Content-Disposition', 'attachment; filename="'+name+'.zip"')
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    self.wfile.write(body)
                except (ValueError, OSError) as exc:
                    self.bad_request(str(exc))
            elif path == '/map.png':
                with node.lock:
                    body = node.navigation.png
                    # The browser must use image pixels and coordinates from
                    # the same map revision, especially while SLAM expands it.
                    requested = urlsplit(self.path).query
                    if requested.startswith('v=') and requested != 'v='+str(node.navigation.revision):
                        self.send_error(409, 'Map updated; request current metadata')
                        return
                if body is None:
                    self.send_error(503, 'Map not ready')
                else:
                    self.bytes_reply(body, 'image/png')
            elif path == '/scan':
                with node.lock:
                    online = time.monotonic()-node.last_scan < 1
                    scan = dict(points=node.scan_points if online else [], online=online,
                                lidar=node.lidar.snapshot(),
                                front=node.clearance[0], rear=node.clearance[1])
                self.bytes_reply(json.dumps(scan).encode(), 'application/json')
            else:
                self.send_error(404)

        def do_POST(self):
            origin = self.headers.get('Origin')
            if not self.valid_host() or (origin and origin != 'http://' + self.headers.get('Host', '')) or self.headers.get('X-Limo-Control') != '1':
                self.send_error(403)
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 <= size <= 16384:
                    raise ValueError('Request too large')
                data = json.loads(self.rfile.read(size) or b'{}')
                if self.path in ('/lidar/pause','/lidar/resume'):
                    self.send_error(410,'Lidar control has been removed');return
                if self.path.startswith('/recording/'):
                    if self.path == '/recording/finish': node.request('/stop', {})
                    return self.proxy('http://127.0.0.1:8766'+self.path[len('/recording'):], json.dumps(data).encode())
                if self.path == '/capture/configure':
                    node.request('/stop', {})
                    return self.proxy('http://127.0.0.1:8767/configure',json.dumps(data).encode())
                if self.path == '/events':
                    with node.lock: node.log_event('operator',data)
                    return self.reply('/status',{})
                if self.path == '/desktop':
                    node.request('/stop', {})
                    subprocess.run(['bash', '/control/manage.sh', 'desktop'], check=True, timeout=20)
                    self.reply('/status', {})
                    return
                self.reply(self.path, data)
            except (ValueError, KeyError, TypeError) as exc:
                self.bad_request(str(exc))

        def bad_request(self, message):
            body = json.dumps({'error': message}).encode()
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def reply(self, path, data):
            try:
                body = json.dumps(node.request(path, data)).encode()
            except (ValueError, KeyError, TypeError) as exc:
                self.bad_request(str(exc))
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.gate.stop()
        if rclpy.ok():
            try: node.tick()
            except Exception: pass
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
