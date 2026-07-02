---
phase: "01"
status: gaps_found
files_reviewed: 8
critical: 2
blocker: 2
warning: 5
info: 7
total: 14
depth: deep
date: 2026-06-30
---

# Phase 01: Deep Code Review — Per-Tool X/Y Endstop Routing

**Reviewed:** 2026-06-30T00:00:00Z
**Depth:** deep
**Files Reviewed:** 8
**Status:** gaps_found

## Summary

This is a deep cross-file review of `tool_axis_endstop.py` and its integration with the existing toolchanger ecosystem. The implementation closely follows the established pattern from `tool_probe_endstop.py`, which is a good sign. However, several **critical bugs** were found: a `load_config_prefix` return-value issue that creates duplicate `Toolchanger` objects, a `set_active_tool(None)` edge case that can leave endstop routing in an inconsistent state during tool unselection, and a `_handle_shutdown` race condition that doesn't update endstop routers. Additionally, there are warnings around variable shadowing, dead code, and missing consistency with the probe routing pattern.

The previous review (01-REVIEW-DEEP.md) incorrectly flagged `get_position_endstop` as missing — it IS present at line 80. Its previous CR-02 about `load_config_prefix` never matching `[tool Tn]` sections was also incorrect — the example config correctly uses `[tool_axis_endstop Tn]` sections. This independent review corrects those false positives and finds new real issues.

---

## Critical Issues

### CR-01: `toolchanger.py` `load_config_prefix` creates duplicate `Toolchanger` objects

**Severity:** Critical
**File:** `klipper/extras/toolchanger.py:896-897`
**Description:**
The `load_config_prefix` function at line 896 creates a new `Toolchanger` for every config section whose name starts with the module prefix `toolchanger`. In Klipper, `load_config` handles the exact section match (`[toolchanger]`), and `load_config_prefix` handles prefix matches (`[toolchanger Tn]`, etc.). However, the implementation returns `Toolchanger(config)` unconditionally — if any `[toolchanger Tn]` sections exist, a duplicate `Toolchanger` object is created and registered with the printer.

Even more critically, this is dead code in practice (no `[toolchanger Tn]` sections are used), but it's a latent bug that will cause issues if someone adds such sections. The correct pattern is shown by `tool.py` and `tool_probe.py` — `load_config_prefix` creates objects for per-tool sections, not for the main module.

**Evidence:**
```python
# klipper/extras/toolchanger.py:896-897
def load_config_prefix(config):
    return Toolchanger(config)
```

Compare with `tool.py` which correctly handles per-tool `[tool Tn]` sections:
```python
# klipper/extras/tool.py:213-214
def load_config_prefix(config):
    return Tool(config)
```

**Suggestion:**
Remove `load_config_prefix` from `toolchanger.py` entirely, or replace with:
```python
def load_config_prefix(config):
    # Per-tool toolchanger sections are not supported;
    # all tools are defined via [tool Tn] sections in tool.py
    return None
```

### CR-02: `_handle_shutdown` doesn't update axis endstop routers — stale routing after shutdown

**Severity:** Critical
**File:** `klipper/extras/toolchanger.py:238-242`
**Description:**
`_handle_shutdown` resets `self.active_tool = None` and `self.gcode_transform.tool = None`, but it does NOT update the axis endstop routers (`toolchanger_x` and `toolchanger_y`). Compare with `_handle_command_error` (lines 232-236) which also resets `active_tool` but similarly doesn't update routers.

After a shutdown, if the printer recovers and a tool is selected, the routers will still have the old `active_mcu_endstop` from before the shutdown. This means homing could route to a tool's endstop that was active before the shutdown, which may not be the correct tool.

More importantly, if `_handle_shutdown` is called during a toolchange (e.g., MCU error), the `active_mcu_endstop` remains pointing to the previous tool's endstop. On recovery, the next homing command could use the wrong endstop.

