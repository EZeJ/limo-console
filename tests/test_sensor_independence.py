from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'robot'))
from safety import Gate
class SensorIndependenceTests(unittest.TestCase):
    def output(self,mode,scan_age=.1):
        gate=Gate();gate.arm(mode,10);gate.receive(.05,0,10)
        return gate.output(10.1,.1,scan_age,2,2,2,0,0,camera_age=100)
    def test_missing_camera_does_not_block_manual_or_navigation(self):
        for mode in ('manual','navigation'):self.assertGreater(self.output(mode)[0][0],0)
    def test_missing_lidar_still_stops_navigation(self):
        self.assertEqual(self.output('navigation',2)[0],(0,0))
