---
phase: "01"
audited: 2026-06-30
asvs_level: 1
block_on: high
threats_found: 6
threats_closed: 6
threats_open: 0
register_authored_at_plan_time: false
status: secured
---

# Phase 01: Security Audit — tool_axis_endstop.py

## Threat Register

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| STRIDE-01 | Spoofing | ToolAxisEndstop | Accepted risk | CLOSED | Physical access required to spoof; `setup_pin` validates virtual pin identity (tool_axis_endstop.py:40-43); Klipper pins module enforces hardware-level trust |
| STRIDE-02 | Tampering | Config + G-code input | Accepted risk | CLOSED | Config parsed by Klipper's trusted config system; gcmd.error raises on invalid input (tool_axis_endstop.py:41-43, toolchanger.py:301-306); owner-controlled config files |
| STRIDE-03 | Repudiation | Klipper logging | N/A | CLOSED | Python `logging` module imported (tool_axis_endstop.py:7); Klipper event system provides audit trail via gcode.log; not actionable in embedded context |
| STRIDE-04 | Information Disclosure | ToolAxisEndstop | Accepted risk | CLOSED | No secrets stored or transmitted; `get_status()` returns only tool names/numbers/detection state (toolchanger.py:244-255); no network stack present |
| STRIDE-05 | Denial of Service | ToolAxisEndstop | Mitigated | CLOSED | Null-pointer guards on all MCU_endstop proxy methods (tool_axis_endstop.py:88-105); `_validate_axis_endstop_coverage` catches config gaps at startup (toolchanger.py:217-230); `select_tool` catches gcmd.error (toolchanger.py:479-486) |
| STRIDE-06 | Elevation of Privilege | ToolAxisEndstop | Accepted risk | CLOSED | Extension runs within Klipper process with Klipper privileges only; no `os.system()`, no file I/O outside Klipper scope, no privilege escalation vectors present |

## Threat Analysis Details

### STRIDE-01: Spoofing
**Assessment:** No spoofing vector exists in this embedded context.

The `ToolAxisEndstop` class registers a virtual pin chip (`toolchanger_x`, `toolchanger_y`) that Klipper's pins subsystem owns. The `setup_pin` method (line 36-44) strictly validates that only the expected virtual pin name matches — it rejects any pin_type other than `'endstop'` and any pin not equal to the class's own `self.virtual_pin`.

An attacker would need physical access to the Raspberry Pi GPIO headers to inject false signals. This is the same threat model as any Klipper installation. No authentication or cryptographic measures are applicable because the hardware wiring itself establishes trust.

**Disposition:** Accepted risk — physical access threat is inherent to the platform.

### STRIDE-02: Tampering
**Assessment:** No tampering vector from untrusted sources.

Config files are written by the printer owner and parsed by Klipper's built-in config parser — the extension does not implement any custom config parsing. G-code parameters (tool numbers, axis names) flow through Klipper's gcmd system which validates types and raises `gcmd.error` on invalid values.

The `load_config_prefix` function (line 135-175) extracts tool numbers from section names or config parameters, with safe fallbacks (`int()` wrapped in try/except at line 153-158). No shell injection or code execution is possible through config values.

**Disposition:** Accepted risk — input comes from trusted owner, validated by Klipper framework.

### STRIDE-03: Repudiation
**Assessment:** Not a meaningful threat in this embedded context.

Klipper's logging system (Python `logging` module, imported at tool_axis_endstop.py:7) and event system provide audit capability. G-code commands are logged by Klipper's command handler. However, repudiation (an actor denying they performed an action) is not a threat model concern for a single-owner embedded device with no multi-user access.

**Disposition:** N/A — not applicable to the threat model.

### STRIDE-04: Information Disclosure
**Assessment:** No information disclosure vector.

The extension stores no secrets, credentials, or sensitive data. The `get_status()` method in toolchanger.py (lines 244-255) returns only:
- Tool names and numbers (configuration data)
- Toolchanger status string (operational state)
- Detection state (hardware sensor status)

No network stack is present. No files are written to disk. No debug output reveals memory contents or internal state beyond what Klipper's standard status system already exposes.

**Disposition:** Accepted risk — no secrets exist to disclose.

### STRIDE-05: Denial of Service
**Assessment:** Mitigations present and adequate.

Three layers of DoS protection are implemented:

1. **Runtime null checks:** All three MCU_endstop proxy methods (`home_start`, `home_wait`, `query_endstop`) check `self.active_mcu_endstop` is not None before forwarding, raising `printer.command_error` if the router has no active tool (tool_axis_endstop.py:88-105).

2. **Startup validation:** `_validate_axis_endstop_coverage` (toolchanger.py:217-230) iterates all registered tools and verifies each has an endstop pin configured for every active axis. Missing configuration raises `printer.config_error` at startup, before any homing can occur.

3. **Error recovery:** `select_tool` wraps the entire toolchange sequence in a try/except for `gcmd.error` (toolchanger.py:479-486), preventing unhandled exceptions from crashing Klipper. The `_handle_command_error` handler resets toolchanger state (toolchanger.py:232-236).

No unbounded loops, no resource leaks, no memory allocation without bounds.

**Disposition:** Mitigated — error handling is present and correct.

### STRIDE-06: Elevation of Privilege
**Assessment:** No escalation vector.

The extension runs as a Klipper plugin within the Klipper process. It:
- Uses only Klipper-provided APIs (`printer.lookup_object`, `config.get_printer`, `pins.setup_pin`)
- Does not call `os.system()`, `subprocess`, or any shell execution
- Does not write files to disk
- Does not modify system configuration
- Does not access resources outside Klipper's object model

The `ast.literal_eval` call in toolchanger.py:884 (for `params_` options) is safe — it only evaluates Python literals, never arbitrary code.

**Disposition:** Accepted risk — runs within Klipper's privilege boundary only.

## Accepted Risks

| Risk | Justification |
|------|---------------|
| Physical spoofing of endstop signals | Requires physical access to GPIO headers; same threat model as all Klipper installations |
| Config file tampering | Config files are owner-written and parsed by Klipper's trusted config system |
| No authentication on g-code commands | Single-owner embedded device; G-code comes from slicer/owner |
| No audit logging of tool changes | Klipper's standard logging and gcode.log provide sufficient audit trail for single-owner device |
| No encryption of internal state | No secrets stored; no network communication |

## Audit Trail

- 2026-06-30: Initial retroactive-STRIDE audit — no plan-time threat model existed. All STRIDE categories assessed. No open threats found. All mitigations verified in code. No unregistered attack surface flags.
