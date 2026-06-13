# Configuration reference

This reference covers every repository-defined configuration-file parameter
read by the Python extensions, plus the knobs exposed by shipped examples and
the installer. It is organized by Klipper config section. G-code command
arguments are documented in the component guides instead.

Parameters marked **inherited** are parsed by a standard Klipper helper. Their
exact accepted options, defaults, requirements, and validation are not defined
in this repository and follow the installed Klipper version.

## Core extensions

### `[toolchanger]` and `[toolchanger <name>]`

The unnamed `[toolchanger]` is the main toolchanger. Named sections create
additional configuration/default providers. A tool may inherit options from a
named toolchanger, but numbered tool assignment and generated `T<n>` commands
are still registered with the main toolchanger.

| Parameter | Required | Default | Type / values | Description |
|---|---:|---|---|---|
| `initialize_on` | No | `first-use` | `manual`, `home`, or `first-use` | Selects when the toolchanger initializes. |
| `initialize_gcode` | No | empty | G-code template | Runs during initialization. It may call initialization again to identify the active tool without rerunning the template. |
| `verify_tool_pickup` | No | `True` | Boolean | When detection pins exist, verifies the selected tool after pickup. |
| `require_tool_present` | No | `False` | Boolean | Disables `UNSELECT_TOOL` and rejects initialization when active-tool configuration/detection runs but finds no tool. |
| `transfer_fan_speed` | No | `True` | Boolean | Transfers the previous or pending part-cooling speed to the newly active tool fan. |
| `uses_axis` | No | `xyz` | Axis letters | Axes that must be homed before a tool change. Use an empty value when no axes are required. |
| `on_axis_not_homed` | No | `abort` | `abort` or `home` | Aborts or attempts to home missing axes before a tool change. |
| `before_change_gcode` | No | empty | G-code template | Default pre-change template; a tool-level value overrides it. |
| `after_change_gcode` | No | empty | G-code template | Default post-change template; a tool-level value overrides it. |
| `error_gcode` | No | unset | G-code template | Runs when tool validation or `SELECT_TOOL_ERROR` puts the toolchanger in an error state. Required for asynchronous detection verification. |
| `abort_on_tool_missing` | No | `False` | Boolean | During virtual-SD printing, runs toolchanger error handling if the detected tool no longer matches the requested tool. |
| `tool_missing_delay` | No | `2.0` | Seconds, greater than `0` | Delay before a missing-tool detection event is considered valid. |
| `params_*` | No | none | Python literal | Adds arbitrary values to toolchanger status/template context. Values must be valid Python literals, such as `12.5`, `"text"`, lists, or dictionaries. |

The following options can be inherited from a toolchanger when a tool consumes
them:
`pickup_gcode`, `dropoff_gcode`, `before_change_gcode`, `after_change_gcode`,
`recover_gcode`, `gcode_x_offset`, `gcode_y_offset`, `gcode_z_offset`,
`t_command_restore_axis`, `extruder`, `heater`, `extruder_stepper`, `fan`, and
`tool_probe`. See `[tool <name>]` below for their behavior. `heater`,
`extruder_stepper`, and `tool_probe` are not pre-read when no tool consumes
them.

### `[tool <name>]`

| Parameter | Required | Default | Type / values | Description |
|---|---:|---|---|---|
| `toolchanger` | No | `toolchanger` | Object name | Toolchanger section used for inherited defaults and related helpers. Number assignment and generated `T<n>` commands still use the main toolchanger. |
| `tool_number` | No | unassigned (`-1`) | Integer, minimum `0` | Assigns a number and registers the corresponding `T<n>` command. |
| `detection_pin` | No | unset | Pin | Tool-presence input. A triggered pin means absent; an open pin means mounted. All tools assigned to the main toolchanger must either define detection or omit it. |
| `pickup_gcode` | No | parent value or empty | G-code template | Runs to pick up this tool. |
| `dropoff_gcode` | No | parent value or empty | G-code template | Runs to drop off this tool. |
| `before_change_gcode` | No | parent value or empty | G-code template | Runs before a change when this is the currently active tool. |
| `after_change_gcode` | No | parent value or empty | G-code template | Runs after this tool becomes active. |
| `recover_gcode` | No | parent value or empty | G-code template | Runs during `INITIALIZE_TOOLCHANGER RECOVER=1` only when recovering from `STATUS_ERROR` with a selected recovery tool. |
| `gcode_x_offset` | No | parent value or `0.0` | Float, mm | X offset applied by the toolchanger move transform. |
| `gcode_y_offset` | No | parent value or `0.0` | Float, mm | Y offset applied by the toolchanger move transform. |
| `gcode_z_offset` | No | parent value or `0.0` | Float, mm | Z offset applied by the toolchanger move transform. |
| `extruder` | No | parent value or unset | Object name | Extruder activated with the tool; its heater is used unless `heater` overrides it. |
| `heater` | No | parent value or unset | Object name | Heater used by `SET_TOOL_TEMPERATURE`, overriding the extruder heater. |
| `extruder_stepper` | No | parent value or unset | Object name | Extruder stepper synchronized to the active extruder motion queue. |
| `fan` | No | parent value or unset | Fan name | `fan_generic` or legacy `multi_fan` used as this tool's part-cooling fan. A regular `[fan]` cannot be used with tool fans. |
| `tool_probe` | No | parent value or unset | Object name | Per-tool probe selected when this tool becomes active. All tools assigned to the main toolchanger must define a probe if any assigned tool does. |
| `t_command_restore_axis` | No | parent value or `XYZ` | Axis letters | Axes restored after this tool's generated `T<n>` command. |
| `params_*` | No | inherited values | Python literal | Adds or overrides arbitrary tool status/template values. |

