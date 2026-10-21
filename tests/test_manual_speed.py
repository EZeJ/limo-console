import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'robot'))
from safety import Gate
from speed_settings import load_limits, save_limits, validate_limits


class ManualSpeedTests(unittest.TestCase):
    def output(self, gate):
        return gate.output(100.1, .1, .1, 5., 5., 5., 0, 0,
                           camera_age=.1, vehicle_state=0, control_mode=1)[0]

    def test_user_limits_reach_manual_output_without_old_point_one_cap(self):
        gate = Gate(forward=.8, reverse=.6)
        gate.arm('manual', 100.); gate.receive(1., 0., 100.)
        self.assertEqual(self.output(gate), (.8, 0.))
        gate.receive(-1., 0., 100.)
        self.assertEqual(self.output(gate), (-.6, 0.))

    def test_speed_change_disarms_and_discards_existing_command(self):
        gate = Gate(); gate.arm('manual', 100.); gate.receive(.1, .3, 100.)
        gate.set_manual_limits(.9, .2, 1.2)
        self.assertEqual(gate.mode, 'stopped')
        self.assertEqual(self.output(gate), (0., 0.))

    def test_high_speed_does_not_bypass_watchdog(self):
        gate = Gate(forward=1., reverse=1., angular=2.)
        gate.arm('manual', 99.); gate.receive(1., 2., 100.)
        self.assertEqual(self.output(gate), (0., 0.))

    def test_manual_limits_do_not_raise_navigation_speed(self):
        gate = Gate(forward=1., reverse=1., angular=2.)
        gate.arm('navigation', 100.); gate.receive(1., 2., 100.)
        self.assertLessEqual(self.output(gate)[0], .5)
        self.assertEqual(self.output(gate)[1], .3)

    def test_turn_limit_applies_in_both_directions_and_zero_disables_turning(self):
        gate = Gate(angular=1.2)
        gate.arm('manual', 100.)
        for command, expected in ((2., 1.2), (-2., -1.2), (.8, .8)):
            gate.receive(0., command, 100.)
            self.assertEqual(self.output(gate), (0., expected))
        gate.set_manual_limits(.1, .05, 0.)
        gate.arm('manual', 100.); gate.receive(0., 2., 100.)
        self.assertEqual(self.output(gate), (0., 0.))

    def test_invalid_values_rejected(self):
        for value in (-.01, 1.01, math.nan, math.inf, True, '0.5', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_limits(value, .1)
        for value in (-.01, 2.01, math.nan, math.inf, True, '0.5', None):
            with self.subTest(angular=value), self.assertRaises(ValueError):
                validate_limits(.1, .1, value)

    def test_limits_persist_and_zero_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'speed.json'
            save_limits(path, .75, 0., 1.2)
            self.assertEqual(load_limits(path), {'forward': .75, 'reverse': 0., 'angular': 1.2})

    def test_existing_linear_limits_survive_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'speed.json'
            path.write_text('{"forward": 0.35, "reverse": 0.36}')
            self.assertEqual(load_limits(path), {'forward': .35, 'reverse': .36, 'angular': .3})


if __name__ == '__main__':
    unittest.main()
