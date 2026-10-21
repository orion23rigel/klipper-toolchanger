#!/usr/bin/env python3
"""Conservative Moonraker upload-time repair for toolchanger destinations.

This module is both a Moonraker component (when linked into its components
package) and the subprocess invoked by Moonraker's G-code metadata processor.
It only rewrites an out-of-bounds destination when a bounded scan proves that
an absolute, pure XY move follows a Z descent before any extrusion/other move.
All other files/transitions are left byte-for-byte unchanged.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import shlex
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

VERSION = "0.1.0"
_WORD_RE = re.compile(r"(?<!\S)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\s;]+)")
_MOTION_RE = re.compile(r"^\s*(G0|G00|G1|G01)\b", re.IGNORECASE)
_CHANGE_RE = re.compile(r"^\s*(?:_SLICER_CHANGE|SELECT_TOOL|T\d+)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Limits:
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def contains(self, x: float, y: float) -> bool:
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max


def _code(line: str) -> str:
    # Semicolon comments are universal in the supported slicer output. Parenthesis
    # comments are deliberately not stripped: encountering unusual syntax should
    # make a transition unclassifiable, not invite a guessed rewrite.
    return line.split(";", 1)[0].strip()


def _words(line: str) -> Dict[str, str]:
    return {key.upper(): value for key, value in _WORD_RE.findall(_code(line))}


def _motion_words(line: str) -> Dict[str, str]:
    """Parse conventional G-code axis words such as X12.3 and E-.4."""
    return {key.upper(): value for key, value in
            re.findall(r"(?<![A-Za-z0-9_])([A-Za-z])([+-]?(?:[0-9]+(?:[.][0-9]*)?|[.][0-9]+))", _code(line))}


def _command(line: str) -> str:
    code = _code(line)
    return code.split(None, 1)[0].upper() if code else ""


def _is_toolchange(line: str) -> bool:
    return bool(_CHANGE_RE.match(_code(line)))


def _out_of_bounds_destination(line: str, limits: Limits) -> bool:
    words = _words(line)
    try:
        x, y = float(words["X"]), float(words["Y"])
    except (KeyError, ValueError):
        return False
    return not limits.contains(x, y)


def _replace_xy(line: str, x: float, y: float) -> str:
    code, sep, comment = line.partition(";")
    code = re.sub(r"(?<!\S)X\s*=\s*[^\s;]+", f"X={x:.5f}", code, count=1, flags=re.IGNORECASE)
    code = re.sub(r"(?<!\S)Y\s*=\s*[^\s;]+", f"Y={y:.5f}", code, count=1, flags=re.IGNORECASE)
    return code + (sep + comment if sep else "")


def _next_xy_if_recoverable(stream, start_absolute: bool, layer_z: float,
                            max_lines: int, max_bytes: int,
                            expected_tool: Optional[int] = None):
    """Return (state, target): safe, repairable, or ambiguous.

    A pure XY travel before the layer-Z move is already safe. A target is only
    repairable if an absolute Z descent precedes a pure XY travel with no
    intervening extrusion or state-changing motion.
    """
    absolute = start_absolute
    descent_seen = False
    extrusion_seen = False
    paired_tool_seen = False
    bytes_seen = 0
    for _ in range(max_lines):
        line = stream.readline()
        if not line:
            return "ambiguous", None
        bytes_seen += len(line.encode("latin-1"))
        if bytes_seen > max_bytes:
            return "ambiguous", None
        code = _code(line)
        if not code:
            continue
        command = _command(line)
        if _is_toolchange(line):
            if (expected_tool is not None and not paired_tool_seen
                    and re.fullmatch(r"T\d+", command)
                    and int(command[1:]) == expected_tool):
                paired_tool_seen = True
                continue
            return "ambiguous", None
        if command == "G90":
            absolute = True
            continue
        if command == "G91":
            absolute = False
            continue
        if command in {"G20", "G92"}:
            return "ambiguous", None
        if command in {"G21", "G4"}:
            continue
        motion = _MOTION_RE.match(code)
        if motion:
            words = _motion_words(code)
            if "Z" in words:
                if (not absolute or any(axis in words for axis in ("X", "Y", "E"))
                        or not set(words).issubset({"G", "F", "Z"})):
                    return "ambiguous", None
                try:
                    z = float(words["Z"])
                except ValueError:
                    return "ambiguous", None
                if z <= layer_z + 1e-4:
                    descent_seen = True
                continue
            if "E" in words:
                extrusion_seen = True
                continue
            if "X" in words or "Y" in words:
                if (not absolute or "X" not in words or "Y" not in words
                        or not set(words).issubset({"G", "F", "X", "Y"})):
                    return "ambiguous", None
                try:
                    xy = (float(words["X"]), float(words["Y"]))
                except ValueError:
                    return "ambiguous", None
                if not descent_seen:
                    return "safe", None
                return ("repairable", xy) if not extrusion_seen else ("ambiguous", None)
            continue
        if command.startswith("G"):
            return "ambiguous", None
    return "ambiguous", None


def _scan(path: Path, limits: Optional[Limits], max_lines: int,
          max_bytes: int) -> Tuple[Dict[int, str], bool]:
    replacements: Dict[int, str] = {}
    unresolved = False
    absolute = True
    with path.open("r", encoding="latin-1", newline="") as stream:
        line_number = 0
        while True:
            line = stream.readline()
            if not line:
                break
            line_number += 1
            command = _command(line)
            if command == "G90":
                absolute = True
                continue
            if command == "G91":
                absolute = False
                continue
            if not _is_toolchange(line):
                continue
            words = _words(line)
            if limits is None or not _out_of_bounds_destination(line, limits):
                continue
            expected_tool = None
            if command == "_SLICER_CHANGE":
                try:
                    expected_tool = int(words["NEXT_EXTRUDER"])
                except (KeyError, ValueError):
                    pass
            try:
                layer_z = float(words["Z"])
            except (KeyError, ValueError):
                unresolved = True
                continue
            if not absolute:
                unresolved = True
                continue
            lookahead_offset = stream.tell()
            state, candidate = _next_xy_if_recoverable(
                stream, absolute, layer_z, max_lines, max_bytes, expected_tool
            )
            stream.seek(lookahead_offset)
            if state == "safe":
                continue
            if state != "repairable" or candidate is None or not limits.contains(*candidate):
                unresolved = True
                continue
            replacements[line_number] = _replace_xy(line, *candidate)
    return replacements, unresolved


def process_file(path: os.PathLike[str] | str, limits: Optional[Limits],
                 max_lines: int = 96, max_bytes: int = 16384) -> Tuple[int, int]:
    """Atomically apply only proven repairs; return (changed, unresolved)."""
    target = Path(path).resolve()
    replacements, unresolved = _scan(target, limits, max_lines, max_bytes)
    if not replacements:
        return 0, int(unresolved)
    stat = target.stat()
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="latin-1", newline="") as output, target.open(
            "r", encoding="latin-1", newline=""
        ) as source:
            for number, line in enumerate(source, 1):
                output.write(replacements.get(number, line))
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temp_name, stat.st_mode)
        os.replace(temp_name, target)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return len(replacements), int(unresolved)


def _component_config(config) -> None:
    server = config.get_server()
    file_manager = server.load_component(config, "file_manager")
    metadata_store = getattr(file_manager, "gcode_metadata", None)
    register_processor = getattr(metadata_store, "register_gcode_processor", None)
    if not callable(register_processor):
        raise config.error(
            "Moonraker file manager lacks "
            "gcode_metadata.register_gcode_processor; "
            "this component requires the G-code metadata processor API"
        )
    enabled = config.getboolean("enabled", False)
    limits = {name: config.getfloat(name, None) for name in
              ("x_min", "x_max", "y_min", "y_max")}
    if enabled and any(value is None for value in limits.values()):
        raise config.error(
            "enabled processing requires x_min, x_max, y_min, and y_max"
        )
    if enabled and not all(math.isfinite(value) for value in limits.values()):
        raise config.error("axis bounds must be finite numbers")
    if enabled and (limits["x_min"] >= limits["x_max"] or
                    limits["y_min"] >= limits["y_max"]):
        raise config.error("axis minimums must be less than their maximums")
    cli_args = [sys.executable, str(Path(__file__).resolve()), "--process",
                "{gcode_file_path}"]
    if all(value is not None for value in limits.values()):
        for name, value in limits.items():
            cli_args.extend((f"--{name.replace('_', '-')}", str(value)))
    command = " ".join(shlex.quote(arg) for arg in cli_args)
    register_processor("toolchanger_destination", {
        "name": "toolchanger_destination",
        "version": VERSION,
        "command": command,
        "timeout": config.getfloat("timeout", 120., above=0.),
        "enabled": enabled,
    })


class ToolchangerGcodeProcessor:
    def __init__(self, config):
        _component_config(config)

    def component_init(self):
        pass

    def close(self):
        pass


def load_component(config):
    # Moonraker invokes this during component loading, before config validation.
    # Parsing options here marks them consumed even if component_init runs later.
    return ToolchangerGcodeProcessor(config)


def _main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--process", action="store_true")
    parser.add_argument("file")
    for axis in ("x", "y"):
        parser.add_argument(f"--{axis}-min", type=float)
        parser.add_argument(f"--{axis}-max", type=float)
    args = parser.parse_args(argv)
    values = (args.x_min, args.x_max, args.y_min, args.y_max)
    limits = Limits(*values) if all(value is not None for value in values) else None
    try:
        changed, unresolved = process_file(args.file, limits)
    except Exception as exc:
        print(f"Toolchanger G-code processor error; file left unchanged: {exc}", file=sys.stderr)
        return 1
    if unresolved:
        # Moonraker v0.11 logs processor failure but continues metadata/upload
        # processing. This is intentionally diagnostic, not a print gate.
        print("Toolchanger G-code processor: unresolved transition(s) left unchanged; "
              "runtime bounds guard remains responsible for optional XY destinations.",
              file=sys.stderr)
        return 1
    if changed:
        print(f"Toolchanger G-code processor repaired {changed} transition(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
