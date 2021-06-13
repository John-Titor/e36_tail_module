#!/usr/bin/env python3

import can
import struct


class MessageError(Exception):
    """a received message was not as expected"""
    pass


class ModuleError(Exception):
    """the module did something unexpected"""
    pass


class Message(object):
    """
    Abstract class for CAN messages.

    Concrete class attributes:

    _format     struct.pack script for packing args when constructing
                a message from fields, or unpacking a raw message
    _filter     (optional) used when unpacking a raw message to validate
                fields
    """
    _arbid = None
    _filter = None

    def __init__(self, raw):
        """parse a raw message and set attributes"""
        if self._arbid is not None and raw.arbitration_id != self._arbid:
            raise MessageError(f'expected message with ID 0x{self._arbid:x} '
                               f'but got {raw}')
        expected_dlc = struct.calcsize(self._format)
        if raw.dlc != expected_dlc:
            raise MessageError(f'expected message with length {expected_dlc} '
                               f'but got {raw}')

        self._raw = raw
        self._data = raw.data
        self._values = struct.unpack(self._format, self._data)
        if self._filter is not None:
            for (index, (check, value)) in enumerate(self._filter):
                if check and value != self._values[index]:
                    raise MessageError(f'message field {index} is '
                                       f'0x{self._values[index]:x} '
                                       f'but expected 0x{value:x}')

    @classmethod
    def with_fields(cls, *args):
        """construct from individual fields"""
        return cls.with_id_and_fields(cls._arbid, *args)
        return cls(raw)

    @classmethod
    def with_id_and_fields(cls, arbid, *args):
        """construct from individual fields"""
        raw = can.Message(arbitration_id=arbid,
                          is_extended_id=cls._extended,
                          dlc=struct.calcsize(cls._format),
                          data=struct.pack(cls._format, *args))
        return cls(raw)

    @classmethod
    def len(self):
        return struct.calcsize(self._format)

    @property
    def raw(self):
        return self._raw

    def __str__(self):
        return f'{self._raw}'


class MSG_mjs_power(Message):
    """mjs adapter power control message"""
    _format = '>B'
    _arbid = 0x0fffffff
    _extended = True

    @classmethod
    def with_fields(cls, t30_state, t15_state):
        if not t30_state:
            arg = 0x00
        elif not t15_state:
            arg = 0x01
        else:
            arg = 0x03
        return super().with_fields(arg)


class MSG_brake(Message):
    """BMW brake (etc.) status message"""
    _format = '>BHHBBB'
    _arbid = 0x0a8
    _extended = False

    @classmethod
    def with_fields(cls, brake_state):
        return super().with_fields(0x54,              # magic
                                   0,                 # actual torque
                                   0,                 # rounded torque
                                   240,               # clutch not depressed
                                   0x0f,              # magic
                                   32 if brake_state else 3)


class MSG_lights(Message):
    """BMW light control message"""
    _format = '>BBB'
    _arbid = 0x21a
    _extended = False

    @classmethod
    def with_fields(cls, brake_light, tail_light, rain_light):
        return super().with_fields(((0x80 if brake_light else 0) |
                                    (0x04 if tail_light else 0) |
                                    (0x40 if rain_light else 0)),
                                   0,
                                   0xf7)


class MSG_BMW_parameter(Message):
    """BMW parameter query/response"""
    _format = '>BBBBBBBB'
    _extended = False

    def __init__(self, raw):
        super().__init__(raw=raw)
        if ((raw.arbitration_id & 0xf00) != 0x600) or (raw.dlc != 8):
            raise MessageError('not a BMW parameter message')
        self.sender = raw.arbitration_id & 0xff
        self.recipient = self._values[0]
        self.sequence = self._values[1]
        if self.sequence == 0x10:
            self.length = self._values[2]
            self.data = self._values[3:]
        else:
            self.data = self._values[2:]

    @classmethod
    def short_with_fields(cls, sender, recipient, cmd):
        """short parameter message"""
        length = len(cmd)
        cmd_bytes = cmd
        while len(cmd_bytes) < 6:
            cmd_bytes = cmd_bytes + [0]
        return super().with_id_and_fields(0x600 | sender,
                                          recipient,
                                          length,
                                          *cmd_bytes)

    @classmethod
    def long_with_initial_fields(cls, sender, recipient, length, cmd):
        """first part of a long message"""
        cmd_bytes = cmd
        while len(cmd_bytes) < 5:
            cmd_bytes = cmd_bytes + [0]
        return super().with_id_and_fields(0x600 | sender,
                                          recipient,
                                          0x10,
                                          length,
                                          *cmd_bytes)

    @classmethod
    def long_with_continuation_fields(cls, sender, recipient, sequence, cmd):
        """second or later part of a long message"""
        cmd_bytes = cmd
        while len(cmd_bytes) < 6:
            cmd_bytes = cmd_bytes + [0]
        return super().with_id_and_fields(0x600 | sender,
                                          recipient,
                                          sequence,
                                          *cmd_bytes)

    @classmethod
    def continuation_request(cls, sender, recipient):
        """request to the recipient to send the remainder of a message"""
        return super().with_id_and_fields(0x600 | sender,
                                          recipient,
                                          0x30,
                                          0x00,
                                          0x01,
                                          0x00,
                                          0x00,
                                          0x00,
                                          0x00)


class MSG_ack(Message):
    """broadcast message sent by module on power-up, reboot or crash"""
    _format = '>BIBH'
    _arbid = 0x1ffffff0
    _extended = True

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
        super().__init__(raw=raw)
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
            self.status = 'unknown'


class MSG_status_system(Message):
    """firmware system status message"""
    _format = '>HHBBBB'
    _arbid = 0x0f00000
    _extended = True
    _filter = [(True, 0),
               (False, 0),
               (False, 0),
               (False, 0),
               (False, 0),
               (False, 0)]

    def __init__(self, raw):
        super().__init__(raw=raw)
        (_,
         self.t15_voltage,
         self.temperature,
         self.fuel_level,
         self.output_request,
         self.function_request) = self._values


class MSG_status_voltage_current(Message):
    """firmware voltage/current report"""
    _format = '>BBBBBBBB'
    _arbid = 0x0f00001
    _extended = True

    def __init__(self, raw):
        super().__init__(raw=raw)
        self.output_voltage = self._values[0:4]
        self.output_current = self._values[4:8]


class MSG_status_faults(Message):
    """firmware fault status report"""
    _format = '>BBBBBBBB'
    _arbid = 0x0f00002
    _extended = True
    _filter = [(False, 0),
               (False, 0),
               (False, 0),
               (False, 0),
               (True, 0x11),
               (True, 0x22),
               (True, 0x33),
               (False, 0)]

    def __init__(self, raw):
        super().__init__(raw=raw)
        self.output_faults = self._values[0:4]
        self.system_faults = self._values[7]


class MSG_status_dde(Message):
    """resent DDE status for AiM unit"""
    _format = '>HHHH'
    _arbid = 0x700
    _extended = False

    def __init__(self, raw):
        super().__init__(raw=raw)
        (self.fuel_temp,
         self.intake_temp,
         self.exhaust_temp,
         self.manifold_pressure) = self._values

