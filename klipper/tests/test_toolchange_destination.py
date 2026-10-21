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
        tc = object.__new__(toolchanger.Toolchanger)
        tc.gcode_transform = types.SimpleNamespace(tool=None)
        tc.gcode = Mock()
        tc.gcode_move = Mock()
        tc.gcode_move.get_status.return_value = {"absolute_coordinates": False}
        tc.last_change_absolute_coord = False
        tc.last_change_gcode_offset = [0.0, 0.0, 0.0]
        tc.last_change_restore_axis = "XYZ"
        commands = []
        tc.gcode.run_script_from_command.side_effect = commands.append
        tc.gcode.create_gcode_command.side_effect = lambda *args: args
        tc.gcode_move.cmd_G1.side_effect = lambda command: commands.append(command)

        tc._restore_state_and_transform(object(), [41.0, 82.0, 0.25])

        self.assertEqual(commands[0], "RESTORE_GCODE_STATE NAME=_toolchange_state MOVE=0")
        self.assertEqual(commands[1], "G90")
        self.assertEqual(commands[2][2], {"X": 41.0, "Y": 82.0})
        self.assertEqual(commands[3], "G91")
        self.assertFalse(any(isinstance(command, tuple) and "Z" in command[2]
                             for command in commands))
        self.assertIsNone(tc.last_change_gcode_offset)

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
