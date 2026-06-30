---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 0
status: Awaiting next milestone
last_updated: "2026-06-30T04:58:53.940Z"
last_activity: 2026-06-30
last_activity_desc: Milestone v1.0 completed and archived
progress:
  total_phases: 3
  completed_phases: 3
  total_plans: 3
  completed_plans: 3
  percent: 100
---

# STATE.md — Per-Tool X/Y Endstop Routing

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-29)

**Core value:** Any tool can home X (and Y) independently — the firmware dynamically routes endstop queries to the selected toolhead's physical endstop pin.
**Current focus:** Phase 1 — Core module `tool_axis_endstop.py`

## Current State

### Completed

- Codebase mapping: `.planning/codebase/` (ARCHITECTURE, CONCERNS, CONVENTIONS, STACK, etc.)
- Debug artifact: `tool-probe-z-offset-not-applied.md` (resolved)
- PROJECT.md: written with requirements, context, constraints, key decisions
- REQUIREMENTS.md: 15 v1 requirements scoped across X/Y routing, tool change, validation, compatibility
- ROADMAP.md: 3 phases mapped to all requirements
- Implementation plan: `.opencode/plans/per-tool-axis-endstop.md` (detailed code design)

### In Progress

- GSD planning docs backfill: PROJECT.md ✓, REQUIREMENTS.md ✓, ROADMAP.md ✓
- Phase 1: Core module `tool_axis_endstop.py` — not yet started

### Blocked

- None

## Key Decisions Log

| Date | Decision | Details |
|------|----------|---------|
| 2026-06-29 | Virtual pin chip pattern | Use `setup_pin` returning `self` — same as `HommingViaProbeHelper` for Z probes |
| 2026-06-29 | Per-tool config sections | `[tool_axis_endstop Tn]` with `x_pin`/`y_pin`, not global defaults |
| 2026-06-29 | Separate probe/endstop | Probe and X endstop use separate `MCU_endstop` instances via `allow_multi_use_pin` |
| 2026-06-29 | X + Y routing | Both axes supported by same code, Y optional |
| 2026-06-29 | Validation at `klippy:connect` | Catches missing tool definitions before runtime |

## Next Steps

1. Write `tool_axis_endstop.py` — `ToolAxisEndstop` class + both config loaders
2. Patch `toolchanger.py` — routing + validation
3. Add example configs
4. Compile test + review

## Current Position

Phase: Milestone v1.0 complete
Plan: —
Status: Awaiting next milestone
Last activity: 2026-06-30 — Milestone v1.0 completed and archived

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
