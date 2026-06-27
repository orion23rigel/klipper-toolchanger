# Stack: klipper-toolchanger

**Date:** 2026-06-27

## Language & Runtime

- **Language:** Python 3 (Klipper plugin ecosystem)
- **Runtime:** Klipper firmware (runs on Raspberry Pi / Linux SBC alongside Marlin-compatible G-code)
- **Python version:** 3.14+ (detected from `cpython-314.pyc` cache files)

## Dependencies

This project has **no external Python package dependencies**. It is a Klipper extension that relies on the Klipper core library APIs:

| Dependency | Purpose |
|------------|---------|
| `klipper` (core) | Main Klipper firmware — provides `config`, `gcode`, `gcode_move`, `toolhead`, `homing`, `probe`, `stepper`, `pins`, `motion_queuing`, `force_move`, `printer`, `reactor`, `buttons`, `heaters`, `fan`, `gcode_macro`, `heated_bed` |
| `numpy` | Used by `rounded_path.py` for Bezier curve computation (`np.linspace`, `np.array`, `np.transpose`) |

## Configuration

- Klipper `[include]` directives pull in the extension files
- Config sections: `[toolchanger]`, `[tool <name>]`, `[tool_probe <name>]`, `[tool_probe_endstop]`, `[tools_calibrate]`, `[rounded_path]`, `[manual_rail]`, `[multi_fan]`, `[bed_thermal_adjust]`
- Installation via `install.sh` script that symlinks files into Klipper's `extra_folder`
- Update manager integration via `moonraker.conf`

## External Integrations

| Integration | Description |
|-------------|-------------|
| Klipper core API | Deep integration with Klipper's reactor, toolhead, homing, probe, and gcode subsystems |
| Moonraker update manager | Automatic updates via `[update_manager klipper-toolchanger]` |
| Slicer G-code (Prusa/Orca) | Expects slicer-generated `T<n>`, `M104 T<n>`, `M109 T<n>`, `M106` commands |
| Klipper `probe` subsystem | Replaces the standard `[probe]` section with per-tool probe routing |
| Klipper `buttons` subsystem | Tool detection pins registered as buttons for debounced detection |
| Klipper `heaters` subsystem | Temperature management with per-tool heater/extruder assignment |
