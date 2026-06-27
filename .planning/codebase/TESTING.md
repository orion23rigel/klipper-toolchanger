# Testing: klipper-toolchanger

**Date:** 2026-06-27

## Testing Status

**No automated test suite found.** The codebase does not include any test files (no `tests/` directory, no `pytest.ini`, no `setup.py` with test configuration).

## Manual Validation Methods

### Static Analysis

The project uses several static validation approaches (referenced in debug artifact):

```bash
python3 -m compileall -q klipper/extras          # Syntax validation
git diff --check                                   # Whitespace/lint check
targeted py_compile checks                         # Module-level compilation
```

### API Compatibility Checks

Against upstream Klipper:
```bash
# Verify Klipper APIs used by the extension still exist in target Klipper version
# (custom scripted checks referenced in debug artifact)
```

### Integration Testing

- **Printer-side verification:** The debug artifact notes "printer-side print-start verification" as the primary validation method
- **Docking tests:** `TEST_TOOL_DOCKING` G-code command for manual dock/undock testing
- **Tool detection verification:** `VERIFY_TOOL_DETECTED` G-code command

## Test Coverage Gaps

| Area | Tests | Notes |
|------|-------|-------|
| Tool change state machine | None | Critical path, relies on printer testing |
| Probe routing | None | Core functionality, relies on physical probe testing |
| Tool detection/debouncing | None | Relies on hardware testing |
| Calibration calculations | None | `PrinterProbeMultiAxis` math is untested |
| Rounded path Bezier math | None | Complex vector math, no test cases |
| Fan switching | None | Relies on printer-side testing |
| Error recovery | None | `process_error()` path untested |
| Temperature management | None | Relies on printer testing |

## Recommended Testing Approach

Given the hardware-dependent nature of this project:

1. **Unit tests for pure math:** `rounded_path.py` vector math, `tools_calibrate.py` offset calculations
2. **Mock-based tests for state machine:** `toolchanger.py` state transitions with mocked Klipper objects
3. **Integration tests:** Require actual Klipper instance (can run in simulation mode)
4. **Hardware testing:** Physical tool change validation on target printer

## CI/CD

No CI configuration found (no `.github/workflows/`, no `tox.ini`, no `Makefile`). The project relies on manual testing before commits.
