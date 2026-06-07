---
status: resolved
trigger: "After updating Klipper and Klipper Toolchanger, calibrated tool probe Z offsets no longer affect print height; live Z adjustment still works. Investigate whether PR 1 caused the regression."
created: 2026-06-06
updated: 2026-06-07
---

# Symptoms

- Expected: The Z offset saved by the probe calibration macro changes the tool's effective print height.
- Actual: Even a deliberately large configured offset does not change print distance from the bed.
- Errors: None reported.
- Timeline: Observed after updating Klipper and Klipper Toolchanger to their latest versions.
- Reproduction: Calibrate or manually enlarge a tool probe Z offset, then print; height remains unchanged. Live Z adjustment during the print still works.

# Current Focus

- hypothesis: Resolved.
- test: Completed automated compatibility checks and printer-side print-start verification.
- expecting: Tool probe Z offsets affect standalone homing and print height.
- next_action: None.

# Evidence

- timestamp: 2026-06-06
  result: In d6e70aa/2551fa9, ToolProbeEndstop constructs upstream HomingViaProbeHelper with `self.probe_offsets.get_offsets()[2]`.
  implication: ProbeRouter has no active probe during construction, so get_offsets() returns `(0.0, 0.0, 0.0)` and Klipper stores a static zero endstop position. This is a real compatibility defect.
- timestamp: 2026-06-06
  result: Current upstream Klipper identifies probe Z homing by the presence of get_position_endstop, but performs the home using `probe.start_probe_session()` and the returned offset-adjusted `bed_z`.
  implication: The static zero virtual-endstop position is unlikely to directly bypass configured probe offsets on current Klipper.
- timestamp: 2026-06-06
  result: d7afb69 replaces upstream HomingViaProbeHelper with a local helper receiving `lambda: self.get_offsets()[2]`.
  implication: The virtual endstop resolves the active tool probe's configured Z offset at runtime.
- timestamp: 2026-06-06
  result: fork/main points to d6e70aa while the dynamic fix is on tool-probe-latest-klipper-api at d7afb69 and upstream PR 174.
  implication: Updating from fork/main installs the regression; updating from PR 174 installs the fix.
- timestamp: 2026-06-06
  result: PR 173 only changes TOOL_CALIBRATE_PROBE_OFFSET calculation to use raw `test_z`.
  implication: PR 173 changes the calibrated value but does not bypass application of a configured probe Z offset during homing or printing.
- timestamp: 2026-06-06
  result: TOOL_CALIBRATE_PROBE_OFFSET defaults its save target to `[tools_calibrate] probe`, whose default is the synthetic object name `probe`.
  implication: Unless `probe:` or the command's `PROBE=` names the actual `[tool_probe Tn]`, the calibration does not save to the active tool probe section.
- timestamp: 2026-06-06
  result: `[tool_probe Tn] z_offset` and `[tool Tn] gcode_z_offset` have separate application paths.
  implication: Probe z_offset affects probe results and Z homing; gcode_z_offset affects normal print moves through the tool transform.
- timestamp: 2026-06-07
  result: The Trident print-start path ran `TOOL_BED_MESH_CALIBRATE`, whose legacy `SET_KINEMATIC_POSITION` calls discarded the probe-derived Z coordinate and baked an opposing correction into the mesh.
  implication: This config behavior, not the tool-probe API compatibility patch, caused configured probe offsets to disappear only during prints.
- timestamp: 2026-06-07
  result: Trident config commit `5606ef81` replaced legacy post-home and mesh coordinate manipulation with current klipper-toolchanger behavior; the user confirmed the printer now works.
  implication: Printer-side verification confirms the identified root cause and fix.
- timestamp: 2026-06-07
  result: Compatibility commit `2be5487` replaced the custom virtual-endstop helper with upstream Klipper's `HomingViaProbeHelper`, removing 38 lines while retaining active probe-session routing.
  implication: The PR now uses the minimum current Klipper API surface required for virtual Z homing.
- timestamp: 2026-06-07
  result: Validation against upstream Klipper `2fb3d54e2` confirmed `HomingViaProbeHelper`, `SampleAveragingHelper`, and the current `ProbeEndstopWrapper` constructor are present; no removed probe APIs remain referenced.
  implication: The compatibility patch matches the latest available upstream Klipper probe API.
- timestamp: 2026-06-07
  result: `python3 -m compileall -q klipper/extras`, targeted `py_compile`, `git diff --check`, and scripted current-API contract checks all passed.
  implication: Static, syntax, and API compatibility validation passed.
# Eliminated

# Resolution

- root_cause: Current Klipper correctly applied the active tool probe offset during `G28 Z`, but the Trident's legacy `TOOL_BED_MESH_CALIBRATE` macro subsequently replaced the correct Z coordinate using `SET_KINEMATIC_POSITION` values that omitted the probe offset.
- fix: Updated the Trident config to use `ADJUST_Z_AFTER_TOOL_NOZZLE_HOME`, removed legacy post-home G-code offsets, and made `TOOL_BED_MESH_CALIBRATE` a direct pass-through. Simplified the klipper-toolchanger compatibility patch to use upstream `HomingViaProbeHelper`.
- verification: User confirmed correct printer behavior after applying Trident config commit `5606ef81`. Automated validation passed against upstream Klipper `2fb3d54e2`.
- files_changed: `.planning/debug/tool-probe-z-offset-not-applied.md`, `klipper/extras/tool_probe_endstop.py`, and the Trident config files recorded in commit `5606ef81`.
