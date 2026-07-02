# Security Audit Report

**Project:** klipper-toolchanger (Klipper firmware extensions for multi-tool 3D printers)
**Audit Date:** 2026-07-01
**Auditor:** Automated Security Audit
**Scope:** All source files, shell scripts, and user modules in the repository

---

## Executive Summary

This is a Klipper firmware extension for multi-tool 3D printer toolchangers. The codebase runs within the Klipper firmware process on a Raspberry Pi (or similar SBC) connected to a 3D printer via serial/CAN bus. **This is an embedded, air-gapped device firmware — not a network-facing service.** Most traditional web application security concerns (XSS, CSRF, SQL injection, network attacks) do not apply.

However, several real security concerns exist in the context of embedded device firmware, configuration file handling, and the installation/update pipeline. **1 Critical, 3 High, 5 Medium, 4 Low, and 2 Info findings were identified.**

---

## Findings

### CRITICAL

#### C1: Piping Remote Script to Bash Without Validation

- **Severity:** Critical
- **Location:** `README.md`, line 10
- **Description:** The README instructs users to pipe a remote script directly to bash:
  ```
  wget -O - https://raw.githubusercontent.com/viesturz/klipper-toolchanger/main/install.sh | bash
  ```
  This is a well-known anti-pattern. The script is downloaded and executed in the same pipeline with no checksum verification, no integrity check, and no way to audit the script before execution.

- **Risk:** If the GitHub repository is compromised (supply chain attack), or if a MITM attacker intercepts the `wget` request, a malicious script could execute arbitrary commands on the user's Raspberry Pi with their user privileges. The script runs `sudo systemctl restart klipper`, which requires sudo access and affects the printer's core firmware process.

