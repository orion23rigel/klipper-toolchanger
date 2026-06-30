# Phase 1: Core Module — `tool_axis_endstop.py` - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Create the `ToolAxisEndstop` virtual chip class and both config loaders. This is the foundation that enables per-tool X and Y endstop routing — the same pattern already used for Z probe routing in `tool_probe_endstop.py`.

</domain>

<decisions>
## Implementation Decisions

### Virtual Chip Registration
- **D-01:** Use Klipper's `pins.register_chip()` pattern — register `toolchanger_x` and `toolchanger_y` chips that implement the `MCU_endstop` proxy interface. Same approach as `HommingViaProbeHelper` for Z probes.
- **D-02:** `setup_pin()` returns `self` so the stepper rail uses this object as its endstop. Virtual pins referenced as `toolchanger_x:x_virtual_endstop` and `toolchanger_y:y_virtual_endstop`.

### Config Loader Design
- **D-03:** `load_config()` handles optional unnamed `[tool_axis_endstop]` section with `x_default_pin`/`y_default_pin` for global fallback.
- **D-04:** `load_config_prefix()` handles per-tool `[tool_axis_endstop Tn]` sections — tool number inferred from section name suffix (e.g., "T0" → 0) or explicit `tool` parameter.
- **D-05:** Lazy chip creation — the virtual chip is only created when the first config section references it. If no sections exist, no behavior change.

### CoreXY Cross-Wiring
- **D-06:** `add_stepper()` forwards steppers to ALL registered endstops (default + per-tool). This ensures each MCU's trigger dispatch knows which steppers to monitor during homing — required for CoreXY kinematics.

### Shared Pin Support
- **D-07:** `allow_multi_use_pin()` called before `setup_pin()` for each pin to prevent conflicts when probe pin and endstop pin share the same physical pin (e.g., PB8 on EBB36 toolhead MCUs).

### Public API
- **D-08:** `has_endstop(tool_number)` public method for validation — used by Phase 2's `_validate_axis_endstop_coverage()`.

### the agent's Discretion
- Module file path: `klipper/extras/tool_axis_endstop.py` (consistent with existing `tool_probe_endstop.py` location)
- Error messages: Use `printer.config_error` for config-time errors, `printer.command_error` for runtime errors
- Logging: Use existing `import logging` pattern from other modules

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements
- `.planning/ROADMAP.md` §Phase 1 — Full phase description with success criteria and tasks
- `.planning/REQUIREMENTS.md` — XEND-01 through XEND-05, YEND-01, YEND-02, COMPAT-01, COMPAT-03

### Existing Code (Pattern Reference)
- `klipper/extras/tool_probe_endstop.py` — Z probe routing pattern (EndstopRouter/ProbeRouter)
- `klipper/extras/tool_probe.py` — Per-tool probe registration
- `klipper/extras/toolchanger.py` — Tool lifecycle, `_configure_toolhead_for_tool()` integration point
- `klipper/extras/tool.py` — Per-tool settings and probe registration

### Implementation Plan
- `.opencode/plans/per-tool-axis-endstop.md` — Detailed code design with full implementations

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ToolProbeEndstop` / `EndstopRouter` / `ProbeRouter` in `tool_probe_endstop.py` — the Z probe routing pattern to replicate for X/Y axes
- `ToolAxisEndstop` class already exists in `klipper/extras/tool_axis_endstop.py` (175 lines) — fully implemented
- `toolchanger._configure_toolhead_for_tool()` — integration point for routing on tool change (already patched at lines 624-629)
- `toolchanger._validate_axis_endstop_coverage()` — validation at `klippy:connect` (already patched at lines 217-230)

### Established Patterns
- Virtual chip registration via `ppins.register_chip(chip_name, self)` returns `self` from `setup_pin()`
- Per-tool config via `load_config_prefix()` with tool number from section name suffix
- `allow_multi_use_pin()` before `setup_pin()` for shared pins
- `printer.lookup_object('toolchanger', None)` for optional toolchanger dependency

### Integration Points
- `toolchanger.py:624-629` — X/Y routing in `_configure_toolhead_for_tool()` (already implemented)
- `toolchanger.py:217-230` — validation in `_handle_connect()` (already implemented)
- `klipper/extras/tool_axis_endstop.py` — core module (already created, compiles successfully)

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the ROADMAP success criteria. The implementation plan at `.opencode/plans/per-tool-axis-endstop.md` provides the full code design.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Core Module — `tool_axis_endstop.py`*
*Context gathered: 2026-06-29*
