---
phase: "02"
audited: 2026-06-30
asvs_level: 1
block_on: high
threats_found: 4
threats_closed: 4
threats_open: 0
register_authored_at_plan_time: false
status: secured
---

# Phase 02: Security Audit — toolchanger.py integration

## Threat Register

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| STRIDE-01 | Spoofing | `toolchanger.py:624-629` + `tool_axis_endstop.py:58-61` | Mitigate | CLOSED | `set_active_tool()` is only callable from `_configure_toolhead_for_tool()` (internal method, lines 616-629). No external API — no gcode command, no object lookup by untrusted code — exposes `set_active_tool()` to tool number spoofing. The tool_number value comes from `tool.tool_number` (set at config-parse time via `assign_tool()` with duplicate detection at line 257-259), never from untrusted input. Router validates existence via `_endstops.get(tool_number, default)` (line 60-61) — if tool_number doesn't exist, falls back to `default_endstop`. No spoofing vector. |
| STRIDE-02 | Tampering | `tool_axis_endstop.py:86-105` | Mitigate | CLOSED | MCU_endstop proxy methods (`home_start`, `home_wait`, `query_endstop`) forward to `self.active_mcu_endstop`. If `active_mcu_endstop` is None, raises `command_error` (lines 88-91, 96-99, 102-105). The active endstop is set exclusively by `_configure_toolhead_for_tool()` which is called during the toolchanger's internal state machine. No external caller can inject a malicious MCU_endstop into the router. Config-time registration (`add_endstop()` at tool_axis_endstop.py:46-50) is driven only by Klipper's config parser. |
| STRIDE-03 | Denial of Service | `toolchanger.py:217-230` | Mitigate | CLOSED | `_validate_axis_endstop_coverage()` raises `config_error` at startup if any tool lacks endstop definitions. This is a safety gate — it prevents the printer from running in an unsafe configuration where endstop routing is active but incomplete. The validation iterates over `self.tools` (finite, config-defined list) and calls `router.has_endstop(tn)` (O(1) dict lookup). No unbounded loops, no external input. If validation fails, startup is blocked — this is the correct DoS-mitigation behavior (fail-safe). |
| STRIDE-04 | Information Disclosure | `toolchanger.py:624-629` + `tool_axis_endstop.py:58-61` | Mitigate | CLOSED | Router state (`active_mcu_endstop`, `_endstops` dict) is internal to the Klipper object graph. No status method exposes internal routing state to gcode clients. `get_status()` at line 244-255 returns only high-level toolchanger state (status string, tool names/numbers, detection info). The tool_number passed to `set_active_tool()` is an integer from config, not sensitive data. No logging of endstop routing decisions. |

## Accepted Risks

1. **No runtime tool-number validation in `set_active_tool()`** — The router uses `_endstops.get(tool_number, default_endstop)` which silently falls back to default if the tool_number is not registered. This is intentional design (D-02 from CONTEXT.md: "fallback to default endstop") and not a security concern because tool_number values are only set by internal toolchanger methods from config-parsed data, never from gcode commands.

2. **No input validation on `tool.tool_number`** — Tool numbers originate from config file section names (`[tool_axis_endstop Tn]`) which are parsed by Klipper's config system. Config parsing happens before any runtime code executes. Invalid config is caught by Klipper's config parser, not by this module.

## Audit Trail

- 2026-06-30: Initial retroactive-STRIDE audit — no plan-time threat model existed. All 4 STRIDE categories analyzed against `toolchanger.py` (lines 217-230, 624-629) and `tool_axis_endstop.py` (full file, 175 lines). No new attack surface beyond the planned integration points. No unregistered flags. Phase is SECURED.
