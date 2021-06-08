#!/usr/bin/env python3

import curses
import time

from messages import *
from logger import Logger

# colours we use
RED = 1
GREEN = 2
CYAN = 3


class ModuleState(object):

    def __init__(self, win, logger):
        self._win = win
        self._logger = logger
        self._can_in_timeout = False
        self._can_did_timeout = False
        self.module_resets = 0
        self.message_errors = 0
        self.message_rx_count = 0
        self._reset()

    def _reset(self):
        self.status_system = None
        self.status_v_i = None
        self.status_faults = None

    def update(self, msg):
        self.message_rx_count += 1
        self._can_in_timeout = False
        try:
            self.status_system = MSG_status_system(msg)
            return
        except MessageError:
            pass
        try:
            self.status_v_i = MSG_status_voltage_current(msg)
            return
        except MessageError:
            pass
        try:
            self.status_faults = MSG_status_faults(msg)
            return
        except MessageError:
            pass
        try:
            ack = MSG_ack(msg)
            self.module_resets += 1
            return
        except MessageError:
            pass
        if msg.arbitration_id not in [0x349, 0x130, 0x6f1, 0x700]:
            self.message_errors += 1
            self._logger.log(f'CAN? {msg}')

    def timeout(self):
        self._can_in_timeout = True
        self._can_did_timeout = True
        self._reset()

    def module_reset(self):
        self.module_resets += 1

    def __getattr__(self, attrName):
        for obj in [self.status_system, self.status_v_i, self.status_faults]:
            try:
                return getattr(obj, attrName)
            except AttributeError:
                pass
        raise AttributeError


class DispObj(object):
    def __init__(self, win, y, x, source, propname, index=None):
        self._win = win
        self._y = y
        self._x = x
        self._source = source
        self._propname = propname
        self._index = index

    @property
    def attr(self):
        try:
            val = self.value
            return curses.A_BOLD
        except Exception:
            return curses.A_DIM

    @property
    def property(self):
        val = getattr(self._source, self._propname)
        if self._index is not None:
            val = val[self._index]
        return val

    def draw(self):
        self._win.addstr(self._y, self._x, self.value, self.attr)


class MilliUnit(DispObj):
    def __init__(self, win, y, x, source, propname, index, suffix):
        super().__init__(win, y, x, source, propname, index)
        self._suffix = suffix

    @property
    def value(self):
        try:
            return f'{self.property / 1000:>6.3f}{self._suffix}'
        except Exception:
            return f'--.---{self._suffix}'


class CentiUnit(DispObj):
    def __init__(self, win, y, x, source, propname, index, suffix):
        super().__init__(win, y, x, source, propname, index)
        self._suffix = suffix

    @property
    def value(self):
        try:
            return f'{self.property / 100:>5.2f}{self._suffix}'
        except Exception:
            return f'--.--{self._suffix}'


class DeciUnit(DispObj):
    def __init__(self, win, y, x, source, propname, index, suffix):
        super().__init__(win, y, x, source, propname, index)
        self._suffix = suffix

    @property
    def value(self):
        try:
            return f'{self.property / 10:>4.1f}{self._suffix}'
        except Exception:
            return f'--.-{self._suffix}'


class Millivolts(MilliUnit):
    def __init__(self, win, y, x, source, propname, index=None):
        super().__init__(win, y, x, source, propname, index, 'V')


class DeciVolts(DeciUnit):
    def __init__(self, win, y, x, source, propname, index=None):
        super().__init__(win, y, x, source, propname, index, 'V')


class CentiAmps(CentiUnit):
    def __init__(self, win, y, x, source, propname, index=None):
        super().__init__(win, y, x, source, propname, index, 'A')


class ByteUnit(DispObj):
    def __init__(self, win, y, x, source, propname, suffix):
        super().__init__(win, y, x, source, propname)
        self._suffix = suffix

    @property
    def value(self):
        try:
            return f'{self.property:3}{self._suffix}'
        except Exception:
            return f'---{self._suffix}'


class Temperature(ByteUnit):
    def __init__(self, win, y, x, source, propname):
        super().__init__(win, y, x, source, propname, '°C')


class Percentage(ByteUnit):
    def __init__(self, win, y, x, source, propname):
        super().__init__(win, y, x, source, propname, '%')


