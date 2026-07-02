# Requirements: Per-Tool X/Y Endstop Routing

**Defined:** 2026-06-29
**Core Value:** Any tool can home X (and Y) independently — the firmware dynamically routes endstop queries to the selected toolhead's physical endstop pin.

## v1 Requirements

### X Endstop Routing

- [ ] **XEND-01**: `[tool_axis_endstop Tn]` config section accepts `x_pin` parameter defining the X endstop pin for each toolhead
- [ ] **XEND-02**: `toolchanger_x` virtual pin chip registers with Klipper's pins system and provides `x_virtual_endstop`
- [ ] **XEND-03**: `[stepper_x] endstop_pin` set to `toolchanger_x:x_virtual_endstop` delegates X homing to the router
- [ ] **XEND-04**: Router routes `home_start`, `home_wait`, `query_endstop` to the active tool's physical MCU_endstop
- [ ] **XEND-05**: Router's `add_stepper()` forwards steppers to all registered endstops (CoreXY cross-wiring support)

### Y Endstop Routing

- [ ] **YEND-01**: Same pattern as X endstop routing via `toolchanger_y` chip and `[tool_axis_endstop Tn] y_pin`
- [ ] **YEND-02**: Optional — if no `[tool_axis_endstop Tn]` defines `y_pin`, Y endstop stays global as configured in `[stepper_y]`

### Tool Change Integration

- [ ] **TOOL-01**: `toolchanger._configure_toolhead_for_tool()` calls `router.set_active_tool(tool.tool_number)` for both X and Y routers
- [ ] **TOOL-02**: When no tool-specific endstop exists for the selected tool, router falls back to default endstop

### Validation

- [ ] **VALID-01**: At `klippy:connect`, `toolchanger._validate_axis_endstop_coverage()` checks that every registered tool has its X/Y endstop registered
- [ ] **VALID-02**: Missing tool definitions raise `printer.config_error` with a clear message listing which tools are missing
- [ ] **VALID-03**: Validation only runs if the virtual chip was created (i.e., at least one tool defined an endstop)

### Backward Compatibility

- [ ] **COMPAT-01**: If no `[tool_axis_endstop]` sections exist, the virtual chip is never created — no behavior change
- [ ] **COMPAT-02**: Existing `[tool_probe Tn]` / `[tool_probe_endstop]` for Z probing continues to work unchanged
- [ ] **COMPAT-03**: Shared pin support — `allow_multi_use_pin` allows probe pin and X endstop pin to share the same physical pin

## v2 Requirements

### Position Endstop Override

- [ ] **XEND-02**: Per-tool `x_position_endstop` in `[tool_axis_endstop Tn]` overrides the global value at tool change time

### Additional Axis Support

- [ ] **YEND-03**: Per-tool `y_position_endstop` support (same as X)

### Sensorless Endstop Routing

- [ ] **XEND-03**: Sensorless homing routing via TMC DIAG pins (requires TMC driver integration)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Per-tool position_endstop | Not needed now; architecture supports it for future |
| Sensorless homing routing | DIAG pins are on mainboard, not toolhead; stays global |
| Multi-toolhead IDEX support | Different architecture; this is for single-gantry toolchangers |
| Automated config migration | User makes 3 config changes manually — minimal enough |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| XEND-01 | Phase 1 | Pending |
| XEND-02 | Phase 1 | Pending |
| XEND-03 | Phase 1 | Pending |
| XEND-04 | Phase 1 | Pending |
| XEND-05 | Phase 1 | Pending |
| YEND-01 | Phase 1 | Pending |
| YEND-02 | Phase 1 | Pending |
| TOOL-01 | Phase 2 | Pending |
| TOOL-02 | Phase 2 | Pending |
| VALID-01 | Phase 2 | Pending |
| VALID-02 | Phase 2 | Pending |
| VALID-03 | Phase 2 | Pending |
| COMPAT-01 | Phase 1 | Pending |
| COMPAT-02 | Phase 1 | Pending |
| COMPAT-03 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-29*
