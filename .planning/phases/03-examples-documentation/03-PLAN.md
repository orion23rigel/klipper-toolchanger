---
phase: "03"
wave: 1
depends_on:
  - "01", "02"
files_modified:
  - examples/axis_endstop/printer.cfg
  - examples/axis_endstop/toolhead_n.cfg
  - examples/axis_endstop/homing.cfg
autonomous: true
---

# Phase 03: Examples + Documentation

## Overview

Verify example configs in `examples/axis_endstop/` demonstrate the full setup for both X-only and X+Y configurations.

## must_haves

- Example configs in `examples/axis_endstop/` demonstrate the full setup
- Examples show both X-only and X+Y configurations
- Migration guide documents the 3 config changes needed
- Documentation explains the architecture

## Requirements

- COMPAT-02 (implicit via examples)

## Plans

### Plan 1: Verify Example Configs

**<action>Verify the example configs exist and demonstrate the full setup correctly.</action>

**<verify>**
- `examples/axis_endstop/printer.cfg` shows `toolchanger_x:x_virtual_endstop`
- `examples/axis_endstop/toolhead_n.cfg` shows `[tool_axis_endstop Tn]` with `x_pin`, `y_pin`
- `examples/axis_endstop/homing.cfg` shows homing with per-tool X endstops
- Examples demonstrate both X-only and X+Y configurations

**<acceptance_criteria>**
1. printer.cfg shows correct endstop_pin reference
2. toolhead_n.cfg shows per-tool config sections
3. homing.cfg shows homing configuration
4. Examples are self-contained and illustrative

**<read_first>**
- examples/axis_endstop/printer.cfg
- examples/axis_endstop/toolhead_n.cfg
- examples/axis_endstop/homing.cfg
- .planning/ROADMAP.md (Phase 3 success criteria)

**<task_id>** 03-verify
**<task>** Verify example configs demonstrate the full setup.
