import math,unittest
from unittest.mock import MagicMock,patch
from harness.client import LimoHarness,Outcome
class HarnessTests(unittest.TestCase):
    def test_motion_is_disabled_by_default(self):
        client=LimoHarness();client.request=MagicMock()
        with self.assertRaises(ValueError):client.drive_for(.1,0,1)
        client.request.assert_not_called()
        with self.assertRaises(ValueError):client.scan_in_place()
        client.request.assert_not_called()
    def test_stop_verifies_output_and_does_not_end_recording(self):
        client=LimoHarness();client.request=MagicMock(side_effect=[{}, {'mode':'stopped','output':[0,0],'recording':{'active':True}}])
        result=client.stop()
        self.assertTrue(result.verified);self.assertTrue(result.evidence['recording']['active'])
        self.assertEqual([c.args[0] for c in client.request.call_args_list],['/stop','/status'])
    def test_stationary_lock_blocks_even_explicit_motion_client(self):
        client=LimoHarness(allow_motion=True);client.request=MagicMock(return_value={'stationary_mode':True})
        with self.assertRaises(ValueError):client.drive_for(.1,0,1)
        client.request.assert_called_once_with('/status')
    def test_full_scan_verifies_unwrapped_rotation_and_zero_linear_output(self):
        client=LimoHarness(allow_motion=True)
        def state(yaw,active):return {'odometry':{'yaw':yaw},'output':[0,.18 if active else 0],
            'navigation':{'exploration':{'active':active},'message':'' if active else '360° lidar scan complete. Robot stopped.'}}
        client.observe=MagicMock(side_effect=[state(0,False),state(math.pi/2,True),state(math.pi,True),state(-math.pi/2,True),state(0,False)])
        client.request=MagicMock(return_value={'navigation':{'mission_id':'scan'}})
        client.stop=MagicMock(return_value=Outcome('stop',True,{}))
        with patch('harness.client.time.sleep'):result=client.scan_in_place()
        self.assertTrue(result.verified);self.assertAlmostEqual(result.evidence['rotation_rad'],2*math.pi)
        client.stop.assert_called_once()
    def test_scan_transport_error_still_stops(self):
        client=LimoHarness(allow_motion=True);client.observe=MagicMock(return_value={'odometry':{'yaw':0}})
        client.request=MagicMock(side_effect=RuntimeError('connection lost'));client.stop=MagicMock()
        with self.assertRaises(RuntimeError):client.scan_in_place()
        client.stop.assert_called_once()
