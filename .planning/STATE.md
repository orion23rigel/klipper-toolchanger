# STATE.md — Per-Tool X/Y Endstop Routing

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-30)

**Core value:** Any tool can home X (and Y) independently — the firmware dynamically routes endstop queries to the selected toolhead's physical endstop pin.
**Current focus:** v1.0 shipped — planning next milestone

## Current State

### Completed
- Codebase mapping: `.planning/codebase/` (ARCHITECTURE, CONCERNS, CONVENTIONS, STACK, etc.)
- PROJECT.md: written with requirements, context, constraints, key decisions
- REQUIREMENTS.md: 15 v1 requirements scoped across X/Y routing, tool change, validation, compatibility
- ROADMAP.md: 3 phases mapped to all requirements
- Phase 1: Core Module — `tool_axis_endstop.py` (175 lines) — COMPLETED
- Phase 2: Toolchanger Integration + Validation — COMPLETED
- Phase 3: Examples + Documentation — COMPLETED
- Milestone v1.0: SHIPPED (2026-06-30)
- Audit: PASSED (15/15 requirements, 9/9 integration points, 3/3 E2E flows)

### In Progress
- None

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
| 2026-06-30 | Milestone v1.0 shipped | All 15 requirements satisfied, 3/3 phases complete |

## Next Steps

1. Start next milestone: `/gsd-new-milestone`
