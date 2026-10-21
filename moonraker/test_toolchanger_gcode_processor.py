import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

from moonraker.toolchanger_gcode_processor import Limits, load_component, process_file


class FakeFileManager:
    def __init__(self):
        self.name = None
        self.processor = None

    def register_gcode_processor(self, name, processor):
        self.name = name
        self.processor = processor


class FakeServer:
    def __init__(self):
        self.file_manager = FakeFileManager()

    def load_component(self, config, name):
        assert name == "file_manager"
        return self.file_manager


class FakeConfig:
    def __init__(self, enabled=False, values=None):
        self.server = FakeServer()
        self.enabled = enabled
        self.values = values or {}

    def get_server(self):
        return self.server

    def getboolean(self, name, default=False):
        return self.enabled if name == "enabled" else default

    def getfloat(self, name, default=None, **kwargs):
        return self.values.get(name, default)

    def error(self, message):
        return ValueError(message)


class ProcessorTests(unittest.TestCase):
    limits = Limits(0, 350, 0, 350)

    def test_component_registers_disabled_by_default_and_has_lifecycle_methods(self):
        config = FakeConfig()
        file_manager = config.server.file_manager
        component = load_component(config)
        self.assertEqual(file_manager.name, "toolchanger_destination")
        self.assertIsNotNone(file_manager.processor)
        processor = file_manager.processor or {}
        self.assertFalse(processor["enabled"])
        command = shlex.split(processor["command"])
        self.assertEqual(command[-2:], ["--process", "{gcode_file_path}"])
        command[-1] = "/first/upload.gcode"
        self.assertIn("{gcode_file_path}", shlex.split(processor["command"]))
        component.component_init()
        component.close()

    def test_registered_subprocess_command_processes_multiple_files(self):
        config = FakeConfig(enabled=True, values={
            "x_min": 0., "x_max": 350., "y_min": 0., "y_max": 350.
        })
        load_component(config)
        processor = config.server.file_manager.processor or {}
        command_template = shlex.split(processor["command"])
        source = (
            "G90\n"
            "_SLICER_CHANGE NEXT_EXTRUDER=0 NEXT_TEMP=220 X=495.128 Y=166.777 Z=9\n"
            "G1 Z9\nG1 X87.445 Y157.144\n"
        )
        expected = source.replace("X=495.128 Y=166.777", "X=87.44500 Y=157.14400")
        with tempfile.TemporaryDirectory() as directory:
            for index in range(2):
                path = Path(directory) / f"upload-{index}.gcode"
                path.write_text(source)
                command = [str(path) if arg == "{gcode_file_path}" else arg
                           for arg in command_template]
                result = subprocess.run(command, capture_output=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertEqual(path.read_text(), expected)
        self.assertIn("{gcode_file_path}", shlex.split(processor["command"]))

    def test_enabling_requires_explicit_axis_envelope(self):
        with self.assertRaisesRegex(ValueError, "requires x_min"):
            load_component(FakeConfig(enabled=True))

    def run_gcode(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.gcode"
            path.write_text(text)
            result = process_file(path, self.limits)
            return result, path.read_text()

    def test_safe_xy_then_z_file_is_byte_for_byte_unchanged(self):
        source = (
            "G90\n"
            "_SLICER_CHANGE NEXT_EXTRUDER=0 NEXT_TEMP=220 X=495.128 Y=166.777 Z=9\n"
            "M106 S255\nT0\n"
            "G1 E-.4 F1800\n"
            "G1 X87.445 Y157.144 F15000\n"
            "G1 Z9\n"
        )
        result, actual = self.run_gcode(source)
        self.assertEqual(result, (0, 0))
        self.assertEqual(actual, source)

    def test_z_descent_then_unambiguous_absolute_xy_repairs_only_destination(self):
        source = (
            "G90\n"
            "_SLICER_CHANGE NEXT_EXTRUDER=0 NEXT_TEMP=220 X=495.128 Y=166.777 Z=9 ; switch\n"
            "T0\n"
            "G1 Z9\n"
            "G1 X87.445 Y157.144 F15000\n"
        )
        expected = source.replace("X=495.128 Y=166.777", "X=87.44500 Y=157.14400")
        result, actual = self.run_gcode(source)
        self.assertEqual(result, (1, 0))
        self.assertEqual(actual, expected)

    def test_mismatched_following_tool_command_is_ambiguous(self):
        source = (
            "G90\n"
            "_SLICER_CHANGE NEXT_EXTRUDER=0 NEXT_TEMP=220 X=495.128 Y=166.777 Z=9\n"
            "T1\nG1 X87.445 Y157.144\nG1 Z9\n"
        )
        result, actual = self.run_gcode(source)
        self.assertEqual(result, (0, 1))
        self.assertEqual(actual, source)

    def test_relative_z_sequence_is_left_unchanged_and_flagged(self):
        source = (
            "G90\n"
            "_SLICER_CHANGE NEXT_EXTRUDER=0 NEXT_TEMP=220 X=495.128 Y=166.777 Z=9\n"
            "G91\nG1 Z-0.5\nG90\nG1 X87.445 Y157.144\n"
        )
        result, actual = self.run_gcode(source)
        self.assertEqual(result, (0, 1))
        self.assertEqual(actual, source)

    def test_extrusion_before_xy_keeps_transition_unchanged(self):
        source = (
            "G90\n"
            "_SLICER_CHANGE NEXT_EXTRUDER=0 NEXT_TEMP=220 X=495.128 Y=166.777 Z=9\n"
            "G1 Z9\nG1 E0.4\nG1 X87.445 Y157.144\n"
        )
        result, actual = self.run_gcode(source)
        self.assertEqual(result, (0, 1))
        self.assertEqual(actual, source)

    def test_candidate_outside_configured_range_is_not_substituted(self):
        source = (
            "G90\n"
            "_SLICER_CHANGE NEXT_EXTRUDER=0 NEXT_TEMP=220 X=495.128 Y=166.777 Z=9\n"
            "G1 Z9\nG1 X400 Y157.144\n"
        )
        result, actual = self.run_gcode(source)
        self.assertEqual(result, (0, 1))
        self.assertEqual(actual, source)

    def test_repair_preserves_non_utf8_comment_bytes(self):
        source = (
            "G90\n"
            "_SLICER_CHANGE NEXT_EXTRUDER=0 NEXT_TEMP=220 X=495.128 Y=166.777 Z=9 ; note \xff\n"
            "G1 Z9\nG1 X87.445 Y157.144\n"
        ).encode("latin-1")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.gcode"
            path.write_bytes(source)
            result = process_file(path, self.limits)
            actual = path.read_bytes()
        expected = source.replace(b"X=495.128 Y=166.777", b"X=87.44500 Y=157.14400")
        self.assertEqual(result, (1, 0))
        self.assertEqual(actual, expected)

    def test_repair_preserves_symlink_and_updates_target(self):
        source = (
            "G90\n"
            "_SLICER_CHANGE NEXT_EXTRUDER=0 NEXT_TEMP=220 X=495.128 Y=166.777 Z=9\n"
            "G1 Z9\nG1 X87.445 Y157.144\n"
        )
        expected = source.replace("X=495.128 Y=166.777", "X=87.44500 Y=157.14400")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.gcode"
            link = Path(directory) / "upload.gcode"
            target.write_text(source)
            link.symlink_to(target)
            result = process_file(link, self.limits)
            self.assertTrue(link.is_symlink())
            self.assertEqual(target.read_text(), expected)
        self.assertEqual(result, (1, 0))

    def test_valid_destination_is_untouched(self):
        source = (
            "G90\n"
            "_SLICER_CHANGE NEXT_EXTRUDER=0 NEXT_TEMP=220 X=100 Y=120 Z=9\n"
            "G1 Z9\nG1 X87.445 Y157.144\n"
        )
        result, actual = self.run_gcode(source)
        self.assertEqual(result, (0, 0))
        self.assertEqual(actual, source)


if __name__ == "__main__":
    unittest.main()