class Count(DispObj):
    def __init__(self, win, y, x, source, propname):
        super().__init__(win, y, x, source, propname)

    @property
    def value(self):
        return f'{self.property:5}'


class OnOff(DispObj):
    def __init__(self, win, y, x, source, propname, index=None):
        super().__init__(win, y, x, source, propname, index)

    @property
    def attr(self):
        try:
            if self.property:
                return curses.color_pair(GREEN)
        except Exception:
            pass
        return curses.A_DIM

    @property
    def value(self):
        try:
            return 'ON ' if self.property else 'OFF'
        except Exception:
            return '---'


class Fault(DispObj):
    def __init__(self, win, y, x, source, propname, field, label, index=None):
        super().__init__(win, y, x, source, propname, index)
        self._field = field
        self._label = label

    @property
    def _state(self):
        try:
            val = self.property
            if val & (1 << self._field):
                return 'current'
            if val & (1 << (self._field + 4)):
                return 'latched'
        except Exception:
            pass
        return 'none'

    @property
    def attr(self):
        state = self._state
        if state == 'current':
            return curses.color_pair(RED)
        elif state == 'latched':
            return curses.color_pair(CYAN)
        return curses.A_DIM

    @property
    def value(self):
        return '-' * len(self._label) if self._state == 'none' else self._label


class Flag(DispObj):
    def __init__(self, win, y, x, source, propname, field, label):
        super().__init__(win, y, x, source, propname)
        self._field = field
        self._label = label

    @property
    def attr(self):
        try:
            if self.property & (1 << self._field):
                return curses.color_pair(GREEN)
        except Exception:
            pass
        return curses.A_DIM

    @property
    def value(self):
        try:
            if self.property & (1 << self._field):
                return self._label
        except Exception:
            pass
        return '-' * len(self._label)


class MonitorState(object):
    def __init__(self):
        self.sw_t15 = False
        self.sw_brake = False
        self.sw_lights = False
        self.sw_rain = False
        self.sw_can = False