Every tool template receives `tool` and `toolchanger`. Additional context
depends on the operation: normal changes provide `dropoff_tool`, `pickup_tool`,
`start_position`, and `restore_position`; initialization additionally provides
`dropoff_tool` and `pickup_tool`; recovery additionally provides `pickup_tool`,
`start_position`, and `restore_position`. See [toolchanger.md](toolchanger.md)
for lifecycle and G-code details.

### `[tool_probe <name>]`

| Parameter | Required | Default | Type / values | Description |
|---|---:|---|---|---|
| `pin` | Yes | none | Pin | Probe input. The pin may be shared with tool detection. |
| `tool` | No | unset | Integer | Associates the probe with a tool number for standalone active-probe detection and crash detection. |
| Standard probe offset and sampling options | Varies | Klipper defaults | Standard Klipper probe values | **Inherited** through Klipper's probe helpers. Common options used by shipped examples include `x_offset`, `y_offset`, `z_offset`, `speed`, `lift_speed`, `samples`, `sample_retract_dist`, `samples_result`, `samples_tolerance`, and `samples_tolerance_retries`. |
| Standard probe activation templates | Varies | Klipper defaults | G-code templates | **Inherited** through Klipper's probe helpers, including `activate_gcode` and `deactivate_gcode` where supported by the installed Klipper version. |

### `[tool_probe_endstop]`

This standalone router exposes the selected `[tool_probe ...]` as Klipper's
global `probe` object. Do not configure a separate `[probe]` section with it.
When tools reference `tool_probe`, the toolchanger creates an internal router,
so a standalone section is usually unnecessary.

| Parameter | Required | Default | Type / values | Description |
|---|---:|---|---|---|
| `crash_mintime` | No | `0.5` | Seconds, greater than `0` | Probe must remain triggered this long before crash handling runs. |
| `crash_gcode` | No | empty | G-code template | Runs after a sustained active-tool probe trigger while crash detection is enabled. |
| Standard probe command/sample options | No | Klipper defaults | See `[tool_probe]` | **Inherited** by Klipper's probe command and sample helpers. |

### `[tools_calibrate]`

| Parameter | Required | Default | Type / values | Description |
|---|---:|---|---|---|
| `pin` | Yes | none | Pin | Contact-probe input used for X, Y, and Z calibration moves. |
| `probe` | No | `probe` | Object name | Nozzle/bed probe used by `TOOL_CALIBRATE_PROBE_OFFSET`. |
| `travel_speed` | No | `10.0` | mm/s, greater than `0` | Speed for travel between contacts. |
| `spread` | No | `5.0` | Float, mm | XY distance from the estimated center used to begin side probes. |
| `lower_z` | No | `0.5` | Float, mm | Distance below the top contact plane used for side probes. |
| `lift_z` | No | `1.0` | Float, mm | Z clearance between the top contact and side-probe moves. |
| `trigger_to_bottom_z` | No | `0.0` | Float, mm | Mechanical distance from contact trigger to bottom-out, added to calculated probe Z offset. |
| `lift_speed` | No | `speed` | Float, mm/s | Speed for calibration lifts and sample retracts. |
| `final_lift_z` | No | `4.0` | Float, mm | Final clearance above the located sensor center. |
| `speed` | No | `5.0` | mm/s, greater than `0` | Contact probing speed. |
| `max_travel` | No | `4` | mm, greater than `0` | Parsed and stored by the calibration probe helper, but currently unused by calibration probing calls. |
| `samples` | No | `1` | Integer, minimum `1` | Samples per contact. |
| `sample_retract_dist` | No | `2.0` | mm, greater than `0` | Retract distance between samples. |
| `samples_result` | No | `average` | `average` or `median` | Method used to aggregate accepted samples. |
| `samples_tolerance` | No | `0.100` | Float, minimum `0` | Maximum spread along the probed axis. |
| `samples_tolerance_retries` | No | `0` | Integer, minimum `0` | Number of full sample-set retries after a tolerance failure. |

