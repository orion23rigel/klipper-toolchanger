# Concerns: klipper-toolchanger

**Date:** 2026-06-27

## Technical Debt

### 1. Typo in Type Names
- `STATUS_UNINITALIZED` should be `STATUS_INITIALIZED` (typo in constant name, `toolchanger.py:11`)
- Class name `Toolchnagers` in module docstring typo (`toolchanger.py:3`, `tool.py:1`)
- `cmd_ENTER_DOCKING_MODE` / `cmd_EXIT_DOCKING_MODE` help text has typo: "dock" → "docking" (`toolchanger.py:247`)
- `cmd_TEST_TOOL_DOCKING` help: "Dock and undock" — minor inconsistency

### 2. No Automated Tests
- Zero test files in the entire codebase
- All validation relies on manual printer-side testing
- Critical paths (tool change state machine, probe routing) have no regression protection
- This is the highest-priority concern — any change risks undetected breakage

### 3. Magic Numbers and Hardcoded Values
- `_FUTURE = 9999999999999999.` in `toolchanger.py:27` — unclear purpose
- `10` active interval limit in `ToolMissingHelper` (`toolchanger.py:61`)
- `EPSILON = 1e-9` and `EPSILON_ANGLE = 0.001` in `rounded_path.py` — unexplained thresholds
- `BED_COOLDOWN_TIME = 30 * 60 * 1.0` in `bed_thermal_adjust.py:9` — magic constant

### 4. Monkey Patching and Command Interception
- `bed_thermal_adjust.py:32-37` removes and re-registers `M140`/`M190` — fragile if another module registers these first
- `rounded_path.py:103-104` can replace `G0` entirely — dangerous if other extensions expect standard G0
- `tool_probe_endstop.py:37-39` replaces the `[probe]` object — potential conflict with other probe-using extensions

## Known Issues and Bug History

### Resolved (from `.planning/debug/tool-probe-z-offset-not-applied.md`)
- **Probe Z offset not applied during prints** — `TOOL_BED_MESH_CALIBRATE` macro used `SET_KINEMATIC_POSITION` which discarded probe-derived Z coordinate (fixed in commit `5606ef81`)
- **Virtual endstop static zero offset** — `HomingViaProbeHelper` constructed with static zero instead of dynamic probe offset (fixed in commit `d7afb69`)

### Potential Issues
- **Tool detection race condition:** `note_detect_change()` calls `tool_missing_helper.note_tool_change()` which schedules a delayed callback — if multiple detection changes happen rapidly, callbacks may fire out of order
- **Fan speed transfer edge case:** `FanSwitcher` uses `pending_speed` to handle speed changes before fan is active — potential for lost speed if multiple rapid changes occur
- **Position restore during error:** `_recover_position()` in `process_error()` uses `last_change_pickup_tool` which may be None during error recovery

## Fragile Areas

### 1. Klipper API Compatibility (`tool_probe_endstop.py`)
- Directly constructs `HomingViaProbeHelper`, `SampleAveragingHelper`, `ProbeEndstopWrapper` — these are internal Klipper APIs that may change between versions
- The debug artifact shows this has already caused regressions when upstream Klipper changed probe APIs
- **Risk:** High — breaking changes in Klipper will break this extension

### 2. G-code State Manipulation (`toolchanger.py`)
- Direct manipulation of `gcode_move.saved_states` in `process_error()` (`toolchanger.py:494-496`) — described as "HACKY HACKY HACKY" in code comment
- Manual position restoration bypasses normal Klipper state management
- **Risk:** Medium — Klipper internal state changes could break position restoration

### 3. Reactor Timer Management (`toolchanger.py`, `tool_probe_endstop.py`)
- `validate_tool_timer` registration/unregistration (`toolchanger.py:590-593`) — timer lifecycle management is error-prone
- `ToolMissingHelper` uses lookahead callbacks and reactor timers for delayed tool-missing detection
- **Risk:** Medium — timer leaks or missed callbacks could cause false tool-missing detection

### 4. Tool Number Assignment (`toolchanger.py`, `tool.py`)
- `assign_tool()` modifies `tool_numbers` list and `tool_names` list simultaneously
- `register_t_gcode()` checks for existing command registration but may silently fail
- **Risk:** Low — but duplicate tool numbers cause config errors rather than graceful handling

## Security Considerations

- **No authentication:** Klipper runs on local network, assumes trusted environment
- **G-code injection:** All user G-code is executed directly — standard Klipper threat model
- **No file I/O:** Extension does not read/write files at runtime
- **No network:** Extension does not make network calls

## Performance Concerns

- **Rounded path Bezier computation:** Uses numpy for curve generation — acceptable for Klipper's timescale but could be optimized with precomputed tables
- **Active interval list in ToolMissingHelper:** Fixed size 10 with `del self.active_intervals[0]` — acceptable but could use deque
- **No caching:** `get_status()` is called frequently by Moonraker/web interface — some computations could be cached
