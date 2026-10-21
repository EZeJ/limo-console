import json
from concurrent.futures import Future
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'robot'))
from lidar_control import LidarControl
from safety import Gate


class Client:
    def __init__(self):
        self.ready = True
        self.calls = []
        self.removed = []

    def service_is_ready(self):
        return self.ready

    def call_async(self, request):
        f = Future()
        self.calls.append(f)
        return f

    def remove_pending_request(self, future):
        self.removed.append(future)


class LidarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'state.json'
        self.start, self.stop = Client(), Client()
        self.now = 100.
        self.lidar = LidarControl(self.start, self.stop, object,
                                  self.path, lambda: self.now)
        self.lidar.tick(.1)

    def test_pause_waits_for_service_ack_and_stream_to_stop(self):
        self.lidar.request(True)
        self.lidar.tick(.1)
        self.assertEqual(self.lidar.state, 'pausing')
        self.lidar.tick(2)
        self.assertNotEqual(self.lidar.state, 'paused')
        self.stop.calls[0].set_result(object())
        self.lidar.tick(.1)
        self.assertEqual(self.lidar.state, 'pausing')
        self.lidar.tick(2)
        self.assertEqual(self.lidar.state, 'paused')
        with self.assertRaises(ValueError):
            self.lidar.require_scanning()
        self.assertTrue(json.loads(self.path.read_text())['paused'])

    def test_resume_requires_fresh_data_and_preserves_no_motion_state(self):
        self.lidar.request(True); self.lidar.tick(2)
        self.stop.calls[0].set_result(object()); self.lidar.tick(2)
        self.lidar.request(False); self.lidar.tick(3)
        self.start.calls[0].set_result(object()); self.lidar.tick(3)
        self.assertEqual(self.lidar.state, 'starting')
        self.now += 1
        self.lidar.tick(.1)
        self.assertEqual(self.lidar.state, 'running')
        self.lidar.require_scanning()
        self.assertFalse(json.loads(self.path.read_text())['paused'])

    def test_timeout_does_not_report_success_and_can_retry(self):
        self.lidar.request(True); self.lidar.tick(.1)
        self.now += 13; self.lidar.tick(2)
        self.assertEqual(self.lidar.state, 'error')
        self.assertEqual(len(self.stop.removed), 1)
        self.lidar.request(True); self.lidar.tick(2)
        self.assertEqual(len(self.stop.calls), 2)

    def test_restarted_guard_reapplies_persisted_pause(self):
        self.path.write_text('{"paused": true}')
        lidar = LidarControl(self.start, self.stop, object, self.path, lambda: self.now)
        lidar.tick(.1)
        self.assertEqual(len(self.stop.calls), 1)
        self.assertTrue(lidar.target_paused)

    def test_paused_guard_reapplies_pause_after_driver_restart(self):
        self.lidar.request(True); self.lidar.tick(2)
        self.stop.calls[0].set_result(object()); self.lidar.tick(2)
        self.lidar.tick(.1); self.lidar.tick(.1)
        self.assertEqual(len(self.stop.calls), 2)

    def test_concurrent_opposite_request_rejected(self):
        self.lidar.request(True)
        with self.assertRaises(ValueError):
            self.lidar.request(False)
        self.assertTrue(self.lidar.target_paused)

    def test_driver_missing_is_an_error_after_timeout(self):
        self.stop.ready = False
        self.lidar.request(True); self.lidar.tick(.1)
        self.now += 13; self.lidar.tick(.1)
        self.assertEqual(self.lidar.state, 'error')
        self.assertFalse(self.lidar.snapshot()['available'])

    def test_invalid_saved_state_defaults_to_pause(self):
        self.path.write_text('broken')
        self.assertTrue(LidarControl.read_paused(self.path))

    def test_navigation_gate_stops_on_stale_lidar(self):
        g = Gate(); g.arm('navigation', 100.); g.receive(.1, 0, 100.)
        command, _ = g.output(100.1, .1, 2., 2., 2., 2., 0, 0,
                              camera_age=.1, vehicle_state=0, control_mode=1)
        self.assertEqual(command, (0., 0.))
        self.assertEqual(g.mode, 'stopped')

    def test_manual_camera_control_remains_available_while_lidar_paused(self):
        g = Gate(); g.arm('manual', 100.); g.receive(.1, 0, 100.)
        command, _ = g.output(100.1, .1, 20., 0., 0., 0., 0, 0,
                              camera_age=.1, vehicle_state=0, control_mode=1)
        self.assertEqual(command, (.1, 0.))


if __name__ == '__main__':
    unittest.main()
