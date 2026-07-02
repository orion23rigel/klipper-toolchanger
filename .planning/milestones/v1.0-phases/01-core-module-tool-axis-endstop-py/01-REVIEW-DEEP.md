---
phase: "01"
status: issues_found
files_reviewed: 9
critical: 3
blocker: 3
warning: 4
info: 5
total: 12
depth: deep
date: 2026-06-30
---

# Phase 01: Deep Code Review — Per-Tool X/Y Endstop Routing

**Reviewed:** 2026-06-30T00:00:00Z
**Depth:** deep
**Files Reviewed:** 9
**Status:** issues_found

## Summary

This is a deep cross-file review of the `tool_axis_endstop.py` module and its integration with the existing toolchanger ecosystem. The implementation follows the established pattern from `tool_probe_endstop.py` closely, which is a good sign. However, several **critical bugs** were found in the `home_wait` method, the `add_stepper` forwarding logic, and the `load_config_prefix` design. Additionally, there are warnings around edge cases during tool unselection, validation timing, and `ast.literal_eval` usage that could cause runtime failures.

---

## Critical Issues

### CR-01: `home_wait` ignores `home_start` return value — homing completion never checked

**Severity:** Critical
**File:** `klipper/extras/tool_axis_endstop.py:95-99`
**Description:**
The `home_wait` method discards the return value of `home_start` from `home_start`. In the MCU_endstop interface, `home_start` returns an `event_time` that `home_wait` must use as the `home_end_time` parameter. The current implementation of `home_wait` receives `home_end_time` as a parameter from the caller (the homing module), but the `home_start` call at line 92-93 returns a value that is **never stored or used**. More critically, the `home_start` return value is the event time when the MCU is expected to trigger — this is what `home_wait` needs to synchronize with. The current code forwards to `active_mcu_endstop.home_start()` but discards the return value, then calls `home_wait(home_end_time)` with a parameter that was passed in from outside. This is actually the correct Klipper API pattern — but the problem is that `home_start` may raise an exception (e.g., if the MCU is not ready), and that exception is silently ignored because the return value is not checked.

The real issue: looking at how `tool_probe_endstop.py`'s `EndstopRouter` handles this — it does NOT implement `home_start` or `home_wait` at all. The probe module uses `probe.ProbeCommandHelper` and `probe.HomingViaProbeHelper` which handle the homing flow differently. The `tool_axis_endstop.py` implements `home_start` and `home_wait` directly as proxy methods, which is correct for an endstop chip. However, the **return value of `home_start` should be returned** so the homing module can call `home_wait` with the correct time. Currently, `home_wait` at line 95-99 takes `home_end_time` as a parameter — this is correct for the MCU_endstop interface. But `home_start` at line 86-93 returns the result of `self.active_mcu_endstop.home_start(...)` which is correct.

Wait — let me re-examine. The MCU_endstop interface requires:
- `home_start(print_time, sample_time, sample_count, rest_time, triggered=True)` → returns event_time
- `home_wait(home_end_time)` → returns triggered boolean

The current implementation at lines 92-93 returns the result of `home_start`, and lines 95-99 receives `home_end_time` as a parameter. This is actually correct for the proxy pattern.

**Re-evaluating: This is NOT a bug.** The implementation correctly proxies both methods. Moving to other findings.

### CR-01 (REVISED): `add_stepper` forwards steppers to ALL endstops including unregistered ones — CoreXY cross-wiring causes phantom triggers

**Severity:** Critical
**File:** `klipper/extras/tool_axis_endstop.py:63-75`
**Description:**
The `add_stepper` method (lines 63-75) forwards each stepper to **every** registered MCU_endstop, including the default endstop. During Klipper's kinematics initialization, the stepper rail calls `add_stepper` on the endstop object. For CoreXY machines, the X stepper rail consists of both A and B motors, and each motor may be on a different MCU. When `add_stepper` forwards the stepper to all registered endstops, **every tool's endstop on that axis receives the stepper**. This means during X homing, the MCU will monitor ALL tools' endstops for trigger events, not just the active tool's.

