#!/usr/bin/env python3
#
# Functional tests for the 7x_e36 tail module firmware.
#
# Test setup:
#
# - 5A power supply
# - programmer/probe connected
# - DO_1 programmable load
# - DO_2 LED to ground
# - DO_3 open
# - DO_4 open
# - AI_1 some value 0-5V
# - KL15 on relay

import argparse
import struct
import time
import can
import curses
import time

# colours we use
RED = 1
GREEN = 2
CYAN = 3

# message IDs
ACK_ID = 0x1ffffff0
CONSOLE_ID = 0x1ffffffe
MJS_POWER_ID = 0x0fffffff
LIGHT_CTRL_ID = 0x21a
BRAKE_CTRL_ID = 0x0a8


class MessageError(Exception):
    """a received message was not as expected"""
    pass


class ModuleError(Exception):
    """the module did something unexpected"""
    pass


class TXMessageStd(can.Message):
    """
    Abstract for messages that will be sent.

    Concrete classes set self._format and pass args to struct.pack()
    that format to __init__.
    """
    def __init__(self, arbitration_id, *args):
        super().__init__(arbitration_id=arbitration_id,
                         is_extended_id=False,
                         dlc=struct.calcsize(self._format),
                         data=struct.pack(self._format, *args))


class TXMessageExt(can.Message):
    """
    Abstract for messages that will be sent.

    Concrete classes set self._format and pass args to struct.pack()
    that format to __init__.
    """
    def __init__(self, arbitration_id, *args):
        super().__init__(arbitration_id=arbitration_id,
                         is_extended_id=True,
                         dlc=struct.calcsize(self._format),
                         data=struct.pack(self._format, *args))


class MSG_mjs_power(TXMessageExt):
    """mjs adapter power control message"""
    _format = '>B'

    def __init__(self, t30_state, t15_state):
        if not t30_state:
            arg = 0x00
        elif not t15_state:
            arg = 0x01
        else:
            arg = 0x03
        super().__init__(MJS_POWER_ID, arg)


class MSG_brake(TXMessageStd):
    """BMW brake (etc.) status message"""
    _format = '>BHHBBB'

    def __init__(self, brake_state):
        super().__init__(BRAKE_CTRL_ID,
                         0x54,              # magic
                         0,                 # actual torque
                         0,                 # rounded torque
                         240,               # clutch not depressed
                         0x0f,              # magic
                         32 if brake_state else 3)


class MSG_lights(TXMessageStd):
    """BMW light control message"""
    _format = '>BBB'

    def __init__(self, brake_light, tail_light, rain_light):
        super().__init__(LIGHT_CTRL_ID,
                         ((0x80 if brake_light else 0) |
                          (0x04 if tail_light else 0) |
                          (0x40 if rain_light else 0)),
                         0,
                         0xf7)


class MSG_scantool(TXMessageStd):
    """Message from BMW scantool"""
    _format = '>BBBBBBBB'

    def __init__(self, recipient, length, cmd):
        while len(cmd) < 6:
            cmd.append(0)
        super().__init__(0x6f1,
                         recipient,
                         length,
                         *cmd)


class RXMessage(object):
    """
    Abstract for messages that have been received.

    Concretes set self._format to struct.unpack() received bytes,
    and self._filter to a list of tuple-per-unpacked-item with each
    tuple containing True/False and, if True, the required value.
    """
    def __init__(self, expected_id, raw):
        if raw.arbitration_id != expected_id:
            raise MessageError(f'expected reply with ID 0x{expected_id:x} '
                               f'but got {raw}')
        expected_dlc = struct.calcsize(self._format)
        if raw.dlc != expected_dlc:
            raise MessageError(f'expected reply with length {expected_dlc} '
                               f'but got {raw}')

        self._data = raw.data
        self._values = struct.unpack(self._format, self._data)
        for (index, (check, value)) in enumerate(self._filter):
            if check and value != self._values[index]:
                raise MessageError(f'reply field {index} is '
                                   f'0x{self._values[index]:x} '
                                   f'but expected 0x{value:x}')

    @classmethod
    def len(self):
        return struct.calcsize(self._format)