### `[rounded_path]`

| Parameter | Required | Default | Type / values | Description |
|---|---:|---|---|---|
| `resolution` | No | `1.0` | mm, greater than `0` | Approximate arc length per generated Bezier segment. Smaller values generate more G0 segments. |
| `replace_g0` | No | `False` | Boolean | Replaces the normal `G0` handler with rounded-path buffering. Every buffered chain must end with `D=0`. |

### `[bed_thermal_adjust]`

This module replaces `M140` and `M190` so their requested temperature represents
the estimated bed-surface temperature rather than the heater sensor temperature.

| Parameter | Required | Default | Type / values | Description |
|---|---:|---|---|---|
| `temperature_drop_per_degree` | Yes | none | Float, greater than `0` and less than `1` | Fraction of the heater-to-ambient temperature difference treated as thermal loss. |
| `chamber_temperature_sensor` | Conditional | unset | Object name | Temperature sensor used as ambient temperature. |
| `use_bed_temperature` | No | `False` | Boolean | Allows an `M140`/`M190` call to refresh ambient from the bed temperature when starting to heat after the bed has cooled down (i.e. the cooldown-timer condition passes). |
| `fixed_chamber_temperature` | Conditional | none | Float, `0` to `100` | Fixed ambient temperature. Required when neither `chamber_temperature_sensor` nor `use_bed_temperature` is configured. |

`fixed_chamber_temperature` is read only when neither dynamic strategy is
enabled. The code permits `chamber_temperature_sensor` and
`use_bed_temperature` together: the timer refreshes ambient from the chamber
sensor, while qualifying `M140`/`M190` calls may refresh it from the bed.

### `[multi_fan <name>]` (legacy)

Each section constructs a standard Klipper fan and adds it to a shared active-fan
controller. The first configured fan starts active. This module cannot be used
with a regular `[fan]` section.

All fan parameters are **inherited** from Klipper's standard fan
implementation. Consult the installed Klipper configuration reference for the
exact supported options and defaults.

### `[manual_rail <name>]`

This module delegates stepper and homing configuration to Klipper. Defining
`endstop_pin` creates a homeable multi-stepper rail; omitting it creates a
single non-homeable stepper.

| Parameter | Required | Default | Type / values | Description |
|---|---:|---|---|---|
| `velocity` | No | `5.0` | mm/s, greater than `0` | Default `MANUAL_RAIL` move speed. |
| `accel` | No | `0.0` | mm/s², minimum `0` | Default move and homing acceleration; zero disables acceleration. |
| `position_min` | Conditional | unset | Float, mm | Lower command bound. Must be explicitly available for positive-direction homing because that homing travel calculation uses it. |
| `position_max` | Conditional | unset | Float, mm | Upper command bound. Must be explicitly available for negative-direction homing because that homing travel calculation uses it. |
| Standard stepper options | Varies | Klipper defaults | Standard Klipper stepper values | **Inherited** through Klipper's stepper/rail helpers. Shipped examples use `step_pin`, `dir_pin`, `enable_pin`, `microsteps`, and `rotation_distance`; exact requirements and defaults follow the installed Klipper version. |
| `endstop_pin` | No | unset | Pin | **Inherited**. Enables homing and multi-stepper rail behavior. |
| `position_endstop` | Conditional | none | Float, mm | **Inherited** and required for a homeable rail. |
| Other homing options | No | Klipper defaults | Standard Klipper homing values | **Inherited**, including `homing_speed`, `homing_retract_dist`, `homing_retract_speed`, `second_homing_speed`, and `homing_positive_dir`. |

Additional sections ending in a numeric suffix from `1` through `98`, such as
`[manual_rail <name>1]`, are treated as secondary motors when the base section
exists.

## Optional usermods

Usermods are community-contributed and are not part of the core extension.

### `[tool_drop_detection]`