- **Recommended Fix:**
  1. Download the script first, inspect it, then execute:
     ```bash
     wget -O install.sh https://raw.githubusercontent.com/viesturz/klipper-toolchanger/main/install.sh
     chmod +x install.sh
     # Review the script
     bash install.sh
     ```
  2. Better yet, use the `update_manager` section documented in the README (which uses Klipper's built-in update manager with git repo verification).
  3. Consider signing the install script with GPG and providing the public key for verification.

---

### HIGH

#### H1: `ast.literal_eval()` on Untrusted G-Code Input

- **Severity:** High
- **Location:** `klipper/extras/toolchanger.py`, line 762
- **Description:** The `cmd_SET_TOOL_PARAMETER` command accepts a `VALUE` parameter from g-code and passes it directly to `ast.literal_eval()`:
  ```python
  value = ast.literal_eval(gcmd.get("VALUE"))
  ```
  While `ast.literal_eval()` is safer than `eval()` (it only parses Python literals and will raise `ValueError` on arbitrary code), it is still invoked on user-provided input from the g-code stream.

- **Risk:** A malicious g-code file could send crafted `SET_TOOL_PARAMETER` commands that trigger repeated `ValueError` exceptions, causing g-code execution to abort mid-print. While this won't execute arbitrary code (unlike `eval()`), it can be used as a denial-of-service vector against the print job. An attacker with g-code upload access (e.g., via OctoPrint/Moonraker) could disrupt printing.

- **Recommended Fix:** Add input validation to restrict the accepted value types. Instead of accepting any Python literal, validate against expected types (numbers, strings, lists of numbers). Consider a custom parser:
  ```python
  def safe_parse_value(raw):
      try:
          val = ast.literal_eval(raw)
          if not isinstance(val, (int, float, str, list, dict, bool, type(None))):
              raise ValueError("Unsupported type")
          return val
      except (ValueError, SyntaxError) as e:
          raise gcmd.error(f"Invalid parameter value: {e}")
  ```

---

#### H2: `ast.literal_eval()` on Config File Values

- **Severity:** High
- **Location:** `klipper/extras/toolchanger.py`, lines 927-936 (`get_params_dict()`)
- **Description:** The `get_params_dict()` function parses arbitrary config file values using `ast.literal_eval()`:
  ```python
  def get_params_dict(config):
      result = {}
      for option in config.get_prefix_options('params_'):
          try:
              result[option] = ast.literal_eval(config.get(option))
          except ValueError as e:
              raise config.error(...)
      return result
  ```
  Config files are typically written by the user, but in multi-user environments (shared printers, Mainsail/Octoprint web interfaces), a user with web UI access could inject crafted `params_*` values.

- **Risk:** While `ast.literal_eval()` prevents code execution, malformed config values could cause Klipper to fail to start. In the context of a shared printer, a user with web UI access could cause a denial of service by writing a config that crashes the firmware on restart.

- **Recommended Fix:** Restrict accepted value types to numbers and strings only. Reject complex types (lists, dicts, booleans) unless explicitly needed. Add a whitelist of allowed parameter names.

---

#### H3: Hardcoded Filesystem Path in `save_babies.py`

- **Severity:** High
- **Location:** `usermods/VIN-y/save_baby_steps/save_babies.py`, lines 27-28
- **Description:** The `save_babysteps.py` usermod hardcodes the printer config file path:
  ```python
  home_dir = os.path.expanduser("~")
  printer_config = os.path.join(home_dir, "printer_data/config/printer.cfg")
  ```
  This assumes a specific Klipper installation layout (`~/printer_data/config/printer.cfg`). If the path doesn't exist, the `open()` call will raise a `FileNotFoundError`. If the path exists but the Klipper service user doesn't have write permissions, the file write will fail silently or crash.

- **Risk:** 
  1. **Write access to printer config:** If an attacker can trigger this g-code command, they can modify the Klipper printer configuration file, potentially adding malicious config sections that could affect printer behavior (e.g., modifying temperature limits, enabling unsafe movements).
  2. **Information disclosure:** The code reveals the exact filesystem layout of the Klipper installation.
  3. **Silent failure:** The code has no error handling around the file I/O — if the path is wrong or permissions are insufficient, the g-code command will crash the Klipper process.

- **Recommended Fix:**
  1. Add try/except error handling around the file I/O.
  2. Validate that the target file exists before attempting to write.
  3. Consider using Klipper's `configfile` API instead of direct file access (as done in `tools_calibrate.py` lines 161-162).
  4. Add a configuration option for the config file path rather than hardcoding it.

---

### MEDIUM

#### M1: No Input Validation on Tool Number in `cmd_SELECT_TOOL`

- **Severity:** Medium
- **Location:** `klipper/extras/toolchanger.py`, lines 321-338
- **Description:** The `cmd_SELECT_TOOL` command accepts a tool number `T` from g-code input and passes it directly to `lookup_tool()`. While `lookup_tool()` returns `None` for invalid tool numbers (which triggers an error), there is no range validation on the input before the lookup.

- **Risk:** A malicious g-code file could send extremely large tool numbers (e.g., `T999999999`) as a resource exhaustion attempt. While Python handles large integers gracefully, this could be used to stress the tool lookup logic.

- **Recommended Fix:** Add a reasonable range check on tool numbers (e.g., 0-255) before performing the lookup.

---

#### M2: G-Code Template Injection via `run_gcode()`

- **Severity:** Medium
- **Location:** `klipper/extras/toolchanger.py`, lines 748-757
- **Description:** The `run_gcode()` method executes g-code templates with context variables that include user-controlled data (tool names, positions, etc.):
  ```python
  def run_gcode(self, name, template, extra_context):
      curtime = self.printer.get_reactor().monotonic()
      context = {
          **template.create_template_context(),
          'tool': self.active_tool.get_status(curtime) if self.active_tool else {},
          'toolchanger': self.get_status(curtime),
          **extra_context,
      }
      template.run_gcode_from_command(context)
  ```
  Template context variables (tool names, positions, tool numbers) are interpolated into g-code commands. While Klipper's g-code macro system is not a web browser (no XSS risk), crafted tool names containing special characters could produce malformed g-code.

- **Risk:** A user could configure a tool with a name containing characters that break g-code macro parsing (e.g., quotes, braces), causing g-code execution failures. In a shared printer environment, this could be used to disrupt printing.

- **Recommended Fix:** Sanitize tool names and other context variables before passing them to g-code templates. Validate that tool names contain only safe characters (alphanumeric, underscore, hyphen).

---

#### M3: `configfile.set()` Without Validation in `tools_calibrate.py`

- **Severity:** Medium
- **Location:** `klipper/extras/tools_calibrate.py`, lines 156-162
- **Description:** The `cmd_TOOL_CALIBRATE_SAVE_TOOL_OFFSET` command accepts `SECTION` and `ATTRIBUTE` parameters from g-code and writes them directly to the config file:
  ```python
  section_name = gcmd.get("SECTION")
  param_name = gcmd.get("ATTRIBUTE")
  template = gcmd.get("VALUE", "{x:0.6f}, {y:0.6f}, {z:0.6f}")
  value = template.format(x=self.last_result[0], y=self.last_result[1],
                          z=self.last_result[2])
  configfile = self.printer.lookup_object('configfile')
  configfile.set(section_name, param_name, value)
  ```
  There is no validation on `section_name` or `param_name`. A user could potentially write to arbitrary configuration sections.

- **Risk:** An attacker with g-code access could modify arbitrary configuration sections, potentially enabling unsafe printer behavior (e.g., disabling temperature limits, modifying stepper currents, enabling force_move on axes that should be locked).

- **Recommended Fix:** Validate `section_name` against a whitelist of allowed sections. Validate `param_name` against known safe parameter names. Reject any section/attribute that could affect printer safety.

---

#### M4: No Rate Limiting on Accelerometer Polling

- **Severity:** Medium
- **Location:** `usermods/Contomo/tool_drop_detection/tool_drop_detection.py`, lines 125, 312-333
- **Description:** The `TDD_POLLING_START` command can start continuous polling of ADXL345 accelerometers at configurable frequencies (up to 20 Hz clamped, but the config `polling_rate` can be set up to 3200 Hz internally). There is no rate limiting on how many pollers a user can start simultaneously.

- **Risk:** A user could start polling on all connected accelerometers at maximum frequency, consuming significant I2C bus bandwidth and CPU time. On a resource-constrained Raspberry Pi, this could cause Klipper to become unresponsive, disrupting ongoing prints.

- **Recommended Fix:** 
  1. Cap the maximum number of simultaneous pollers per user command.
  2. Add a global maximum polling frequency across all pollers.
  3. Implement per-user rate limiting if Moonraker authentication is available.

---

#### M5: `os.path.expanduser("~")` Path Traversal via Home Directory

- **Severity:** Medium
- **Location:** `usermods/VIN-y/save_baby_steps/save_babies.py`, line 27
- **Description:** The `save_babysteps.py` usermod resolves `~` to the current user's home directory and constructs a path to `printer_data/config/printer.cfg`. If run as a different user (e.g., via a sudo-invoked g-code command), the path resolution would differ.

- **Risk:** While not a classic path traversal, the hardcoded path assumption means the module could write to an unintended location if the environment changes. Combined with the lack of input validation on the file write (see H3), this creates an unpredictable file modification vector.

- **Recommended Fix:** Use Klipper's config API for config file modifications. If direct file access is required, validate the resolved path against an expected directory.

---

### LOW

#### L1: Information Disclosure in Error Messages

- **Severity:** Low
- **Location:** `klipper/extras/toolchanger.py`, lines 396-397, 460-461
- **Description:** Error messages expose internal state information:
  ```python
  raise gcmd.error(
      "Cannot enter docking mode, toolchanger status is %s, reason: %s" % (self.status, self.error_message))
  ```
  These messages reveal the internal state machine status and error messages to the g-code client.

- **Risk:** In a shared printer environment, these messages could reveal internal implementation details about the toolchanger's state machine, which could be used to craft attacks against the tool change process.

- **Recommended Fix:** Keep error messages concise and avoid exposing internal state machine names. Use generic error descriptions for external-facing messages.

---

#### L2: Logging of Internal State

- **Severity:** Low
- **Location:** `klipper/extras/toolchanger.py`, lines 71, 82, 84, 86, 89; `klipper/extras/tools_calibrate.py`, lines 387, 391
- **Description:** The codebase uses Python's `logging` module to output internal state information (tool missing events, probe axis details). While these are Klipper-internal logs and not network-facing, they could be visible in log files accessible via Moonraker's log endpoint.

- **Risk:** Log files could contain sensitive information about the printer's configuration (tool names, positions, offsets) that could be useful to an attacker with filesystem access.

- **Recommended Fix:** Use `logging.debug()` for verbose internal state. Use `logging.info()` for significant events. Ensure log files are not world-readable.

---

#### L3: No Authentication on G-Code Commands

- **Severity:** Low
- **Location:** All g-code command registrations across all modules
- **Description:** All g-code commands are registered without any authentication check. In a networked Klipper setup (via Moonraker/OctoPrint), any user with API access can execute these commands.

- **Risk:** Any user with API access to the printer can execute tool changes, modify tool parameters, start calibration routines, and other operations that could damage the printer or produce defective prints.

- **Recommended Fix:** Rely on Moonraker's authentication system (if available) to restrict command access. Document which commands require elevated privileges.

---

#### L4: Symlink-Based Installation Could Be Abused

- **Severity:** Low
- **Location:** `install.sh`, line 44
- **Description:** The install script creates symlinks from the extension directory to Klipper's extras directory:
  ```bash
  for file in "${INSTALL_PATH}"/klipper/extras/*.py; do ln -sfn "${file}" "${KLIPPER_PATH}/klippy/extras/"; done
  ```
  The `-f` flag forces overwriting existing symlinks. If an attacker can write to the `INSTALL_PATH` directory, they could replace the Python files, and the next install run would symlink the malicious versions.

- **Risk:** If the repository is cloned to a world-writable directory, or if the user's home directory is compromised, an attacker could inject malicious code that gets symlinked into Klipper's extension directory.

- **Recommended Fix:** Verify file integrity after symlink creation. Consider using `cp` instead of `ln -s` for a copy-based install. Add checksum verification.

---

### INFO

#### I1: No Network Stack — No Network Attack Surface

- **Severity:** Info
- **Location:** Entire codebase
- **Description:** The codebase does not contain any network code (no sockets, HTTP servers, WebSocket handlers, or network protocols). All communication is via g-code commands through Klipper's internal command system.

- **Assessment:** This is an embedded firmware extension. The attack surface is limited to:
  - G-code files (uploaded via Moonraker/OctoPrint)
  - Configuration files (written via web UI)
  - The install/update script

- **Recommendation:** No network security measures are needed. Focus on input validation for g-code and config file handling.

---

#### I2: No Cryptographic Operations

- **Severity:** Info
- **Location:** Entire codebase
- **Description:** The codebase does not perform any cryptographic operations (no encryption, hashing, signing, or certificate handling).

- **Assessment:** No cryptographic vulnerabilities are possible. The install script uses HTTPS for downloads, which is the appropriate security mechanism for that context (see C1).

- **Recommendation:** No changes needed.

---

## Dependency Analysis

The codebase has minimal external dependencies:

| Dependency | Used In | Risk |
|------------|---------|------|
| `numpy` | `rounded_path.py` | Low — only used for array operations in path computation |
| `math` | `rounded_path.py` | None — standard library |
| `ast` | `toolchanger.py` | Medium — used on user input (see H1, H2) |
| `os` | `save_babies.py` | High — hardcoded path (see H3) |
| `logging` | Multiple files | Low — internal logging |
| `bisect` | `toolchanger.py` | None — standard library |
| `stepper`, `force_move`, `probe`, `fan`, `pins`, `homing`, `homing`, `motion_queuing` | Various | None — Klipper core modules |

**No pip packages, no external Python libraries.** The only third-party dependency is `numpy` (used in `rounded_path.py`).

---

## Configuration Security

### Secrets and Credentials

- **No secrets, API keys, passwords, or tokens found in the codebase.**
- Example configuration files contain hardware pin designators (e.g., `et0:PB6`, `et0:PD0`) which are publicly documented GPIO pins — not secrets.
- CAN bus UUIDs in example configs (e.g., `bafd9b10a1b4`) are hardware identifiers, not secrets.

### File Permissions

- The `.gitignore` only excludes `__pycache__/`. No `.env` files, no secret files.
- The install script requires non-root execution and checks for Klipper service presence.

---

## Summary Table

| ID | Severity | Category | Status |
|----|----------|----------|--------|
| C1 | Critical | Supply Chain — piped remote script to bash | Needs Fix |
| H1 | High | Input Validation — `ast.literal_eval()` on g-code | Needs Fix |
| H2 | High | Input Validation — `ast.literal_eval()` on config | Needs Fix |
| H3 | High | Filesystem — hardcoded path, no error handling | Needs Fix |
| M1 | Medium | Input Validation — no tool number range check | Consider Fix |
| M2 | Medium | Injection — g-code template context injection | Consider Fix |
| M3 | Medium | Config Write — unrestricted `configfile.set()` | Needs Fix |
| M4 | Medium | Resource Exhaustion — unlimited polling | Consider Fix |
| M5 | Medium | Path Traversal — `expanduser("~")` assumption | Needs Fix |
| L1 | Low | Information Disclosure — verbose error messages | Consider Fix |
| L2 | Low | Information Disclosure — logging internal state | Consider Fix |
| L3 | Low | Authentication — no g-code command auth | Consider Fix |
| L4 | Low | Installation — symlink-based install | Consider Fix |
| I1 | Info | Assessment — no network stack | No Fix Needed |
| I2 | Info | Assessment — no crypto operations | No Fix Needed |

---

## Recommendations Priority

1. **Immediate (Critical):** Update README to remove the `wget | bash` installation pattern. Users should use the documented `update_manager` approach or download+inspect before running.
2. **High Priority:** Add input validation to `SET_TOOL_PARAMETER` and `TOOL_CALIBRATE_SAVE_TOOL_OFFSET` commands. Fix the `save_babies.py` usermod to use Klipper's config API.
3. **Medium Priority:** Add tool number range validation, sanitize template context variables, limit concurrent polling.
4. **Low Priority:** Review error message verbosity, audit logging levels, document command privilege requirements.

---

## Conclusion

This codebase is Klipper firmware firmware for 3D printers — an embedded, air-gapped system. The primary attack surface is through g-code files and configuration files, typically delivered via web UIs like Mainsail or OctoPrint. The most critical finding is the installation script pattern in the README, which exposes users to supply chain attacks. The code itself is reasonably well-structured for its domain, with no network-facing code, no cryptographic operations, and no secrets stored. The main remaining concerns are input validation on g-code parameters and the hardcoded filesystem path in the `save_babies.py` usermod.
