#!/usr/bin/env python3

import can
import struct


class MessageError(Exception):
    """a received message was not as expected"""
    pass


class MessageFormat(object):
    """
    Base class for message formats. Handles parsing and generating CAN frames.

    Concrete class attributes:

    _arbid      CAN arbitration ID expected at matching time, or forced
                when generating. May be None.
    _extended   Whether _arbid is (expected to be) an extended ID.
    _format     struct.pack script for packing args when constructing
                a message from fields, or unpacking a raw message. Required.
    _keys       list of keys corresponding to fields in _format, keys whose names 
                begin with '_' are ignored when unpacking.
    _filter     dict containing values to verify against keys to determine message
                validity.
    """
    _arbid = None
    _extended = False
    _format = None
    _fields = None

    def __init__(self, raw):
        """parse a raw message, verify it conforms, and set attributes"""
        raise RuntimeError('cannot instantiate')

    @classmethod
    def unpack(cls, message):
        if cls._arbid is not None and message.arbitration_id != cls._arbid:
            raise MessageError(f'arbitration id mismatch')
        if cls._extended is not None and message.is_extended_id != cls._extended:
            raise MessageError(f'arbitration id type mismatch')
        expected_dlc = struct.calcsize(cls._format)
        if message.dlc != expected_dlc:
            raise MessageError(f'dlc mismatch')

        values = {
            'arbitration_id': message.arbitration_id,
            'is_extended_id': message.is_extended_id,
            'dlc': message.dlc,
            'timestamp': message.timestamp,
            'data': message.data,
        }
        for key, value in zip(cls._fields.keys(), struct.unpack(cls._format, message.data)):
            required_value = cls._fields[key]
            if required_value is not None and required_value != value:
                raise MessageError(f'required value {key} mismatch')
            if not key.startswith('_'):
                values[key] = value

        return values

    @classmethod
    def message(cls, **kwargs):
        """
        Generate a conforming CAN message with supplied arbitration ID and values.
        Values are expected as keyword arguments; missing values are searched for in
        _filter as well.
        """
        if 'arbitration_id' in kwargs:
            arbid = kwargs['arbitration_id']
        else:
            arbid = cls._arbid

        arglist = list()
        for key in cls._fields.keys():
            if key in kwargs:
                arglist.append(kwargs[key])
            else:
                arglist.append(cls._fields[key])

        return can.Message(arbitration_id=arbid,
                           is_extended_id=cls._extended,
                           dlc=struct.calcsize(cls._format),
                           data=struct.pack(cls._format, *arglist))

    @classmethod
    def len(self):
        return struct.calcsize(cls._format)


class MSG_DDE_torque_brake(MessageFormat):
    """BMW brake status message from the DDE"""
    _format = '<BHHBBB'
    _arbid = 0x0a8
    _fields = {
        '_0': 0x54,             # magic
        '_1': 0,                # actual torque
        '_2': 0,                # rounded torque
        '_3': 0xf0,             # clutch not depressed
        '_4': 0x0f,             # magic
        'brake_state': None,
    }

    BRAKE_ON = 32
    BRAKE_OFF = 3

    @classmethod
    def message(cls, brake_state):
        if brake_state not in (cls.BRAKE_ON, cls.BRAKE_OFF):
            brake_state = cls.BRAKE_ON if brake_state else cls.BRAKE_OFF
        return super().message(brake_state=brake_state)


class MSG_DDE_rpm_tps(MessageFormat):
    """BMW engine speed and throttle position from the DDE"""
    _format = '<HHHH'
    _arbid = 0xaa
    _fields = {
        '_0': 0,
        'tps': None,
        'rpm': None,
        '_1': 0,
    }


class MSG_DDE_coolant(MessageFormat):
    """BMW engine coolant temperature from the DDE"""
    _format = '<B7s'
    _arbid = 0x1d0
    _fields = {
        'coolant_temp': None,
        '_0': b'\0' * 7,
    }


class MSG_EGS_gear(MessageFormat):
    """BMW selected gear from the EGS"""
    _format = '<B7s'
    _arbid = 0x1d2
    _fields = {
        'selected_gear': None,
        '_0': b'\0' * 7,
    }


class MSG_lights(MessageFormat):
    """BMW light control message"""
    _format = '>BBB'
    _arbid = 0x21a
    _fields = {
        'light_status': None,
        '_0': 0,
        '_1': 0xf7,
    }

    BRAKE_LIGHT = 0x80
    RAIN_LIGHT = 0x40
    TAIL_LIGHT = 0x04

    @classmethod
    def message(cls, brake_light, tail_light, rain_light):
        return super().message(light_status=((0x80 if brake_light else 0) |
                                             (0x04 if tail_light else 0) |
                                             (0x40 if rain_light else 0)))


class MSG_ack(MessageFormat):
    """broadcast message sent by module on power-up, reboot or crash"""
    _format = '>BIBH'
    _arbid = 0x1ffffff0
    _extended = True
    _fields = {
        'reason_code': None,
        'module_id': None,
        'status_code': None,
        'sw_version': None,
    }

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


class MSG_status_system(MessageFormat):
    """module system status message"""
    _format = '>HHBBBB'
    _arbid = 0x0f00000
    _extended = True
    _fields = {
        '_0': 0,
        't15_voltage': None,
        'temperature': None,
        'fuel_level': None,
        'output_request': None,
        'function_request': None,
    }