| Parameter | Required | Default | Type / values | Description |
|---|---:|---|---|---|
| `accelerometer` | Yes | none | List | One or more ADXL345 section names or aliases, separated by commas or config-list lines. |
| `polling_freq` | No | `1.0` | Hz, `0.01` to `20.0` | Reactor polling frequency. |
| `polling_rate` | No | `10` | Integer Hz | Requested ADXL345 data rate; the closest supported rate is selected. |
| `peak_g_threshold` | No | unset | Float, minimum `0.01` | Sets the default immediate peak-acceleration threshold used when crash detection is armed. |
| `rotation_threshold` | No | unset | Degrees, `0` to `180` | Vector-angle threshold. Used only when pitch and roll thresholds are both unset. |
| `pitch_threshold` | No | unset | Degrees, `0` to `180` | Absolute pitch threshold. |
| `roll_threshold` | No | unset | Degrees, `0` to `180` | Absolute roll threshold. |
| `drop_mintime` | No | `1.0` | Seconds, minimum `0` | Duration an angle threshold must remain exceeded before crash G-code runs. |
| `crash_gcode` | No | empty | G-code template | Runs when an armed drop/crash threshold is met. |
| `angle_hysteresis` | No | `5.0` | Degrees, `0.1` to `180` | Return-to-normal margin for angle state transitions. |
| `angle_exceed_gcode` | No | empty | G-code template | Runs when configured angle thresholds are crossed. |
| `angle_return_gcode` | No | empty | G-code template | Runs after values return inside threshold minus hysteresis. |
| `decimals` | No | `3` | Integer, `0` to `10` | Decimal places exposed in status and template context. |
| `session_time` | No | `1.0` | Seconds, `0.01` to `60` | Length of the rolling session window. |
| `current_samples` | No | `10` | Integer, minimum `0` | Number of latest samples used for current readings; `0` uses the full batch. |
| `samples_result` | No | `median` | `median` or `mean` | Statistic used when collapsing sample windows. |
| `default_<alias>` | No | `g=1`, pitch/roll `0`, vector `(0,0,1)` | Baseline expression | Per-accelerometer reference containing `g`, `pitch`/`p`, and `roll`/`r`. The parser intends to accept `vector`/`vec`, but comma-containing vectors are currently split incorrectly and fall back to `(0,0,1)`. |

See [the usermod guide](usermods/Contomo/tool_drop_detection/readme.md) for its
commands and status fields.

### `[save_babies]`

The `save_babies` usermod has no configuration-file parameters. Loading the
section registers the `SAVE_BABYSTEPS` command.

## Example macro knobs

The shipped examples also define user-editable `variable_*` values in G-code
macro sections. These are macro configuration rather than Python-extension
parameters.

| Macro | Variables | Role |
|---|---|---|
| `[gcode_macro TC_DOCK_AUTOTUNE]` | `variable_range_mm`, `variable_step_mm`, `variable_pitch_tol`, `variable_roll_tol`, `variable_threshold`, `variable_changes_per`, `variable_abort_on_g`, `variable_debug` | User tuning |
| `[gcode_macro TC_DOCK_AUTOTUNE]` | `variable_name`, `variable_storage` | Internal identity/state |
| `[gcode_macro CAMERA_ALIGN_START]` | `variable_zero_x`, `variable_zero_y`, `variable_zero_z` | User tuning |
| `[gcode_macro LIFTBAR_LAYER_CHANGE]` | `variable_clearance` | User tuning |
| `[gcode_macro LIFTBAR_MOVE]` | `variable_position` | Runtime state |
| `[gcode_macro _SENSORLESS_HOME_X]` | `variable_home_current` | User tuning |
| Tool-selection UI macros | `variable_color` | UI metadata |
| Save-babysteps `_CURRENT_OFFSET` | `variable_xg`, `variable_yg`, `variable_zg` | Runtime state |
| Save-babysteps `_RECORD` | `variable_xa`, `variable_ya`, `variable_za`, `variable_xr`, `variable_yr`, `variable_zr` | Runtime state |

### Shipped template `params_*`

The meaning of `params_*` is template-defined. The shipped templates use the
following concrete names:

| Area | Parameters |
|---|---|
| Common docking paths | `params_safe_y`, `params_close_y`, `params_fast_speed`, `params_path_speed`, `params_dropoff_path`, `params_pickup_path`, `params_park_x`, `params_park_y`, `params_park_z` |
| Liftbar variants | `params_bed_drop`, `params_park_liftbar_z`, `params_z_lift`, `params_liftbar_stow_height`, `params_liftbar_min_z`, `params_liftbar_max_z` |
| Optional behavior | `params_input_shaper_freq_x`, `params_input_shaper_freq_y`, `params_servo_angle`, `params_accel` |

## Installer constants

The installer has two editable shell constants rather than command-line
parameters:

| Constant | Default | Description |
|---|---|---|
| `KLIPPER_PATH` | `${HOME}/klipper` | Klipper checkout whose `klippy/extras` directory receives symlinks. |
| `INSTALL_PATH` | `${HOME}/klipper-toolchanger` | Clone or existing checkout used as the symlink source. |

## Parameters intentionally outside this reference

- Standard Klipper sections used by the examples, such as `[extruder]`,
  `[fan_generic]`, `[gcode_macro]`, and `[mcu]`, are documented by Klipper.
- G-code command arguments are runtime inputs, not configuration-file
  parameters. They remain documented in the component guides and usermod
  READMEs.
- `params_*` names are intentionally open-ended; their meaning is defined by
  the user's tool-change templates.