class MSG_ack(RXMessage):
    """broadcast message sent by module on power-up, reboot or crash"""
    _format = '>BIBH'
    _filter = [(False, 0),
               (False, 0),
               (False, 0),
               (False, 0)]
    REASON_MAP = {
        0x00: 'power-on',
        0x01: 'reset',
        0x11: 'low-voltage reset',
        0x21: 'clock lost',
        0x31: 'address error',
        0x41: 'illegal opcode',
        0x51: 'watchdog timeout'
    }
    STATUS_MAP = {
        0: 'OK',
        4: 'NO PROG'
    }

    def __init__(self, raw):
        super().__init__(expected_id=ACK_ID,
                         raw=raw)
        (self.reason_code,
         self.module_id,
         self.status_code,
         self.sw_version) = self._values
        try:
            self.reason = self.REASON_MAP[self.reason_code]
        except KeyError:
            self.reason = 'unknown'
        try:
            self.status = self.STATUS_MAP[self.status_code]
        except KeyError:
            self.status = "unknown"


class MSG_status_system(RXMessage):
    """firmware system status message"""
    _format = ">HHBBBB"
    _filter = [(True, 0),
               (False, 0),
               (False, 0),
               (False, 0),
               (False, 0),
               (False, 0)]

    def __init__(self, raw):
        super().__init__(expected_id=0x0f00000,
                         raw=raw)
        (_,
         self.t15_voltage,
         self.temperature,
         self.fuel_level,
         self.output_request,
         self.function_request) = self._values


class MSG_status_voltage_current(RXMessage):
    """firmware voltage/current report"""
    _format = ">BBBBBBBB"
    _filter = [(False, 0),
               (False, 0),
               (False, 0),
               (False, 0),
               (False, 0),
               (False, 0),
               (False, 0),
               (False, 0)]

    def __init__(self, raw):
        super().__init__(expected_id=0x0f00001,
                         raw=raw)
        self.output_voltage = self._values[0:4]
        self.output_current = self._values[4:8]


class MSG_status_faults(RXMessage):
    """firmware fault status report"""
    _format = ">BBBBBBBB"
    _filter = [(False, 0),
               (False, 0),
               (False, 0),
               (False, 0),
               (True, 0x11),
               (True, 0x22),
               (True, 0x33),
               (False, 0)]

    def __init__(self, raw):
        super().__init__(expected_id=0x0f00002,
                         raw=raw)
        self.output_faults = self._values[0:4]
        self.system_faults = self._values[7]


class MSG_ecu_reply(RXMessage):
    """reply from CAS or JBE"""
    _format = ">BBBBBBBB"
    _filter = [(False, 0),
               (False, 0),
               (False, 0),
               (False, 0),
               (False, 0),
               (False, 0),
               (False, 0),
               (False, 0)]

    def __init__(self, raw, respondent):
        super().__init__(expected_id=0x600 | respondent,
                         raw=raw)
        self.recipient = self._values[0]
        self.sequence = self._values[1]
        if self.sequence == 0x10:
            self.length = self._values[2]
            self.data = self._values[3:]
        else:
            self.data = self._values[2:]


