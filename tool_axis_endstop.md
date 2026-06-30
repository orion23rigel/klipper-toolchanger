# Tool Axis Endstop

Per-tool X and Y axis endstop routing for toolchangers. Enables any toolhead to home X (and Y) independently, regardless of which tool is mounted on the gantry.

## Overview

When a tool is selected, Klipper uses that tool's physical endstop pin for homing. The extension registers virtual pin chips (`toolchanger_x` and `toolchanger_y`) that proxy the `MCU_endstop` interface and route homing queries to the active toolhead's physical endstop.

This is the same pattern already used for per-tool Z probing via `tool_probe_endstop.py`.

## How It Works

1. Each tool defines its X (and optionally Y) endstop pin in a `[tool_axis_endstop Tn]` config section.
2. Virtual chips `toolchanger_x` and `toolchanger_y` are registered with Klipper's pins system.
3. `[stepper_x] endstop_pin` is set to `toolchanger_x:x_virtual_endstop` (and similarly for Y).
4. On tool change, the router switches to the selected tool's physical endstop.
5. CoreXY cross-wiring is handled automatically — each MCU monitors the correct steppers during homing.

## Configuration

### printer.cfg

Change the stepper X endstop pin to use the virtual chip:

```
[stepper_x]
endstop_pin: toolchanger_x:x_virtual_endstop

[stepper_y]
endstop_pin: toolchanger_y:y_virtual_endstop
```

### Per-tool endstop definitions

Add a `[tool_axis_endstop Tn]` section for each tool (order relative to `[tool Tn]` does not matter):

```
[tool_axis_endstop T0]
x_pin: tool_0:PB8
# y_pin: tool_0:PB8
```

```
[tool_axis_endstop T1]
x_pin: tool_1:PB8
# y_pin: tool_1:PB8
```

### Optional global defaults

An unnamed `[tool_axis_endstop]` section provides fallback pins for when no tool-specific pin is defined:

```
[tool_axis_endstop]
x_default_pin: ^mainboard:PB8
y_default_pin: ^mainboard:PB9
```

### Shared pin support

If the probe pin and endstop pin share the same physical pin (e.g., PB8 on EBB36 toolhead MCUs), Klipper's built-in `allow_multi_use_pin` mechanism handles this automatically — no additional configuration needed.

## Migration

The minimal migration requires 3 config changes:

1. Change `[stepper_x] endstop_pin` from a direct pin to `toolchanger_x:x_virtual_endstop`
2. Add `[tool_axis_endstop Tn]` sections for each tool with `x_pin` (and optionally `y_pin`)
3. (Optional) Add an unnamed `[tool_axis_endstop]` section for global defaults

## Backward Compatibility

If no `[tool_axis_endstop]` sections are defined, the virtual chip is never created and the printer behaves exactly as before — no changes to existing functionality.

Existing `[tool_probe Tn]` / `[tool_probe_endstop]` for Z probing continues to work unchanged.

## Validation

At `klippy:connect`, the extension validates that every registered tool has its X and Y endstop pins defined. If any tool is missing its `[tool_axis_endstop Tn]` section, startup is blocked with a clear error listing which tools are missing.

## Commands

No new gcode commands are required. Endstop routing happens automatically during tool changes via `_configure_toolhead_for_tool()`.