**Evidence:**
```python
# klipper/extras/toolchanger.py:238-242
def _handle_shutdown(self):
    self.status = STATUS_UNINITALIZED
    self.tool_missing_helper.deactivate_at_time(_FUTURE)
    self.active_tool = None
    self.gcode_transform.tool = None
    # Missing: router.set_active_tool(None) for each axis
```

Compare with `_configure_toolhead_for_tool` which correctly updates routers:
```python
# klipper/extras/toolchanger.py:623-629
for axis in ('x', 'y'):
    chip_name = 'toolchanger_%c' % (axis,)
    router = self.printer.lookup_object(chip_name, None)
    if router:
        tn = tool.tool_number if tool else None
        router.set_active_tool(tn)
```

**Suggestion:**
Add router updates to `_handle_shutdown` and `_handle_command_error`:
```python
def _handle_shutdown(self):
    self.status = STATUS_UNINITALIZED
    self.tool_missing_helper.deactivate_at_time(_FUTURE)
    self.active_tool = None
    self.gcode_transform.tool = None
    for axis in ('x', 'y'):
        router = self.printer.lookup_object('toolchanger_%c' % (axis,), None)
        if router:
            router.set_active_tool(None)

def _handle_command_error(self):
    self.status = STATUS_UNINITALIZED
    self.tool_missing_helper.deactivate()
    self.active_tool = None
    self.gcode_transform.tool = None
    for axis in ('x', 'y'):
        router = self.printer.lookup_object('toolchanger_%c' % (axis,), None)
        if router:
            router.set_active_tool(None)
```

---

## Warnings

### WR-01: `note_detect_change` parameter `tool` is shadowed by loop variable

**Severity:** Warning
**File:** `klipper/extras/toolchanger.py:558-568`
**Description:**
The method parameter `tool` is shadowed by the `for tool in self.tools.values()` loop variable. After the loop, `tool` refers to the last element of `self.tools.values()`, not the original parameter. While the parameter is not used after the loop (only `eventtime` is used), this is confusing and could lead to bugs if someone later tries to use the `tool` parameter.

**Evidence:**
```python
# klipper/extras/toolchanger.py:558-561
def note_detect_change(self, tool, eventtime):
    detected = None
    detected_names = []
    for tool in self.tools.values():  # shadows parameter
```

**Suggestion:**
Rename the loop variable:
```python
for t in self.tools.values():
    if t.detect_state == DETECT_PRESENT:
        detected = t
        detected_names.append(t.name)
```

### WR-02: `add_stepper` forwards to ALL endstops including default — phantom trigger risk

**Severity:** Warning
**File:** `klipper/extras/tool_axis_endstop.py:63-75`
**Description:**
`add_stepper` forwards each stepper to the default endstop AND all per-tool endstops. During X homing, the MCU monitors ALL endstops that have the stepper registered. If tool 0's X endstop triggers (due to noise, vibration, or a shared pin), the MCU will detect it even though tool 1 is active.

The router correctly selects which endstop to call for `home_start`/`home_wait`/`query_endstop`, but the MCU-level trigger dispatch fires on all endstops with registered steppers. This is a fundamental limitation of the virtual chip pattern — the MCU doesn't know which endstop is "active."

Compare with `tool_probe_endstop.py`'s `EndstopRouter.add_stepper` (line 239-242) which uses the same pattern. For Z-probe, this is acceptable because the probe is only queried during probing. For X/Y endstops, the risk of phantom triggers is higher.

**Evidence:**
```python
# klipper/extras/tool_axis_endstop.py:63-75
def add_stepper(self, stepper):
    self._steppers.append(stepper)
    if self.default_endstop:
        self.default_endstop.add_stepper(stepper)  # forwards to default
    for es in self._endstops.values():
        es.add_stepper(stepper)  # forwards to ALL tools
```

**Suggestion:**
Document this as a known limitation. If phantom triggers become a problem, consider delaying stepper registration until after MCU identification and registering steppers only with the active tool's endstop. This would require a Klipper API change.

### WR-03: `set_active_tool(None)` falls back to default endstop — silent behavior change

