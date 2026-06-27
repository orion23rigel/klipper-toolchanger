# Architecture: klipper-toolchanger

**Date:** 2026-06-27

## Overview

This is a Klipper firmware extension that adds multi-tool (toolchanger) support to 3D printers. It provides a framework for managing multiple tools (extruders/hotends), each with its own geometry offsets, probe, fans, and temperature control.

## Architectural Pattern

**Plugin/Extension architecture** — the code registers as Klipper configuration sections and hooks into Klipper's reactor event loop, gcode command dispatch, and toolhead motion pipeline.

## Component Layers

### 1. Tool Management Layer (`toolchanger.py`, `tool.py`)

The core tool management system:

```
Toolchanger (singleton, per instance)
  ├── tools[] — dict of Tool objects by number
  ├── active_tool — currently selected Tool
  ├── detected_tool — tool detected by sensor
  ├── tool_numbers — sorted list of registered tool numbers
  ├── tool_names — matching names
  ├── gcode_transform — ToolGcodeTransform applying per-tool offsets
  ├── fan_switcher — FanSwitcher for part cooling
  └── tool_probe_endstop — shared per-tool probe router
```

**Tool class** encapsulates per-tool configuration:
- `extruder`, `heater`, `extruder_stepper` — hardware assignment
- `fan` — per-tool cooling fan
- `probe` — per-tool Z probe reference
- `detection_pin` — tool presence detection
- `gcode_x/y/z_offset` — nozzle geometry offsets
- `pickup_gcode` / `dropoff_gcode` — tool change motion macros
- `before_change_gcode` / `after_change_gcode` — lifecycle hooks

### 2. State Machine

Toolchanger operates as a finite state machine:

```
uninitialized → initializing → ready → changing → ready/error
                                                    ↓
                                              uninitialized (on error)
```

**States:**
- `STATUS_UNINITALIZED` — startup, after error, after shutdown
- `STATUS_INITIALIZING` — running initialize_gcode
- `STATUS_READY` — normal operation, tool changes allowed
- `STATUS_CHANGING` — mid-tool-change or docking mode
- `STATUS_ERROR` — tool change failed, error_gcode executed

### 3. Per-Tool Probe Layer (`tool_probe.py`, `tool_probe_endstop.py`)

Replaces Klipper's standard `[probe]` section with per-tool probe routing:

```
ToolProbeEndstop (singleton)
  ├── probes[] — all registered ToolProbe objects
  ├── tool_number_to_probe — mapping
  ├── active_probe — currently active probe
  ├── mcu_probe (EndstopRouter) — routes endstop queries
  ├── probe (ProbeRouter) — routes offset/param queries
  └── probe_session (SampleAveragingHelper) — sampling wrapper
```

**Key mechanism:** `EndstopRouter` and `ProbeRouter` dynamically route Klipper's probe queries to whichever tool's probe is currently active. This allows each tool to have its own Z probe for homing.

**Crash detection:** Monitors active tool probe for unexpected triggers during printing, runs `crash_gcode` on detection.

### 4. Calibration Layer (`tools_calibrate.py`)

Provides calibration commands for tool offset and probe offset measurement:

- `TOOL_LOCATE_SENSOR` — find calibration sensor position
- `TOOL_CALIBRATE_TOOL_OFFSET` — measure XYZ offset relative to tool 0
- `TOOL_CALIBRATE_SAVE_TOOL_OFFSET` — persist offsets to config
- `TOOL_CALIBRATE_PROBE_OFFSET` — calibrate tool probe Z offset vs nozzle

Uses `PrinterProbeMultiAxis` (adapted from Klipper's `probe_multi_axis.py`) for multi-axis probing.

### 5. Motion Optimization Layer (`rounded_path.py`)

Bezier curve rounding for fast non-print travel moves:

```
RoundedPath
  ├── buffer[ControlPoint] — pending move segments
  ├── G0_params — cached G0 command template
  └── real_G0 → gcode_move.cmd_G1
```

Buffers G0 moves and rounds corners using cubic Bezier curves, reducing speed changes at corners. Supports configurable rounding distance `D` per segment.

### 6. Infrastructure Extras

| Module | Purpose |
|--------|---------|
| `manual_rail.py` | Manually controlled stepper rail with homing (for liftbar mechanisms) |
| `multi_fan.py` | Switchable part cooling fan system |
| `bed_thermal_adjust.py` | Heated bed temperature adjustment for thermal loss compensation |

## Data Flow

### Tool Change (`SELECT_TOOL`)

```
SELECT_TOOL T<n> or TOOL=<name>
  → ensure_homed()
  → save G-code state (_toolchange_state)
  → zero G-code offsets (toolchange transform)
  → run before_change_gcode
  → run dropoff_gcode (current tool)
  → configure toolhead for new tool
  → run pickup_gcode (new tool)
  → verify tool detection
  → run after_change_gcode
  → restore G-code state + position
  → apply tool gcode offsets via ToolGcodeTransform
```

### Temperature Management

```
M104 T<n> S<temp> → macros.cfg → SET_TOOL_TEMPERATURE T=<n> TARGET=<temp>
  → toolchanger._get_tool_from_gcmd() → heater lookup → heaters.set_temperature()

M109 T<n> S<temp> → macros.cfg → SET_TOOL_TEMPERATURE T=<n> TARGET=<temp> WAIT=1
  → respects temperature_wait_threshold to skip redundant M109 waits
```

## Entry Points

- `klipper/extras/toolchanger.py:load_config()` — main toolchanger registration
- `klipper/extras/toolchanger.py:load_config_prefix()` — per-tool `[tool <name>]` registration
- `klipper/extras/tool_probe.py:load_config_prefix()` — per-tool probe registration
- `klipper/extras/tools_calibrate.py:load_config()` — calibration module
- `klipper/extras/tool_probe_endstop.py:load_config()` — probe endstop router
- `klipper/extras/rounded_path.py:load_config()` — rounded path optimizer
- `klipper/extras/manual_rail.py:load_config_prefix()` — manual rail
- `klipper/extras/multi_fan.py:load_config_prefix()` — multi-fan
- `klipper/extras/bed_thermal_adjust.py:load_config()` — bed thermal adjust
