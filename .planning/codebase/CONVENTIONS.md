# Conventions: klipper-toolchanger

**Date:** 2026-06-27

## Code Style

- **Indentation:** 4 spaces (standard Python)
- **Line length:** ~120 characters max (some lines exceed, no formatter applied)
- **String style:** Single quotes for strings, f-strings for interpolation
- **Docstrings:** Module-level license header (GNU GPLv3), minimal inline docstrings
- **Type hints:** None used — pure dynamic Python (Klipper convention)

## Class Patterns

### Klipper Extension Module Pattern

Every module follows this structure:

```python
class ClassName:
    def __init__(self, config):
        self.printer = config.get_printer()
        # ... initialization ...
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command("COMMAND_NAME", self.cmd_COMMAND_NAME,
                                    desc=self.cmd_COMMAND_NAME_help)

    cmd_COMMAND_NAME_help = "Description"
    def cmd_COMMAND_NAME(self, gcmd):
        # ... implementation ...

def load_config(config):
    return ClassName(config)

def load_config_prefix(config):
    return ClassName(config)  # For prefix sections like [tool name]
```

### Command Method Convention

- Method name: `cmd_<GCODE_COMMAND>` (e.g., `cmd_SELECT_TOOL`)
- Help text: `cmd_<GCODE_COMMAND>_help` attribute (string)
- Parameters: extracted via `gcmd.get()`, `gcmd.get_int()`, `gcmd.get_float()`, `gcmd.getchoice()`
- Errors: raised via `gcmd.error("message")` or `self.printer.command_error("message")`

### Config Parameter Convention

```python
# Required parameter
self.name = config.get_name()
pin = config.get('pin')  # May be None

# Optional with default
self.speed = config.getfloat('speed', 5.0, above=0.)
self.enabled = config.getboolean('feature', False)
self.choice = config.getchoice('mode', {'opt1': 1, 'opt2': 2}, 'opt1')

# Prefix options (params_*)
self.params = config.get_prefix_options('params_')
```

## Error Handling

- **G-code errors:** `gcmd.error("message")` raises an exception that Klipper catches
- **Config errors:** `config.error("message")` or `self.printer.config_error("message")`
- **Command errors:** `self.printer.command_error("message")` returns error string
- **Logging:** `logging.warning()` and `logging.error()` for non-fatal issues
- **State recovery:** Error state (`STATUS_ERROR`) triggers `error_gcode` if configured

## State Management

### Toolchanger State Machine

States are module-level constants:
```python
STATUS_UNINITALIZED = 'uninitialized'
STATUS_INITIALIZING = 'initializing'
STATUS_READY = 'ready'
STATUS_CHANGING = 'changing'
STATUS_ERROR = 'error'
```

State transitions are explicit in methods, with validation at entry points:
```python
if self.status != STATUS_READY:
    raise gcmd.error("Cannot select tool, toolchanger status is %s" % self.status)
```

### G-code State Save/Restore

```python
self.gcode.run_script_from_command("SAVE_GCODE_STATE NAME=_toolchange_state")
# ... toolchange operations ...
self.gcode.run_script_from_command("RESTORE_GCODE_STATE NAME=_toolchange_state MOVE=0")
```

## Inheritance and Extension

- Modules extend Klipper's base classes: `probe.ProbeEndstopWrapper`, `probe.ProbeOffsetsHelper`, `stepper.LookupMultiRail`
- ToolProbeEndstop replaces the standard `[probe]` section by registering itself as `probe` object
- BedThermalAdjust intercepts and replaces `M140`/`M190` commands

## Design Patterns

- **Router pattern:** `EndstopRouter` and `ProbeRouter` dynamically dispatch to active tool probe
- **Observer pattern:** Event handlers registered via `printer.register_event_handler()`
- **Template pattern:** G-code templates loaded via `gcode_macro.load_template()` for user-customizable behavior
- **Strategy pattern:** `on_axis_not_homed` option selects abort vs home behavior
- **Factory pattern:** `load_config()` / `load_config_prefix()` are Klipper's object factory hooks
