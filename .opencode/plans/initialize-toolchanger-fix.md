# Initialize Toolchanger Fix

## Root Cause

When `homing:home_rails_begin` fires, `_handle_home_rails_begin` calls `initialize(self.detected_tool)` where `detected_tool` may be `None` (buttons module hasn't processed the detection pin state yet). This runs `initialize_gcode` which contains `INITIALIZE_TOOLCHANGER`, which calls `initialize(self.detected_tool)` again — both pass `None`, causing `_configure_toolhead_for_tool(None)` to clear the active probe.

## Part 1: cmd_INITIALIZE_TOOLCHANGER (line 311-318)

**Current:**
```python
def cmd_INITIALIZE_TOOLCHANGER(self, gcmd):
    tool = self.gcmd_tool(gcmd, self.detected_tool)
    was_error  = self.status == STATUS_ERROR
    self.initialize(tool)
```

**New:**
```python
def cmd_INITIALIZE_TOOLCHANGER(self, gcmd):
    tool = self.gcmd_tool(gcmd, None)
    if tool is None:
        tool = self.require_detected_tool(gcmd.respond_info)
    was_error  = self.status == STATUS_ERROR
    self.initialize(tool)
```

This ensures `INITIALIZE_TOOLCHANGER` always resolves the tool via `require_detected_tool()` (waits for debounce, detects current tool) before calling `initialize()`.

## Part 2: initialize() (line 435)

**Current:**
```python
        if select_tool or self.has_detection:
            self._configure_toolhead_for_tool(select_tool)
```

**New:**
```python
        if select_tool or self.has_detection:
            configure_tool = select_tool if select_tool else (self.detected_tool if self.detected_tool else self.require_detected_tool(lambda msg: None))
            self._configure_toolhead_for_tool(configure_tool)
```

When `select_tool` is `None` but `has_detection` is `True`, use `detected_tool` if already settled, otherwise call `require_detected_tool()` to detect. The no-op lambda avoids unnecessary logging during programmatic calls.

When `select_tool` is `None` but `has_detection` is `True`, use `detected_tool` if already settled, otherwise call `require_detected_tool()` to detect. The no-op lambda avoids unnecessary logging during programmatic calls.
