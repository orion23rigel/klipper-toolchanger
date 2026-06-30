# Phase 2: Toolchanger Integration + Validation - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the axis endstop routers into the toolchanger lifecycle and add config validation. This phase patches `toolchanger.py` to call `router.set_active_tool()` on every tool change and validates coverage at `klippy:connect`.

</domain>

<decisions>
## Implementation Decisions

### Tool Change Integration
- **D-01:** `_configure_toolhead_for_tool()` calls `router.set_active_tool(tool.tool_number)` for both X and Y routers after the existing probe routing. Same pattern as `set_active_probe()`.
- **D-02:** When no tool-specific endstop exists for the selected tool, router falls back to default endstop (built into `ToolAxisEndstop.set_active_tool()`).

### Validation
- **D-03:** `_validate_axis_endstop_coverage()` runs at `klippy:connect` — all config is parsed by then.
- **D-04:** Missing tool definitions raise `printer.config_error` with a clear message listing which tools are missing.
- **D-05:** Validation only runs if the virtual chip was created (at least one tool defined an endstop).

### the agent's Discretion
- Validation placement: In `_handle_connect()` alongside existing initialization logic
- Error message format: Consistent with existing Klipper config error patterns

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements
- `.planning/ROADMAP.md` §Phase 2 — Full phase description with success criteria and tasks
- `.planning/REQUIREMENTS.md` — TOOL-01, TOOL-02, VALID-01, VALID-02, VALID-03

### Existing Code (Pattern Reference)
- `klipper/extras/tool_axis_endstop.py` — Core module from Phase 1
- `klipper/extras/tool_probe_endstop.py` — Z probe routing pattern for comparison
- `klipper/extras/toolchanger.py` — Integration target

### Implementation Plan
- `.opencode/plans/per-tool-axis-endstop.md` — Full code design including toolchanger.py patches

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ToolAxisEndstop.set_active_tool()` — already implemented, handles routing + fallback
- `ToolAxisEndstop.has_endstop()` — already implemented, used for validation
- `toolchanger._configure_toolhead_for_tool()` — integration point (already patched at lines 624-629)
- `toolchanger._handle_connect()` — validation entry point (already patched at lines 211-230)

### Established Patterns
- `printer.lookup_object(chip_name, None)` — optional lookup, skips if chip not registered
- `printer.config_error()` — config-time error for validation failures
- Loop over axes ('x', 'y') with same logic — DRY pattern already in place

### Integration Points
- `toolchanger.py:624-629` — X/Y routing in `_configure_toolhead_for_tool()` (already implemented)
- `toolchanger.py:217-230` — `_validate_axis_endstop_coverage()` in `_handle_connect()` (already implemented)
- `toolchanger.py:215` — validation called at connect time

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the ROADMAP success criteria. The implementation plan provides full code.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 2-Toolchanger Integration + Validation*
*Context gathered: 2026-06-29*
