# Per-Tool X/Y Endstop Routing — Implementation Plan

## Context: What Already Exists

The **per-tool Z probe** is already implemented in `tool_probe_endstop.py` / `tool_probe.py`:
- `[tool_probe Tn]` sections define a probe pin per toolhead
- `ToolProbeEndstop` replaces Klipper's singleton `[probe]` and routes Z probe queries (`query_endstop`, `start_probe_session`, `get_offsets`) to the active tool via `EndstopRouter`/`ProbeRouter`
- `[stepper_z] endstop_pin: probe:z_virtual_endstop` delegates Z homing to this router
- Tool change in `toolchanger._configure_toolhead_for_tool()` already calls `set_active_probe()` to switch probes

The **missing piece** that this plan addresses: per-tool X (and Y) axis endstop routing.

## Goal

Enable Klipper to use the X (and optionally Y) endstop pin of the **selected toolhead** for homing, so any tool can home X correctly regardless of which tool is mounted.

## Approach

Virtual pin chip pattern — same as `tool_probe_endstop.py` uses for Z probes. Register `toolchanger_x` and `toolchanger_y` chips that proxy `home_start`/`home_wait`/`query_endstop`/`add_stepper` to the active tool's physical endstop.

## Files

### 1. CREATE: `klipper/extras/tool_axis_endstop.py`

Full implementation below. Two entry points:
- `load_config(config)` — unnamed `[tool_axis_endstop]` section (optional global defaults)
- `load_config_prefix(config)` — per-tool `[tool_axis_endstop Tn]` sections

### 2. MODIFY: `klipper/extras/toolchanger.py`

In `_configure_toolhead_for_tool()`, add X/Y endstop routing after Z probe routing. About 8 lines added.

### 3. CREATE: `examples/axis_endstop/toolhead_n.cfg`
### 4. CREATE: `examples/axis_endstop/homing.cfg`
### 5. CREATE: `examples/axis_endstop/printer.cfg`

---

## Implementation Details

### `tool_axis_endstop.py` — ToolAxisEndstop class

```python
class ToolAxisEndstop:
    def __init__(self, printer, axis_name):
        self.printer = printer
        self.axis_name = axis_name
        self.chip_name = 'toolchanger_%c' % (axis_name,)
        self.virtual_pin = '%c_virtual_endstop' % (axis_name,)
        self.active_mcu_endstop = None
        self.default_endstop = None
        self._endstops = {}       # tool_number -> MCU_endstop
        self._steppers = []

        ppins = printer.lookup_object('pins')
        ppins.register_chip(self.chip_name, self)
        printer.add_object(self.chip_name, self)

    def setup_pin(self, pin_type, pin_params):
        # Called by Klipper when stepper_x config references
        # toolchanger_x:x_virtual_endstop
        if pin_type != 'endstop' or pin_params['pin'] != self.virtual_pin:
            raise self.printer.config_error(
                "Tool %s virtual endstop requires pin '%s'"
                % (self.axis_name.upper(), self.virtual_pin))
        return self  # Acts as the endstop object

    def add_endstop(self, tool_number, mcu_endstop):
        # Register a tool's physical MCU_endstop
        self._endstops[tool_number] = mcu_endstop
        for s in self._steppers:
            mcu_endstop.add_stepper(s)

    def set_default_endstop(self, mcu_endstop):
        # Set the fallback endstop (from [tool_axis_endstop] default)
        self.default_endstop = mcu_endstop
        if self.active_mcu_endstop is None:
            self.active_mcu_endstop = mcu_endstop

    def set_active_tool(self, tool_number):
        # Switch to the active tool's endstop, or fallback to default
        self.active_mcu_endstop = self._endstops.get(
            tool_number, self.default_endstop)

    def add_stepper(self, stepper):
        # Called during CoreXY cross-wiring: forwards stepper to all
        # registered endstops so each MCU knows which steppers to monitor
        self._steppers.append(stepper)
        if self.default_endstop:
            self.default_endstop.add_stepper(stepper)
        for es in self._endstops.values():
            es.add_stepper(stepper)

    def get_steppers(self):
        return list(self._steppers)

    # -- MCU_endstop proxy methods --
    def home_start(self, print_time, sample_time, sample_count,
                   rest_time, triggered=True):
        if not self.active_mcu_endstop:
            raise self.printer.command_error(
                "Cannot home %s - no active tool endstop configured"
                % (self.axis_name.upper(),))
        return self.active_mcu_endstop.home_start(
            print_time, sample_time, sample_count, rest_time, triggered)

    def home_wait(self, home_end_time):
        if not self.active_mcu_endstop:
            raise self.printer.command_error(
                "Cannot get home position - no active tool endstop")
        return self.active_mcu_endstop.home_wait(home_end_time)

    def query_endstop(self, print_time):
        if not self.active_mcu_endstop:
            raise self.printer.command_error(
                "Cannot query endstop - no active tool endstop")
        return self.active_mcu_endstop.query_endstop(print_time)
```

### `tool_axis_endstop.py` — Entry points

**Unnamed section (global defaults):**
```python
def load_config(config):
    printer = config.get_printer()
    x_default = config.get('x_default_pin', None)
    y_default = config.get('y_default_pin', None)

    for axis, default_pin in (('x', x_default), ('y', y_default)):
        if default_pin is None:
            continue
        chip_name = 'toolchanger_%c' % (axis,)
        router = printer.lookup_object(chip_name, None)
        if router is None:
            router = ToolAxisEndstop(printer, axis)
        ppins = printer.lookup_object('pins')
        ppins.allow_multi_use_pin(
            default_pin.replace('^', '').replace('!', ''))
        mcu_endstop = ppins.setup_pin('endstop', default_pin)
        router.set_default_endstop(mcu_endstop)

    return printer.lookup_object('toolchanger', None)
```

