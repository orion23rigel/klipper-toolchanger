---
phase: "02"
wave: 1
depends_on:
  - "01"
files_modified:
  - klipper/extras/toolchanger.py
autonomous: true
---

# Phase 02: Toolchanger Integration + Validation

## Overview

Verify that the axis endstop routers are wired into the toolchanger lifecycle and config validation is in place.

## must_haves

- `_configure_toolhead_for_tool()` routes X and Y endstops on every tool change
- `_validate_axis_endstop_coverage()` runs at `klippy:connect` and blocks startup if tools are missing endstop definitions
- Existing Z probe routing (`tool_probe_endstop.set_active_probe()`) continues to work
- No regression in existing tool change behavior

## Requirements

- TOOL-01, TOOL-02
- VALID-01, VALID-02, VALID-03

## Plans

### Plan 1: Verify Toolchanger Integration

**<action>Verify the existing `klipper/extras/toolchanger.py` file has correct X/Y routing and validation integration.</action>

**<verify>**
- `_configure_toolhead_for_tool()` calls `router.set_active_tool(tn)` for both x and y axes
- `_validate_axis_endstop_coverage()` iterates axes, checks `router.has_endstop(tn)` for each tool
- Missing tools raise `printer.config_error` with clear message
- Validation only runs when router chip exists (lookup returns non-None)
- Z probe routing (`set_active_probe`) is untouched

**<acceptance_criteria>**
1. X/Y routing in `_configure_toolhead_for_tool()` routes to active tool
2. Validation in `_handle_connect()` checks all tools have endstop definitions
3. Existing Z probe routing unchanged
4. No regressions in tool change flow

**<read_first>**
- klipper/extras/toolchanger.py
- klipper/extras/tool_axis_endstop.py
- .planning/ROADMAP.md (Phase 2 success criteria)
- .planning/REQUIREMENTS.md (TOOL-01, TOOL-02, VALID-01, VALID-02, VALID-03)

**<task_id>** 02-verify
**<task>** Verify toolchanger.py integration matches all requirements.
