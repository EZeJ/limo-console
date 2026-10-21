#!/usr/bin/env python3
"""Local visual preview. Synthetic data only; no ROS imports or robot connection."""
import argparse
import io
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'robot'))
from speed_settings import validate_limits

LIMITS = {'forward': .10, 'reverse': .05, 'angular': .30}
META = {'width': 320, 'height': 240, 'resolution': .05, 'origin': [-8., -6., 0.]}
map_image = Image.new('L', (320, 240), 45)
draw = ImageDraw.Draw(map_image)
draw.rectangle((38, 30, 286, 214), fill=8)
draw.rectangle((43, 35, 281, 209), fill=230)
for wall in [(117, 35, 122, 99), (117, 127, 122, 208), (43, 120, 90, 125), (147, 132, 281, 137), (205, 35, 210, 89)]:
    draw.rectangle(wall, fill=8)
for furniture in [(59, 52, 98, 79), (147, 58, 181, 89), (235, 52, 261, 83), (59, 155, 94, 191), (165, 168, 243, 190)]:
    draw.rectangle(furniture, fill=8)
stream = io.BytesIO()
map_image.save(stream, format='PNG')
MAP_PNG = stream.getvalue()
CAMERA_SVG = b'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600"><defs><linearGradient id="floor" x2="0" y2="1"><stop stop-color="#c4d3d1"/><stop offset="1" stop-color="#899e9b"/></linearGradient><linearGradient id="wall"><stop stop-color="#d9e2df"/><stop offset="1" stop-color="#afbfb9"/></linearGradient></defs><rect width="800" height="600" fill="#d4ded9"/><path d="M0 0H800L578 130H220Z" fill="#eef2ec"/><path d="M0 0 220 130V335L0 600Z" fill="url(#wall)"/><path d="M800 0 578 130V335L800 600Z" fill="#adbfba"/><path d="M220 130H578V335H220Z" fill="#d6e0d8"/><path d="M0 600 220 335H578L800 600Z" fill="url(#floor)"/><g stroke="#7e9792" stroke-width="1" opacity=".35"><path d="M0 600 290 335M150 600 340 335M350 600 400 335M560 600 465 335M800 600 525 335M175 390H625M110 470H690M35 558H765"/></g><rect x="332" y="164" width="122" height="171" rx="2" fill="#98aba4"/><rect x="340" y="171" width="106" height="164" fill="#465f5b"/><rect x="348" y="180" width="92" height="155" fill="#5e7771"/><circle cx="428" cy="255" r="3" fill="#c8d8cb"/><path d="m50 218 112 30v162L50 456Z" fill="#425f59"/><path d="m59 231 45 12v159L59 432Z" fill="#67837a"/><g stroke="#8fa89b" stroke-width="3"><path d="m62 285 40-2M62 338l40-20M62 390l40-40"/></g><path d="m605 278 120-35 44 59-131 51Z" fill="#e7e8d9"/><path d="m638 353 131-51v55L638 420Z" fill="#a0b6ab"/><path d="m638 353-33-75v55l33 87" fill="#819e91"/><path d="m654 420 6 35m91-80v28" stroke="#6e887d" stroke-width="7"/><path d="M501 325v-59" stroke="#648d71" stroke-width="5"/><g fill="#789d7a"><ellipse cx="486" cy="266" rx="20" ry="9" transform="rotate(25 486 266)"/><ellipse cx="516" cy="252" rx="19" ry="9" transform="rotate(-35 516 252)"/><ellipse cx="490" cy="240" rx="15" ry="8" transform="rotate(35 490 240)"/></g><path d="m482 314 6 28h28l6-28Z" fill="#bdc9b3"/><path d="M350 600Q363 444 390 365" stroke="#54c5b0" stroke-width="3" stroke-dasharray="12 10" opacity=".6"/><path d="m381 377 9-17 8 18" fill="none" stroke="#54c5b0" stroke-width="3"/><rect x="1" y="1" width="798" height="598" fill="none" stroke="#1e474130" stroke-width="2"/></svg>'''


def navigation():
    return {'mapping_backend': 'cartographer', 'ready': False, 'preparing': False, 'phase': 'idle',
            'message': 'Preview only. Connect a robot to drive or map.', 'mission_id': None,
            'pose': [-.6, -.7, .9], 'target': None, 'map': META, 'revision': 1,
            'trail': [[-2.2, -2.8], [-2.2, -1.5], [-1.4, -.8], [-.6, -.7]], 'plan': [],
            'home': [-2.2, -2.8], 'return_available': False, 'reverse_available': False,
            'return_mode': None, 'distance_remaining': None, 'exploration': {'active': False, 'save_message': ''}}


def status():
    return {'demo': True, 'mode': 'stopped', 'reason': 'Stopped',
            'chassis': {'battery_voltage': 11.8, 'vehicle_state': 0, 'control_mode': 1, 'error_code': 0, 'motion_mode': 0},
            'odometry': {'linear': 0., 'angular': 0.}, 'output': [0., 0.],
            'chassis_online': True, 'camera_online': True, 'lidar_online': True,
            'manual_speed': dict(LIMITS, rated_max=1., angular_max=2.),
            'lidar': {'state': 'running', 'message': 'Lidar is scanning', 'busy': False, 'available': True, 'requested_paused': False},
            'mapping': {'active': True, 'busy': False, 'waiting': False, 'operation': 'idle', 'message': 'Preview only. Connect a robot to drive or map.', 'error': '', 'last_saved': None, 'revision': 1, 'map': META},
            'navigation': navigation()}


class Preview(BaseHTTPRequestHandler):
    def respond(self, body, content_type='application/json', code=200):
        if isinstance(body, dict): body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/status': self.respond(status())
        elif path == '/navigation': self.respond(navigation())
        elif path == '/scan':
            points = []
            for i in range(90):
                a = i * math.tau / 90
                radius = min(2.6 / max(abs(math.cos(a)), .1), 1.7 / max(abs(math.sin(a)), .1))
                points.append([radius*math.cos(a), radius*math.sin(a)])
            self.respond({'online': True, 'points': points})
        elif path == '/maps': self.respond({'maps': []})
        elif path == '/camera.jpg': self.respond(CAMERA_SVG, 'image/svg+xml')
        elif path == '/map.png': self.respond(MAP_PNG, 'image/png')
        elif path in ('/', '/app.js', '/style.css', '/i18n.js', '/messages.js'):
            name = 'index.html' if path == '/' else path[1:]
            kind = 'text/html' if name.endswith('.html') else 'text/css' if name.endswith('.css') else 'application/javascript'
            self.respond((ROOT/'robot/web'/name).read_bytes(), kind+'; charset=utf-8')
        else: self.send_error(404)

    def do_POST(self):
        if self.path == '/stop': return self.respond(status())
        if self.path == '/manual/speed':
            try:
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 1024: raise ValueError('Request too large')
                values = json.loads(self.rfile.read(size))
                LIMITS.update(validate_limits(**values))
                return self.respond(status())
            except (ValueError, TypeError): return self.respond({'error': 'Invalid speed limits'}, code=400)
        self.respond({'error': 'Preview only. Connect a robot to drive or map.'}, code=409)

    def log_message(self, *_): pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18766)
    args = parser.parse_args()
    print(f'Limo Console preview: http://127.0.0.1:{args.port}/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Preview).serve_forever()