**Severity:** Warning
**File:** `klipper/extras/tool_axis_endstop.py:58-61`
**Description:**
When `set_active_tool(None)` is called (during tool unselection), the code does:
```python
self.active_mcu_endstop = self._endstops.get(None, self.default_endstop)
```
This returns `self.default_endstop` since `None` is never a key in `_endstops`. If a default endstop is configured (via unnamed `[tool_axis_endstop]` section), homing after tool unselection will silently use the default endstop instead of raising an error. This is not documented and could confuse users who expect homing to fail when no tool is selected.

**Evidence:**
```python
# klipper/extras/tool_axis_endstop.py:58-61
def set_active_tool(self, tool_number):
    self.active_mcu_endstop = self._endstops.get(
        tool_number, self.default_endstop)
```

**Suggestion:**
Either:
1. Document the fallback behavior in the docstring
2. Raise a clear error when `tool_number` is `None` and no default is configured
3. Add a gcode command `SET_ACTIVE_TOOL_AXIS ENDSTOP=none` to explicitly clear routing

### WR-04: `_handle_home_rails_begin` initializes toolchanger before endstop routing is ready

**Severity:** Warning
**File:** `klipper/extras/toolchanger.py:207-209`
**Description:**
When `initialize_on == INIT_ON_HOME`, the toolchanger initializes at the beginning of homing (`homing:home_rails_begin` event). At this point, `self.detected_tool` might be `None` (no tool detected yet), which means `_configure_toolhead_for_tool(None)` is called. This sets `active_mcu_endstop` to the default endstop (if configured) or `None`.

If no default is configured, `active_mcu_endstop` is `None`, and when the actual homing move starts (G28 X), `home_start` will raise "Cannot home X - no active tool endstop configured". This is a race condition between initialization and homing.

**Evidence:**
```python
# klipper/extras/toolchanger.py:207-209
def _handle_home_rails_begin(self, homing_state, rails):
    if self.initialize_on == INIT_ON_HOME and self.status == STATUS_UNINITALIZED:
        self.initialize(self.detected_tool)
```

**Suggestion:**
Add a check in `initialize` to verify that endstop routing is set up before completing initialization:
```python
# In initialize(), after _configure_toolhead_for_tool(select_tool):
for axis in ('x', 'y'):
    router = self.printer.lookup_object('toolchanger_%c' % (axis,), None)
    if router and not router.active_mcu_endstop:
        raise self.printer.config_error(
            "Endstop routing for %s is active but no default endstop configured" % axis)
```

### WR-05: `tool.py` line 13 `self.params` assignment is dead code — immediately overwritten at line 36

**Severity:** Warning
**File:** `klipper/extras/tool.py:13, 36`
**Description:**
Line 13 assigns `self.params = config.get_prefix_options('params_')` which returns a list of option name strings. Line 36 immediately overwrites it: `self.params = {**self.toolchanger.params, **toolchanger.get_params_dict(config)}` which creates a dict. The line 13 assignment is dead code that serves no purpose.

**Evidence:**
```python
# klipper/extras/tool.py:13
self.params = config.get_prefix_options('params_')  # dead code
# ...
# klipper/extras/tool.py:36
self.params = {**self.toolchanger.params, **toolchanger.get_params_dict(config)}  # overwrites
```

**Suggestion:**
Remove line 13.

---

## Info

### IN-01: `from unittest.mock import sentinel` is imported but shadowed by `class sentinel`

**Severity:** Info
**File:** `klipper/extras/toolchanger.py:8, 784-785`
**Description:**
Line 8 imports `sentinel` from `unittest.mock`, but lines 784-785 define a local `class sentinel: pass`. The import is never used because the local class shadows it. The `Toolchanger.sentinel` class is used as a unique sentinel value for the `default` parameter in `gcmd_tool`. This is a common pattern, but importing `sentinel` from `unittest.mock` and then shadowing it is confusing and suggests a copy-paste error.

