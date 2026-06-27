# Structure: klipper-toolchanger

**Date:** 2026-06-27

## Directory Layout

```
.
├── klipper/extras/                    # Klipper extension modules
│   ├── __init__.py                   # (not present — Klipper discovers via load_config)
│   ├── toolchanger.py                # Core tool management (874 lines)
│   ├── tool.py                       # Per-tool configuration and activation (214 lines)
│   ├── tool_probe.py                 # Per-tool Z probe (36 lines)
│   ├── tool_probe_endstop.py         # Probe routing for per-tool homing (256 lines)
│   ├── tools_calibrate.py            # Tool offset calibration (474 lines)
│   ├── rounded_path.py               # Bezier travel path rounding (258 lines)
│   ├── manual_rail.py                # Manual stepper rail (243 lines)
│   ├── multi_fan.py                  # Switchable part cooling fans (70 lines)
│   └── bed_thermal_adjust.py         # Bed thermal loss compensation (108 lines)
├── examples/                          # Configuration examples
│   ├── README.md                     # Setup guide and slicer macros
│   ├── printer.cfg                   # Main printer config include
│   ├── T0.cfg                        # Tool 0 configuration
│   ├── calibrate-offsets.cfg         # Calibration configuration
│   ├── camera-tool-align.cfg         # Camera alignment macro
│   ├── single-toolhead-multi-extruder.cfg
│   ├── tool_paths.md                 # Travel path examples
│   ├── toolchanger-macros.cfg        # Tool change macros
│   ├── dock location/               # Dock configuration variants
│   └── z probe/                     # Z probe configuration variants
├── usermods/                          # (empty or user-specific mods)
├── macros.cfg                         # M104/M109 tool temperature macros
├── install.sh                         # Installation script
├── toolchanger.md                     # Full documentation
├── tool_probe.md                      # Tool probe documentation
├── tools_calibrate.md                 # Calibration documentation
├── rounded_path.md                    # Rounded path documentation
├── manual_rail.md                     # Manual rail documentation
├── tool_probe.md                      # Tool probe documentation
├── README.md                          # Project overview
├── Lifecycle.png                      # Toolchanger lifecycle diagram
├── Sequence.png                       # Tool change sequence diagram
├── LICENSE
└── .git/                              # Git repository
```

## Key Locations

### Source Files

| File | Lines | Role |
|------|-------|------|
| `klipper/extras/toolchanger.py` | 874 | Core — Toolchanger class, state machine, tool selection, error handling |
| `klipper/extras/tools_calibrate.py` | 474 | Calibration — TOOL_CALIBRATE_* commands, PrinterProbeMultiAxis |
| `klipper/extras/tool_probe_endstop.py` | 256 | Probe routing — EndstopRouter, ProbeRouter, crash detection |
| `klipper/extras/rounded_path.py` | 258 | Motion — RoundedPath, Bezier corner rounding |
| `klipper/extras/manual_rail.py` | 243 | Infrastructure — ManualRail for liftbar mechanisms |
| `klipper/extras/tool.py` | 214 | Per-tool — Tool class, activation/deactivation, T<n> registration |
| `klipper/extras/tool_probe.py` | 36 | Per-tool probe — ToolProbe wrapper |
| `klipper/extras/multi_fan.py` | 70 | Fan switching — MultiFan, MultiFanController |
| `klipper/extras/bed_thermal_adjust.py` | 108 | Bed thermal — BedThermalAdjust |

### Documentation

- `toolchanger.md` — Comprehensive toolchanger documentation (config, G-codes, status reference)
- `tool_probe.md` — Tool probe documentation
- `tools_calibrate.md` — Calibration documentation
- `rounded_path.md` — Rounded path documentation
- `README.md` — Project overview and changelog

### Configuration Examples

- `examples/printer.cfg` — Main config with `[include]` directives
- `examples/T0.cfg` — Example tool 0 configuration
- `examples/toolchanger-macros.cfg` — Tool change macros
- `examples/calibrate-offsets.cfg` — Calibration config
- `examples/dock location/` — Dock configurations by mechanism type
- `examples/z probe/` — Z probe configurations by type

## Naming Conventions

- **Module names:** snake_case, descriptive (`tool_probe_endstop`, `bed_thermal_adjust`)
- **Class names:** PascalCase (`Toolchanger`, `Tool`, `ToolProbeEndstop`, `PrinterProbeMultiAxis`)
- **G-code commands:** UPPER_SNAKE_CASE (`INITIALIZE_TOOLCHANGER`, `SELECT_TOOL`)
- **Config sections:** snake_case with hyphens (`[toolchanger]`, `[tool_probe_endstop]`)
- **Help attributes:** `cmd_<COMMAND>_help` pattern on command methods
- **Status constants:** UPPER_SNAKE_CASE (`STATUS_READY`, `DETECT_PRESENT`)
- **Internal methods:** `_` prefix (`_configure_toolhead_for_tool`, `_save_state`)
