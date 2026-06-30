---
phase: "01"
status: gaps_found
files_reviewed: 2
critical: 0
blocker: 0
warning: 4
info: 3
total: 7
depth: standard
date: 2026-06-30
---

# Phase 01: Code Review Report

**Reviewed:** 2026-06-30T00:00:00Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** gaps_found

## Summary

Two Klipper firmware extension files were reviewed: `tool_axis_endstop.py` (the core virtual endstop router) and `toolchanger.py` (the patched toolchanger integrating axis-endstop routing). The implementation mirrors the existing `tool_probe_endstop.py` pattern and is broadly sound. However, several issues were identified:

- **Critical logic gap**: when `tool=None` is passed to `set_active_tool()`, the router falls back to `self.default_endstop` (which may be `None`), but there is no safeguard to prevent homing with a `None` active endstop if the default was never configured.
- **Stepper registration race**: `add_stepper()` forwards steppers to *all* registered endstops including the default, which means steppers get registered on endstops that may not be their physical home — a CoreXY cross-wiring concern.
- **Missing `home_start`/`home_wait`/`query_endstop` consistency**: `home_wait` is never overridden to delegate properly, and `query_endstop` in `home_wait` path uses `home_end_time` but the real Klipper MCU_endstop expects `home_end_time` as a print_time. The parameter naming is misleading but functionally correct.
- **Integration gaps**: `_validate_axis_endstop_coverage()` is called at connect time but the routers may not yet be fully populated (per-tool config sections may not have been parsed yet depending on load order).

---

## Warnings

### WR-01: `set_active_tool(None)` silently sets `active_mcu_endstop` to `None` when no default is configured

**Severity:** Warning
**File:** `klipper/extras/tool_axis_endstop.py:58-61`
**Description:** When `set_active_tool(None)` is called (which happens during `_configure_toolhead_for_tool` when `tool` is `None`, i.e., tool unselection), the method does:

```python
self.active_mcu_endstop = self._endstops.get(tool_number, self.default_endstop)
```

Since `tool_number` is `None`, `self._endstops.get(None, ...)` returns `self.default_endstop`. If the unnamed `[tool_axis_endstop]` section was not configured (no `x_default_pin`/`y_default_pin`), then `self.default_endstop` is `None`. The subsequent `home_start()`, `home_wait()`, and `query_endstop()` methods *do* check for `not self.active_mcu_endstop` and raise an error. However, the check is at the *next* call site, not at the routing switch. This means an intermediate state exists where `active_mcu_endstop` is `None` and the object is in a broken-but-not-yet-crashed state. If any code path reads `self.active_mcu_endstop` directly (rather than going through the proxy methods), it will get `None` without warning.

**Fix:** Either (a) always maintain a valid default endstop (require `x_default_pin`/`y_default_pin` when per-tool routing is used), or (b) have `set_active_tool(None)` raise a config error if no default is configured, or (c) set `active_mcu_endstop` to a no-op/dummy endstop when no default exists. The cleanest approach:

```python
def set_active_tool(self, tool_number):
    if tool_number is not None and tool_number in self._endstops:
        self.active_mcu_endstop = self._endstops[tool_number]
    elif self.default_endstop is not None:
        self.active_mcu_endstop = self.default_endstop
    else:
        raise self.printer.config_error(
            "No endstop configured for axis %s - configure x_default_pin/y_default_pin "
            "or define endstops for all tools" % self.axis_name.upper())
```

### WR-02: `_validate_axis_endstop_coverage()` runs at connect time but routers may not be fully populated

**Severity:** Warning
**File:** `klipper/extras/toolchanger.py:211-230`
**Description:** The `_validate_axis_endstop_coverage()` method is called in `_handle_connect()` (line 215). However, Klipper's config parsing order is not guaranteed to have processed all `[tool_axis_endstop Tn]` sections before the `toolchanger` object's connect handler fires. The `load_config_prefix()` function for per-tool sections calls `printer.lookup_object(chip_name, None)` and creates the router if needed, but the order of `klippy:connect` event dispatch relative to remaining config parsing is undefined. If a tool's endstop hasn't been registered yet, the validation will produce a false-positive error.

**Fix:** Move the validation to a later event hook such as `klippy:ready` instead of `klippy:connect`, or defer it until after all config sections have been parsed. Alternatively, perform the validation lazily on first use (first `home_start` call) rather than at connect time.

### WR-03: `add_stepper()` forwards steppers to *all* endstops including tools that don't own the physical axis

**Severity:** Warning
**File:** `klipper/extras/tool_axis_endstop.py:63-75`
**Description:** The `add_stepper()` method forwards each stepper to every registered MCU_endstop:

