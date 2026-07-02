---
phase: 01-02
reviewed: 2026-07-01T00:00:00Z
depth: deep
files_reviewed: 13
files_reviewed_list:
  - klipper/extras/tool_probe.py
  - klipper/extras/tool.py
  - klipper/extras/tools_calibrate.py
  - klipper/extras/toolchanger.py
  - klipper/extras/tool_probe_endstop.py
  - klipper/extras/tool_axis_endstop.py
  - klipper/extras/rounded_path.py
  - klipper/extras/manual_rail.py
  - klipper/extras/multi_fan.py
  - klipper/extras/bed_thermal_adjust.py
  - install.sh
  - usermods/Contomo/tool_drop_detection/tool_drop_detection.py
  - usermods/VIN-y/save_baby_steps/save_babies.py
findings:
  critical: 3
  warning: 11
  info: 8
  total: 22
status: issues_found
---

# Code Review Report — Deep Review

**Reviewed:** 2026-07-01T00:00:00Z
**Depth:** deep
**Files Reviewed:** 13
**Status:** issues_found

## Summary

A deep cross-file review of the entire Klipper toolchanger codebase was performed. The codebase implements a multi-tool printer system with per-tool endstop routing, Z-probe switching, bed calibration, thermal compensation, and accelerometer-based crash detection.

**Key concerns identified:**

1. **Security: `ast.literal_eval` used on user-provided gcode parameters** in `SET_TOOL_PARAMETER` — while `literal_eval` is safer than `eval`, it still allows construction of arbitrary Python data structures (lists, tuples, dicts) which could be exploited to cause side effects or bypass intended parameter types.

2. **Bug: `tools_calibrate.py` references undefined `pins` module** — `ProbeEndstopWrapper` calls `pins.error()` on line 318–320 but `pins` is never imported.

3. **Bug: `tool_axis_endstop.py` `load_config()` returns the wrong object** — it returns `printer.lookup_object('toolchanger', None)` instead of returning itself, which may break Klipper's object registration expectations.

4. **Bug: `manual_rail.py` uses `force_move.calc_move_time` but `accel` may be 0** — when `accel` defaults to 0, the move-time calculation will produce division-by-zero or infinite cruise time.

5. **Multiple race conditions** in tool detection and state transitions across `toolchanger.py`, `tool_probe_endstop.py`, and `tool_drop_detection.py`.

---

## Critical Issues

### CR-01: `ast.literal_eval` on user-provided gcode parameter allows arbitrary Python data structures

**File:** `klipper/extras/toolchanger.py:762`
**Issue:** The `cmd_SET_TOOL_PARAMETER` command uses `ast.literal_eval()` to parse user-supplied parameter values from gcode. While `literal_eval` does not execute arbitrary code, it *does* parse arbitrary Python literals including lists, tuples, dicts, sets, and nested structures. An attacker with gcode access could pass complex data structures like `"[[1,2],[3,4]]"` or `"{\"key\": \"value\"}"` that could cause unexpected behavior downstream. This is a security boundary violation — gcode input should be strictly typed, not parsed as arbitrary Python.

**Fix:** Replace `ast.literal_eval` with a strict type parser that only accepts the types the toolchanger actually supports:

```python
def cmd_SET_TOOL_PARAMETER(self, gcmd):
    tool = self._get_tool_from_gcmd(gcmd)
    name = gcmd.get("PARAMETER")
    value_str = gcmd.get("VALUE")
    # Parse based on the expected type of the parameter
    if name in tool.params:
        expected_type = type(tool.params[name])
        if expected_type == float:
            value = float(value_str)
        elif expected_type == int:
            value = int(value_str)
        elif expected_type == bool:
            value = value_str.lower() in ('true', '1', 'yes')
        else:
            value = value_str  # string
    else:
        # Default: try float, then int, then string
        try:
            value = float(value_str)
        except ValueError:
            value = value_str
    tool.set_parameter(name, value)
```

---

### CR-02: `ProbeEndstopWrapper` references undefined `pins` module

**File:** `klipper/extras/tools_calibrate.py:318-320`
**Issue:** In the `PrinterProbeMultiAxis.setup_pin()` method, the code calls `pins.error()` at lines 318 and 320, but the `pins` module is never imported in this file. The file imports only `logging`. This will raise a `NameError` at runtime whenever a stepper references the `xy_virtual_endstop` pin, causing the entire printer configuration to fail on startup.

```python
# Line 317-320:
def setup_pin(self, pin_type, pin_params):
    if pin_type != 'endstop' or pin_params['pin'] != 'xy_virtual_endstop':
        raise pins.error("Probe virtual endstop only useful as endstop pin")
    if pin_params['invert'] or pin_params['pullup']:
        raise pins.error("Can not pullup/invert probe virtual endstop")
```

