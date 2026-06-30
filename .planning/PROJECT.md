# Per-Tool X/Y Endstop Routing for Klipper Toolchangers

## What This Is

A Klipper firmware extension that enables per-tool X and Y axis endstop routing for multi-tool (toolchanger) 3D printers. When a tool is selected, Klipper uses that tool's physical endstop pin for homing — allowing any toolhead to home X correctly regardless of which tool is mounted on the gantry.

## Core Value

**Any tool can home X (and Y) independently** — the firmware dynamically routes endstop queries to the selected toolhead's physical endstop pin, so tool changes don't require re-homing or hardcoded pin references.

## Business Context

- **Customer**: 3D printer users with multi-tool toolchanger setups (Voron Trident, Voron 2.4, similar CoreXY designs)
- **Problem**: Current klipper-toolchanger plugin supports per-tool Z probing but X/Y endstops are hardcoded to a single tool — homing X only works when that tool is mounted
- **Success metric**: Homing X works correctly with any mounted tool, no manual intervention needed

## Requirements

### Validated

- ✓ Per-tool Z probe routing — `tool_probe_endstop.py` routes Z probe queries to the active tool's probe via `EndstopRouter`/`ProbeRouter`
- ✓ Tool change lifecycle — `toolchanger._configure_toolhead_for_tool()` switches active probe, extruder, fan on tool change
- ✓ Tool offset transform — `ToolGcodeTransform` applies per-tool `gcode_x/y/z_offset` transparently
- ✓ Tool detection — per-tool detection pins registered via Klipper's `buttons` subsystem
- ✓ Crash detection — `ToolProbeEndstop` monitors active probe for unexpected triggers during printing

### Validated

- ✓ **REQ-01**: Per-tool X endstop routing — v1.0
- ✓ **REQ-02**: Per-tool Y endstop routing — v1.0
- ✓ **REQ-03**: Config validation at `klippy:connect` — v1.0
- ✓ **REQ-04**: CoreXY cross-wiring compatibility — v1.0
- ✓ **REQ-05**: Shared pin support — v1.0

### Active

- [ ] Per-tool position_endstop overrides — architecture supports it, not implementing now
- [ ] Sensorless endstop routing — DIAG pins on mainboard, stays global

### Out of Scope

- [ ] Per-tool position_endstop overrides — architecture supports it, not implementing now
- [ ] Sensorless endstop routing — DIAG pins on mainboard, stays global
- [ ] Multi-toolhead IDEX support — different architecture; single-gantry toolchangers only

## Context

### Technical Environment

- Klipper firmware (Python 3.14+)
- Toolchanger plugin: `klipper-toolchanger` (GPLv3) at `/home/orion/coding/tool-probe-bed-calibration-position`
- Hardware: Voron Trident 250/300/350mm with MadMax toolchanger
- Mainboard: BTT Octopus Pro (STM32F446, CAN bus)
- Toolhead MCUs: BTT EBB36 CAN (STM32G0B1), one per tool
- CoreXY kinematics
- Each toolhead has its own CAN-connected MCU with X endstop switch and Z probe switch on the same pin (PB8)

### Existing Architecture (from `.planning/codebase/`)

- **Tool Management**: `toolchanger.py` (874 lines) — state machine, tool lifecycle, `ToolGcodeTransform`
- **Per-Tool Config**: `tool.py` (214 lines) — per-tool settings, probe registration, detection
- **Per-Tool Probe**: `tool_probe.py` (36 lines) + `tool_probe_endstop.py` (256 lines) — virtual probe routing
- **Calibration**: `tools_calibrate.py` (474 lines) — offset measurement
- **Motion**: `rounded_path.py` (258 lines), `manual_rail.py` (243 lines)

### Known Issues

- No automated test suite (documented in `.planning/codebase/TESTING.md`)
- Klipper API compatibility is fragile — changes to core Klipper can break extensions
- `STATUS_UNINITALIZED` typo (documented in CONCERNS.md)

## Constraints

- **No Klipper core changes** — must use existing virtual endstop pattern (`setup_pin` returning `self`)
- **Backward compatible** — if no `[tool_axis_endstop]` sections exist, behavior is unchanged
- **Minimal config delta** — user changes: 1 line in `printer.cfg`, 1 section per tool
- **CAN bus dependency** — toolhead MCUs must be reachable on CAN bus even when docked

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Virtual pin chip over rail swapping | Core Klipper binds endstops at config time; virtual chip is the only way to swap dynamically without core changes | `toolchanger_x` chip registered with pins system |
| Per-tool config sections over global defaults | Each tool's pin is tool-specific; per-tool sections are explicit and self-documenting | `[tool_axis_endstop Tn]` with `x_pin`, `y_pin` |
| Validation at `klippy:connect` | All config parsed by then; catches missing tool definitions before runtime | Blocks startup with clear error |
| `allow_multi_use_pin` for shared pins | Probe and X endstop share PB8 on each tool; Klipper's built-in mechanism handles this | No pin conflict |
| Y endstop included alongside X | Same pattern, future-proof for setups with per-tool Y endstops | `toolchanger_y` chip, same code path |
| `home_start`/`home_wait`/`query_endstop` proxy chain | Routes to active tool's physical MCU_endstop | Matches `ToolProbeEndstop` pattern for Z probes |
| CoreXY cross-wiring via `add_stepper()` | Each MCU monitors all relevant steppers during homing | Handles both ordering scenarios |

---
*Last updated: Tue Jun 30 2026 after v1.0 milestone*
