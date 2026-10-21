from pathlib import Path
import sys,unittest,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'robot'))
from pivot import Pivot,rotation_clear
from safety import Gate
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
    def test_pivot_gate_never_allows_linear_motion_or_an_unchecked_sweep(self):
        gate=Gate();gate.arm('navigation',10);gate.pivot_active=True;gate.pivot_clear=True
        gate.receive(0,.3,10)
        args=(10.1,.1,.1,.2,0,.2,0,0)
        self.assertEqual(gate.output(*args)[0],(0,.18))
        gate.receive(.05,.2,10)
        self.assertEqual(gate.output(*args)[0],(0,0))
        gate.receive(0,.2,10);gate.pivot_clear=False
        self.assertEqual(gate.output(*args)[0],(0,0))
        gate.stop();self.assertFalse(gate.pivot_active)
    def test_wrap_and_timeout(self):
        turn=Pivot(math.pi-.1,0,angle=.3)
        turn.command(-math.pi+.1,1)
        self.assertAlmostEqual(turn.progress,.2)
        with self.assertRaises(ValueError):turn.command(-math.pi+.1,10)
    def test_full_circle_integrates_yaw_wrap_and_stops(self):
        turn=Pivot(2.8,0,angle=2*math.pi)
        for i in range(72):
            yaw=math.atan2(math.sin(2.8+i*.09),math.cos(2.8+i*.09))
            command,done=turn.command(yaw,i*.5)
            self.assertEqual(command[0],0)
            if done:break
        self.assertTrue(done);self.assertEqual(command,(0,0))
        self.assertAlmostEqual(turn.progress,6.3)
    def test_full_sweep_includes_body_corners_in_every_direction(self):
        self.assertFalse(rotation_clear([(.24,0)],2*math.pi))
        self.assertFalse(rotation_clear([(-.26,0)],-2*math.pi))
        self.assertTrue(rotation_clear([(.29,0),(0,-.4)],2*math.pi))
