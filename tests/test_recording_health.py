from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'robot'))
from recording_health import recording_problem
class OptionalRecordingTests(unittest.TestCase):
    def test_idle_recording_never_blocks_driving(self):
        self.assertEqual(recording_problem({'active':False,'ready':False},100),'')
        self.assertEqual(recording_problem({},float('inf')),'')
    def test_active_recording_fault_is_reported(self):
        self.assertTrue(recording_problem({'active':True,'ready':False},0))
        self.assertTrue(recording_problem({'active':True,'ready':True},1))
        self.assertEqual(recording_problem({'active':True,'ready':True},.1),'')
