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

The update manager updates the checkout but does not run `install.sh`; run the installer once to create the Klipper and Moonraker component links.

For a checkout that contains this fork's Moonraker processor, run the installer from that checkout:

```sh
bash ~/klipper-toolchanger/install.sh
```

When it finds the standard Moonraker source tree at `~/moonraker`, the installer links the optional component, backs up `~/printer_data/config/moonraker.conf` before adding a disabled config section, then restarts Klipper and Moonraker. Override `MOONRAKER_PATH`, `MOONRAKER_CONFIG`, or `MOONRAKER_SERVICE` if those paths/service names differ. It does not enable processing or invent axis bounds; verify the safe envelope and edit the section before enabling it.

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