class CANInterface(object):
    def __init__(self, args):
        self._verbose = args.verbose
        # bootloader always signs on at 125kbps
        self._interface_type = args.interface_type
        self._interface = args.interface
        self._reinit(125000)
        self._detect(args.T15_at_start)

        # get a new interface at the runtime bitrate
        self._reinit(args.can_speed)

    def _reinit(self, bitrate):
        self._bus = can.interface.Bus(bustype=self._interface_type,
                                      channel=self._interface,
                                      bitrate=bitrate,
                                      sleep_after_open=0.2)

    def _detect(self, with_t15=False):
        """
        Power on the module and listen for it to sign on.
        Returns the ID of the detected module.
        """
        self.set_power_off()
        while self.recv(0.25) is not None:
            # drain buffered messages
            pass
        if with_t15:
            self.set_power_t30_t15()
        else:
            self.set_power_t30()
        while True:
            rsp = self.recv(2)
            if rsp is None:
                raise ModuleError('no power-on message from module')
            try:
                signon = MSG_ack(rsp)
                break
            except MessageError as e:
                raise ModuleError(f'unexpected power-on message '
                                  'from module: {rsp}')
        return signon.module_id

    def send(self, message):
        """send the message"""
        assert(message.dlc <= 8)
        self._bus.send(message, 1)
        if self._verbose:
            print(f'CAN SEND: {message}')

    def recv(self, timeout=2):
        """
        wait for a message

        Note the can module will barf if a bad message is received, so we need
        to catch this and retry
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            wait_time = deadline - time.time()
            try:
                message = self._bus.recv(wait_time)
                if self._verbose and message is not None:
                    print(f'CAN RECV: {message}')
                return message
            except Exception:
                pass
        return None

    def set_power_off(self):
        self.send(MSG_mjs_power(False, False))

    def set_power_t30(self):
        self.send(MSG_mjs_power(True, False))

    def set_power_t30_t15(self):
        self.send(MSG_mjs_power(True, True))


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
        self.message_errors += 1
        self._logger.log(f"CAN? {msg}")

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
            return f"{self.property / 1000:>6.3f}{self._suffix}"
        except Exception:
            return f"--.---{self._suffix}"


class CentiUnit(DispObj):
    def __init__(self, win, y, x, source, propname, index, suffix):
        super().__init__(win, y, x, source, propname, index)
        self._suffix = suffix

    @property
    def value(self):
        try:
            return f"{self.property / 100:>5.2f}{self._suffix}"
        except Exception:
            return f"--.--{self._suffix}"


class DeciUnit(DispObj):
    def __init__(self, win, y, x, source, propname, index, suffix):
        super().__init__(win, y, x, source, propname, index)
        self._suffix = suffix

    @property
    def value(self):
        try:
            return f"{self.property / 10:>4.1f}{self._suffix}"
        except Exception:
            return f"--.-{self._suffix}"


class Millivolts(MilliUnit):
    def __init__(self, win, y, x, source, propname, index=None):
        super().__init__(win, y, x, source, propname, index, "V")


class DeciVolts(DeciUnit):
    def __init__(self, win, y, x, source, propname, index=None):
        super().__init__(win, y, x, source, propname, index, "V")


class CentiAmps(CentiUnit):
    def __init__(self, win, y, x, source, propname, index=None):
        super().__init__(win, y, x, source, propname, index, "A")


class ByteUnit(DispObj):
    def __init__(self, win, y, x, source, propname, suffix):
        super().__init__(win, y, x, source, propname)
        self._suffix = suffix

    @property
    def value(self):
        try:
            return f"{self.property:3}{self._suffix}"
        except Exception:
            return f"---{self._suffix}"


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
        return f"{self.property:5}"


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
            return "ON " if self.property else "OFF"
        except Exception:
            return "---"


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
        return "-" * len(self._label) if self._state == 'none' else self._label


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
        return "-" * len(self._label)


class Logger(object):
    def __init__(self, win, args):
        self._verbose = args.verbose
        self._win = win
        if self._win is not None:
            self._win.addstr(0, 0, "initializing...\n")
            self._win.idlok(True)
            self._win.scrollok(True)
            self._win.refresh()
        self._cons_buf = ""

    def log_can(self, msg):
        if self._verbose:
            self.log(f"CAN: {msg}")

    def log_console(self, msg):
        if msg.arbitration_id != CONSOLE_ID:
            raise KeyError
        for idx in range(0, msg.dlc):
            if msg.data[idx] == 0:
                self.log(f"CONS: {self._cons_buf}", curses.A_BOLD)
                self._cons_buf = ""
            else:
                self._cons_buf += chr(msg.data[idx])

    def log(self, msg, attr=curses.A_DIM):
        if self._win is not None:
            self._win.addstr(f"{msg}\n", attr)
            self._win.refresh()
        else:
            print(f'{msg}')


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
        Flag(statwin, 7, 9, module_state, 'function_request', 0, "Brake"),
        Flag(statwin, 7, 15, module_state, 'function_request', 1, "Light"),
        Flag(statwin, 7, 21, module_state, 'function_request', 2, "Rain"),
        Fault(statwin, 8, 9, module_state, 'system_faults', 0, "T15"),
        Fault(statwin, 8, 13, module_state, 'system_faults', 1, "CAN"),
        Fault(statwin, 8, 17, module_state, 'system_faults', 2, "TEMP"),

        OnOff(statwin, 16, 7, monitor_state, 'sw_t15'),
        OnOff(statwin, 16, 20, monitor_state, 'sw_brake'),
        OnOff(statwin, 16, 34, monitor_state, 'sw_lights'),
        OnOff(statwin, 16, 46, monitor_state, 'sw_rain'),
        OnOff(statwin, 16, 57, monitor_state, 'sw_can'),
    ]
    for channel in range(0, 4):
        widgets += [
            Flag(statwin, 11 + channel, 12, module_state, 'output_request', channel, "ON"),
            DeciVolts(statwin, 11 + channel, 19, module_state, 'output_voltage', channel),
            CentiAmps(statwin, 11 + channel, 31, module_state, 'output_current', channel),
            Fault(statwin, 11 + channel, 43, module_state, 'output_faults', 0, "OPEN", channel),
            Fault(statwin, 11 + channel, 48, module_state, 'output_faults', 1, "STUCK", channel),
            Fault(statwin, 11 + channel, 54, module_state, 'output_faults', 2, "OVERLOAD", channel),
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
                msg = MSG_brake(monitor_state.sw_brake)
            else:
                msg = MSG_lights(False, monitor_state.sw_lights, monitor_state.sw_rain)
                # msg = MSG_lights(sw_brake, sw_lights, sw_rain)
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


# CAS / JBE emulator test
#
def do_cas_jbe_test(interface, args):

    logger = Logger(None, args)

    def get_part_response(respondent):
        deadline = time.time() + 2
        while time.time() < deadline:
            msg = interface.recv(0.2)
            if msg is not None:
                try:
                    logger.log_console(msg)
                except KeyError:
                    try:
                        return MSG_ecu_reply(msg, respondent)
                    except MessageError:
                        continue
        return None

    def get_response(respondent, cmd):
        reply = get_part_response(respondent)
        if reply is None:
            raise ModuleError('timed out waiting for initial response')

        if reply.recipient != 0xf1:
            raise MessageError(f'message not addressed correctly: {reply}')
        if reply.sequence != 0x10:
            raise MessageError(f'message has wrong sequence: {reply}')
        if reply.length < len(cmd):
            raise MessageError(f'message length is too short: {reply}')

        for i in range(0, len(cmd)):
            if reply.data[i] != cmd[i]:
                raise MessageError(f'command echo mismatch: {reply}')

        residual = reply.length - len(cmd)
        if (residual > 0):
            interface.send(MSG_scantool(respondent, 0x30, [0x00, 0x01]))
            seq = 0x21

            while (residual > 0):
                reply = get_part_response(respondent)
                if reply is None:
                    raise ModuleError('timed out waiting for continued response')
                if reply.sequence != seq:
                    raise MessageError(f'wrong response sequence: {reply}')
                seq += 1
                residual -= 6

    # T15 on
    interface.set_power_t30_t15()

    # stall / monitor console for a couple of seconds
    get_part_response(0xfffffff)

    # send HARDWARE_REFERENZ_LESEN to the CAS
    cmd = [0x1a, 0x80]
    interface.send(MSG_scantool(0x40, 0x02, cmd))
    get_response(0x40, cmd)

    # read the VIN from the CAS
    cmd = [0x22, 0x10, 0x10]
    interface.send(MSG_scantool(0x40, 0x03, cmd))
    get_response(0x40, cmd)

    # expect a reply with the expected VIN

    # CA_FA_LESEN block 0
    cmd = [0x22, 0x3f, 0x00]
    interface.send(MSG_scantool(0x40, 0x03, cmd))
    get_response(0x40, cmd)

    # CA_FA_LESEN block 1
    cmd = [0x22, 0x3f, 0x01]
    interface.send(MSG_scantool(0x40, 0x03, cmd))
    get_response(0x40, cmd)

    # CA_FA_LESEN block 2
    cmd = [0x22, 0x3f, 0x02]
    interface.send(MSG_scantool(0x40, 0x03, cmd))
    get_response(0x40, cmd)

    # CA_FA_LESEN block 3
    cmd = [0x22, 0x3f, 0x03]
    interface.send(MSG_scantool(0x40, 0x03, cmd))
    get_response(0x40, cmd)

    # CA_FA_LESEN block 4
    cmd = [0x22, 0x3f, 0x04]
    interface.send(MSG_scantool(0x40, 0x03, cmd))
    get_response(0x40, cmd)

    # ???
    cmd = [0x30, 0x01, 0x01]
    interface.send(MSG_scantool(0x40, 0x03, cmd))
    get_response(0x40, cmd)

    # ???
    cmd = [0x30, 0x01, 0x01]
    interface.send(MSG_scantool(0x40, 0x03, cmd))
    get_response(0x40, cmd)

    # CA_FA_LESEN block 0 (repeated)
    cmd = [0x22, 0x3f, 0x00]
    interface.send(MSG_scantool(0x40, 0x03, cmd))
    get_response(0x40, cmd)

    # send HARDWARE_REFERENZ_LESEN to the broadcast address
    cmd = [0x1a, 0x80]
    interface.send(MSG_scantool(0xed, 0x02, cmd))

    # expect a reply from CAS
    get_response(0x40, cmd)

    # expect a reply from JBE
    get_response(0x00, cmd)


parser = argparse.ArgumentParser(description='E36 tail module tester')
parser.add_argument('--interface',
                    type=str,
                    required=True,
                    metavar='INTERFACE_NAME',
                    help='interface name or path')
parser.add_argument('--interface-type',
                    type=str,
                    metavar='INTERFACE_TYPE',
                    default='slcan',
                    help='interface type')
parser.add_argument('--can-speed',
                    type=int,
                    default=125000,
                    metavar='BITRATE',
                    help='CAN bitrate')
parser.add_argument('--no-CAN-at-start',
                    action='store_true',
                    help='disable vehicle CAN emulation at start')
parser.add_argument('--T15-at-start',
                    action='store_true',
                    help='turn on T15 with T30')
parser.add_argument('--verbose',
                    action='store_true',
                    help='print verbose progress information')

actiongroup = parser.add_mutually_exclusive_group(required=True)
actiongroup.add_argument('--monitor',
                         action='store_true',
                         help='interactive monitor')
actiongroup.add_argument('--cas-jbe',
                         action='store_true',
                         help='test the CAS / JBE emulator')


args = parser.parse_args()
interface = None
try:
    interface = CANInterface(args)
    if args.monitor:
        curses.wrapper(do_monitor, interface, args)
    elif args.cas_jbe:
        do_cas_jbe_test(interface, args)
except KeyboardInterrupt:
    pass
except ModuleError as err:
    print(f'MODULE ERROR: {err}')
except MessageError as err:
    print(f'MESSAGE ERROR: {err}')
if interface is not None:
    interface.set_power_off()
