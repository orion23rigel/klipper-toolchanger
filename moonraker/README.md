# Moonraker toolchange destination processor (experimental)

This optional component uses Moonraker's file-manager G-code processor registration API; it does not monkey-patch `METADATA_SCRIPT` or modify Moonraker core. It is disabled by default.

## Behavior

- Scans a G-code file with bounded lookahead around toolchange commands carrying `X`, `Y`, and `Z` destinations. For `_SLICER_CHANGE`, it tolerates one following `Tn` only when `n` matches `NEXT_EXTRUDER`.
- Leaves valid destinations and transitions with XY travel before the layer-Z move untouched.
- Rewrites only an out-of-configured-range destination when it can prove an absolute, pure XY travel follows a Z descent before any extrusion or unsupported motion; it substitutes that explicit later XY target.
- Leaves relative, combined-axis, extrusion-before-XY, missing-target, out-of-range replacement, and otherwise ambiguous transitions unchanged. It reports these as processor failures in Moonraker's log.
- Uses atomic replacement only when a proven repair exists; safe/no-op files are not rewritten.

The rewrite rule is deliberately narrow, but this is **not** a general G-code verifier. The bounds supplied to this processor must be a conservative safe XY envelope in the coordinate frame used by the slicer, accounting for the configured tool offsets and homing-origin shifts. Klipper's runtime destination guard remains the final bounds check. If it skips the substituted destination, this processor cannot guarantee that a later slicer move or Z descent is safe.

Moonraker v0.11.0 awaits metadata parsing before starting a print after upload-and-print, but its processor runner logs a nonzero processor exit and continues. Therefore an ambiguous transition is not blocked: it remains unchanged, and direct upload-and-print may still start. If the same file also contains separately proven transitions, those repairs may have been applied. This follows the selected policy; it is not a print-safety interlock.

## Compatibility and installation

The registration API was verified in public Moonraker v0.11.0 source on `FileManager.register_gcode_processor`. The user-reported build string `v0.11.0-3-g9e676eba` did not resolve as a commit in the public Moonraker repository, so that exact build must be checked on the printer before enabling this component. At startup, the component requires the file-manager registration method and reports a configuration failure if the API is absent.

Install the module as an optional Moonraker component (adjust paths for the host's actual checkouts):

```sh
ln -s ~/klipper-toolchanger/moonraker/toolchanger_gcode_processor.py \
  ~/moonraker/moonraker/components/toolchanger_gcode_processor.py
```

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