**Per-tool section:**
```python
def load_config_prefix(config):
    printer = config.get_printer()
    ppins = printer.lookup_object('pins')
    name = config.get_name()

    # Extract tool tag from "tool_axis_endstop T0" -> "T0" -> 0
    parts = name.split(None, 1)
    tool_tag = parts[1] if len(parts) > 1 else ''

    tool_number = config.getint('tool', None)
    if tool_number is None and tool_tag:
        try:
            t = tool_tag.upper()
            if t.startswith('T'):
                tool_number = int(t[1:])
        except ValueError:
            pass

    x_pin = config.get('x_pin', None)
    y_pin = config.get('y_pin', None)

    for axis, pin in (('x', x_pin), ('y', y_pin)):
        if pin is None:
            continue
        chip_name = 'toolchanger_%c' % (axis,)
        router = printer.lookup_object(chip_name, None)
        if router is None:
            router = ToolAxisEndstop(printer, axis)
        ppins.allow_multi_use_pin(
            pin.replace('^', '').replace('!', ''))
        mcu_endstop = ppins.setup_pin('endstop', pin)
        router.add_endstop(tool_number, mcu_endstop)

    return printer.lookup_object('toolchanger', None)
```

### `toolchanger.py` changes — ~8 lines

In `_configure_toolhead_for_tool`, after the existing `tool_probe_endstop` routing (line 604-606), add:

```python
def _configure_toolhead_for_tool(self, tool):
    if self.active_tool:
        self.active_tool.deactivate()
    self.active_tool = tool
    if self.tool_probe_endstop:
        probe = tool.probe if tool else None
        self.tool_probe_endstop.set_active_probe(probe)
    # NEW: Route axis endstops to the active tool
    for axis in ('x', 'y'):
        chip_name = 'toolchanger_%c' % (axis,)
        router = self.printer.lookup_object(chip_name, None)
        if router:
            tn = tool.tool_number if tool else None
            router.set_active_tool(tn)
    if self.active_tool:
        self.active_tool.activate()
```

Import `logging` is already present. No other imports needed since we look up via `printer.lookup_object`.

---

## Config Migration (user's Laurion3D Trident)

### `printer.cfg` — line 175:
```diff
- endstop_pin: tool_0:PB8
+ endstop_pin: toolchanger_x:x_virtual_endstop
```

### `klipper-toolchanger/tool_0.cfg` — add before [tool T0]:
```cfg
[tool_axis_endstop T0]
tool: 0
x_pin: tool_0:PB8
```

### `klipper-toolchanger/tool_1.cfg` — add before [tool T1]:
```cfg
[tool_axis_endstop T1]
tool: 1
x_pin: tool_1:PB8
```

### `klipper-toolchanger/includes.cfg` — no changes needed
The per-tool files are already included, and the `[tool_axis_endstop Tn]` sections will be processed before `[stepper_x]` (which is at line 168 of printer.cfg).

---

## Example Configs

### `examples/axis_endstop/toolhead_n.cfg`
```
[tool_axis_endstop T0]
tool: 0
x_pin: ^mcu_t0:PB8

[tool T0]
...
```

### `examples/axis_endstop/homing.cfg`
```
[homing_override]
axes: xyz
gcode:
    G90
    INITIALIZE_TOOLCHAIN
    {% if 'X' in params or home_all %}
        G28 X
    {% endif %}
    ...
```

### `examples/axis_endstop/printer.cfg`
```
[stepper_x]
endstop_pin: toolchanger_x:x_virtual_endstop
...
```

---

## Verification

1. `python3 -m compileall klipper/extras/tool_axis_endstop.py` — syntax check
2. `python3 -c "import sys; sys.path.insert(0, 'klipper'); from extras.tool_axis_endstop import ToolAxisEndstop; print('OK')"` — import test
3. Review the toolchanger.py patch for correctness

---

## Validation: Config-time Coverage Check

Added to `toolchanger._handle_connect()`:

```python
def _validate_axis_endstop_coverage(self):
    for axis in ('x', 'y'):
        router = self.printer.lookup_object('toolchanger_%c' % (axis,), None)
        if router is None:
            continue  # Per-tool routing not active for this axis
        missing = [str(tn) for tn in self.tools
                    if not router.has_endstop(tn)]
        if missing:
            raise self.printer.config_error(
                "Per-tool %s endstop routing active but tool(s) %s "
                "have no %s_pin in [tool_axis_endstop TN] section"
                % (axis.upper(), ', '.join(missing), axis))
```

Public method on `ToolAxisEndstop`:
```python
def has_endstop(self, tool_number):
    return tool_number in self._endstops
```

This runs at `klippy:connect`, after all config is parsed. If a tool lacks its `[tool_axis_endstop Tn]` section, the printer won't start — the error is caught early.

## Edge Cases Covered

- **No `[tool_axis_endstop Tn]` sections exist**: Virtual chip is never created. `[stepper_x]` with old pin works as before. No behavior change.
- **Tool without override selected**: Falls back to default endstop. If no default registered, raises clear error during homing.
- **CoreXY cross-wiring**: `add_stepper` forwards to ALL registered tool endstops, so each MCU knows which steppers to monitor during homing.
- **Shared probe/X pin**: `allow_multi_use_pin` prevents pin conflict.
- **Unmounted tool**: The router doesn't care about tool presence — it routes to whatever tool is "active". Pin is on CAN-connected MCU so it's always accessible.
- **Duplicate chips**: `printer.lookup_object(chip_name, None)` checks before creating, so the first `[tool_axis_endstop Tn]` creates the chip and subsequent ones reuse it.
