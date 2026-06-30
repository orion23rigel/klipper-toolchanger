# Phase 3: Examples + Documentation - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Provide example configs showing the minimal migration path and document the feature. Creates example configs in `examples/axis_endstop/` demonstrating the full setup for both X-only and X+Y configurations.

</domain>

<decisions>
## Implementation Decisions

### Example Configs
- **D-01:** Three config files: `printer.cfg` (stepper_x endstop_pin), `toolhead_n.cfg` (per-tool sections), `homing.cfg` (homing with per-tool X endstops)
- **D-02:** Examples show both X-only and X+Y configurations
- **D-03:** Migration guide documents the 3 config changes needed

### the agent's Discretion
- Example pin references: Use realistic pin names matching the user's hardware (EBB36 CAN, PB8)
- Config structure: Match the Laurion3D Trident project structure

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements
- `.planning/ROADMAP.md` §Phase 3 — Full phase description with success criteria and tasks
- `.planning/REQUIREMENTS.md` — COMPAT-02 (implicit via examples)

### Existing Code
- `klipper/extras/tool_axis_endstop.py` — Phase 1 implementation
- `klipper/extras/toolchanger.py` — Phase 2 integration
- `.opencode/plans/per-tool-axis-endstop.md` — Implementation plan with example config snippets

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Example config snippets already in `.opencode/plans/per-tool-axis-endstop.md`
- User's Laurion3D Trident hardware context from PROJECT.md

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the ROADMAP success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 3-Examples + Documentation*
*Context gathered: 2026-06-29*
