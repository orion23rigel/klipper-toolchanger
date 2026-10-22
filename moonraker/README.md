# Moonraker toolchange destination processor (experimental)

This optional component uses Moonraker's file-manager G-code processor registration API; it does not monkey-patch `METADATA_SCRIPT` or modify Moonraker core. It is disabled by default.

## Behavior

When enabled, this optional Moonraker file-manager G-code processor examines uploaded files during metadata/preprint processing. Its bounded scan looks around slicer toolchange markers and may repair a narrowly proven out-of-bounds XY destination before the file is printed. It is an upload-time mitigation, not a substitute for Klipper's runtime destination guard and not a general G-code verifier.

- Scans toolchange markers carrying `X`, `Y`, and `Z`; for `_SLICER_CHANGE`, it tolerates one following `Tn` only when `n` matches `NEXT_EXTRUDER`.
- Leaves valid destinations and transitions with XY travel before the layer-Z move byte-for-byte unchanged.
- Rewrites only an out-of-envelope toolchange destination when bounded lookahead proves an absolute Z descent followed by a pure absolute XY travel, before extrusion or unsupported/state-changing motion. The explicit subsequent XY target must itself lie inside the configured envelope; that target is substituted into the toolchange marker.
- Leaves relative, combined-axis, extrusion-before-XY, missing-target, out-of-range replacement, and otherwise ambiguous transitions unchanged. It reports unresolved cases diagnostically; it does not reject the upload or prevent a print.
- Applies proven edits atomically. If a file contains both resolvable and ambiguous transitions, proven repairs can still be applied while the ambiguous ones remain unchanged.

By default, bounds are derived when Klipper reports ready. Moonraker queries Klipper's active `configfile.config` for `[stepper_x]`/`[stepper_y]` limits and every `[tool Tn]` section, applying each tool's `gcode_x_offset`/`gcode_y_offset` or its parent toolchanger's defaults. It also incorporates the current XY `gcode_move.homing_origin`. The component intersects the per-tool slicer-space intervals so every configured tool fits the envelope. Auto bounds are refreshed on each Klipper-ready event; runtime changes to offsets or homing origin are not tracked. If such changes are used, supply a verified manual envelope or leave processing disabled.

Klipper's runtime safe-bounds guard remains the final check. The preprint scan does not validate later slicer moves or guarantee safe behavior after a substituted or skipped destination. Use this as defense-in-depth, not as a safety interlock.

## Compatibility and installation

The G-code processor registration method is on Moonraker's metadata store, exposed as `file_manager.gcode_metadata.register_gcode_processor()`—not directly on the `FileManager` object. This path is present in the official `Arksine/moonraker` v0.11 source. The component and installer check for this exact API path; a missing method here indicates a different/incomplete runtime checkout or API layout.

Install the module and register it with Moonraker by running the toolchanger installer from the updated checkout:

```sh
bash ~/klipper-toolchanger/install.sh
```

With the standard source checkout/config paths, the installer links the component into `~/moonraker/moonraker/components`, backs up `~/printer_data/config/moonraker.conf`, and adds `[toolchanger_gcode_processor]` with `enabled: False` if that section does not already exist. Set `MOONRAKER_PATH`, `MOONRAKER_CONFIG`, or `MOONRAKER_SERVICE` in the environment when the printer uses different paths or service name. The installer restarts Moonraker when the source checkout is detected.

The processor intentionally remains disabled until you verify the automatically derived safe XY envelope and change `enabled` to `True`. On Klipper-ready, the Moonraker log reports the computed bounds. If deriving bounds fails (missing axes/tools/origin, invalid values, or no shared envelope), the processor remains unregistered and logs an error; this does not prevent printing. Alternatively, set all four `x_min`, `x_max`, `y_min`, and `y_max` values to use a manual slicer-space envelope. Partial manual overrides are rejected.

```ini
[toolchanger_gcode_processor]
enabled: False
timeout: 120
# Optional: set all four values to override automatic derivation.
# x_min: ...
# x_max: ...
# y_min: ...
# y_max: ...
```

The derived envelope uses the XY homing origin at the time Klipper reports ready. If any macro changes XY homing origin or tool offsets later, automatic bounds become stale; use a manually verified envelope or keep the processor disabled. Even with valid bounds, ambiguous scan transitions are left unchanged and do not block a print.

## Local tests

Run from the repository root:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q moonraker/test_toolchanger_gcode_processor.py
```

Tests exercise safe XY-before-Z pass-through, a narrowly repairable Z-before-XY case, and unchanged ambiguous/out-of-bounds cases. They do not replace validation against the exact printer configuration or a controlled hardware test.