**Fix:** Either import the pins module or use `self.printer.config_error` which is already available:

```python
def setup_pin(self, pin_type, pin_params):
    if pin_type != 'endstop' or pin_params['pin'] != 'xy_virtual_endstop':
        raise self.printer.config_error("Probe virtual endstop only useful as endstop pin")
    if pin_params['invert'] or pin_params['pullup']:
        raise self.printer.config_error("Can not pullup/invert probe virtual endstop")
```

---

### CR-03: `tool_axis_endstop.py` `load_config()` returns wrong object — may break Klipper object registration

**File:** `klipper/extras/tool_axis_endstop.py:151`
**Issue:** The `load_config()` function (for the unnamed `[tool_axis_endstop]` section) returns `printer.lookup_object('toolchanger', None)` instead of returning an object representing itself. Klipper's config system expects config loaders to return the object that should be registered or accessible via `lookup_object`. Returning the toolchanger object means the `tool_axis_endstop` object is never properly registered, and any code that tries to `lookup_object('tool_axis_endstop')` will get the toolchanger instead. This could cause subtle bugs in any future code that expects to interact with the axis endstop module through the standard Klipper object system.

**Fix:** Return a meaningful object or `None` explicitly:

```python
def load_config(config):
    # ... existing code ...
    return None  # or return the router for x/y if needed
```

Or if the module needs to be addressable:

```python
def load_config(config):
    printer = config.get_printer()
    # ... existing code ...
    # Register self as tool_axis_endstop
    printer.add_object('tool_axis_endstop', cls)
    return cls
```

---

## Warnings

### WR-01: Race condition in tool change — `current_change_id` can be stale if multiple tool changes overlap

**File:** `klipper/extras/toolchanger.py:467-469, 510`
**Issue:** The `select_tool()` method sets `self.current_change_id` at the start and resets it at the end. However, the `process_error()` method also resets `self.current_change_id` to -1. If an error occurs during a tool change and `process_error` is called, it resets the change ID. If another tool change is initiated before the error handler completes, the new change's ID check in `process_error` (line 523: `self.current_change_id != -1`) may incorrectly determine whether it's inside a tool change. This is a classic TOCTOU race.

**Fix:** Add a lock or use atomic operations. Consider using a context manager:

```python
import threading

class Toolchanger:
    def __init__(self, config):
        self._change_lock = threading.Lock()
        # ...

    def select_tool(self, gcmd, tool, restore_axis):
        with self._change_lock:
            this_change_id = self.next_change_id
            self.next_change_id += 1
            self.current_change_id = this_change_id
            try:
                # ... rest of method ...
            finally:
                self.current_change_id = -1
```

---

### WR-02: `tool.py` `_handle_connect` can crash if `fan_name` lookup fails

**File:** `klipper/extras/tool.py:111-112`
**Issue:** The `_handle_connect` method tries two lookups for the fan:
```python
self.fan = self.printer.lookup_object(self.fan_name,
          self.printer.lookup_object("fan_generic " + self.fan_name, None))
```
If `fan_generic <name>` doesn't exist, `lookup_object` with a default returns `None`, but if the first lookup for `self.fan_name` fails (returns `None` because the section doesn't exist), the second lookup is attempted. However, if the fan section name contains spaces or special characters, string concatenation `"fan_generic " + self.fan_name` could produce an invalid section name. Additionally, `lookup_object` with a non-`None` default doesn't work as a fallback — it evaluates the default argument *before* the function call, which could raise if `"fan_generic " + self.fan_name` doesn't exist.

**Fix:** Use explicit conditional lookup:

```python
if self.fan_name:
    self.fan = self.printer.lookup_object(self.fan_name, None)
    if self.fan is None:
        self.fan = self.printer.lookup_object("fan_generic " + self.fan_name, None)
```

---

### WR-03: `tool.py` `activate()` runs sync extruder motion twice with potential for failure

