# Integrations: klipper-toolchanger

**Date:** 2026-06-27

## Klipper Core Integrations

### G-code Command Registration
All modules register commands via `self.gcode.register_command()`:

| Module | Commands |
|--------|----------|
| `toolchanger.py` | `INITIALIZE_TOOLCHANGER`, `SELECT_TOOL`, `SELECT_TOOL_ERROR`, `UNSELECT_TOOL`, `SET_TOOL_TEMPERATURE`, `VERIFY_TOOL_DETECTED`, `ENTER_DOCKING_MODE`, `EXIT_DOCKING_MODE`, `TEST_TOOL_DOCKING`, `SET_TOOL_PARAMETER`, `RESET_TOOL_PARAMETER`, `SAVE_TOOL_PARAMETER`, `ADJUST_Z_AFTER_TOOL_NOZZLE_HOME` |
| `tool.py` | `ASSIGN_TOOL` (mux), `T<n>` (auto-generated for each tool_number), `M104 T<n>`, `M109 T<n>` (via `macros.cfg`) |
| `tool_probe.py` | Integrated via `tool_probe_endstop` |
| `tool_probe_endstop.py` | `SET_ACTIVE_TOOL_PROBE`, `DETECT_ACTIVE_TOOL_PROBE`, `START_TOOL_PROBE_CRASH_DETECTION`, `STOP_TOOL_PROBE_CRASH_DETECTION` |
| `tools_calibrate.py` | `TOOL_LOCATE_SENSOR`, `TOOL_CALIBRATE_TOOL_OFFSET`, `TOOL_CALIBRATE_SAVE_TOOL_OFFSET`, `TOOL_CALIBRATE_PROBE_OFFSET`, `TOOL_CALIBRATE_QUERY_PROBE` |
| `rounded_path.py` | `ROUNDED_G0` (optionally replaces `G0`) |
| `manual_rail.py` | `MANUAL_RAIL` (mux) |
| `multi_fan.py` | `ACTIVATE_FAN` (mux), `M106`, `M107` |
| `bed_thermal_adjust.py` | Replaces `M140`, `M190` |

### Klipper Event Handlers
Modules register event handlers via `printer.register_event_handler()`:

- `klippy:connect` — initialization of lookups, probe registration, chamber sensor setup
- `klippy:shutdown` — reset toolchanger state
- `klippy:ready` — start periodic timers (bed_thermal_adjust)
- `gcode:command_error` — reset toolchanger/rounded_path state
- `homing:home_rails_begin` — auto-initialize toolchanger on homing
- `gcode:command_error` — reset toolchanger state

### Klipper Object Lookups
All modules use `printer.lookup_object()` or `printer.load_object()` for:
- `toolhead` — motion control
- `gcode` — command registration and execution
- `gcode_move` — G-code state management (SAVE/RESTORE_GCODE_STATE)
- `probe` — probe subsystem (replaced by tool_probe_endstop)
- `heaters` — temperature management
- `homing` — homing moves
- `pins` — pin lookup and multi-use registration
- `motion_queuing` — trapq allocation
- `stepper_enable` — motor enable/disable

## External System Integrations

### Slicer Integration
- **Prusa/Orca Slicer:** Uses `T<n>`, `M104 T<n>`, `M109 T<n>`, `M106`, `M107` G-code commands
- **PRINT_START macro:** Accepts `EXTRUDER=`, `T0_TEMP=`, `T1_TEMP=`, `TOOL=`, `CHAMBER=` parameters
- **AFTER_LAYER_CHANGE:** `VERIFY_TOOL_DETECTED ASYNC=1`

### Moonraker
- Update manager integration for automatic updates
- Configured via `[update_manager klipper-toolchanger]`

### Hardware Integrations
- **Detection pins:** GPIO pins for tool presence detection (registered via `buttons` subsystem)
- **Tool probes:** Per-tool Z probes for homing and bed mesh (eddy current, mechanical, etc.)
- **Extruders/heaters:** Per-tool extruder and heater assignment
- **Fans:** Per-tool cooling fans via `fan_generic` (not `[fan]`)
- **Manual rail:** Optional stepper rail for liftbar mechanisms
