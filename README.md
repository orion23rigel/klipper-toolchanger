# klipper-toolchanger

An assortment of Klipper extensions that I have made while working on [Tapchanger](https://github.com/viesturz/tapchanger)

# Installation

To install this plugin, run:

```
curl -sL https://raw.githubusercontent.com/orion23rigel/klipper-toolchanger/main/install.sh -o install.sh && bash install.sh
```

Alternatively, use the `update_manager` to install and update automatically. Add the following to your moonraker.conf:
```
[update_manager klipper-toolchanger]
type: git_repo
channel: dev
path: ~/klipper-toolchanger
origin: https://github.com/orion23rigel/klipper-toolchanger.git
managed_services: klipper
primary_branch: main
```

The update manager updates the checkout but does not run `install.sh`; run the installer once to create the Klipper and Moonraker component links. In Moonraker, `install_script` is **not** a post-update command hook—it is read for system package names and is deprecated in favor of `system_dependencies`. Remove `install_script: install.sh` from this entry unless the script contains the package-list format Moonraker expects; it will not execute the installer.

After updating this repository, run the installer manually when you need to create/refresh installed links or apply installation/configuration changes:

```sh
bash ~/klipper-toolchanger/install.sh
```

The Moonraker component is linked to the checkout, so changes to the linked component source are visible without rerunning the installer. Restart Moonraker to load source changes. Rerun the installer for new/renamed runtime files, missing or changed links, or installation/config changes; updating the installer itself does not run it. The installer also restarts services as documented below.

When it finds the standard Moonraker source tree at `~/moonraker`, the installer links the optional component, backs up `~/printer_data/config/moonraker.conf` before adding a disabled config section, then restarts Klipper and Moonraker. Override `MOONRAKER_PATH`, `MOONRAKER_CONFIG`, or `MOONRAKER_SERVICE` if those paths/service names differ. Processing remains disabled by default. With no manual bounds, the component derives a shared XY envelope from Klipper's active axis limits, configured tool offsets, and XY homing origin when Klipper reports ready. Verify the logged result before enabling. Optional manual bounds override auto-derivation when all four are provided.

## Toolchange destination handling

Toolchange destination handling has two complementary parts:

- **Klipper runtime guard and post-change positioning:** when slicer-supplied post-toolchange X/Y/Z coordinates are restored, the toolchanger checks the XY target against the active kinematics limits, homing origin, and selected tool's XY offsets. If it cannot verify the target is in range, it skips that optional destination move and reports why. For a valid destination it moves to XY while retaining the post-pickup Z, leaving the slicer's following moves to handle the actual print XY and Z descent. It restores relative coordinate mode when needed. This does not validate later independent slicer moves.
- **Optional Moonraker pre-print scan:** the component can inspect uploaded G-code and repair only an out-of-envelope toolchange destination when bounded lookahead proves a safe later XY target before extrusion or unsupported motion. Ambiguous transitions are left unchanged; Moonraker's processor is not a print interlock. See [Moonraker processor behavior, limits, and installation](moonraker/README.md).

Keep the Moonraker processor disabled until the automatically derived envelope is verified in the slicer's coordinate frame, accounting for active tool offsets and XY homing origin; alternatively, set all four manual bounds explicitly. Auto bounds are refreshed when Klipper reports ready, not on later runtime offset changes. If macros alter XY homing origin or tool offsets after that, do not rely on the derived envelope; use a verified manual envelope or keep processing disabled. Klipper's runtime guard remains the final check, and the processor is not a print interlock.

Add the [macros.cfg](/macros.cfg) to your printer config.

## Changelog
 * 2026.6.30 - Add per-tool X/Y endstop routing via `tool_axis_endstop.py` — any tool can home X (and Y) independently.
 * 2026.6.26 - Add detection_debounce config option to filter noisy tool detection pins.
* 2026.6.26 - Add temperature_wait_threshold to skip redundant M109 waits when already at target temperature.
* 2026.2.15 - Bring back the adjust Z after nozzle homing.
* 2026.2.8
     - **Breaking change** tool.detection_pin is inverted. Add/Remove the `!` in pin definition when updating.
     - Simplify use of per-tool probe. Toolchanger can automatically detect active probe, see updated configuration example.
     - Update tool probe for newest Klipper. 
* 2026.1.25 - Example script for camera tool alignment.
* 2025.12.26 - **Breaking change** Stop using Gcode offset for tool offsets. Uses a dedicated gcode transform instead.
* 2025.12.25 - Use Bezier curves for rounded paths.
* 2025.12.25 - Manual rail update to latest Klipper.

## Updates that add new files

Note that new Klipper extras and Moonraker components are not automatically linked into their runtime directories by an update. Run the install script manually to create or refresh those links:
```commandline
bash ~/klipper-toolchanger/install.sh
```

# Components

* [Toolchanger](/toolchanger.md) - tool management support.
* [Tool probe](/tool_probe.md) - per tool Z probe.
* [Tool axis endstop](/tool_axis_endstop.md) - per tool X/Y endstop routing for homing.
* [Rounded path](/rounded_path.md) - rounds the travel path corners for fast non-print moves.
* [Tools calibrate](/tools_calibrate.md) - support for contact based XYZ offset calibration probes, including optional bed-position tool probe offset calibration.
