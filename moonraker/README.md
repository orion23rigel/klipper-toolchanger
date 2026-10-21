# Moonraker toolchange destination processor (experimental)

This optional component uses Moonraker's file-manager G-code processor registration API; it does not monkey-patch `METADATA_SCRIPT` or modify Moonraker core. It is disabled by default.

## Behavior

When enabled, this optional Moonraker file-manager G-code processor examines uploaded files during metadata/preprint processing. Its bounded scan looks around slicer toolchange markers and may repair a narrowly proven out-of-bounds XY destination before the file is printed. It is an upload-time mitigation, not a substitute for Klipper's runtime destination guard and not a general G-code verifier.

- Scans toolchange markers carrying `X`, `Y`, and `Z`; for `_SLICER_CHANGE`, it tolerates one following `Tn` only when `n` matches `NEXT_EXTRUDER`.
- Leaves valid destinations and transitions with XY travel before the layer-Z move byte-for-byte unchanged.
- Rewrites only an out-of-envelope toolchange destination when bounded lookahead proves an absolute Z descent followed by a pure absolute XY travel, before extrusion or unsupported/state-changing motion. The explicit subsequent XY target must itself lie inside the configured envelope; that target is substituted into the toolchange marker.
- Leaves relative, combined-axis, extrusion-before-XY, missing-target, out-of-range replacement, and otherwise ambiguous transitions unchanged. It reports unresolved cases diagnostically; it does not reject the upload or prevent a print.
- Applies proven edits atomically. If a file contains both resolvable and ambiguous transitions, proven repairs can still be applied while the ambiguous ones remain unchanged.

The configured bounds must be a conservative safe XY envelope in the coordinate frame used by the slicer, accounting for tool offsets and homing-origin shifts. Klipper's runtime safe-bounds guard remains the final check. After a toolchange, coordinate state and any skipped/substituted destination can affect subsequent motion; this processor does not validate later slicer moves or guarantee safe behavior after the substitution. If the runtime guard skips a destination, this scan cannot establish that subsequent moves or Z descents are safe. Use conservative bounds and treat the processor as defense-in-depth, not a safety interlock.

## Compatibility and installation

The G-code processor registration method is on Moonraker's metadata store, exposed as `file_manager.gcode_metadata.register_gcode_processor()`—not directly on the `FileManager` object. This path is present in the official `Arksine/moonraker` v0.11 source. The component and installer check for this exact API path; a missing method here indicates a different/incomplete runtime checkout or API layout.

Install the module and register it with Moonraker by running the toolchanger installer from the updated checkout:

```sh
bash ~/klipper-toolchanger/install.sh
```

With the standard source checkout/config paths, the installer links the component into `~/moonraker/moonraker/components`, backs up `~/printer_data/config/moonraker.conf`, and adds `[toolchanger_gcode_processor]` with `enabled: False` if that section does not already exist. Set `MOONRAKER_PATH`, `MOONRAKER_CONFIG`, or `MOONRAKER_SERVICE` in the environment when the printer uses different paths or service name. The installer restarts Moonraker when the source checkout is detected.

The processor intentionally remains disabled until you set and verify all four safe XY bounds and change `enabled` to `True`. Do not use the kinematic min/max values blindly: account for tool offsets and homing-origin shifts in the coordinate frame used by the slicer.

Add a Moonraker config section, initially leaving it disabled:

```ini
[toolchanger_gcode_processor]
enabled: False
# Before enabling, set all four bounds to a conservative safe XY envelope.
# x_min: ...
# x_max: ...
# y_min: ...
# y_max: ...
timeout: 120
```

Only enable after verifying the bounds against the active printer configuration, tool offsets, homing origin, and representative sliced files. If enabled, all four bounds are required and each minimum must be below its maximum. Then restart Moonraker and verify that its log reports `GCode Processor toolchanger_destination registered`.

## Local tests

Run from the repository root:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q moonraker/test_toolchanger_gcode_processor.py
```

Tests exercise safe XY-before-Z pass-through, a narrowly repairable Z-before-XY case, and unchanged ambiguous/out-of-bounds cases. They do not replace validation against the exact printer configuration or a controlled hardware test.