While the router correctly selects which endstop to call for `home_start`/`home_wait`/`query_endstop`, the **MCU-level trigger dispatch** still fires on all endstops that have the stepper. If tool 0's X endstop triggers (e.g., due to noise, vibration, or a shared pin), the homing could terminate prematurely even though tool 1 is active.

Compare with `tool_probe_endstop.py`'s `EndstopRouter.add_stepper` (lines 239-242):
```python
def add_stepper(self, stepper):
    self._steppers.append(stepper)
    for m in self._mcus:
        m.add_stepper(stepper)
```
This is the same pattern — it also forwards to all MCUs. However, for Z-probe, this is acceptable because only one probe is ever triggered at a time (the active tool's probe is queried). For X/Y endstops, this is more dangerous because endstop pins can trigger from mechanical vibration, and the MCU monitors ALL endstops with registered steppers.

**Evidence:**
```python
# tool_axis_endstop.py lines 63-75
def add_stepper(self, stepper):
    self._steppers.append(stepper)
    if self.default_endstop:
        self.default_endstop.add_stepper(stepper)  # <-- forwards to default too
    for es in self._endstops.values():
        es.add_stepper(stepper)  # <-- forwards to ALL tools
```

**Suggestion:**
This is a known limitation of the virtual chip pattern. The MCU monitors all endstops that have steppers registered. A mitigation is to document this risk. If this becomes a real issue, the fix would be to delay stepper registration until after MCU identification and register steppers only with the active tool's endstop. However, Klipper requires steppers to be registered before homing, so this is inherently limited by the MCU architecture. **Mark as Warning rather than Critical** since this is a fundamental limitation of the approach, not a code bug.

### CR-01 (FINAL): `set_active_tool` with `tool_number=None` during tool unselect — `active_mcu_endstop` becomes `None` if no default

**Severity:** Critical
**File:** `klipper/extras/tool_axis_endstop.py:58-61`
**Description:**
When `set_active_tool(None)` is called (which happens during `UNSELECT_TOOL` via `_configure_toolhead_for_tool(None)`), the code does:
```python
self.active_mcu_endstop = self._endstops.get(None, self.default_endstop)
```
`self._endstops.get(None, self.default_endstop)` returns `self.default_endstop` since `None` is never a key in `_endstops`. If `self.default_endstop` is also `None` (no unnamed `[tool_axis_endstop]` section configured), then `active_mcu_endstop` becomes `None`.

Subsequent calls to `home_start`, `home_wait`, or `query_endstop` will raise `printer.command_error` with "Cannot home X - no active tool endstop configured". This is **correct behavior** for an unselected tool — you shouldn't be able to home if no tool is mounted. However, there's a subtle issue: if a user has configured a default pin (unnamed `[tool_axis_endstop]` section), then after unselecting a tool, homing will use the **default endstop** instead of erroring. This is arguably correct (the default endstop is a fallback), but it means the user's homing behavior changes depending on whether they configured a global default — and this is not documented.

The bigger issue is in `_configure_toolhead_for_tool` (toolchanger.py:616-631). When `tool` is `None` (unselecting), the code sets `tn = None` and calls `router.set_active_tool(None)`. The router then looks up `_endstops.get(None, self.default_endstop)` which returns the default. But the tool's endstop was never unregistered — it's still in `_endstops`. This means the old tool's MCU_endstop is never explicitly deactivated, though it's no longer the active one.

**Evidence:**
```python
# tool_axis_endstop.py:58-61
def set_active_tool(self, tool_number):
    self.active_mcu_endstop = self._endstops.get(
        tool_number, self.default_endstop)
```

**Suggestion:**
This behavior is actually correct and safe: when no tool is selected, routing falls back to the default endstop if one exists, otherwise operations fail with a clear error. The documentation should clarify this behavior. I'll downgrade this to a Warning for documentation clarity.

### CR-02 (ACTUAL CRITICAL): `load_config_prefix` is called for EVERY `[tool Tn]` section — creates duplicate MCU_endstop instances per pin

**Severity:** Critical
**File:** `klipper/extras/tool_axis_endstop.py:135-163`
**Description:**
`load_config_prefix` is called by Klipper for each configuration section that has a matching prefix. The function name `load_config_prefix` in Klipper means this function is called when a config section matches the prefix of the module name. For `tool_axis_endstop.py`, Klipper will call `load_config_prefix` for any section starting with `tool_axis_endstop`, including `[tool_axis_endstop T0]`, `[tool_axis_endstop T1]`, etc.

However, the implementation at line 145 reads `tool_number = config.getint('tool_number', None)`. This expects the config section to have a `tool_number` parameter. But `[tool T0]` sections do NOT have a `tool_number` parameter in the `[tool T0]` section itself — the `tool_number` is read from the `[tool T0]` section by the `Tool` class in `tool.py`, not from a `[tool_axis_endstop T0]` section.

Looking at the example config (`toolhead_n.cfg`), the endstop pins are defined directly in the `[tool T0]` section:
```ini
[tool T0]
tool_number: 0
x_endstop_pin: tool_0:PB8
```

But `load_config_prefix` is looking for a `[tool_axis_endstop T0]` section with `tool_number: 0` and `x_endstop_pin` parameters. The example config does NOT have `[tool_axis_endstop T0]` sections — it has the pins directly in `[tool T0]` sections.

**This means `load_config_prefix` will never find any pins because it's looking in the wrong config sections.** The function name `load_config_prefix` means Klipper calls it for sections matching the module's prefix pattern. But the pins are in `[tool Tn]` sections, not `[tool_axis_endstop Tn]` sections.

Wait — let me re-examine. In Klipper, `load_config_prefix` is called for config sections that share a prefix with the module filename. For `tool_axis_endstop.py`, Klipper will call `load_config_prefix` for sections like:
- `[tool_axis_endstop]` (unnamed)
- `[tool_axis_endstop T0]`
- `[tool T0]` — NO, this doesn't match the prefix `tool_axis_endstop`

Actually, I need to reconsider. In Klipper, `load_config_prefix` is called for sections whose name starts with the module name. So `tool_axis_endstop.py` would get calls for:
- `[tool_axis_endstop]`
- `[tool_axis_endstop T0]`
- `[tool_axis_endstop T1]`

But the example config puts pins in `[tool T0]` sections, which do NOT match. This means the pins are **never read** by `load_config_prefix`.

**HOWEVER**, looking more carefully at the example config and the documentation, it seems the intent is that pins are defined in `[tool Tn]` sections. But `load_config_prefix` won't see those. The fix would be to either:
1. Define pins in `[tool_axis_endstop Tn]` sections (which the example doesn't do)
2. Have `tool.py`'s `load_config_prefix` or `Tool.__init__` call into `tool_axis_endstop` to register pins

Looking at how `tool_probe.py` handles this: `ToolProbe.__init__` creates its own MCU endstop and calls `self.endstop.add_probe(config, self)`. The `tool_probe_endstop` module manages the routing. There's no cross-module config reading.

For `tool_axis_endstop`, the design seems to expect `[tool_axis_endstop Tn]` sections with `tool_number` and `x_endstop_pin` parameters, but the example config puts pins in `[tool Tn]` sections. **This is a fundamental integration bug — the pins are never registered.**

**Evidence:**
```python
# tool_axis_endstop.py:135-163
def load_config_prefix(config):
    """Per-tool [tool Tn] section — reads x_endstop_pin / y_endstop_pin.
    ...
    """
    tool_number = config.getint('tool_number', None)  # expects tool_number in config
    x_pin = config.get('x_endstop_pin', None)         # expects x_endstop_pin in config
    ...
```

But the example config has:
```ini
[tool T0]
tool_number: 0
x_endstop_pin: tool_0:PB8
```

The section `[tool T0]` does NOT match the prefix `tool_axis_endstop`, so `load_config_prefix` is never called for it.

**Suggestion:**
This needs a fundamental redesign. Options:
1. Change the example config to use `[tool_axis_endstop T0]` sections with `tool_number` and `x_endstop_pin` parameters
2. Have `tool.py` register the endstop pins with `tool_axis_endstop` during `Tool.__init__`
3. Rename the module to match the prefix of `[tool Tn]` sections (e.g., `tool.py` already exists, so this won't work)

The cleanest approach is option 1: the example config should define `[tool_axis_endstop T0]` sections separately from `[tool T0]` sections, similar to how `[tool_probe T0]` is separate from `[tool T0]`.

**Wait — let me re-read the example config more carefully.**

Looking at `examples/axis_endstop/toolhead_n.cfg`:
```ini
[tool T0]
tool_number: 0
x_endstop_pin: tool_0:PB8
```

And `examples/axis_endstop/printer.cfg`:
```ini
[stepper_x]
endstop_pin: toolchanger_x:x_virtual_endstop
```

The documentation says:
> Each tool defines its X (and optionally Y) endstop pin via `x_endstop_pin` / `y_endstop_pin` parameters in its `[tool Tn]` section.

But `load_config_prefix` won't see `[tool Tn]` sections. **This is a critical bug — the feature doesn't work as documented.**

**Suggestion:**
Either:
A) Change the example to use separate `[tool_axis_endstop T0]` sections:
```ini
[tool T0]
tool_number: 0

[tool_axis_endstop T0]
tool_number: 0
x_endstop_pin: tool_0:PB8
```

B) Have `tool.py` register the pins in `Tool.__init__`:
```python
# In Tool.__init__
x_pin = self._config_get(config, 'x_endstop_pin', None)
y_pin = self._config_get(config, 'y_endstop_pin', None)
if x_pin or y_pin:
    tc = self.main_toolchanger
    if hasattr(tc, 'register_axis_endstop'):
        tc.register_axis_endstop(self.tool_number, x_pin, y_pin)
```

### CR-03: `load_config_prefix` reads `tool_number` from config but the config section is `[tool Tn]` — `tool_number` is only set on the Tool object, not in the section

**Severity:** Critical
**File:** `klipper/extras/tool_axis_endstop.py:145`
**Description:**
Even if the prefix matching worked correctly, `config.getint('tool_number', None)` at line 145 reads the `tool_number` parameter from the config section. In a `[tool T0]` section, `tool_number: 0` IS present (see `toolhead_n.cfg` line 11). So IF the prefix matching worked, this would read correctly. But the prefix matching doesn't work as explained in CR-02.

Additionally, the `load_config_prefix` function returns `printer.lookup_object('toolchanger', None)` at line 163. This is the standard Klipper pattern for prefix config functions that participate in a larger module. But since the prefix matching fails, this return value is never used.

### CR-04: `_validate_axis_endstop_coverage` runs in `_handle_connect` before tools are fully initialized

**Severity:** Warning
**File:** `klipper/extras/toolchanger.py:217-230`
**Description:**
`_validate_axis_endstop_coverage` is called in `_handle_connect` (line 215). The `klippy:connect` event fires after all config sections are parsed but before the printer is fully initialized. At this point, `self.tools` should contain all registered tools. However, the validation checks `router.has_endstop(tn)` which looks up `_endstops` in the `ToolAxisEndstop` router.

If `load_config_prefix` is never called for the `[tool Tn]` sections (as per CR-02), then `_endstops` will be empty, and the validation will correctly report that all tools are missing endstop pins. But this creates a confusing error message: "Per-tool X endstop routing active but tool(s) 0, 1 have no x_pin in [tool_axis_endstop TN] section" — when the user has actually configured the pins in `[tool Tn]` sections.

This means the validation will always fail with the current example configuration, even though the user has done everything "correctly" per the documentation.

### CR-05: `set_active_tool` is called with `tool.tool_number` but tool could be `None` — no explicit handling

**Severity:** Warning
**File:** `klipper/extras/toolchanger.py:624-629`
**Description:**
In `_configure_toolhead_for_tool` (lines 616-631):
```python
for axis in ('x', 'y'):
    chip_name = 'toolchanger_%c' % (axis,)
    router = self.printer.lookup_object(chip_name, None)
    if router:
        tn = tool.tool_number if tool else None
        router.set_active_tool(tn)
```

When `tool` is `None` (unselecting), `tn` becomes `None`, and `router.set_active_tool(None)` is called. As analyzed in CR-01 (FINAL), this falls back to `default_endstop` if configured, otherwise sets `active_mcu_endstop` to `None`. This is acceptable behavior but should be explicitly documented.

### CR-06: `ast.literal_eval` in `cmd_SET_TOOL_PARAMETER` — potential for injection via gcode parameter

**Severity:** Warning
**File:** `klipper/extras/toolchanger.py:715`
**Description:**
```python
value = ast.literal_eval(gcmd.get("VALUE"))
```
`ast.literal_eval` is safe for Python literals (strings, numbers, lists, dicts, tuples, booleans, None). It does NOT execute arbitrary code. However, if a user sends a malicious VALUE like `"__import__('os').system('rm -rf /')"`, `ast.literal_eval` will raise a `ValueError` (not execute the code). So this is actually safe.

But the result of `ast.literal_eval` is passed directly to `tool.set_parameter(name, value)` without type validation. If the VALUE is a complex nested structure, it could cause issues in downstream code that expects simple types. This is a minor concern.

**Actually, this is safe.** `ast.literal_eval` only parses Python literal expressions and cannot execute arbitrary code. The Klipper codebase already uses this pattern in `get_params_dict` (line 884). No change needed.

### CR-07: `import ast` at module level is unused except for `ast.literal_eval` — acceptable but note the dual usage

**Severity:** Info
**File:** `klipper/extras/toolchanger.py:7`
**Description:**
`import ast` is used in two places: `cmd_SET_TOOL_PARAMETER` (line 715) and `get_params_dict` (line 884). Both use `ast.literal_eval`. This is acceptable usage.

### CR-08: `from unittest.mock import sentinel` is imported but `Toolchanger.sentinel` class shadows it

**Severity:** Warning
**File:** `klipper/extras/toolchanger.py:8, 784-785`
**Description:**
Line 8 imports `sentinel` from `unittest.mock`:
```python
from unittest.mock import sentinel
```

But lines 784-785 define a local `sentinel` class:
```python
class sentinel:
    pass
```

And line 800 uses it:
```python
if default == sentinel:
```

The `from unittest.mock import sentinel` import is **never used** because the local class shadows it. The `Toolchanger.sentinel` class is used as a unique sentinel value for the `default` parameter in `gcmd_tool`. This is a common pattern, but importing `sentinel` from `unittest.mock` and then shadowing it is confusing and suggests a copy-paste error. The import should be removed.

**Suggestion:**
Remove line 8: `from unittest.mock import sentinel`

### CR-09: `tool_axis_endstop.py` does not implement `get_position_endstop` — required by MCU_endstop interface

**Severity:** Critical
**File:** `klipper/extras/tool_axis_endstop.py`
**Description:**
The Klipper `MCU_endstop` interface requires the following methods:
- `home_start(print_time, sample_time, sample_count, rest_time, triggered=True)` ✓
- `home_wait(home_end_time)` ✓
- `query_endstop(print_time)` ✓
- `add_stepper(stepper)` ✓
- `get_steppers()` ✓
- `get_position_endstop()` ✗ **MISSING**

The `get_position_endstop` method returns the Z position at which the endstop triggered (typically 0.0 for virtual endstops). The `tool_probe_endstop.py`'s `EndstopRouter` also does NOT implement this method, but the `ProbeEndstopWrapper` in `tools_calibrate.py` does implement it (line 469).

If Klipper's homing code calls `get_position_endstop` on the endstop object, it will raise `AttributeError`. This depends on whether the homing module calls this method on the virtual chip's endstop.

**Evidence:** The `probe.HomingViaProbeHelper` in `tool_probe_endstop.py` line 32 calls:
```python
probe.HomingViaProbeHelper(config, 0.0, self.mcu_probe.query_endstop)
```
The `HomingViaProbeHelper` is initialized with a fixed offset (0.0), which means it doesn't call `get_position_endstop` on the endstop object. So for the probe module, this is not an issue.

However, for X/Y axis endstops, the standard Klipper homing code DOES call `get_position_endstop` on the endstop object to determine the homing position. If this method is missing, homing will fail with `AttributeError`.

**Suggestion:**
Add `get_position_endstop` method to `ToolAxisEndstop`:
```python
def get_position_endstop(self):
    return 0.0
```

### CR-10: `load_config` (unnamed section) returns `printer.lookup_object('toolchanger', None)` which could be `None`

**Severity:** Info
**File:** `klipper/extras/tool_axis_endstop.py:132`
**Description:**
Both `load_config` (line 132) and `load_config_prefix` (line 163) return `printer.lookup_object('toolchanger', None)`. In Klipper, if a `load_config` function returns `None`, the config section is still processed but no object is registered. If it returns an object, that object is registered with the printer.

Returning `None` here is fine — the unnamed `[tool_axis_endstop]` section doesn't need to register an object. The virtual chips are created in `ToolAxisEndstop.__init__` (which is called from the prefix handler). But this return value pattern is inconsistent with other Klipper modules.

### CR-11: No `get_position_endstop` in `EndstopRouter` of `tool_probe_endstop.py` either — shared pattern gap

**Severity:** Info
**File:** `klipper/extras/tool_probe_endstop.py:223-253`
**Description:**
The `EndstopRouter` class in `tool_probe_endstop.py` (lines 223-253) also lacks `get_position_endstop`. This is consistent with `tool_axis_endstop.py`, suggesting both modules have the same gap. If Klipper's homing code requires this method, both will fail.

### CR-12: `_handle_home_rails_begin` may initialize toolchanger during homing before axis endstops are ready

**Severity:** Warning
**File:** `klipper/extras/toolchanger.py:207-209`
**Description:**
```python
def _handle_home_rails_begin(self, homing_state, rails):
    if self.initialize_on == INIT_ON_HOME and self.status == STATUS_UNINITALIZED:
        self.initialize(self.detected_tool)
```

When `initialize_on == INIT_ON_HOME`, the toolchanger initializes at the beginning of homing. If per-tool X/Y endstop routing is active, the router will attempt to set the active tool's endstop. But at this point, `self.detected_tool` might be `None` (no tool detected yet), which means `set_active_tool(None)` is called, falling back to `default_endstop` if configured.

If no default is configured, `active_mcu_endstop` is `None`, and when the actual homing move starts (G28 X), `home_start` will raise an error. This is a race condition between initialization and homing.

**Suggestion:**
Add a check in `initialize` to verify that endstop routing is set up before completing initialization:
```python
if self.tool_probe_endstop or any(
    self.printer.lookup_object('toolchanger_%c' % a, None)
    for a in ('x', 'y')
):
    # Verify endstop routing is active
    for axis in ('x', 'y'):
        router = self.printer.lookup_object('toolchanger_%c' % axis, None)
        if router and not router.active_mcu_endstop:
            raise self.printer.config_error(
                "Endstop routing for %s is active but no default endstop configured" % axis)
```

---

## Warnings

### WR-01: `add_endstop` forwards steppers only at registration time — late-registered endstops miss existing steppers

**Severity:** Warning
**File:** `klipper/extras/tool_axis_endstop.py:46-50`
**Description:**
```python
def add_endstop(self, tool_number, mcu_endstop):
    self._endstops[tool_number] = mcu_endstop
    for s in self._steppers:
        mcu_endstop.add_stepper(s)
```

This forwards existing steppers to the new endstop. However, if steppers are added AFTER the endstop (via `add_stepper`), the new endstop won't receive them. The order of Klipper's initialization determines which happens first. If the endstop is registered after the steppers are already known, the endstop won't get the steppers.

This is unlikely to be an issue in practice because Klipper processes config sections in order and the pins module creates MCU_endstops during config parsing, before kinematics initialization. But it's a fragility.

### WR-02: No validation that `x_endstop_pin` and `y_endstop_pin` pins are on the same MCU per tool

**Severity:** Warning
**File:** `klipper/extras/tool_axis_endstop.py:149-162`
**Description:**
If a tool has `x_endstop_pin: tool_0:PB8` and `y_endstop_pin: tool_1:PB8` (different MCUs), the two MCU_endstops will be on different MCUs. During homing, the homing module expects all endstops for an axis to be on the same MCU (or compatible MCUs). Cross-MCU endstops for the same axis could cause timing issues.

**Suggestion:**
Add validation that all endstops for an axis are on compatible MCUs.

### WR-03: `tool.py` typo in header: "toolchnagers" instead of "toolchangers"

**Severity:** Info
**File:** `klipper/extras/tool.py:2`
**Description:**
Header comment says "Support for toolchnagers" — typo.

### WR-04: `toolchanger.py` typo in header: "toolchnagers" instead of "toolchangers"

**Severity:** Info
**File:** `klipper/extras/toolchanger.py:1`
**Description:**
Header comment says "Support for toolchnagers" — typo.

### WR-05: `tool_probe_endstop.py` uses `probe` module import but `probe.py` is not in the repo

**Severity:** Info
**File:** `klipper/extras/tool_probe_endstop.py:6`
**Description:**
```python
from . import probe
```
This imports Klipper's core `probe` module which is not present in this repository. This is expected since the repo only contains the extensions, not the full Klipper source. But reviewers should be aware that any changes to Klipper's `probe` module API could break these extensions.

---

## Info

### IN-01: Missing `get_position_endstop` method in `ToolAxisEndstop`

**File:** `klipper/extras/tool_axis_endstop.py`
**Description:**
The `MCU_endstop` interface in Klipper requires `get_position_endstop()` which returns the position at which the endstop triggered. For virtual endstops, this should return `0.0`. Without this method, homing may fail with `AttributeError`.

**Suggestion:**
```python
def get_position_endstop(self):
    return 0.0
```

### IN-02: `set_active_tool` should document the `None` behavior

**File:** `klipper/extras/tool_axis_endstop.py:58`
**Description:**
The docstring says "Switch routing to the active tool's endstop, or fall back to default." but doesn't document what happens when `tool_number` is `None` (tool unselected).

**Suggestion:**
Update docstring: "Switch routing to the active tool's endstop. If tool_number is None (tool unselected), falls back to default_endstop if configured, otherwise sets active_mcu_endstop to None."

### IN-03: `_configure_toolhead_for_tool` iterates over axes but could be a loop variable

**File:** `klipper/extras/toolchanger.py:624-629`
**Description:**
Minor: the loop variable `axis` shadows the tuple iteration. Not a bug but could be clearer as:
```python
for axis_name in ('x', 'y'):
    chip_name = 'toolchanger_%c' % (axis_name,)
```

### IN-04: No gcode commands exposed by `tool_axis_endstop` for manual endstop switching

**File:** `klipper/extras/tool_axis_endstop.py`
**Description:**
Unlike `tool_probe_endstop.py` which exposes `SET_ACTIVE_TOOL_PROBE` and `DETECT_ACTIVE_TOOL_PROBE`, the axis endstop module has no gcode commands for manual switching. This is by design (it's automatic), but users may want to debug or manually override routing.

### IN-05: `tool_axis_endstop.py` copyright year is 2026 — future-dated

**File:** `klipper/extras/tool_axis_endstop.py:3`
**Description:**
Copyright says 2026. This is fine since we're in 2026, but the year should be updated if the code is modified in a future year.

---

## Structural Findings

### Import Graph

```
tool_axis_endstop.py
  → (no imports except logging)
  → registers chip 'toolchanger_x' and 'toolchanger_y'

toolchanger.py
  → tool_probe_endstop (imported at module level)
  → tool (via tool.py's Tool class)
  → calls tool_axis_endstop via printer.lookup_object('toolchanger_x', None)

tool_probe_endstop.py
  → probe (Klipper core, not in repo)
  → creates EndstopRouter and ProbeRouter

tool_probe.py
  → probe (Klipper core)
  → tool_probe_endstop (via self.endstop.add_probe)

tool.py
  → toolchanger (imported at module level)
  → calls toolchanger.add_probe(self.probe)
```

### Key Integration Points

1. **`toolchanger._configure_toolhead_for_tool`** (lines 616-631): Central routing point. Called during tool selection/deselection. Routes probe, fan, extruder, and axis endstops.

2. **`tool_axis_endstop.load_config_prefix`** (lines 135-163): Per-tool endstop registration. **BROKEN** — prefix matching doesn't match `[tool Tn]` sections.

3. **`toolchanger._validate_axis_endstop_coverage`** (lines 217-230): Validation at `klippy:connect`. Will always fail with current example config because `load_config_prefix` never registers pins.

4. **`toolchanger._handle_home_rails_begin`** (lines 207-209): Auto-initialization on homing. Race condition with endstop routing.

### Cross-Module Consistency

| Pattern | tool_probe_endstop | tool_axis_endstop |
|---------|-------------------|-------------------|
| Virtual chip registration | `printer.add_object('probe', self)` | `printer.add_object(chip_name, self)` |
| Stepper forwarding | `EndstopRouter.add_stepper` | `ToolAxisEndstop.add_stepper` |
| Active routing | `set_active_probe` | `set_active_tool` |
| get_position_endstop | ❌ Missing | ❌ Missing |
| Gcode commands | 4 commands | 0 commands |
| Manual override | SET_ACTIVE_TOOL_PROBE | None |

---

## Summary of Findings

| Severity | Count | Key Issues |
|----------|-------|------------|
| Critical | 3 | CR-02: `load_config_prefix` never sees `[tool Tn]` sections (broken integration); CR-04: Validation always fails with documented config; CR-09: Missing `get_position_endstop` |
| Warning | 4 | WR-01: Late stepper registration gap; WR-02: No cross-MCU validation; WR-05: Probe module import gap; WR-03/04: Typos |
| Info | 5 | IN-01 through IN-05: Documentation, naming, and design notes |

**The most critical finding is CR-02: the `load_config_prefix` function will never be called for `[tool Tn]` sections because the section name prefix doesn't match the module name.** This means the entire per-tool X/Y endstop routing feature is non-functional with the documented configuration. The example configs and documentation describe using `[tool Tn]` sections with `x_endstop_pin`/`y_endstop_pin` parameters, but Klipper's config prefix matching system will never invoke `load_config_prefix` for those sections.

**Recommended fix:** Either (A) change the example config to use separate `[tool_axis_endstop Tn]` sections, or (B) have `tool.py` register the endstop pins with the router during `Tool.__init__`.

---

_Reviewed: 2026-06-30T00:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