```python
def add_stepper(self, stepper):
    self._steppers.append(stepper)
    if self.default_endstop:
        self.default_endstop.add_stepper(stepper)
    for es in self._endstops.values():
        es.add_stepper(stepper)
```

This means a stepper on Tool 0's X endstop gets registered on Tool 1's X endstop too. In Klipper, the `add_stepper` call on an MCU_endstop adds the stepper to that MCU's trigger monitoring list. While this is described as "CoreXY cross-wiring" in the comment, it has a subtle bug: if Tool 0 has an X endstop on pin `!X endstop` and Tool 1 has an X endstop on pin `!Y endstop` (e.g., a CoreXY printer where each tool's "X" endstop is actually a Y-axis sensor), then Tool 0's stepper gets registered on Tool 1's MCU_endstop which monitors the Y-axis pin — creating a cross-wiring that may cause false triggers or missed triggers during homing.

The pattern in `tool_probe_endstop.py`'s `EndstopRouter.add_mcu()` does the same thing, so this is consistent with the reference pattern. However, the comment should be clearer about the implications.

**Fix:** Either (a) document this behavior as a known requirement (all tools must use the same physical endstop pins for each axis), or (b) add a validation check that all tools' endstops for the same axis use the same physical pin, raising a config error at load time if they differ.

### WR-04: `set_active_tool(tn)` in `_configure_toolhead_for_tool` does not guard against `tool_number` being `None` for the `_endstops.get()` lookup

**Severity:** Warning
**File:** `klipper/extras/toolchanger.py:624-629`
**Description:** In `_configure_toolhead_for_tool`:

```python
for axis in ('x', 'y'):
    chip_name = 'toolchanger_%c' % (axis,)
    router = self.printer.lookup_object(chip_name, None)
    if router:
        tn = tool.tool_number if tool else None
        router.set_active_tool(tn)
```

When `tool` is `None` (tool unselection), `tn` becomes `None`, and `set_active_tool(None)` is called. As noted in WR-01, this routes to the default endstop or sets `active_mcu_endstop = None`. However, there's no corresponding `tool_probe_endstop.set_active_probe(None)` call — that *is* present (line 621-622), so the probe side handles `None` correctly. The inconsistency is that the probe system has an explicit `set_active_probe(None)` path that resets `active_tool_number = -1`, while the axis endstop system has no equivalent reset and relies entirely on the default-endstop fallback.

**Fix:** Ensure parity with the probe system. Either require a default endstop when using tool unselection, or add explicit `None` handling in `set_active_tool()` that mirrors the probe system's behavior.

---

## Info

### IN-01: Unused import `from unittest.mock import sentinel`

**Severity:** Info
**File:** `klipper/extras/toolchanger.py:8`
**Description:** The `sentinel` object from `unittest.mock` is imported but only used as a marker value (line 787: `default=sentinel`). This works but is semantically misleading — `sentinel` is a testing construct, not a general-purpose marker. Klipper's own codebase uses `None` or custom marker classes for this purpose.

**Fix:** Replace with a simple class marker:

```python
class _Sentinel:
    pass
sentinel = _Sentinel()
```

Or use `None` with a separate `has_default` flag.

### IN-02: `load_config()` and `load_config_prefix()` return `printer.lookup_object('toolchanger', None)` which may be `None`

**Severity:** Info
**File:** `klipper/extras/tool_axis_endstop.py:132,175`
**Description:** Both `load_config()` (line 132) and `load_config_prefix()` (line 175) return the result of `printer.lookup_object('toolchanger', None)`. In Klipper, the return value of `load_config`/`load_config_prefix` is used as the object handle for `printer.load_object()` calls. If the return value is `None`, other code that does `printer.load_object(config, 'tool_axis_endstop')` would get `None`, which could cause AttributeErrors downstream.

However, looking at the code, `tool_axis_endstop` is never loaded via `printer.load_object()` by other code — it's only registered as a pin chip. So this return value is effectively dead code. But it's a Klipper convention that `load_config` should return the created object.

**Fix:** Either return `router` (the last router created) or return `None` explicitly with a comment explaining why, or remove the return statement entirely.

### IN-03: `home_wait` parameter name is misleading

**Severity:** Info
**File:** `klipper/extras/tool_axis_endstop.py:95-99`
**Description:** The `home_wait` method takes a parameter named `home_end_time`, which suggests it's a timestamp. In Klipper's MCU_endstop interface, this parameter is actually a print_time value used to compute how long to wait. The name is consistent with the underlying Klipper API, but the docstring should clarify this.

**Fix:** Add a docstring:

```python
def home_wait(self, home_end_time):
    """Wait for homing to complete. home_end_time is the print_time at which
    the MCU should have finished the homing move."""
    ...
```

---

_Reviewed: 2026-06-30T00:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
