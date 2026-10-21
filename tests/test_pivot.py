from pathlib import Path
import sys,unittest,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'robot'))
from pivot import Pivot,rotation_clear
class PivotTests(unittest.TestCase):
    def test_all_pivot_outputs_have_zero_linear_velocity(self):
        for sign in (-1,1):
            turn=Pivot(0,0,angle=sign*.35)
            for i in range(8):
                command,done=turn.command(sign*.05*i,i*.2)
                self.assertEqual(command[0],0)
            self.assertTrue(done);self.assertEqual(command,(0,0))
    def test_rotation_sweep_checks_corners_not_only_current_footprint(self):
        self.assertTrue(rotation_clear([(0,.26)],.3))
        self.assertFalse(rotation_clear([(0,.26)],1.))
        self.assertFalse(rotation_clear([(.1,.1)],.3))
        self.assertFalse(rotation_clear([],.3))
    def test_wrap_and_timeout(self):
        turn=Pivot(math.pi-.1,0,angle=.3)
        turn.command(-math.pi+.1,1)
        self.assertAlmostEqual(turn.progress,.2)
        with self.assertRaises(ValueError):turn.command(-math.pi+.1,10)