**Evidence:**
```python
# klipper/extras/toolchanger.py:8
from unittest.mock import sentinel
# ...
# klipper/extras/toolchanger.py:784-785
class sentinel:
    pass
# klipper/extras/toolchanger.py:800
if default == sentinel:
```

**Suggestion:**
Remove line 8: `from unittest.mock import sentinel`

### IN-02: `tool.py` typo in header: "toolchnagers" instead of "toolchangers"

**Severity:** Info
**File:** `klipper/extras/tool.py:1`
**Description:**
Header comment says "Support for toolchnagers" — typo.

**Suggestion:**
Change to "Support for toolchangers".

### IN-03: `toolchanger.py` typo in header: "toolchnagers" instead of "toolchangers"

**Severity:** Info
**File:** `klipper/extras/toolchanger.py:1`
**Description:**
Header comment says "Support for toolchnagers" — typo.

**Suggestion:**
Change to "Support for toolchangers".

### IN-04: `tool.py` fan lookup at line 112-113 has confusing structure

**Severity:** Info
**File:** `klipper/extras/tool.py:112-113`
**Description:**
```python
self.fan = self.printer.lookup_object(self.fan_name,
          self.printer.lookup_object("fan_generic " + self.fan_name, None))
```
The fallback `fan_generic` lookup is evaluated eagerly (before the outer `lookup_object`) and used as the default argument. The indentation suggests the `fan_generic` lookup is the primary lookup, but it's actually the fallback. The code works correctly but is misleading.

**Suggestion:**
Split into explicit logic:
```python
self.fan = self.printer.lookup_object(self.fan_name, None)
if self.fan is None:
    self.fan = self.printer.lookup_object("fan_generic " + self.fan_name, None)
```

### IN-05: `tool_axis_endstop.py` `set_active_tool` docstring doesn't document `None` behavior

**Severity:** Info
**File:** `klipper/extras/tool_axis_endstop.py:58`
**Description:**
The docstring says "Switch routing to the active tool's endstop, or fall back to default." but doesn't document what happens when `tool_number` is `None` (tool unselected). When `None` is passed, `_endstops.get(None, self.default_endstop)` returns `self.default_endstop` (since `None` is never a key).

**Suggestion:**
Update docstring:
```python
def set_active_tool(self, tool_number):
    """Switch routing to the active tool's endstop, or fall back to default.

    If tool_number is None (tool unselected), falls back to default_endstop
    if configured, otherwise sets active_mcu_endstop to None (homing will fail).
    """
```

### IN-06: `tool_axis_endstop.py` `load_config_prefix` silently handles unnamed sections

**Severity:** Info
**File:** `klipper/extras/tool_axis_endstop.py:138-178`
**Description:**
`load_config_prefix` is called by Klipper for BOTH `[tool_axis_endstop]` (unnamed) and `[tool_axis_endstop Tn]` (per-tool) sections. For the unnamed section, `tool_tag` is empty, `tool_number` stays `None`, and `x_pin`/`y_pin` are `None` (since the unnamed section uses `x_default_pin`/`y_default_pin`). The loop skips because pins are `None`. No harm is done, but the function silently does nothing for the unnamed section, which is handled by `load_config` instead.

**Suggestion:**
Add an early return for unnamed sections:
```python
if not tool_tag:
    return printer.lookup_object('toolchanger', None)
```

### IN-07: `_configure_toolhead_for_tool` iterates over axes but doesn't check if router exists before calling `set_active_tool`

**Severity:** Info
**File:** `klipper/extras/toolchanger.py:624-629`
**Description:**
The loop checks `if router:` before calling `set_active_tool(tn)`, which is correct. However, if the router doesn't exist (no `[tool_axis_endstop Tn]` sections configured), the axis endstop routing is silently skipped. This means the feature is opt-in — if no `[tool_axis_endstop]` sections exist, the virtual chips are never created and homing uses the old hardcoded pins.

This is by design (the feature is optional), but users who expect per-tool routing to be active without configuring `[tool_axis_endstop]` sections will be confused.