**File:** `klipper/extras/tool.py:193-197`
**Issue:** The `activate()` method runs two `SYNC_EXTRUDER_MOTION` commands sequentially via `gcode.run_script_from_command()`. If the first command fails (e.g., the extruder stepper doesn't exist), the second command still runs, potentially causing a double-sync or error cascade. There's no error checking between the two calls.

**Fix:** Check for the extruder stepper before running:

```python
if self.extruder_stepper and hotend_extruder:
    gcode.run_script_from_command(
        "SYNC_EXTRUDER_MOTION EXTRUDER='%s' MOTION_QUEUE=" % (self.extruder_stepper_name,))
    if self.extruder_stepper_name != hotend_extruder:
        gcode.run_script_from_command(
            "SYNC_EXTRUDER_MOTION EXTRUDER='%s' MOTION_QUEUE='%s'" % (self.extruder_stepper_name, hotend_extruder,))
```

---

### WR-04: `tool_drop_detection.py` global variable mutation — `_STATISTIC_FN` reassigned mid-class

**File:** `usermods/Contomo/tool_drop_detection/tool_drop_detection.py:149`
**Issue:** The module-level variable `_STATISTIC_FN` is defined at line 16 as `statistics.median`, then reassigned at line 149 inside `ToolDropDetection.__init__`:
```python
global _STATISTIC_FN
_STATISTIC_FN = cfg.getchoice('samples_result', statistics_mode, 'median')
```
This global mutation means that if multiple `ToolDropDetection` instances are created (e.g., with different configurations), they will all share the same statistics function, and the last one to initialize wins. This is a subtle state corruption bug that's hard to debug.

**Fix:** Make `_STATISTIC_FN` an instance variable:

```python
self.stat_fn = cfg.getchoice('samples_result', statistics_mode, 'median')
# Then use self.stat_fn everywhere instead of _STATISTIC_FN
```

---

### WR-05: `tool_drop_detection.py` `_raw_to_vector` division by zero if `base_g` is 0

**File:** `usermods/Contomo/tool_drop_detection/tool_drop_detection.py:41`
**Issue:** The `_raw_to_vector` function divides by `defaults.get('base_g', 1.0) * FREEFALL_MS2`. If a user configures `base_g = 0`, this produces a division by zero. While the default is 1.0, user-configurable values are not validated.

**Fix:** Add validation:

```python
def _raw_to_vector(raw_vector, defaults={}):
    base_g = defaults.get('base_g', 1.0)
    if base_g == 0.0:
        base_g = 1.0  # or raise an error
    gx, gy, gz = (axis / 1.0 / (base_g * FREEFALL_MS2) for axis in raw_vector)
    return (gx, gy, gz)
```

---

### WR-06: `tool_drop_detection.py` `_average_samples` empty `zip` on empty input after window slicing

**File:** `usermods/Contomo/tool_drop_detection/tool_drop_detection.py:53-61`
**Issue:** The function checks `if not samples: return (0.0, 0.0, 0.0)` at the top, but the window slicing at line 58 can produce an empty window even when `samples` is non-empty. For example, `samples[:0]` returns `[]`, and `zip(*[])` raises `ValueError: zip() argument 2 must be an iterable`. This happens when `amount=0` and the input is non-empty.

**Fix:** Add an additional check after windowing:

```python
def _average_samples(samples, amount=0):
    if not samples:
        return (0.0, 0.0, 0.0)
    window = (samples[:amount] if amount > 0 else samples[amount:] if amount < 0 else samples)
    if not window:
        return (0.0, 0.0, 0.0)
    xs, ys, zs = zip(*window)
    return (_STATISTIC_FN(xs), _STATISTIC_FN(ys), _STATISTIC_FN(zs))
```

---

### WR-07: `tool_drop_detection.py` `_reset()` method is effectively a no-op

**File:** `usermods/Contomo/tool_drop_detection/tool_drop_detection.py:355-360`
**Issue:** The `_reset()` method has all its body commented out:
```python
def _reset(self):
    _ = None
    #for n in self._targets(None):
        #p = self.pollers.pop(n, None)
        #if p:
            #p.stop();
```
This method is registered as a handler for `klippy:firmware_restart` event. When a firmware restart occurs, pollers are never stopped, which means the timer callbacks continue to fire and may reference stale objects after restart. This is a resource leak and potential crash vector.

**Fix:** Uncomment and fix the reset logic:

```python
def _reset(self):
    for name in list(self.pollers.keys()):
        p = self.pollers.pop(name, None)
        if p:
            p.stop()
```

---

### WR-08: `tool_drop_detection.py` `polling_freq` maxval check allows values above `MAX_POLL_FREQ`

**File:** `usermods/Contomo/tool_drop_detection/tool_drop_detection.py:125`
**Issue:** The config defines `maxval=MAX_POLL_FREQ` (20.0 Hz) for `polling_freq`, but the `_cmd_polling_start` method at line 316 clamps `freq_req` to `MAX_POLL_FREQ` again:
```python
freq = min(freq_req, MAX_POLL_FREQ)
```
The config validation and runtime clamping are redundant but not harmful. However, the config-level `maxval` only prevents Klipper from accepting values above 20, while the runtime clamp silently reduces values. This inconsistency means the startup report doesn't warn about clamping, but the runtime does. The real issue is that `def_freq` (the config value) is used as a default in some code paths and the clamped `freq` in others, leading to inconsistent behavior.

**Fix:** Ensure consistency by always using the clamped value:

```python
self.def_freq = min(cfg.getfloat('polling_freq', 1.00, minval=0.01, maxval=MAX_POLL_FREQ), MAX_POLL_FREQ)
```

---

### WR-09: `tool_drop_detection.py` typo in variable name: `_angle_diffrence`

**File:** `usermods/Contomo/tool_drop_detection/tool_drop_detection.py:35`
**Issue:** The function `_angle_diffrence` has a typo in its name ("diffrence" instead of "difference"). While this is primarily a code quality issue, the function appears to be unused (not called anywhere in the file), making it dead code. Dead code increases maintenance burden and confusion.

**Fix:** Either rename the function and use it, or remove it:

```python
def _angle_difference(a0, a1):
    diff = ((a0 - a1 + 180) % 360) - 180
    return diff
```

---

### WR-10: `install.sh` hardcoded paths — script will fail on non-standard Klipper installations

**File:** `install.sh:3-4`
**Issue:** The script hardcodes `KLIPPER_PATH="${HOME}/klipper"` and `INSTALL_PATH="${HOME}/klipper-toolchanger"`. If Klipper is installed in a non-standard location (e.g., `/opt/klipper` or a virtualenv), the install will silently fail by creating symlinks to the wrong directory. There's no validation that the Klipper path actually exists before proceeding.

**Fix:** Add path validation and make paths configurable:

```bash
KLIPPER_PATH="${KLIPPER_PATH:-${HOME}/klipper}"
INSTALL_PATH="${INSTALL_PATH:-${HOME}/klipper-toolchanger}"

function preflight_checks {
    if [ ! -d "$KLIPPER_PATH" ]; then
        echo "[ERROR] Klipper path '$KLIPPER_PATH' does not exist!"
        exit -1
    fi
    # ... rest of checks
}
```

---

### WR-11: `bed_thermal_adjust.py` `to_heater_temp` division by zero when `temp_drop` is 1.0

**File:** `klipper/extras/bed_thermal_adjust.py:90`
**Issue:** The `to_heater_temp` method computes:
```python
return max(surface_temp, min(self.max_heater_temp, (surface_temp - self.ambient_temp * self.temp_drop) / (1.0 - self.temp_drop)))
```
If `temp_drop` is configured as exactly `1.0`, this produces division by zero. The config validation at line 29 uses `below=1.0`, which should prevent this, but Klipper's `config.getfloat` with `below` uses a strict comparison. If a user sets `temperature_drop_per_degree: 0.9999999999`, the result approaches infinity. Additionally, if `temp_drop` is exactly `0.0`, the division `1.0 - 0.0 = 1.0` is fine, but the `to_surface_temp` method at line 82 would return `heater_temp - max((heater_temp - self.ambient_temp) * 0.0, 0.0) = heater_temp`, which is correct but the inverse formula would be `surface_temp / 1.0 = surface_temp` — consistent but potentially confusing.

**Fix:** Add explicit guard:

```python
def to_heater_temp(self, surface_temp):
    if surface_temp <= 0:
        return surface_temp
    if abs(1.0 - self.temp_drop) < 1e-9:
        return surface_temp  # no adjustment needed
    return max(surface_temp, min(self.max_heater_temp, (surface_temp - self.ambient_temp * self.temp_drop) / (1.0 - self.temp_drop)))
```

---

## Info

### IN-01: `toolchanger.py` magic number `_FUTURE = 9999999999999999.`

**File:** `klipper/extras/toolchanger.py:28`
**Issue:** The constant `_FUTURE` is used as a sentinel for "never expire" in interval tracking. While the value is large, it's a magic number without documentation. The value `9999999999999999` is close to Python's float precision limit and could cause floating-point comparison issues.

**Fix:** Use `float('inf')` instead:

```python
_FUTURE = float('inf')
```

---

### IN-02: `toolchanger.py` `cmd_SELECT_TOOL` doesn't validate T parameter range

**File:** `klipper/extras/toolchanger.py:330-331`
**Issue:** The `T` parameter in `cmd_SELECT_TOOL` is parsed as a bare integer without validation. A user could pass `T=-1` or `T=999999` which would be passed to `lookup_tool()` and return `None`, then the error message would be shown. While this is handled gracefully, the error message format is inconsistent — `gcmd.error` raises an exception that terminates the command, but the message format differs from other validation errors.

**Fix:** Add explicit range validation:

```python
tool_nr = gcmd.get_int('T', None, minval=0)
```

---

### IN-03: `tool.py` `get_status` returns `0.0` for offsets that are falsy but valid

**File:** `klipper/extras/tool.py:148-150`
**Issue:** The `get_status` method uses `self.gcode_x_offset if self.gcode_x_offset else 0.0` which treats `0.0` as falsy. If a tool's offset is legitimately `0.0`, the status will correctly show `0.0`, but if the offset is `-0.0` (which equals `0.0` in Python), or if the offset is `0` (integer), the behavior is correct but the pattern is misleading. More importantly, if `gcode_x_offset` is `0.0` and the user checks the status to determine if an offset has been set, they cannot distinguish "not set" from "set to zero".

**Fix:** Use explicit `is not None` check or a sentinel value:

```python
'gcode_x_offset': self.gcode_x_offset if self.gcode_x_offset is not None else 0.0,
```

---

### IN-04: `tools_calibrate.py` `cmd_TOOL_CALIBRATE_SAVE_TOOL_OFFSET` doesn't validate SECTION/ATTRIBUTE

**File:** `klipper/extras/tools_calibrate.py:156-157`
**Issue:** The `save_tool_offset` command accepts arbitrary `SECTION` and `ATTRIBUTE` parameters from the user. A malicious user could craft a command like `TOOL_CALIBRATE_SAVE_TOOL_OFFSET SECTION="[gcode_macro FOO]" ATTRIBUTE=gcode VALUE=...` to inject arbitrary config entries. While Klipper's `configfile.set()` may have its own protections, the lack of input validation is a concern.

**Fix:** Validate section and attribute names against a whitelist:

```python
import re
if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', section_name):
    raise gcmd.error("Invalid section name")
```

---

### IN-05: `tool_probe_endstop.py` `_describe_tool_detection_issue` uses `map()` which returns iterator in Python 3

**File:** `klipper/extras/tool_probe_endstop.py:117`
**Issue:** The string formatting `"%s" % map(lambda p: p.name, candidates)` in Python 3 produces `<map object at 0x...>` instead of the actual names, because `map()` returns an iterator, not a list. The `%s` formatter calls `str()` on the map object, which produces the unhelpful representation.

**Fix:** Convert to list:

```python
return "Multiple probes not triggered: %s" % ", ".join(p.name for p in candidates)
```

---

### IN-06: `rounded_path.py` unused import `from math import comb`

**File:** `klipper/extras/rounded_path.py:13`
**Issue:** The `comb` function is imported from `math` but the `_bernstein_poly` function (line 72-77) uses it. Actually, `comb` *is* used. However, `numpy` is imported as `np` but only used in `_bezier_curve`. This is fine, but the import order is unconventional — `numpy` is imported before the standard library `math` module.

---

### IN-07: `tool_drop_detection.py` `adxl345` module not found in repository

**File:** `usermods/Contomo/tool_drop_detection/tool_drop_detection.py:6`
**Issue:** The `tool_drop_detection.py` module imports `from . import adxl345` but no `adxl345.py` file exists in the repository (confirmed by glob search). This module is a usermod that depends on an external Klipper usermod (`adxl345`). If users install `tool_drop_detection.py` without also installing the `adxl345` usermod, the import will fail at startup. The README should document this dependency explicitly.

---

### IN-08: `tool_drop_detection.py` `_vector_angle` comment admits unguarded divide-by-zero

**File:** `usermods/Contomo/tool_drop_detection/tool_drop_detection.py:27`
**Issue:** The comment on line 27 reads: `# 5$ if you can manage to get a divide by 0, not guarding it.` This is a dangerous admission — the function computes `mag0 = math.sqrt(sum(a*a for a in v0))` and divides by `mag0 * mag1`. If `v0` is `(0, 0, 0)`, `mag0` is `0.0` and division by zero occurs. While the caller should not pass a zero vector, there's no defensive check.

**Fix:** Add a guard:

```python
def _vector_angle(v0, defaults={}):
    v1 = defaults.get('base_vector', (0.0, -1.0, 0.0))
    dot = sum(a*b for a,b in zip(v0, v1))
    mag0 = math.sqrt(sum(a*a for a in v0))
    mag1 = math.sqrt(sum(a*a for a in v1))
    if mag0 == 0.0 or mag1 == 0.0:
        return 0.0  # or raise an error
    arg = max(-1.0, min(1.0, dot/(mag0*mag1)))
    return math.degrees(math.acos(arg))
```

---

## Structural Findings (fallow)

No fallow structural pre-pass was configured (fallow is disabled by default).

---

---

_Reviewed: 2026-07-01T00:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
