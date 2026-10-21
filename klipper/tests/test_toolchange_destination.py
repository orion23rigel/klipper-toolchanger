import importlib
import os
import sys
import types
import unittest
from unittest.mock import Mock


# The extension checkout omits Klipper's upstream probe.py, so stub the
# unrelated probe extension dependency when importing toolchanger.py in tests.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_probe_module = types.ModuleType("klipper.extras.tool_probe_endstop")
sys.modules.setdefault("klipper.extras.tool_probe_endstop", _probe_module)
toolchanger = importlib.import_module("klipper.extras.toolchanger")


class FakeGcmd:
    error = ValueError

    def __init__(self, values):
        self.values = values

    def get_float(self, key, default=None):
        value = self.values.get(key, default)
        return default if value is None else float(value)


class ToolchangeDestinationTest(unittest.TestCase):
    def make_toolchanger_for_destination_restore(self, absolute_coordinates=True):
        tc = object.__new__(toolchanger.Toolchanger)
        tc.gcode_transform = types.SimpleNamespace(tool=None)
        tc.gcode = Mock()
        tc.gcode_move = Mock()
        tc.gcode_move.get_status.return_value = {
            "absolute_coordinates": absolute_coordinates,
            "homing_origin": [0.0, 0.0, 0.0],
        }
        kin_status = {
            "axis_minimum": [-2.0, -2.0, 0.0],
            "axis_maximum": [350.0, 350.0, 300.0],
        }
        toolhead = Mock()
        toolhead.get_kinematics().get_status.return_value = kin_status
        tc.printer = Mock()
        tc.printer.lookup_object.return_value = toolhead
        tc.printer.get_reactor().monotonic.return_value = 1.0
        tc.last_change_absolute_coord = absolute_coordinates
        tc.last_change_gcode_offset = [0.0, 0.0, 0.0]
        tc.last_change_restore_axis = "XYZ"
        return tc

    def test_destination_requires_all_three_coordinates(self):
        with self.assertRaisesRegex(ValueError, "X, Y, and Z"):
            toolchanger.Toolchanger._get_toolchange_destination(
                object.__new__(toolchanger.Toolchanger), FakeGcmd({"X": "10", "Y": "20"}))

    def test_destination_rejects_non_finite_coordinates(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            toolchanger.Toolchanger._get_toolchange_destination(
                object.__new__(toolchanger.Toolchanger), FakeGcmd({"X": "nan", "Y": "20", "Z": "0.2"}))

    def test_missing_destination_preserves_legacy_path_indicator(self):
        self.assertIsNone(
            toolchanger.Toolchanger._get_toolchange_destination(
                object.__new__(toolchanger.Toolchanger), FakeGcmd({})))

    def test_destination_moves_xy_without_descending_and_restores_relative_mode(self):
        tc = self.make_toolchanger_for_destination_restore(absolute_coordinates=False)
        commands = []
        tc.gcode.run_script_from_command.side_effect = commands.append
        tc.gcode.create_gcode_command.side_effect = lambda *args: args
        tc.gcode_move.cmd_G1.side_effect = lambda command: commands.append(command)

        tool = types.SimpleNamespace(gcode_x_offset=0.0, gcode_y_offset=0.0)
        tc._restore_state_and_transform(tool, [41.0, 82.0, 0.25])

        self.assertEqual(commands[0], "RESTORE_GCODE_STATE NAME=_toolchange_state MOVE=0")
        self.assertEqual(commands[1], "G90")
        self.assertEqual(commands[2][2], {"X": 41.0, "Y": 82.0})
        self.assertEqual(commands[3], "G91")
        self.assertFalse(any(isinstance(command, tuple) and "Z" in command[2]
                             for command in commands))
        self.assertIsNone(tc.last_change_gcode_offset)

    def test_out_of_bounds_destination_is_skipped_without_error(self):
        tc = self.make_toolchanger_for_destination_restore(absolute_coordinates=False)
        commands = []
        tc.gcode.run_script_from_command.side_effect = commands.append
        tc.gcode.create_gcode_command.side_effect = lambda *args: args
        tc.gcode_move.cmd_G1.side_effect = lambda command: commands.append(command)
        tool = types.SimpleNamespace(gcode_x_offset=0.0, gcode_y_offset=0.0)

        tc._restore_state_and_transform(tool, [495.128, 166.777, 9.0])

        tc.gcode_move.cmd_G1.assert_not_called()
        tc.gcode.respond_info.assert_called_once()
        self.assertIn("X target 495.128 is outside configured range",
                      tc.gcode.respond_info.call_args[0][0])
        self.assertEqual(commands, [
            "RESTORE_GCODE_STATE NAME=_toolchange_state MOVE=0",
            "G91",
        ])

    def test_destination_bounds_include_tool_and_homing_offsets(self):
        tc = self.make_toolchanger_for_destination_restore()
        tc.gcode_move.get_status.return_value = {
            "homing_origin": [3.0, -2.0, 0.0],
        }
        tool = types.SimpleNamespace(gcode_x_offset=4.0, gcode_y_offset=1.0)

        self.assertIsNone(
            tc._destination_bounds_error([340.0, 340.0, 9.0], tool))
        self.assertIn(
            "X target 351.000 is outside configured range",
            tc._destination_bounds_error([344.0, 340.0, 9.0], tool))

    def test_no_destination_keeps_existing_axis_restore_behavior(self):
        tc = object.__new__(toolchanger.Toolchanger)
        tc.gcode_transform = types.SimpleNamespace(tool=None)
        tc.gcode = Mock()
        tc.gcode_move = Mock()
        tc.last_change_gcode_offset = [0.0, 0.0, 0.0]
        tc.last_change_gcode_position = [1.0, 2.0, 3.0]
        tc.last_change_restore_axis = "XYZ"
        commands = []
        tc.gcode.run_script_from_command.side_effect = commands.append
        tc._restore_axis = Mock()

        tc._restore_state_and_transform(object(), None)

        tc._restore_axis.assert_called_once()
        self.assertEqual(commands, [
            "RESTORE_GCODE_STATE NAME=_toolchange_state MOVE=0",
            "RESTORE_GCODE_STATE NAME=_toolchange_state MOVE=0",
        ])


if __name__ == "__main__":
    unittest.main()
