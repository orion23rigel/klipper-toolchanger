---
phase: "03"
audited: 2026-06-30
asvs_level: 1
block_on: high
threats_found: 0
threats_closed: 0
threats_open: 0
register_authored_at_plan_time: false
status: secured
---

# Phase 03: Security Audit — Example configs

## Threat Register

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| STRIDE-001 | Spoofing | Config examples | Accept | CLOSED | Examples use public Klipper pin naming conventions (e.g. `tool_0:PB8`, `toolchanger_x:x_virtual_endstop`). No credentials, tokens, or secrets. Misleading config would cause a print failure, not a security breach. |
| STRIDE-002 | Tampering | Config files | Accept | CLOSED | Config files are authored by the printer owner on a local machine. They are not downloaded from untrusted sources and are not transmitted over a network. |
| STRIDE-003 | Repudiation | Example docs | N/A | CLOSED | Example configs have no user-facing actions that require audit logging. No claims of authorship or non-repudiation needed. |
| STRIDE-004 | Information Disclosure | Config examples | Accept | CLOSED | Pin names (e.g. `PB8`, `PB6`) are hardware-specific GPIO designators. These are publicly documented in the printer's hardware manual and are not secrets. No passwords, API keys, or sensitive data present. |
| STRIDE-005 | Denial of Service | Config examples | Accept | CLOSED | Examples are reference configs. A user copying them verbatim into their printer.cfg would produce a working Klipper config. There is no code execution path triggered by these files alone. |
| STRIDE-006 | Elevation of Privilege | Config examples | Accept | CLOSED | Klipper config files operate within the printer firmware's single privilege domain. Config syntax errors cause startup failures, not privilege escalation. No sudo, shell access, or system-level commands are present. |

## Accepted Risks

- **AR-001: Config misuse causing hardware damage.** A user who misconfigures pin references (e.g. pointing a tool endstop to an unused GPIO) may cause a print failure or, in rare cases, a crash. This is a safety/reliability concern, not a security vulnerability. The examples explicitly document the correct 3-step migration path to minimize this risk.

- **AR-002: No plan-time threat model.** Phase 03 was created during implementation without a pre-existing threat model. This audit retroactively confirms that the phase scope (example config files only) presents no exploitable attack surface.

## Audit Trail

- 2026-06-30: Initial retroactive-STRIDE audit — no plan-time threat model existed. Phase contains only example config files (YAML-like Klipper configuration), no Python code changes, and no network attack surface. All STRIDE categories evaluated; no threats found.