# Live monitoring mode for testing, etc.
#
# -- Monitor Status -------------------------------------
# Resets:        0  Messages Recvd:        6
# Faults: X         Message Errors:        0
#
# -- Module Status --------------------------------------
# T15 0.000V  Temp   0°C  Fuel: 000%
# Status: Brake Light Rain
# Faults: T15 CAN TEMP
#
# Output    Status  Voltage     Current     Faults
#    1       OFF    0.000V      0.000A      OPEN STUCK OVERLOAD
#    2       OFF    0.000V      0.000A      OPEN STUCK OVERLOAD
#    3       OFF    0.000V      0.000A      OPEN STUCK OVERLOAD
#    4       OFF    0.000V      0.000A      OPEN STUCK OVERLOAD
#
# [T]15 OFF  [B]rake OFF  [L]ights OFF  [R]ain OFF  [C]AN OFF
# [Q]uit
#
# Fault text is red if the fault is current, cyan if saved,
# dashed out otherwise.
#
def do_monitor(stdscr, interface, args):

    # monitor initialization
    tx_phase = True
    tx_time = time.time()

    monitor_state = MonitorState()
    if not args.no_CAN_at_start:
        monitor_state.sw_can = True
    if args.T15_at_start:
        monitor_state.sw_t15 = True

    # curses init
    curses.curs_set(False)
    curses.start_color()
    stdscr.nodelay(True)
    stdscr.clear()
    stdscr.refresh()
    curses.init_pair(RED, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(GREEN, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(CYAN, curses.COLOR_CYAN, curses.COLOR_BLACK)

    # lay out the status window
    statwin = curses.newwin(19, 80, 0, 0)
    statwin.addstr(1, 1, '-- Monitor Status -------------------------------------')
    statwin.addstr(2, 1, 'Resets:           Messages Recvd:')
    statwin.addstr(3, 1, 'Faults:           Message Errors:')

    statwin.addstr(5, 1, '-- Module Status --------------------------------------')
    statwin.addstr(6, 1, 'T15          Temp        Fuel:    %')
    statwin.addstr(7, 1, 'Status:')
    statwin.addstr(8, 1, 'Faults:')

    statwin.addstr(10, 1, 'Output    Status  Voltage     Current     Faults')
    statwin.addstr(11, 4, '1')
    statwin.addstr(12, 4, '2')
    statwin.addstr(13, 4, '3')
    statwin.addstr(14, 4, '4')

    statwin.addstr(16, 1, '[T]15      [B]rake      [L]ights      [R]ain      [C]AN')
    statwin.addstr(17, 1, '[Q]uit')
    statwin.refresh()

    # initialize the logger window
    maxy, maxx = stdscr.getmaxyx()
    logwin = curses.newwin(maxy - 18, maxx, 19, 0)
    logger = Logger(logwin, args)

    # create the module state tracker
    module_state = ModuleState(statwin, logger)

    # create display widgets
    widgets = [
        Count(statwin, 2, 10, module_state, 'module_resets'),
        Count(statwin, 2, 35, module_state, 'message_rx_count'),
        Count(statwin, 3, 35, module_state, 'message_errors'),
        # Fault(statwin, 3, 9, monitor_state, 'monitor_faults', 0, 'CAN')

        Millivolts(statwin, 6, 5, module_state, 't15_voltage'),
        Temperature(statwin, 6, 19, module_state, 'temperature'),
        Percentage(statwin, 6, 32, module_state, 'fuel_level'),
        Flag(statwin, 7, 9, module_state, 'function_request', 0, 'Brake'),
        Flag(statwin, 7, 15, module_state, 'function_request', 1, 'Light'),
        Flag(statwin, 7, 21, module_state, 'function_request', 2, 'Rain'),
        Fault(statwin, 8, 9, module_state, 'system_faults', 0, 'T15'),
        Fault(statwin, 8, 13, module_state, 'system_faults', 1, 'CAN'),
        Fault(statwin, 8, 17, module_state, 'system_faults', 2, 'TEMP'),

        OnOff(statwin, 16, 7, monitor_state, 'sw_t15'),
        OnOff(statwin, 16, 20, monitor_state, 'sw_brake'),
        OnOff(statwin, 16, 34, monitor_state, 'sw_lights'),
        OnOff(statwin, 16, 46, monitor_state, 'sw_rain'),
        OnOff(statwin, 16, 57, monitor_state, 'sw_can'),
    ]
    for channel in range(0, 4):
        widgets += [
            Flag(statwin, 11 + channel, 12, module_state, 'output_request', channel, 'ON'),
            DeciVolts(statwin, 11 + channel, 19, module_state, 'output_voltage', channel),
            CentiAmps(statwin, 11 + channel, 31, module_state, 'output_current', channel),
            Fault(statwin, 11 + channel, 43, module_state, 'output_faults', 0, 'OPEN', channel),
            Fault(statwin, 11 + channel, 48, module_state, 'output_faults', 1, 'STUCK', channel),
            Fault(statwin, 11 + channel, 54, module_state, 'output_faults', 2, 'OVERLOAD', channel),
        ]

    # run the monitor loop
    while True:
        statwin.refresh()
        msg = interface.recv(0.1)
        if msg is not None:
            try:
                logger.log_console(msg)
            except KeyError:
                logger.log_can(msg)
                module_state.update(msg)

        for widget in widgets:
            widget.draw()

        if monitor_state.sw_can and ((time.time() - tx_time) > 0.1):
            if tx_phase:
                msg = MSG_brake.with_fields(monitor_state.sw_brake)
            else:
                msg = MSG_lights.with_fields(False, monitor_state.sw_lights, monitor_state.sw_rain)
                # msg = MSG_lights.with_fields(sw_brake, sw_lights, sw_rain)
            logger.log_can(msg)
            interface.send(msg)
            tx_time = time.time()
            tx_phase = not tx_phase

        try:
            ch = stdscr.getkey()
            if ch == 't' or ch == 'T':
                monitor_state.sw_t15 = not monitor_state.sw_t15
                if monitor_state.sw_t15:
                    interface.set_power_t30_t15()
                else:
                    interface.set_power_t30()
            if ch == 'b' or ch == 'B':
                monitor_state.sw_brake = not monitor_state.sw_brake
            if ch == 'l' or ch == 'L':
                monitor_state.sw_lights = not monitor_state.sw_lights
            if ch == 'r' or ch == 'R':
                monitor_state.sw_rain = not monitor_state.sw_rain
            if ch == 'c' or ch == 'C':
                monitor_state.sw_can = not monitor_state.sw_can
            if ch == 'q' or ch == 'Q':
                return
        except Exception:
            pass
