import unittest
from unittest.mock import MagicMock
from harness.client import LimoHarness
class HarnessTests(unittest.TestCase):
    def test_motion_is_disabled_by_default(self):
        client=LimoHarness();client.request=MagicMock()
        with self.assertRaises(ValueError):client.drive_for(.1,0,1)
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