class MSG_status_voltage_current(MessageFormat):
    """module voltage/current report"""
    _format = '>4s4s'
    _arbid = 0x0f00001
    _extended = True
    _fields = {
        'output_voltage': None,
        'output_current': None,
    }


class MSG_status_faults(MessageFormat):
    """module fault status report"""
    _format = '>4sBBBB'
    _arbid = 0x0f00002
    _extended = True
    _fields = {
        'output_faults': None,
        '_0': 0x11,
        '_1': 0x22,
        '_2': 0x33,
        'system_faults': None,
    }


class MSG_module_dde_status(MessageFormat):
    """module-echoed DDE status for AiM unit"""
    _format = '>HHHH'
    _arbid = 0x700
    _extended = False
    _fields = {
        'fuel_temp': None,
        'intake_temp': None,
        'exhaust_temp': None,
        'manifold_pressure': None,
    }


class MSG_DDE_PID_request(MessageFormat):
    """ISO-TP encoded single PID request to the DDE"""
    _arbid = 0x6f1
    _format = '>BBBB2s2s'
    _extended = False
    _fields = {
        '_0': 0x12,         # for DDE
        '_1': 4,            # ISO-TP single frame, 4 bytes of data
        '_2': 0x2c,         # get value ...
        '_3': 0x10,         # ... by PID
        'pid_id': None,     # PID
        '_4': b'\0' * 2,    # zeros
    }


class MSG_DDE_PID_response(MessageFormat):
    """ISO-TP encoded single PID reply from the DDE"""
    _arbid = 0x612
    _format = '>BBBB2s2s'
    _extended = False
    _fields = {
        '_0': 0xf1,
        'msglen': None,
        '_1': 0x6c,
        '_2': 0x10,
        'pid_value': None,
        '_3': b'\x55' * 2
    }

    @classmethod
    def message(cls, pid_id, pid_value):
        if len(pid_value) == 1:
            msglen = 3
            value = pid_value + b'\x55'
        else:
            msglen = 4
            value = pid_value
        return super().message(msglen=msglen,
                               pid_id=pid_id,
                               pid_value=value)


class MSG_EGS_PID_request(MessageFormat):
    """ISO-TP encoded single PID request to the EGS"""
    _arbid = 0x6f1
    _format = '>BBBB'
    _extended = False
    _fields = {
        '_0': 0x18,         # for EGS
        '_1': 2,            # ISO-TP single frame, 2 bytes of data
        '_2': 0x21,         # get value by PID
        'pid_id': None,     # PID
    }


class MSG_EGS_PID_response(MessageFormat):
    """ISO-TP encoded single PID reply from the EGS"""
    _arbid = 0x618
    _format = '>BBBBB3s'
    _extended = False
    _fields = {
        '_0': 0xf1,
        '_1': 3,
        '_2': 0x61,
        'pid_id': None,
        'pid_value': None,
        '_3': b'\0' * 3,
    }

    @classmethod
    def message(cls, pid_id, pid_value):
        if len(pid_value) == 1:
            msglen = 5
            value = pid_value + b'\0'
        else:
            msglen = 6
            value = pid_value
        return super().message(msglen=msglen,
                               pid_id=pid_id,
                               pid_value=value)


class MSG_ISO_TP_single(MessageFormat):
    """ISO-TP single message"""
    _format = '>BB6s'
    _extended = False
    _fields = {
        'recipient': None,
        'type_length': None,
        'payload': b'\x00\x00\x00\x00\x00\x00'
    }

    @classmethod
    def message(cls, sender, recipient, data):
        type_length=len(data)
        while len(data) < 6:
            data += b'\0'
        return super().message(arbitration_id=0x600 + sender,
                               recipient=recipient,
                               type_length=type_length,
                               payload=data)


class MSG_ISO_TP_initial(MessageFormat):
    """ISO-TP initial message"""
    _format = '>BBB5s'
    _extended = False
    _fields = {
        'recipient': None,
        'type_length_hi': None,
        'length_lo': None,
        'payload': None
    }

    @classmethod
    def message(cls, sender, recipient, data):
        return super().message(arbitration_id=0x600 + sender,
                               recipient=recipient,
                               type_length_hi=0x10 + (len(data) >> 8),
                               length_lo=len(data) & 0xff,
                               payload=data[:5])


class MSG_ISO_TP_consecutive(MessageFormat):
    """ISO-TP continuation message"""
    _format = '>BB6s'
    _extended = False
    _fields = {
        'recipient': None,
        'type_sequence': None,
        'payload': None
    }

    @classmethod
    def message(cls, sender, recipient, sequence, data):
        return super().message(arbitration_id=0x600 + sender,
                               recipient=recipient,
                               type_sequence=0x20 | sequence,
                               payload=data[:6])


class MSG_ISO_TP_flow_continue(MessageFormat):
    """ISO-TP flow-continue request"""
    _format = '>BBBB'
    _extended = False
    _fields = {
        'recipient': None,
        '_0': 0x30,     # flow control continue
        '_1': 0x00,     # send all messages
        '_2': 0x01      # at 1ms pacing
    }

    @classmethod
    def message(cls, sender, recipient):
        return super().message(arbitration_id=0x600 + sender,
                               recipient=recipient)
