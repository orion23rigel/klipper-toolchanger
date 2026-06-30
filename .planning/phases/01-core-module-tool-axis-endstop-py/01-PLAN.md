---
phase: "01"
wave: 1
depends_on: []
files_modified:
  - klipper/extras/tool_axis_endstop.py
autonomous: true
---

# Phase 01: Core Module — `tool_axis_endstop.py`

## Overview

Verify and validate the `ToolAxisEndstop` virtual chip class and both config loaders in `klipper/extras/tool_axis_endstop.py`.

## must_haves

- `ToolAxisEndstop` class implements full `MCU_endstop` proxy interface (`home_start`, `home_wait`, `query_endstop`, `add_stepper`, `get_steppers`, `setup_pin`)
- `load_config()` handles unnamed `[tool_axis_endstop]` section with optional `x_default_pin`/`y_default_pin`
- `load_config_prefix()` handles per-tool `[tool_axis_endstop Tn]` sections with `x_pin`/`y_pin`
- Virtual chips (`toolchanger_x`, `toolchanger_y`) registered with pins system and printer object system
- `allow_multi_use_pin` prevents conflicts when probe and endstop share the same physical pin
- `python3 -m compileall` passes on the new module
- `has_endstop(tool_number)` public method available for validation

## Requirements

- XEND-01, XEND-02, XEND-03, XEND-04, XEND-05
- YEND-01, YEND-02
- COMPAT-01, COMPAT-03

## Plans

### Plan 1: Verify `tool_axis_endstop.py` Implementation

**<action>Verify the existing `klipper/extras/tool_axis_endstop.py` file matches all requirements.</action>

**<verify>**
- `ToolAxisEndstop.__init__` registers virtual chip via `ppins.register_chip(self.chip_name, self)`
- `setup_pin` returns `self` for endstop pin type
- `add_endstop` registers MCU_endstop and forwards existing steppers
- `set_default_endstop` sets fallback endstop
- `set_active_tool` routes to active tool's endstop with fallback
- `add_stepper` forwards to all registered endstops (CoreXY cross-wiring)
- `has_endstop` returns tool_number in `_endstops` dict
- `home_start`, `home_wait`, `query_endstop` proxy to `active_mcu_endstop`
- `load_config` creates default endstops from unnamed section
- `load_config_prefix` creates per-tool endstops from Tn sections
- `python3 -m compileall` passes
</verify>

**<acceptance_criteria>**
1. All MCU_endstop proxy methods present and correct
2. Both config loaders functional
3. Virtual chips registered correctly
4. Compilation passes

**<read_first>**
- klipper/extras/tool_axis_endstop.py
- klipper/extras/tool_probe_endstop.py (pattern reference)
- .planning/ROADMAP.md (Phase 1 success criteria)
- .planning/REQUIREMENTS.md (XEND-01 through XEND-05, YEND-01, YEND-02, COMPAT-01, COMPAT-03)

**<task_id>** 01-verify
**<task>** Verify `tool_axis_endstop.py` implementation matches all requirements.
