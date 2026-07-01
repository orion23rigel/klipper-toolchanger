# Per-tool axis endstop support for toolchangers
#
# Copyright (C) 2026 Viesturs Zarins <viesturz@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging


class ToolAxisEndstop:
    """Virtual endstop proxy that routes to the active tool's physical endstop.

    Registers a Klipper virtual pin chip (e.g. 'toolchanger_x') that
    implements the MCU_endstop interface.  All homing/query operations
    are forwarded to whichever tool's MCU_endstop is currently active.

    The router is lazily created by the first config section that
    references it (either the unnamed [tool_axis_endstop] section or
    a per-tool [tool_axis_endstop Tn] section).
    """

    def __init__(self, printer, axis_name):
        self.printer = printer
        self.axis_name = axis_name
        self.chip_name = 'toolchanger_%c' % (axis_name,)
        self.virtual_pin = '%c_virtual_endstop' % (axis_name,)
        self.active_mcu_endstop = None
        self.default_endstop = None
        self._endstops = {}       # tool_number -> MCU_endstop
        self._steppers = []
        self._rail = None
        self._default_position = 0.0
        self._position_endstop_overrides = {}  # tool_number -> position

        ppins = printer.lookup_object('pins')
        ppins.register_chip(self.chip_name, self)
        printer.add_object(self.chip_name, self)
        printer.register_event_handler(
            'klippy:connect', self._handle_connect)

    def setup_pin(self, pin_type, pin_params):
        """Called by Klipper when a stepper references the virtual pin.
        Returns self so the stepper rail uses this object as its endstop.
        """
        if pin_type != 'endstop' or pin_params['pin'] != self.virtual_pin:
            raise self.printer.config_error(
                "Tool %s virtual endstop requires pin '%s'"
                % (self.axis_name.upper(), self.virtual_pin))
        return self

    def add_endstop(self, tool_number, mcu_endstop):
        """Register a tool's physical MCU_endstop for this axis."""
        self._endstops[tool_number] = mcu_endstop
        for s in self._steppers:
            mcu_endstop.add_stepper(s)

    def set_default_endstop(self, mcu_endstop):
        """Set the fallback endstop (from optional unnamed [tool_axis_endstop])."""
        self.default_endstop = mcu_endstop
        if self.active_mcu_endstop is None:
            self.active_mcu_endstop = mcu_endstop

    def _handle_connect(self):
        toolhead = self.printer.lookup_object('toolhead')
        kin = toolhead.get_kinematics()
        rail = getattr(kin, 'rail_' + self.axis_name, None)
        if rail is not None:
            self._rail = rail
            self._default_position = rail.position_endstop

    def set_active_tool(self, tool_number):
        """Switch routing to the active tool's endstop, or fall back to default."""
        self.active_mcu_endstop = self._endstops.get(
            tool_number, self.default_endstop)
        if self._rail is not None:
            if tool_number in self._position_endstop_overrides:
                self._rail.position_endstop = \
                    self._position_endstop_overrides[tool_number]
            else:
                self._rail.position_endstop = self._default_position

    def add_stepper(self, stepper):
        """Forward stepper to all registered endstops (CoreXY cross-wiring).

        Klipper calls add_stepper on each endstop during kinematics
        initialization.  We must forward to every registered MCU_endstop
        so that each MCU's trigger dispatch knows which steppers to
        monitor during homing.
        """
        self._steppers.append(stepper)
        if self.default_endstop:
            self.default_endstop.add_stepper(stepper)
        for es in self._endstops.values():
            es.add_stepper(stepper)

    def get_steppers(self):
        return list(self._steppers)

    def has_endstop(self, tool_number):
        """Public accessor used by validation check."""
        return tool_number in self._endstops

    # ---- MCU_endstop proxy methods ----

    def home_start(self, print_time, sample_time, sample_count,
                   rest_time, triggered=True):
        if not self.active_mcu_endstop:
            raise self.printer.command_error(
                "Cannot home %s - no active tool endstop configured"
                % (self.axis_name.upper(),))
        return self.active_mcu_endstop.home_start(
            print_time, sample_time, sample_count, rest_time, triggered)

    def home_wait(self, home_end_time):
        if not self.active_mcu_endstop:
            raise self.printer.command_error(
                "Cannot get home position - no active tool endstop")
        return self.active_mcu_endstop.home_wait(home_end_time)

    def query_endstop(self, print_time):
        if not self.active_mcu_endstop:
            raise self.printer.command_error(
                "Cannot query endstop - no active tool endstop")
        return self.active_mcu_endstop.query_endstop(print_time)


def load_config(config):
    """Unnamed [tool_axis_endstop] section — optional global defaults.

    Creates the virtual chips and registers default MCU_endstops.
    This section is optional; if no per-tool sections exist the
    virtual chip is never created and behavior is unchanged.
    """
    printer = config.get_printer()
    x_default = config.get('x_default_pin', None)
    y_default = config.get('y_default_pin', None)

    for axis, default_pin in (('x', x_default), ('y', y_default)):
        if default_pin is None:
            continue
        chip_name = 'toolchanger_%c' % (axis,)
        router = printer.lookup_object(chip_name, None)
        if router is None:
            router = ToolAxisEndstop(printer, axis)
        ppins = printer.lookup_object('pins')
        ppins.allow_multi_use_pin(
            default_pin.replace('^', '').replace('!', ''))
        mcu_endstop = ppins.setup_pin('endstop', default_pin)
        router.set_default_endstop(mcu_endstop)

    return None


def load_config_prefix(config):
    """Per-tool [tool_axis_endstop Tn] section.

    Registers this tool's physical endstop pin(s) with the
    corresponding virtual chip.  The tool number is inferred
    from the section name suffix (e.g. "T0" -> 0) or from an
    explicit 'tool' parameter.
    """
    printer = config.get_printer()
    ppins = printer.lookup_object('pins')
    name = config.get_name()

    # Extract tool tag from "tool_axis_endstop T0" -> "T0" -> 0
    parts = name.split(None, 1)
    tool_tag = parts[1] if len(parts) > 1 else ''

    tool_number = config.getint('tool', None)
    if tool_number is None and tool_tag:
        try:
            t = tool_tag.upper()
            if t.startswith('T'):
                tool_number = int(t[1:])
        except ValueError:
            pass

    x_pin = config.get('x_pin', None)
    y_pin = config.get('y_pin', None)

    position_endstop = config.getfloat('position_endstop', None)

    for axis, pin in (('x', x_pin), ('y', y_pin)):
        if pin is None:
            continue
        chip_name = 'toolchanger_%c' % (axis,)
        router = printer.lookup_object(chip_name, None)
        if router is None:
            router = ToolAxisEndstop(printer, axis)
        ppins.allow_multi_use_pin(
            pin.replace('^', '').replace('!', ''))
        mcu_endstop = ppins.setup_pin('endstop', pin)
        router.add_endstop(tool_number, mcu_endstop)
        if position_endstop is not None:
            router._position_endstop_overrides[tool_number] = position_endstop

    return None