**Suggestion:**
No code change needed — this is documented behavior. Consider adding a warning in `_handle_connect` if `uses_axis` includes 'x' or 'y' but no axis endstop routers are configured.

---

## Structural Findings

### Import Graph

```
tool_axis_endstop.py
  → (no imports except logging)
  → registers chip 'toolchanger_x' and 'toolchanger_y'
  → called by: toolchanger.py (via printer.lookup_object)

toolchanger.py
  → tool_probe_endstop (imported at module level, line 9)
  → registers gcode commands: INITIALIZE_TOOLCHANGER, SELECT_TOOL, SET_TOOL_TEMPERATURE, etc.
  → calls tool_axis_endstop via printer.lookup_object('toolchanger_x', None) in _configure_toolhead_for_tool

tool_probe_endstop.py
  → probe (Klipper core, not in repo)
  → creates EndstopRouter and ProbeRouter
  → called by: toolchanger.py (via add_probe)

tool_probe.py
  → probe (Klipper core)
  → tool_probe_endstop (via self.endstop.add_probe)

tool.py
  → toolchanger (imported at module level)
  → calls toolchanger.add_probe(self.probe)
```

### Key Integration Points

1. **`toolchanger._configure_toolhead_for_tool`** (lines 616-631): Central routing point. Called during tool selection/deselection. Routes probe, fan, extruder, and axis endstops.

2. **`tool_axis_endstop.load_config_prefix`** (lines 138-178): Per-tool endstop registration. Correctly matches `[tool_axis_endstop Tn]` sections.

3. **`toolchanger._validate_axis_endstop_coverage`** (lines 217-230): Validation at `klippy:connect`. Correctly checks all tools have endstop pins.

4. **`toolchanger._handle_home_rails_begin`** (lines 207-209): Auto-initialization on homing. Race condition with endstop routing.

5. **`toolchanger._handle_shutdown`** (lines 238-242): Does NOT update axis endstop routers — stale routing after shutdown.

6. **`toolchanger._handle_command_error`** (lines 232-236): Does NOT update axis endstop routers — stale routing after error.

### Cross-Module Consistency

| Pattern | tool_probe_endstop | tool_axis_endstop |
|---------|-------------------|-------------------|
| Virtual chip registration | `printer.add_object('probe', self)` | `printer.add_object(chip_name, self)` |
| Stepper forwarding | `EndstopRouter.add_stepper` | `ToolAxisEndstop.add_stepper` |
| Active routing | `set_active_probe` | `set_active_tool` |
| get_position_endstop | ❌ Missing | ✅ Present (line 80) |
| Gcode commands | 4 commands | 0 commands |
| Manual override | SET_ACTIVE_TOOL_PROBE | None |
| Shutdown cleanup | N/A (probe doesn't track state) | ❌ Missing router update |
| Error cleanup | N/A | ❌ Missing router update |

---

## Summary of Findings

| Severity | Count | Key Issues |
|----------|-------|------------|
| Critical | 2 | CR-01: `load_config_prefix` creates duplicate `Toolchanger` objects; CR-02: `_handle_shutdown` doesn't update axis endstop routers |
| Warning | 5 | WR-01: Variable shadowing; WR-02: Phantom trigger risk; WR-03: Silent fallback behavior; WR-04: Race condition on home; WR-05: Dead code |
| Info | 7 | IN-01 through IN-07: Imports, typos, documentation, and design notes |

**The most critical finding is CR-02:** `_handle_shutdown` and `_handle_command_error` don't update the axis endstop routers, leaving stale routing after a shutdown or error. This means after recovery, homing could use the wrong tool's endstop, which could cause physical damage to the printer (homing into a tool that isn't mounted, or using an endstop that's on a detached toolhead).

**Recommended fix for CR-02:** Add `router.set_active_tool(None)` for each axis in both `_handle_shutdown` and `_handle_command_error`.

---

_Reviewed: 2026-06-30T00:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
