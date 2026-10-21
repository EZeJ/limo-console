"""Nonblocking lidar control with persisted intent and observed scan verification."""
import json
import time
from pathlib import Path


class LidarControl:
    def __init__(self, start_client, stop_client, request_factory,
                 state_path='/control/lidar-state.json', clock=time.monotonic):
        self.start_client, self.stop_client = start_client, stop_client
        self.request_factory, self.clock = request_factory, clock
        self.path = Path(state_path)
        self.target_paused = self.read_paused(self.path)
        self.state = 'waiting'
        self.error = ''
        self.pending = None
        self.client = None
        self.needs_command = self.target_paused
        self.started = clock()
        self.acknowledged = False

    @staticmethod
    def read_paused(path):
        try:
            data = json.loads(Path(path).read_text())
            return data.get('paused') is not False
        except FileNotFoundError:
            return False
        except (OSError, ValueError, AttributeError):
            return True

    @property
    def busy(self):
        return self.needs_command or self.pending is not None or self.state in ('starting', 'pausing')

    def request(self, paused):
        if self.busy:
            if paused == self.target_paused:
                return
            raise ValueError('Lidar state is changing. Please wait before retrying.')
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'paused': paused})+'\n')
        temporary.replace(self.path)
        self.target_paused = paused
        self.error = ''
        self.acknowledged = False
        self.needs_command = True
        self.started = self.clock()
        self.state = 'pausing' if paused else 'starting'

    def fail(self, message):
        if self.pending is not None:
            self.client.remove_pending_request(self.pending)
        self.pending = None
        self.needs_command = False
        self.state = 'error'
        self.error = message

    def tick(self, scan_age):
        now = self.clock()
        if self.busy and now-self.started > 12:
            self.fail('Lidar change timed out. Check the connection and retry.')
            return
        if self.pending is not None and self.pending.done():
            try:
                self.pending.result()
            except Exception:
                self.fail('Lidar driver could not execute the command. Please retry.')
                return
            self.pending = None
            self.acknowledged = True
        if self.needs_command:
            self.client = self.stop_client if self.target_paused else self.start_client
            if not self.client.service_is_ready():
                return
            try:
                self.pending = self.client.call_async(self.request_factory())
            except Exception:
                self.fail('Cannot reach the lidar control service.')
                return
            self.needs_command = False
            self.state = 'pausing' if self.target_paused else 'starting'
            return
        if self.pending is not None or self.state == 'error':
            return
        if self.target_paused:
            if self.acknowledged and scan_age >= 1:
                self.state = 'paused'
            elif self.state == 'paused' and scan_age < 1:
                # Reapply the saved setting if the driver restarts independently.
                self.needs_command = True
                self.acknowledged = False
                self.started = now
                self.state = 'pausing'
        elif scan_age < 1 and (self.state != 'starting' or now-scan_age >= self.started):
            self.state = 'running'
        elif self.state != 'starting':
            self.state = 'offline'

    def snapshot(self):
        messages = {
            'waiting': 'Connecting to lidar control service',
            'pausing': 'Pausing scan data…',
            'paused': 'Scan data paused; this function does not stop the lidar motor.',
            'starting': 'Resuming scan data…',
            'running': 'Lidar is scanning',
            'offline': 'No lidar data. Try resuming the scan.',
            'error': self.error,
        }
        return dict(state=self.state, requested_paused=self.target_paused,
                    paused=self.state == 'paused', busy=self.busy, motor_rotation_verified=False,
                    available=self.start_client.service_is_ready() and self.stop_client.service_is_ready(),
                    message=messages[self.state], error=self.error)

    def require_scanning(self):
        if self.target_paused or self.busy or self.state != 'running':
            raise ValueError('Resume lidar and wait for fresh scans before mapping or navigation.')
