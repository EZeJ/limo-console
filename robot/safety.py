"""Command gate independent of ROS, so timeout behavior can be tested."""
import math
from speed_settings import validate_limits


class Gate:
    def __init__(self, forward=.10, reverse=.05, angular=.30):
        self.mode = 'stopped'
        self.lease = float('-inf')
        self.command_time = float('-inf')
        self.command = (0.0, 0.0)
        self.manual_limits = validate_limits(forward, reverse, angular)

    def set_manual_limits(self, forward, reverse, angular=.30):
        limits = validate_limits(forward, reverse, angular)
        self.stop()
        self.manual_limits = limits

    def stop(self):
        self.mode = 'stopped'
        self.command = (0.0, 0.0)
        self.command_time = float('-inf')

    def arm(self, mode, now):
        if mode not in ('manual', 'navigation'):
            raise ValueError('Mode must be manual or navigation')
        self.stop()
        self.mode, self.lease = mode, now

    def receive(self, x, z, now):
        if not all(math.isfinite(v) for v in (x, z)):
            raise ValueError('Velocity must be finite')
        forward = self.manual_limits['forward'] if self.mode == 'manual' else .50
        reverse = self.manual_limits['reverse'] if self.mode == 'manual' else .05
        angular = self.manual_limits['angular'] if self.mode == 'manual' else .30
        self.command = (max(-reverse, min(forward, x)), max(-angular, min(angular, z)))
        self.command_time = now

    def output(self, now, status_age, scan_age, front, rear, closest, error, motion_mode, camera_age=0, vehicle_state=0, control_mode=1):
        if vehicle_state != 0:
            self.stop()
            return (0.0, 0.0), 'Chassis paused or not ready (state %s); check the robot pause button' % vehicle_state
        if control_mode != 1:
            self.stop()
            return (0.0, 0.0), 'Chassis is not in command control mode'
        if self.mode == 'stopped':
            return (0.0, 0.0), 'Stopped'
        if now - self.lease > 0.6:
            self.stop()
            return (0.0, 0.0), 'Connection timeout; re-arm required'
        if status_age > 1.0 or (self.mode == 'navigation' and scan_age > 1.0) or (self.mode == 'manual' and camera_age > 2.0):
            self.stop()
            return (0.0, 0.0), 'Sensor timeout; re-arm required'
        if error:
            self.stop()
            return (0.0, 0.0), 'Chassis reports error %s' % error
        if self.mode == 'navigation' and motion_mode != 0:
            self.stop()
            return (0.0, 0.0), 'Navigation requires four-wheel differential mode'
        if now - self.command_time > 0.3:
            return (0.0, 0.0), 'Waiting for command'
        x, z = self.command
        if self.mode == 'manual':
            # Operator judges obstacles from the camera; the camera does not see behind.
            return (max(-self.manual_limits['reverse'], min(self.manual_limits['forward'], x)),
                    max(-self.manual_limits['angular'], min(self.manual_limits['angular'], z))), 'Camera-guided manual control'
        if x > 0 and front == 0:
            return (0.0, 0.0), 'No usable front lidar returns'
        if x < 0 and rear == 0:
            return (0.0, 0.0), 'No usable rear lidar returns'
        if (x > 0 and front < 0.35) or (x < 0 and rear < 0.4) or (z and closest < 0.25):
            return (0.0, 0.0), 'Obstacle close to chassis'
        if x > 0:
            # v*t + v²/(2*a) must fit before the 0.35 m stand-off.
            # Budget sensor age plus command/watchdog latency; use the Nav2
            # configured 0.3 m/s² braking rate. Slow turns and stale scans.
            latency, braking = max(0., scan_age)+.4, .3
            available = max(0., front-.35)
            maximum = math.sqrt((braking*latency)**2+2*braking*available)-braking*latency
            x = min(x, maximum, .18 if abs(z) > .10 else .5,
                    .15 if scan_age > .25 else .5)
        return (x, z), 'Ready'
